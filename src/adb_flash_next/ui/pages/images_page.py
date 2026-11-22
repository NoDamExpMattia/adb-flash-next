"""Images page: six fixed partition rows (tick, file, slot) and a red 'Write partitions' button."""
from __future__ import annotations

import dataclasses
import html
import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.config.constants import SUPPORTED_PARTITIONS
from adb_flash_next.core.file_hash import sha256_of_file
from adb_flash_next.core.flash_plan import FlashPlan, PartitionSelection
from adb_flash_next.core.image_validator import LEVEL_ERROR, LEVEL_OK, format_size, validate_image
from adb_flash_next.core.models import DeviceInfo, PartitionScheme
from adb_flash_next.core.slot_resolver import SlotChoice
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.toggle_button import ToggleButton
from adb_flash_next.workers.base_worker import FunctionWorker


class PartitionRow(QFrame):
    """One partition: include checkbox, slot selector, file chooser and validation line."""

    changed = Signal()

    def __init__(self, partition: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.selection = PartitionSelection(partition=partition)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # --- top line: tick + slot ---
        top = QHBoxLayout()
        name = QLabel(partition)
        name.setStyleSheet("font-weight: 800; font-size: 13pt;")
        top.addWidget(name)
        top.addStretch()
        self._slot_box = QWidget()
        slot_layout = QHBoxLayout(self._slot_box)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.addWidget(QLabel("Slot:"))
        self._slot = QComboBox()
        self._slot.setMinimumWidth(190)
        self._slot.currentIndexChanged.connect(self._on_slot)
        slot_layout.addWidget(self._slot)
        top.addWidget(self._slot_box)
        # Big on/off button on the right: click to skip this partition.
        self._enabled = ToggleButton("✔ Included", "Skipped", checked=True)
        self._enabled.setToolTip("Click to include or skip this partition")
        self._enabled.toggled.connect(self._on_enabled)
        top.addWidget(self._enabled)
        layout.addLayout(top)

        # --- body: file + validation ---
        self._body = QWidget()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        file_row = QHBoxLayout()
        self._file = QLabel()
        self._file.setTextFormat(Qt.TextFormat.RichText)  # rich text can break long paths anywhere
        self._file.setWordWrap(True)
        self._choose = M3Button("Choose file...", "tonal", height=40)
        self._clear = M3Button("Clear", "text", height=40)
        self._hash_button = M3Button("SHA-256", "text", height=40)
        self._hash_button.setMinimumWidth(132)
        self._hash_button.setToolTip("Show the SHA-256 checksum of this file")
        self._hash_button.clicked.connect(self._on_hash_clicked)
        file_row.addWidget(self._file, 1)
        file_row.addWidget(self._choose)
        file_row.addWidget(self._hash_button)
        file_row.addWidget(self._clear)
        body.addLayout(file_row)
        self._validation = QLabel()
        self._validation.setWordWrap(True)
        body.addWidget(self._validation)

        # SHA-256 result (hidden until the button is used)
        self._hash_value: str | None = None
        self._hash_error: str | None = None
        self._hash_busy = False
        self._hash_job = 0
        self._hash_cancel = threading.Event()
        self._hash_workers: list[FunctionWorker] = []
        hash_row = QHBoxLayout()
        self._hash_label = QLabel()
        self._hash_label.setTextFormat(Qt.TextFormat.RichText)  # rich text can wrap the long hash anywhere
        self._hash_label.setWordWrap(True)
        self._hash_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._hash_copy = M3Button("Copy", "text", height=36)
        self._hash_copy.clicked.connect(self._copy_hash)
        hash_row.addWidget(self._hash_label, 1)
        hash_row.addWidget(self._hash_copy)
        body.addLayout(hash_row)
        layout.addWidget(self._body)

        self.configure_slot(None)
        self.refresh()

    # -- signals to the page ----------------------------------------------------
    def connect_buttons(self, choose_callback, clear_callback) -> None:
        self._choose.clicked.connect(lambda: choose_callback(self))
        self._clear.clicked.connect(lambda: clear_callback(self))

    # -- user actions -------------------------------------------------------------
    def _on_enabled(self, checked: bool) -> None:
        self.selection.enabled = checked
        self._slot_box.setEnabled(checked)
        self._body.setEnabled(checked)
        self.changed.emit()

    def _on_slot(self, _index: int) -> None:
        value = self._slot.currentData()
        self.selection.slot = SlotChoice(value) if value else None
        self.changed.emit()

    def set_path(self, path: Path | None) -> None:
        self._cancel_hash()  # a hash of the previous file must never be shown for the new one
        self.selection.path = path
        self.refresh()
        self.changed.emit()

    # -- SHA-256 ---------------------------------------------------------------------
    def _cancel_hash(self) -> None:
        self._hash_cancel.set()
        self._hash_job += 1
        self._hash_busy = False
        self._hash_value = None
        self._hash_error = None

    def _on_hash_clicked(self) -> None:
        path = self.selection.path
        if path is None or self._hash_busy:
            return
        self._hash_job += 1
        job = self._hash_job
        self._hash_busy = True
        self._hash_value = None
        self._hash_error = None
        self._hash_cancel = threading.Event()
        cancel = self._hash_cancel

        def work():
            try:
                return (job, str(path), sha256_of_file(path, cancel), None)
            except InterruptedError:
                return (job, str(path), None, "Cancelled.")
            except OSError as exc:
                return (job, str(path), None, f"Could not read the file ({exc.strerror or exc}).")

        worker = FunctionWorker(work)
        worker.succeeded.connect(self._on_hash_result)
        worker.failed.connect(self._on_hash_failed)
        worker.finished.connect(self._prune_workers)
        self._hash_workers.append(worker)
        self._update_hash_view()
        worker.start()

    def _on_hash_result(self, result) -> None:
        job, path, digest, error = result
        if job != self._hash_job:
            return  # an older request: ignore
        self._hash_busy = False
        current = self.selection.path
        if current is not None and str(current) == path:
            self._hash_value = digest
            self._hash_error = error
        self._update_hash_view()

    def _on_hash_failed(self, message: str) -> None:
        self._hash_busy = False
        self._hash_error = f"Unexpected error: {message}"
        self._update_hash_view()

    def _prune_workers(self) -> None:
        self._hash_workers = [w for w in self._hash_workers if w.isRunning()]

    def _copy_hash(self) -> None:
        if self._hash_value:
            QApplication.clipboard().setText(self._hash_value)

    def shutdown(self) -> None:
        """Stop any running hash and wait for its thread (called when the app closes)."""
        self._hash_cancel.set()
        for worker in list(self._hash_workers):
            worker.wait(5000)

    def _update_hash_view(self) -> None:
        has_file = self.selection.path is not None
        self._hash_button.setEnabled(has_file and not self._hash_busy)
        self._hash_button.setText("Calculating..." if self._hash_busy else "SHA-256")
        mono = "font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px;"
        self._hash_copy.setVisible(False)
        if self._hash_busy:
            self._hash_label.setText("Calculating SHA-256...")
            self._hash_label.setStyleSheet(f"color: {Colors.MUTED};")
            self._hash_label.setVisible(True)
        elif self._hash_value:
            self._hash_label.setText(f"<b>SHA-256</b><br>{html.escape(self._hash_value)}")
            self._hash_label.setStyleSheet(f"color: {Colors.TEXT}; {mono}")
            self._hash_label.setVisible(True)
            self._hash_copy.setVisible(True)
        elif self._hash_error:
            self._hash_label.setText(f"✖ {html.escape(self._hash_error)}")
            self._hash_label.setStyleSheet(f"color: {Colors.ERROR};")
            self._hash_label.setVisible(True)
        else:
            self._hash_label.setText("")
            self._hash_label.setVisible(False)

    # -- configuration from the selected device ---------------------------------------
    def configure_slot(self, device: DeviceInfo | None) -> None:
        """Rebuild the slot selector for the device's partition scheme."""
        self._slot.blockSignals(True)
        self._slot.clear()
        self.selection.slot = None
        if device is None:
            self._slot.addItem("No device selected", None)
            self._slot.setEnabled(False)
        elif device.scheme is PartitionScheme.AB:
            self._slot.addItem("Select slot...", None)
            for choice in SlotChoice:
                self._slot.addItem(choice.label, choice.value)
            self._slot.setEnabled(True)
            if device.active_slot in ("a", "b"):  # default: the active slot
                self._slot.setCurrentIndex(max(self._slot.findData(device.active_slot), 0))
                self.selection.slot = SlotChoice(device.active_slot)
        elif device.scheme is PartitionScheme.A_ONLY:
            self._slot.addItem("Not applicable (A-only)", None)
            self._slot.setEnabled(False)
        else:
            self._slot.addItem("Unknown partition scheme", None)
            self._slot.setEnabled(False)
        self._slot.blockSignals(False)

    # -- display --------------------------------------------------------------------------
    def refresh(self) -> None:
        path = self.selection.path
        if path is None:
            self._file.setText("No file selected")
            self._file.setObjectName("Muted")
            self._file.setStyleSheet(f"color: {Colors.MUTED};")
            self._validation.setText("Choose an image file, or untick this partition if you do not need it.")
            self._validation.setStyleSheet(f"color: {Colors.MUTED};")
            self._clear.setEnabled(False)
            self._update_hash_view()
            return
        result = validate_image(path, self.selection.partition)
        size = format_size(result.info.size) if result.info.size is not None else "size unknown"
        self._file.setText(f"<b>{html.escape(path.name)}</b>  ({html.escape(size)})<br>{html.escape(str(path.parent))}")
        self._file.setStyleSheet(f"color: {Colors.TEXT};")
        self._clear.setEnabled(True)
        if result.level == LEVEL_OK:
            glyph, color = "✔", Colors.SUCCESS
        elif result.level == LEVEL_ERROR:
            glyph, color = "✖", Colors.ERROR
        else:
            glyph, color = "⚠", Colors.WARNING
        self._validation.setText(f"{glyph} {result.message}")
        self._validation.setStyleSheet(f"color: {color};")
        self._update_hash_view()


class ImagesPage(QWidget):
    """Emits `selections_changed` on every change and `flash_requested` for the red button."""

    selections_changed = Signal(object)  # list[PartitionSelection] (copies)
    flash_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_dir = str(Path.home())
        self._device_signature: tuple | None = None
        self._last_plan: FlashPlan | None = None
        self._rows: list[PartitionRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        title = QLabel("Images")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        intro = QLabel(
            "Untick the partitions you do not need, choose an image file for each one that is ticked, "
            "and pick the slot (A/B devices only). 'Both slots' writes the A and B partitions as two "
            "separate commands. File names are never used to decide where an image goes, and the header "
            "checks cannot prove an image fits your device."
        )
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        rows_layout = QVBoxLayout(holder)
        rows_layout.setContentsMargins(0, 0, 8, 0)
        rows_layout.setSpacing(10)
        for partition in SUPPORTED_PARTITIONS:
            row = PartitionRow(partition)
            row.connect_buttons(self._on_choose, self._on_clear)
            row.changed.connect(self._emit)
            self._rows.append(row)
            rows_layout.addWidget(row)
        rows_layout.addStretch()
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        self._status = QLabel()
        self._status.setWordWrap(True)
        bottom.addWidget(self._status, 1)
        self._stop = M3Button("Stop after current step", "outlined", height=52)
        self._stop.clicked.connect(self.stop_requested.emit)
        self._stop.setVisible(False)
        bottom.addWidget(self._stop)
        self._write = M3Button("Flash partitions", "filled", icon="flash", height=52)
        self._write.setMinimumWidth(230)
        self._write.clicked.connect(self.flash_requested.emit)
        bottom.addWidget(self._write)
        root.addLayout(bottom)

        self.set_plan_status(None)
        self._emit()

    # ------------------------------------------------------------------ public API
    def set_device(self, device: DeviceInfo | None) -> None:
        """Adapt the slot selectors to the device. Choices are kept while the device is unchanged."""
        signature = (
            None if device is None else (device.key, device.scheme, device.active_slot)
        )
        if signature == self._device_signature:
            return
        self._device_signature = signature
        for row in self._rows:
            row.configure_slot(device)
        self._emit()

    def set_busy(self, busy: bool, can_stop: bool = False) -> None:
        """Disable flashing while an operation runs; optionally offer 'stop after current step'."""
        self._write.setEnabled(not busy)
        self._stop.setVisible(busy and can_stop)

    def shutdown(self) -> None:
        """Stop background hashing before the app closes."""
        for row in self._rows:
            row.shutdown()

    def apply_theme(self) -> None:
        """Re-render colours that were baked into labels after a theme change."""
        for row in self._rows:
            row.refresh()
        self.set_plan_status(self._last_plan)

    def publish(self) -> None:
        """Send the current selections to listeners (used once after the window is wired up)."""
        self._emit()

    def set_plan_status(self, plan: FlashPlan | None) -> None:
        self._last_plan = plan
        if plan is None:
            self._status.setText("")
            return
        if plan.blocked:
            first = plan.errors[0].message if plan.errors else "Nothing to write yet."
            extra = f" (+{len(plan.errors) - 1} more)" if len(plan.errors) > 1 else ""
            self._status.setText(f"✖ {first}{extra}")
            self._status.setStyleSheet(f"color: {Colors.ERROR};")
        else:
            self._status.setText("✔ Plan ready for review. Click 'Flash partitions' to see every command first.")
            self._status.setStyleSheet(f"color: {Colors.SUCCESS};")

    # ---------------------------------------------------------------------- actions
    def _on_choose(self, row: PartitionRow) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            f"Select the image for {row.selection.partition}",
            self._last_dir,
            "Android images (*.img);;All files (*)",
        )
        if path:
            self._last_dir = str(Path(path).parent)
            row.set_path(Path(path))

    def _on_clear(self, row: PartitionRow) -> None:
        row.set_path(None)

    def _emit(self) -> None:
        self.selections_changed.emit([dataclasses.replace(r.selection) for r in self._rows])
