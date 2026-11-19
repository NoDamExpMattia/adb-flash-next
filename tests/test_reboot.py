import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.models import ConnectionMode as M
from adb_flash_next.core.models import DeviceInfo, Transport
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult
from adb_flash_next.core.reboot import (
    ADB_ACTIONS, FASTBOOT_ACTIONS, availability, build_reboot_command, run_reboot,
)

TOOLS = PlatformTools(Path("/t"), Path("/t/adb"), Path("/t/fastboot"))


def dev(transport, mode, serial="ABC123"):
    return DeviceInfo(serial=serial, transport=transport, mode=mode)


class RebootTests(unittest.TestCase):
    def test_all_requested_actions_exist(self):
        self.assertEqual([a.label for a in ADB_ACTIONS],
                         ["Reboot", "Reboot to bootloader", "Reboot to recovery", "Reboot to fastbootd"])
        self.assertEqual([a.args for a in ADB_ACTIONS],
                         [("reboot",), ("reboot", "bootloader"), ("reboot", "recovery"), ("reboot", "fastboot")])
        self.assertEqual([a.label for a in FASTBOOT_ACTIONS if a.key != "fb_bootloader"],
                         ["fastboot reboot", "fastboot reboot fastboot", "fastboot reboot recovery"])

    def test_availability_by_mode(self):
        android = dev(Transport.ADB, M.ANDROID)
        fastboot = dev(Transport.FASTBOOT, M.FASTBOOT)
        for a in ADB_ACTIONS:
            self.assertTrue(availability(a, android)[0])
            self.assertFalse(availability(a, fastboot)[0])
            self.assertFalse(availability(a, None)[0])
        for a in FASTBOOT_ACTIONS:
            self.assertTrue(availability(a, fastboot)[0])
            self.assertFalse(availability(a, android)[0])

    def test_adb_actions_not_offered_when_unauthorized_or_offline(self):
        for mode in (M.UNAUTHORIZED, M.OFFLINE):
            self.assertFalse(availability(ADB_ACTIONS[0], dev(Transport.ADB, mode))[0])

    def test_adb_actions_allowed_in_recovery_and_sideload(self):
        for mode in (M.RECOVERY, M.SIDELOAD):
            self.assertTrue(availability(ADB_ACTIONS[0], dev(Transport.ADB, mode))[0])

    def test_command_is_bound_to_serial(self):
        cmd = build_reboot_command(TOOLS, "ABC123", ADB_ACTIONS[2])
        self.assertEqual(cmd, ["/t/adb", "-s", "ABC123", "reboot", "recovery"])
        cmd = build_reboot_command(TOOLS, "FB1", FASTBOOT_ACTIONS[2])
        self.assertEqual(cmd, ["/t/fastboot", "-s", "FB1", "reboot", "fastboot"])

    def test_bad_serial_is_refused(self):
        with self.assertRaises(ValueError):
            build_reboot_command(TOOLS, "x; rm -rf /", ADB_ACTIONS[0])

    def test_run_uses_runner_and_checks_mode(self):
        calls = []

        def runner(args, timeout, cancel_event=None):
            calls.append(list(args))
            return CommandResult(tuple(args), 0, stdout="ok")

        ok = run_reboot(TOOLS, dev(Transport.ADB, M.ANDROID), ADB_ACTIONS[0], runner=runner)
        self.assertTrue(ok.ok)
        self.assertEqual(calls, [["/t/adb", "-s", "ABC123", "reboot"]])

        refused = run_reboot(TOOLS, dev(Transport.FASTBOOT, M.FASTBOOT), ADB_ACTIONS[0], runner=runner)
        self.assertFalse(refused.ok)
        self.assertEqual(len(calls), 1)  # nothing was executed

    def test_failed_command_is_reported(self):
        def runner(args, timeout, cancel_event=None):
            return CommandResult(tuple(args), 1, stderr="unknown reboot target recovery")

        r = run_reboot(TOOLS, dev(Transport.FASTBOOT, M.FASTBOOT), FASTBOOT_ACTIONS[3], runner=runner)
        self.assertFalse(r.ok)
        self.assertIn("unknown reboot target", r.failure_reason())


if __name__ == "__main__":
    unittest.main()
