"""Detects connected devices (ADB and Fastboot) and reads what they report.

Rules followed here:
  * Only values the device actually reported are shown; the rest stay unknown.
  * Details are read once per device/mode and cached, so polling stays quiet.
  * Every device command is bound to a verified serial number.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from adb_flash_next.config.constants import MAX_INFO_READ_ATTEMPTS
from adb_flash_next.core.adb_client import AdbClient
from adb_flash_next.core.fastboot_client import FastbootClient
from adb_flash_next.core.models import (
    ConnectionMode,
    DeviceInfo,
    PollResult,
    Transport,
)
from adb_flash_next.core.parsers import AdbListEntry
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult, run_command
from adb_flash_next.core.slot_detection import (
    decide_scheme,
    normalize_slot,
    votes_from_adb,
    votes_from_fastboot,
)

LogFn = Callable[[str, str], None]  # (level, message)

_ADB_STATE_MODES: dict[str, ConnectionMode] = {
    "device": ConnectionMode.ANDROID,
    "recovery": ConnectionMode.RECOVERY,
    "sideload": ConnectionMode.SIDELOAD,
    "rescue": ConnectionMode.RESCUE,
    "unauthorized": ConnectionMode.UNAUTHORIZED,
    "offline": ConnectionMode.OFFLINE,
}

_FASTBOOT_VARIABLES = (
    "product",
    "is-userspace",
    "current-slot",
    "slot-count",
    "has-slot:boot",
    "unlocked",
)


def _prop(props: dict[str, str], *keys: str) -> str | None:
    """First non-empty property among `keys`, else None."""
    for key in keys:
        value = props.get(key, "").strip()
        if value:
            return value
    return None


def apply_adb_properties(info: DeviceInfo, props: dict[str, str]) -> None:
    """Fill `info` from `adb shell getprop` output. Missing values stay None."""
    info.product = _prop(props, "ro.product.device", "ro.build.product", "ro.product.name")
    info.model = _prop(props, "ro.product.model")
    info.manufacturer = _prop(props, "ro.product.manufacturer", "ro.product.vendor.manufacturer")

    soc = " ".join(p for p in (_prop(props, "ro.soc.manufacturer"), _prop(props, "ro.soc.model")) if p)
    parts = []
    if soc:
        parts.append(f"SoC {soc}")
    board = _prop(props, "ro.board.platform")
    if board:
        parts.append(f"platform {board}")
    hardware = _prop(props, "ro.hardware")
    if hardware:
        parts.append(f"hardware {hardware}")
    info.platform = " | ".join(parts) or None

    release = _prop(props, "ro.build.version.release")
    sdk = _prop(props, "ro.build.version.sdk")
    if release:
        info.android_version = f"Android {release}" + (f" (API {sdk})" if sdk else "")
    elif sdk:
        info.android_version = f"API level {sdk}"

    info.active_slot = normalize_slot(_prop(props, "ro.boot.slot_suffix"))
    info.scheme, info.scheme_evidence = decide_scheme(votes_from_adb(props))

    completed = _prop(props, "sys.boot_completed")
    info.boot_completed = None if completed is None else completed == "1"

    if info.mode is ConnectionMode.RECOVERY:
        info.notes.append(
            "Properties were read from recovery; values may describe the recovery "
            "environment rather than the installed system."
        )
    if info.active_slot:
        info.notes.append(
            "Active slot from ADB is the slot that was booted. Fastboot's value is "
            "authoritative before flashing."
        )
    if info.is_excluded:
        info.warnings.append(
            "Samsung devices are outside the supported scope of this app. "
            "Flashing will not be offered for this device."
        )


def apply_fastboot_variables(info: DeviceInfo, values: dict[str, str | None]) -> None:
    """Fill `info` from Fastboot variables. Missing values stay None / Unknown."""
    userspace = (values.get("is-userspace") or "").strip().lower()
    if userspace == "yes":
        info.is_userspace = True
        info.mode = ConnectionMode.FASTBOOTD
    elif userspace == "no":
        info.is_userspace = False
        info.mode = ConnectionMode.FASTBOOT
    else:
        info.is_userspace = None
        info.mode = ConnectionMode.FASTBOOT_UNCONFIRMED

    info.product = values.get("product")
    info.active_slot = normalize_slot(values.get("current-slot"))
    info.scheme, info.scheme_evidence = decide_scheme(
        votes_from_fastboot(values.get("slot-count"), values.get("has-slot:boot"), values.get("current-slot"))
    )

    unlocked = (values.get("unlocked") or "").strip().lower()
    if unlocked in ("yes", "no"):
        info.bootloader_unlocked = unlocked
    if unlocked == "no":
        info.warnings.append("The bootloader reports that it is LOCKED. Flashing is expected to fail.")

    raw_slot = values.get("current-slot")
    if raw_slot and info.active_slot is None:
        info.warnings.append(f"Unrecognised current-slot value reported by the device: {raw_slot!r}.")

    info.read_ok = any(v is not None for v in values.values())
    if not info.read_ok:
        info.warnings.append("The device did not answer any Fastboot query.")


class DeviceManager:
    """Polls ADB and Fastboot and builds DeviceInfo objects. Not a Qt class."""

    def __init__(
        self,
        tools: PlatformTools,
        log: LogFn | None = None,
        runner: Callable[..., CommandResult] = run_command,
    ) -> None:
        self._adb = AdbClient(Path(tools.adb), runner)
        self._fastboot = FastbootClient(Path(tools.fastboot), runner)
        self._log_fn = log
        self._cancel = threading.Event()
        self._cache: dict[tuple, DeviceInfo] = {}
        self._attempts: dict[tuple, int] = {}
        self._last_warning: str | None = None

    # -- control ---------------------------------------------------------------
    def cancel(self) -> None:
        """Abort the command currently running and every later one."""
        self._cancel.set()

    def clear_cache(self) -> None:
        """Forget what was read so the next poll re-reads every device."""
        self._cache.clear()
        self._attempts.clear()

    # -- logging ---------------------------------------------------------------
    def _log(self, level: str, message: str) -> None:
        if self._log_fn:
            self._log_fn(level, message)

    def _log_result(self, result: CommandResult, success_text: str) -> None:
        if result.ok:
            self._log("INFO", f"$ {result.command_line}  ->  {success_text}")
        else:
            self._log("WARNING", f"$ {result.command_line}  ->  failed: {result.failure_reason()}")

    # -- polling ---------------------------------------------------------------
    def poll(self) -> PollResult:
        warnings: list[str] = []

        adb_entries, adb_result = self._adb.list_devices(self._cancel)
        if not adb_result.ok and not adb_result.cancelled:
            warnings.append(f"ADB device list failed: {adb_result.failure_reason()}")
            adb_entries = []

        fastboot_serials, fb_result = self._fastboot.list_devices(self._cancel)
        if not fb_result.ok and not fb_result.cancelled:
            warnings.append(f"Fastboot device list failed: {fb_result.failure_reason()}")
            fastboot_serials = []

        devices: list[DeviceInfo] = []
        seen: set[tuple] = set()
        for entry in adb_entries:
            key = ("adb", entry.serial, entry.state)
            seen.add(key)
            devices.append(self._get_info(key, lambda e=entry: self._inspect_adb(e)))
        for serial in fastboot_serials:
            key = ("fastboot", serial)
            seen.add(key)
            devices.append(self._get_info(key, lambda s=serial: self._inspect_fastboot(s)))

        for stale in [k for k in self._cache if k not in seen]:
            del self._cache[stale]
        for stale in [k for k in self._attempts if k not in seen]:
            del self._attempts[stale]

        # Report each distinct polling problem once instead of every 2 seconds.
        message = "; ".join(warnings) if warnings else None
        if message != self._last_warning:
            self._last_warning = message
            if message:
                self._log("WARNING", message)

        return PollResult(devices=tuple(devices), warnings=tuple(warnings))

    def _get_info(self, key: tuple, factory: Callable[[], DeviceInfo]) -> DeviceInfo:
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if self._cancel.is_set():
            return DeviceInfo(serial=str(key[1]), transport=Transport(key[0]), read_ok=False)
        info = factory()
        attempts = self._attempts.get(key, 0) + 1
        self._attempts[key] = attempts
        if info.read_ok or attempts >= MAX_INFO_READ_ATTEMPTS:
            self._cache[key] = info
            if not info.read_ok:
                self._log("WARNING", f"Giving up reading details of {info.serial}; use Refresh to retry.")
        return info

    # -- inspection ------------------------------------------------------------
    def _inspect_adb(self, entry: AdbListEntry) -> DeviceInfo:
        mode = _ADB_STATE_MODES.get(entry.state, ConnectionMode.UNKNOWN)
        info = DeviceInfo(serial=entry.serial, transport=Transport.ADB, mode=mode, adb_state=entry.state)
        self._log("INFO", f"Reading details of {entry.serial} (ADB state: {entry.state})...")

        if mode in (ConnectionMode.ANDROID, ConnectionMode.RECOVERY):
            props, result = self._adb.get_properties(entry.serial, self._cancel)
            self._log_result(result, f"{len(props)} properties read")
            if props:
                apply_adb_properties(info, props)
            else:
                info.read_ok = False
                info.warnings.append(f"Could not read device properties: {result.failure_reason()}")
        elif mode is ConnectionMode.UNAUTHORIZED:
            info.warnings.append(
                "This computer is not authorized. Unlock the phone and accept the "
                "'Allow USB debugging' prompt, then press Refresh."
            )
        elif mode is ConnectionMode.OFFLINE:
            info.warnings.append("ADB reports the device as offline. Reconnect the USB cable and press Refresh.")
        elif mode is ConnectionMode.SIDELOAD:
            info.notes.append("Device is in sideload mode; properties cannot be read in this mode.")
        elif mode is ConnectionMode.RESCUE:
            info.notes.append("Device is in ADB rescue mode; properties cannot be read in this mode.")
        else:
            info.warnings.append(f"Unrecognised ADB state: {entry.state!r}.")
        return info

    def _inspect_fastboot(self, serial: str) -> DeviceInfo:
        info = DeviceInfo(serial=serial, transport=Transport.FASTBOOT)
        self._log("INFO", f"Reading details of {serial} (Fastboot)...")

        values: dict[str, str | None] = {}
        for name in _FASTBOOT_VARIABLES:
            value, result = self._fastboot.getvar(serial, name, self._cancel)
            values[name] = value
            if value is not None:
                self._log("INFO", f"$ {result.command_line}  ->  {value}")
            elif result.timed_out or result.cancelled or result.error:
                self._log("WARNING", f"$ {result.command_line}  ->  failed: {result.failure_reason()}")
                break  # the device is probably gone; do not wait for every remaining variable
            else:
                self._log("INFO", f"$ {result.command_line}  ->  not reported by this device")
        apply_fastboot_variables(info, values)
        return info
