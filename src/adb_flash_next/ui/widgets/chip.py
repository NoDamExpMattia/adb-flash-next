"""Status chip: a label with a pill background that is DRAWN, not styled.

Qt style sheets ignore a corner radius larger than half the widget's height, which
turns a pill into a rectangle. Painting the background ourselves always gives a pill.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel, QWidget

from adb_flash_next.ui.m3.util import qcolor
from adb_flash_next.ui.theme import Colors


class StatusChip(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = Colors.MUTED
        self.setWordWrap(True)
        self.setContentsMargins(18, 9, 18, 9)

    def set_state(self, text: str, color: str, size: int = 14) -> None:
        """Show `text` in `color` on a soft tint of the same colour."""
        self._color = color
        self.setText(text)
        self.setStyleSheet(f"color: {color}; font-weight: bold; font-size: {size}px;")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = min(rect.height() / 2, 26.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(self._color, 0.16))
        painter.drawRoundedRect(rect, radius, radius)
        painter.end()
        super().paintEvent(event)
