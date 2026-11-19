"""Background thread that keeps polling ADB and Fastboot for devices."""
from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from adb_flash_next.config.constants import POLL_INTERVAL_SECONDS
from adb_flash_next.core.device_manager import DeviceManager
from adb_flash_next.core.platform_tools import PlatformTools


class DetectionWorker(QThread):
    """Emits `devices_changed(PollResult)` only when something actually changed."""

    devices_changed = Signal(object)
    log_message = Signal(str, str)  # level, message

    def __init__(self, tools: PlatformTools, interval: float = POLL_INTERVAL_SECONDS, parent=None) -> None:
        super().__init__(parent)
        self._interval = interval
        self._manager = DeviceManager(tools, log=self._forward_log)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._refresh = threading.Event()
        self._paused = threading.Event()

    def _forward_log(self, level: str, message: str) -> None:
        self.log_message.emit(level, message)

    # -- control (called from the UI thread) -----------------------------------
    def stop(self) -> None:
        """Ask the loop to end and abort any command in progress. Call wait() afterwards."""
        self._stop.set()
        self._manager.cancel()
        self._wake.set()

    def request_refresh(self) -> None:
        """Re-read every device on the next cycle."""
        self._refresh.set()
        self._wake.set()

    def pause(self) -> None:
        """Stop polling (used while flashing so detection never interferes)."""
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()
        self._wake.set()

    # -- thread body -----------------------------------------------------------
    def run(self) -> None:
        last_signature = None
        while not self._stop.is_set():
            if self._refresh.is_set():
                self._refresh.clear()
                self._manager.clear_cache()
                self.log_message.emit("INFO", "Refreshing device information...")
                last_signature = None  # force the UI to update

            if not self._paused.is_set():
                try:
                    result = self._manager.poll()
                except Exception as exc:  # keep the loop alive and show the problem
                    self.log_message.emit("ERROR", f"Device detection error: {exc}")
                else:
                    if not self._stop.is_set() and result.signature != last_signature:
                        last_signature = result.signature
                        self.devices_changed.emit(result)

            self._wake.wait(self._interval)
            self._wake.clear()
