"""Short confetti animation drawn over a page (shown when everything finished and Android booted)."""
from __future__ import annotations

import random

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from adb_flash_next.core.confetti_physics import Particle, make_particles, step_particles

_FRAME_MS = 16
_FADE_MS = 700


class ConfettiOverlay(QWidget):
    """Transparent overlay that never takes mouse input. Call start() to play it once."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._particles: list[Particle] = []
        self._colors: list[str] = ["#FFFFFF"]
        self._elapsed = 0
        self._duration = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self, colors: list[str], count: int = 140, duration_ms: int = 3000) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(parent.rect())
        self._colors = list(colors) or ["#FFFFFF"]
        self._particles = make_particles(float(self.width()), float(self.height()), count, len(self._colors), random.Random())
        self._elapsed = 0
        self._duration = duration_ms
        self.show()
        self.raise_()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._particles.clear()
        self.hide()

    def _tick(self) -> None:
        step_particles(self._particles, _FRAME_MS / 1000.0)
        self._elapsed += _FRAME_MS
        if self._elapsed >= self._duration:
            self.stop()
            return
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        remaining = self._duration - self._elapsed
        alpha = 1.0 if remaining > _FADE_MS else max(0.0, remaining / _FADE_MS)
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self._particles:
            if p.y > self.height() + 20:
                continue
            color = QColor(self._colors[p.color_index % len(self._colors)])
            color.setAlphaF(alpha)
            painter.setBrush(color)
            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rotation)
            painter.drawRect(QRectF(-p.size / 2, -p.size / 4, p.size, p.size / 2))
            painter.restore()
        painter.end()
