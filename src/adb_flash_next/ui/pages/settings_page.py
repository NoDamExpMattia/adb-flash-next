<<<<<<< HEAD
"""Settings page: Platform-Tools location and appearance (accent colour, dark / light mode)."""
=======
"""Settings page: choose and verify the Android Platform-Tools folder."""
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
<<<<<<< HEAD
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
=======
from PySide6.QtWidgets import (
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
<<<<<<< HEAD
    QScrollArea,
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.config.constants import NOT_AVAILABLE
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.ui.m3.button import M3Button
<<<<<<< HEAD
from adb_flash_next.ui.m3.segmented import M3Segmented
from adb_flash_next.ui.m3.tokens import DEFAULT_SEED, PRESET_SEEDS, normalize_hex
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.color_swatch import ColorSwatch


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(24, 20, 24, 22)
    layout.setSpacing(12)
    header = QLabel(title)
    header.setObjectName("CardTitle")
    layout.addWidget(header)
    return card, layout
=======
from adb_flash_next.ui.theme import Colors
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b


class SettingsPage(QWidget):
    """Only displays state and emits requests; MainWindow does the actual work."""

    directory_chosen = Signal(str)
    autodetect_requested = Signal()
<<<<<<< HEAD
    appearance_changed = Signal(str, str)  # accent colour '#RRGGBB', mode 'dark' / 'light'

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_state = ("Checking...", "warn")
        self._seed = DEFAULT_SEED
        self._mode = "dark"
        self._swatches: list[ColorSwatch] = []

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
=======

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

<<<<<<< HEAD
        # ---------------------------------------------------------- Platform-Tools
        tools_card, layout = _card("Android Platform-Tools")
=======
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(12)

        header = QLabel("Android Platform-Tools")
        header.setObjectName("CardTitle")
        layout.addWidget(header)

>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
        self._status = QLabel("Checking...")
        self._status.setObjectName("StatusText")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        self._folder = self._add_row(grid, 0, "Folder")
        self._folder.setTextFormat(Qt.TextFormat.RichText)  # long paths can wrap anywhere
        self._adb_version = self._add_row(grid, 1, "adb version")
        self._fastboot_version = self._add_row(grid, 2, "fastboot version")
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        self._browse_button = M3Button("Browse...", "filled", height=44)
        self._browse_button.clicked.connect(self._on_browse)
        self._auto_button = M3Button("Auto-detect", "tonal", icon="refresh", height=44)
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
<<<<<<< HEAD
        root.addWidget(tools_card)

        # -------------------------------------------------------------- Appearance
        look_card, look = _card("Appearance")
        mode_label = QLabel("Mode")
        mode_label.setObjectName("Muted")
        look.addWidget(mode_label)
        mode_row = QHBoxLayout()
        self._segmented = M3Segmented([("dark", "Dark"), ("light", "Light")], "dark")
        self._segmented.value_changed.connect(self._on_mode)
        mode_row.addWidget(self._segmented)
        mode_row.addStretch()
        look.addLayout(mode_row)

        accent_label = QLabel("Accent color")
        accent_label.setObjectName("Muted")
        look.addWidget(accent_label)
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(4)
        for name, hex_color in PRESET_SEEDS:
            swatch = ColorSwatch(hex_color, name)
            swatch.clicked.connect(lambda _checked=False, h=hex_color: self._on_seed(h))
            self._swatches.append(swatch)
            swatch_row.addWidget(swatch)
        swatch_row.addStretch()
        look.addLayout(swatch_row)

        custom_row = QHBoxLayout()
        self._custom_button = M3Button("Custom color...", "tonal", height=44)
        self._custom_button.clicked.connect(self._on_custom)
        self._reset_button = M3Button("Reset to default", "text", height=44)
        self._reset_button.clicked.connect(self._on_reset)
        self._hex_label = QLabel()
        self._hex_label.setObjectName("Muted")
        custom_row.addWidget(self._custom_button)
        custom_row.addWidget(self._reset_button)
        custom_row.addWidget(self._hex_label)
        custom_row.addStretch()
        look.addLayout(custom_row)

        hint = QLabel("Changes apply immediately and are saved for the next start.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        look.addWidget(hint)
        root.addWidget(look_card)
        root.addStretch()

        self._sync_appearance()
        self._render_status()

=======

        root.addWidget(card)
        root.addStretch()

>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
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

<<<<<<< HEAD
    # ------------------------------------------------------------ Platform-Tools state
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select the platform-tools folder")
        if directory:
            self.directory_chosen.emit(directory)

<<<<<<< HEAD
    def _render_status(self) -> None:
        text, level = self._status_state
        color = {"ok": Colors.SUCCESS, "warn": Colors.WARNING, "error": Colors.ERROR}.get(level, Colors.MUTED)
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color};")

    def show_checking(self) -> None:
        self._status_state = ("Checking Platform-Tools...", "warn")
        self._render_status()
=======
    def _set_status(self, text: str, color: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color};")

    # -- called by MainWindow --------------------------------------------------
    def show_checking(self) -> None:
        self._set_status("Checking Platform-Tools...", Colors.WARNING)
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
        self._browse_button.setEnabled(False)
        self._auto_button.setEnabled(False)

    def show_tools(self, tools: PlatformTools) -> None:
<<<<<<< HEAD
        self._status_state = ("Platform-Tools ready", "ok")
        self._render_status()
=======
        self._set_status("Platform-Tools ready", Colors.SUCCESS)
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
        self._folder.setText(html.escape(str(tools.directory)))
        self._adb_version.setText(tools.adb_version or NOT_AVAILABLE)
        self._fastboot_version.setText(tools.fastboot_version or NOT_AVAILABLE)
        self._browse_button.setEnabled(True)
        self._auto_button.setEnabled(True)

    def show_error(self, message: str) -> None:
<<<<<<< HEAD
        self._status_state = (message, "error")
        self._render_status()
        self._browse_button.setEnabled(True)
        self._auto_button.setEnabled(True)

    # ------------------------------------------------------------------- appearance
    def set_appearance(self, seed: str, mode: str) -> None:
        """Show the saved appearance without emitting a change."""
        self._seed = normalize_hex(seed)
        self._mode = mode if mode in ("dark", "light") else "dark"
        self._sync_appearance()

    def _sync_appearance(self) -> None:
        self._segmented.set_value(self._mode)
        for swatch in self._swatches:
            swatch.set_selected(swatch.hex_color == self._seed)
        self._hex_label.setText(f"Current accent: {self._seed}")

    def _emit_appearance(self) -> None:
        self._sync_appearance()
        self.appearance_changed.emit(self._seed, self._mode)

    def _on_mode(self, mode: str) -> None:
        self._mode = mode
        self._emit_appearance()

    def _on_seed(self, hex_color: str) -> None:
        self._seed = normalize_hex(hex_color)
        self._emit_appearance()

    def _on_custom(self) -> None:
        color = QColorDialog.getColor(QColor(self._seed), self, "Choose the accent color")
        if color.isValid():
            self._on_seed(color.name().upper())

    def _on_reset(self) -> None:
        self._seed = DEFAULT_SEED
        self._mode = "dark"
        self._emit_appearance()

    def apply_theme(self) -> None:
        """Re-render colours that were baked into labels."""
        self._render_status()
=======
        self._set_status(message, Colors.ERROR)
        self._browse_button.setEnabled(True)
        self._auto_button.setEnabled(True)
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
