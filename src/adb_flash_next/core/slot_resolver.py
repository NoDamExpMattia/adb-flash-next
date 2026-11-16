"""Turns a logical partition name plus the user's slot choice into exact partition names.

Nothing is guessed: an unknown scheme or a missing slot choice stops the plan.
"ab" in the UI means BOTH slots and always becomes TWO separate partitions
(<partition>_a and <partition>_b). A partition named "<partition>_ab" is never produced.
"""
from __future__ import annotations

from enum import Enum

from adb_flash_next.config.constants import SUPPORTED_PARTITIONS
from adb_flash_next.core.models import PartitionScheme


class SlotChoice(str, Enum):
    A = "a"
    B = "b"
    BOTH = "ab"

    @property
    def label(self) -> str:
        return {"a": "Slot A", "b": "Slot B", "ab": "Both slots (A + B)"}[self.value]


class SlotResolutionError(Exception):
    """The target partition name cannot be determined safely."""


def resolve_targets(
    partition: str,
    scheme: PartitionScheme,
    choice: SlotChoice | None,
    active_slot: str | None,
) -> list[str]:
    """Return the partition names to flash, in the order they should be flashed.

    For BOTH slots with a known active slot, the INACTIVE slot is flashed first, so a
    failure never leaves the active slot half-written.
    """
    if partition not in SUPPORTED_PARTITIONS:
        raise SlotResolutionError(f"'{partition}' is not a supported partition.")

    if scheme is PartitionScheme.A_ONLY:
        return [partition]  # the slot choice does not apply; never add a suffix
    if scheme is PartitionScheme.UNKNOWN:
        raise SlotResolutionError(
            "The partition scheme (A/B or A-only) could not be determined for this device, "
            "so partition names cannot be prepared."
        )

    # A/B
    if choice is None:
        raise SlotResolutionError(f"{partition}: choose a slot (A, B or both).")
    if choice is SlotChoice.A:
        return [f"{partition}_a"]
    if choice is SlotChoice.B:
        return [f"{partition}_b"]
    if active_slot in ("a", "b"):
        inactive = "b" if active_slot == "a" else "a"
        order = [inactive, active_slot]
    else:
        order = ["a", "b"]
    return [f"{partition}_{slot}" for slot in order]
