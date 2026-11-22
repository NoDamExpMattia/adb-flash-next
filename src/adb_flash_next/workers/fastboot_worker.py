"""Background thread that runs a flash/utility plan with Fastboot."""
from __future__ import annotations

import threading
from typing import Sequence

from PySide6.QtCore import QThread, Signal

from adb_flash_next.core.fastboot_executor import FlashRunResult, preflight, run_steps
from adb_flash_next.core.flash_plan import PlannedStep
from adb_flash_next.core.platform_tools import PlatformTools


class FastbootWorker(QThread):
    """Pre-flight, then the steps in order. Emits one final FlashRunResult."""

    step_started = Signal(int, int, str)  # index, total, description
    log_message = Signal(str, str)  # level, message
    run_finished = Signal(object)  # FlashRunResult

    def __init__(
        self,
        tools: PlatformTools,
        serial: str,
        steps: Sequence[PlannedStep],
        require_unlocked: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._require_unlocked = require_unlocked
        self._tools = tools
        self._serial = serial
        self._steps = tuple(steps)
        self._stop = threading.Event()

    def request_stop(self) -> None:
        """Stop after the current step finishes (a running step is never killed)."""
        self._stop.set()

    def run(self) -> None:
        total = len(self._steps)
        try:
            self.log_message.emit("INFO", f"Checking device {self._serial} before starting...")
            checks = preflight(self._tools, self._serial, self._steps, require_unlocked=self._require_unlocked)
            for warning in checks.warnings:
                self.log_message.emit("WARNING", warning)
            if not checks.ok:
                for error in checks.errors:
                    self.log_message.emit("ERROR", error)
                result = FlashRunResult(
                    False, 0, total, None,
                    "Not started: " + " ".join(checks.errors),
                )
            else:
                result = run_steps(
                    self._tools,
                    self._serial,
                    self._steps,
                    on_step=lambda i, n, step: self.step_started.emit(i, n, step.description),
                    on_log=self.log_message.emit,
                    stop_event=self._stop,
                )
        except Exception as exc:  # never leave the UI waiting if something unexpected happens
            result = FlashRunResult(False, 0, total, None, f"Unexpected error: {exc}")
        self.run_finished.emit(result)
