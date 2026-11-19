import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.device_manager import DeviceManager
from adb_flash_next.core.models import ConnectionMode as M
from adb_flash_next.core.models import PartitionScheme as S
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult

ADB = "/tools/adb"
FB = "/tools/fastboot"
TOOLS = PlatformTools(Path("/tools"), Path(ADB), Path(FB))

PIXEL_PROPS = (
    "[ro.product.device]: [sunfish]\n[ro.product.model]: [Pixel 4a]\n"
    "[ro.product.manufacturer]: [Google]\n[ro.board.platform]: [sm7150]\n[ro.hardware]: [sunfish]\n"
    "[ro.build.version.release]: [14]\n[ro.build.version.sdk]: [34]\n"
    "[ro.build.ab_update]: [true]\n[ro.boot.slot_suffix]: [_a]\n[sys.boot_completed]: [1]\n"
)


class FakeRunner:
    """Maps argument lists (without the executable) to canned results and records calls."""

    def __init__(self):
        self.responses: dict[tuple, CommandResult] = {}
        self.calls: list[tuple] = []

    def set(self, args, stdout="", stderr="", rc=0):
        self.responses[tuple(args)] = CommandResult(args=tuple(args), returncode=rc, stdout=stdout, stderr=stderr)

    def __call__(self, args, timeout, cancel_event=None):
        args = tuple(args)
        self.calls.append(args)
        key = args[1:]
        if key in self.responses:
            r = self.responses[key]
            return CommandResult(args=args, returncode=r.returncode, stdout=r.stdout, stderr=r.stderr)
        # Unknown Fastboot variable: exits 0 with a FAILED line, like many bootloaders.
        if key[:3] == ("-s", key[1], "getvar") if len(key) > 1 else False:
            return CommandResult(args=args, returncode=0, stderr=f"getvar:{key[3]} FAILED (remote: 'not found')\n")
        return CommandResult(args=args, returncode=1, stderr="unexpected command in test")


def fb_var(runner, serial, name, value):
    runner.set(("-s", serial, "getvar", name), stderr=f"{name}: {value}\nFinished. Total time: 0.001s\n")


