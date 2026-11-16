"""Large expressive action tile (icon + title + description) used on the Reboot page."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QFont, QFontMetricsF, QLinearGradient, QPainter
from PySide6.QtWidgets import QAbstractButton, QWidget

from adb_flash_next.ui.m3.icons import draw_icon
from adb_flash_next.ui.m3.tokens import SCHEME, STATE
from adb_flash_next.ui.m3.util import lerp, qcolor, spring


class ActionTile(QAbstractButton):
    """Red gradient tile whose corners squeeze with a small spring when pressed."""

    def __init__(self, title: str, subtitle: str, icon: str = "reboot", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon = icon
        self._hover = False
        self._morph = 0.0
        self.setMinimumHeight(84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_morph)
        self.pressed.connect(self._retarget)
        self.released.connect(self._retarget)

    def set_usable(self, usable: bool) -> None:
        """Enable or disable the tile (disabled tiles turn into a quiet grey surface)."""
        self.setEnabled(usable)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(260, 84)

    def _retarget(self, *_args) -> None:
        target = 1.0 if self.isDown() else 0.0
        if abs(self._morph - target) < 0.001:
            return
        self._anim.stop()
        self._anim.setStartValue(float(self._morph))
        self._anim.setEndValue(target)
        self._anim.setDuration(240 if target > 0 else 220)
        self._anim.setEasingCurve(spring(1.5) if target > 0 else QEasingCurve(QEasingCurve.Type.OutCubic))
        self._anim.start()

    def _on_morph(self, value) -> None:
        self._morph = float(value)
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
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = max(8.0, lerp(28.0, 14.0, self._morph))
        enabled = self.isEnabled()

        painter.setPen(Qt.PenStyle.NoPen)
        if enabled:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, qcolor(SCHEME.primary))
            gradient.setColorAt(1.0, qcolor(SCHEME.primary_dark))
            painter.setBrush(gradient)
        else:
            painter.setBrush(qcolor(SCHEME.surface_container_high))
        painter.drawRoundedRect(rect, radius, radius)

        if enabled and (self.isDown() or self._hover or self.hasFocus()):
            layer = STATE["pressed"] if self.isDown() else (STATE["hover"] if self._hover else STATE["focus"])
            painter.setBrush(qcolor("#FFFFFF", layer))
            painter.drawRoundedRect(rect, radius, radius)

        title_color = qcolor("#FFFFFF") if enabled else qcolor(SCHEME.on_surface, STATE["disabled_content"])
        sub_color = qcolor("#FFD9DB", 0.9) if enabled else qcolor(SCHEME.on_surface, 0.30)

        # Icon in a soft circle on the left.
        circle = QRectF(rect.left() + 18, rect.center().y() - 22, 44, 44)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor("#FFFFFF", 0.18) if enabled else qcolor(SCHEME.on_surface, 0.08))
        painter.drawEllipse(circle)
        draw_icon(painter, self._icon, circle.adjusted(10, 10, -10, -10), title_color, stroke=2.2)

        # Title and description.
        text_left = circle.right() + 16
        text_width = rect.right() - text_left - 16
        title_font = QFont(self.font())
        title_font.setPixelSize(16)
        title_font.setWeight(QFont.Weight.Bold)
        sub_font = QFont(self.font())
        sub_font.setPixelSize(12)
        title_metrics = QFontMetricsF(title_font)
        sub_metrics = QFontMetricsF(sub_font)
        painter.setFont(title_font)
        painter.setPen(title_color)
        painter.drawText(
            QRectF(text_left, rect.center().y() - 24, text_width, 24),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            title_metrics.elidedText(self._title, Qt.TextElideMode.ElideRight, text_width),
        )
        painter.setFont(sub_font)
        painter.setPen(sub_color)
        painter.drawText(
            QRectF(text_left, rect.center().y(), text_width, 24),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            sub_metrics.elidedText(self._subtitle, Qt.TextElideMode.ElideRight, text_width),
        )
        painter.end()
