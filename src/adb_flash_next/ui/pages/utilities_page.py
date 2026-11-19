"""Utilities page: single Fastboot commands (erase userdata / metadata / FRP, patch vbmeta)."""
from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.core.image_validator import LEVEL_ERROR, LEVEL_OK, ValidationResult, format_size, validate_image
from adb_flash_next.core.models import DeviceInfo
from adb_flash_next.core.utilities import (
    ERASE_FRP,
    ERASE_METADATA,
    ERASE_USERDATA,
    PATCH_VBMETA,
    UtilityAction,
    fastboot_readiness,
)
from adb_flash_next.ui.m3.action_tile import ActionTile
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.chip import StatusChip


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(24, 20, 24, 22)
    layout.setSpacing(14)
    header = QLabel(title)
    header.setObjectName("CardTitle")
    header.setWordWrap(True)
    layout.addWidget(header)
    return card, layout


class UtilitiesPage(QWidget):
    """Emits `utility_requested(key, path_or_None)`. MainWindow builds the plan and confirms it."""

    utility_requested = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._device: DeviceInfo | None = None
        self._busy = False
        self._vbmeta: ValidationResult | None = None
        self._last_dir = str(Path.home())
        self._tiles: dict[str, ActionTile] = {}

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

        title = QLabel("Utilities")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        intro = QLabel(
            "Run a single Fastboot command on the selected device. The device must be in Fastboot "
            "mode. Every command is shown to you first and needs your confirmation."
        )
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self._chip = StatusChip()
        root.addWidget(self._chip)

        # --- erase ---
        erase_card, erase_layout = _card("Erase")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for index, action in enumerate((ERASE_USERDATA, ERASE_METADATA, ERASE_FRP)):
            tile = self._make_tile(action)
            grid.addWidget(tile, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        erase_layout.addLayout(grid)
        warning = QLabel("These commands delete data permanently. You will be asked to type ERASE to confirm.")
        warning.setObjectName("Muted")
        warning.setWordWrap(True)
        erase_layout.addWidget(warning)
        root.addWidget(erase_card)

        # --- patch vbmeta ---
        vbmeta_card, vbmeta_layout = _card("Patch vbmeta")
        hint = QLabel(
            "Select your device's own vbmeta.img. It is flashed with verity and verification disabled."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        vbmeta_layout.addWidget(hint)

        box = QFrame()
        box.setObjectName("DropBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(20, 16, 20, 16)
        box_layout.setSpacing(8)
        self._file_name = QLabel("No vbmeta.img selected")
        self._file_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._file_name.setTextFormat(Qt.TextFormat.RichText)
        self._file_name.setWordWrap(True)
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
        self._choose = M3Button("Choose vbmeta.img...", "tonal", height=44)
        self._choose.clicked.connect(self._on_choose)
        self._clear = M3Button("Clear", "text", height=44)
        self._clear.clicked.connect(self._on_clear)
        buttons.addWidget(self._choose)
        buttons.addWidget(self._clear)
        buttons.addStretch()
        box_layout.addLayout(buttons)
        vbmeta_layout.addWidget(box)

        vbmeta_layout.addWidget(self._make_tile(PATCH_VBMETA, subtitle="Disable verity and verification"))
        root.addWidget(vbmeta_card)
        root.addStretch()
        self._refresh()

    def _make_tile(self, action: UtilityAction, subtitle: str | None = None) -> ActionTile:
        tile = ActionTile(action.label, subtitle or action.command_text, icon=action.icon)
        tile.clicked.connect(lambda _checked=False, a=action: self._on_tile(a))
        self._tiles[action.key] = tile
        return tile

    # ------------------------------------------------------------- public API
    def set_device(self, device: DeviceInfo | None) -> None:
        self._device = device
        self._refresh()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh()

    def apply_theme(self) -> None:
        self._refresh()

    # ---------------------------------------------------------------- internals
    def _on_tile(self, action: UtilityAction) -> None:
        if self._busy:
            return
        if action.key == "patch_vbmeta":
            if self._vbmeta is None or self._vbmeta.level == LEVEL_ERROR:
                return
            self.utility_requested.emit(action.key, self._vbmeta.info.path)
        else:
            self.utility_requested.emit(action.key, None)

    def _on_choose(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select your device's vbmeta.img", self._last_dir, "Android images (*.img);;All files (*)"
        )
        if not path:
            return
        self._last_dir = str(Path(path).parent)
        self._vbmeta = validate_image(Path(path), "vbmeta")
        self._refresh()

    def _on_clear(self) -> None:
        self._vbmeta = None
        self._refresh()

    def _refresh(self) -> None:
        ready, text, hint = fastboot_readiness(self._device)
        color = Colors.SUCCESS if ready else Colors.WARNING
        self._chip.set_state(text + (f". {hint}" if hint else ""), color, size=14)

        check = self._vbmeta
        if check is None:
            self._file_name.setText("No vbmeta.img selected")
            self._file_meta.setText("")
            self._file_check.setText("Choose the vbmeta.img that matches your device and ROM.")
            self._file_check.setStyleSheet(f"color: {Colors.MUTED};")
        else:
            path = check.info.path
            size = format_size(check.info.size) if check.info.size is not None else "size unknown"
            self._file_name.setText(html.escape(path.name))
            self._file_meta.setText(f"{html.escape(size)}   |   {html.escape(str(path.parent))}")
            glyph, tint = {
                LEVEL_OK: ("✔", Colors.SUCCESS),
                LEVEL_ERROR: ("✖", Colors.ERROR),
            }.get(check.level, ("⚠", Colors.WARNING))
            self._file_check.setText(f"{glyph} {check.message}")
            self._file_check.setStyleSheet(f"color: {tint};")

        vbmeta_ok = check is not None and check.level != LEVEL_ERROR
        for key, tile in self._tiles.items():
            usable = ready and not self._busy
            if key == "patch_vbmeta":
                usable = usable and vbmeta_ok
            tile.set_usable(usable)
            command = {
                "erase_userdata": "fastboot erase userdata",
                "erase_metadata": "fastboot erase metadata",
                "erase_frp": "fastboot erase frp",
                "patch_vbmeta": "fastboot flash vbmeta --disable-verity --disable-verification",
            }[key]
            if usable:
                tile.setToolTip(command)
            elif not ready:
                tile.setToolTip(f"{command}\nUnavailable: {text}. {hint}".strip())
            elif key == "patch_vbmeta" and not vbmeta_ok:
                tile.setToolTip(f"{command}\nUnavailable: choose a valid vbmeta.img first.")
            else:
                tile.setToolTip(f"{command}\nUnavailable: another operation is running.")
        self._choose.setEnabled(not self._busy)
        self._clear.setEnabled(check is not None and not self._busy)
