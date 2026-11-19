import struct
import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.config.constants import SUPPORTED_PARTITIONS
from adb_flash_next.core.flash_plan import PartitionSelection, build_plan
from adb_flash_next.core.models import ConnectionMode as M
from adb_flash_next.core.models import DeviceInfo, Transport
from adb_flash_next.core.models import PartitionScheme as S
from adb_flash_next.core.slot_resolver import SlotChoice as C


def device(scheme=S.AB, slot="b", mode=M.FASTBOOT, transport=Transport.FASTBOOT, manufacturer=None):
    return DeviceInfo(serial="ABC123", transport=transport, mode=mode, product="sunfish",
                      scheme=scheme, active_slot=slot, manufacturer=manufacturer)


def boot_bytes(kernel=1000):
    d = bytearray(4096)
    d[0:8] = b"ANDROID!"
    struct.pack_into("<I", d, 8, kernel)
    struct.pack_into("<I", d, 40, 4)
    return bytes(d)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = Path(self._tmp.name)
        self.boot = t / "boot.img"
        self.boot.write_bytes(boot_bytes())
        self.recovery = t / "recovery.img"
        self.recovery.write_bytes(boot_bytes())
        self.vbmeta = t / "vbmeta.img"
        self.vbmeta.write_bytes(b"AVB0" + bytes(500))
        self.dtbo = t / "dtbo.img"
        self.dtbo.write_bytes(bytes.fromhex("d7b7ab1e") + bytes(500))

    def tearDown(self):
        self._tmp.cleanup()

    def row(self, partition, path=None, slot=C.B, enabled=True):
        return PartitionSelection(partition=partition, enabled=enabled, path=path, slot=slot)

    def test_ui_order_of_partitions(self):
        self.assertEqual(SUPPORTED_PARTITIONS,
                         ("boot", "dtbo", "vendor_boot", "recovery", "init_boot", "vbmeta"))

    def test_no_device_blocks(self):
        plan = build_plan(None, [self.row("boot", self.boot)])
        self.assertTrue(plan.blocked)
        self.assertEqual(plan.command_previews(), [])

    def test_example_from_the_user(self):
        sels = [
            self.row("boot", self.boot, C.A),
            self.row("recovery", self.recovery, C.B),
            self.row("vbmeta", self.vbmeta, C.BOTH),
        ]
        plan = build_plan(device(slot="a"), sels)
        self.assertFalse(plan.blocked, plan.issues)
        previews = plan.command_previews()
        self.assertEqual(previews, [
            f"fastboot -s ABC123 flash boot_a {self.boot}",
            f"fastboot -s ABC123 flash recovery_b {self.recovery}",
            f"fastboot -s ABC123 flash vbmeta_b {self.vbmeta}",   # inactive first
            f"fastboot -s ABC123 flash vbmeta_a {self.vbmeta}",
        ])
        self.assertFalse(any("_ab" in p for p in previews))

    def test_images_page_never_adds_erase_or_verity_flags(self):
        plan = build_plan(device(), [self.row("vbmeta", self.vbmeta)])
        self.assertFalse(any(s.kind == "erase" or s.destructive for s in plan.steps))
        self.assertFalse(any("--disable" in c for c in plan.command_previews()))
        self.assertFalse(plan.has_destructive_step)

    def test_enabled_row_without_file_blocks(self):
        plan = build_plan(device(), [self.row("boot", None)])
        self.assertTrue(plan.blocked)
        self.assertTrue(any("no image selected" in e.message for e in plan.errors))

    def test_unticked_rows_are_ignored_even_without_file(self):
        plan = build_plan(device(), [self.row("boot", self.boot), self.row("dtbo", None, enabled=False)])
        self.assertFalse(plan.blocked, plan.issues)
        self.assertEqual(len(plan.steps), 1)

    def test_unticked_row_with_file_is_never_flashed(self):
        plan = build_plan(device(), [self.row("boot", self.boot, enabled=False), self.row("dtbo", self.dtbo)])
        self.assertEqual([s.target_partition for s in plan.steps], ["dtbo_b"])

    def test_ab_requires_slot_choice(self):
        plan = build_plan(device(), [self.row("boot", self.boot, slot=None)])
        self.assertTrue(plan.blocked)
        self.assertTrue(any("choose a slot" in e.message for e in plan.errors))

    def test_a_only_uses_plain_names_and_ignores_slot(self):
        plan = build_plan(device(S.A_ONLY, None), [self.row("boot", self.boot, C.BOTH)])
        self.assertEqual(plan.command_previews(), [f"fastboot -s ABC123 flash boot {self.boot}"])

    def test_header_mismatch_blocks(self):
        self.assertTrue(build_plan(device(), [self.row("boot", self.vbmeta)]).blocked)

    def test_unknown_scheme_blocks_with_a_single_error(self):
        sels = [self.row("boot", self.boot), self.row("dtbo", self.dtbo)]
        plan = build_plan(device(S.UNKNOWN, None), sels)
        self.assertTrue(plan.blocked)
        self.assertEqual(plan.steps, ())
        self.assertEqual(sum("could not be determined" in e.message for e in plan.errors), 1)

    def test_inactive_slot_warning(self):
        plan = build_plan(device(slot="a"), [self.row("boot", self.boot, C.B)])
        self.assertFalse(plan.blocked)
        self.assertTrue(any("active slot" in w.message for w in plan.warnings))

    def test_nothing_ticked_blocks(self):
        self.assertTrue(build_plan(device(), [self.row("boot", self.boot, enabled=False)]).blocked)

    def test_samsung_blocks(self):
        self.assertTrue(build_plan(device(manufacturer="samsung"), [self.row("boot", self.boot)]).blocked)

    def test_not_in_fastboot_blocks_execution(self):
        plan = build_plan(device(mode=M.ANDROID, transport=Transport.ADB), [self.row("boot", self.boot)])
        self.assertTrue(plan.blocked)
        self.assertTrue(any("Fastboot" in e.message for e in plan.errors))

    def test_fastbootd_and_unconfirmed_fastboot_are_allowed(self):
        for mode in (M.FASTBOOTD, M.FASTBOOT_UNCONFIRMED):
            plan = build_plan(device(mode=mode), [self.row("boot", self.boot)])
            self.assertFalse(plan.blocked, (mode, plan.issues))

    def test_summary_lists_files_and_partitions(self):
        plan = build_plan(device(), [self.row("boot", self.boot, C.BOTH)])
        text = "\n".join(plan.summary_lines())
        for expected in ("sunfish", "ABC123", "boot.img -> boot_a", "boot.img -> boot_b"):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
