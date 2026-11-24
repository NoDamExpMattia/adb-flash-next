import random
import threading
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.auto_flash import (
    STEP_TITLES, AutoStage, BootState, check_boot_completed, choose_sideload_serial, step_states, wait_for_boot,
)
from adb_flash_next.core.confetti_physics import make_particles, step_particles
from adb_flash_next.core.parsers import AdbListEntry
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult
from adb_flash_next.core.progress import Phase, overall_percent
from adb_flash_next.core.recovery_guide import AUTO_FLASH_STEPS

TOOLS = PlatformTools(Path("/t"), Path("/t/adb"), Path("/t/fastboot"))


def E(serial, state):
    return AdbListEntry(serial, state)


class StageTests(unittest.TestCase):
    def test_idle_and_done(self):
        self.assertEqual(step_states(AutoStage.IDLE), ["pending"] * 5)
        self.assertEqual(step_states(AutoStage.DONE), ["done"] * 5)

    def test_active_and_failed_step(self):
        self.assertEqual(step_states(AutoStage.FLASHING), ["done", "active", "pending", "pending", "pending"])
        self.assertEqual(step_states(AutoStage.CHECKING, failed=True), ["failed"] + ["pending"] * 4)
        self.assertEqual(step_states(AutoStage.BOOT), ["done"] * 4 + ["active"])

    def test_every_stage_has_one_state_per_step(self):
        for stage in AutoStage:
            for failed in (False, True):
                self.assertEqual(len(step_states(stage, failed)), len(STEP_TITLES))


class ProgressRulesTests(unittest.TestCase):
    def test_the_workflow_never_reaches_100_before_android_booted(self):
        for fraction in (0.0, 0.5, 1.0):
            for phase in (Phase.PREPARE, Phase.FLASH, Phase.SIDELOAD, Phase.FINISHING):
                self.assertLess(overall_percent(phase, fraction, include_flash=True), 100)
        self.assertEqual(overall_percent(Phase.FINISHING, 1.0, include_flash=True), 99)
        self.assertEqual(overall_percent(Phase.VERIFIED, 1.0, include_flash=True), 100)


class SerialChoiceTests(unittest.TestCase):
    def test_same_serial_in_sideload_is_sent_without_asking(self):
        c = choose_sideload_serial([E("A1", "sideload")], "A1")
        self.assertEqual((c.serial, c.needs_confirmation), ("A1", False))

    def test_same_serial_but_not_in_sideload_sends_nothing(self):
        for state in ("recovery", "device", "unauthorized", "offline"):
            c = choose_sideload_serial([E("A1", state)], "A1")
            self.assertIsNone(c.serial)
            self.assertIn("Nothing was sent", c.message)
            self.assertIn(state, c.message)

    def test_other_serial_needs_confirmation_only_when_it_is_the_only_device(self):
        c = choose_sideload_serial([E("B2", "sideload")], "A1")
        self.assertEqual((c.serial, c.needs_confirmation), ("B2", True))

    def test_never_guess_with_several_devices(self):
        self.assertIsNone(choose_sideload_serial([E("B2", "sideload"), E("C3", "device")], "A1").serial)
        self.assertIsNone(choose_sideload_serial([E("B2", "sideload"), E("C3", "sideload")], "A1").serial)

    def test_other_single_device_not_in_sideload(self):
        self.assertIsNone(choose_sideload_serial([E("B2", "device")], "A1").serial)

    def test_no_device(self):
        c = choose_sideload_serial([], "A1")
        self.assertIsNone(c.serial)
        self.assertIn("No device", c.message)

    def test_matching_serial_wins_even_with_another_device_present(self):
        c = choose_sideload_serial([E("B2", "device"), E("A1", "sideload")], "A1")
        self.assertEqual(c.serial, "A1")


class FakeAdb:
    def __init__(self, script):
        self.script = list(script)  # list of (adb devices stdout, getprop value or None)
        self.calls = []

    def __call__(self, args, timeout, cancel_event=None):
        args = tuple(args)
        self.calls.append(args)
        if args[1:] == ("devices", "-l"):
            text = self.script[0][0] if len(self.script) == 1 else self.script[0][0]
            return CommandResult(args, 0, stdout="List of devices attached\n" + text)
        if args[1:5] == ("-s", "A1", "shell", "getprop"):
            value = self.script[0][1]
            if len(self.script) > 1:
                self.script.pop(0)
            if value is None:
                return CommandResult(args, 1, stderr="error: closed")
            return CommandResult(args, 0, stdout=value + "\n")
        return CommandResult(args, 1, stderr="unexpected")

    def advance(self):
        if len(self.script) > 1:
            self.script.pop(0)


