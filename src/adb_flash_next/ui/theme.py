"""Material 3 Expressive theme: application palette, font and style sheet.

`Colors` keeps the names older code uses and maps them onto Material 3 roles, so
every page follows the tokens in ui/m3/tokens.py.
"""
from __future__ import annotations

from string import Template

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from adb_flash_next.ui.m3.tokens import DEFAULT_SEED, FONT_FAMILIES, SCHEME, build_scheme


class Colors:
    """Compatibility names mapped onto the CURRENT Material 3 scheme (updated by refresh())."""

    BG: str = ""
    SIDEBAR: str = ""
    CARD: str = ""
    BORDER: str = ""
    TEXT: str = ""
    MUTED: str = ""
    ACCENT: str = ""
    ACCENT_HOVER: str = ""
    ACCENT_PRESSED: str = ""
    ACCENT_SOFT: str = ""
    ON_PRIMARY: str = ""
    RING_TRACK: str = ""
    INFO: str = ""
    SUCCESS: str = ""
    WARNING: str = ""
    ERROR: str = ""

    @classmethod
    def refresh(cls) -> None:
        """Copy the current scheme into the compatibility names. Call after SCHEME.set()."""
        s = SCHEME
        cls.BG = s.surface
        cls.SIDEBAR = s.surface_container_low
        cls.CARD = s.surface_container
        cls.BORDER = s.outline_variant
        cls.TEXT = s.on_surface
        cls.MUTED = s.on_surface_variant
        cls.ACCENT = s.primary
        cls.ACCENT_HOVER = s.primary_hover
        cls.ACCENT_PRESSED = s.primary_pressed
        cls.ACCENT_SOFT = s.secondary_container
        cls.ON_PRIMARY = s.on_primary
        cls.RING_TRACK = s.surface_container_highest
        cls.INFO = s.on_surface_variant
        cls.SUCCESS = s.success
        cls.WARNING = s.warning
        cls.ERROR = s.error


Colors.refresh()


class _ThemeManager(QObject):
    """Emits `changed` after the theme was applied, so pages can re-render colours they baked in."""

    changed = Signal()


_manager: _ThemeManager | None = None


def theme_manager() -> _ThemeManager:
    global _manager
    if _manager is None:
        _manager = _ThemeManager()
    return _manager


def _style_values() -> dict[str, str]:
    values = {k.upper(): v for k, v in SCHEME.as_dict().items() if isinstance(v, str)}
    values.update({k: v for k, v in vars(Colors).items() if k.isupper() and isinstance(v, str)})
    return values


