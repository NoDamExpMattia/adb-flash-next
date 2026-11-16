"""ROM ZIP checks and the `adb sideload` workflow.

Honest limits:
  * ZIP checks only look at the archive's file list. They cannot prove the ROM is right
    for the device or correctly signed.
  * `adb sideload` reports how much of the file the PHONE has requested, not how far the
    installation inside the recovery has got. The final result must be confirmed on the
    device and by the later boot check.
"""
from __future__ import annotations

import re
import subprocess
import threading
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from adb_flash_next.core.adb_client import AdbClient
from adb_flash_next.core.models import ConnectionMode, DeviceInfo, Transport
from adb_flash_next.core.parsers import validate_serial
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult, run_command, run_streaming

LEVEL_OK = "OK"
LEVEL_WARNING = "WARNING"
LEVEL_ERROR = "ERROR"

_INSTALLABLE_MARKERS = (
    "meta-inf/com/google/android/update-binary",
    "meta-inf/com/google/android/updater-script",
    "meta-inf/com/android/metadata",
    "payload.bin",
)

_PERCENT_PATTERNS = (
    re.compile(r"\(~?\s*(\d{1,3})\s*%\)"),  # serving: 'rom.zip'  (~47%)
    re.compile(r"(\d{1,3})\s*%"),
)


# --------------------------------------------------------------------------- ZIP check
@dataclass(frozen=True)
class ZipCheck:
    path: Path
    size: int | None
    level: str  # LEVEL_OK / LEVEL_WARNING / LEVEL_ERROR
    message: str


def validate_rom_zip(path: Path) -> ZipCheck:
    """Check that `path` is a readable ZIP and say whether it looks installable from recovery."""
    path = Path(path)
    try:
        stat = path.stat()
    except OSError as exc:
        return ZipCheck(path, None, LEVEL_ERROR, f"File not found or unreadable ({exc.strerror or exc}).")
    if not path.is_file():
        return ZipCheck(path, None, LEVEL_ERROR, "Not a regular file.")
    if stat.st_size == 0:
        return ZipCheck(path, 0, LEVEL_ERROR, "The file is empty.")
    try:
        if not zipfile.is_zipfile(path):
            return ZipCheck(path, stat.st_size, LEVEL_ERROR, "This is not a valid ZIP archive.")
        with zipfile.ZipFile(path) as archive:
            names = [name.lower() for name in archive.namelist()]
    except (zipfile.BadZipFile, OSError) as exc:
        return ZipCheck(path, stat.st_size, LEVEL_ERROR, f"The ZIP could not be read ({exc}).")

    installable = any(marker in names for marker in _INSTALLABLE_MARKERS)
    if not installable:
        has_images = any(name.endswith(".img") for name in names)
        detail = (
            "It contains .img files, which suggests a Fastboot package rather than a recovery ROM. "
            if has_images
            else ""
        )
        return ZipCheck(
            path,
            stat.st_size,
            LEVEL_WARNING,
            f"This ZIP does not look like a recovery-installable package. {detail}"
            "Sideloading it will most likely fail. Only continue if your ROM's instructions say so.",
        )
    suffix = "" if path.name.lower().endswith(".zip") else " The file does not have the .zip extension."
    return ZipCheck(
        path,
        stat.st_size,
        LEVEL_OK if not suffix else LEVEL_WARNING,
        "Recovery-installable package detected. This does not guarantee it is the right ROM for "
        "your device." + suffix,
    )


# ------------------------------------------------------------------ device readiness
def sideload_readiness(device: DeviceInfo | None) -> tuple[bool, str, str]:
    """(ready, short status text, hint) for sideloading to `device`."""
    if device is None:
        return False, "No device selected", (
            "Connect the device and select it on the Dashboard. If several are connected, choose one."
        )
    if device.transport is Transport.ADB and device.mode is ConnectionMode.SIDELOAD:
        return True, "Device is in sideload mode", ""
    if device.transport is Transport.ADB and device.mode is ConnectionMode.RECOVERY:
        return False, "Device is in recovery", (
            "Now choose 'Apply update', then 'Apply from ADB' (or 'ADB Sideload') on the device."
        )
    if device.transport is Transport.FASTBOOT:
        return False, f"Device is in {device.mode.value}", (
            "Boot into recovery first (see step 1). Sideload does not work from Fastboot."
        )
    if device.mode is ConnectionMode.ANDROID:
        return False, "Device is running Android", (
            "Boot into recovery first (see step 1), then start ADB sideload on the device."
        )
    return False, f"Device mode: {device.mode.value}", (
        "The device must be in recovery's ADB sideload mode."
    )


def command_preview(serial: str, path: Path) -> str:
    """Display-only command line."""
    return subprocess.list2cmdline(["adb", "-s", serial, "sideload", str(path)])


# ------------------------------------------------------------------------ the command
def build_sideload_command(tools: PlatformTools, serial: str, path: Path) -> list[str]:
    """Full argument list. The serial is validated and always passed with -s."""
    rom = Path(path)
    if not rom.is_file():
        raise ValueError(f"ROM file not found: {rom}")
    return [str(tools.adb), "-s", validate_serial(serial), "sideload", str(rom.resolve())]


def parse_progress(text: str) -> int | None:
    """Percent from one line of adb output, or None when the line carries no percentage."""
    for pattern in _PERCENT_PATTERNS:
        match = pattern.search(text)
        if match:
            value = int(match.group(1))
            if 0 <= value <= 100:
                return value
    return None


