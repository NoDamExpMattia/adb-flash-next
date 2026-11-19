import re
import unittest

from tests import _bootstrap  # noqa: F401
from adb_flash_next.ui.m3.tokens import (
    DEFAULT_SEED, PRESET_SEEDS, ColorScheme, blend, build_scheme, contrast_ratio, normalize_hex,
)

SEEDS = [hex_ for _name, hex_ in PRESET_SEEDS] + [
    "#000000", "#FFFFFF", "#808080", "#FFEE00", "#000080", "#FF00FF", "#00FFFF",
    "#123456", "#FEFEFE", "#010101", "#00FF00", "#FF0000", "#7F7F00", "#C0C0C0",
]
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SURFACES = ("surface", "surface_container_lowest", "surface_container_low", "surface_container",
            "surface_container_high", "surface_container_highest")


class NormalizeTests(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertEqual(normalize_hex("#e5141e"), "#E5141E")
        self.assertEqual(normalize_hex("  #00ff00 "), "#00FF00")
        for bad in ("red", "#12345", "#GGGGGG", "", None, 5, "#1234567"):
            self.assertEqual(normalize_hex(bad), DEFAULT_SEED, bad)


class SchemeReadabilityTests(unittest.TestCase):
    def check(self, seed, dark):
        s = build_scheme(seed, dark)
        label = f"{seed} dark={dark}"
        self.assertIs(s.is_dark, dark, label)
        for name, value in vars(s).items():
            if isinstance(value, str):
                self.assertRegex(value, HEX, f"{label} {name}")
        self.assertGreaterEqual(contrast_ratio(s.on_primary, s.primary), 4.5, f"{label} on_primary")
        self.assertGreaterEqual(contrast_ratio(s.primary, s.surface), 3.0, f"{label} primary vs surface")
        self.assertGreaterEqual(contrast_ratio(s.primary_bright, s.surface), 4.5, f"{label} primary_bright")
        for surface in SURFACES:
            self.assertGreaterEqual(contrast_ratio(s.on_surface, getattr(s, surface)), 4.5, f"{label} on_surface/{surface}")
        for surface in ("surface", "surface_container", "surface_container_highest"):
            self.assertGreaterEqual(contrast_ratio(s.on_surface_variant, getattr(s, surface)), 4.5, f"{label} variant/{surface}")
        self.assertGreaterEqual(contrast_ratio(s.on_secondary_container, s.secondary_container), 4.5, f"{label} secondary")
        self.assertGreaterEqual(contrast_ratio(s.on_primary_container, s.primary_container), 4.5, f"{label} primary container")
        for status in (s.success, s.warning, s.error):
            for surface in ("surface", "surface_container", "surface_container_highest"):
                self.assertGreaterEqual(contrast_ratio(status, getattr(s, surface)), 4.5, f"{label} status {status}/{surface}")
        # white/black text drawn on the gradient used by the Reboot/Utilities tiles
        self.assertGreaterEqual(contrast_ratio(s.on_primary, s.primary_dark), 3.0, f"{label} gradient end")
        lightness = [sum(int(getattr(s, n)[i:i + 2], 16) for i in (1, 3, 5)) for n in SURFACES]
        ordered = sorted(lightness[1:], reverse=not dark)
        self.assertEqual(lightness[1:], ordered, f"{label} surface hierarchy")

    def test_every_seed_in_both_modes(self):
        for seed in SEEDS:
            for dark in (True, False):
                self.check(seed, dark)

    def test_default_dark_red_is_the_original_hand_tuned_scheme(self):
        self.assertEqual(build_scheme(DEFAULT_SEED, True), ColorScheme())
        self.assertEqual(build_scheme("#e5141e", True), ColorScheme())

    def test_default_light_red_differs_and_is_light(self):
        light = build_scheme(DEFAULT_SEED, False)
        self.assertFalse(light.is_dark)
        self.assertGreater(contrast_ratio(light.surface, "#000000"), 10)

    def test_invalid_seed_falls_back_to_default(self):
        self.assertEqual(build_scheme("nonsense", True), ColorScheme())

    def test_accent_hue_is_kept_for_a_normal_colour(self):
        blue = build_scheme("#2F6FED", True)
        r, g, b = (int(blue.primary[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(b, r)
        self.assertGreater(b, g)

    def test_blend(self):
        self.assertEqual(blend("#000000", "#FFFFFF", 0.5), "#808080")
        self.assertEqual(blend("#102030", "#102030", 0.7), "#102030")


if __name__ == "__main__":
    unittest.main()
