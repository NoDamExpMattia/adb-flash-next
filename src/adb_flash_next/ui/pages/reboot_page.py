"""Reboot page: ADB and Fastboot reboot actions, enabled only when they fit the device's mode."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from adb_flash_next.core.models import DeviceInfo
from adb_flash_next.core.reboot import ADB_ACTIONS, FASTBOOT_ACTIONS, RebootAction, availability
from adb_flash_next.ui.m3.action_tile import ActionTile


def _subtitle(action: RebootAction) -> str:
    """Short description line, e.g. 'Restart into recovery.'"""
    text = action.description.split(": ", 1)[-1]
    return text[:1].upper() + text[1:]


def _icon_for(action: RebootAction) -> str:
    if "bootloader" in action.args:
        return "flash"
    if "recovery" in action.args:
        return "recovery"
    if "fastboot" in action.args:
        return "terminal"
    return "reboot"


class RebootPage(QWidget):
    """Emits `reboot_requested(RebootAction)`; the main window confirms and runs it."""

    reboot_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._device: DeviceInfo | None = None
        self._busy = False
        self._tiles: list[tuple[ActionTile, RebootAction]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Reboot")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        self._device_label = QLabel()
        self._device_label.setWordWrap(True)
        root.addWidget(self._device_label)

        note = QLabel(
            "Tiles are enabled only when they fit the device's current mode. Whether a device "
            "supports a particular reboot target (for example recovery or fastbootd) depends on "
            "the device; a failure is shown in the log."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        root.addWidget(note)

        root.addWidget(self._build_group("Using ADB (Android, recovery or sideload)", ADB_ACTIONS))
        root.addWidget(self._build_group("Using Fastboot (bootloader or fastbootd)", FASTBOOT_ACTIONS))
        root.addStretch()
        self._refresh()

    def _build_group(self, title: str, actions: tuple[RebootAction, ...]) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(14)
        header = QLabel(title)
        header.setObjectName("CardTitle")
        header.setWordWrap(True)
        layout.addWidget(header)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for index, action in enumerate(actions):
            tile = ActionTile(action.label, _subtitle(action), icon=_icon_for(action))
            tile.clicked.connect(lambda _checked=False, a=action: self.reboot_requested.emit(a))
            grid.addWidget(tile, index // 2, index % 2)
            self._tiles.append((tile, action))
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return card

    # ------------------------------------------------------------- public API
    def set_device(self, device: DeviceInfo | None) -> None:
        self._device = device
        self._refresh()

    def set_busy(self, busy: bool) -> None:
        """Disable every tile while a command is running."""
        self._busy = busy
        self._refresh()

    # ---------------------------------------------------------------- internals
    def _refresh(self) -> None:
        if self._device is None:
            self._device_label.setText("No device selected. Connect a device and select it on the Dashboard.")
        else:
            self._device_label.setText(
                f"Device: {self._device.product_text()} ({self._device.serial}) - {self._device.mode.value}"
            )
        for tile, action in self._tiles:
            usable, reason = availability(action, self._device)
            tile.set_usable(usable and not self._busy)
            tip = action.description if usable else f"{action.description}\nUnavailable: {reason}"
            tile.setToolTip(tip)
