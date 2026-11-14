"""Settings page: choose and verify the Android Platform-Tools folder."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.config.constants import NOT_AVAILABLE
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.ui.theme import Colors


class SettingsPage(QWidget):
    """Only displays state and emits requests; MainWindow does the actual work."""

    directory_chosen = Signal(str)
    autodetect_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QLabel("Android Platform-Tools")
        header.setObjectName("CardTitle")
        layout.addWidget(header)

        self._status = QLabel("Checking...")
        self._status.setObjectName("StatusText")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        self._folder = self._add_row(grid, 0, "Folder")
        self._adb_version = self._add_row(grid, 1, "adb version")
        self._fastboot_version = self._add_row(grid, 2, "fastboot version")
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        self._browse_button = QPushButton("Browse...")
        self._browse_button.setObjectName("Primary")
        self._browse_button.clicked.connect(self._on_browse)
        self._auto_button = QPushButton("Auto-detect")
        self._auto_button.clicked.connect(self.autodetect_requested.emit)
        buttons.addWidget(self._browse_button)
        buttons.addWidget(self._auto_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        note = QLabel(
            "ADB Flash Next does not bundle Platform-Tools. Download the official package "
            "from Google (developer.android.com/tools/releases/platform-tools), extract it, "
            "then select the folder that contains adb and fastboot. Platform-Tools is "
            "provided by Google under the Android SDK License Agreement."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        root.addWidget(card)
        root.addStretch()

    @staticmethod
    def _add_row(grid: QGridLayout, row: int, name: str) -> QLabel:
        label = QLabel(name)
        label.setObjectName("Muted")
        value = QLabel(NOT_AVAILABLE)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(label, row, 0)
        grid.addWidget(value, row, 1)
        return value

    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select the platform-tools folder")
        if directory:
            self.directory_chosen.emit(directory)

    def _set_status(self, text: str, color: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color};")

    # -- called by MainWindow --------------------------------------------------
    def show_checking(self) -> None:
        self._set_status("Checking Platform-Tools...", Colors.WARNING)
        self._browse_button.setEnabled(False)
        self._auto_button.setEnabled(False)

    def show_tools(self, tools: PlatformTools) -> None:
        self._set_status("Platform-Tools ready", Colors.SUCCESS)
        self._folder.setText(str(tools.directory))
        self._adb_version.setText(tools.adb_version or NOT_AVAILABLE)
        self._fastboot_version.setText(tools.fastboot_version or NOT_AVAILABLE)
        self._browse_button.setEnabled(True)
        self._auto_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self._set_status(message, Colors.ERROR)
        self._browse_button.setEnabled(True)
        self._auto_button.setEnabled(True)
