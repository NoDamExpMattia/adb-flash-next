"""Builds the flash plan: what would be run, and what blocks it. Nothing is executed here."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from adb_flash_next.config.constants import NOT_AVAILABLE, SUPPORTED_PARTITIONS
from adb_flash_next.core.image_validator import LEVEL_ERROR, LEVEL_WARNING, validate_image
from adb_flash_next.core.models import ConnectionMode, DeviceInfo, PartitionScheme, Transport
from adb_flash_next.core.slot_resolver import SlotChoice, SlotResolutionError, resolve_targets

ERROR = "ERROR"
WARNING = "WARNING"

FASTBOOT_MODES = (
    ConnectionMode.FASTBOOT,
    ConnectionMode.FASTBOOTD,
    ConnectionMode.FASTBOOT_UNCONFIRMED,
)


@dataclass
class PartitionSelection:
    """One row of the Images page. Rows start enabled; the user unticks what is not needed."""

    partition: str
    enabled: bool = True
    path: Path | None = None
    slot: SlotChoice | None = None  # only meaningful for A/B devices


@dataclass(frozen=True)
class PlanIssue:
    level: str  # ERROR blocks the plan; WARNING is informational
    message: str


@dataclass(frozen=True)
class PlannedStep:
    kind: str  # "flash" or "erase"
    description: str
    args: tuple[str, ...]  # Fastboot arguments that follow "-s <serial>"
    target_partition: str
    image: Path | None = None
    destructive: bool = False


@dataclass(frozen=True)
class FlashPlan:
    device_serial: str | None
    device_label: str
    mode_text: str
    scheme_text: str
    slot_text: str
    steps: tuple[PlannedStep, ...]
    issues: tuple[PlanIssue, ...]

    @property
    def errors(self) -> list[PlanIssue]:
        return [i for i in self.issues if i.level == ERROR]

    @property
    def warnings(self) -> list[PlanIssue]:
        return [i for i in self.issues if i.level == WARNING]

    @property
    def blocked(self) -> bool:
        """True when the plan must not be executed."""
        return bool(self.errors) or not self.steps or self.device_serial is None

    @property
    def has_destructive_step(self) -> bool:
        return any(step.destructive for step in self.steps)

    def command_previews(self, fastboot: str = "fastboot") -> list[str]:
        """Display-only command lines. They are never executed from these strings."""
        if self.device_serial is None:
            return []
        return [
            subprocess.list2cmdline([fastboot, "-s", self.device_serial, *step.args])
            for step in self.steps
        ]

    def summary_lines(self) -> list[str]:
        lines = [
            f"Device: {self.device_label}",
            f"Connection mode: {self.mode_text}",
            f"Partition scheme: {self.scheme_text}",
            f"Current active slot: {self.slot_text}",
            "Operations:",
        ]
        if not self.steps:
            lines.append("  (none)")
        for index, step in enumerate(self.steps, start=1):
            marker = "  !! " if step.destructive else "  "
            lines.append(f"{marker}{index}. {step.description}")
        return lines


def device_identity(device: DeviceInfo | None) -> dict:
    """Identity fields shared by every plan, with 'not available' for anything unknown."""
    if device is None:
        return dict(
            device_serial=None,
            device_label="No device selected",
            mode_text=NOT_AVAILABLE,
            scheme_text=NOT_AVAILABLE,
            slot_text=NOT_AVAILABLE,
        )
    return dict(
        device_serial=device.serial,
        device_label=f"{device.product_text()} ({device.serial})",
        mode_text=device.mode.value,
        scheme_text=device.scheme_text(),
        slot_text=device.active_slot or NOT_AVAILABLE,
    )


def build_plan(
    device: DeviceInfo | None, selections: list[PartitionSelection], defer_images: bool = False
) -> FlashPlan:
    """Plan for flashing: one `fastboot flash <partition> <image>` per ticked row/slot.

    With defer_images=True (Auto Flash "Extract partitions") the images do not exist yet: they are
    shown as <extracted from ROM>\\<partition>.img and are NOT validated. The real plan is built again,
    with real files, after the extraction.
    """
    issues: list[PlanIssue] = []

    if device is None:
        issues.append(PlanIssue(ERROR, "No device is selected. Connect a device and select it on the Dashboard."))
        return FlashPlan(steps=(), issues=tuple(issues), **device_identity(None))

    chosen = [s for s in selections if s.enabled]
    steps: list[PlannedStep] = []

    # --- device-level checks -------------------------------------------------
    if device.is_excluded:
        issues.append(PlanIssue(ERROR, "This device's manufacturer is outside the supported scope of this app."))
    if device.mode not in FASTBOOT_MODES:
        issues.append(PlanIssue(
            ERROR,
            f"The device is currently in '{device.mode.value}'. Flashing needs Fastboot mode: use the "
            "Reboot page to restart it into the bootloader, then press Refresh on the Dashboard.",
        ))
    if not chosen:
        issues.append(PlanIssue(ERROR, "Nothing to do: tick at least one partition."))

    scheme_error_reported = False
    for sel in chosen:
        name = sel.partition
        if sel.partition not in SUPPORTED_PARTITIONS:
            issues.append(PlanIssue(ERROR, f"'{name}' is not a supported partition."))
            continue
        if defer_images:
            image_path = Path("<extracted from ROM>") / f"{sel.partition}.img"
        elif sel.path is None:
            issues.append(PlanIssue(ERROR, f"{name}: no image selected. Choose a file or untick this partition."))
            continue
        else:
            image_path = sel.path
            # image checks
            result = validate_image(image_path, sel.partition)
            if result.level == LEVEL_ERROR:
                issues.append(PlanIssue(ERROR, f"{name} ({image_path.name}): {result.message}"))
                continue
            if result.level == LEVEL_WARNING:
                issues.append(PlanIssue(WARNING, f"{name} ({image_path.name}): {result.message}"))

        # slot / partition-name resolution
        if device.scheme is PartitionScheme.AB and sel.slot is None:
            issues.append(PlanIssue(ERROR, f"{name}: choose a slot (A, B or both)."))
            continue
        try:
            targets = resolve_targets(sel.partition, device.scheme, sel.slot, device.active_slot)
        except SlotResolutionError as exc:
            if device.scheme is PartitionScheme.UNKNOWN:
                if not scheme_error_reported:
                    issues.append(PlanIssue(ERROR, str(exc)))
                    scheme_error_reported = True
            else:
                issues.append(PlanIssue(ERROR, str(exc)))
            continue

        if (
            device.scheme is PartitionScheme.AB
            and sel.slot in (SlotChoice.A, SlotChoice.B)
            and device.active_slot in ("a", "b")
            and sel.slot.value != device.active_slot
        ):
            issues.append(PlanIssue(
                WARNING,
                f"{name}: targets slot {sel.slot.value.upper()} but the active slot is "
                f"{device.active_slot.upper()}. The device keeps booting the active slot until you switch.",
            ))

        for target in targets:
            steps.append(PlannedStep(
                kind="flash",
                description=f"Flash {image_path.name} -> {target}",
                args=("flash", target, str(image_path)),
                target_partition=target,
                image=image_path,
            ))

    return FlashPlan(steps=tuple(steps), issues=tuple(issues), **device_identity(device))
