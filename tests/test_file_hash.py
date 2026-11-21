import hashlib
import tempfile
import threading
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.config import constants
from adb_flash_next.core.file_hash import sha256_of_file


class HashTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_known_vectors(self):
        abc = self.tmp / "abc.img"
        abc.write_bytes(b"abc")
        self.assertEqual(sha256_of_file(abc), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        empty = self.tmp / "empty.img"
        empty.write_bytes(b"")
        self.assertEqual(sha256_of_file(empty), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_large_file_spanning_several_chunks(self):
        big = self.tmp / "big.img"
        data = bytes(range(256)) * (9 * 1024 * 4)  # about 9 MiB: more than two 4 MiB chunks
        big.write_bytes(data)
        self.assertEqual(sha256_of_file(big), hashlib.sha256(data).hexdigest())

    def test_result_is_lowercase_64_hex(self):
        f = self.tmp / "x.img"
        f.write_bytes(b"x")
        digest = sha256_of_file(f)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, digest.lower())

    def test_cancel(self):
        f = self.tmp / "x.img"
        f.write_bytes(b"x" * 100)
        ev = threading.Event()
        ev.set()
        with self.assertRaises(InterruptedError):
            sha256_of_file(f, ev)

    def test_missing_file_and_folder(self):
        with self.assertRaises(OSError):
            sha256_of_file(self.tmp / "nope.img")
        with self.assertRaises(OSError):
            sha256_of_file(self.tmp)


class AboutConstantsTests(unittest.TestCase):
    def test_author(self):
        self.assertEqual(constants.AUTHOR_HANDLE, "NoDamExpMattia")
        self.assertEqual(constants.AUTHOR_URL, "https://github.com/NoDamExpMattia")


if __name__ == "__main__":
    unittest.main()
