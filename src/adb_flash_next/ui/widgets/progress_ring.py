"""Circular progress ring: dark track, red arc filling clockwise from 12 o'clock."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from adb_flash_next.ui.theme import Colors


class ProgressRing(QWidget):
    """Shows overall progress from 0 to 100.

    The displayed percentage is floored, never rounded up, so a value such as
    99.7 shows "99%". "100%" is only displayed when the value is exactly 100.
    """

    def __init__(self, parent: QWidget | None = None, thickness: int = 14) -> None:
        super().__init__(parent)
        self._value: float = 0.0
        self._thickness = thickness
        self.setMinimumSize(140, 140)

    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        """Set progress in the range 0..100 (values outside are clamped)."""
        clamped = max(0.0, min(100.0, float(value)))
        if clamped != self._value:
            self._value = clamped
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(200, 200)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        side = min(self.width(), self.height())
        inset = self._thickness / 2 + 2
        rect = QRectF(
            (self.width() - side) / 2 + inset,
            (self.height() - side) / 2 + inset,
            side - 2 * inset,
            side - 2 * inset,
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark track (full circle).
        track_pen = QPen(QColor(Colors.RING_TRACK), self._thickness)
        track_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        # Red progress arc. Qt angles are in 1/16 degree, 0 = 3 o'clock,
        # counter-clockwise positive. Start at 12 o'clock (90 deg) and use a
        # NEGATIVE span so the arc grows clockwise.
        if self._value > 0:
            arc_pen = QPen(QColor(Colors.ACCENT), self._thickness)
            arc_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(arc_pen)
            span = -int(round(self._value / 100.0 * 360 * 16))
            painter.drawArc(rect, 90 * 16, span)

        # Percentage text in the centre (floored on purpose).
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(max(14, int(side * 0.22)))
        painter.setFont(font)
        painter.setPen(QColor(Colors.TEXT))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}%")
        painter.end()
