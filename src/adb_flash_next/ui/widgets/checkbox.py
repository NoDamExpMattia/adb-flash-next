"""Material 3 checkbox with a wrapping label (drawn by us, so it is always visible)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from adb_flash_next.ui.m3.icons import draw_icon
from adb_flash_next.ui.m3.tokens import SCHEME, STATE
from adb_flash_next.ui.m3.util import qcolor


class _Box(QWidget):
    def __init__(self, owner: "M3Checkbox") -> None:
        super().__init__(owner)
        self._owner = owner
        self.setFixedSize(40, 40)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._owner._hover or self._owner.hasFocus():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(SCHEME.on_surface, STATE["hover"]))
            painter.drawEllipse(QRectF(0, 0, 40, 40))
        box = QRectF(10, 10, 20, 20)
        if self._owner._checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(SCHEME.primary))
            painter.drawRoundedRect(box, 6, 6)
            draw_icon(painter, "check", box.adjusted(2, 2, -2, -2), qcolor(SCHEME.on_primary), stroke=3.0)
        else:
            painter.setPen(QPen(qcolor(SCHEME.outline), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), 5, 5)
        painter.end()


class M3Checkbox(QWidget):
    """Same basics as a checkbox: isChecked(), setChecked(), toggled(bool)."""

    toggled = Signal(bool)

    def __init__(self, text: str, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._box = _Box(self)
        layout.addWidget(self._box, 0, Qt.AlignmentFlag.AlignTop)
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setContentsMargins(0, 10, 0, 0)
        layout.addWidget(self._label, 1)

    def isChecked(self) -> bool:  # noqa: N802 (Qt naming)
        return self._checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt naming)
        checked = bool(checked)
        if checked != self._checked:
            self._checked = checked
            self._box.update()
            self.toggled.emit(checked)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.setChecked(not self._checked)
            return
        super().keyPressEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._hover = True
        self._box.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._hover = False
        self._box.update()
        super().leaveEvent(event)
