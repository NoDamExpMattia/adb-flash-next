"""Replaceable logo. Drop assets/logo.png or assets/logo.svg to override."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from adb_flash_next.config.constants import ASSETS_DIR, LOGO_CANDIDATES
from adb_flash_next.ui.theme import Colors


class LogoWidget(QWidget):
    """Shows the user's logo if present, otherwise a simple red placeholder."""

    def __init__(self, size: int = 40, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._pixmap: QPixmap | None = self._load_logo(size)

    @staticmethod
    def _load_logo(size: int) -> QPixmap | None:
        for name in LOGO_CANDIDATES:
            path = ASSETS_DIR / name
            if path.is_file():
                pixmap = QIcon(str(path)).pixmap(QSize(size * 2, size * 2))
                if not pixmap.isNull():
                    return pixmap
        return None

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._pixmap is not None:
            painter.drawPixmap(self.rect(), self._pixmap)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(Colors.ACCENT))
            painter.drawRoundedRect(QRectF(self.rect()), 14, 14)
            font = QFont(self.font())
            font.setBold(True)
            font.setPixelSize(int(self.height() * 0.42))
            painter.setFont(font)
            painter.setPen(QColor(Colors.ON_PRIMARY))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "AF")
        painter.end()