# ------------------------------------------------------------------------- the result
class SideloadOutcome(str, Enum):
    COMPLETED = "completed"  # adb exited with code 0
    INCONCLUSIVE = "inconclusive"  # transfer ended in a way that must be confirmed on the phone
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SideloadResult:
    outcome: SideloadOutcome
    message: str
    last_percent: int | None = None
    command_line: str = ""
    returncode: int | None = None
    output_tail: str = ""


def _tail(text: str, lines: int = 6) -> str:
    kept = [line for line in text.splitlines() if line.strip()][-lines:]
    return "\n".join(kept)


def classify(result: CommandResult, last_percent: int | None) -> SideloadResult:
    """Turn the finished adb command into an outcome. Never reports success unless adb did."""
    base = dict(
        last_percent=last_percent,
        command_line=result.command_line if result.args else "",
        returncode=result.returncode,
        output_tail=_tail(result.combined_output),
    )
    lowered = result.combined_output.lower()

    if result.cancelled:
        return SideloadResult(
            SideloadOutcome.CANCELLED,
            "Sideload cancelled. The ROM was not installed (or its state is unknown): check the "
            "phone's screen. You may need to start ADB sideload again on the device.",
            **base,
        )
    if result.error:
        return SideloadResult(SideloadOutcome.FAILED, f"adb could not be started: {result.error}", **base)
    if result.timed_out:
        return SideloadResult(SideloadOutcome.FAILED, "The sideload took longer than the allowed time and was stopped.", **base)
    if result.returncode == 0:
        return SideloadResult(
            SideloadOutcome.COMPLETED,
            "adb finished sending the ROM (exit code 0). This is NOT yet proof that the ROM installed: "
            "check the phone's screen, reboot when it says the install is done, and wait for Android to start.",
            **base,
        )
    if "failed to read command: success" in lowered:
        return SideloadResult(
            SideloadOutcome.INCONCLUSIVE,
            "adb ended with a message that many recoveries produce when the transfer is complete, but "
            "it also exited with an error code. Check the phone's screen for the real install result "
            "before doing anything else.",
            **base,
        )
    if (
        "no devices/emulators found" in lowered
        or "device offline" in lowered
        or ("device '" in lowered and "not found" in lowered)
        or ("error:" in lowered and "closed" in lowered)
    ):
        return SideloadResult(
            SideloadOutcome.FAILED,
            "The device disconnected during the sideload. Check the cable, make sure the phone is still "
            "in ADB sideload mode, and try again.",
            **base,
        )
    return SideloadResult(SideloadOutcome.FAILED, f"adb sideload failed: {result.failure_reason()}", **base)


# ------------------------------------------------------------------------- the workflow
ProgressFn = Callable[[int], None]
LineFn = Callable[[str, str], None]  # (level, message)


def run_sideload(
    tools: PlatformTools,
    serial: str,
    rom_path: Path,
    on_progress: ProgressFn | None = None,
    on_log: LineFn | None = None,
    cancel_event: threading.Event | None = None,
    list_runner: Callable[..., CommandResult] = run_command,
    streamer: Callable[..., CommandResult] = run_streaming,
    max_seconds: float | None = 4 * 3600,
) -> SideloadResult:
    """Pre-flight checks, then `adb -s <serial> sideload <zip>` with live progress."""

    def log(level: str, message: str) -> None:
        if on_log is not None:
            on_log(level, message)

    failed = lambda message: SideloadResult(SideloadOutcome.FAILED, message)  # noqa: E731

    check = validate_rom_zip(rom_path)
    if check.level == LEVEL_ERROR:
        return failed(f"The ROM file cannot be used: {check.message}")

    try:
        command = build_sideload_command(tools, serial, rom_path)
    except ValueError as exc:
        return failed(str(exc))

    # Fresh check right before starting: the selected device must STILL be in sideload mode.
    entries, listing = AdbClient(tools.adb, list_runner).list_devices(cancel_event)
    if listing.cancelled:
        return SideloadResult(SideloadOutcome.CANCELLED, "Cancelled before the sideload started.")
    if not listing.ok:
        return failed(f"Could not ask ADB for the device list: {listing.failure_reason()}")
    state = next((entry.state for entry in entries if entry.serial == serial), None)
    if state is None:
        return failed(f"Device {serial} is no longer connected. Nothing was sent.")
    if state != "sideload":
        return failed(
            f"Device {serial} is in state '{state}', not 'sideload'. Nothing was sent. "
            "Start ADB sideload on the device and try again."
        )

    log("INFO", f"$ {subprocess.list2cmdline(command)}")
    state_box = {"percent": None, "logged": -1}

    def handle_line(_stream: str, text: str) -> None:
        percent = parse_progress(text)
        if percent is None:
            log("INFO", text)  # real adb output, line by line
            return
        if percent != state_box["percent"]:
            state_box["percent"] = percent
            if on_progress is not None:
                on_progress(percent)
            if percent % 10 == 0 and percent != state_box["logged"]:
                state_box["logged"] = percent
                log("INFO", f"Transferred {percent}% of the ZIP (reported by adb).")

    result = streamer(command, on_line=handle_line, cancel_event=cancel_event, max_seconds=max_seconds)
    return classify(result, state_box["percent"])
