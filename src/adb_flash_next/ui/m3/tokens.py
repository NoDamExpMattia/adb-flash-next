"""Material 3 Expressive design tokens (dark scheme with a red seed).

Pure data: no Qt in this module. Change colours here to re-theme the whole app.
Role names follow the Material 3 colour system (surface containers, primary, ...).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorScheme:
    # Surfaces (slightly warm/red-tinted neutrals)
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
    success: str = "#5DDC91"
    warning: str = "#FFB74D"
    error: str = "#FF8F87"


SCHEME = ColorScheme()

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
