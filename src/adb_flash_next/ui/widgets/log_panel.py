<<<<<<< HEAD
"""Real-time log view. Entries are kept so they can be re-coloured when the theme changes."""
=======
"""Basic real-time log view. The full logging service arrives in a later stage."""
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtWidgets import QTextEdit, QWidget

from adb_flash_next.ui.theme import Colors

<<<<<<< HEAD

def _level_color(level: str) -> str:
    return {
        "INFO": Colors.INFO,
        "SUCCESS": Colors.SUCCESS,
        "WARNING": Colors.WARNING,
        "ERROR": Colors.ERROR,
    }.get(level, Colors.INFO)
=======
LEVEL_COLORS: dict[str, str] = {
    "INFO": Colors.INFO,
    "SUCCESS": Colors.SUCCESS,
    "WARNING": Colors.WARNING,
    "ERROR": Colors.ERROR,
}
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b


class LogPanel(QTextEdit):
    """Read-only log with timestamp, coloured severity and message."""

    MAX_LINES = 5000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LogView")
        self.setReadOnly(True)
        self.viewport().setAutoFillBackground(False)
        self.document().setMaximumBlockCount(self.MAX_LINES)
<<<<<<< HEAD
        self._entries: list[tuple[str, str, str]] = []

    def append_entry(self, level: str, message: str) -> None:
        """Append one entry. `level` is INFO, SUCCESS, WARNING or ERROR."""
        entry = (datetime.now().strftime("%H:%M:%S"), level.upper(), message)
        self._entries.append(entry)
        if len(self._entries) > self.MAX_LINES:
            del self._entries[: len(self._entries) - self.MAX_LINES]
        self._append_html(*entry)

    def _append_html(self, timestamp: str, level: str, message: str) -> None:
        safe_message = html.escape(message).replace("\n", "<br>")
        self.append(
            f'<span style="color:{Colors.MUTED}">[{timestamp}]</span> '
            f'<span style="color:{_level_color(level)}"><b>{level}</b></span> '
            f'<span style="color:{Colors.TEXT}">{safe_message}</span>'
        )

    def rebuild(self) -> None:
        """Redraw every entry with the current theme colours."""
        self.clear()
        for entry in self._entries:
            self._append_html(*entry)

=======

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

>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    def plain_text(self) -> str:
        return self.toPlainText()
