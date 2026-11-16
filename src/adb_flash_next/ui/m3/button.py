"""Material 3 Expressive button: pill shape that morphs on press, with state layers."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from adb_flash_next.ui.m3.icons import draw_icon
from adb_flash_next.ui.m3.tokens import SCHEME, STATE
from adb_flash_next.ui.m3.util import lerp, qcolor, spring

VARIANTS = ("filled", "tonal", "outlined", "text")


class M3Button(QAbstractButton):
    """Variants: filled (red), tonal (rose), outlined, text.

    Fully rounded at rest; presses (and checked toggles) morph the corners towards a
    rounded square with a small spring, as in Material 3 Expressive.
    """

    def __init__(
        self,
        text: str = "",
        variant: str = "filled",
        icon: str | None = None,
        height: int = 40,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if variant not in VARIANTS:
            raise ValueError(f"Unknown button variant: {variant}")
        self._variant = variant
        self._icon = icon
        self._height = height
        self._hover = False
        self._morph = 0.0

        self.setText(text)
        self.setFixedHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        font = QFont(self.font())
        font.setPixelSize(14 if height < 56 else 16)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)

        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_morph)
        self.pressed.connect(self._retarget)
        self.released.connect(self._retarget)
        self.toggled.connect(self._retarget)

    # -- API ---------------------------------------------------------------------
    def set_variant(self, variant: str) -> None:
        if variant not in VARIANTS:
            raise ValueError(f"Unknown button variant: {variant}")
        self._variant = variant
        self.update()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        super().setText(text)
        self.updateGeometry()
        self.update()

    # -- geometry --------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        metrics = QFontMetricsF(self.font())
        text_width = metrics.horizontalAdvance(self.text()) if self.text() else 0.0
        icon_width = 18 if self._icon else 0
        gap = 8 if (self._icon and self.text()) else 0
        padding = 20 if self._icon else 24
        return QSize(int(text_width + icon_width + gap + padding * 2), self._height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return self.sizeHint()

    # -- animation ----------------------------------------------------------------------
    def _target(self) -> float:
        return 1.0 if (self.isDown() or (self.isCheckable() and self.isChecked())) else 0.0

    def _retarget(self, *_args) -> None:
        target = self._target()
        if abs(self._morph - target) < 0.001:
            return
        self._anim.stop()
        self._anim.setStartValue(float(self._morph))
        self._anim.setEndValue(target)
        self._anim.setDuration(260 if target > 0 else 220)
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

    # -- painting -------------------------------------------------------------------------
    def _colors(self) -> tuple[str | None, str, str | None]:
        """(background, foreground, border) for the current variant."""
        s = SCHEME
        if self._variant == "filled":
            return s.primary, s.on_primary, None
        if self._variant == "tonal":
            return s.secondary_container, s.on_secondary_container, None
        if self._variant == "outlined":
            return None, s.primary_bright, s.outline
        return None, s.primary_bright, None

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        full = rect.height() / 2
        squarish = min(full, 12 + max(0, self._height - 40) * 0.15)
        radius = max(4.0, min(full, lerp(full, squarish, self._morph)))

        background, foreground, border = self._colors()
        enabled = self.isEnabled()
        if not enabled:
            fg_color = qcolor(SCHEME.on_surface, STATE["disabled_content"])
            bg_color = qcolor(SCHEME.on_surface, STATE["disabled_container"]) if background else None
            border_color = qcolor(SCHEME.on_surface, STATE["disabled_container"]) if border else None
        else:
            fg_color = qcolor(foreground)
            bg_color = qcolor(background) if background else None
            border_color = qcolor(border) if border else None

        painter.setPen(Qt.PenStyle.NoPen)
        if bg_color is not None:
            painter.setBrush(bg_color)
            painter.drawRoundedRect(rect, radius, radius)

        # State layer (hover / keyboard focus / pressed).
        layer = 0.0
        if enabled:
            if self.isDown():
                layer = STATE["pressed"]
            elif self._hover:
                layer = STATE["hover"]
            elif self.hasFocus():
                layer = STATE["focus"]
        if layer:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(foreground, layer))
            painter.drawRoundedRect(rect, radius, radius)

        if border_color is not None:
            painter.setPen(QPen(border_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)

        # Content: optional icon + text, centred.
        metrics = QFontMetricsF(self.font())
        text = self.text()
        text_width = metrics.horizontalAdvance(text) if text else 0.0
        icon_width = 18.0 if self._icon else 0.0
        gap = 8.0 if (self._icon and text) else 0.0
        x = (self.width() - (icon_width + gap + text_width)) / 2
        if self._icon:
            icon_rect = QRectF(x, (self.height() - icon_width) / 2, icon_width, icon_width)
            draw_icon(painter, self._icon, icon_rect, fg_color, stroke=2.2)
            x += icon_width + gap
        if text:
            painter.setFont(self.font())
            painter.setPen(fg_color)
            painter.drawText(
                QRectF(x, 0, text_width + 2, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )
        painter.end()
