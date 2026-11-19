"""Round colour swatch used to pick the accent colour."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from adb_flash_next.ui.m3.icons import draw_icon
from adb_flash_next.ui.m3.tokens import SCHEME, contrast_ratio
from adb_flash_next.ui.m3.util import qcolor


class ColorSwatch(QAbstractButton):
    def __init__(self, hex_color: str, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hex_color = hex_color.upper()
        self._selected = False
        self._hover = False
        self.setFixedSize(44, 44)
        self.setToolTip(f"{name} ({self.hex_color})")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = QRectF(7, 7, 30, 30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.hex_color))
        painter.drawEllipse(circle)
        if self._selected or self._hover:
            painter.setPen(QPen(qcolor(SCHEME.on_surface if self._selected else SCHEME.outline), 3 if self._selected else 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(2.5, 2.5, 39, 39))
        if self._selected:
            mark = "#FFFFFF" if contrast_ratio("#FFFFFF", self.hex_color) >= contrast_ratio("#000000", self.hex_color) else "#000000"
            draw_icon(painter, "check", circle.adjusted(7, 7, -7, -7), QColor(mark), stroke=3.0)
        painter.end()
