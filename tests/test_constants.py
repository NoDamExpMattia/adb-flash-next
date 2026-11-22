import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.config.constants import APP_DIR, ASSETS_DIR, LOGO_CANDIDATES, _resolve_roots


class ResolveRootsTests(unittest.TestCase):
    def test_from_source_both_are_the_project_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "proj" / "src" / "adb_flash_next" / "config" / "constants.py"
            root, app_dir = _resolve_roots(False, None, "python", str(module))
            self.assertEqual(root, (Path(tmp) / "proj").resolve())
            self.assertEqual(app_dir, root)

    def test_frozen_uses_the_bundle_for_assets_and_the_exe_folder_for_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "dist" / "ADB Flash Next" / "ADB Flash Next.exe"
            bundle = Path(tmp) / "dist" / "ADB Flash Next" / "_internal"
            root, app_dir = _resolve_roots(True, str(bundle), str(exe), "ignored.py")
            self.assertEqual(root, bundle)
            self.assertEqual(app_dir, exe.resolve().parent)

    def test_frozen_without_bundle_folder_falls_back_to_the_exe_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "app.exe"
            root, app_dir = _resolve_roots(True, None, str(exe), "ignored.py")
            self.assertEqual(root, app_dir)

    def test_real_values_are_consistent(self):
        self.assertEqual(ASSETS_DIR, ASSETS_DIR.parent / "assets")
        self.assertIn("logo.png", LOGO_CANDIDATES)
        self.assertTrue(APP_DIR.is_absolute())


if __name__ == "__main__":
    unittest.main()
