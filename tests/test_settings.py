import json
import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.config.settings import Settings


class SettingsThemeTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.path = Path(self._t.name) / "sub" / "settings.json"

    def tearDown(self):
        self._t.cleanup()

    def test_defaults(self):
        s = Settings(self.path)
        s.load()
        self.assertEqual(s.theme_seed, "#E5141E")
        self.assertEqual(s.theme_mode, "dark")

    def test_round_trip(self):
        s = Settings(self.path)
        s.theme_seed = "#2f6fed"
        s.theme_mode = "light"
        s.platform_tools_dir = "C:\\Dev\\platform-tools"
        self.assertTrue(s.save())
        again = Settings(self.path)
        again.load()
        self.assertEqual(again.theme_seed, "#2F6FED")
        self.assertEqual(again.theme_mode, "light")
        self.assertEqual(again.platform_tools_dir, "C:\\Dev\\platform-tools")

    def test_invalid_values_are_ignored(self):
        s = Settings(self.path)
        s.theme_seed = "banana"
        s.theme_mode = "purple"
        self.assertEqual(s.theme_seed, "#E5141E")
        self.assertEqual(s.theme_mode, "dark")
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"theme_seed": 123, "theme_mode": ["x"]}), encoding="utf-8")
        s.load()
        self.assertEqual(s.theme_seed, "#E5141E")
        self.assertEqual(s.theme_mode, "dark")

    def test_corrupt_file_does_not_crash(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        s = Settings(self.path)
        s.load()
        self.assertEqual(s.theme_mode, "dark")


if __name__ == "__main__":
    unittest.main()
