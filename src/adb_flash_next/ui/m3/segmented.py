"""Material 3 connected button group (single choice), drawn by us."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from adb_flash_next.ui.m3.icons import draw_icon
from adb_flash_next.ui.m3.tokens import SCHEME, STATE
from adb_flash_next.ui.m3.util import qcolor


class M3Segmented(QWidget):
    """Options are (value, label) pairs. Emits `value_changed(value)` only on user input."""

    value_changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = list(options)
        values = [v for v, _label in self._options]
        self._value = value if value in values else None
        self._hover = -1
        self.setFixedHeight(44)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._font = QFont(self.font())
        self._font.setPixelSize(14)
        self._font.setWeight(QFont.Weight.DemiBold)

    # -- API -----------------------------------------------------------------------
    def value(self) -> str | None:
        return self._value

    def set_value(self, value: str | None) -> None:
        """Select `value` without emitting a signal."""
        self._value = value
        self.update()

    # -- geometry ------------------------------------------------------------------------
    def _widths(self) -> list[float]:
        metrics = QFontMetricsF(self._font)
        return [max(104.0, metrics.horizontalAdvance(label) + 64.0) for _v, label in self._options]

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(int(sum(self._widths())), 44)

    def _segments(self) -> list[QRectF]:
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        widths = self._widths()
        scale = rect.width() / max(sum(widths), 1.0)
        segments, x = [], rect.left()
        for width in widths:
            segments.append(QRectF(x, rect.top(), width * scale, rect.height()))
            x += width * scale
        return segments

    def _index_at(self, x: float) -> int:
        for index, segment in enumerate(self._segments()):
            if segment.left() <= x <= segment.right():
                return index
        return -1

    # -- input ----------------------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        index = self._index_at(event.position().x())
        if index != self._hover:
            self._hover = index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._index_at(event.position().x())
            if index >= 0:
                self._choose(index)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        values = [v for v, _label in self._options]
        current = values.index(self._value) if self._value in values else -1
        if event.key() == Qt.Key.Key_Right and current < len(values) - 1:
            self._choose(current + 1)
        elif event.key() == Qt.Key.Key_Left and current > 0:
            self._choose(current - 1)
        else:
            super().keyPressEvent(event)

    def _choose(self, index: int) -> None:
        value = self._options[index][0]
        if value != self._value:
            self._value = value
            self.update()
            self.value_changed.emit(value)

    # -- painting ----------------------------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2
        segments = self._segments()

        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(clip)
        for index, ((value, _label), segment) in enumerate(zip(self._options, segments)):
            if value == self._value:
                painter.fillRect(segment, qcolor(SCHEME.secondary_container))
            if index == self._hover:
                painter.fillRect(segment, qcolor(SCHEME.on_surface, STATE["hover"]))
        painter.restore()

        painter.setPen(QPen(qcolor(SCHEME.outline), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)
        for segment in segments[1:]:
            painter.drawLine(QPointF(segment.left(), rect.top()), QPointF(segment.left(), rect.bottom()))

        painter.setFont(self._font)
        metrics = QFontMetricsF(self._font)
        for (value, label), segment in zip(self._options, segments):
            selected = value == self._value
            color = qcolor(SCHEME.on_secondary_container if selected else SCHEME.on_surface)
            text_width = metrics.horizontalAdvance(label)
            icon_width = 20.0 if selected else 0.0
            gap = 8.0 if selected else 0.0
            x = segment.center().x() - (icon_width + gap + text_width) / 2
            if selected:
                draw_icon(painter, "check", QRectF(x, segment.center().y() - 10, 20, 20), color, stroke=2.4)
                x += icon_width + gap
            painter.setPen(color)
            painter.drawText(
                QRectF(x, segment.top(), text_width + 2, segment.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )
        painter.end()
