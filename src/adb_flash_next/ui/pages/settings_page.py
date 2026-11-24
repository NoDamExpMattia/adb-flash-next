"""Settings page: Platform-Tools location and appearance (accent colour, dark / light mode)."""
from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.config.constants import APP_NAME, APP_VERSION, AUTHOR_HANDLE, AUTHOR_URL, NOT_AVAILABLE
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.ui.m3.button import M3Button
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


class SettingsPage(QWidget):
    """Only displays state and emits requests; MainWindow does the actual work."""

    directory_chosen = Signal(str)
    autodetect_requested = Signal()
    payload_tool_chosen = Signal(str)
    appearance_changed = Signal(str, str)  # accent colour '#RRGGBB', mode 'dark' / 'light'

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_state = ("Checking...", "warn")
        self._payload_tool: Path | None = None
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
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # ---------------------------------------------------------- Platform-Tools
        tools_card, layout = _card("Android Platform-Tools")
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

        # ------------------------------------------------------ payload-dumper-go
        payload_card, pay = _card("payload-dumper-go (optional)")
        self._payload_status = QLabel()
        self._payload_status.setTextFormat(Qt.TextFormat.RichText)
        self._payload_status.setWordWrap(True)
        pay.addWidget(self._payload_status)
        pay_row = QHBoxLayout()
        self._payload_button = M3Button("Choose payload-dumper-go...", "tonal", height=44)
        self._payload_button.clicked.connect(self._on_choose_payload)
        pay_row.addWidget(self._payload_button)
        pay_row.addStretch()
        pay.addLayout(pay_row)
        pay_note = QLabel(
            "Used by Auto Flash > Extract partitions. Put payload-dumper-go.exe in the 'bin' folder next to "
            "the app and it is found automatically."
        )
        pay_note.setObjectName("Muted")
        pay_note.setWordWrap(True)
        pay.addWidget(pay_note)
        root.addWidget(payload_card)

        # ------------------------------------------------------------------- About
        about_card, about = _card("About")
        app_line = QLabel(f"{APP_NAME}  v{APP_VERSION}")
        app_line.setStyleSheet("font-size: 16px; font-weight: bold;")
        about.addWidget(app_line)
        author_line = QLabel(f"Developer: @{AUTHOR_HANDLE}")
        author_line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        about.addWidget(author_line)
        about_row = QHBoxLayout()
        self._profile_button = M3Button("Open GitHub profile", "filled", icon="open", height=44)
        self._profile_button.setToolTip(AUTHOR_URL)
        self._profile_button.clicked.connect(self._open_profile)
        about_row.addWidget(self._profile_button)
        about_row.addStretch()
        about.addLayout(about_row)
        root.addWidget(about_card)
        root.addStretch()

        self._sync_appearance()
        self._render_status()
        self.show_payload_tool(None)

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

    # ------------------------------------------------------------ Platform-Tools state
    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select the platform-tools folder")
        if directory:
            self.directory_chosen.emit(directory)

    def _render_status(self) -> None:
        text, level = self._status_state
        color = {"ok": Colors.SUCCESS, "warn": Colors.WARNING, "error": Colors.ERROR}.get(level, Colors.MUTED)
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color};")

    def show_checking(self) -> None:
        self._status_state = ("Checking Platform-Tools...", "warn")
        self._render_status()
        self._browse_button.setEnabled(False)
        self._auto_button.setEnabled(False)

    def show_tools(self, tools: PlatformTools) -> None:
        self._status_state = ("Platform-Tools ready", "ok")
        self._render_status()
        self._folder.setText(html.escape(str(tools.directory)))
        self._adb_version.setText(tools.adb_version or NOT_AVAILABLE)
        self._fastboot_version.setText(tools.fastboot_version or NOT_AVAILABLE)
        self._browse_button.setEnabled(True)
        self._auto_button.setEnabled(True)

    def show_error(self, message: str) -> None:
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

    def _on_choose_payload(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select payload-dumper-go", "", "Programs (*.exe);;All files (*)"
        )
        if path:
            self.payload_tool_chosen.emit(path)

    def show_payload_tool(self, tool: Path | None) -> None:
        self._payload_tool = tool
        if tool is None:
            text, color = "Not found. 'Extract partitions' is unavailable until you add it.", Colors.WARNING
        else:
            text, color = f"Found: {html.escape(str(tool))}", Colors.SUCCESS
        self._payload_status.setText(f'<span style="color:{color}">{text}</span>')

    def _open_profile(self) -> None:
        """Open the developer's GitHub profile in the default browser (fixed address, no user input)."""
        QDesktopServices.openUrl(QUrl(AUTHOR_URL))

    def apply_theme(self) -> None:
        """Re-render colours that were baked into labels."""
        self._render_status()
        self.show_payload_tool(self._payload_tool)
