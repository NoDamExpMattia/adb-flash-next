"""Pure functions that turn raw ADB / Fastboot output into values.

Nothing here runs a command, so everything is easy to unit test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from adb_flash_next.config.constants import FASTBOOT_VAR_PATTERN, SERIAL_PATTERN

_SERIAL_RE = re.compile(SERIAL_PATTERN)
_VAR_RE = re.compile(FASTBOOT_VAR_PATTERN)
_PROP_RE = re.compile(r"^\[(?P<key>[^\]]+)\]: \[(?P<value>.*)\]\s*$")


def is_valid_serial(serial: str) -> bool:
    return bool(_SERIAL_RE.match(serial))


def validate_serial(serial: str) -> str:
    """Return the serial unchanged or raise ValueError. Used before building commands."""
    if not isinstance(serial, str) or not is_valid_serial(serial):
        raise ValueError(f"Refusing to use an invalid device serial: {serial!r}")
    return serial


def validate_fastboot_var(name: str) -> str:
    if not isinstance(name, str) or not _VAR_RE.match(name):
        raise ValueError(f"Refusing to use an invalid Fastboot variable name: {name!r}")
    return name


def validate_property_name(name: str) -> str:
    """Android property names (e.g. sys.boot_completed) use the same safe character set."""
    if not isinstance(name, str) or not _VAR_RE.match(name):
        raise ValueError(f"Refusing to use an invalid property name: {name!r}")
    return name


@dataclass(frozen=True)
class AdbListEntry:
    serial: str
    state: str  # raw ADB state, e.g. "device", "recovery", "sideload", "unauthorized"


def parse_adb_devices(text: str) -> list[AdbListEntry]:
    """Parse `adb devices` / `adb devices -l`. Only lines after the header count."""
    entries: list[AdbListEntry] = []
    header_seen = False
    for raw in text.splitlines():
        line = raw.strip()
        if not header_seen:
            header_seen = line.startswith("List of devices attached")
            continue
        if not line or line.startswith("*"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 2 or not is_valid_serial(parts[0]):
            continue
        state = parts[1].lower()
        if state == "no" and len(parts) > 2 and parts[2].lower().startswith("permissions"):
            state = "no permissions"
        entries.append(AdbListEntry(serial=parts[0], state=state))
    return entries


def parse_fastboot_devices(text: str) -> list[str]:
    """Parse `fastboot devices`: the serial is the first token of each line."""
    serials: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("<") or line.startswith("*"):
            continue
        token = line.split(None, 1)[0]
        if is_valid_serial(token) and token not in serials:
            serials.append(token)
    return serials


def parse_getprop(text: str) -> dict[str, str]:
    """Parse the output of `adb shell getprop` ("[key]: [value]" lines)."""
    props: dict[str, str] = {}
    for raw in text.splitlines():
        match = _PROP_RE.match(raw.rstrip())
        if match:
            props[match.group("key")] = match.group("value")
    return props


def parse_fastboot_var(text: str, name: str) -> str | None:
    """Extract the value of `fastboot getvar <name>`.

    Fastboot prints its answers on stderr in the form "name: value" (older versions
    prefix "(bootloader) "). Returns None when the variable is missing, empty or the
    bootloader reported a failure: never a guess.
    """
    prefix = f"{name}:"
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("(bootloader)"):
            line = line[len("(bootloader)"):].strip()
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            return value or None
    return None
