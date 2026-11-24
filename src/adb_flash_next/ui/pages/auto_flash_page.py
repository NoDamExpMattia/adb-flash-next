"""Auto Flash page (compact): ring top-left, tick + Choose file per partition, ROM + Sideload + Logs below."""
from __future__ import annotations

import dataclasses
import html
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
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
from adb_flash_next.core.image_validator import LEVEL_ERROR, LEVEL_OK, format_size, validate_image
from adb_flash_next.core.models import DeviceInfo, PartitionScheme
from adb_flash_next.core.recovery_guide import AUTO_FLASH_STEPS
from adb_flash_next.core.slot_resolver import SlotChoice
from adb_flash_next.core.sideload import LEVEL_ERROR as ZIP_ERROR
from adb_flash_next.core.sideload import LEVEL_OK as ZIP_OK
from adb_flash_next.core.sideload import ZipCheck, validate_rom_zip
from adb_flash_next.core.utilities import fastboot_readiness
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.checkbox import M3Checkbox
from adb_flash_next.ui.widgets.chip import StatusChip
from adb_flash_next.ui.widgets.confetti import ConfettiOverlay
from adb_flash_next.ui.widgets.elided_label import ElidedLabel
from adb_flash_next.ui.widgets.log_panel import LogPanel
from adb_flash_next.ui.widgets.progress_ring import ProgressRing
from adb_flash_next.ui.widgets.toggle_button import ToggleButton


def _card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 12, 18, 14)
    layout.setSpacing(6)
    if title:
        header = QLabel(title)
        header.setObjectName("CardTitle")
        layout.addWidget(header)
    return card, layout


