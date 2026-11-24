"""Background thread that extracts partitions from the ROM with payload-dumper-go."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QThread, Signal

from adb_flash_next.core.payload_extractor import ExtractResult, extract_partitions


class ExtractWorker(QThread):
    log_message = Signal(str, str)  # level, message
    extract_finished = Signal(object)  # ExtractResult

    def __init__(self, tool: Path, rom: Path, partitions: Sequence[str], output_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self._tool, self._rom, self._partitions, self._output = tool, rom, tuple(partitions), output_dir
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Safe at any time: extraction only writes temporary files, never the device."""
        self._cancel.set()

    def run(self) -> None:
        try:
            result = extract_partitions(
                self._tool, self._rom, self._partitions, self._output,
                on_log=self.log_message.emit, cancel_event=self._cancel,
            )
        except Exception as exc:  # never leave the UI waiting
            result = ExtractResult(False, {}, f"Unexpected error during extraction: {exc}")
        self.extract_finished.emit(result)
