import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.config.settings import Settings
from adb_flash_next.core.flash_plan import PartitionSelection, build_plan
from adb_flash_next.core.models import ConnectionMode as M
from adb_flash_next.core.models import DeviceInfo, Transport
from adb_flash_next.core.models import PartitionScheme as S
from adb_flash_next.core.payload_extractor import (
    build_extract_command, cleanup_dir, extract_partitions, locate_tool, new_run_dir, zip_has_payload,
)
from adb_flash_next.core.process_runner import CommandResult
from adb_flash_next.core.slot_resolver import SlotChoice as C


class ToolAndZipTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_locate_configured_tool(self):
        tool = self.tmp / "payload-dumper-go.exe"
        tool.write_bytes(b"x")
        self.assertEqual(locate_tool(str(tool)), tool.resolve())
        self.assertNotEqual(locate_tool(str(self.tmp / "missing.exe")), self.tmp / "missing.exe")

    def test_zip_has_payload(self):
        good = self.tmp / "a.zip"
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("payload.bin", b"x")
        bad = self.tmp / "b.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("system.new.dat", b"x")
        self.assertTrue(zip_has_payload(good))
        self.assertFalse(zip_has_payload(bad))
        self.assertFalse(zip_has_payload(self.tmp / "none.zip"))
        notzip = self.tmp / "c.zip"
        notzip.write_bytes(b"nope")
        self.assertFalse(zip_has_payload(notzip))

    def test_command_uses_an_argument_list_and_allow_listed_names(self):
        cmd = build_extract_command(Path("/t/pd"), Path("/r/rom.zip"), ["boot", "vendor_boot", "boot"], Path("/o"))
        self.assertEqual(cmd, ["/t/pd", "-p", "boot,vendor_boot", "-o", "/o", "/r/rom.zip"])
        for bad in (["system"], ["boot; calc"], ["../boot"], []):
            with self.assertRaises(ValueError):
                build_extract_command(Path("/t/pd"), Path("/r/rom.zip"), bad, Path("/o"))


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.out = self.tmp / "out"

    def tearDown(self):
        self._t.cleanup()

    def streamer(self, create=(), rc=0, cancelled=False, text="Extracting..."):
        calls = []

        def run(args, on_line=None, cancel_event=None, max_seconds=None):
            calls.append(list(args))
            for name in create:
                (self.out / f"{name}.img").write_bytes(b"IMG")
            if on_line:
                on_line("stdout", text)
            return CommandResult(tuple(args), None if cancelled else rc, "", text, cancelled=cancelled)
        run.calls = calls
        return run

    def test_success(self):
        logs = []
        r = extract_partitions(Path("/t/pd"), Path("/r.zip"), ["boot", "dtbo"], self.out,
                               on_log=lambda l, m: logs.append(m), streamer=self.streamer(["boot", "dtbo"]))
        self.assertTrue(r.success, r.message)
        self.assertEqual(set(r.files), {"boot", "dtbo"})
        self.assertTrue(any("Extracting" in m for m in logs))

    def test_missing_partition_is_reported_and_nothing_is_returned(self):
        r = extract_partitions(Path("/t/pd"), Path("/r.zip"), ["boot", "recovery"], self.out,
                               streamer=self.streamer(["boot"]))
        self.assertFalse(r.success)
        self.assertEqual(r.files, {})
        self.assertIn("recovery", r.message)
        self.assertIn("Nothing was flashed", r.message)

    def test_empty_output_file_counts_as_missing(self):
        def run(args, on_line=None, cancel_event=None, max_seconds=None):
            (self.out / "boot.img").write_bytes(b"")
            return CommandResult(tuple(args), 0)
        self.assertFalse(extract_partitions(Path("/t/pd"), Path("/r.zip"), ["boot"], self.out, streamer=run).success)

    def test_tool_failure_and_cancel(self):
        fail = extract_partitions(Path("/t/pd"), Path("/r.zip"), ["boot"], self.out,
                                  streamer=self.streamer(rc=1, text="error: bad payload"))
        self.assertFalse(fail.success)
        self.assertIn("bad payload", fail.message)
        cancel = extract_partitions(Path("/t/pd"), Path("/r.zip"), ["boot"], self.out,
                                    streamer=self.streamer(cancelled=True))
        self.assertTrue(cancel.cancelled)
        self.assertFalse(cancel.success)

    def test_bad_partition_never_runs_the_tool(self):
        s = self.streamer()
        r = extract_partitions(Path("/t/pd"), Path("/r.zip"), ["system"], self.out, streamer=s)
        self.assertFalse(r.success)
        self.assertEqual(s.calls, [])


class CleanupTests(unittest.TestCase):
    def test_only_deletes_inside_its_own_root(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "extracted"
            run = new_run_dir(root)
            run.mkdir(parents=True)
            (run / "boot.img").write_bytes(b"x")
            outside = Path(t) / "precious"
            outside.mkdir()
            (outside / "file.txt").write_bytes(b"keep")
            self.assertFalse(cleanup_dir(outside, root))
            self.assertFalse(cleanup_dir(root, root))
            self.assertFalse(cleanup_dir(None, root))
            self.assertTrue(outside.exists())
            self.assertTrue(cleanup_dir(run, root))
            self.assertFalse(run.exists())


class DeferredPlanTests(unittest.TestCase):
    def dev(self):
        return DeviceInfo(serial="ABC123", transport=Transport.FASTBOOT, mode=M.FASTBOOT, product="x",
                          scheme=S.AB, active_slot="a")

    def test_plan_without_files_is_valid_in_deferred_mode(self):
        sels = [PartitionSelection("boot", True, None, C.A), PartitionSelection("vbmeta", True, None, C.BOTH),
                PartitionSelection("dtbo", False, None, C.A)]
        plan = build_plan(self.dev(), sels, defer_images=True)
        self.assertFalse(plan.blocked, plan.issues)
        previews = plan.command_previews()
        self.assertEqual(len(previews), 3)
        self.assertIn("flash boot_a", previews[0])
        self.assertIn("extracted from ROM", previews[0])
        self.assertFalse(build_plan(self.dev(), sels).blocked is False)  # normal mode still needs real files

    def test_slot_choice_is_still_required(self):
        plan = build_plan(self.dev(), [PartitionSelection("boot", True, None, None)], defer_images=True)
        self.assertTrue(plan.blocked)

    def test_real_plan_after_extraction(self):
        with tempfile.TemporaryDirectory() as t:
            img = Path(t) / "boot.img"
            img.write_bytes(b"ANDROID!" + bytes(4088))
            plan = build_plan(self.dev(), [PartitionSelection("boot", True, img, C.A)])
            self.assertFalse(plan.blocked, plan.issues)
            self.assertEqual(plan.command_previews(), [f"fastboot -s ABC123 flash boot_a {img}"])


class SettingsPayloadTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as t:
            s = Settings(Path(t) / "s.json")
            self.assertIsNone(s.payload_dumper_path)
            s.payload_dumper_path = "C:\\tools\\payload-dumper-go.exe"
            s.save()
            again = Settings(Path(t) / "s.json")
            again.load()
            self.assertEqual(again.payload_dumper_path, "C:\\tools\\payload-dumper-go.exe")


if __name__ == "__main__":
    unittest.main()
