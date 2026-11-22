"""Visual smoke test: builds every page and saves screenshots.

On Windows a window appears for a few seconds while the screenshots are taken.

Run from the project root:
    python tools/smoke_test.py

It needs no phone and no Platform-Tools. Screenshots go to the 'screenshots' folder;
send them (and any error text) when something looks wrong.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

# The offscreen platform has no fonts on Windows (text becomes empty boxes), so only use it elsewhere.
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from adb_flash_next.core.models import (  # noqa: E402
    ConnectionMode,
    DeviceInfo,
    PartitionScheme,
    PollResult,
    Transport,
)
from adb_flash_next.core.image_validator import validate_image  # noqa: E402
from adb_flash_next.core.sideload import SideloadOutcome, SideloadResult, validate_rom_zip  # noqa: E402
from adb_flash_next.core.utilities import build_utility_plan  # noqa: E402
from adb_flash_next.ui.dialogs.plan_dialog import PlanDialog  # noqa: E402
from adb_flash_next.ui.dialogs.sideload_dialog import SideloadDialog  # noqa: E402
from adb_flash_next.ui.main_window import MainWindow  # noqa: E402
from adb_flash_next.ui.theme import apply_theme  # noqa: E402

OUT = ROOT / "screenshots"
failures: list[str] = []


def step(name: str, func) -> None:
    try:
        func()
        print(f"ok    {name}")
    except Exception:  # report and continue so one failure does not hide the others
        failures.append(name)
        print(f"FAIL  {name}")
        traceback.print_exc()


def main() -> int:
    OUT.mkdir(exist_ok=True)
    app = QApplication([])
    apply_theme(app)

    window = MainWindow(start_services=False)
    window.resize(900, 650)
    window.show()
    app.processEvents()

    def shot(name: str) -> None:
        QTest.qWait(550)  # let the rail and button animations finish
        window.grab().save(str(OUT / f"{name}.png"))

    step("dashboard (waiting)", lambda: shot("1_dashboard_waiting"))

    device = DeviceInfo(
        serial="320246836040",
        transport=Transport.FASTBOOT,
        mode=ConnectionMode.FASTBOOT,
        product="sunfish",
        scheme=PartitionScheme.AB,
        scheme_evidence="slot-count=2; current-slot=b",
        active_slot="b",
    )

    def detected() -> None:
        window.dashboard.show_poll_result(PollResult(devices=(device,)))
        window._on_device_selected(device)  # same as the signal; keeps the check independent of signals
        window.dashboard._ring.set_value(62)
        window.dashboard._ring.set_wavy(True)
        window.dashboard.log("SUCCESS", "Sample log line")
        window.dashboard.log("WARNING", "Sample warning")
        shot("2_dashboard_device")

    step("dashboard (device)", detected)

    def images() -> None:
        tmp = Path(tempfile.mkdtemp())
        boot = tmp / "boot.img"
        boot.write_bytes(b"ANDROID!" + bytes(4088))
        window.images_page._rows[0].set_path(boot)
        window.show_page_named("Images")
        shot("3_images")

    step("images", images)

    def utilities() -> None:
        tmp = Path(tempfile.mkdtemp())
        vbmeta = tmp / "vbmeta.img"
        vbmeta.write_bytes(b"AVB0" + bytes(500))
        window.utilities_page._vbmeta = validate_image(vbmeta, "vbmeta")
        window.utilities_page._refresh()
        window.show_page_named("Utilities")
        shot("4_utilities")

    step("utilities", utilities)

    def reboot() -> None:
        window.show_page_named("Reboot")
        shot("5_reboot_fastboot")

    step("reboot", reboot)

    def settings() -> None:
        window.show_page_named("Settings")
        shot("6_settings")

    step("settings", settings)

    zip_path = Path(tempfile.mkdtemp()) / "lineage-sample-rom.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("payload.bin", b"x")
        archive.writestr("META-INF/com/android/metadata", b"x")
    zip_check = validate_rom_zip(zip_path)
    sideload_device = DeviceInfo(
        serial="320246836040",
        transport=Transport.ADB,
        mode=ConnectionMode.SIDELOAD,
        adb_state="sideload",
    )
    recovery_device = DeviceInfo(
        serial="320246836040",
        transport=Transport.ADB,
        mode=ConnectionMode.RECOVERY,
        adb_state="recovery",
    )

    def install() -> None:
        window.install_page._check = zip_check
        window.install_page.set_device(recovery_device)
        window.show_page_named("Install")
        shot("9_install")

    step("install page", install)

    def install_running() -> None:
        window.install_page.set_device(sideload_device)
        window.install_page.set_busy(True)
        window._on_sideload_progress(47)
        shot("10_install_progress_47")
        window.show_page_named("Dashboard")
        shot("11_dashboard_progress_47")

    step("sideload progress", install_running)

    def outcomes() -> None:
        for outcome in SideloadOutcome:
            window._on_sideload_finished(SideloadResult(outcome, f"Sample message for {outcome.value}.", last_percent=47))
        window._on_sideload_finished(SideloadResult(SideloadOutcome.COMPLETED, "Sample finished message."))
        window.show_page_named("Dashboard")
        shot("12_dashboard_after_sideload_99")

    step("sideload outcomes", outcomes)

    def sideload_dialog() -> None:
        dlg = SideloadDialog(zip_check, recovery_device, window)
        dlg.show()
        QTest.qWait(250)
        dlg.grab().save(str(OUT / "13_sideload_dialog_waiting.png"))
        dlg.set_device(sideload_device)
        dlg._ack.setChecked(True)
        QTest.qWait(250)
        dlg.grab().save(str(OUT / "14_sideload_dialog_ready.png"))
        dlg.close()

    step("sideload dialog", sideload_dialog)

    def themes() -> None:
        from adb_flash_next.ui.theme import apply_theme

        for name, seed, dark in (
            ("light_red", "#E5141E", False),
            ("dark_blue", "#2F6FED", True),
            ("light_green", "#2EA44F", False),
            ("light_yellow", "#FFEE00", False),
        ):
            apply_theme(app, seed, dark)
            window._on_theme_changed()  # same as the signal; keeps the check independent of signals
            for label, page_name in (("Dashboard", "dashboard"), ("Auto Flash", "auto_flash"), ("Images", "images"), ("Utilities", "utilities"), ("Reboot", "reboot"), ("Install", "install"), ("Settings", "settings")):
                window.show_page_named(label)
                shot(f"20_{name}_{page_name}")
        apply_theme(app, "#E5141E", True)
        window._on_theme_changed()

    step("themes", themes)

    def auto_flash() -> None:
        from adb_flash_next.core.auto_flash import AutoStage

        page = window.auto_flash_page
        window.show_page_named("Auto Flash")
        shot("30_auto_flash_idle")
        page.set_stage(AutoStage.RECOVERY)
        page.set_progress(35)
        page.set_message("Flashing finished. The procedure is paused. Enter recovery, then press Sideload.", "success")
        shot("31_auto_flash_recovery")
        page.set_stage(AutoStage.BOOT, waiting=True)
        page.set_progress(99)
        page.set_wavy(True)
        page.set_message("", "info")
        shot("32_auto_flash_waiting_for_android_99")
        page.set_stage(AutoStage.FLASHING, failed=True)
        page.set_wavy(False)
        page.set_message("The bootloader is LOCKED: an unlocked bootloader is required. Nothing was run.", "error")
        shot("33_auto_flash_error")
        page.set_stage(AutoStage.DONE)
        page.set_progress(100)
        page.set_message("Done. Android has started and the installation is complete.", "success")
        page.celebrate()
        QTest.qWait(900)
        window.grab().save(str(OUT / "34_auto_flash_done_confetti.png"))
        QTest.qWait(2600)
        page.set_stage(AutoStage.IDLE)
        page.set_progress(0)
        page.set_message("", "info")

    step("auto flash", auto_flash)

    def collapsed() -> None:
        window.show_page_named("Dashboard")
        window._rail.set_expanded(False, animate=False)
        shot("7_rail_collapsed")
        window._rail.set_expanded(True, animate=False)

    step("rail collapsed", collapsed)

    def dialog() -> None:
        dlg = PlanDialog(window._plan, parent=window)
        dlg.show()
        QTest.qWait(250)
        dlg.grab().save(str(OUT / "8_review_dialog_flash.png"))
        dlg.close()
        erase = build_utility_plan(device, "erase_userdata")
        dlg = PlanDialog(erase, title="Review: Erase userdata", start_text="Run command", parent=window)
        dlg.show()
        QTest.qWait(250)
        dlg.grab().save(str(OUT / "8b_review_dialog_erase.png"))
        dlg.close()

    step("review dialogs", dialog)

    window._rail.set_expanded(True, animate=False)
    window.close()
    print()
    print("Screenshots saved in:", OUT)
    if failures:
        print("FAILED STEPS:", ", ".join(failures))
        return 1
    print("All steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
