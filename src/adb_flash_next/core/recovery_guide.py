"""Plain-language steps shown before an ADB sideload.

Recovery menus differ between ROMs and devices, so every step is a general guide and the
ROM's official installation instructions always win. The application NEVER formats data.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuideStep:
    title: str
    bullets: tuple[str, ...]
    warning: bool = False  # highlighted as a risky or destructive manual action


RECOVERY_STEPS: tuple[GuideStep, ...] = (
    GuideStep(
        "1. Boot into recovery",
        (
            "Easiest: open the Reboot page and use 'Reboot to recovery' (not every device supports it).",
            "Or switch the device off and hold the recovery key combination for your model until the "
            "recovery appears. Many devices use Power + Volume Up; some use Volume Down.",
            "From the bootloader (Fastboot) screen you can usually pick 'Recovery mode' with the volume "
            "keys and confirm with Power.",
            "Menus differ between recoveries. Follow your ROM's official installation guide.",
        ),
    ),
    GuideStep(
        "2. Format data (manual, only if your ROM's instructions say so)",
        (
            "WARNING: formatting data ERASES EVERYTHING on the device, including internal storage "
            "(photos, apps, settings). Back up first.",
            "Many ROM guides require it when coming from another ROM or when encryption differs. "
            "If your guide does not mention it, do not do it.",
            "LineageOS-style recovery: Factory reset, then 'Format data / factory reset', then confirm.",
            "TWRP: Wipe, then 'Format Data', then type yes. (A normal wipe is not the same as Format Data.)",
            "Other recoveries: look for 'Format data' or 'Wipe data'.",
            "This application never formats data for you.",
        ),
        warning=True,
    ),
    GuideStep(
        "3. Start ADB sideload on the device",
        (
            "LineageOS-style recovery: Apply update, then 'Apply from ADB'.",
            "TWRP: Advanced, then 'ADB Sideload' (swipe to start).",
            "Other recoveries: look for 'Apply update', 'ADB sideload' or 'Sideload'.",
            "The screen should say it is waiting for a package. This app detects the device in "
            "sideload mode automatically.",
        ),
    ),
    GuideStep(
        "4. Come back here",
        (
            "Wait until the status above says the device is in sideload mode.",
            "Tick the confirmation and press 'Start sideload'. Keep the cable connected and do not "
            "lock or unplug the phone while it transfers.",
            "Some recoveries seem to stall around 47% or end the transfer early; this can be normal. "
            "Check the phone's screen for the real install result.",
        ),
    ),
)


# Same steps for the Auto Flash page (wording adapted to its own buttons).
AUTO_FLASH_STEPS: tuple[GuideStep, ...] = (
    GuideStep(
        "1. Boot into recovery",
        (
            "Easiest: press 'Reboot to recovery' (not every device supports it).",
            "Or switch the device off and hold the recovery key combination for your model until the "
            "recovery appears. Many devices use Power + Volume Up; some use Volume Down.",
            "From the bootloader (Fastboot) screen you can usually pick 'Recovery mode' with the volume "
            "keys and confirm with Power.",
            "Menus differ between recoveries. Follow your ROM's official installation guide.",
        ),
    ),
    RECOVERY_STEPS[1],  # format data: manual only, the app never does it
    RECOVERY_STEPS[2],  # start ADB sideload on the device
    GuideStep(
        "4. Come back here",
        (
            "Press 'Sideload'. The app checks that the device is in ADB sideload mode and only then "
            "sends the ZIP.",
            "Keep the cable connected and do not lock or unplug the phone while it transfers.",
            "Some recoveries seem to stall around 47% or end the transfer early; this can be normal. "
            "Check the phone's screen for the real install result.",
            "When the install finishes, choose 'Reboot system now' on the phone. The first start can "
            "take several minutes: the app stays at 99% until Android has fully started.",
        ),
    ),
)
