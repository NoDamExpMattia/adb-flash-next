import unittest

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.models import PartitionScheme as S
from adb_flash_next.core.slot_resolver import SlotChoice as C
from adb_flash_next.core.slot_resolver import SlotResolutionError, resolve_targets


class ResolverTests(unittest.TestCase):
    def test_a_only_has_no_suffix_whatever_the_choice(self):
        for choice in (None, C.A, C.B, C.BOTH):
            self.assertEqual(resolve_targets("boot", S.A_ONLY, choice, None), ["boot"])

    def test_ab_single_slots(self):
        self.assertEqual(resolve_targets("boot", S.AB, C.A, "b"), ["boot_a"])
        self.assertEqual(resolve_targets("recovery", S.AB, C.B, "a"), ["recovery_b"])

    def test_ab_both_is_two_separate_partitions_inactive_first(self):
        self.assertEqual(resolve_targets("vbmeta", S.AB, C.BOTH, "b"), ["vbmeta_a", "vbmeta_b"])
        self.assertEqual(resolve_targets("vbmeta", S.AB, C.BOTH, "a"), ["vbmeta_b", "vbmeta_a"])

    def test_ab_both_with_unknown_active_slot(self):
        self.assertEqual(resolve_targets("dtbo", S.AB, C.BOTH, None), ["dtbo_a", "dtbo_b"])

    def test_ab_requires_a_slot_choice(self):
        with self.assertRaises(SlotResolutionError):
            resolve_targets("boot", S.AB, None, "a")

    def test_unknown_scheme_stops(self):
        for choice in (None, C.A, C.B, C.BOTH):
            with self.assertRaises(SlotResolutionError):
                resolve_targets("boot", S.UNKNOWN, choice, "a")

    def test_unsupported_partition(self):
        with self.assertRaises(SlotResolutionError):
            resolve_targets("system", S.AB, C.BOTH, "a")

    def test_never_generates_ab_suffix(self):
        for scheme in (S.AB, S.A_ONLY):
            for choice in (None, C.A, C.B, C.BOTH):
                for slot in ("a", "b", None):
                    try:
                        names = resolve_targets("boot", scheme, choice, slot)
                    except SlotResolutionError:
                        continue
                    self.assertTrue(all(not n.endswith("_ab") for n in names))

    def test_slot_choice_values(self):
        self.assertEqual({c.value for c in C}, {"a", "b", "ab"})


if __name__ == "__main__":
    unittest.main()
