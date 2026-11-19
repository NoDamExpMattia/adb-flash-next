"""Circular progress ring: rounded red arc filling clockwise from 12 o'clock.

Material 3 Expressive style: thick rounded stroke, a small gap between the active arc
and the track, and an optional wavy active arc for operations that are running.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from adb_flash_next.ui.theme import Colors


class ProgressRing(QWidget):
    """Shows overall progress from 0 to 100.

    The displayed percentage is floored, never rounded up, so 99.7 shows "99%".
    "100%" is only displayed when the value is exactly 100.
    """

    _WAVES = 10

    def __init__(self, parent: QWidget | None = None, thickness: int = 14) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._thickness = thickness
        self._wavy = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.setMinimumSize(150, 150)

    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        """Set progress in the range 0..100 (values outside are clamped)."""
        clamped = max(0.0, min(100.0, float(value)))
        if clamped != self._value:
            self._value = clamped
            self.update()

    def set_wavy(self, wavy: bool) -> None:
        """Animate a wave along the active arc (use while an operation is running)."""
        self._wavy = wavy
        if wavy:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.22) % (2 * math.pi)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(210, 210)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        side = min(self.width(), self.height())
        inset = self._thickness + 6
        rect = QRectF(
            (self.width() - side) / 2 + inset,
            (self.height() - side) / 2 + inset,
            side - 2 * inset,
            side - 2 * inset,
        )
        radius = rect.width() / 2
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cap_deg = math.degrees((self._thickness / 2) / radius)
        gap_deg = cap_deg + 4.0
        # Below 100% a small notch always stays open, so 99% can never look like a finished ring.
        active_deg = 360.0 if self._value >= 100 else min(self._value * 3.6, 360.0 - 2 * gap_deg)

        track_pen = QPen(QColor(Colors.RING_TRACK), self._thickness)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        active_pen = QPen(QColor(Colors.ACCENT), self._thickness)
        active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        active_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        # Track: whole circle when idle, otherwise only the part after the active arc (with a gap).
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._value <= 0:
            painter.setPen(track_pen)
            painter.drawEllipse(rect)
        elif self._value < 100:
            span = 360 - active_deg - 2 * gap_deg
            if span > 0:
                painter.setPen(track_pen)
                painter.drawArc(rect, int(round((90 - active_deg - gap_deg) * 16)), int(round(-span * 16)))

        # Active arc, clockwise from 12 o'clock (Qt angles are counter-clockwise, so use a negative span).
        if self._value > 0:
            painter.setPen(active_pen)
            if self._wavy and self._value < 100:
                painter.drawPath(self._wavy_path(rect, radius, active_deg))
            elif self._value >= 100:
                painter.drawEllipse(rect)
            else:
                painter.drawArc(rect, 90 * 16, int(round(-active_deg * 16)))

        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(max(16, int(side * 0.22)))
        painter.setFont(font)
        painter.setPen(QColor(Colors.TEXT))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}%")
        painter.end()

    def _wavy_path(self, rect: QRectF, radius: float, active_deg: float) -> QPainterPath:
        amplitude = self._thickness * 0.28
        center = rect.center()
        path = QPainterPath()
        steps = max(2, int(active_deg / 1.5))
        for i in range(steps + 1):
            travelled = active_deg * i / steps
            angle = math.radians(90 - travelled)
            wobble = amplitude * math.sin(math.radians(travelled) * self._WAVES + self._phase)
            r = radius + wobble
            point = QPointF(center.x() + r * math.cos(angle), center.y() - r * math.sin(angle))
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        return path
