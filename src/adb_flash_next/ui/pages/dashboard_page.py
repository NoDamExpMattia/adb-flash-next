"""Dashboard: device status, device info, progress ring, operation and log."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.config.constants import NOT_AVAILABLE
from adb_flash_next.core.models import INFO_FIELDS, ConnectionMode, DeviceInfo, PollResult
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.log_panel import LogPanel
from adb_flash_next.ui.widgets.progress_ring import ProgressRing


def _make_card() -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    return card


class DashboardPage(QWidget):
    """Main screen. Later stages use the public methods and signals."""

    # Emitted with the selected DeviceInfo, or None when no single device is selected.
    device_selected = Signal(object)
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._info_values: dict[str, QLabel] = {}
        self._devices: dict[str, DeviceInfo] = {}
        self._selected_key: str | None = None
        self._tools_missing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        top_row.addWidget(self._build_device_card(), 3)
        top_row.addWidget(self._build_progress_card(), 2)
        root.addLayout(top_row)

        root.addWidget(self._build_log_card(), 1)

        self._render()

    # ------------------------------------------------------------------ build
    def _build_device_card(self) -> QFrame:
        card = _make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._status_dot = QLabel("●")
        self._status_text = QLabel()
        self._status_text.setObjectName("StatusText")
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.refresh_requested.emit)
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_text, 1)
        status_row.addWidget(self._refresh_button)
        layout.addLayout(status_row)

        self._hint = QLabel()
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        # Shown only when several devices are connected: the user must pick one.
        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._combo.setVisible(False)
        layout.addWidget(self._combo)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        for row, field in enumerate(INFO_FIELDS):
            name = QLabel(field)
            name.setObjectName("Muted")
            name.setAlignment(Qt.AlignmentFlag.AlignTop)
            value = QLabel(NOT_AVAILABLE)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self._info_values[field] = value
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch()
        return card

    def _build_progress_card(self) -> QFrame:
        card = _make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self._ring = ProgressRing()
        layout.addWidget(self._ring, 1)

        caption = QLabel("Current operation")
        caption.setObjectName("Muted")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._operation_label = QLabel("Idle")
        self._operation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._operation_label.setWordWrap(True)
        layout.addWidget(caption)
        layout.addWidget(self._operation_label)

        # TEMPORARY: lets you verify the ring. Removed once real progress exists.
        test_label = QLabel("Ring test (temporary)")
        test_label.setObjectName("Muted")
        test_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._test_slider = QSlider(Qt.Orientation.Horizontal)
        self._test_slider.setRange(0, 100)
        self._test_slider.valueChanged.connect(self._ring.set_value)
        layout.addWidget(test_label)
        layout.addWidget(self._test_slider)
        return card

    def _build_log_card(self) -> QFrame:
        card = _make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)

        header = QLabel("Log")
        header.setObjectName("CardTitle")
        layout.addWidget(header)

        self._log = LogPanel()
        layout.addWidget(self._log, 1)
        return card

    # ------------------------------------------------------------- public API
    def selected_device(self) -> DeviceInfo | None:
        """The device the user (or auto-selection of a single device) has chosen."""
        return self._devices.get(self._selected_key) if self._selected_key else None

    def set_tools_missing(self) -> None:
        self._tools_missing = True
        self._devices = {}
        self._selected_key = None
        self._rebuild_combo([])
        self._render()
        self.device_selected.emit(None)

    def reset_devices(self) -> None:
        """Forget all devices (used when Platform-Tools change)."""
        self._tools_missing = False
        self._devices = {}
        self._selected_key = None
        self._rebuild_combo([])
        self._render()
        self.device_selected.emit(None)

    def show_poll_result(self, result: PollResult) -> None:
        self._tools_missing = False
        devices = list(result.devices)
        self._log_transitions(devices)
        self._devices = {d.key: d for d in devices}

        keys = [d.key for d in devices]
        if self._selected_key not in keys:
            self._selected_key = None
        if self._selected_key is None and len(devices) == 1:
            self._selected_key = keys[0]

        self._rebuild_combo(devices)
        self._render()
        self.device_selected.emit(self.selected_device())

    def set_progress(self, percent: float) -> None:
        self._ring.set_value(percent)

    def set_operation(self, text: str) -> None:
        self._operation_label.setText(text)

    def log(self, level: str, message: str) -> None:
        self._log.append_entry(level, message)

    # ---------------------------------------------------------------- internals
    def _log_transitions(self, devices: list[DeviceInfo]) -> None:
        new = {d.key: d for d in devices}
        for key, device in new.items():
            if key not in self._devices:
                self.log("SUCCESS", f"Device connected: {device.serial} - {device.mode.value}")
                for warning in device.warnings:
                    self.log("WARNING", f"{device.serial}: {warning}")
                for note in device.notes:
                    self.log("INFO", f"{device.serial}: {note}")
        for key, device in self._devices.items():
            if key not in new:
                self.log("WARNING", f"Device disconnected: {device.serial} - {device.mode.value}")

    def _rebuild_combo(self, devices: list[DeviceInfo]) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        if len(devices) > 1:
            self._combo.addItem("Select a device...", None)
            for device in devices:
                label = f"{device.product_text()}  |  {device.serial}  |  {device.mode.value}"
                self._combo.addItem(label, device.key)
            index = self._combo.findData(self._selected_key) if self._selected_key else 0
            self._combo.setCurrentIndex(max(index, 0))
            self._combo.setVisible(True)
        else:
            self._combo.setVisible(False)
        self._combo.blockSignals(False)

    def _on_combo_changed(self, _index: int) -> None:
        key = self._combo.currentData()
        self._selected_key = key if key in self._devices else None
        self._render()
        self.device_selected.emit(self.selected_device())

    def _set_status(self, text: str, color: str, hint: str = "") -> None:
        self._status_text.setText(text)
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 14pt;")
        self._hint.setText(hint)
        self._hint.setVisible(bool(hint))

    def _show_info(self, info: dict[str, str]) -> None:
        for field, label in self._info_values.items():
            label.setText(info.get(field) or NOT_AVAILABLE)

    def _render(self) -> None:
        device = self.selected_device()
        if self._tools_missing:
            self._set_status(
                "Platform-Tools not found",
                Colors.ERROR,
                "Open Settings and select the folder that contains adb and fastboot.",
            )
            self._show_info({})
        elif not self._devices:
            self._set_status("Waiting for device...", Colors.WARNING)
            self._show_info({})
        elif device is None:
            self._set_status(
                "Multiple devices detected",
                Colors.WARNING,
                "Several devices are connected. Select the target device from the list below. "
                "Nothing will run on a device until you choose one.",
            )
            self._show_info({})
        else:
            self._show_info(device.to_display_dict())
            hint = " ".join(device.warnings)
            if device.is_excluded:
                self._set_status("Unsupported device", Colors.ERROR, hint)
            elif device.mode in (ConnectionMode.UNAUTHORIZED, ConnectionMode.OFFLINE):
                self._set_status("Device found - not ready", Colors.WARNING, hint)
            elif not device.read_ok:
                self._set_status("Device found - details unavailable", Colors.WARNING, hint)
            else:
                self._set_status("Device Detected!", Colors.SUCCESS, hint)
