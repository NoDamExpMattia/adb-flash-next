"""Reboot actions (ADB and Fastboot). Every command is bound to a verified serial."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from adb_flash_next.config.constants import TIMEOUT_REBOOT
from adb_flash_next.core.models import ConnectionMode, DeviceInfo, Transport
from adb_flash_next.core.parsers import validate_serial
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult, run_command

Runner = Callable[..., CommandResult]


@dataclass(frozen=True)
class RebootAction:
    key: str
    label: str
    tool: str  # "adb" or "fastboot"
    args: tuple[str, ...]
    description: str


ADB_ACTIONS: tuple[RebootAction, ...] = (
    RebootAction("adb_system", "Reboot", "adb", ("reboot",),
                 "adb reboot: restart into Android."),
    RebootAction("adb_bootloader", "Reboot to bootloader", "adb", ("reboot", "bootloader"),
                 "adb reboot bootloader: restart into the bootloader (Fastboot)."),
    RebootAction("adb_recovery", "Reboot to recovery", "adb", ("reboot", "recovery"),
                 "adb reboot recovery: restart into recovery."),
    RebootAction("adb_fastbootd", "Reboot to fastbootd", "adb", ("reboot", "fastboot"),
                 "adb reboot fastboot: restart into fastbootd. Needs Android 10+ support on the device."),
)

FASTBOOT_ACTIONS: tuple[RebootAction, ...] = (
    RebootAction("fb_system", "fastboot reboot", "fastboot", ("reboot",),
                 "fastboot reboot: restart into Android."),
    RebootAction("fb_bootloader", "fastboot reboot bootloader", "fastboot", ("reboot", "bootloader"),
                 "fastboot reboot bootloader: restart the bootloader."),
    RebootAction("fb_fastbootd", "fastboot reboot fastboot", "fastboot", ("reboot", "fastboot"),
                 "fastboot reboot fastboot: restart into fastbootd. Not every device supports it."),
    RebootAction("fb_recovery", "fastboot reboot recovery", "fastboot", ("reboot", "recovery"),
                 "fastboot reboot recovery: restart into recovery. Not every bootloader supports it."),
)

_ADB_READY_MODES = (ConnectionMode.ANDROID, ConnectionMode.RECOVERY, ConnectionMode.SIDELOAD)


def availability(action: RebootAction, device: DeviceInfo | None) -> tuple[bool, str]:
    """(usable now?, reason if not). The command itself may still fail on some devices."""
    if device is None:
        return False, "No device selected."
    if action.tool == "adb":
        if device.transport is not Transport.ADB:
            return False, "Needs a device that ADB can see (Android, recovery or sideload)."
        if device.mode not in _ADB_READY_MODES:
            return False, f"ADB cannot send commands while the device is '{device.mode.value}'."
        return True, ""
    if device.transport is not Transport.FASTBOOT:
        return False, "Needs the device in Fastboot mode."
    return True, ""


def build_reboot_command(tools: PlatformTools, serial: str, action: RebootAction) -> list[str]:
    """Full argument list. The serial is validated and always passed with -s."""
    executable = tools.adb if action.tool == "adb" else tools.fastboot
    return [str(executable), "-s", validate_serial(serial), *action.args]


def run_reboot(
    tools: PlatformTools,
    device: DeviceInfo,
    action: RebootAction,
    cancel_event: threading.Event | None = None,
    runner: Runner = run_command,
) -> CommandResult:
    """Run one reboot action on `device`. Refuses if the action does not fit the device's mode."""
    usable, reason = availability(action, device)
    if not usable:
        return CommandResult(args=(), returncode=None, error=reason)
    try:
        command = build_reboot_command(tools, device.serial, action)
    except ValueError as exc:
        return CommandResult(args=(), returncode=None, error=str(exc))
    return runner(command, timeout=TIMEOUT_REBOOT, cancel_event=cancel_event)