class DeviceManagerTests(unittest.TestCase):
    def make(self):
        runner = FakeRunner()
        logs = []
        manager = DeviceManager(TOOLS, log=lambda lvl, msg: logs.append((lvl, msg)), runner=runner)
        return manager, runner, logs

    def test_no_devices(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\n\n")
        r.set(("devices",), stdout="")
        result = manager.poll()
        self.assertEqual(result.devices, ())
        self.assertEqual(result.warnings, ())

    def test_android_device_over_adb(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nABC123\tdevice usb:1\n")
        r.set(("devices",), stdout="")
        r.set(("-s", "ABC123", "shell", "getprop"), stdout=PIXEL_PROPS)
        (d,) = manager.poll().devices
        self.assertIs(d.mode, M.ANDROID)
        self.assertEqual(d.product, "sunfish")
        self.assertEqual(d.product_text(), "sunfish (Pixel 4a)")
        self.assertEqual(d.android_version, "Android 14 (API 34)")
        self.assertIs(d.scheme, S.AB)
        self.assertEqual(d.active_slot, "a")
        self.assertTrue(d.boot_completed)
        self.assertEqual(d.fastboot_status_text(), "Not in Fastboot mode")
        self.assertFalse(d.is_excluded)

    def test_fastboot_bootloader_device(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\n\n")
        r.set(("devices",), stdout="FB001\tfastboot\n")
        for name, val in (("product", "sunfish"), ("is-userspace", "no"), ("current-slot", "b"),
                          ("slot-count", "2"), ("has-slot:boot", "yes"), ("unlocked", "yes")):
            fb_var(r, "FB001", name, val)
        (d,) = manager.poll().devices
        self.assertIs(d.mode, M.FASTBOOT)
        self.assertEqual(d.active_slot, "b")
        self.assertIs(d.scheme, S.AB)
        self.assertEqual(d.fastboot_status_text(), "Fastboot (bootloader)")
        self.assertEqual(d.warnings, [])

    def test_fastbootd_and_locked_bootloader(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\n")
        r.set(("devices",), stdout="FB001\tfastboot\n")
        fb_var(r, "FB001", "product", "x")
        fb_var(r, "FB001", "is-userspace", "yes")
        fb_var(r, "FB001", "unlocked", "no")
        (d,) = manager.poll().devices
        self.assertIs(d.mode, M.FASTBOOTD)
        self.assertTrue(any("LOCKED" in w for w in d.warnings))

    def test_missing_variables_are_never_invented(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\n")
        r.set(("devices",), stdout="FB001\tfastboot\n")
        fb_var(r, "FB001", "product", "oddphone")  # everything else "not found"
        (d,) = manager.poll().devices
        self.assertIs(d.mode, M.FASTBOOT_UNCONFIRMED)
        self.assertIs(d.scheme, S.UNKNOWN)
        self.assertIsNone(d.active_slot)
        disp = d.to_display_dict()
        self.assertEqual(disp["Active slot"], "Not available")
        self.assertEqual(disp["Android version"], "Not available")
        self.assertEqual(disp["Platform / SoC"], "Not available")

    def test_sideload_mode_does_not_query_properties(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nSIDE1\tsideload\n")
        r.set(("devices",), stdout="")
        (d,) = manager.poll().devices
        self.assertIs(d.mode, M.SIDELOAD)
        self.assertFalse(any("getprop" in c for c in r.calls))

    def test_unauthorized_device_is_reported_not_queried(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nU1\tunauthorized\n")
        r.set(("devices",), stdout="")
        (d,) = manager.poll().devices
        self.assertIs(d.mode, M.UNAUTHORIZED)
        self.assertTrue(d.warnings)
        self.assertFalse(any("getprop" in c for c in r.calls))

    def test_samsung_is_flagged(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nS1\tdevice\n")
        r.set(("devices",), stdout="")
        r.set(("-s", "S1", "shell", "getprop"), stdout="[ro.product.manufacturer]: [samsung]\n[ro.product.device]: [a52]\n")
        (d,) = manager.poll().devices
        self.assertTrue(d.is_excluded)
        self.assertTrue(any("Samsung" in w for w in d.warnings))

    def test_every_device_command_has_serial_flag(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nABC123\tdevice\n")
        r.set(("devices",), stdout="FB001\tfastboot\n")
        r.set(("-s", "ABC123", "shell", "getprop"), stdout=PIXEL_PROPS)
        fb_var(r, "FB001", "product", "x")
        manager.poll()
        for call in r.calls:
            if call[1:] in (("devices", "-l"), ("devices",)):
                continue
            self.assertEqual(call[1], "-s", call)
            self.assertIn(call[2], ("ABC123", "FB001"))

    def test_details_are_cached_between_polls(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nABC123\tdevice\n")
        r.set(("devices",), stdout="")
        r.set(("-s", "ABC123", "shell", "getprop"), stdout=PIXEL_PROPS)
        manager.poll()
        manager.poll()
        self.assertEqual(sum(1 for c in r.calls if "getprop" in c), 1)
        manager.clear_cache()
        manager.poll()
        self.assertEqual(sum(1 for c in r.calls if "getprop" in c), 2)

    def test_failed_read_is_retried_then_given_up(self):
        manager, r, logs = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nABC123\tdevice\n")
        r.set(("devices",), stdout="")
        r.set(("-s", "ABC123", "shell", "getprop"), stderr="error: closed", rc=1)
        for _ in range(5):
            (d,) = manager.poll().devices
        self.assertFalse(d.read_ok)
        self.assertEqual(sum(1 for c in r.calls if "getprop" in c), 3)
        self.assertTrue(any("Giving up" in m for _, m in logs))

    def test_adb_list_failure_becomes_warning(self):
        manager, r, logs = self.make()
        r.set(("devices", "-l"), stderr="cannot connect to daemon", rc=1)
        r.set(("devices",), stdout="")
        result = manager.poll()
        self.assertTrue(result.warnings)
        manager.poll()
        self.assertEqual(sum(1 for lvl, m in logs if "ADB device list failed" in m), 1)  # logged once

    def test_disconnected_device_disappears(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nABC123\tdevice\n")
        r.set(("devices",), stdout="")
        r.set(("-s", "ABC123", "shell", "getprop"), stdout=PIXEL_PROPS)
        self.assertEqual(len(manager.poll().devices), 1)
        r.set(("devices", "-l"), stdout="List of devices attached\n")
        self.assertEqual(len(manager.poll().devices), 0)

    def test_two_devices_are_both_listed(self):
        manager, r, _ = self.make()
        r.set(("devices", "-l"), stdout="List of devices attached\nA1\tdevice\nB2\tdevice\n")
        r.set(("devices",), stdout="")
        r.set(("-s", "A1", "shell", "getprop"), stdout=PIXEL_PROPS)
        r.set(("-s", "B2", "shell", "getprop"), stdout=PIXEL_PROPS)
        result = manager.poll()
        self.assertEqual(sorted(d.serial for d in result.devices), ["A1", "B2"])


if __name__ == "__main__":
    unittest.main()
