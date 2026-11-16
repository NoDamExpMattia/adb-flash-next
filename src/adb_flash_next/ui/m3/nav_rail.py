"""Material 3 Expressive navigation rail: collapsible, with an animated pill indicator."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from adb_flash_next.config.constants import APP_NAME, APP_VERSION
from adb_flash_next.ui.m3.icons import draw_icon
from adb_flash_next.ui.m3.tokens import SCHEME, STATE
from adb_flash_next.ui.m3.util import qcolor, spring
from adb_flash_next.ui.widgets.logo import LogoWidget

EXPANDED_WIDTH = 232
COLLAPSED_WIDTH = 80
_ITEM_HEIGHT = 64


class _RailItem(QAbstractButton):
    """One destination. Draws itself as a row (expanded) or icon + label (collapsed)."""

    def __init__(self, label: str, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon = icon
        self._hover = False
        self._sel = 0.0
        self.setText(label)
        self.setCheckable(True)
        self.setAutoExclusive(True)  # exactly one item stays selected
        self.setFixedHeight(_ITEM_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._on_toggled)

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(COLLAPSED_WIDTH, _ITEM_HEIGHT)

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(float(self._sel))
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.setDuration(340 if checked else 180)
        self._anim.setEasingCurve(spring(1.3) if checked else QEasingCurve(QEasingCurve.Type.OutCubic))
        self._anim.start()

    def _on_anim(self, value) -> None:
        self._sel = float(value)
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
        width = self.width()
        expanded = width >= 150
        selected = self.isChecked()

        if expanded:
            slot = QRectF(8, 4, width - 16, 56)
        else:
            slot = QRectF((width - 56) / 2, 6, 56, 32)

        sel = max(0.0, min(1.0, self._sel))
        if sel > 0.01:
            # The pill grows in place from the centre.
            scale = 0.35 + 0.65 * sel
            pill = QRectF(0, 0, slot.width() * scale, slot.height())
            pill.moveCenter(slot.center())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(SCHEME.secondary_container, min(1.0, sel * 1.3)))
            painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)

        if self._hover and sel < 0.5:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(SCHEME.on_surface, STATE["hover"] * (1.0 - sel * 2)))
            painter.drawRoundedRect(slot, slot.height() / 2, slot.height() / 2)

        icon_color = qcolor(SCHEME.on_secondary_container if selected else SCHEME.on_surface_variant)
        label_color = qcolor(SCHEME.on_surface if selected else SCHEME.on_surface_variant)
        font = QFont(self.font())
        font.setWeight(QFont.Weight.Bold if selected else QFont.Weight.Medium)

        if expanded:
            icon_rect = QRectF(slot.left() + 20, slot.center().y() - 12, 24, 24)
            draw_icon(painter, self._icon, icon_rect, icon_color, stroke=2.4 if selected else 2.0)
            font.setPixelSize(15)
            painter.setFont(font)
            painter.setPen(label_color)
            painter.drawText(
                QRectF(slot.left() + 56, slot.top(), slot.width() - 64, slot.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self.text(),
            )
        else:
            icon_rect = QRectF(slot.center().x() - 12, slot.center().y() - 12, 24, 24)
            draw_icon(painter, self._icon, icon_rect, icon_color, stroke=2.4 if selected else 2.0)
            font.setPixelSize(11)
            painter.setFont(font)
            painter.setPen(label_color)
            painter.drawText(
                QRectF(0, 42, width, 18),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self.text(),
            )
        painter.end()


class _MenuButton(QAbstractButton):
    """Round icon button that collapses / expands the rail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hover = False
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip("Collapse or expand the menu")

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
        layer = STATE["pressed"] if self.isDown() else (STATE["hover"] if self._hover else 0.0)
        if layer:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(SCHEME.on_surface, layer))
            painter.drawEllipse(QRectF(self.rect()).adjusted(2, 2, -2, -2))
        draw_icon(painter, "menu", QRectF(12, 12, 24, 24), qcolor(SCHEME.on_surface_variant), stroke=2.2)
        painter.end()


class NavigationRail(QFrame):
    """Left navigation. `entries` is a list of (label, icon name)."""

    current_changed = Signal(int)

    def __init__(self, entries: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Rail")
        self._expanded = True
        self._items: list[_RailItem] = []
        self.setFixedWidth(EXPANDED_WIDTH)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 12)
        root.setSpacing(0)

        menu_row = QHBoxLayout()
        menu_row.setContentsMargins(16, 0, 0, 0)
        self._menu = _MenuButton()
        self._menu.clicked.connect(lambda: self.set_expanded(not self._expanded))
        menu_row.addWidget(self._menu)
        menu_row.addStretch()
        root.addLayout(menu_row)
        root.addSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(20, 0, 8, 0)
        brand_row.setSpacing(12)
        brand_row.addWidget(LogoWidget(40))
        self._brand = QLabel("ADB Flash\nNext")
        self._brand.setObjectName("BrandName")
        brand_row.addWidget(self._brand)
        brand_row.addStretch()
        root.addLayout(brand_row)
        root.addSpacing(18)

        for index, (label, icon) in enumerate(entries):
            item = _RailItem(label, icon)
            item.clicked.connect(lambda _checked=False, i=index: self.current_changed.emit(i))
            self._items.append(item)
            root.addWidget(item)

        root.addStretch()
        self._version = QLabel(f"v{APP_VERSION}")
        self._version.setObjectName("Muted")
        self._version.setContentsMargins(24, 0, 0, 0)
        root.addWidget(self._version)

        self._width_anim = QVariantAnimation(self)
        self._width_anim.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))
        self._width_anim.finished.connect(self._after_width_animation)

    # -- API ---------------------------------------------------------------------
    def set_current(self, index: int) -> None:
        """Select a destination programmatically and announce it."""
        if 0 <= index < len(self._items):
            self._items[index].setChecked(True)
            self.current_changed.emit(index)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        self._expanded = expanded
        target = EXPANDED_WIDTH if expanded else COLLAPSED_WIDTH
        if expanded:
            self._brand.setVisible(True)
            self._version.setVisible(True)
        if not animate:
            self.setFixedWidth(target)
            self._after_width_animation()
            return
        self._width_anim.stop()
        self._width_anim.setStartValue(self.width())
        self._width_anim.setEndValue(target)
        self._width_anim.setDuration(260)
        self._width_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        self._width_anim.start()

    def _after_width_animation(self) -> None:
        if not self._expanded:
            self._brand.setVisible(False)
            self._version.setVisible(False)
