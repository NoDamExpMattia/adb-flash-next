"""Tiny JSON settings store.

Only application preferences live here (for example the Platform-Tools folder).
Device profiles are intentionally NOT stored anywhere.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from adb_flash_next.config.constants import APP_DATA_DIRNAME
<<<<<<< HEAD
from adb_flash_next.ui.m3.tokens import normalize_hex
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b


def app_data_dir() -> Path:
    """Per-user data folder (settings, and session logs in a later stage)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else Path.home() / ".config"
    return root / APP_DATA_DIRNAME


class Settings:
    """Loads and saves a small dictionary of preferences. Never raises on I/O errors."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (app_data_dir() / "settings.json")
        self._data: dict[str, Any] = {}

    @property
    def path(self) -> Path:
        return self._path

    # -- values --------------------------------------------------------------
    @property
    def platform_tools_dir(self) -> str | None:
        value = self._data.get("platform_tools_dir")
        return value if isinstance(value, str) and value else None

    @platform_tools_dir.setter
    def platform_tools_dir(self, value: str | None) -> None:
        self._data["platform_tools_dir"] = value

<<<<<<< HEAD
    @property
    def theme_seed(self) -> str:
        """Accent colour as '#RRGGBB' (invalid or missing values fall back to the default red)."""
        return normalize_hex(self._data.get("theme_seed"))

    @theme_seed.setter
    def theme_seed(self, value: str) -> None:
        self._data["theme_seed"] = normalize_hex(value)

    @property
    def theme_mode(self) -> str:
        """'dark' or 'light' (anything else means dark)."""
        value = self._data.get("theme_mode")
        return value if value in ("dark", "light") else "dark"

    @theme_mode.setter
    def theme_mode(self, value: str) -> None:
        self._data["theme_mode"] = value if value in ("dark", "light") else "dark"

=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    # -- persistence ---------------------------------------------------------
    def load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._data = {}
            return
        self._data = raw if isinstance(raw, dict) else {}

    def save(self) -> bool:
        """Write settings atomically. Returns False if the file could not be written."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
            return True
        except OSError:
            return False
