"""Fastboot commands. Every device-specific command is bound to an explicit serial (-s)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from adb_flash_next.config.constants import TIMEOUT_DEVICE_LIST, TIMEOUT_FASTBOOT_GETVAR
from adb_flash_next.core.parsers import (
    parse_fastboot_devices,
    parse_fastboot_var,
    validate_fastboot_var,
    validate_serial,
)
from adb_flash_next.core.process_runner import CommandResult, run_command

Runner = Callable[..., CommandResult]


class FastbootClient:
    def __init__(self, fastboot_path: Path, runner: Runner = run_command) -> None:
        self._fastboot = str(fastboot_path)
        self._run = runner

    def _device_args(self, serial: str, *rest: str) -> list[str]:
        return [self._fastboot, "-s", validate_serial(serial), *rest]

    def list_devices(
        self, cancel_event: threading.Event | None = None
    ) -> tuple[list[str], CommandResult]:
        """`fastboot devices` -> list of serial numbers."""
        result = self._run([self._fastboot, "devices"], timeout=TIMEOUT_DEVICE_LIST, cancel_event=cancel_event)
        serials = parse_fastboot_devices(result.stdout) if result.ok else []
        return serials, result

    def getvar(
        self, serial: str, name: str, cancel_event: threading.Event | None = None
    ) -> tuple[str | None, CommandResult]:
        """`fastboot -s <serial> getvar <name>`.

        Returns (value, raw result). The value is None when the variable is not
        reported: Fastboot prints answers on stderr and some bootloaders exit with
        code 0 even for unknown variables, so the output text decides, not the exit code.
        """
        result = self._run(
            self._device_args(serial, "getvar", validate_fastboot_var(name)),
            timeout=TIMEOUT_FASTBOOT_GETVAR,
            cancel_event=cancel_event,
        )
        value = parse_fastboot_var(result.combined_output, name)
        return value, result
