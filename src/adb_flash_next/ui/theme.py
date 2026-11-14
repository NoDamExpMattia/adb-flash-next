"""Dark theme with a saturated red accent (palette + Qt style sheet)."""
from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class Colors:
    """Central colour definitions. Change the accent here to re-theme the app."""

    BG = "#0b0b0c"
    SIDEBAR = "#111113"
    CARD = "#1a1a1e"
    BORDER = "#2b2b31"
    TEXT = "#ececee"
    MUTED = "#8b8b94"

    ACCENT = "#e5141e"
    ACCENT_HOVER = "#ff2a35"
    ACCENT_PRESSED = "#b30f17"
    ACCENT_SOFT = "#1f1214"

    RING_TRACK = "#26262b"

    INFO = "#b8b8c0"
    SUCCESS = "#3ddc84"
    WARNING = "#f5a623"
    ERROR = "#ff5252"


_STYLESHEET = Template(
    """
QWidget {
    background-color: $BG;
    color: $TEXT;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QLabel { background: transparent; }
QLabel#PageTitle { font-size: 18pt; font-weight: 700; }
QLabel#CardTitle { font-size: 11pt; font-weight: 700; }
QLabel#BrandName { font-size: 11pt; font-weight: 800; }
QLabel#Muted { color: $MUTED; }
QLabel#StatusText { font-size: 12pt; font-weight: 700; }

QFrame#Sidebar { background-color: $SIDEBAR; border-right: 1px solid $BORDER; }
QFrame#Card {
    background-color: $CARD;
    border: 1px solid $BORDER;
    border-radius: 10px;
}
QFrame#Card QLabel, QFrame#Card QWidget { background-color: transparent; }

QPushButton#NavButton {
    text-align: left;
    padding: 11px 18px;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    background-color: transparent;
    color: $MUTED;
    font-weight: 600;
}
QPushButton#NavButton:hover { background-color: #18181c; color: $TEXT; }
QPushButton#NavButton:checked {
    color: $TEXT;
    background-color: $ACCENT_SOFT;
    border-left: 3px solid $ACCENT;
}

QPushButton {
    background-color: $CARD;
    border: 1px solid $BORDER;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { border-color: $ACCENT; }
QPushButton:pressed { background-color: $ACCENT_PRESSED; }
QPushButton:disabled { color: $MUTED; border-color: $BORDER; }
QPushButton#Primary {
    background-color: $ACCENT;
    border: none;
    color: white;
    font-weight: 700;
}
QPushButton#Primary:hover { background-color: $ACCENT_HOVER; }
QPushButton#Primary:pressed { background-color: $ACCENT_PRESSED; }

QComboBox {
    background-color: $CARD;
    border: 1px solid $BORDER;
    border-radius: 6px;
    padding: 5px 10px;
}
QComboBox:hover { border-color: $ACCENT; }
QComboBox QAbstractItemView {
    background-color: $CARD;
    border: 1px solid $BORDER;
    selection-background-color: $ACCENT;
    outline: 0;
}

QTextEdit#LogView {
    background-color: #0f0f11;
    border: 1px solid $BORDER;
    border-radius: 8px;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 9pt;
    padding: 4px;
}

QSlider::groove:horizontal { height: 4px; background: $RING_TRACK; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ACCENT; border-radius: 2px; }
QSlider::handle:horizontal {
    background: $ACCENT; width: 14px; margin: -6px 0; border-radius: 7px;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #33333a; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $ACCENT; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #33333a; border-radius: 5px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: $ACCENT; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

QToolTip { background-color: $CARD; color: $TEXT; border: 1px solid $ACCENT; }
"""
)


def _build_palette() -> QPalette:
    palette = QPalette()
    roles = QPalette.ColorRole
    palette.setColor(roles.Window, QColor(Colors.BG))
    palette.setColor(roles.WindowText, QColor(Colors.TEXT))
    palette.setColor(roles.Base, QColor("#0f0f11"))
    palette.setColor(roles.AlternateBase, QColor(Colors.CARD))
    palette.setColor(roles.Text, QColor(Colors.TEXT))
    palette.setColor(roles.Button, QColor(Colors.CARD))
    palette.setColor(roles.ButtonText, QColor(Colors.TEXT))
    palette.setColor(roles.Highlight, QColor(Colors.ACCENT))
    palette.setColor(roles.HighlightedText, QColor("#ffffff"))
    palette.setColor(roles.ToolTipBase, QColor(Colors.CARD))
    palette.setColor(roles.ToolTipText, QColor(Colors.TEXT))
    return palette


def apply_theme(app: QApplication) -> None:
    """Apply the Fusion style, the dark palette and the style sheet."""
    app.setStyle("Fusion")
    app.setPalette(_build_palette())
    values = {k: v for k, v in vars(Colors).items() if k.isupper()}
    app.setStyleSheet(_STYLESHEET.substitute(values))
