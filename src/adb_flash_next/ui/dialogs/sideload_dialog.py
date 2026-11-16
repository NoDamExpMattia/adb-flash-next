"""Guided dialog shown when the user presses 'Sideload ROM'.

It explains how to enter recovery, how to format data (manually) and how to start ADB
sideload, waits for the device to show up in sideload mode, and only then allows Start.
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.core.image_validator import format_size
from adb_flash_next.core.models import DeviceInfo
from adb_flash_next.core.recovery_guide import RECOVERY_STEPS
from adb_flash_next.core.sideload import (
    LEVEL_ERROR,
    LEVEL_OK,
    ZipCheck,
    command_preview,
    sideload_readiness,
)
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.checkbox import M3Checkbox
from adb_flash_next.ui.widgets.chip import StatusChip


class SideloadDialog(QDialog):
    """Accepted only when everything is confirmed AND the device is in sideload mode."""

    def __init__(self, check: ZipCheck, device: DeviceInfo | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._check = check
        self._device = device
        self.setWindowTitle("Before you sideload")
        self.resize(780, 700)

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        title = QLabel("Before you sideload")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # --- what will be sent ---
        summary = QFrame()
        summary.setObjectName("Card")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(20, 16, 20, 16)
        summary_layout.setSpacing(6)
        self._summary = QLabel()
        self._summary.setTextFormat(Qt.TextFormat.RichText)
        self._summary.setWordWrap(True)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary_layout.addWidget(self._summary)
        layout.addWidget(summary)

        zip_color = {LEVEL_OK: Colors.SUCCESS, LEVEL_ERROR: Colors.ERROR}.get(check.level, Colors.WARNING)
        zip_glyph = {LEVEL_OK: "✔", LEVEL_ERROR: "✖"}.get(check.level, "⚠")
        zip_note = QLabel(f"{zip_glyph} {check.message}")
        zip_note.setWordWrap(True)
        zip_note.setStyleSheet(f"color: {zip_color};")
        layout.addWidget(zip_note)

        # --- live device status ---
        self._status = StatusChip()
        layout.addWidget(self._status)

        # --- the guide ---
        for step in RECOVERY_STEPS:
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 14, 20, 16)
            card_layout.setSpacing(6)
            heading = QLabel(step.title)
            heading.setObjectName("CardTitle")
            if step.warning:
                heading.setStyleSheet(f"color: {Colors.WARNING};")
            card_layout.addWidget(heading)
            body = QLabel("<br>".join(f"•&nbsp;&nbsp;{html.escape(line)}" for line in step.bullets))
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setWordWrap(True)
            if step.warning:
                body.setStyleSheet(f"color: {Colors.WARNING};")
            card_layout.addWidget(body)
            layout.addWidget(card)

        text = "I have read the steps and warnings above, and formatted data only if my ROM's instructions require it"
        self._ack = M3Checkbox(text)
        self._ack.toggled.connect(self._update_start)
        layout.addWidget(self._ack)
        layout.addStretch()

        # --- footer ---
        footer = QHBoxLayout()
        cancel = M3Button("Cancel", "outlined", height=48)
        cancel.clicked.connect(self.reject)
        self._start = M3Button("Start sideload", "filled", icon="install", height=48)
        self._start.clicked.connect(self.accept)
        footer.addStretch()
        footer.addWidget(cancel)
        footer.addWidget(self._start)
        outer.addLayout(footer)

        self._refresh()

    # ------------------------------------------------------------- public API
    def set_device(self, device: DeviceInfo | None) -> None:
        """Called whenever detection reports a change, so the dialog always shows the live state."""
        self._device = device
        self._refresh()

    # ---------------------------------------------------------------- internals
    def _refresh(self) -> None:
        ready, text, hint = sideload_readiness(self._device)
        color = Colors.SUCCESS if ready else Colors.WARNING
        self._status.set_state(text + (f". {hint}" if hint else ". You can start once it is detected."), color, size=14)
        size = format_size(self._check.size) if self._check.size is not None else "size unknown"
        if self._device is not None:
            command = command_preview(self._device.serial, self._check.path)
            device_line = f"{html.escape(self._device.product_text())} ({html.escape(self._device.serial)})"
        else:
            command = "(select a device on the Dashboard)"
            device_line = "no device selected"
        self._summary.setText(
            f"<b>ROM:</b> {html.escape(self._check.path.name)} ({html.escape(size)})<br>"
            f"<b>Device:</b> {device_line}<br>"
            f"<b>Command:</b> <span style='font-family:Consolas'>{html.escape(command)}</span>"
        )
        self._update_start()

    def _update_start(self, *_args) -> None:
        ready, _text, _hint = sideload_readiness(self._device)
        self._start.setEnabled(ready and self._ack.isChecked() and self._check.level != LEVEL_ERROR)
