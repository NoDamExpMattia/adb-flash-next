"""Background thread that waits until Android reports it has started."""
from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from adb_flash_next.core.auto_flash import BootResult, BootState, wait_for_boot
from adb_flash_next.core.platform_tools import PlatformTools


class BootWatchWorker(QThread):
    """Emits status updates while waiting, then one final BootResult."""

    status = Signal(str, str)  # state value, message
    watch_finished = Signal(object)  # BootResult

    def __init__(self, tools: PlatformTools, serial: str, timeout_seconds: float = 1200.0, parent=None) -> None:
        super().__init__(parent)
        self._tools = tools
        self._serial = serial
        self._timeout = timeout_seconds
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            result = wait_for_boot(
                self._tools,
                self._serial,
                on_state=lambda state, message: self.status.emit(state.value, message),
                cancel_event=self._cancel,
                timeout_seconds=self._timeout,
            )
        except Exception as exc:  # never leave the UI waiting if something unexpected happens
            result = BootResult(False, BootState.ERROR, f"Unexpected error while waiting: {exc}")
        self.watch_finished.emit(result)
