import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.models import ConnectionMode as M
from adb_flash_next.core.models import DeviceInfo, Transport
from adb_flash_next.core.models import PartitionScheme as S
from adb_flash_next.core.utilities import ACTIONS, build_utility_plan, fastboot_readiness


def fb(scheme=S.AB, slot="a", manufacturer=None, mode=M.FASTBOOT):
    return DeviceInfo(serial="ABC123", transport=Transport.FASTBOOT, mode=mode, product="x",
                      scheme=scheme, active_slot=slot, manufacturer=manufacturer)


def android():
    return DeviceInfo(serial="ABC123", transport=Transport.ADB, mode=M.ANDROID)


class UtilityTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.vbmeta = Path(self._t.name) / "vbmeta.img"
        self.vbmeta.write_bytes(b"AVB0" + bytes(500))

    def tearDown(self):
        self._t.cleanup()

    def test_the_four_utilities_exist(self):
        self.assertEqual(set(ACTIONS), {"erase_userdata", "erase_metadata", "erase_frp", "patch_vbmeta"})

    def test_erase_commands_are_exactly_what_was_asked(self):
        expected = {
            "erase_userdata": "fastboot -s ABC123 erase userdata",
            "erase_metadata": "fastboot -s ABC123 erase metadata",
            "erase_frp": "fastboot -s ABC123 erase frp",
        }
        for key, command in expected.items():
            plan = build_utility_plan(fb(), key)
            self.assertFalse(plan.blocked, (key, plan.issues))
            self.assertEqual(plan.command_previews(), [command])
            self.assertTrue(plan.has_destructive_step)
            self.assertTrue(plan.warnings)

    def test_patch_vbmeta_command(self):
        plan = build_utility_plan(fb(), "patch_vbmeta", self.vbmeta)
        self.assertFalse(plan.blocked, plan.issues)
        self.assertEqual(
            plan.command_previews(),
            [f"fastboot -s ABC123 --disable-verity --disable-verification flash vbmeta {self.vbmeta}"],
        )
        self.assertFalse(plan.has_destructive_step)

    def test_patch_vbmeta_warns_about_current_slot_on_ab(self):
        plan = build_utility_plan(fb(S.AB, "b"), "patch_vbmeta", self.vbmeta)
        self.assertTrue(any("CURRENT slot (B)" in w.message for w in plan.warnings))
        a_only = build_utility_plan(fb(S.A_ONLY, None), "patch_vbmeta", self.vbmeta)
        self.assertFalse(any("CURRENT slot" in w.message for w in a_only.warnings))

    def test_patch_vbmeta_needs_a_valid_vbmeta(self):
        self.assertTrue(build_utility_plan(fb(), "patch_vbmeta", None).blocked)
        bad = Path(self._t.name) / "boot.img"
        bad.write_bytes(b"ANDROID!" + bytes(500))
        plan = build_utility_plan(fb(), "patch_vbmeta", bad)
        self.assertTrue(plan.blocked)
        self.assertEqual(plan.steps, ())
        self.assertTrue(build_utility_plan(fb(), "patch_vbmeta", Path(self._t.name) / "none.img").blocked)

    def test_everything_needs_fastboot_mode(self):
        for key in ACTIONS:
            plan = build_utility_plan(android(), key, self.vbmeta)
            self.assertTrue(plan.blocked, key)
            self.assertTrue(any("Fastboot" in e.message for e in plan.errors))

    def test_no_device_and_samsung_block(self):
        self.assertTrue(build_utility_plan(None, "erase_frp").blocked)
        self.assertTrue(build_utility_plan(fb(manufacturer="samsung"), "erase_frp").blocked)

    def test_fastbootd_is_accepted(self):
        self.assertFalse(build_utility_plan(fb(mode=M.FASTBOOTD), "erase_userdata").blocked)

    def test_unknown_key(self):
        with self.assertRaises(ValueError):
            build_utility_plan(fb(), "format_everything")

    def test_readiness(self):
        self.assertTrue(fastboot_readiness(fb())[0])
        self.assertFalse(fastboot_readiness(android())[0])
        self.assertFalse(fastboot_readiness(None)[0])


if __name__ == "__main__":
    unittest.main()
