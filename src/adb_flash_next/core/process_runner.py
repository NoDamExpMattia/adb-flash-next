"""The ONLY place in the project that starts external processes.

Safety rules enforced here:
  * Commands are argument lists; a shell is never used (shell=False).
  * The executable must be an absolute path to an existing file.
  * Every call has a timeout and can be cancelled with a threading.Event.
  * Output is always returned (never swallowed) together with the exit code.
"""
from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# Hides the console window that would otherwise flash on Windows.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_POLL_STEP_SECONDS = 0.2


@dataclass(frozen=True)
class CommandResult:
    """Outcome of one external command."""

    args: tuple[str, ...]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    cancelled: bool = False
    error: str | None = None  # the command could not be started at all

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and not self.timed_out
            and not self.cancelled
            and self.returncode == 0
        )

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part)

    @property
    def command_line(self) -> str:
        """For display in logs only. Never executed."""
        return subprocess.list2cmdline(list(self.args))

    def failure_reason(self) -> str:
        """One short human-readable line explaining why the command did not succeed."""
        if self.error:
            return self.error
        if self.timed_out:
            return "the command timed out"
        if self.cancelled:
            return "the command was cancelled"
        for text in (self.stderr, self.stdout):
            for line in text.splitlines():
                if line.strip():
                    return f"{line.strip()} (exit code {self.returncode})"
        return f"exit code {self.returncode}"


def _decode(data: bytes | None) -> str:
    if not data:
        return ""
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _stop_process(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def _drain(proc: subprocess.Popen) -> tuple[bytes, bytes]:
    try:
        return proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        # A child process (for example the ADB server) may still hold the pipes.
        return b"", b""


def run_command(
    args: Sequence[str],
    timeout: float,
    cancel_event: threading.Event | None = None,
) -> CommandResult:
    """Run `args` without a shell and return its result.

    Never raises for ordinary failures: problems are reported in the result.
    """
    argv = tuple(args)

    if not argv or not all(isinstance(a, str) for a in argv):
        return CommandResult(argv, None, error="Invalid command: arguments must be non-empty strings.")
    if any("\x00" in a for a in argv):
        return CommandResult(argv, None, error="Invalid command: argument contains a NUL character.")
    exe = Path(argv[0])
    if not exe.is_absolute() or not exe.is_file():
        return CommandResult(argv, None, error=f"Executable not found or not an absolute path: {argv[0]}")

    try:
        proc = subprocess.Popen(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, ValueError) as exc:
        return CommandResult(argv, None, error=f"Could not start the command: {exc}")

    deadline = time.monotonic() + timeout
    timed_out = False
    cancelled = False
    while True:
        try:
            out, err = proc.communicate(timeout=_POLL_STEP_SECONDS)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
            elif time.monotonic() >= deadline:
                timed_out = True
            if cancelled or timed_out:
                _stop_process(proc)
                out, err = _drain(proc)
                break

    return CommandResult(
        args=argv,
        returncode=proc.returncode,
        stdout=_decode(out),
        stderr=_decode(err),
        timed_out=timed_out,
        cancelled=cancelled,
    )
