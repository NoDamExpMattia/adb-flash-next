"""ADB commands. Every device-specific command is bound to an explicit serial (-s)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from adb_flash_next.config.constants import TIMEOUT_ADB_PROPS, TIMEOUT_DEVICE_LIST
from adb_flash_next.core.parsers import AdbListEntry, parse_adb_devices, parse_getprop, validate_serial
from adb_flash_next.core.process_runner import CommandResult, run_command

Runner = Callable[..., CommandResult]


class AdbClient:
    def __init__(self, adb_path: Path, runner: Runner = run_command) -> None:
        self._adb = str(adb_path)
        self._run = runner

    def _device_args(self, serial: str, *rest: str) -> list[str]:
        """Build a device command. The serial is validated and always passed with -s."""
        return [self._adb, "-s", validate_serial(serial), *rest]

    def list_devices(
        self, cancel_event: threading.Event | None = None
    ) -> tuple[list[AdbListEntry], CommandResult]:
        """`adb devices -l`. Starts the ADB server if it is not running yet."""
        result = self._run([self._adb, "devices", "-l"], timeout=TIMEOUT_DEVICE_LIST, cancel_event=cancel_event)
        entries = parse_adb_devices(result.stdout) if result.ok else []
        return entries, result

    def get_properties(
        self, serial: str, cancel_event: threading.Event | None = None
    ) -> tuple[dict[str, str], CommandResult]:
        """`adb -s <serial> shell getprop` parsed into a dictionary (empty on failure)."""
        result = self._run(
            self._device_args(serial, "shell", "getprop"),
            timeout=TIMEOUT_ADB_PROPS,
            cancel_event=cancel_event,
        )
        props = parse_getprop(result.stdout) if result.ok else {}
        return props, result
