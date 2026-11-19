<<<<<<< HEAD
"""Material 3 Expressive design tokens, with dark and light schemes built from any accent colour.

Pure data and maths: no Qt in this module (so it can be unit-tested). `SCHEME` always points at
the CURRENT scheme; widgets read it at paint time, so switching theme only needs a repaint.
"""
from __future__ import annotations

import colorsys
import re
from dataclasses import asdict, dataclass

DEFAULT_SEED = "#E5141E"

# Accent colour presets offered in Settings: (name, hex).
PRESET_SEEDS = (
    ("Red", "#E5141E"),
    ("Orange", "#F57C00"),
    ("Amber", "#F9A825"),
    ("Green", "#2EA44F"),
    ("Teal", "#00A3A3"),
    ("Blue", "#2F6FED"),
    ("Purple", "#8E44EC"),
    ("Pink", "#E91E8C"),
)
=======
"""Material 3 Expressive design tokens (dark scheme with a red seed).

Pure data: no Qt in this module. Change colours here to re-theme the whole app.
Role names follow the Material 3 colour system (surface containers, primary, ...).
"""
from __future__ import annotations

from dataclasses import dataclass
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b


@dataclass(frozen=True)
class ColorScheme:
<<<<<<< HEAD
    """Defaults are the hand-tuned DARK RED scheme the app shipped with."""

    # Surfaces
=======
    # Surfaces (slightly warm/red-tinted neutrals)
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    surface: str = "#140F10"
    surface_container_lowest: str = "#0F0A0B"
    surface_container_low: str = "#1C1617"
    surface_container: str = "#211A1B"
    surface_container_high: str = "#2B2425"
    surface_container_highest: str = "#362E2F"
    on_surface: str = "#EDE0DF"
    on_surface_variant: str = "#D8C2C0"
    outline: str = "#A08C8B"
    outline_variant: str = "#534342"

<<<<<<< HEAD
    # Primary: the accent colour
    primary: str = "#E5141E"
    primary_dark: str = "#8F0B12"  # gradient end for expressive filled surfaces
    on_primary: str = "#FFFFFF"
    primary_bright: str = "#FF6B72"  # accent for text, icons and focus on surfaces
    primary_container: str = "#5C0A0F"
    on_primary_container: str = "#FFDAD8"

    # Secondary: navigation indicator and tonal buttons
    secondary_container: str = "#4D2A2C"
    on_secondary_container: str = "#FFDAD8"

    # Status colours
=======
    # Primary: the saturated brand red
    primary: str = "#E5141E"
    primary_dark: str = "#8F0B12"  # gradient end for expressive filled surfaces
    on_primary: str = "#FFFFFF"
    primary_bright: str = "#FF6B72"  # red for text, icons and focus on dark surfaces
    primary_container: str = "#5C0A0F"
    on_primary_container: str = "#FFDAD8"

    # Secondary: muted rose, used for the navigation indicator and tonal buttons
    secondary_container: str = "#4D2A2C"
    on_secondary_container: str = "#FFDAD8"

    # Status colours (not Material roles, but needed by this app)
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    success: str = "#5DDC91"
    warning: str = "#FFB74D"
    error: str = "#FF8F87"

<<<<<<< HEAD
    # Derived states (used by the style sheet)
    is_dark: bool = True
    primary_hover: str = "#FF2A35"
    primary_pressed: str = "#B30F17"
    surface_hover: str = "#443B3C"
    surface_pressed: str = "#50464A"
    disabled_text: str = "#6f605f"
    primary_disabled_bg: str = "#3a1417"
    primary_disabled_text: str = "#8b6b6e"

=======

SCHEME = ColorScheme()
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b

# Shape scale in pixels. "full" (pill) is height / 2 and is computed per component.
SHAPE = {"xs": 4, "s": 8, "m": 12, "l": 16, "xl": 28, "xxl": 48}

# State layer opacities.
STATE = {
    "hover": 0.08,
    "focus": 0.10,
    "pressed": 0.12,
    "disabled_container": 0.12,
    "disabled_content": 0.38,
}

# Motion durations in milliseconds.
MOTION = {"short": 150, "medium": 250, "long": 400}

# Preferred font families, first one installed wins.
FONT_FAMILIES = ("Roboto Flex", "Roboto", "Segoe UI Variable Text", "Segoe UI", "Arial")
<<<<<<< HEAD


# ----------------------------------------------------------------------------- colour maths
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_hex(value: object, fallback: str = DEFAULT_SEED) -> str:
    """'#rrggbb' in upper case, or `fallback` when `value` is not a valid colour."""
    if isinstance(value, str) and _HEX_RE.match(value.strip()):
        return value.strip().upper()
    return fallback


