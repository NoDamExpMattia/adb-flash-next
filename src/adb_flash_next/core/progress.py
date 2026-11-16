"""Overall workflow progress for the ring on the Dashboard.

The ring covers the WHOLE installation, not just one transfer. 100% is reserved for the
final verified state (Android booted); everything before it stays at or below 99%.
"""
from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    IDLE = "idle"
    PREPARE = "prepare"
    FLASH = "flash"
    SIDELOAD = "sideload"
    FINISHING = "finishing"  # sideload done, final verification still pending
    VERIFIED = "verified"  # Android confirmed running: the only state that reaches 100%


PREPARE_END = 5.0
FLASH_END = 35.0
SIDELOAD_END = 90.0
FINISHING_VALUE = 99.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def overall_percent(phase: Phase, fraction: float = 0.0, include_flash: bool = False) -> float:
    """Map a phase and its own 0..1 progress to the overall 0..100 value.

    include_flash: whether a Fastboot flashing phase is part of this run. Without it the
    sideload phase starts right after preparation instead of after flashing.
    """
    fraction = _clamp01(fraction)
    if phase is Phase.IDLE:
        return 0.0
    if phase is Phase.PREPARE:
        return PREPARE_END * fraction
    if phase is Phase.FLASH:
        if not include_flash:
            return PREPARE_END
        return PREPARE_END + (FLASH_END - PREPARE_END) * fraction
    if phase is Phase.SIDELOAD:
        start = FLASH_END if include_flash else PREPARE_END
        return start + (SIDELOAD_END - start) * fraction
    if phase is Phase.FINISHING:
        return FINISHING_VALUE
    return 100.0  # Phase.VERIFIED
