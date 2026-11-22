"""Auto Flash page: choose images, slots and the ROM ZIP, then follow the whole procedure."""
from __future__ import annotations

import dataclasses
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

from adb_flash_next.config.constants import SUPPORTED_PARTITIONS
from adb_flash_next.core.auto_flash import STEP_TITLES, AutoStage, step_states
from adb_flash_next.core.flash_plan import PartitionSelection
from adb_flash_next.core.image_validator import format_size
from adb_flash_next.core.models import DeviceInfo
from adb_flash_next.core.recovery_guide import AUTO_FLASH_STEPS
from adb_flash_next.core.sideload import LEVEL_ERROR, LEVEL_OK, ZipCheck, validate_rom_zip
from adb_flash_next.core.utilities import fastboot_readiness
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.pages.images_page import PartitionRow
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.chip import StatusChip
from adb_flash_next.ui.widgets.confetti import ConfettiOverlay
from adb_flash_next.ui.widgets.progress_ring import ProgressRing


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(24, 20, 24, 22)
    layout.setSpacing(12)
    header = QLabel(title)
    header.setObjectName("CardTitle")
    header.setWordWrap(True)
    layout.addWidget(header)
    return card, layout


class AutoFlashPage(QWidget):
    """Shows state and emits requests; AutoFlashController runs the procedure."""

    start_requested = Signal()
    stop_requested = Signal()
    reboot_recovery_requested = Signal()
    sideload_requested = Signal()
    cancel_sideload_requested = Signal()
    check_boot_requested = Signal()
    stop_waiting_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._device: DeviceInfo | None = None
        self._device_signature: tuple | None = None
        self._stage = AutoStage.IDLE
        self._failed = False
        self._waiting = False
        self._zip_check: ZipCheck | None = None
        self._message_state = ("", "info")
        self._last_dir = str(Path.home())
        self._rows: list[PartitionRow] = []

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

        title = QLabel("Auto Flash")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        intro = QLabel(
            "Flash the partitions you choose, then install a ROM with ADB sideload. The bootloader must "
            "be unlocked (it is checked first). After flashing, the procedure pauses in recovery: you "
            "format data by hand only if your ROM requires it. The app only explains how."
        )
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self._chip = StatusChip()
        root.addWidget(self._chip)

        # ---------------------------------------------------------------- setup
        self._setup = QWidget()
        setup = QVBoxLayout(self._setup)
        setup.setContentsMargins(0, 0, 0, 0)
        setup.setSpacing(16)

        images_card, images = _card("1. Partitions, images and slots")
        note = QLabel("Untick the partitions you do not need. Pick the slot (A/B devices only).")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        images.addWidget(note)
        for partition in SUPPORTED_PARTITIONS:
            row = PartitionRow(partition)
            row.connect_buttons(self._on_choose_image, self._on_clear_image)
            self._rows.append(row)
            images.addWidget(row)
        setup.addWidget(images_card)

        zip_card, zip_layout = _card("2. ROM ZIP")
        box = QFrame()
        box.setObjectName("DropBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(20, 16, 20, 16)
        box_layout.setSpacing(8)
        self._zip_name = QLabel("No ROM selected")
        self._zip_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._zip_name.setTextFormat(Qt.TextFormat.RichText)
        self._zip_name.setWordWrap(True)
        box_layout.addWidget(self._zip_name)
        self._zip_meta = QLabel()
        self._zip_meta.setObjectName("Muted")
        self._zip_meta.setTextFormat(Qt.TextFormat.RichText)
        self._zip_meta.setWordWrap(True)
        box_layout.addWidget(self._zip_meta)
        self._zip_note = QLabel()
        self._zip_note.setWordWrap(True)
        box_layout.addWidget(self._zip_note)
        zip_buttons = QHBoxLayout()
        self._zip_choose = M3Button("Choose ZIP...", "tonal", height=44)
        self._zip_choose.clicked.connect(self._on_choose_zip)
        self._zip_clear = M3Button("Clear", "text", height=44)
        self._zip_clear.clicked.connect(self._on_clear_zip)
        zip_buttons.addWidget(self._zip_choose)
        zip_buttons.addWidget(self._zip_clear)
        zip_buttons.addStretch()
        box_layout.addLayout(zip_buttons)
        zip_layout.addWidget(box)
        setup.addWidget(zip_card)

        start_row = QHBoxLayout()
        self._start_button = M3Button("Review and start", "filled", icon="auto", height=56)
        self._start_button.setMinimumWidth(260)
        self._start_button.clicked.connect(self.start_requested.emit)
        start_row.addStretch()
        start_row.addWidget(self._start_button)
        setup.addLayout(start_row)
        root.addWidget(self._setup)

        # -------------------------------------------------------------- progress
        progress_card, progress = _card("Progress")
        top = QHBoxLayout()
        top.setSpacing(20)
        self._ring = ProgressRing(thickness=12)
        self._ring.setMinimumSize(150, 150)
        self._ring.setMaximumSize(190, 190)
        top.addWidget(self._ring)
        steps_col = QVBoxLayout()
        steps_col.setSpacing(6)
        self._step_labels: list[QLabel] = []
        for _title in STEP_TITLES:
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            self._step_labels.append(label)
            steps_col.addWidget(label)
        steps_col.addStretch()
        top.addLayout(steps_col, 1)
        progress.addLayout(top)

        self._status = QLabel("Idle")
        self._status.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._status.setWordWrap(True)
        progress.addWidget(self._status)
        self._message = QLabel()
        self._message.setTextFormat(Qt.TextFormat.RichText)
        self._message.setWordWrap(True)
        progress.addWidget(self._message)

        buttons = QHBoxLayout()
        self._btn_stop = M3Button("Stop after current step", "outlined", height=44)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        self._btn_reboot = M3Button("Reboot to recovery", "tonal", icon="reboot", height=48)
        self._btn_reboot.clicked.connect(self.reboot_recovery_requested.emit)
        self._btn_sideload = M3Button("Sideload", "filled", icon="install", height=48)
        self._btn_sideload.clicked.connect(self.sideload_requested.emit)
        self._btn_cancel_sideload = M3Button("Cancel sideload", "outlined", height=44)
        self._btn_cancel_sideload.clicked.connect(self.cancel_sideload_requested.emit)
        self._btn_stop_waiting = M3Button("Stop waiting", "outlined", height=44)
        self._btn_stop_waiting.clicked.connect(self.stop_waiting_requested.emit)
        self._btn_check_boot = M3Button("Check again", "tonal", icon="refresh", height=44)
        self._btn_check_boot.clicked.connect(self.check_boot_requested.emit)
        self._btn_reset = M3Button("Start over", "text", height=44)
        self._btn_reset.clicked.connect(self.reset_requested.emit)
        for button in (self._btn_stop, self._btn_reboot, self._btn_sideload, self._btn_cancel_sideload,
                       self._btn_stop_waiting, self._btn_check_boot, self._btn_reset):
            buttons.addWidget(button)
        buttons.addStretch()
        progress.addLayout(buttons)
        root.addWidget(progress_card)

        # ---------------------------------------------------- recovery instructions
        self._guide, guide = _card("Recovery instructions")
        for step in AUTO_FLASH_STEPS:
            heading = QLabel(step.title)
            heading.setStyleSheet("font-weight: bold;")
            heading.setProperty("warn", step.warning)
            body = QLabel("<br>".join(f"•&nbsp;&nbsp;{html.escape(line)}" for line in step.bullets))
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setWordWrap(True)
            body.setProperty("warn", step.warning)
            guide.addWidget(heading)
            guide.addWidget(body)
        root.addWidget(self._guide)
        root.addStretch()

        self._confetti = ConfettiOverlay(self)
        self.set_stage(AutoStage.IDLE)
        self._render_zip()
        self._render_message()

    # ------------------------------------------------------------- public API
    def selections(self) -> list[PartitionSelection]:
        return [dataclasses.replace(row.selection) for row in self._rows]

    def zip_path(self) -> Path | None:
        return self._zip_check.path if self._zip_check else None

    def set_device(self, device: DeviceInfo | None) -> None:
        self._device = device
        self._refresh_chip()
        if self._stage is AutoStage.IDLE:
            self._configure_rows()

    def set_stage(self, stage: AutoStage, *, failed: bool = False, waiting: bool = False) -> None:
        self._stage = stage
        self._failed = failed
        self._waiting = waiting
        self._render_stepper()
        self._guide.setVisible(stage is AutoStage.RECOVERY and not failed)
        self._restyle_guide()
        self._update_buttons()
        self._setup.setEnabled(stage is AutoStage.IDLE)
        self._refresh_chip()
        if stage is AutoStage.IDLE:
            self._configure_rows()

    def set_progress(self, percent: float) -> None:
        self._ring.set_value(percent)

    def set_wavy(self, wavy: bool) -> None:
        self._ring.set_wavy(wavy)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_message(self, text: str, level: str) -> None:
        """`level`: 'info', 'success', 'warning' or 'error'."""
        self._message_state = (text, level)
        self._render_message()

    def set_sideload_enabled(self, enabled: bool) -> None:
        self._btn_sideload.setEnabled(enabled)

    def celebrate(self) -> None:
        self._confetti.start([Colors.ACCENT, Colors.SUCCESS, Colors.WARNING, Colors.TEXT])

    def shutdown(self) -> None:
        for row in self._rows:
            row.shutdown()

    def apply_theme(self) -> None:
        self._refresh_chip()
        self._render_zip()
        self._render_stepper()
        self._render_message()
        self._restyle_guide()
        for row in self._rows:
            row.refresh()

    # ---------------------------------------------------------------- internals
    def _configure_rows(self) -> None:
        device = self._device
        signature = None if device is None else (device.key, device.scheme, device.active_slot)
        if signature == self._device_signature:
            return
        self._device_signature = signature
        for row in self._rows:
            row.configure_slot(device)

    def _refresh_chip(self) -> None:
        if self._stage is not AutoStage.IDLE:
            mode = self._device.mode.value if self._device else "no device"
            self._chip.set_state(f"Auto Flash is in progress. Device: {mode}.", Colors.WARNING, size=14)
            return
        ready, text, hint = fastboot_readiness(self._device)
        if ready:
            hint = "The bootloader is checked first: it must report 'unlocked: yes' or nothing is flashed."
        elif self._device is not None and not self._device.is_excluded:
            hint = (
                "Auto Flash starts from Fastboot mode. Use the Reboot page to restart into the bootloader, "
                "then press Refresh on the Dashboard."
            )
        self._chip.set_state(f"{text}. {hint}" if hint else text, Colors.SUCCESS if ready else Colors.WARNING, size=14)

    def _render_stepper(self) -> None:
        glyphs = {"pending": ("○", Colors.MUTED, Colors.MUTED), "active": ("●", Colors.ACCENT, Colors.TEXT),
                  "done": ("✔", Colors.SUCCESS, Colors.TEXT), "failed": ("✖", Colors.ERROR, Colors.ERROR)}
        for label, title, state in zip(self._step_labels, STEP_TITLES, step_states(self._stage, self._failed)):
            glyph, glyph_color, text_color = glyphs[state]
            weight = "bold" if state in ("active", "failed") else "normal"
            label.setText(
                f'<span style="color:{glyph_color}">{glyph}</span>&nbsp;&nbsp;'
                f'<span style="color:{text_color}; font-weight:{weight}">{html.escape(title)}</span>'
            )

    def _render_message(self) -> None:
        text, level = self._message_state
        color = {"success": Colors.SUCCESS, "warning": Colors.WARNING, "error": Colors.ERROR}.get(level, Colors.MUTED)
        self._message.setText(f'<span style="color:{color}">{html.escape(text)}</span>' if text else "")

    def _restyle_guide(self) -> None:
        for label in self._guide.findChildren(QLabel):
            if label.property("warn"):
                label.setStyleSheet(f"color: {Colors.WARNING};" + (" font-weight: bold;" if "bold" in label.styleSheet() else ""))

    def _update_buttons(self) -> None:
        stage, failed, waiting = self._stage, self._failed, self._waiting
        self._btn_stop.setVisible(stage is AutoStage.FLASHING and not failed)
        self._btn_reboot.setVisible(stage is AutoStage.RECOVERY and not failed)
        self._btn_sideload.setVisible(stage is AutoStage.RECOVERY and not failed)
        self._btn_cancel_sideload.setVisible(stage is AutoStage.SIDELOAD and not failed)
        self._btn_stop_waiting.setVisible(stage is AutoStage.BOOT and waiting and not failed)
        self._btn_check_boot.setVisible(stage is AutoStage.BOOT and not waiting and not failed)
        self._btn_reset.setVisible(
            stage is not AutoStage.IDLE
            and (failed or stage in (AutoStage.DONE, AutoStage.RECOVERY) or (stage is AutoStage.BOOT and not waiting))
        )

    # -- file choosers -------------------------------------------------------------------
    def _on_choose_image(self, row: PartitionRow) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, f"Select the image for {row.selection.partition}", self._last_dir,
            "Android images (*.img);;All files (*)",
        )
        if path:
            self._last_dir = str(Path(path).parent)
            row.set_path(Path(path))

    def _on_clear_image(self, row: PartitionRow) -> None:
        row.set_path(None)

    def _on_choose_zip(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select the ROM ZIP", self._last_dir, "ROM packages (*.zip);;All files (*)"
        )
        if path:
            self._last_dir = str(Path(path).parent)
            self._zip_check = validate_rom_zip(Path(path))
            self._render_zip()

    def _on_clear_zip(self) -> None:
        self._zip_check = None
        self._render_zip()

    def _render_zip(self) -> None:
        check = self._zip_check
        if check is None:
            self._zip_name.setText("No ROM selected")
            self._zip_meta.setText("")
            self._zip_note.setText("Choose the custom ROM .zip you want to install.")
            self._zip_note.setStyleSheet(f"color: {Colors.MUTED};")
        else:
            size = format_size(check.size) if check.size is not None else "size unknown"
            self._zip_name.setText(html.escape(check.path.name))
            self._zip_meta.setText(f"{html.escape(size)}   |   {html.escape(str(check.path.parent))}")
            glyph, tint = {LEVEL_OK: ("✔", Colors.SUCCESS), LEVEL_ERROR: ("✖", Colors.ERROR)}.get(
                check.level, ("⚠", Colors.WARNING)
            )
            self._zip_note.setText(f"{glyph} {check.message}")
            self._zip_note.setStyleSheet(f"color: {tint};")
        self._zip_clear.setEnabled(check is not None)