class BootCheckTests(unittest.TestCase):
    def check(self, devices, prop=None):
        return check_boot_completed(TOOLS, "A1", runner=FakeAdb([(devices, prop)]))

    def test_states(self):
        self.assertEqual(self.check("")[0], BootState.WAITING)
        self.assertEqual(self.check("A1\toffline\n")[0], BootState.WAITING)
        for state in ("sideload", "recovery", "rescue"):
            self.assertEqual(self.check(f"A1\t{state}\n")[0], BootState.RECOVERY)
        self.assertEqual(self.check("A1\tunauthorized\n")[0], BootState.UNAUTHORIZED)
        self.assertEqual(self.check("A1\tdevice\n", "")[0], BootState.BOOTING)
        self.assertEqual(self.check("A1\tdevice\n", "0")[0], BootState.BOOTING)
        self.assertEqual(self.check("A1\tdevice\n", "1")[0], BootState.BOOTED)

    def test_other_device_is_not_mistaken_for_ours(self):
        self.assertEqual(self.check("B2\tdevice\n", "1")[0], BootState.WAITING)

    def test_only_reads(self):
        runner = FakeAdb([("A1\tdevice\n", "1")])
        check_boot_completed(TOOLS, "A1", runner=runner)
        for call in runner.calls:
            self.assertIn(call[1:], [("devices", "-l"), ("-s", "A1", "shell", "getprop", "sys.boot_completed")])

    def test_command_failure_is_waiting_not_booted(self):
        state, message = self.check("A1\tdevice\n", None)
        self.assertEqual(state, BootState.WAITING)
        self.assertNotEqual(state, BootState.BOOTED)

    def test_adb_list_failure_is_an_error(self):
        def broken(args, timeout, cancel_event=None):
            return CommandResult(tuple(args), 1, stderr="cannot connect to daemon")
        self.assertEqual(check_boot_completed(TOOLS, "A1", runner=broken)[0], BootState.ERROR)


class WaitForBootTests(unittest.TestCase):
    def run_wait(self, sequence, timeout=100.0, cancel=None, on_state=None):
        runner = FakeAdb(sequence)
        times = iter(range(0, 100000, 5))   # every clock() call advances 5 "seconds"

        def sleep(_s):
            runner.advance()

        return wait_for_boot(TOOLS, "A1", on_state=on_state, cancel_event=cancel, timeout_seconds=timeout,
                             runner=runner, sleep=sleep, clock=lambda: float(next(times)))

    def test_waits_then_reports_booted_only_at_the_end(self):
        seen = []
        result = self.run_wait(
            [("", None), ("A1\tsideload\n", None), ("A1\tdevice\n", "0"), ("A1\tdevice\n", "1")],
            on_state=lambda s, m: seen.append(s),
        )
        self.assertTrue(result.booted)
        self.assertEqual(seen, [BootState.WAITING, BootState.RECOVERY, BootState.BOOTING, BootState.BOOTED])

    def test_never_booted_times_out_without_claiming_success(self):
        result = self.run_wait([("A1\tdevice\n", "0")], timeout=30.0)
        self.assertFalse(result.booted)
        self.assertTrue(result.timed_out)
        self.assertIn("Check again", result.message)

    def test_unauthorized_stops_immediately_and_explains(self):
        result = self.run_wait([("A1\tunauthorized\n", None)])
        self.assertFalse(result.booted)
        self.assertEqual(result.state, BootState.UNAUTHORIZED)
        self.assertIn("authorized", result.message)

    def test_cancel(self):
        ev = threading.Event()
        ev.set()
        result = self.run_wait([("", None)], cancel=ev)
        self.assertTrue(result.cancelled)
        self.assertFalse(result.booted)


class GuideTests(unittest.TestCase):
    def test_auto_flash_guide_keeps_format_data_manual(self):
        self.assertEqual(len(AUTO_FLASH_STEPS), 4)
        format_step = next(s for s in AUTO_FLASH_STEPS if "Format data" in s.title)
        self.assertTrue(format_step.warning)
        text = " ".join(format_step.bullets)
        self.assertIn("never formats data", text)
        self.assertIn("ERASES EVERYTHING", text)
        self.assertIn("Sideload", " ".join(AUTO_FLASH_STEPS[3].bullets))


class ConfettiTests(unittest.TestCase):
    def test_particles_start_above_the_view_and_fall(self):
        rng = random.Random(1)
        particles = make_particles(800, 600, 120, 5, rng)
        self.assertEqual(len(particles), 120)
        self.assertTrue(all(0 <= p.x <= 800 and p.y < 0 and 0 <= p.color_index < 5 for p in particles))
        before = [p.y for p in particles]
        for _ in range(60):
            step_particles(particles, 0.016)
        self.assertTrue(all(p.y > b for p, b in zip(particles, before)))
        self.assertTrue(all(p.vy <= 520.0 and 0 <= p.rotation < 360 for p in particles))

    def test_zero_sizes_do_not_crash(self):
        self.assertEqual(make_particles(0, 0, 0, 0, random.Random(0)), [])
        self.assertEqual(len(make_particles(0, 0, 3, 0, random.Random(0))), 3)


if __name__ == "__main__":
    unittest.main()


class ExtractingStageTests(unittest.TestCase):
    def test_extracting_is_part_of_step_two(self):
        self.assertEqual(step_states(AutoStage.EXTRACTING), ["done", "active", "pending", "pending", "pending"])
        self.assertEqual(step_states(AutoStage.EXTRACTING, failed=True)[1], "failed")
