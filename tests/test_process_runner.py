import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.platform_tools import PlatformToolsError, check_directory
from adb_flash_next.core.process_runner import run_command


class RunnerTests(unittest.TestCase):
    def test_success_captures_output(self):
        r = run_command([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"], timeout=10)
        self.assertTrue(r.ok)
        self.assertEqual(r.stdout.strip(), "out")
        self.assertEqual(r.stderr.strip(), "err")

    def test_nonzero_exit_is_failure(self):
        r = run_command([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=10)
        self.assertFalse(r.ok)
        self.assertEqual(r.returncode, 3)

    def test_timeout(self):
        r = run_command([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.6)
        self.assertTrue(r.timed_out)
        self.assertFalse(r.ok)

    def test_cancel(self):
        ev = threading.Event()
        threading.Timer(0.5, ev.set).start()
        r = run_command([sys.executable, "-c", "import time; time.sleep(30)"], timeout=20, cancel_event=ev)
        self.assertTrue(r.cancelled)
        self.assertFalse(r.ok)

    def test_missing_executable(self):
        r = run_command(["/definitely/not/here"], timeout=2)
        self.assertFalse(r.ok)
        self.assertIsNotNone(r.error)

    def test_relative_executable_refused(self):
        r = run_command(["adb", "devices"], timeout=2)
        self.assertIsNotNone(r.error)

    def test_no_shell_interpretation(self):
        r = run_command([sys.executable, "-c", "import sys; print(sys.argv[1])", "a; echo INJECTED"], timeout=10)
        self.assertEqual(r.stdout.strip(), "a; echo INJECTED")


@unittest.skipIf(sys.platform == "win32", "uses shell-script stand-ins for adb/fastboot")
class CheckDirectoryTests(unittest.TestCase):
    def _make(self, tmp: Path, adb_ok=True):
        adb = tmp / "adb"
        adb.write_text("#!/bin/sh\n" + ("echo 'Android Debug Bridge version 1.0.41'; echo 'Version 36.0.0-123'\n" if adb_ok else "echo boom >&2; exit 1\n"))
        fb = tmp / "fastboot"
        fb.write_text("#!/bin/sh\necho 'fastboot version 36.0.0-123'\n")
        for p in (adb, fb):
            p.chmod(p.stat().st_mode | stat.S_IEXEC)

    def test_valid_folder(self):
        with tempfile.TemporaryDirectory() as d:
            self._make(Path(d))
            tools = check_directory(Path(d))
            self.assertEqual(tools.adb_version, "36.0.0-123")
            self.assertEqual(tools.fastboot_version, "fastboot version 36.0.0-123")

    def test_missing_files(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PlatformToolsError) as ctx:
                check_directory(Path(d))
            self.assertIn("Missing", str(ctx.exception))

    def test_broken_adb(self):
        with tempfile.TemporaryDirectory() as d:
            self._make(Path(d), adb_ok=False)
            with self.assertRaises(PlatformToolsError):
                check_directory(Path(d))

    def test_missing_folder(self):
        with self.assertRaises(PlatformToolsError):
            check_directory(Path("/no/such/folder"))


if __name__ == "__main__":
    unittest.main()
