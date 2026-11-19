"""Generic background task so slow work never blocks the UI thread."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal


class FunctionWorker(QThread):
    """Runs `func()` in a thread, then emits `succeeded(result)` or `failed(message)`."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, func: Callable[[], Any], parent=None) -> None:
        super().__init__(parent)
        self._func = func

    def run(self) -> None:  # noqa: D401 (Qt entry point)
        try:
            result = self._func()
        except Exception as exc:  # report every failure to the UI, never swallow it
            self.failed.emit(str(exc) or type(exc).__name__)
        else:
            self.succeeded.emit(result)
