"""Small helpers shared by the Material 3 widgets."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve
from PySide6.QtGui import QColor


def qcolor(value: str, alpha: float = 1.0) -> QColor:
    """QColor from '#RRGGBB' with an alpha between 0 and 1."""
    color = QColor(value)
    color.setAlphaF(max(0.0, min(1.0, alpha)))
    return color


def rgba_css(value: str, alpha: float) -> str:
    """CSS 'rgba(r, g, b, a)' string for style sheets (alpha 0..1)."""
    color = QColor(value)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(round(alpha * 255))})"


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def spring(overshoot: float = 1.4) -> QEasingCurve:
    """Easing curve that overshoots slightly and settles: a cheap spring."""
    curve = QEasingCurve(QEasingCurve.Type.OutBack)
    curve.setOvershoot(overshoot)
    return curve
