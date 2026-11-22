"""Runs the Auto Flash procedure. Any failed check or command STOPS it with a clear message.

Stages: check device + bootloader -> flash -> (pause in recovery, user works on the phone) ->
sideload -> wait for Android -> 100%. A running flash command is never interrupted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox, QWidget

from adb_flash_next.core.adb_client import AdbClient
from adb_flash_next.core.auto_flash import AutoStage, BootResult, choose_sideload_serial
from adb_flash_next.core.fastboot_executor import FlashRunResult
from adb_flash_next.core.flash_plan import build_plan
from adb_flash_next.core.image_validator import format_size
from adb_flash_next.core.models import ConnectionMode, DeviceInfo, Transport
from adb_flash_next.core.platform_tools import PlatformTools
from adb_flash_next.core.progress import Phase, overall_percent
from adb_flash_next.core.reboot import FASTBOOT_ACTIONS, run_reboot
from adb_flash_next.core.sideload import (
    LEVEL_ERROR,
    LEVEL_WARNING,
    SideloadOutcome,
    SideloadResult,
    validate_rom_zip,
)
from adb_flash_next.ui.dialogs.plan_dialog import PlanDialog
from adb_flash_next.ui.pages.auto_flash_page import AutoFlashPage
from adb_flash_next.workers.base_worker import FunctionWorker
from adb_flash_next.workers.boot_watch_worker import BootWatchWorker
from adb_flash_next.workers.fastboot_worker import FastbootWorker
from adb_flash_next.workers.sideload_worker import SideloadWorker

_LOG_LEVEL = {"info": "INFO", "success": "SUCCESS", "warning": "WARNING", "error": "ERROR"}


@dataclass
class AutoFlashServices:
    """What the controller needs from the main window (keeps the two loosely coupled)."""

    parent: QWidget
    tools: Callable[[], PlatformTools | None]
    selected_device: Callable[[], DeviceInfo | None]
    begin: Callable[[str], bool]  # lock the other pages; False if another operation runs
    end: Callable[[], None]
    pause_detection: Callable[[], None]
    resume_detection: Callable[[], None]
    log: Callable[[str, str], None]
    show_progress: Callable[[float, bool, str], None]


class AutoFlashController(QObject):
    def __init__(self, page: AutoFlashPage, services: AutoFlashServices, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self._s = services
        self._stage = AutoStage.IDLE
        self._failed = False
        self._job_serial: str | None = None  # Fastboot serial of the device being flashed
        self._adb_serial: str | None = None  # ADB serial that received (or will receive) the ZIP
        self._rom_path = None
        self._last_percent = 0.0
        self._fastboot_worker: FastbootWorker | None = None
        self._sideload_worker: SideloadWorker | None = None
        self._boot_worker: BootWatchWorker | None = None
        self._tasks: list[FunctionWorker] = []

        page.start_requested.connect(self.on_start)
        page.stop_requested.connect(self.on_stop)
        page.reboot_recovery_requested.connect(self.on_reboot_recovery)
        page.sideload_requested.connect(self.on_sideload)
        page.cancel_sideload_requested.connect(self.on_cancel_sideload)
        page.check_boot_requested.connect(self.on_check_boot)
        page.stop_waiting_requested.connect(self.on_stop_waiting)
        page.reset_requested.connect(self.on_reset)

    # ------------------------------------------------------------------ helpers
    def is_flashing(self) -> bool:
        return self._fastboot_worker is not None and self._fastboot_worker.isRunning()

    def is_sideloading(self) -> bool:
        return self._sideload_worker is not None and self._sideload_worker.isRunning()

    def shutdown(self) -> None:
        """Stop everything that can be stopped safely before the app closes."""
        if self._sideload_worker is not None:
            self._sideload_worker.cancel()
            self._sideload_worker.wait(10000)
        if self._boot_worker is not None:
            self._boot_worker.cancel()
            self._boot_worker.wait(5000)
        for task in list(self._tasks):
            task.wait(5000)
        self._page.shutdown()

    def _say(self, text: str, level: str) -> None:
        self._page.set_message(text, level)
        if text:
            self._s.log(_LOG_LEVEL.get(level, "INFO"), text)

    def _progress(self, percent: float, running: bool, text: str) -> None:
        self._last_percent = percent
        self._page.set_progress(percent)
        self._page.set_wavy(running)
        self._page.set_status(text)
        self._s.show_progress(percent, running, text)

    def _enter(self, stage: AutoStage, *, failed: bool = False, waiting: bool = False) -> None:
        self._stage = stage
        self._failed = failed
        self._page.set_stage(stage, failed=failed, waiting=waiting)

    def _fail(self, message: str, *, warning: bool = False) -> None:
        """Stop the procedure at the current stage and explain why."""
        self._enter(self._stage, failed=True)
        self._progress(self._last_percent, False, "Stopped. See the message below.")
        self._say(message, "warning" if warning else "error")
        self._s.end()

    def _run_task(self, func, on_success, on_failure) -> None:
        worker = FunctionWorker(func)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_failure)
        worker.finished.connect(lambda w=worker: self._tasks.remove(w) if w in self._tasks else None)
        self._tasks.append(worker)
        worker.start()

    # ------------------------------------------------------------ 1. review + start
    def on_start(self) -> None:
        if self._stage is not AutoStage.IDLE:
            return
        tools = self._s.tools()
        if tools is None:
            self._say("Platform-Tools were not found. Select them in Settings.", "error")
            return
        zip_path = self._page.zip_path()
        if zip_path is None:
            self._say("Choose the ROM ZIP first.", "error")
            return
        check = validate_rom_zip(zip_path)
        if check.level == LEVEL_ERROR:
            self._say(f"The ROM file cannot be used: {check.message}", "error")
            return

        device = self._s.selected_device()
        plan = build_plan(device, self._page.selections())
        size = format_size(check.size) if check.size is not None else "size unknown"
        extra = [
            f"ROM ZIP: {check.path.name} ({size})",
            "Bootloader: it must answer 'unlocked: yes' to fastboot getvar unlocked, otherwise nothing is flashed.",
            "After flashing, the procedure pauses in recovery. You format data by hand only if your ROM "
            "requires it, then start ADB sideload on the phone. The app never formats data.",
            "The ZIP is sent only when the device is in ADB sideload mode. Progress stays at 99% until "
            "Android has fully started.",
        ]
        if check.level == LEVEL_WARNING:
            extra.append(f"WARNING about the ZIP: {check.message}")
        dialog = PlanDialog(
            plan, title="Auto Flash: review", start_text="Start Auto Flash",
            extra_summary=extra, parent=self._s.parent,
        )
        if not bool(dialog.exec()):  # 1 = accepted, 0 = rejected
            return

        # The device may have changed while the dialog was open: verify again before touching anything.
        device = self._s.selected_device()
        if device is None or device.serial != plan.device_serial or device.transport is not Transport.FASTBOOT:
            self._say("The selected device changed or left Fastboot mode. Nothing was run.", "error")
            return
        if not self._s.begin("auto flash"):
            return

        self._job_serial = plan.device_serial
        self._adb_serial = None
        self._rom_path = check.path
        self._say("", "info")
        self._enter(AutoStage.CHECKING)
        self._progress(overall_percent(Phase.PREPARE, 0.5), True, "Checking the device and the bootloader...")
        worker = FastbootWorker(tools, plan.device_serial, plan.steps, require_unlocked=True)
        worker.step_started.connect(self._on_step)
        worker.log_message.connect(self._s.log)
        worker.run_finished.connect(self._on_flash_finished)
        self._fastboot_worker = worker
        self._s.pause_detection()  # polling must not interfere with flashing
        self._s.log("INFO", f"Auto Flash started for {plan.device_serial}: {len(plan.steps)} flash step(s).")
        worker.start()

    # ------------------------------------------------------------------ 2. flashing
    def _on_step(self, index: int, total: int, description: str) -> None:
        if self._stage is AutoStage.CHECKING:
            self._enter(AutoStage.FLASHING)
        percent = overall_percent(Phase.FLASH, index / max(total, 1), include_flash=True)
        self._progress(percent, True, f"Flashing {index + 1}/{total}: {description}")

    def on_stop(self) -> None:
        worker = self._fastboot_worker
        if worker is None:
            return
        worker.request_stop()
        self._s.log("WARNING", "Stop requested: the current step will finish, then nothing further is run.")

    def _on_flash_finished(self, result: FlashRunResult) -> None:
        worker = self._fastboot_worker
        self._fastboot_worker = None
        if worker is not None:
            worker.wait(5000)
        self._s.resume_detection()
        if not result.success:
            self._fail(result.message, warning=result.stopped)
            return
        # Pause here: the rest happens on the phone. The ring holds still (manual action).
        self._enter(AutoStage.RECOVERY)
        self._progress(
            overall_percent(Phase.FLASH, 1.0, include_flash=True), False,
            "Flashing finished. Paused: continue in recovery.",
        )
        self._say(
            "Flashing finished. The procedure is paused. Enter recovery, format data only if your ROM "
            "requires it, start ADB sideload on the phone, then press Sideload.",
            "success",
        )

    # ------------------------------------------------------- 3. recovery (manual part)
    def on_reboot_recovery(self) -> None:
        tools = self._s.tools()
        if self._stage is not AutoStage.RECOVERY or tools is None or self._job_serial is None:
            return
        answer = QMessageBox.question(
            self._s.parent, "Reboot to recovery",
            f"Send 'fastboot reboot recovery' to {self._job_serial}?\n\nNot every device supports it. "
            "If it fails, enter recovery by hand (step 1).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        action = next(a for a in FASTBOOT_ACTIONS if a.key == "fb_recovery")
        device = DeviceInfo(serial=self._job_serial, transport=Transport.FASTBOOT, mode=ConnectionMode.FASTBOOT)
        self._say("Sending 'fastboot reboot recovery'...", "info")
        self._run_task(
            lambda: run_reboot(tools, device, action),
            self._on_reboot_result,
            lambda message: self._say(f"Could not reboot to recovery: {message}. Enter recovery by hand (step 1).", "warning"),
        )

    def _on_reboot_result(self, result) -> None:
        if result.args:
            self._s.log("INFO", f"$ {result.command_line}")
        output = result.combined_output.strip()
        if output:
            self._s.log("INFO", output)
        if result.ok:
            self._say("The device accepted the command and should restart into recovery.", "info")
        else:
            self._say(
                f"Could not reboot to recovery ({result.failure_reason()}). Enter recovery by hand (step 1).",
                "warning",
            )

    # ---------------------------------------------------------------- 4. sideload
    def on_sideload(self) -> None:
        """Check the device is in ADB sideload mode and, only if it is, send the ZIP."""
        tools = self._s.tools()
        if self._stage is not AutoStage.RECOVERY or tools is None:
            return
        self._page.set_sideload_enabled(False)
        self._say("Checking that the device is in ADB sideload mode...", "info")
        self._run_task(
            lambda: AdbClient(tools.adb).list_devices(),
            self._on_adb_entries,
            self._on_adb_entries_failed,
        )

    def _on_adb_entries_failed(self, message: str) -> None:
        self._page.set_sideload_enabled(True)
        self._say(f"Could not ask ADB for the device list: {message}. Nothing was sent.", "error")

    def _on_adb_entries(self, result) -> None:
        self._page.set_sideload_enabled(True)
        entries, listing = result
        if not listing.ok:
            self._say(f"Could not ask ADB for the device list: {listing.failure_reason()}. Nothing was sent.", "error")
            return
        if self._job_serial is None:
            return
        choice = choose_sideload_serial(entries, self._job_serial)
        if choice.serial is None:
            # Nothing is sent. The procedure stays paused here so the user can fix it and press Sideload again.
            self._say(choice.message, "error")
            return
        if choice.needs_confirmation:
            answer = QMessageBox.question(
                self._s.parent, "Different serial number",
                f"{choice.message}\n\nSend the ROM to the device with serial {choice.serial}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._say("Nothing was sent: the different serial number was not confirmed.", "warning")
                return
        self._start_sideload(choice.serial)

    def _start_sideload(self, serial: str) -> None:
        tools = self._s.tools()
        if tools is None or self._rom_path is None:
            return
        self._adb_serial = serial
        self._say("", "info")
        self._enter(AutoStage.SIDELOAD)
        worker = SideloadWorker(tools, serial, self._rom_path)
        worker.progress.connect(self._on_sideload_progress)
        worker.log_message.connect(self._s.log)
        worker.sideload_finished.connect(self._on_sideload_finished)
        self._sideload_worker = worker
        self._s.pause_detection()
        self._progress(overall_percent(Phase.SIDELOAD, 0.0, include_flash=True), True, "Starting ADB sideload...")
        self._s.log("INFO", f"Sending {self._rom_path.name} to {serial}.")
        worker.start()

    def _on_sideload_progress(self, percent: int) -> None:
        overall = overall_percent(Phase.SIDELOAD, percent / 100.0, include_flash=True)
        self._progress(overall, True, f"Sending the ROM to the device: {percent}%")

    def on_cancel_sideload(self) -> None:
        worker = self._sideload_worker
        if worker is None:
            return
        answer = QMessageBox.question(
            self._s.parent, "Cancel sideload",
            "Stop sending the ROM?\n\nThe ROM will not be installed. You may need to start ADB sideload "
            "again on the device.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._s.log("WARNING", "Cancelling the sideload...")
            worker.cancel()

    def _on_sideload_finished(self, result: SideloadResult) -> None:
        worker = self._sideload_worker
        self._sideload_worker = None
        if worker is not None:
            worker.wait(5000)
        self._s.resume_detection()
        if result.output_tail and result.outcome is not SideloadOutcome.COMPLETED:
            self._s.log("INFO", f"Last adb output:\n{result.output_tail}")

        if result.outcome is SideloadOutcome.COMPLETED:
            self._say(result.message, "info")
            self._start_boot_watch()
        elif result.outcome is SideloadOutcome.INCONCLUSIVE:
            # Unclear result: do not assume success. The user decides when to check for Android.
            self._enter(AutoStage.BOOT, waiting=False)
            last = result.last_percent or 0
            self._progress(overall_percent(Phase.SIDELOAD, last / 100.0, include_flash=True), False,
                           "Transfer ended. Confirm the result on the phone.")
            self._say(result.message + " When the phone has restarted into Android, press Check again.", "warning")
            self._s.end()
        elif result.outcome is SideloadOutcome.CANCELLED:
            self._fail(result.message, warning=True)
        else:
            self._fail(result.message)

    # ------------------------------------------------------------ 5. wait for Android
    def _start_boot_watch(self) -> None:
        tools = self._s.tools()
        if tools is None or self._adb_serial is None:
            return
        self._enter(AutoStage.BOOT, waiting=True)
        # 99%, never more: the ring only reaches 100% when Android confirmed it has started.
        self._progress(overall_percent(Phase.FINISHING), True, "Waiting for Android to start...")
        worker = BootWatchWorker(tools, self._adb_serial)
        worker.status.connect(self._on_boot_status)
        worker.watch_finished.connect(self._on_boot_result)
        self._boot_worker = worker
        worker.start()

    def _on_boot_status(self, _state: str, message: str) -> None:
        self._page.set_status(message)
        self._s.show_progress(overall_percent(Phase.FINISHING), True, message)

    def _on_boot_result(self, result: BootResult) -> None:
        worker = self._boot_worker
        self._boot_worker = None
        if worker is not None:
            worker.wait(5000)
        if result.booted:
            self._enter(AutoStage.DONE)
            self._progress(overall_percent(Phase.VERIFIED), False, "Android has started.")
            self._say("Done. Android has started and the installation is complete.", "success")
            self._page.celebrate()
            self._s.end()
            return
        # Not confirmed: stay at 99%, explain, and let the user re-check by hand.
        self._enter(AutoStage.BOOT, waiting=False)
        self._progress(overall_percent(Phase.FINISHING), False, "Waiting for confirmation.")
        self._say(result.message, "warning")
        self._s.end()

    def on_check_boot(self) -> None:
        if self._stage is not AutoStage.BOOT or self._boot_worker is not None or self._adb_serial is None:
            return
        if not self._s.begin("auto flash"):
            return
        self._say("", "info")
        self._start_boot_watch()

    def on_stop_waiting(self) -> None:
        if self._boot_worker is not None:
            self._boot_worker.cancel()

    # ---------------------------------------------------------------------- reset
    def on_reset(self) -> None:
        """Back to the start. Not allowed while a command is running."""
        if self.is_flashing() or self.is_sideloading() or self._boot_worker is not None:
            return
        self._s.end()
        self._job_serial = None
        self._adb_serial = None
        self._rom_path = None
        self._say("", "info")
        self._enter(AutoStage.IDLE)
        self._progress(0.0, False, "Idle")