_STYLESHEET = Template(
    """
QMainWindow, QDialog { background-color: $SURFACE; }

QLabel#PageTitle { font-size: 32px; font-weight: bold; }
QLabel#CardTitle { font-size: 16px; font-weight: bold; }
QLabel#BrandName { font-size: 15px; font-weight: bold; }
QLabel#Muted { color: $ON_SURFACE_VARIANT; }
QLabel#StatusText { font-size: 18px; font-weight: bold; }

QFrame#Rail { background-color: $SURFACE_CONTAINER_LOW; border: none; }
QFrame#Card {
    background-color: $SURFACE_CONTAINER;
    border: none;
    border-radius: 28px;
}

QFrame#DropBox {
    background-color: $SURFACE_CONTAINER_LOW;
    border: 2px dashed $OUTLINE_VARIANT;
    border-radius: 24px;
}

QPushButton {
    background-color: $SURFACE_CONTAINER_HIGHEST;
    border: none;
    border-radius: 14px;
    padding: 9px 22px;
    font-weight: bold;
}
QPushButton:hover { background-color: $SURFACE_HOVER; }
QPushButton:pressed { background-color: $SURFACE_PRESSED; }
QPushButton:disabled { color: $DISABLED_TEXT; background-color: $SURFACE_CONTAINER_HIGH; }

QPushButton#Primary {
    background-color: $PRIMARY;
    color: $ON_PRIMARY;
    border-radius: 16px;
    padding: 10px 26px;
    font-size: 15px;
}
QPushButton#Primary:hover { background-color: $ACCENT_HOVER; }
QPushButton#Primary:pressed { background-color: $ACCENT_PRESSED; }
QPushButton#Primary:disabled { background-color: $PRIMARY_DISABLED_BG; color: $PRIMARY_DISABLED_TEXT; }

QComboBox {
    background-color: $SURFACE_CONTAINER_HIGHEST;
    border: none;
    border-radius: 14px;
    padding: 8px 16px;
}
QComboBox:hover { background-color: $SURFACE_HOVER; }
QComboBox:disabled { color: $DISABLED_TEXT; background-color: $SURFACE_CONTAINER_HIGH; }
QComboBox QAbstractItemView {
    background-color: $SURFACE_CONTAINER_HIGH;
    border: 1px solid $OUTLINE_VARIANT;
    border-radius: 14px;
    padding: 6px;
    selection-background-color: $PRIMARY;
    outline: 0;
}
QComboBox QAbstractItemView::item { border-radius: 10px; padding: 8px 12px; min-height: 22px; }

QLineEdit {
    background-color: $SURFACE_CONTAINER_HIGHEST;
    border: 2px solid transparent;
    border-radius: 14px;
    padding: 8px 14px;
}
QLineEdit:focus { border-color: $PRIMARY_BRIGHT; }

QTextEdit#LogView {
    background-color: $SURFACE_CONTAINER_LOWEST;
    border: none;
    border-radius: 20px;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
    padding: 8px;
}

QSlider::groove:horizontal { height: 6px; background: $SURFACE_CONTAINER_HIGHEST; border-radius: 3px; }
QSlider::sub-page:horizontal { background: $PRIMARY; border-radius: 3px; }
QSlider::handle:horizontal { background: $PRIMARY; width: 20px; margin: -8px 0; border-radius: 10px; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $OUTLINE_VARIANT; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $OUTLINE; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: $OUTLINE_VARIANT; border-radius: 4px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: $OUTLINE; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

QToolTip {
    background-color: $SURFACE_CONTAINER_HIGHEST;
    color: $ON_SURFACE;
    border: 1px solid $OUTLINE_VARIANT;
    border-radius: 8px;
    padding: 6px 10px;
}
"""
)


def _build_palette() -> QPalette:
    palette = QPalette()
    roles = QPalette.ColorRole
    palette.setColor(roles.Window, QColor(SCHEME.surface))
    palette.setColor(roles.WindowText, QColor(SCHEME.on_surface))
    palette.setColor(roles.Base, QColor(SCHEME.surface_container_lowest))
    palette.setColor(roles.AlternateBase, QColor(SCHEME.surface_container))
    palette.setColor(roles.Text, QColor(SCHEME.on_surface))
    palette.setColor(roles.Button, QColor(SCHEME.surface_container_highest))
    palette.setColor(roles.ButtonText, QColor(SCHEME.on_surface))
    palette.setColor(roles.Highlight, QColor(SCHEME.primary))
    palette.setColor(roles.HighlightedText, QColor(SCHEME.on_primary))
    palette.setColor(roles.ToolTipBase, QColor(SCHEME.surface_container_highest))
    palette.setColor(roles.ToolTipText, QColor(SCHEME.on_surface))
    palette.setColor(roles.PlaceholderText, QColor(SCHEME.outline))
    return palette


def _build_font() -> QFont:
    font = QFont()
    font.setFamilies(list(FONT_FAMILIES))
    font.setPixelSize(14)
    return font


def apply_theme(app: QApplication, seed: str = DEFAULT_SEED, dark: bool = True) -> None:
    """Apply a theme built from `seed` (dark or light) to the whole application, live."""
    SCHEME.set(build_scheme(seed, dark))
    Colors.refresh()
    app.setStyle("Fusion")
    app.setPalette(_build_palette())
    app.setFont(_build_font())
    app.setStyleSheet(_STYLESHEET.substitute(_style_values()))
    for widget in app.allWidgets():
        widget.update()  # repaint custom-drawn widgets with the new colours
    theme_manager().changed.emit()
