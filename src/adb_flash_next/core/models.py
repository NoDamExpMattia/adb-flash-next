"""Plain data models shared by the core, worker and UI layers. No Qt in here."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from adb_flash_next.config.constants import EXCLUDED_MANUFACTURERS, NOT_AVAILABLE

# Rows shown in the dashboard's device information grid (in this order).
INFO_FIELDS: tuple[str, ...] = (
    "Serial number",
    "Product / codename",
    "Platform / SoC",
    "Android version",
    "Connection mode",
    "Partition scheme",
    "Active slot",
    "Fastboot / Fastbootd",
)


class Transport(str, Enum):
    """Which tool currently sees the device."""

    ADB = "adb"
    FASTBOOT = "fastboot"


class ConnectionMode(str, Enum):
    ANDROID = "Android (ADB)"
    RECOVERY = "Recovery (ADB)"
    SIDELOAD = "ADB sideload"
    RESCUE = "ADB rescue"
    UNAUTHORIZED = "ADB - not authorized"
    OFFLINE = "ADB - offline"
    FASTBOOT = "Fastboot (bootloader)"
    FASTBOOTD = "Fastbootd (userspace)"
    FASTBOOT_UNCONFIRMED = "Fastboot (bootloader/fastbootd not confirmed)"
    UNKNOWN = "Unknown"


class PartitionScheme(str, Enum):
    AB = "A/B"
    A_ONLY = "A-only"
    UNKNOWN = "Unknown"


@dataclass
class DeviceInfo:
    """Everything we could verify about one connected device.

    Any field left as None / UNKNOWN means "could not be determined": it is never
    filled with a guess.
    """

    serial: str
    transport: Transport
    mode: ConnectionMode = ConnectionMode.UNKNOWN
    adb_state: str | None = None
    product: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    platform: str | None = None
    android_version: str | None = None
    scheme: PartitionScheme = PartitionScheme.UNKNOWN
    scheme_evidence: str = ""
    active_slot: str | None = None  # "a" or "b"
    is_userspace: bool | None = None  # Fastboot only: True = fastbootd
    bootloader_unlocked: str | None = None  # raw Fastboot value ("yes"/"no") if reported
    boot_completed: bool | None = None  # ADB only: sys.boot_completed == 1
    read_ok: bool = True  # False when details should have been readable but were not
    warnings: list[str] = field(default_factory=list)  # shown to the user
    notes: list[str] = field(default_factory=list)  # informational, log only

    # -- identity ------------------------------------------------------------
    @property
    def key(self) -> str:
        """Unique key for this device in this transport, e.g. 'fastboot:ABC123'."""
        return f"{self.transport.value}:{self.serial}"

    @property
    def is_excluded(self) -> bool:
        """True for manufacturers outside the supported scope (e.g. Samsung)."""
        return bool(self.manufacturer) and self.manufacturer.strip().lower() in EXCLUDED_MANUFACTURERS

    # -- presentation --------------------------------------------------------
    def product_text(self) -> str:
        if self.product and self.model and self.model != self.product:
            return f"{self.product} ({self.model})"
        return self.product or self.model or NOT_AVAILABLE

    def fastboot_status_text(self) -> str:
        if self.mode in (
            ConnectionMode.FASTBOOT,
            ConnectionMode.FASTBOOTD,
            ConnectionMode.FASTBOOT_UNCONFIRMED,
        ):
            return self.mode.value
        return "Not in Fastboot mode"

    def scheme_text(self) -> str:
        if self.scheme is PartitionScheme.UNKNOWN:
            return f"Unknown ({self.scheme_evidence})" if self.scheme_evidence else "Unknown"
        return f"{self.scheme.value} ({self.scheme_evidence})" if self.scheme_evidence else self.scheme.value

    def slot_text(self) -> str:
        if self.active_slot:
            return self.active_slot
        if self.scheme is PartitionScheme.A_ONLY:
            return "Not applicable (A-only)"
        return NOT_AVAILABLE

    def to_display_dict(self) -> dict[str, str]:
        """Strings for the dashboard grid, keyed by INFO_FIELDS."""
        return {
            "Serial number": self.serial,
            "Product / codename": self.product_text(),
            "Platform / SoC": self.platform or NOT_AVAILABLE,
            "Android version": self.android_version or NOT_AVAILABLE,
            "Connection mode": self.mode.value,
            "Partition scheme": self.scheme_text(),
            "Active slot": self.slot_text(),
            "Fastboot / Fastbootd": self.fastboot_status_text(),
        }


@dataclass(frozen=True)
class PollResult:
    """One snapshot of every connected device plus any problems found while polling."""

    devices: tuple[DeviceInfo, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def signature(self) -> tuple:
        """Comparable value used to skip UI updates when nothing changed."""
        return (
            tuple(
                (d.key, d.mode.value, d.read_ok, tuple(d.to_display_dict().items()), tuple(d.warnings))
                for d in self.devices
            ),
            self.warnings,
        )
