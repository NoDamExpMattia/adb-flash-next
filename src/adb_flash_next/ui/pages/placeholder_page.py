"""Simple page shown for features that are built in later stages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, description: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setObjectName("Muted")
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(description_label)
        layout.addStretch()
