import struct
import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.image_validator import (
    LEVEL_ERROR, LEVEL_OK, LEVEL_WARNING, format_size, validate_image,
)


def boot_image(header_version=4, kernel_size=1000, ramdisk_size=500) -> bytes:
    data = bytearray(4096)
    data[0:8] = b"ANDROID!"
    struct.pack_into("<I", data, 8, kernel_size)
    if header_version >= 3:
        struct.pack_into("<I", data, 12, ramdisk_size)
    struct.pack_into("<I", data, 40, header_version)
    return bytes(data)


def make(tmp, name, data):
    p = Path(tmp) / name
    p.write_bytes(data)
    return p


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_boot_ok(self):
        r = validate_image(make(self.tmp, "boot.img", boot_image()), "boot")
        self.assertEqual(r.level, LEVEL_OK)
        self.assertIn("does not prove", r.message)

    def test_filename_is_not_trusted(self):
        # A file NAMED boot.img that really is a vendor_boot image must be rejected for boot.
        p = make(self.tmp, "boot.img", b"VNDRBOOT" + struct.pack("<I", 4) + bytes(4000))
        self.assertEqual(validate_image(p, "boot").level, LEVEL_ERROR)
        self.assertEqual(validate_image(p, "vendor_boot").level, LEVEL_OK)

    def test_vbmeta_and_dtbo(self):
        self.assertEqual(validate_image(make(self.tmp, "a.img", b"AVB0" + bytes(500)), "vbmeta").level, LEVEL_OK)
        self.assertEqual(validate_image(make(self.tmp, "b.img", bytes.fromhex("d7b7ab1e") + bytes(500)), "dtbo").level, LEVEL_OK)
        self.assertEqual(validate_image(make(self.tmp, "c.img", b"AVB0" + bytes(500)), "dtbo").level, LEVEL_ERROR)

    def test_init_boot_hints(self):
        ramdisk_only = make(self.tmp, "i.img", boot_image(4, kernel_size=0))
        self.assertEqual(validate_image(ramdisk_only, "init_boot").level, LEVEL_OK)
        self.assertEqual(validate_image(ramdisk_only, "boot").level, LEVEL_WARNING)
        with_kernel = make(self.tmp, "k.img", boot_image(4, kernel_size=5000))
        self.assertEqual(validate_image(with_kernel, "init_boot").level, LEVEL_WARNING)

    def test_unrecognised_header_warns(self):
        r = validate_image(make(self.tmp, "x.img", b"\x00" * 200), "boot")
        self.assertEqual(r.level, LEVEL_WARNING)
        self.assertIn("cannot be validated", r.message)

    def test_sparse_warns(self):
        r = validate_image(make(self.tmp, "s.img", bytes.fromhex("3aff26ed") + bytes(100)), "boot")
        self.assertEqual(r.level, LEVEL_WARNING)

    def test_empty_and_missing_are_errors(self):
        self.assertEqual(validate_image(make(self.tmp, "e.img", b""), "boot").level, LEVEL_ERROR)
        self.assertEqual(validate_image(Path(self.tmp) / "nope.img", "boot").level, LEVEL_ERROR)
        self.assertEqual(validate_image(Path(self.tmp), "boot").level, LEVEL_ERROR)

    def test_wrong_extension_warns(self):
        r = validate_image(make(self.tmp, "boot.bin", boot_image()), "boot")
        self.assertEqual(r.level, LEVEL_WARNING)

    def test_no_partition_chosen(self):
        r = validate_image(make(self.tmp, "boot.img", boot_image()), None)
        self.assertIn("Choose a destination", r.message)

    def test_format_size(self):
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(2048), "2.0 KiB")
        self.assertEqual(format_size(64 * 1024 * 1024), "64.0 MiB")


if __name__ == "__main__":
    unittest.main()
