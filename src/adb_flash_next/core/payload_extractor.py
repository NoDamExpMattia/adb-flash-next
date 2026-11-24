"""Extract partition images from a ROM's payload.bin with payload-dumper-go (Apache-2.0).

The tool is not written by this project: the app only runs it (no shell, argument list) and then
checks that every requested image exists and has a recognised header before anything is flashed.
Works for FULL OTA ROMs. Incremental OTAs need a base image and are not supported here.
"""
from __future__ import annotations

import shutil
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from adb_flash_next.config.constants import APP_DIR, PROJECT_ROOT, SUPPORTED_PARTITIONS
from adb_flash_next.config.settings import app_data_dir
from adb_flash_next.core.process_runner import CommandResult, run_streaming

LineFn = Callable[[str, str], None]  # (level, message)


def tool_name() -> str:
    return "payload-dumper-go.exe" if sys.platform == "win32" else "payload-dumper-go"


def locate_tool(configured: str | None = None) -> Path | None:
    """Find payload-dumper-go: the saved path, a 'bin' folder (bundled), next to the program, or PATH."""
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    name = tool_name()
    candidates += [PROJECT_ROOT / "bin" / name, APP_DIR / "bin" / name, APP_DIR / name]
    on_path = shutil.which("payload-dumper-go")
    if on_path:
        candidates.append(Path(on_path))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def zip_has_payload(path: Path) -> bool:
    """True when the ZIP contains a top-level payload.bin (a full A/B OTA package)."""
    try:
        with zipfile.ZipFile(path) as archive:
            return any(name.lower() == "payload.bin" for name in archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return False


def build_extract_command(tool: Path, rom: Path, partitions: Sequence[str], output_dir: Path) -> list[str]:
    """Argument list for `payload-dumper-go -p a,b -o <dir> <rom.zip>`. Partition names are allow-listed."""
    names = list(dict.fromkeys(partitions))
    if not names:
        raise ValueError("No partitions to extract.")
    bad = [name for name in names if name not in SUPPORTED_PARTITIONS]
    if bad:
        raise ValueError(f"Unsupported partition name(s): {', '.join(bad)}")
    return [str(tool), "-p", ",".join(names), "-o", str(output_dir), str(rom)]


@dataclass(frozen=True)
class ExtractResult:
    success: bool
    files: dict[str, Path]  # partition -> extracted image
    message: str
    cancelled: bool = False


def extract_partitions(
    tool: Path,
    rom: Path,
    partitions: Sequence[str],
    output_dir: Path,
    on_log: LineFn | None = None,
    cancel_event: threading.Event | None = None,
    streamer: Callable[..., CommandResult] = run_streaming,
    max_seconds: float = 1800.0,
) -> ExtractResult:
    """Run the extraction and verify the result. Nothing here touches a device."""
    try:
        command = build_extract_command(tool, rom, partitions, output_dir)
    except ValueError as exc:
        return ExtractResult(False, {}, str(exc))
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return ExtractResult(False, {}, f"Could not create the folder for the extracted images: {exc}")

    if on_log:
        on_log("INFO", "$ " + " ".join(f'"{part}"' if " " in part else part for part in command))
    result = streamer(
        command,
        on_line=(lambda _stream, text: on_log("INFO", text)) if on_log else None,
        cancel_event=cancel_event,
        max_seconds=max_seconds,
    )
    if result.cancelled:
        return ExtractResult(False, {}, "Extraction cancelled. Nothing was flashed.", cancelled=True)
    if not result.ok:
        return ExtractResult(False, {}, f"Extraction failed: {result.failure_reason()}. Nothing was flashed.")

    files: dict[str, Path] = {}
    missing: list[str] = []
    for name in dict.fromkeys(partitions):
        image = output_dir / f"{name}.img"
        if image.is_file() and image.stat().st_size > 0:
            files[name] = image
        else:
            missing.append(name)
    if missing:
        return ExtractResult(
            False, {},
            f"The extraction finished but these partitions were not produced: {', '.join(missing)}. "
            "They are probably not in this ROM's payload. Untick them and try again. Nothing was flashed.",
        )
    return ExtractResult(True, files, f"Extracted {len(files)} partition(s): {', '.join(files)}.")


# ----------------------------------------------------------------- temporary folders
def extraction_root() -> Path:
    return app_data_dir() / "extracted"


def new_run_dir(root: Path | None = None) -> Path:
    """A fresh folder for one run (not created yet)."""
    return (root or extraction_root()) / time.strftime("run-%Y%m%d-%H%M%S")


def cleanup_dir(path: Path | None, root: Path | None = None) -> bool:
    """Delete an extraction folder, but ONLY if it lies inside the app's own extraction root."""
    if path is None:
        return False
    base = (root or extraction_root()).resolve()
    try:
        target = Path(path).resolve()
        if target == base or base not in target.parents:
            return False
        shutil.rmtree(target, ignore_errors=True)
        return True
    except OSError:
        return False
