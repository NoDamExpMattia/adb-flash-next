"""Background thread that runs `adb sideload` and reports progress."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.sideload import SideloadOutcome, SideloadResult, run_sideload


class SideloadWorker(QThread):
    """Emits progress (0-100, as reported by adb), log lines, and one final SideloadResult."""

    progress = Signal(int)
    log_message = Signal(str, str)  # level, message
    sideload_finished = Signal(object)  # SideloadResult

    def __init__(self, tools: PlatformTools, serial: str, rom_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._tools = tools
        self._serial = serial
        self._rom_path = Path(rom_path)
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Ask the running adb command to stop (it is terminated within a fraction of a second)."""
        self._cancel.set()

    def run(self) -> None:
        try:
            result = run_sideload(
                self._tools,
                self._serial,
                self._rom_path,
                on_progress=self.progress.emit,
                on_log=self.log_message.emit,
                cancel_event=self._cancel,
            )
        except Exception as exc:  # never leave the UI waiting if something unexpected happens
            result = SideloadResult(SideloadOutcome.FAILED, f"Unexpected error during sideload: {exc}")
        self.sideload_finished.emit(result)
