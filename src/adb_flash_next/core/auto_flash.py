"""Pure logic for the Auto Flash workflow (no Qt): stages, serial matching, Android boot check.

Safety principles:
  * Nothing is assumed: a device is only used when its serial / state was verified.
  * The boot check only READS (adb devices / getprop sys.boot_completed).
  * 100% is only reported once Android answered sys.boot_completed = 1.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from adb_flash_next.core.adb_client import AdbClient
from adb_flash_next.core.parsers import AdbListEntry
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult, run_command


# ------------------------------------------------------------------------------ stages
class AutoStage(str, Enum):
    IDLE = "idle"
    CHECKING = "checking"
    EXTRACTING = "extracting"  # optional: partitions are taken from the ROM with payload-dumper-go
    FLASHING = "flashing"
    RECOVERY = "recovery"  # paused: the user works on the phone
    SIDELOAD = "sideload"
    BOOT = "boot"  # waiting for Android (or stuck and waiting for a manual re-check)
    DONE = "done"


STEP_TITLES = (
    "Check the device and the bootloader",
    "Extract (if chosen) and flash the partitions",
    "Recovery: format data (if needed) and start ADB sideload",
    "Sideload the ROM ZIP",
    "Wait for Android to start",
)

_ACTIVE_INDEX = {
    AutoStage.CHECKING: 0,
    AutoStage.EXTRACTING: 1,
    AutoStage.FLASHING: 1,
    AutoStage.RECOVERY: 2,
    AutoStage.SIDELOAD: 3,
    AutoStage.BOOT: 4,
}


def step_states(stage: AutoStage, failed: bool = False) -> list[str]:
    """'pending' / 'active' / 'done' / 'failed' for each of the five steps."""
    count = len(STEP_TITLES)
    if stage is AutoStage.IDLE:
        return ["pending"] * count
    if stage is AutoStage.DONE:
        return ["done"] * count
    active = _ACTIVE_INDEX[stage]
    return ["done"] * active + ["failed" if failed else "active"] + ["pending"] * (count - active - 1)


# ----------------------------------------------------------------- which device gets the ZIP
@dataclass(frozen=True)
class SerialChoice:
    serial: str | None  # None = do not send anything
    needs_confirmation: bool  # the serial differs from the Fastboot one: the user must agree
    message: str


def choose_sideload_serial(entries: Sequence[AdbListEntry], fastboot_serial: str) -> SerialChoice:
    """Decide which ADB device may receive the ZIP.

    The Fastboot serial is used when it is in sideload mode. Some phones report another serial
    in recovery: only if exactly ONE ADB device is visible, and it is in sideload mode, is it
    offered - and only after the user explicitly confirms.
    """
    states = {entry.serial: entry.state for entry in entries}
    if fastboot_serial in states:
        state = states[fastboot_serial]
        if state == "sideload":
            return SerialChoice(fastboot_serial, False, "")
        return SerialChoice(
            None, False,
            f"The device is in ADB state '{state}', not in sideload mode. Nothing was sent. Start ADB "
            "sideload on the device (for example Apply update > Apply from ADB) and press Sideload again.",
        )
    sideload = [entry for entry in entries if entry.state == "sideload"]
    if len(entries) == 1 and len(sideload) == 1:
        other = sideload[0].serial
        return SerialChoice(
            other, True,
            f"The device in sideload mode has serial {other}, which differs from the Fastboot serial "
            f"{fastboot_serial}. Some phones report a different serial in recovery.",
        )
    if not entries:
        return SerialChoice(
            None, False,
            "No device is visible to ADB. Nothing was sent. Check the cable, enter recovery and start "
            "ADB sideload on the phone, then press Sideload again.",
        )
    return SerialChoice(
        None, False,
        f"The device {fastboot_serial} is not visible to ADB in sideload mode (ADB sees {len(entries)} "
        "other device(s)). Nothing was sent. Disconnect other devices or start ADB sideload on the right one.",
    )


# ------------------------------------------------------------------- the Android boot check
class BootState(str, Enum):
    WAITING = "waiting"
    RECOVERY = "recovery"
    BOOTING = "booting"
    UNAUTHORIZED = "unauthorized"
    BOOTED = "booted"
    ERROR = "error"


def check_boot_completed(
    tools: PlatformTools,
    serial: str,
    cancel_event: threading.Event | None = None,
    runner: Callable[..., CommandResult] = run_command,
) -> tuple[BootState, str]:
    """One read-only check. Never changes anything on the device."""
    client = AdbClient(tools.adb, runner)
    entries, listing = client.list_devices(cancel_event)
    if listing.cancelled:
        return BootState.WAITING, "Stopped."
    if not listing.ok:
        return BootState.ERROR, f"ADB device list failed: {listing.failure_reason()}"

    state = next((entry.state for entry in entries if entry.serial == serial), None)
    if state is None:
        return BootState.WAITING, "Waiting for the device to appear in ADB..."
    if state in ("sideload", "recovery", "rescue"):
        return BootState.RECOVERY, (
            "The device is still in recovery. When the install has finished, choose 'Reboot system now' "
            "on the phone."
        )
    if state == "unauthorized":
        return BootState.UNAUTHORIZED, (
            "Android seems to be running but ADB is not authorized on this computer, so the startup "
            "cannot be confirmed. Unlock the phone, accept the USB debugging prompt and press Check again."
        )
    if state != "device":
        return BootState.WAITING, f"The device is in ADB state '{state}'. Waiting..."

    value, result = client.get_property(serial, "sys.boot_completed", cancel_event)
    if result.cancelled:
        return BootState.WAITING, "Stopped."
    if not result.ok:
        return BootState.WAITING, f"The device did not answer yet ({result.failure_reason()}). Waiting..."
    if value == "1":
        return BootState.BOOTED, "Android has started (sys.boot_completed = 1)."
    return BootState.BOOTING, "Android is starting (boot not completed yet)..."


@dataclass(frozen=True)
class BootResult:
    booted: bool
    state: BootState
    message: str
    cancelled: bool = False
    timed_out: bool = False


def wait_for_boot(
    tools: PlatformTools,
    serial: str,
    on_state: Callable[[BootState, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    timeout_seconds: float = 1200.0,
    interval_seconds: float = 3.0,
    runner: Callable[..., CommandResult] = run_command,
    sleep: Callable[[float], object] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> BootResult:
    """Poll until Android reports it has booted. Stops on cancel, timeout or missing authorization."""
    if sleep is None:
        sleep = cancel_event.wait if cancel_event is not None else time.sleep
    started = clock()
    last: tuple[BootState, str] | None = None
    while True:
        if cancel_event is not None and cancel_event.is_set():
            return BootResult(False, BootState.WAITING, "Stopped waiting for Android.", cancelled=True)
        state, message = check_boot_completed(tools, serial, cancel_event, runner)
        if (state, message) != last:
            last = (state, message)
            if on_state is not None:
                on_state(state, message)
        if state is BootState.BOOTED:
            return BootResult(True, state, message)
        if state is BootState.UNAUTHORIZED:
            return BootResult(False, state, message)
        if clock() - started >= timeout_seconds:
            minutes = int(timeout_seconds // 60)
            return BootResult(
                False, state,
                f"Android did not finish starting within {minutes} minutes (last status: {message}) "
                "Check the phone, then press Check again.",
                timed_out=True,
            )
        sleep(interval_seconds)
