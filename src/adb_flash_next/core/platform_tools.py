"""Locate and validate the official Google Android Platform-Tools (adb + fastboot).

The tools are NOT bundled with this application. The user points the app at a
folder, or the app looks in a few well-known places.
"""
from __future__ import annotations

import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from adb_flash_next.config.constants import APP_DIR, TIMEOUT_TOOL_VERSION
from adb_flash_next.core.process_runner import CommandResult, run_command

Runner = Callable[..., CommandResult]


class PlatformToolsError(Exception):
    """The chosen folder does not contain working adb / fastboot executables."""


@dataclass(frozen=True)
class PlatformTools:
    directory: Path
    adb: Path
    fastboot: Path
    adb_version: str | None = None
    fastboot_version: str | None = None


def tool_filename(name: str) -> str:
    """'adb' -> 'adb.exe' on Windows, 'adb' elsewhere."""
    return f"{name}.exe" if sys.platform == "win32" else name


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def _adb_version_line(text: str) -> str | None:
    """`adb version` prints two lines; the 'Version x.y.z-build' one is the useful one."""
    for line in text.splitlines():
        if line.strip().startswith("Version "):
            return line.strip()[len("Version "):]
    return _first_line(text)


def check_directory(
    directory: Path,
    cancel_event: threading.Event | None = None,
    runner: Runner = run_command,
) -> PlatformTools:
    """Verify that `directory` holds runnable adb and fastboot; raise PlatformToolsError if not."""
    try:
        resolved = Path(directory).expanduser().resolve(strict=True)
    except OSError:
        raise PlatformToolsError(f"Folder not found: {directory}") from None
    if not resolved.is_dir():
        raise PlatformToolsError(f"Not a folder: {resolved}")

    adb = resolved / tool_filename("adb")
    fastboot = resolved / tool_filename("fastboot")
    missing = [p.name for p in (adb, fastboot) if not p.is_file()]
    if missing:
        raise PlatformToolsError(
            f"Missing {', '.join(missing)} in {resolved}. "
            "Select the 'platform-tools' folder that contains adb and fastboot."
        )

    adb_result = runner([str(adb), "version"], timeout=TIMEOUT_TOOL_VERSION, cancel_event=cancel_event)
    if not adb_result.ok:
        raise PlatformToolsError(f"adb did not run correctly: {adb_result.failure_reason()}")
    fb_result = runner([str(fastboot), "--version"], timeout=TIMEOUT_TOOL_VERSION, cancel_event=cancel_event)
    if not fb_result.ok:
        raise PlatformToolsError(f"fastboot did not run correctly: {fb_result.failure_reason()}")

    return PlatformTools(
        directory=resolved,
        adb=adb,
        fastboot=fastboot,
        adb_version=_adb_version_line(adb_result.stdout),
        fastboot_version=_first_line(fb_result.stdout or fb_result.stderr),
    )


def candidate_directories(configured: str | None) -> list[tuple[str, Path]]:
    """Folders to try, in priority order, as (description, path)."""
    candidates: list[tuple[str, Path]] = []
    if configured:
        candidates.append(("the folder saved in Settings", Path(configured)))
    candidates.append(("the 'platform-tools' folder inside the program folder", APP_DIR / "platform-tools"))
    candidates.append(("the 'platform-tools' folder next to the program folder", APP_DIR.parent / "platform-tools"))
    on_path = shutil.which("adb")
    if on_path:
        candidates.append(("the system PATH", Path(on_path).parent))

    unique: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for label, path in candidates:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append((label, path))
    return unique


def locate(
    configured: str | None = None,
    cancel_event: threading.Event | None = None,
    runner: Runner = run_command,
) -> tuple[PlatformTools | None, list[str]]:
    """Find working Platform-Tools. Returns (tools or None, messages for the log)."""
    messages: list[str] = []
    for label, path in candidate_directories(configured):
        if not path.is_dir():
            if label.startswith("the folder saved"):
                messages.append(f"Saved Platform-Tools folder no longer exists: {path}")
            continue
        try:
            tools = check_directory(path, cancel_event=cancel_event, runner=runner)
        except PlatformToolsError as exc:
            messages.append(f"Checked {label} ({path}): {exc}")
            continue
        messages.append(f"Using Platform-Tools from {label}: {tools.directory}")
        return tools, messages
    messages.append("No working Platform-Tools folder was found.")
    return None, messages
