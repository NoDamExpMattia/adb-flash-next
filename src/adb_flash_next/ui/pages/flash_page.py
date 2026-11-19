"""Flash page: extra options (erase userdata, vbmeta) and a live review of the plan."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.core.flash_plan import ERROR, FlashPlan, PartitionSelection, build_plan
from adb_flash_next.core.models import DeviceInfo
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.toggle_button import ToggleButton


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 14)
    layout.setSpacing(8)
    header = QLabel(title)
    header.setObjectName("CardTitle")
    header.setWordWrap(True)
    layout.addWidget(header)
    return card, layout


def _option_row(text: str, danger: bool = False) -> tuple[QHBoxLayout, ToggleButton]:
    """A label with a visible On/Off button on the right."""
    row = QHBoxLayout()
    label = QLabel(text)
    label.setWordWrap(True)
    if danger:
        label.setStyleSheet(f"color: {Colors.ERROR}; font-weight: 700;")
    toggle = ToggleButton("On", "Off")
    row.addWidget(label, 1)
    row.addWidget(toggle)
    return row, toggle


def issues_html(plan: FlashPlan) -> str:
    """Rich-text list of problems for a plan (shared with the review dialog)."""
    rows: list[str] = []
    for issue in plan.issues:
        color, glyph = (Colors.ERROR, "✖") if issue.level == ERROR else (Colors.WARNING, "⚠")
        rows.append(f'<span style="color:{color}">{glyph} {html.escape(issue.message)}</span>')
    if not plan.errors and plan.steps:
        rows.append(
            f'<span style="color:{Colors.SUCCESS}">✔ No blocking problems found. These checks cannot '
            "guarantee compatibility: review every command before writing.</span>"
        )
    return "<br>".join(rows) if rows else "No checks to show yet."


def summary_html(plan: FlashPlan) -> str:
    return "<br>".join(html.escape(line) for line in plan.summary_lines())


class FlashPage(QWidget):
    """Rebuilds the plan whenever the device, the images or an option changes."""

    plan_changed = Signal(object)  # FlashPlan

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._device: DeviceInfo | None = None
        self._selections: list[PartitionSelection] = []
        self._plan: FlashPlan | None = None

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
        root.setSpacing(12)

        title = QLabel("Flash")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        info = QLabel(
            "Choose images and slots on the Images page, then click 'Write partitions' there. "
            "This page holds the extra options and shows exactly what would run."
        )
        info.setObjectName("Muted")
        info.setWordWrap(True)
        root.addWidget(info)

        options, options_layout = _card("Extra options")
        vbmeta_row, self._vbmeta = _option_row(
            "Disable verity and verification when flashing vbmeta (only if your ROM says so)"
        )
        options_layout.addLayout(vbmeta_row)
        erase_row, self._erase = _option_row(
            "Erase userdata after flashing (permanently deletes ALL data on the device)", danger=True
        )
        options_layout.addLayout(erase_row)
        root.addWidget(options)

        summary_card, summary_layout = _card("Plan summary")
        self._summary = QLabel()
        self._summary.setTextFormat(Qt.TextFormat.RichText)
        self._summary.setWordWrap(True)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary_layout.addWidget(self._summary)
        root.addWidget(summary_card)

        issues_card, issues_layout = _card("Checks")
        self._issues = QLabel()
        self._issues.setTextFormat(Qt.TextFormat.RichText)
        self._issues.setWordWrap(True)
        issues_layout.addWidget(self._issues)
        root.addWidget(issues_card)

        preview_card, preview_layout = _card("Command preview (dry run)")
        self._preview = QTextEdit()
        self._preview.setObjectName("LogView")
        self._preview.setReadOnly(True)
        self._preview.viewport().setAutoFillBackground(False)
        self._preview.setMinimumHeight(120)
        preview_layout.addWidget(self._preview)
        buttons = QHBoxLayout()
        self._copy_button = M3Button("Copy commands", "tonal", height=44)
        self._copy_button.clicked.connect(self._copy)
        buttons.addWidget(self._copy_button)
        buttons.addStretch()
        preview_layout.addLayout(buttons)
        root.addWidget(preview_card)
        root.addStretch()

        self._vbmeta.toggled.connect(self._rebuild)
        self._erase.toggled.connect(self._rebuild)
        self._rebuild()

    # ------------------------------------------------------------- public API
    def set_device(self, device: DeviceInfo | None) -> None:
        self._device = device
        self._rebuild()

    def set_selections(self, selections: list[PartitionSelection]) -> None:
        self._selections = list(selections)
        self._rebuild()

    def current_plan(self) -> FlashPlan | None:
        return self._plan

    # ---------------------------------------------------------------- internals
    def _rebuild(self, *_args) -> None:
        plan = build_plan(
            self._device,
            self._selections,
            erase_userdata=self._erase.isChecked(),
            vbmeta_disable_checks=self._vbmeta.isChecked(),
        )
        self._plan = plan
        self._summary.setText(summary_html(plan))
        self._issues.setText(issues_html(plan))

        commands = plan.command_previews()
        lines = ["# PREVIEW ONLY - nothing is executed from this page."]
        if plan.blocked:
            lines.append("# PLAN IS BLOCKED: fix the problems listed under 'Checks' first.")
        lines.extend(commands)
        self._preview.setPlainText("\n".join(lines))
        self._copy_button.setEnabled(bool(commands))
        self.plan_changed.emit(plan)

    def _copy(self) -> None:
        if self._plan is not None:
            QApplication.clipboard().setText("\n".join(self._plan.command_previews()))
