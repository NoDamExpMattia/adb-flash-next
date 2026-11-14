import unittest

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.parsers import (
    parse_adb_devices,
    parse_fastboot_devices,
    parse_fastboot_var,
    parse_getprop,
    validate_fastboot_var,
    validate_serial,
)


class AdbDevicesTests(unittest.TestCase):
    def test_parses_states_and_ignores_daemon_noise(self):
        text = (
            "* daemon not running; starting now at tcp:5037\n"
            "* daemon started successfully\n"
            "List of devices attached\n"
            "ABC123\tdevice usb:1-1 product:sunfish model:Pixel_4a device:sunfish transport_id:1\n"
            "XYZ789\tunauthorized usb:1-2 transport_id:2\n"
            "192.168.1.5:5555\toffline\n"
            "\n"
        )
        entries = parse_adb_devices(text)
        self.assertEqual([(e.serial, e.state) for e in entries],
                         [("ABC123", "device"), ("XYZ789", "unauthorized"), ("192.168.1.5:5555", "offline")])

    def test_no_header_means_no_devices(self):
        self.assertEqual(parse_adb_devices("error: something broke\nABC device"), [])

    def test_empty_list(self):
        self.assertEqual(parse_adb_devices("List of devices attached\n\n"), [])

    def test_no_permissions_state(self):
        text = "List of devices attached\nABC123 no permissions (user in plugdev group)\n"
        self.assertEqual(parse_adb_devices(text)[0].state, "no permissions")


class FastbootTests(unittest.TestCase):
    def test_devices(self):
        self.assertEqual(parse_fastboot_devices("ABC123\tfastboot\nDEF456\tfastboot\n"), ["ABC123", "DEF456"])

    def test_devices_ignores_waiting_line(self):
        self.assertEqual(parse_fastboot_devices("< waiting for any device >\n"), [])

    def test_var_from_stderr_style(self):
        text = "product: sunfish\nFinished. Total time: 0.002s\n"
        self.assertEqual(parse_fastboot_var(text, "product"), "sunfish")

    def test_var_with_bootloader_prefix(self):
        self.assertEqual(parse_fastboot_var("(bootloader) current-slot: a\n", "current-slot"), "a")

    def test_var_with_colon_in_name(self):
        self.assertEqual(parse_fastboot_var("has-slot:boot: yes\nFinished.\n", "has-slot:boot"), "yes")

    def test_failed_var_is_none(self):
        text = "getvar:slot-count FAILED (remote: 'GetVar Variable Not found')\nfinished. total time: 0.001s\n"
        self.assertIsNone(parse_fastboot_var(text, "slot-count"))

    def test_empty_value_is_none(self):
        self.assertIsNone(parse_fastboot_var("current-slot: \n", "current-slot"))

    def test_similar_names_do_not_collide(self):
        self.assertIsNone(parse_fastboot_var("product-name: x\n", "product"))


class GetpropTests(unittest.TestCase):
    def test_parse(self):
        text = "[ro.product.device]: [sunfish]\n[ro.empty]: []\nnot a prop line\n"
        self.assertEqual(parse_getprop(text), {"ro.product.device": "sunfish", "ro.empty": ""})


class ValidationTests(unittest.TestCase):
    def test_good_serials(self):
        for s in ("ABC123", "0123456789ABCDEF", "192.168.1.5:5555", "emulator-5554"):
            self.assertEqual(validate_serial(s), s)

    def test_bad_serials_rejected(self):
        for s in ("", "a b", "x;rm -rf", "$(whoami)", "a\nb", "-s", "??????????"):
            with self.assertRaises(ValueError, msg=s):
                validate_serial(s)

    def test_var_names(self):
        validate_fastboot_var("has-slot:boot")
        with self.assertRaises(ValueError):
            validate_fastboot_var("product; reboot")


if __name__ == "__main__":
    unittest.main()