class CompactRow(QWidget):
    """One partition on one line: [tick + name] [slot] [file name] [mark] [Choose file...]."""

    changed = Signal()

    def __init__(self, partition: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selection = PartitionSelection(partition=partition)
        self._extract = False
        self._slot_available = False

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self._check = M3Checkbox(partition, True)
        self._check.setFixedWidth(168)
        self._check.toggled.connect(self._on_toggled)
        self._slot = QComboBox()
        self._slot.setFixedWidth(168)
        self._slot.currentIndexChanged.connect(self._on_slot)
        self._file = ElidedLabel()
        self._mark = QLabel()
        self._mark.setFixedWidth(20)
        self._choose = M3Button("Choose file...", "tonal", height=36)
        for widget, stretch in ((self._check, 0), (self._slot, 0), (self._file, 1), (self._mark, 0), (self._choose, 0)):
            row.addWidget(widget, stretch)
        self.configure_slot(None)
        self.refresh()

    def connect_choose(self, callback) -> None:
        self._choose.clicked.connect(lambda: callback(self))

    # -- state --------------------------------------------------------------------
    def _on_toggled(self, checked: bool) -> None:
        self.selection.enabled = checked
        self._apply_enabled()
        self.changed.emit()

    def _on_slot(self, _index: int) -> None:
        value = self._slot.currentData()
        self.selection.slot = SlotChoice(value) if value else None
        self.changed.emit()

    def _apply_enabled(self) -> None:
        on = self.selection.enabled
        self._slot.setEnabled(on and self._slot_available)
        self._file.setEnabled(on)
        self._choose.setEnabled(on)

    def set_path(self, path: Path | None) -> None:
        self.selection.path = path
        self.refresh()
        self.changed.emit()

    def set_extract_mode(self, on: bool) -> None:
        """When the images come from the ROM there is nothing to choose."""
        self._extract = on
        self._choose.setVisible(not on)
        self.refresh()

    def configure_slot(self, device: DeviceInfo | None) -> None:
        self._slot.blockSignals(True)
        self._slot.clear()
        self.selection.slot = None
        self._slot_available = False
        if device is None:
            self._slot.addItem("No device", None)
        elif device.scheme is PartitionScheme.AB:
            self._slot.addItem("Select slot...", None)
            for choice in SlotChoice:
                self._slot.addItem(choice.label, choice.value)
            self._slot_available = True
            if device.active_slot in ("a", "b"):  # default: the active slot
                self._slot.setCurrentIndex(max(self._slot.findData(device.active_slot), 0))
                self.selection.slot = SlotChoice(device.active_slot)
        elif device.scheme is PartitionScheme.A_ONLY:
            self._slot.addItem("A-only (no slot)", None)
        else:
            self._slot.addItem("Unknown scheme", None)
        self._slot.blockSignals(False)
        self._apply_enabled()

    def refresh(self) -> None:
        path = self.selection.path
        self._mark.setText("")
        self._file.setStyleSheet(f"color: {Colors.MUTED};")
        if self._extract:
            self._file.set_full_text("taken from the ROM (payload.bin)")
        elif path is None:
            self._file.set_full_text("No file selected")
        else:
            result = validate_image(path, self.selection.partition)
            glyph, color = {LEVEL_OK: ("✔", Colors.SUCCESS), LEVEL_ERROR: ("✖", Colors.ERROR)}.get(
                result.level, ("⚠", Colors.WARNING)
            )
            self._file.set_full_text(path.name, tooltip=f"{path}\n{result.message}")
            self._file.setStyleSheet(f"color: {Colors.TEXT};")
            self._mark.setText(glyph)
            self._mark.setStyleSheet(f"color: {color}; font-weight: bold;")
            self._mark.setToolTip(result.message)
        self._apply_enabled()


class _LogDialog(QDialog):
    """Live view of this run's log."""

    def __init__(self, entries: list[tuple[str, str, str]], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto Flash: log")
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        self.panel = LogPanel()
        for timestamp, level, message in entries:
            self.panel.append_entry(level, message, timestamp)
        layout.addWidget(self.panel, 1)
        buttons = QHBoxLayout()
        copy = M3Button("Copy log", "tonal", height=40)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.panel.plain_text()))
        close = M3Button("Close", "outlined", height=40)
        close.clicked.connect(self.close)
        buttons.addWidget(copy)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)


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
        self._sideload_busy = False
        self._extract_on = False
        self._extract_tool: Path | None = None
        self._zip_check: ZipCheck | None = None
        self._message_state = ("", "info")
        self._last_dir = str(Path.home())
        self._rows: list[CompactRow] = []
        self._log_entries: list[tuple[str, str, str]] = []
        self._log_dialog: _LogDialog | None = None

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
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(10)

        # ---- top: title, Extract partitions on/off, Start
        head = QHBoxLayout()
        title = QLabel("Auto Flash")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        head.addWidget(title)
        head.addStretch()
        self._extract_toggle = ToggleButton("Extract partitions: ON", "Extract partitions: OFF")
        self._extract_toggle.setToolTip(
            "ON: payload-dumper-go extracts the ticked partitions from the ROM's payload.bin and they are "
            "flashed with fastboot. OFF: you choose the image files yourself."
        )
        self._extract_toggle.toggled.connect(self._on_extract_toggled)
        self._start_button = M3Button("Review and start", "filled", icon="auto", height=44)
        self._start_button.clicked.connect(self.start_requested.emit)
        head.addWidget(self._extract_toggle)
        head.addWidget(self._start_button)
        root.addLayout(head)
        self._extract_hint = QLabel()
        self._extract_hint.setWordWrap(True)
        self._extract_hint.hide()
        root.addWidget(self._extract_hint)
        self._chip = StatusChip()
        root.addWidget(self._chip)

        # ---- progress: ring top-left, steps and buttons to its right
        progress = QHBoxLayout()
        progress.setSpacing(16)
        self._ring = ProgressRing(thickness=9)
        self._ring.setFixedSize(124, 124)
        progress.addWidget(self._ring, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self._step_labels: list[QLabel] = []
        for _title in STEP_TITLES:
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            self._step_labels.append(label)
            col.addWidget(label)
        self._status = QLabel("Idle")
        self._status.setStyleSheet("font-weight: bold;")
        self._status.setWordWrap(True)
        col.addWidget(self._status)
        self._message = QLabel()
        self._message.setTextFormat(Qt.TextFormat.RichText)
        self._message.setWordWrap(True)
        col.addWidget(self._message)
        buttons = QHBoxLayout()
        self._btn_stop = M3Button("Stop after current step", "outlined", height=36)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        self._btn_reboot = M3Button("Reboot to recovery", "tonal", icon="reboot", height=36)
        self._btn_reboot.clicked.connect(self.reboot_recovery_requested.emit)
        self._btn_cancel_sideload = M3Button("Cancel sideload", "outlined", height=36)
        self._btn_cancel_sideload.clicked.connect(self.cancel_sideload_requested.emit)
        self._btn_stop_waiting = M3Button("Stop waiting", "outlined", height=36)
        self._btn_stop_waiting.clicked.connect(self.stop_waiting_requested.emit)
        self._btn_check_boot = M3Button("Check again", "tonal", icon="refresh", height=36)
        self._btn_check_boot.clicked.connect(self.check_boot_requested.emit)
        self._btn_reset = M3Button("Start over", "text", height=36)
        self._btn_reset.clicked.connect(self.reset_requested.emit)
        for button in (self._btn_stop, self._btn_reboot, self._btn_cancel_sideload,
                       self._btn_stop_waiting, self._btn_check_boot, self._btn_reset):
            buttons.addWidget(button)
        buttons.addStretch()
        col.addLayout(buttons)
        progress.addLayout(col, 1)
        root.addLayout(progress)

        # ---- recovery instructions (only in the recovery stage)
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

        # ---- partitions: one line each
        self._parts_card, parts = _card("Partitions")
        for partition in SUPPORTED_PARTITIONS:
            row = CompactRow(partition)
            row.connect_choose(self._on_choose_image)
            self._rows.append(row)
            parts.addWidget(row)
        root.addWidget(self._parts_card)

        # ---- bottom: ADB Sideload (ROM + Sideload + Logs)
        bar, bar_layout = _card()
        line = QHBoxLayout()
        line.setSpacing(10)
        caption = QLabel("ADB Sideload")
        caption.setObjectName("CardTitle")
        self._zip_name = ElidedLabel("No ROM selected")
        self._zip_mark = QLabel()
        self._zip_mark.setFixedWidth(20)
        self._zip_choose = M3Button("Choose ROM...", "tonal", height=36)
        self._zip_choose.clicked.connect(self._on_choose_zip)
        self._btn_sideload = M3Button("Sideload", "filled", icon="install", height=36)
        self._btn_sideload.setToolTip("Available after flashing, once the device is in recovery.")
        self._btn_sideload.clicked.connect(self.sideload_requested.emit)
        self._btn_logs = M3Button("Logs", "text", height=36)
        self._btn_logs.setToolTip("Show the log of this run")
        self._btn_logs.clicked.connect(self._open_logs)
        for widget, stretch in ((caption, 0), (self._zip_name, 1), (self._zip_mark, 0),
                                (self._zip_choose, 0), (self._btn_sideload, 0), (self._btn_logs, 0)):
            line.addWidget(widget, stretch)
        bar_layout.addLayout(line)
        self._zip_note = QLabel()
        self._zip_note.setWordWrap(True)
        self._zip_note.hide()
        bar_layout.addWidget(self._zip_note)
        root.addWidget(bar)
        root.addStretch()

        self._confetti = ConfettiOverlay(self)
        self.set_stage(AutoStage.IDLE)
        self._render_zip()
        self._render_message()
        self._render_extract_hint()

    # ------------------------------------------------------------- public API
    def selections(self) -> list[PartitionSelection]:
        return [dataclasses.replace(row.selection) for row in self._rows]

    def zip_path(self) -> Path | None:
        return self._zip_check.path if self._zip_check else None

    def extract_enabled(self) -> bool:
        return self._extract_on

    def set_extract_tool(self, tool: Path | None) -> None:
        self._extract_tool = tool
        self._render_extract_hint()

    def set_device(self, device: DeviceInfo | None) -> None:
        self._device = device
        self._refresh_chip()
        if self._stage is AutoStage.IDLE:
            self._configure_rows()

    def set_stage(self, stage: AutoStage, *, failed: bool = False, waiting: bool = False) -> None:
        self._stage, self._failed, self._waiting = stage, failed, waiting
        idle = stage is AutoStage.IDLE
        self._render_stepper()
        self._guide.setVisible(stage is AutoStage.RECOVERY and not failed)
        self._restyle_guide()
        self._update_buttons()
        for widget in (self._parts_card, self._zip_choose, self._extract_toggle, self._start_button):
            widget.setEnabled(idle)
        self._refresh_chip()
        if idle:
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
        self._sideload_busy = not enabled
        self._update_buttons()

    def append_log(self, level: str, message: str) -> None:
        entry = (datetime.now().strftime("%H:%M:%S"), level.upper(), message)
        self._log_entries.append(entry)
        if len(self._log_entries) > 5000:
            del self._log_entries[:1000]
        if self._log_dialog is not None:
            self._log_dialog.panel.append_entry(entry[1], entry[2], entry[0])

    def celebrate(self) -> None:
        self._confetti.start([Colors.ACCENT, Colors.SUCCESS, Colors.WARNING, Colors.TEXT])

    def shutdown(self) -> None:
        if self._log_dialog is not None:
            self._log_dialog.close()

    def apply_theme(self) -> None:
        self._refresh_chip()
        self._render_zip()
        self._render_stepper()
        self._render_message()
        self._render_extract_hint()
        self._restyle_guide()
        for row in self._rows:
            row.refresh()

    # ---------------------------------------------------------------- internals
    def _on_extract_toggled(self, checked: bool) -> None:
        self._extract_on = checked
        for row in self._rows:
            row.set_extract_mode(checked)
        self._render_extract_hint()

    def _render_extract_hint(self) -> None:
        if not self._extract_on:
            self._extract_hint.hide()
            return
        if self._extract_tool is None:
            self._extract_hint.setText(
                "payload-dumper-go was not found. Put payload-dumper-go.exe in the 'bin' folder next to the "
                "app, or choose it in Settings."
            )
            self._extract_hint.setStyleSheet(f"color: {Colors.ERROR};")
        else:
            self._extract_hint.setText(
                f"The ticked partitions will be extracted from the ROM with {self._extract_tool.name} "
                "(full OTA ROMs with payload.bin only)."
            )
            self._extract_hint.setStyleSheet(f"color: {Colors.MUTED};")
        self._extract_hint.show()

    def _open_logs(self) -> None:
        if self._log_dialog is None:
            dialog = _LogDialog(self._log_entries, self)
            dialog.finished.connect(lambda _code=0: setattr(self, "_log_dialog", None))
            self._log_dialog = dialog
        self._log_dialog.show()
        self._log_dialog.raise_()
        self._log_dialog.activateWindow()

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
            self._chip.set_state(f"Auto Flash is in progress. Device: {mode}.", Colors.WARNING, size=13)
            return
        ready, text, hint = fastboot_readiness(self._device)
        if ready:
            hint = "The bootloader must report 'unlocked: yes' or nothing is flashed."
        elif self._device is not None and not self._device.is_excluded:
            hint = "Auto Flash starts from Fastboot mode (Reboot page, then Refresh on the Dashboard)."
        self._chip.set_state(f"{text}. {hint}" if hint else text, Colors.SUCCESS if ready else Colors.WARNING, size=13)

    def _render_stepper(self) -> None:
        glyphs = {"pending": ("○", Colors.MUTED, Colors.MUTED), "active": ("●", Colors.ACCENT, Colors.TEXT),
                  "done": ("✔", Colors.SUCCESS, Colors.TEXT), "failed": ("✖", Colors.ERROR, Colors.ERROR)}
        for label, title, state in zip(self._step_labels, STEP_TITLES, step_states(self._stage, self._failed)):
            glyph, glyph_color, text_color = glyphs[state]
            weight = "bold" if state in ("active", "failed") else "normal"
            label.setText(
                f'<span style="color:{glyph_color}">{glyph}</span>&nbsp;'
                f'<span style="color:{text_color}; font-size:12px; font-weight:{weight}">{html.escape(title)}</span>'
            )

    def _render_message(self) -> None:
        text, level = self._message_state
        color = {"success": Colors.SUCCESS, "warning": Colors.WARNING, "error": Colors.ERROR}.get(level, Colors.MUTED)
        self._message.setText(f'<span style="color:{color}">{html.escape(text)}</span>' if text else "")

    def _restyle_guide(self) -> None:
        for label in self._guide.findChildren(QLabel):
            if label.property("warn"):
                bold = " font-weight: bold;" if "bold" in label.styleSheet() else ""
                label.setStyleSheet(f"color: {Colors.WARNING};{bold}")

    def _update_buttons(self) -> None:
        stage, failed, waiting = self._stage, self._failed, self._waiting
        flashing = stage in (AutoStage.FLASHING, AutoStage.EXTRACTING) and not failed
        self._btn_stop.setVisible(flashing)
        self._btn_stop.setText("Cancel extraction" if stage is AutoStage.EXTRACTING else "Stop after current step")
        self._btn_reboot.setVisible(stage is AutoStage.RECOVERY and not failed)
        self._btn_cancel_sideload.setVisible(stage is AutoStage.SIDELOAD and not failed)
        self._btn_stop_waiting.setVisible(stage is AutoStage.BOOT and waiting and not failed)
        self._btn_check_boot.setVisible(stage is AutoStage.BOOT and not waiting and not failed)
        self._btn_reset.setVisible(
            stage is not AutoStage.IDLE
            and (failed or stage in (AutoStage.DONE, AutoStage.RECOVERY) or (stage is AutoStage.BOOT and not waiting))
        )
        self._btn_sideload.setEnabled(stage is AutoStage.RECOVERY and not failed and not self._sideload_busy)

    # -- file choosers -------------------------------------------------------------------
    def _on_choose_image(self, row: CompactRow) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, f"Select the image for {row.selection.partition}", self._last_dir,
            "Android images (*.img);;All files (*)",
        )
        if path:
            self._last_dir = str(Path(path).parent)
            row.set_path(Path(path))

    def _on_choose_zip(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select the ROM ZIP", self._last_dir, "ROM packages (*.zip);;All files (*)"
        )
        if path:
            self._last_dir = str(Path(path).parent)
            self._zip_check = validate_rom_zip(Path(path))
            self._render_zip()

    def _render_zip(self) -> None:
        check = self._zip_check
        self._zip_mark.setText("")
        self._zip_note.hide()
        if check is None:
            self._zip_name.set_full_text("No ROM selected")
            self._zip_name.setStyleSheet(f"color: {Colors.MUTED};")
            return
        size = format_size(check.size) if check.size is not None else "size unknown"
        self._zip_name.set_full_text(f"{check.path.name}  ({size})", tooltip=str(check.path))
        self._zip_name.setStyleSheet(f"color: {Colors.TEXT};")
        glyph, tint = {ZIP_OK: ("✔", Colors.SUCCESS), ZIP_ERROR: ("✖", Colors.ERROR)}.get(
            check.level, ("⚠", Colors.WARNING)
        )
        self._zip_mark.setText(glyph)
        self._zip_mark.setStyleSheet(f"color: {tint}; font-weight: bold;")
        self._zip_mark.setToolTip(check.message)
        if check.level != ZIP_OK:  # only problems take extra space
            self._zip_note.setText(check.message)
            self._zip_note.setStyleSheet(f"color: {tint};")
            self._zip_note.show()
