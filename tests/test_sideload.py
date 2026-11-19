import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.models import ConnectionMode as M
from adb_flash_next.core.models import DeviceInfo, Transport
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult, run_streaming
from adb_flash_next.core.recovery_guide import RECOVERY_STEPS
from adb_flash_next.core.sideload import (
    LEVEL_ERROR, LEVEL_OK, LEVEL_WARNING, SideloadOutcome, build_sideload_command, classify,
    command_preview, parse_progress, run_sideload, sideload_readiness, validate_rom_zip,
)


def make_zip(path: Path, names):
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(n, b"x")
    return path


class ZipTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_recovery_zip_ok(self):
        z = make_zip(self.tmp / "rom.zip", ["META-INF/com/google/android/update-binary", "system.new.dat"])
        r = validate_rom_zip(z)
        self.assertEqual(r.level, LEVEL_OK)
        self.assertIn("does not guarantee", r.message)

    def test_ab_payload_zip_ok(self):
        z = make_zip(self.tmp / "rom.zip", ["payload.bin", "META-INF/com/android/metadata"])
        self.assertEqual(validate_rom_zip(z).level, LEVEL_OK)

    def test_fastboot_package_warns(self):
        z = make_zip(self.tmp / "images.zip", ["boot.img", "super.img", "flash_all.bat"])
        r = validate_rom_zip(z)
        self.assertEqual(r.level, LEVEL_WARNING)
        self.assertIn("Fastboot package", r.message)

    def test_not_a_zip_is_error(self):
        p = self.tmp / "rom.zip"
        p.write_bytes(b"not a zip at all")
        self.assertEqual(validate_rom_zip(p).level, LEVEL_ERROR)

    def test_empty_and_missing_are_errors(self):
        p = self.tmp / "e.zip"
        p.write_bytes(b"")
        self.assertEqual(validate_rom_zip(p).level, LEVEL_ERROR)
        self.assertEqual(validate_rom_zip(self.tmp / "none.zip").level, LEVEL_ERROR)
        self.assertEqual(validate_rom_zip(self.tmp).level, LEVEL_ERROR)

    def test_wrong_extension_warns(self):
        z = make_zip(self.tmp / "rom.bin", ["payload.bin"])
        self.assertEqual(validate_rom_zip(z).level, LEVEL_WARNING)


class ParseTests(unittest.TestCase):
    def test_progress_formats(self):
        self.assertEqual(parse_progress("serving: 'rom.zip'  (~47%)   "), 47)
        self.assertEqual(parse_progress("serving: 'rom.zip'  (~100%)"), 100)
        self.assertEqual(parse_progress("Sending 12%"), 12)
        self.assertIsNone(parse_progress("Total xfer: 1.00x"))
        self.assertIsNone(parse_progress("adb: failed to read command: Success"))
        self.assertIsNone(parse_progress("serving: 'rom.zip'  (~250%)"))


class ReadinessTests(unittest.TestCase):
    def dev(self, transport, mode):
        return DeviceInfo(serial="A1", transport=transport, mode=mode)

    def test_only_sideload_is_ready(self):
        self.assertTrue(sideload_readiness(self.dev(Transport.ADB, M.SIDELOAD))[0])
        for transport, mode in ((Transport.ADB, M.RECOVERY), (Transport.ADB, M.ANDROID),
                                (Transport.FASTBOOT, M.FASTBOOT), (Transport.ADB, M.UNAUTHORIZED)):
            self.assertFalse(sideload_readiness(self.dev(transport, mode))[0], mode)
        self.assertFalse(sideload_readiness(None)[0])

    def test_recovery_hint_names_the_menu_entry(self):
        _ready, _text, hint = sideload_readiness(self.dev(Transport.ADB, M.RECOVERY))
        self.assertIn("Apply from ADB", hint)


class GuideTests(unittest.TestCase):
    def test_format_data_step_is_marked_manual_and_dangerous(self):
        step = next(s for s in RECOVERY_STEPS if "Format data" in s.title)
        self.assertTrue(step.warning)
        text = " ".join(step.bullets)
        self.assertIn("ERASES EVERYTHING", text)
        self.assertIn("never formats data", text)

    def test_all_steps_present(self):
        titles = [s.title for s in RECOVERY_STEPS]
        self.assertEqual(len(titles), 4)
        self.assertTrue(any("sideload" in t.lower() for t in titles))


class ClassifyTests(unittest.TestCase):
    def res(self, rc=0, out="", err="", **kw):
        return CommandResult(("adb",), rc, out, err, **kw)

    def test_success_only_on_exit_zero(self):
        r = classify(self.res(0, err="serving: 'x'  (~100%)"), 100)
        self.assertEqual(r.outcome, SideloadOutcome.COMPLETED)
        self.assertIn("NOT yet proof", r.message)

    def test_failure_exit_code(self):
        r = classify(self.res(1, err="adb: sideload connection failed: closed"), 12)
        self.assertEqual(r.outcome, SideloadOutcome.FAILED)

    def test_failed_to_read_command_is_inconclusive_not_success(self):
        r = classify(self.res(1, err="serving: 'x'  (~47%)\nadb: failed to read command: Success"), 47)
        self.assertEqual(r.outcome, SideloadOutcome.INCONCLUSIVE)

    def test_disconnect(self):
        r = classify(self.res(1, err="error: no devices/emulators found"), 5)
        self.assertEqual(r.outcome, SideloadOutcome.FAILED)
        self.assertIn("disconnected", r.message)

    def test_cancel_timeout_and_start_error(self):
        self.assertEqual(classify(self.res(None, cancelled=True), 3).outcome, SideloadOutcome.CANCELLED)
        self.assertEqual(classify(self.res(None, timed_out=True), 3).outcome, SideloadOutcome.FAILED)
        self.assertEqual(classify(self.res(None, error="nope"), None).outcome, SideloadOutcome.FAILED)


class RunSideloadTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.zip = make_zip(self.tmp / "rom.zip", ["payload.bin"])
        self.tools = PlatformTools(self.tmp, self.tmp / "adb", self.tmp / "fastboot")
        self.log = []
        self.progress = []

    def tearDown(self):
        self._t.cleanup()

    def lister(self, state):
        def run(args, timeout, cancel_event=None):
            text = "List of devices attached\n" + (f"ABC123\t{state}\n" if state else "\n")
            return CommandResult(tuple(args), 0, stdout=text)
        return run

    def streamer(self, lines, rc=0, record=None):
        def run(args, on_line=None, cancel_event=None, max_seconds=None):
            if record is not None:
                record.append(list(args))
            for ln in lines:
                on_line("stderr", ln)
            return CommandResult(tuple(args), rc, stderr="\n".join(lines))
        return run

    def go(self, state="sideload", lines=(), rc=0, record=None, serial="ABC123", rom=None):
        return run_sideload(
            self.tools, serial, rom or self.zip,
            on_progress=self.progress.append, on_log=lambda l, m: self.log.append((l, m)),
            list_runner=self.lister(state), streamer=self.streamer(lines, rc, record),
        )

    def test_success_flow_and_command(self):
        record = []
        r = self.go(lines=["serving: 'rom.zip'  (~10%)", "serving: 'rom.zip'  (~10%)", "serving: 'rom.zip'  (~50%)",
                           "serving: 'rom.zip'  (~100%)", "Total xfer: 1.00x"], record=record)
        self.assertEqual(r.outcome, SideloadOutcome.COMPLETED)
        self.assertEqual(self.progress, [10, 50, 100])
        self.assertEqual(record[0][1:4], ["-s", "ABC123", "sideload"])
        self.assertTrue(any("Total xfer" in m for _l, m in self.log))
        self.assertEqual(sum("Transferred 10%" in m for _l, m in self.log), 1)

    def test_refuses_when_device_not_in_sideload(self):
        record = []
        r = self.go(state="recovery", record=record)
        self.assertEqual(r.outcome, SideloadOutcome.FAILED)
        self.assertEqual(record, [])  # nothing was run
        self.assertIn("Nothing was sent", r.message)

    def test_refuses_when_device_gone(self):
        record = []
        r = self.go(state=None, record=record)
        self.assertEqual(r.outcome, SideloadOutcome.FAILED)
        self.assertEqual(record, [])

    def test_refuses_bad_serial_and_bad_zip(self):
        record = []
        self.assertEqual(self.go(serial="x; y", record=record).outcome, SideloadOutcome.FAILED)
        bad = self.tmp / "bad.zip"
        bad.write_bytes(b"nope")
        self.assertEqual(self.go(rom=bad, record=record).outcome, SideloadOutcome.FAILED)
        self.assertEqual(record, [])

    def test_failure_is_reported_as_failure(self):
        r = self.go(lines=["serving: 'rom.zip'  (~3%)", "error: closed"], rc=1)
        self.assertEqual(r.outcome, SideloadOutcome.FAILED)

    def test_command_preview(self):
        self.assertEqual(command_preview("A1", Path("/x/rom.zip")), 'adb -s A1 sideload ' + str(Path("/x/rom.zip")))

    def test_build_command_requires_file(self):
        with self.assertRaises(ValueError):
            build_sideload_command(self.tools, "A1", self.tmp / "missing.zip")


class StreamingTests(unittest.TestCase):
    def test_lines_split_on_carriage_return(self):
        code = "import sys,time\nfor i in (10,20,30):\n    sys.stderr.write(f\"serving (~{i}%)\\r\"); sys.stderr.flush(); time.sleep(0.05)\nsys.stderr.write('done\\n')"
        seen = []
        r = run_streaming([sys.executable, "-c", code], on_line=lambda s, t: seen.append(t), max_seconds=20)
        self.assertTrue(r.ok)
        self.assertEqual(seen, ["serving (~10%)", "serving (~20%)", "serving (~30%)", "done"])
        self.assertIn("serving (~30%)", r.stderr)

    def test_stdout_and_exit_code(self):
        r = run_streaming([sys.executable, "-c", "print('hi'); import sys; sys.exit(2)"], max_seconds=20)
        self.assertFalse(r.ok)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "hi")

    def test_cancel(self):
        ev = threading.Event()
        threading.Timer(0.6, ev.set).start()
        r = run_streaming([sys.executable, "-c", "import time; time.sleep(30)"], cancel_event=ev, max_seconds=60)
        self.assertTrue(r.cancelled)

    def test_overall_timeout(self):
        r = run_streaming([sys.executable, "-c", "import time; time.sleep(30)"], max_seconds=0.7)
        self.assertTrue(r.timed_out)

    def test_refuses_relative_executable(self):
        self.assertIsNotNone(run_streaming(["adb", "devices"]).error)

    def test_faulty_callback_does_not_hang(self):
        def boom(_s, _t):
            raise RuntimeError("bad callback")
        r = run_streaming([sys.executable, "-c", "print('a'); print('b')"], on_line=boom, max_seconds=20)
        self.assertTrue(r.ok)
        self.assertEqual(r.stdout, "a\nb")


if __name__ == "__main__":
    unittest.main()
