"""Review dialog shown before any Fastboot command runs: summary, problems, exact commands."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.core.flash_plan import ERROR, FlashPlan
from adb_flash_next.ui.m3.button import M3Button
from adb_flash_next.ui.theme import Colors
from adb_flash_next.ui.widgets.checkbox import M3Checkbox

ERASE_CONFIRM_WORD = "ERASE"


def issues_html(plan: FlashPlan) -> str:
    """Rich-text list of problems for a plan."""
    rows: list[str] = []
    for issue in plan.issues:
        color, glyph = (Colors.ERROR, "✖") if issue.level == ERROR else (Colors.WARNING, "⚠")
        rows.append(f'<span style="color:{color}">{glyph} {html.escape(issue.message)}</span>')
    if not plan.errors and plan.steps:
        rows.append(
            f'<span style="color:{Colors.SUCCESS}">✔ No blocking problems found. These checks cannot '
            "guarantee compatibility: review every command before continuing.</span>"
        )
    return "<br>".join(rows) if rows else "No checks to show yet."


def summary_html(plan: FlashPlan) -> str:
    return "<br>".join(html.escape(line) for line in plan.summary_lines())


class PlanDialog(QDialog):
    """exec() returns accepted only when the plan is not blocked and every confirmation is given."""

    def __init__(
        self,
        plan: FlashPlan,
        *,
        title: str = "Review before flashing",
        start_text: str = "Start flashing",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._plan = plan
        self.setWindowTitle(title)
        self.resize(780, 660)

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        summary = QLabel(summary_html(plan))
        summary.setTextFormat(Qt.TextFormat.RichText)
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(summary)

        issues = QLabel(issues_html(plan))
        issues.setTextFormat(Qt.TextFormat.RichText)
        issues.setWordWrap(True)
        layout.addWidget(issues)

        header = QLabel("Exact commands")
        header.setObjectName("CardTitle")
        layout.addWidget(header)
        preview = QTextEdit()
        preview.setObjectName("LogView")
        preview.setReadOnly(True)
        preview.viewport().setAutoFillBackground(False)
        preview.setMinimumHeight(140)
        preview.setPlainText("\n".join(plan.command_previews()) or "(no commands)")
        layout.addWidget(preview)

        self._ack = M3Checkbox("I have checked every command, file and slot above")
        self._ack.toggled.connect(self._update_start)
        layout.addWidget(self._ack)

        self._erase_input: QLineEdit | None = None
        if plan.has_destructive_step:
            warning = QLabel(
                f"This plan contains a destructive step (marked !!). Type {ERASE_CONFIRM_WORD} to confirm."
            )
            warning.setStyleSheet(f"color: {Colors.ERROR}; font-weight: 700;")
            warning.setWordWrap(True)
            layout.addWidget(warning)
            self._erase_input = QLineEdit()
            self._erase_input.setPlaceholderText(f"Type {ERASE_CONFIRM_WORD}")
            self._erase_input.textChanged.connect(self._update_start)
            layout.addWidget(self._erase_input)
        layout.addStretch()

        buttons = QHBoxLayout()
        copy_button = M3Button("Copy commands", "tonal", height=48)
        copy_button.setEnabled(bool(plan.command_previews()))
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText("\n".join(plan.command_previews()))
        )
        close_button = M3Button("Close", "outlined", height=48)
        close_button.clicked.connect(self.reject)
        self._start = M3Button(start_text, "filled", icon="flash", height=48)
        self._start.clicked.connect(self.accept)
        buttons.addWidget(copy_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        buttons.addWidget(self._start)
        outer.addLayout(buttons)

        self._update_start()

    def _update_start(self, *_args) -> None:
        erase_ok = True
        if self._erase_input is not None:
            erase_ok = self._erase_input.text().strip() == ERASE_CONFIRM_WORD
        self._start.setEnabled(not self._plan.blocked and self._ack.isChecked() and erase_ok)
