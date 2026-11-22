"""Runs a flash plan: pre-flight checks, then each Fastboot command in order.

Safety rules:
  * Every command is bound to the verified serial (-s).
  * Commands run one at a time and the run STOPS at the first failure.
  * A stop request is only honoured BETWEEN steps: killing a flash half-way could leave a
    partition half-written.
  * A step counts as failed on a non-zero exit code OR when Fastboot printed FAILED.
"""
from __future__ import annotations

import re
import subprocess
import threading
from dataclasses import dataclass
from typing import Callable, Sequence

from adb_flash_next.config.constants import TIMEOUT_FLASH_STEP
from adb_flash_next.core.fastboot_client import FastbootClient
from adb_flash_next.core.flash_plan import PlannedStep
from adb_flash_next.core.parsers import validate_serial
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.process_runner import CommandResult, run_command, run_streaming

_FAILED_RE = re.compile(r"\bFAILED\b")

LogFn = Callable[[str, str], None]  # (level, message)
StepFn = Callable[[int, int, PlannedStep], None]  # (index, total, step)


def parse_size(value: str | None) -> int | None:
    """Parse a size such as '0x4000000' or '67108864'. None when it is not a clear number."""
    if not value:
        return None
    text = value.strip().lower()
    try:
        if text.startswith("0x"):
            return int(text, 16)
        if text.isdigit():
            return int(text)
    except ValueError:
        return None
    return None


@dataclass(frozen=True)
class Preflight:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def preflight(
    tools: PlatformTools,
    serial: str,
    steps: Sequence[PlannedStep],
    cancel_event: threading.Event | None = None,
    runner: Callable[..., CommandResult] = run_command,
    require_unlocked: bool = False,
) -> Preflight:
    """Checks made right before running: device present, bootloader state, image fits partition.

    With require_unlocked=True (Auto Flash) the bootloader must ANSWER 'unlocked: yes'; a locked
    bootloader or an answer that cannot be verified both stop everything.
    """
    errors: list[str] = []
    warnings: list[str] = []
    client = FastbootClient(tools.fastboot, runner)

    serials, listing = client.list_devices(cancel_event)
    if not listing.ok:
        return Preflight((f"Could not ask Fastboot for the device list: {listing.failure_reason()}",), ())
    if serial not in serials:
        return Preflight((
            f"Device {serial} is not connected in Fastboot mode any more. Nothing was run.",
        ), ())

    unlocked, _ = client.getvar(serial, "unlocked", cancel_event)
    answer = unlocked.strip().lower() if unlocked else None
    if answer == "no":
        errors.append(
            "The bootloader is LOCKED: an unlocked bootloader is required. Nothing was run."
        )
    elif answer != "yes":
        if require_unlocked:
            errors.append(
                "Could not verify that the bootloader is unlocked ('fastboot getvar unlocked' did not "
                "answer 'yes'), so nothing was started."
            )
        elif answer is None:
            warnings.append("The bootloader did not report whether it is unlocked.")

    for step in steps:
        if step.kind != "flash" or step.image is None:
            continue
        if not step.image.is_file():
            errors.append(f"The image file is missing: {step.image}")
            continue
        value, _ = client.getvar(serial, f"partition-size:{step.target_partition}", cancel_event)
        partition_size = parse_size(value)
        image_size = step.image.stat().st_size
        if partition_size is None:
            warnings.append(
                f"The bootloader did not report the size of '{step.target_partition}', so whether it "
                "exists and fits the image could not be checked."
            )
        elif image_size > partition_size:
            errors.append(
                f"{step.image.name} ({image_size} bytes) is larger than '{step.target_partition}' "
                f"({partition_size} bytes)."
            )
    return Preflight(tuple(errors), tuple(warnings))


def step_failed(result: CommandResult) -> bool:
    return (not result.ok) or bool(_FAILED_RE.search(result.combined_output))


def explain_failure(output: str) -> str:
    """Short plain-language hint for common Fastboot errors."""
    lowered = output.lower()
    if "locked" in lowered:
        return "The bootloader is locked or refused the command in its current state."
    if "too large" in lowered or "size" in lowered and "exceed" in lowered:
        return "The image is larger than the partition."
    if "not found" in lowered and "partition" in lowered or "no such partition" in lowered or "unknown partition" in lowered:
        return "The partition does not exist on this device (wrong name or slot?)."
    if "no devices" in lowered or "device not found" in lowered or "cannot open device" in lowered:
        return "The device disconnected. Check the cable and try again."
    if "unknown command" in lowered or "not supported" in lowered or "unsupported" in lowered:
        return "This device's bootloader does not support the command."
    return "See the log above for Fastboot's own message."


@dataclass(frozen=True)
class FlashRunResult:
    success: bool
    completed: int
    total: int
    failed_step: PlannedStep | None
    message: str
    stopped: bool = False


def run_steps(
    tools: PlatformTools,
    serial: str,
    steps: Sequence[PlannedStep],
    on_step: StepFn | None = None,
    on_log: LogFn | None = None,
    stop_event: threading.Event | None = None,
    streamer: Callable[..., CommandResult] = run_streaming,
    max_step_seconds: float = TIMEOUT_FLASH_STEP,
) -> FlashRunResult:
    """Run the steps in order. Stops at the first failure or when a stop is requested."""

    def log(level: str, message: str) -> None:
        if on_log is not None:
            on_log(level, message)

    total = len(steps)
    for index, step in enumerate(steps):
        if stop_event is not None and stop_event.is_set():
            return FlashRunResult(
                False, index, total, None,
                f"Stopped as requested after {index} of {total} step(s). Nothing further was run.",
                stopped=True,
            )
        if on_step is not None:
            on_step(index, total, step)
        try:
            command = [str(tools.fastboot), "-s", validate_serial(serial), *step.args]
        except ValueError as exc:
            return FlashRunResult(False, index, total, step, str(exc))
        log("INFO", f"$ {subprocess.list2cmdline(command)}")

        # The step itself is never cancelled mid-way (see module docstring).
        result = streamer(
            command,
            on_line=lambda _stream, text: log("INFO", text),
            cancel_event=None,
            max_seconds=max_step_seconds,
        )
        if step_failed(result):
            if result.error:
                reason = f"Could not start fastboot: {result.error}"
            elif result.timed_out:
                reason = "The command took too long and was stopped."
            else:
                reason = explain_failure(result.combined_output)
            partial = (
                " The partition may now be in an inconsistent state: do not boot the device into "
                "Android until you have flashed it again successfully."
                if step.kind == "flash"
                else ""
            )
            return FlashRunResult(
                False, index, total, step,
                f"Step {index + 1} of {total} failed: {step.description}. {reason}{partial} "
                "No further steps were run.",
            )
        log("SUCCESS", f"Step {index + 1} of {total} finished: {step.description}")

    return FlashRunResult(True, total, total, None, f"All {total} step(s) completed successfully.")
