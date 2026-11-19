"""The ONLY place in the project that starts external processes.

Safety rules enforced here:
  * Commands are argument lists; a shell is never used (shell=False).
  * The executable must be an absolute path to an existing file.
  * Every call can be cancelled with a threading.Event; run_command also has a timeout.
  * Output is always returned (never swallowed) together with the exit code.
"""
from __future__ import annotations

import collections
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

# Hides the console window that would otherwise flash on Windows.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_POLL_STEP_SECONDS = 0.2
_MAX_STORED_LINES = 5000


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


def _validation_error(argv: tuple[str, ...]) -> str | None:
    """Return a message if the command is not acceptable to run, else None."""
    if not argv or not all(isinstance(a, str) for a in argv):
        return "Invalid command: arguments must be non-empty strings."
    if any("\x00" in a for a in argv):
        return "Invalid command: argument contains a NUL character."
    exe = Path(argv[0])
    if not exe.is_absolute() or not exe.is_file():
        return f"Executable not found or not an absolute path: {argv[0]}"
    return None


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
    problem = _validation_error(argv)
    if problem:
        return CommandResult(argv, None, error=problem)

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


LineCallback = Callable[[str, str], None]  # (stream name "stdout"/"stderr", text of one line)


def _pump(stream, name: str, on_line: LineCallback | None, sink: collections.deque) -> None:
    """Read `stream` and emit one line per \\n OR \\r (progress output uses \\r)."""
    buffer = bytearray()

    def emit(raw: bytes) -> None:
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return
        sink.append(text)
        if on_line is not None:
            try:
                on_line(name, text)
            except Exception:  # a faulty callback must never stop us draining the pipe
                pass

    while True:
        try:
            chunk = stream.read1(4096)
        except (OSError, ValueError):
            break
        if not chunk:
            break
        buffer.extend(chunk)
        while True:
            positions = [i for i in (buffer.find(b"\n"), buffer.find(b"\r")) if i >= 0]
            if not positions:
                break
            index = min(positions)
            line = bytes(buffer[:index])
            del buffer[: index + 1]
            emit(line)
    if buffer:
        emit(bytes(buffer))


def run_streaming(
    args: Sequence[str],
    on_line: LineCallback | None = None,
    cancel_event: threading.Event | None = None,
    max_seconds: float | None = None,
) -> CommandResult:
    """Run a long command and report its output line by line while it runs.

    Same safety rules as run_command. `max_seconds` is an overall limit (None = no limit).
    The returned result holds the collected output (the last 5000 lines per stream).
    """
    argv = tuple(args)
    problem = _validation_error(argv)
    if problem:
        return CommandResult(argv, None, error=problem)

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

    out_lines: collections.deque = collections.deque(maxlen=_MAX_STORED_LINES)
    err_lines: collections.deque = collections.deque(maxlen=_MAX_STORED_LINES)
    readers = [
        threading.Thread(target=_pump, args=(proc.stdout, "stdout", on_line, out_lines), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, "stderr", on_line, err_lines), daemon=True),
    ]
    for reader in readers:
        reader.start()

    started = time.monotonic()
    timed_out = False
    cancelled = False
    while True:
        try:
            proc.wait(timeout=_POLL_STEP_SECONDS)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
            elif max_seconds is not None and time.monotonic() - started >= max_seconds:
                timed_out = True
            if cancelled or timed_out:
                _stop_process(proc)
                break

    for reader in readers:
        reader.join(timeout=3)
    for stream in (proc.stdout, proc.stderr):
        try:
            stream.close()
        except (OSError, ValueError):
            pass

    return CommandResult(
        args=argv,
        returncode=proc.returncode,
        stdout="\n".join(out_lines),
        stderr="\n".join(err_lines),
        timed_out=timed_out,
        cancelled=cancelled,
    )
