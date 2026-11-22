import tempfile
import threading
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from adb_flash_next.core.fastboot_executor import (
    explain_failure, parse_size, preflight, run_steps, step_failed,
)
from adb_flash_next.core.flash_plan import PlannedStep
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult

TOOLS = PlatformTools(Path("/t"), Path("/t/adb"), Path("/t/fastboot"))


class ParseSizeTests(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(parse_size("0x4000000"), 0x4000000)
        self.assertEqual(parse_size(" 67108864 "), 67108864)
        self.assertIsNone(parse_size("abc"))
        self.assertIsNone(parse_size(""))
        self.assertIsNone(parse_size(None))
        self.assertIsNone(parse_size("0xZZ"))


class FakeRunner:
    def __init__(self):
        self.responses = {}
        self.calls = []

    def set(self, args, stdout="", stderr="", rc=0):
        self.responses[tuple(args)] = (rc, stdout, stderr)

    def __call__(self, args, timeout, cancel_event=None):
        args = tuple(args)
        self.calls.append(args)
        if args[1:] in self.responses:
            rc, out, err = self.responses[args[1:]]
            return CommandResult(args, rc, out, err)
        return CommandResult(args, 0, "", f"getvar:{args[-1]} FAILED (remote: 'not found')\n")


def var(runner, name, value, serial="ABC123"):
    runner.set(("-s", serial, "getvar", name), stderr=f"{name}: {value}\nFinished. Total time: 0.001s\n")


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.img = Path(self._t.name) / "boot.img"
        self.img.write_bytes(b"x" * 1000)
        self.flash = PlannedStep("flash", "Flash boot", ("flash", "boot_a", str(self.img)), "boot_a", image=self.img)
        self.erase = PlannedStep("erase", "Erase", ("erase", "userdata"), "userdata", destructive=True)
        self.r = FakeRunner()
        self.r.set(("devices",), stdout="ABC123\tfastboot\n")

    def tearDown(self):
        self._t.cleanup()

    def test_ok_when_everything_checks_out(self):
        var(self.r, "unlocked", "yes")
        var(self.r, "partition-size:boot_a", "0x4000000")
        result = preflight(TOOLS, "ABC123", [self.flash], runner=self.r)
        self.assertTrue(result.ok, result)
        self.assertEqual(result.warnings, ())

    def test_device_missing_stops_everything(self):
        self.r.set(("devices",), stdout="OTHER\tfastboot\n")
        result = preflight(TOOLS, "ABC123", [self.erase], runner=self.r)
        self.assertFalse(result.ok)
        self.assertIn("Nothing was run", result.errors[0])

    def test_locked_bootloader_is_an_error(self):
        var(self.r, "unlocked", "no")
        self.assertFalse(preflight(TOOLS, "ABC123", [self.erase], runner=self.r).ok)

    def test_unknown_unlock_state_is_only_a_warning(self):
        result = preflight(TOOLS, "ABC123", [self.erase], runner=self.r)
        self.assertTrue(result.ok)
        self.assertTrue(result.warnings)

    def test_image_larger_than_partition_is_an_error(self):
        var(self.r, "unlocked", "yes")
        var(self.r, "partition-size:boot_a", "0x100")
        result = preflight(TOOLS, "ABC123", [self.flash], runner=self.r)
        self.assertFalse(result.ok)
        self.assertIn("larger than", result.errors[0])

    def test_unreported_partition_size_is_a_warning(self):
        var(self.r, "unlocked", "yes")
        result = preflight(TOOLS, "ABC123", [self.flash], runner=self.r)
        self.assertTrue(result.ok)
        self.assertTrue(any("could not be checked" in w for w in result.warnings))

    def test_missing_image_is_an_error(self):
        var(self.r, "unlocked", "yes")
        self.img.unlink()
        self.assertFalse(preflight(TOOLS, "ABC123", [self.flash], runner=self.r).ok)

    def test_every_getvar_uses_the_serial(self):
        var(self.r, "unlocked", "yes")
        preflight(TOOLS, "ABC123", [self.flash], runner=self.r)
        for call in self.r.calls:
            if call[1:] != ("devices",):
                self.assertEqual(call[1:3], ("-s", "ABC123"))


class StrictUnlockTests(unittest.TestCase):
    """Auto Flash: the bootloader must answer 'unlocked: yes', otherwise nothing starts."""

    def setUp(self):
        self.erase = PlannedStep("erase", "Erase", ("erase", "userdata"), "userdata", destructive=True)
        self.r = FakeRunner()
        self.r.set(("devices",), stdout="ABC123\tfastboot\n")

    def run_pre(self, strict=True):
        return preflight(TOOLS, "ABC123", [self.erase], runner=self.r, require_unlocked=strict)

    def test_yes_continues(self):
        var(self.r, "unlocked", "yes")
        self.assertTrue(self.run_pre().ok)

    def test_no_stops_with_a_clear_message(self):
        var(self.r, "unlocked", "no")
        result = self.run_pre()
        self.assertFalse(result.ok)
        self.assertIn("unlocked bootloader is required", result.errors[0])

    def test_unable_to_verify_does_not_start(self):
        result = self.run_pre()  # the fake answers 'FAILED (not found)'
        self.assertFalse(result.ok)
        self.assertIn("Could not verify", result.errors[0])

    def test_unexpected_answer_does_not_start(self):
        var(self.r, "unlocked", "maybe")
        self.assertFalse(self.run_pre().ok)

    def test_the_exact_command_is_used(self):
        var(self.r, "unlocked", "yes")
        self.run_pre()
        self.assertIn(("/t/fastboot", "-s", "ABC123", "getvar", "unlocked"), self.r.calls)

    def test_not_strict_keeps_the_old_behaviour(self):
        self.assertTrue(self.run_pre(strict=False).ok)  # unknown state is only a warning there
        var(self.r, "unlocked", "no")
        self.assertFalse(self.run_pre(strict=False).ok)


class RunStepsTests(unittest.TestCase):
    def steps(self, n=3):
        return [PlannedStep("flash", f"Step {i}", ("flash", f"p{i}", f"/img{i}"), f"p{i}") for i in range(n)]

    def streamer(self, outcomes, record):
        outcomes = list(outcomes)

        def run(args, on_line=None, cancel_event=None, max_seconds=None):
            record.append((list(args), cancel_event))
            rc, text = outcomes.pop(0)
            if on_line:
                for line in text.splitlines():
                    on_line("stderr", line)
            return CommandResult(tuple(args), rc, "", text)
        return run

    def test_all_steps_run_in_order_with_serial(self):
        record, logs, seen = [], [], []
        result = run_steps(TOOLS, "ABC123", self.steps(),
                           on_step=lambda i, n, s: seen.append((i, n)),
                           on_log=lambda l, m: logs.append((l, m)),
                           streamer=self.streamer([(0, "OKAY"), (0, "OKAY"), (0, "OKAY")], record))
        self.assertTrue(result.success)
        self.assertEqual(seen, [(0, 3), (1, 3), (2, 3)])
        self.assertEqual([c[0][1:3] for c in record], [["-s", "ABC123"]] * 3)
        self.assertEqual([c[0][3:5] for c in record], [["flash", "p0"], ["flash", "p1"], ["flash", "p2"]])
        self.assertTrue(all(c[1] is None for c in record))  # steps are never cancelled mid-way

    def test_stops_at_first_failure(self):
        record = []
        result = run_steps(TOOLS, "ABC123", self.steps(),
                           streamer=self.streamer([(0, "OKAY"), (1, "FAILED (remote: 'not allowed in locked state')")], record))
        self.assertFalse(result.success)
        self.assertEqual(len(record), 2)  # the third step was never run
        self.assertEqual(result.completed, 1)
        self.assertEqual(result.failed_step.description, "Step 1")
        self.assertIn("locked", result.message)
        self.assertIn("inconsistent", result.message)

    def test_failed_text_with_exit_code_zero_still_fails(self):
        record = []
        result = run_steps(TOOLS, "ABC123", self.steps(2),
                           streamer=self.streamer([(0, "Sending...\nFAILED (remote: 'x')")], record))
        self.assertFalse(result.success)
        self.assertEqual(len(record), 1)

    def test_stop_request_is_honoured_between_steps_only(self):
        record = []
        stop = threading.Event()

        def on_step(i, n, s):
            if i == 0:
                stop.set()  # asked to stop during step 0

        result = run_steps(TOOLS, "ABC123", self.steps(), on_step=on_step, stop_event=stop,
                           streamer=self.streamer([(0, "OKAY")], record))
        self.assertEqual(len(record), 1)  # step 0 still ran to completion
        self.assertTrue(result.stopped)
        self.assertFalse(result.success)
        self.assertEqual(result.completed, 1)

    def test_bad_serial_runs_nothing(self):
        record = []
        result = run_steps(TOOLS, "x; y", self.steps(), streamer=self.streamer([], record))
        self.assertFalse(result.success)
        self.assertEqual(record, [])

    def test_erase_failure_has_no_partition_warning(self):
        erase = [PlannedStep("erase", "Erase userdata", ("erase", "userdata"), "userdata", destructive=True)]
        result = run_steps(TOOLS, "ABC123", erase, streamer=self.streamer([(1, "FAILED (remote: 'unknown command')")], []))
        self.assertFalse(result.success)
        self.assertNotIn("inconsistent", result.message)

    def test_timeout_and_start_error(self):
        def timeout(args, on_line=None, cancel_event=None, max_seconds=None):
            return CommandResult(tuple(args), None, timed_out=True)

        def broken(args, on_line=None, cancel_event=None, max_seconds=None):
            return CommandResult(tuple(args), None, error="boom")

        self.assertIn("too long", run_steps(TOOLS, "A1", self.steps(1), streamer=timeout).message)
        self.assertIn("boom", run_steps(TOOLS, "A1", self.steps(1), streamer=broken).message)


class FailureTests(unittest.TestCase):
    def test_step_failed(self):
        self.assertFalse(step_failed(CommandResult(("f",), 0, "", "Finished. Total time: 1s")))
        self.assertTrue(step_failed(CommandResult(("f",), 1, "", "")))
        self.assertTrue(step_failed(CommandResult(("f",), 0, "", "FAILED (x)")))
        self.assertTrue(step_failed(CommandResult(("f",), None, timed_out=True)))

    def test_explanations(self):
        self.assertIn("locked", explain_failure("FAILED (remote: 'not allowed in locked state')"))
        self.assertIn("does not exist", explain_failure("FAILED (remote: 'partition not found')"))
        self.assertIn("larger", explain_failure("FAILED (remote: 'data too large')"))
        self.assertIn("disconnected", explain_failure("error: no devices/emulators found"))
        self.assertIn("log above", explain_failure("something odd"))


if __name__ == "__main__":
    unittest.main()
