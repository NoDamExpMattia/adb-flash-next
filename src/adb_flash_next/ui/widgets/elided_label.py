"""A one-line label that shortens long text in the middle ("C:\\very...\\boot.img") instead of growing."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = text
        self.setMinimumWidth(40)
        self._elide()

    def set_full_text(self, text: str, tooltip: str | None = None) -> None:
        self._full = text
        self.setToolTip(tooltip if tooltip is not None else text)
        self._elide()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, max(10, self.width() - 4))
        QLabel.setText(self, shown)
