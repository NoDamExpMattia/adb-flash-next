import unittest

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.progress import Phase, overall_percent


class ProgressTests(unittest.TestCase):
    def test_idle_is_zero(self):
        self.assertEqual(overall_percent(Phase.IDLE), 0.0)

    def test_only_verified_reaches_100(self):
        for include_flash in (False, True):
            for phase in Phase:
                for fraction in (0.0, 0.5, 1.0, 5.0, -3.0):
                    value = overall_percent(phase, fraction, include_flash)
                    if phase is Phase.VERIFIED:
                        self.assertEqual(value, 100.0)
                    else:
                        self.assertLessEqual(value, 99.0, (phase, fraction, include_flash))

    def test_finishing_holds_at_99(self):
        self.assertEqual(overall_percent(Phase.FINISHING), 99.0)

    def test_sideload_only_mapping(self):
        self.assertEqual(overall_percent(Phase.SIDELOAD, 0.0), 5.0)
        self.assertEqual(overall_percent(Phase.SIDELOAD, 1.0), 90.0)
        self.assertAlmostEqual(overall_percent(Phase.SIDELOAD, 0.5), 47.5)

    def test_sideload_after_flash_mapping(self):
        self.assertEqual(overall_percent(Phase.SIDELOAD, 0.0, include_flash=True), 35.0)
        self.assertEqual(overall_percent(Phase.SIDELOAD, 1.0, include_flash=True), 90.0)
        self.assertEqual(overall_percent(Phase.FLASH, 1.0, include_flash=True), 35.0)

    def test_monotonic_within_a_run(self):
        points = [overall_percent(Phase.PREPARE, 1.0)]
        points += [overall_percent(Phase.SIDELOAD, f / 10) for f in range(11)]
        points.append(overall_percent(Phase.FINISHING))
        self.assertEqual(points, sorted(points))


if __name__ == "__main__":
    unittest.main()
