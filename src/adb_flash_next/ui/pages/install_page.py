"""Install page: choose a ROM ZIP and start `adb sideload` (guided by a dialog)."""
from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.core.image_validator import format_size
from adb_flash_next.core.models import DeviceInfo
from adb_flash_next.core.sideload import LEVEL_ERROR, LEVEL_OK, ZipCheck, sideload_readiness, validate_rom_zip
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.chip import StatusChip
from adb_flash_next.ui.widgets.progress_ring import ProgressRing


class InstallPage(QWidget):
    """Emits `sideload_requested(Path)` and `cancel_requested()`. MainWindow does the work."""

    sideload_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._device: DeviceInfo | None = None
        self._check: ZipCheck | None = None
        self._busy = False
        self._result_state = ("", "info")
        self._last_dir = str(Path.home())

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

        title = QLabel("Install")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        intro = QLabel(
            "Install a custom ROM from recovery with ADB sideload. When you press 'Sideload ROM' the "
            "app shows how to enter recovery, how to format data (only if your ROM requires it, and "
            "always by hand) and what to select to start sideload mode. It then waits for the device."
        )
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(14)

        header = QLabel("ADB Sideload")
        header.setObjectName("CardTitle")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        self._device_chip = StatusChip()
        layout.addWidget(self._device_chip)

        # --- ROM ZIP box ---
        box = QFrame()
        box.setObjectName("DropBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(20, 16, 20, 16)
        box_layout.setSpacing(8)
        caption = QLabel("ROM package (.zip)")
        caption.setObjectName("Muted")
        box_layout.addWidget(caption)
        self._file_name = QLabel("No ROM selected")
        self._file_name.setStyleSheet("font-size: 17px; font-weight: bold;")
        self._file_name.setTextFormat(Qt.TextFormat.RichText)  # rich text can break long names anywhere
        self._file_name.setWordWrap(True)
        self._file_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box_layout.addWidget(self._file_name)
        self._file_meta = QLabel()
        self._file_meta.setObjectName("Muted")
        self._file_meta.setTextFormat(Qt.TextFormat.RichText)
        self._file_meta.setWordWrap(True)
        box_layout.addWidget(self._file_meta)
        self._file_check = QLabel()
        self._file_check.setWordWrap(True)
        box_layout.addWidget(self._file_check)
        buttons = QHBoxLayout()
        self._choose = M3Button("Choose ZIP...", "tonal", height=44)
        self._choose.clicked.connect(self._on_choose)
        self._clear = M3Button("Clear", "text", height=44)
        self._clear.clicked.connect(self._on_clear)
        buttons.addWidget(self._choose)
        buttons.addWidget(self._clear)
        buttons.addStretch()
        box_layout.addLayout(buttons)
        layout.addWidget(box)

        # --- Sideload button ---
        self._sideload = M3Button("Sideload ROM", "filled", icon="install", height=56)
        self._sideload.clicked.connect(self._on_sideload)
        layout.addWidget(self._sideload)

        # --- progress ---
        progress_row = QHBoxLayout()
        progress_row.setSpacing(18)
        self._ring = ProgressRing(thickness=10)
        self._ring.setMinimumSize(120, 120)
        self._ring.setMaximumSize(140, 140)
        progress_row.addWidget(self._ring)
        text_col = QVBoxLayout()
        self._status = QLabel("Idle")
        self._status.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._status.setWordWrap(True)
        text_col.addWidget(self._status)
        self._result = QLabel()
        self._result.setTextFormat(Qt.TextFormat.RichText)
        self._result.setWordWrap(True)
        text_col.addWidget(self._result)
        self._cancel = M3Button("Cancel sideload", "outlined", height=44)
        self._cancel.clicked.connect(self.cancel_requested.emit)
        text_col.addWidget(self._cancel)
        text_col.addStretch()
        progress_row.addLayout(text_col, 1)
        layout.addLayout(progress_row)

        root.addWidget(card)
        root.addStretch()
        self._refresh()

    # ------------------------------------------------------------- public API
    def set_device(self, device: DeviceInfo | None) -> None:
        self._device = device
        self._refresh()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh()

    def set_progress(self, percent: float) -> None:
        self._ring.set_value(percent)

    def set_wavy(self, wavy: bool) -> None:
        self._ring.set_wavy(wavy)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_result(self, text: str, level: str) -> None:
        """Show the outcome under the progress ring. `level` is 'success', 'warning' or 'error'."""
        self._result_state = (text, level)
        color = {"success": Colors.SUCCESS, "warning": Colors.WARNING, "error": Colors.ERROR}.get(level, Colors.MUTED)
        self._result.setText(f'<span style="color:{color}">{html.escape(text)}</span>' if text else "")

    def apply_theme(self) -> None:
        """Re-render colours that were baked into labels after a theme change."""
        self._refresh()
        self.set_result(*self._result_state)

    def selected_zip(self) -> Path | None:
        return self._check.path if self._check else None

    # ---------------------------------------------------------------- internals
    def _on_choose(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select the ROM ZIP", self._last_dir, "ROM packages (*.zip);;All files (*)"
        )
        if not path:
            return
        self._last_dir = str(Path(path).parent)
        self._check = validate_rom_zip(Path(path))
        self.set_result("", "info")
        self._refresh()

    def _on_clear(self) -> None:
        self._check = None
        self._refresh()

    def _on_sideload(self) -> None:
        if self._check is None or self._check.level == LEVEL_ERROR or self._busy:
            return
        self.sideload_requested.emit(self._check.path)

    def _refresh(self) -> None:
        # device chip
        _ready, text, hint = sideload_readiness(self._device)
        ready = _ready
        color = Colors.SUCCESS if ready else Colors.WARNING
        self._device_chip.set_state(text + (f". {hint}" if hint else ""), color, size=14)

        # ROM box
        check = self._check
        if check is None:
            self._file_name.setText("No ROM selected")
            self._file_meta.setText("")
            self._file_check.setText("Choose the custom ROM .zip you want to install.")
            self._file_check.setStyleSheet(f"color: {Colors.MUTED};")
        else:
            self._file_name.setText(html.escape(check.path.name))
            size = format_size(check.size) if check.size is not None else "size unknown"
            self._file_meta.setText(f"{html.escape(size)}   |   {html.escape(str(check.path.parent))}")
            glyph, tint = {
                LEVEL_OK: ("✔", Colors.SUCCESS),
                LEVEL_ERROR: ("✖", Colors.ERROR),
            }.get(check.level, ("⚠", Colors.WARNING))
            self._file_check.setText(f"{glyph} {check.message}")
            self._file_check.setStyleSheet(f"color: {tint};")

        usable = check is not None and check.level != LEVEL_ERROR
        self._sideload.setEnabled(usable and not self._busy)
        self._sideload.setToolTip("" if usable else "Choose a valid ROM ZIP first.")
        self._choose.setEnabled(not self._busy)
        self._clear.setEnabled(check is not None and not self._busy)
        self._cancel.setVisible(self._busy)