def _rgb255(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _hls_to_hex(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def relative_luminance(color: str) -> float:
    def linear(channel: int) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _rgb255(color)
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio between two '#rrggbb' colours (1 to 21)."""
    a, b = relative_luminance(first), relative_luminance(second)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def blend(base: str, over: str, amount: float) -> str:
    """Mix `over` into `base` by `amount` (0..1)."""
    b1, b2 = _rgb255(base), _rgb255(over)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * amount) for x, y in zip(b1, b2))


def _text_on(background: str, hue: float, sat: float, light: bool, start: float, target: float = 4.5) -> str:
    """A text colour of the given hue that reaches `target` contrast on `background`."""
    lightness = start
    for _ in range(60):
        candidate = _hls_to_hex(hue, lightness, sat)
        if contrast_ratio(candidate, background) >= target:
            return candidate
        lightness = min(1.0, lightness + 0.02) if light else max(0.0, lightness - 0.02)
    return "#FFFFFF" if light else "#000000"


def build_scheme(seed: str, dark: bool = True) -> ColorScheme:
    """Build a complete scheme from an accent colour. Every text/background pair is checked for
    readability (WCAG AA, 4.5:1) and the accent itself for visibility (3:1) against the surface."""
    seed = normalize_hex(seed)
    if dark and seed == DEFAULT_SEED:
        return ColorScheme()  # keep the hand-tuned original look

    h, _l, s = colorsys.rgb_to_hls(*(c / 255 for c in _rgb255(seed)))
    tint = 0.05 + 0.10 * s  # surfaces carry a faint tint of the accent hue
    levels = (0.045, 0.065, 0.09, 0.115, 0.145, 0.18) if dark else (1.0, 0.975, 0.955, 0.93, 0.91, 0.885)
    lowest, surface, low, container, high, highest = (_hls_to_hex(h, lv, tint) for lv in levels)

    on_surface = _text_on(highest, h, 0.12, dark, 0.90 if dark else 0.10)
    on_variant = _text_on(highest, h, 0.10, dark, 0.80 if dark else 0.30)
    outline = _hls_to_hex(h, 0.60 if dark else 0.45, 0.08)
    outline_variant = _hls_to_hex(h, 0.30 if dark else 0.78, 0.10)

    # Accent: the chosen colour, moved lighter/darker only if it would not stand out from the surface.
    p_l = _l
    primary = seed
    for _ in range(60):
        if contrast_ratio(primary, surface) >= 3.0:
            break
        p_l = min(0.95, p_l + 0.02) if dark else max(0.05, p_l - 0.02)
        primary = _hls_to_hex(h, p_l, s)
    on_primary = "#FFFFFF" if contrast_ratio("#FFFFFF", primary) >= 4.5 else "#000000"

    bright = primary
    b_l = p_l
    for _ in range(60):
        if contrast_ratio(bright, surface) >= 4.5:
            break
        b_l = min(0.97, b_l + 0.02) if dark else max(0.03, b_l - 0.02)
        bright = _hls_to_hex(h, b_l, s)
    else:
        bright = "#FFFFFF" if dark else "#000000"

    primary_dark = _hls_to_hex(h, max(0.05, p_l * 0.62), s) if on_primary == "#FFFFFF" else primary
    primary_container = _hls_to_hex(h, 0.18 if dark else 0.88, min(1.0, 0.25 + 0.6 * s) * 0.8)
    on_primary_container = _text_on(primary_container, h, 0.6, dark, 0.90 if dark else 0.14)
    secondary_container = _hls_to_hex(h, 0.22 if dark else 0.86, 0.10 + 0.25 * s)
    on_secondary_container = _text_on(secondary_container, h, 0.5, dark, 0.90 if dark else 0.16)

    success, warning, error = (
        ("#5DDC91", "#FFB74D", "#FF8F87") if dark else ("#08632F", "#7A4E00", "#A61F19")
    )
    disabled_text = blend(high, on_surface, 0.38)
    return ColorScheme(
        surface=surface,
        surface_container_lowest=lowest,
        surface_container_low=low,
        surface_container=container,
        surface_container_high=high,
        surface_container_highest=highest,
        on_surface=on_surface,
        on_surface_variant=on_variant,
        outline=outline,
        outline_variant=outline_variant,
        primary=primary,
        primary_dark=primary_dark,
        on_primary=on_primary,
        primary_bright=bright,
        primary_container=primary_container,
        on_primary_container=on_primary_container,
        secondary_container=secondary_container,
        on_secondary_container=on_secondary_container,
        success=success,
        warning=warning,
        error=error,
        is_dark=dark,
        primary_hover=blend(primary, on_primary, 0.10),
        primary_pressed=blend(primary, on_primary, 0.18),
        surface_hover=blend(highest, on_surface, 0.08),
        surface_pressed=blend(highest, on_surface, 0.12),
        disabled_text=disabled_text,
        primary_disabled_bg=blend(high, on_surface, 0.12),
        primary_disabled_text=disabled_text,
    )


class _SchemeHolder:
    """Stands in for the current scheme: `SCHEME.primary` always reads the active colours."""

    def __init__(self, scheme: ColorScheme) -> None:
        self._scheme = scheme

    def __getattr__(self, name: str):
        return getattr(self.__dict__["_scheme"], name)

    def set(self, scheme: ColorScheme) -> None:
        self._scheme = scheme

    def current(self) -> ColorScheme:
        return self._scheme

    def as_dict(self) -> dict:
        return asdict(self._scheme)


SCHEME = _SchemeHolder(ColorScheme())
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
