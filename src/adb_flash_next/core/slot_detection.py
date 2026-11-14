"""Decide A/B vs A-only from evidence reported BY THE DEVICE.

Rules: every conclusion must be backed by at least one reported value, and
conflicting evidence results in UNKNOWN. Nothing is assumed.
"""
from __future__ import annotations

from adb_flash_next.core.models import PartitionScheme

Vote = tuple[PartitionScheme, str]  # (scheme suggested, evidence text)


def normalize_slot(value: str | None) -> str | None:
    """'a', '_a', 'A' -> 'a'. Anything other than a or b -> None."""
    if not value:
        return None
    cleaned = value.strip().lstrip("_").lower()
    return cleaned if cleaned in ("a", "b") else None


def votes_from_fastboot(
    slot_count: str | None, has_slot_boot: str | None, current_slot: str | None
) -> list[Vote]:
    votes: list[Vote] = []
    if slot_count is not None and slot_count.strip().isdigit():
        count = int(slot_count.strip())
        if count >= 2:
            votes.append((PartitionScheme.AB, f"slot-count={count}"))
        elif count == 0:
            votes.append((PartitionScheme.A_ONLY, "slot-count=0"))
    if has_slot_boot is not None:
        answer = has_slot_boot.strip().lower()
        if answer == "yes":
            votes.append((PartitionScheme.AB, "has-slot:boot=yes"))
        elif answer == "no":
            votes.append((PartitionScheme.A_ONLY, "has-slot:boot=no"))
    slot = normalize_slot(current_slot)
    if slot:
        votes.append((PartitionScheme.AB, f"current-slot={slot}"))
    return votes


def votes_from_adb(props: dict[str, str]) -> list[Vote]:
    votes: list[Vote] = []
    ab_update = props.get("ro.build.ab_update", "").strip().lower()
    if ab_update == "true":
        votes.append((PartitionScheme.AB, "ro.build.ab_update=true"))
    elif ab_update == "false":
        votes.append((PartitionScheme.A_ONLY, "ro.build.ab_update=false"))
    suffix = props.get("ro.boot.slot_suffix", "").strip().lower()
    if suffix in ("_a", "_b"):
        votes.append((PartitionScheme.AB, f"ro.boot.slot_suffix={suffix}"))
    return votes


def decide_scheme(votes: list[Vote]) -> tuple[PartitionScheme, str]:
    """Combine votes. Returns (scheme, evidence text)."""
    if not votes:
        return PartitionScheme.UNKNOWN, "no slot information reported"
    schemes = {scheme for scheme, _ in votes}
    evidence = "; ".join(text for _, text in votes)
    if len(schemes) == 1:
        return next(iter(schemes)), evidence
    return PartitionScheme.UNKNOWN, f"conflicting information: {evidence}"
