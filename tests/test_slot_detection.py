import unittest

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.models import PartitionScheme as S
from adb_flash_next.core.slot_detection import (
    decide_scheme,
    normalize_slot,
    votes_from_adb,
    votes_from_fastboot,
)


class SlotTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_slot("_a"), "a")
        self.assertEqual(normalize_slot("B"), "b")
        self.assertIsNone(normalize_slot("c"))
        self.assertIsNone(normalize_slot(""))
        self.assertIsNone(normalize_slot(None))

    def test_ab_from_fastboot(self):
        scheme, ev = decide_scheme(votes_from_fastboot("2", "yes", "a"))
        self.assertIs(scheme, S.AB)
        self.assertIn("slot-count=2", ev)

    def test_a_only_from_fastboot(self):
        scheme, _ = decide_scheme(votes_from_fastboot("0", "no", None))
        self.assertIs(scheme, S.A_ONLY)

    def test_nothing_reported_is_unknown(self):
        scheme, ev = decide_scheme(votes_from_fastboot(None, None, None))
        self.assertIs(scheme, S.UNKNOWN)
        self.assertIn("no slot information", ev)

    def test_conflict_is_unknown(self):
        scheme, ev = decide_scheme(votes_from_fastboot("2", "no", None))
        self.assertIs(scheme, S.UNKNOWN)
        self.assertIn("conflicting", ev)

    def test_slot_count_one_is_not_guessed(self):
        scheme, _ = decide_scheme(votes_from_fastboot("1", None, None))
        self.assertIs(scheme, S.UNKNOWN)

    def test_garbage_slot_count_ignored(self):
        scheme, _ = decide_scheme(votes_from_fastboot("abc", None, None))
        self.assertIs(scheme, S.UNKNOWN)

    def test_adb_ab(self):
        scheme, _ = decide_scheme(votes_from_adb({"ro.build.ab_update": "true", "ro.boot.slot_suffix": "_b"}))
        self.assertIs(scheme, S.AB)

    def test_adb_no_properties_is_unknown_not_a_only(self):
        scheme, _ = decide_scheme(votes_from_adb({}))
        self.assertIs(scheme, S.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
