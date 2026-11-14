"""Entry point for ADB Flash Next.

Run from the project root with:  python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the "src" folder importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from adb_flash_next.app import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run())
