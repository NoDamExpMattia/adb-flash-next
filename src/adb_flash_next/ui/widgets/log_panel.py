"""Basic real-time log view. The full logging service arrives in a later stage."""
from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtWidgets import QTextEdit, QWidget

from adb_flash_next.ui.theme import Colors

LEVEL_COLORS: dict[str, str] = {
    "INFO": Colors.INFO,
    "SUCCESS": Colors.SUCCESS,
    "WARNING": Colors.WARNING,
    "ERROR": Colors.ERROR,
}


class LogPanel(QTextEdit):
    """Read-only log with timestamp, coloured severity and message."""

    MAX_LINES = 5000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LogView")
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(self.MAX_LINES)

    def append_entry(self, level: str, message: str) -> None:
        """Append one entry. `level` is INFO, SUCCESS, WARNING or ERROR."""
        level = level.upper()
        color = LEVEL_COLORS.get(level, Colors.INFO)
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_message = html.escape(message).replace("\n", "<br>")
        self.append(
            f'<span style="color:{Colors.MUTED}">[{timestamp}]</span> '
            f'<span style="color:{color}"><b>{level}</b></span> '
            f'<span style="color:{Colors.TEXT}">{safe_message}</span>'
        )

    def plain_text(self) -> str:
        return self.toPlainText()
