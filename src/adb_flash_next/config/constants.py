"""Application-wide constants. No logic lives here."""
from __future__ import annotations

from pathlib import Path

APP_NAME = "ADB Flash Next"
APP_VERSION = "0.8.0"

DEFAULT_WINDOW_SIZE = (900, 650)
MIN_WINDOW_SIZE = (760, 560)

# Project root: .../adb_flash_next/  (this file is src/adb_flash_next/config/constants.py)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "assets"

# Place your own logo here (first file found is used).
LOGO_CANDIDATES = ("logo.png", "logo.svg")

# Folder name used for settings/logs under %LOCALAPPDATA% (Windows) or ~/.config.
APP_DATA_DIRNAME = "ADBFlashNext"

# Destination partitions supported by the flash plan (used from Stage 4 onward).
SUPPORTED_PARTITIONS = (
    "boot",
    "dtbo",
    "vendor_boot",
    "recovery",
    "init_boot",
    "vbmeta",
)


# Shown whenever a value cannot be determined. We never invent values.
NOT_AVAILABLE = "Not available"

# Manufacturers outside the intended compatibility scope (compared in lower case).
# Best effort only: the manufacturer is not exposed in every mode.
EXCLUDED_MANUFACTURERS = ("samsung",)

# --- Device detection -------------------------------------------------------
POLL_INTERVAL_SECONDS = 2.0
MAX_INFO_READ_ATTEMPTS = 3  # retries when a device's details could not be read

# Command timeouts in seconds.
TIMEOUT_TOOL_VERSION = 8.0
TIMEOUT_DEVICE_LIST = 12.0
TIMEOUT_ADB_PROPS = 12.0
TIMEOUT_FASTBOOT_GETVAR = 10.0
TIMEOUT_REBOOT = 30.0
TIMEOUT_FLASH_STEP = 1200.0  # one Fastboot flash/erase step, in seconds

# Allowed shapes for values that end up inside a command line.
# Serial: letters, digits, dot, underscore, dash, colon (e.g. "192.168.1.5:5555").
SERIAL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}$"
# Fastboot variable name, e.g. "product" or "has-slot:boot".
FASTBOOT_VAR_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,63}$"
