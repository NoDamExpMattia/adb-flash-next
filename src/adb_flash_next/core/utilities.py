"""Single-command Fastboot utilities: erase userdata / metadata / frp and patch vbmeta."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from adb_flash_next.core.flash_plan import (
    ERROR,
    WARNING,
    FlashPlan,
    PlanIssue,
    PlannedStep,
    device_identity,
)
from adb_flash_next.core.image_validator import LEVEL_ERROR, LEVEL_WARNING, validate_image
from adb_flash_next.core.models import ConnectionMode, DeviceInfo, PartitionScheme, Transport

# Written before the command, which is the order documented for fastboot options.
VBMETA_FLAGS = ("--disable-verity", "--disable-verification")


@dataclass(frozen=True)
class UtilityAction:
    key: str
    label: str
    command_text: str  # what the user sees, e.g. "fastboot erase userdata"
    icon: str
    warning: str
    partition: str | None = None  # erase target, None for patch_vbmeta


ERASE_USERDATA = UtilityAction(
    "erase_userdata", "Erase userdata", "fastboot erase userdata", "delete",
    "Erases ALL user data on the device (apps, photos, settings, internal storage).",
    partition="userdata",
)
ERASE_METADATA = UtilityAction(
    "erase_metadata", "Erase Metadata", "fastboot erase metadata", "database",
    "Erases the metadata partition, which holds the encryption data for user data. Data on the "
    "device becomes unreadable. It is normally done together with erasing userdata, and only if "
    "your ROM's instructions say so.",
    partition="metadata",
)
ERASE_FRP = UtilityAction(
    "erase_frp", "Erase FRP", "fastboot erase frp", "lock",
    "Erases the Factory Reset Protection data. Use it only on a device you own. The device may "
    "need to be set up again afterwards.",
    partition="frp",
)
PATCH_VBMETA = UtilityAction(
    "patch_vbmeta", "Patch Vbmeta", "fastboot flash vbmeta --disable-verity --disable-verification", "shield",
    "Flashes the vbmeta image you select with verity and verification disabled. This changes the "
    "device's verification state; use it only if your ROM's instructions say so.",
)

ACTIONS: dict[str, UtilityAction] = {
    a.key: a for a in (ERASE_USERDATA, ERASE_METADATA, ERASE_FRP, PATCH_VBMETA)
}


def fastboot_readiness(device: DeviceInfo | None) -> tuple[bool, str, str]:
    """(ready, short status, hint) for running a Fastboot utility on `device`."""
    if device is None:
        return False, "No device selected", (
            "Connect the device and select it on the Dashboard. If several are connected, choose one."
        )
    if device.is_excluded:
        return False, "Unsupported device", "This device's manufacturer is outside the supported scope."
    if device.transport is Transport.FASTBOOT:
        return True, f"Device is in {device.mode.value}", ""
    return False, f"Device is in {device.mode.value}", (
        "Utilities need Fastboot mode. Use the Reboot page to restart into the bootloader, then press "
        "Refresh on the Dashboard."
    )


def build_utility_plan(
    device: DeviceInfo | None, key: str, vbmeta_path: Path | None = None
) -> FlashPlan:
    """A one-step plan for a utility. Raises ValueError for an unknown key."""
    action = ACTIONS.get(key)
    if action is None:
        raise ValueError(f"Unknown utility: {key!r}")

    issues: list[PlanIssue] = []
    if device is None:
        issues.append(PlanIssue(ERROR, "No device is selected. Connect a device and select it on the Dashboard."))
        return FlashPlan(steps=(), issues=tuple(issues), **device_identity(None))

    ready, text, hint = fastboot_readiness(device)
    if not ready:
        issues.append(PlanIssue(ERROR, f"{text}. {hint}".strip()))

    steps: list[PlannedStep] = []
    if action.key == "patch_vbmeta":
        if vbmeta_path is None:
            issues.append(PlanIssue(ERROR, "Choose your device's vbmeta.img first."))
        else:
            check = validate_image(vbmeta_path, "vbmeta")
            if check.level == LEVEL_ERROR:
                issues.append(PlanIssue(ERROR, f"{vbmeta_path.name}: {check.message}"))
            else:
                if check.level == LEVEL_WARNING:
                    issues.append(PlanIssue(WARNING, f"{vbmeta_path.name}: {check.message}"))
                steps.append(PlannedStep(
                    kind="flash",
                    description=f"Flash {vbmeta_path.name} -> vbmeta (verity and verification disabled)",
                    args=(*VBMETA_FLAGS, "flash", "vbmeta", str(vbmeta_path)),
                    target_partition="vbmeta",
                    image=vbmeta_path,
                ))
        if device.scheme is PartitionScheme.AB:
            slot = device.active_slot.upper() if device.active_slot else "reported by the bootloader"
            issues.append(PlanIssue(
                WARNING,
                f"On A/B devices Fastboot writes 'vbmeta' to the CURRENT slot ({slot}).",
            ))
        issues.append(PlanIssue(WARNING, action.warning))
    else:
        steps.append(PlannedStep(
            kind="erase",
            description=f"{action.label} ({action.command_text})",
            args=("erase", action.partition or ""),
            target_partition=action.partition or "",
            destructive=True,
        ))
        issues.append(PlanIssue(WARNING, action.warning))

    return FlashPlan(steps=tuple(steps), issues=tuple(issues), **device_identity(device))
