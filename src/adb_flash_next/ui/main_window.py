"""Main window: Material 3 Expressive navigation rail + stacked pages + background tasks."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
<<<<<<< HEAD
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QWidget
=======
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QWidget
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b

from adb_flash_next.config.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_SIZE,
    MIN_WINDOW_SIZE,
)
from adb_flash_next.config.settings import Settings
from adb_flash_next.core.fastboot_executor import FlashRunResult
<<<<<<< HEAD
from adb_flash_next.core.flash_plan import FlashPlan, PartitionSelection, build_plan
=======
from adb_flash_next.core.flash_plan import FlashPlan, PartitionSelection, build_plan, device_identity
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
from adb_flash_next.core.models import DeviceInfo, Transport
from adb_flash_next.core.platform_tools import PlatformTools, check_directory, locate
from adb_flash_next.core.progress import Phase, overall_percent
from adb_flash_next.core.reboot import RebootAction, availability, run_reboot
from adb_flash_next.core.sideload import (
    LEVEL_ERROR,
    SideloadOutcome,
    SideloadResult,
    sideload_readiness,
    validate_rom_zip,
)
from adb_flash_next.core.utilities import ACTIONS, build_utility_plan
from adb_flash_next.ui.dialogs.plan_dialog import PlanDialog
from adb_flash_next.ui.dialogs.sideload_dialog import SideloadDialog
from adb_flash_next.ui.m3.nav_rail import NavigationRail
from adb_flash_next.ui.pages.dashboard_page import DashboardPage
from adb_flash_next.ui.pages.images_page import ImagesPage
from adb_flash_next.ui.pages.install_page import InstallPage
from adb_flash_next.ui.pages.reboot_page import RebootPage
from adb_flash_next.ui.pages.settings_page import SettingsPage
from adb_flash_next.ui.pages.utilities_page import UtilitiesPage
<<<<<<< HEAD
from adb_flash_next.ui.theme import apply_theme, theme_manager
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
from adb_flash_next.workers.base_worker import FunctionWorker
from adb_flash_next.workers.detection_worker import DetectionWorker
from adb_flash_next.workers.fastboot_worker import FastbootWorker
from adb_flash_next.workers.sideload_worker import SideloadWorker


class MainWindow(QMainWindow):
    def __init__(self, start_services: bool = True) -> None:
        """`start_services=False` skips Platform-Tools lookup and device polling (used by tools/smoke_test.py)."""
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(*MIN_WINDOW_SIZE)

        self._settings = Settings()
        self._settings.load()
        self._tools: PlatformTools | None = None
        self._detector: DetectionWorker | None = None
        self._tasks: list[FunctionWorker] = []
        self._sideload_worker: SideloadWorker | None = None
        self._fastboot_worker: FastbootWorker | None = None
        self._job_kind = ""  # "flash" or "utility" while a Fastboot job runs
        self._busy_name: str | None = None  # only one operation may run at a time
        self._last_percent = 0.0

        # Current inputs of the 'Flash partitions' plan.
        self._device: DeviceInfo | None = None
        self._selections: list[PartitionSelection] = []
        self._plan: FlashPlan | None = None

        self.dashboard = DashboardPage()
        self.settings_page = SettingsPage()
        self.images_page = ImagesPage()
        self.utilities_page = UtilitiesPage()
        self.reboot_page = RebootPage()
        self.install_page = InstallPage()

        # (label, rail icon, page)
        self._pages: list[tuple[str, str, QWidget]] = [
            ("Dashboard", "dashboard", self.dashboard),
            ("Images", "images", self.images_page),
            ("Utilities", "utilities", self.utilities_page),
            ("Reboot", "reboot", self.reboot_page),
            ("Install", "install", self.install_page),
            ("Settings", "settings", self.settings_page),
        ]

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        for _label, _icon, page in self._pages:
            self._stack.addWidget(page)

        self._rail = NavigationRail([(label, icon) for label, icon, _page in self._pages])
        self._rail.current_changed.connect(self._stack.setCurrentIndex)

        root.addWidget(self._rail)
        root.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self.settings_page.directory_chosen.connect(self._on_directory_chosen)
        self.settings_page.autodetect_requested.connect(self._on_autodetect)
<<<<<<< HEAD
        self.settings_page.appearance_changed.connect(self._on_appearance_changed)
        theme_manager().changed.connect(self._on_theme_changed)
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
        self.dashboard.refresh_requested.connect(self._on_refresh)
        self.dashboard.device_selected.connect(self._on_device_selected)
        self.images_page.selections_changed.connect(self._on_selections_changed)
        self.images_page.flash_requested.connect(self._on_flash_requested)
        self.images_page.stop_requested.connect(self._on_stop_requested)
        self.utilities_page.utility_requested.connect(self._on_utility_requested)
        self.reboot_page.reboot_requested.connect(self._on_reboot_requested)
        self.install_page.sideload_requested.connect(self._on_sideload_requested)
        self.install_page.cancel_requested.connect(self._on_sideload_cancel)

<<<<<<< HEAD
        self.settings_page.set_appearance(self._settings.theme_seed, self._settings.theme_mode)
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
        self.show_page(0)
        self.dashboard.log("INFO", f"{APP_NAME} {APP_VERSION} started.")
        self.images_page.publish()
        if start_services:
            QTimer.singleShot(0, self._startup)

    # ------------------------------------------------------------------ navigation
    def show_page(self, index: int) -> None:
        """Select a page in both the rail and the stack."""
        self._rail.set_current(index)

    # ---------------------------------------------------------- device and plan state
    def _on_device_selected(self, device: DeviceInfo | None) -> None:
        self._device = device
        self.images_page.set_device(device)
        self.utilities_page.set_device(device)
        self.reboot_page.set_device(device)
        self.install_page.set_device(device)
        self._rebuild_plan()

    def _on_selections_changed(self, selections: list[PartitionSelection]) -> None:
        self._selections = list(selections)
        self._rebuild_plan()

    def _rebuild_plan(self) -> None:
        self._plan = build_plan(self._device, self._selections)
        self.images_page.set_plan_status(self._plan)

    # ----------------------------------------------------------- one operation at a time
    def _begin(self, name: str, can_stop: bool = False) -> bool:
        if self._busy_name is not None:
            self.dashboard.log(
                "WARNING", f"Another operation is running ({self._busy_name}). Wait for it to finish."
            )
            return False
        self._busy_name = name
        self.images_page.set_busy(True, can_stop=can_stop)
        self.utilities_page.set_busy(True)
        self.reboot_page.set_busy(True)
        return True

    def _end(self) -> None:
        self._busy_name = None
        self.images_page.set_busy(False)
        self.utilities_page.set_busy(False)
        self.reboot_page.set_busy(False)

<<<<<<< HEAD
    # ------------------------------------------------------------------ appearance
    def _on_appearance_changed(self, seed: str, mode: str) -> None:
        """The user picked a colour or a mode in Settings: apply it live and remember it."""
        app = QApplication.instance()
        if app is None:
            return
        self._settings.theme_seed = seed
        self._settings.theme_mode = mode
        apply_theme(app, self._settings.theme_seed, self._settings.theme_mode == "dark")
        if not self._settings.save():
            self.dashboard.log("WARNING", f"Could not save settings to {self._settings.path}")
        self.dashboard.log("INFO", f"Theme changed: {self._settings.theme_mode} mode, accent {self._settings.theme_seed}.")

    def _on_theme_changed(self) -> None:
        """Re-render every page that baked colours into its labels."""
        for page in (self.dashboard, self.images_page, self.utilities_page, self.install_page, self.settings_page):
            page.apply_theme()
        self.update()

=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
    # ------------------------------------------------------------ background tasks
    def _run_task(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_failure: Callable[[str], None],
    ) -> None:
        worker = FunctionWorker(func)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_failure)
        worker.finished.connect(lambda w=worker: self._tasks.remove(w) if w in self._tasks else None)
        self._tasks.append(worker)
        worker.start()

    # -------------------------------------------------------------- platform-tools
    def _startup(self) -> None:
        configured = self._settings.platform_tools_dir
        self.settings_page.show_checking()
        self._run_task(
            lambda: locate(configured),
            self._on_located,
            lambda message: self._on_tools_failed(f"Platform-Tools lookup failed: {message}"),
        )

    def _on_located(self, result: tuple[PlatformTools | None, list[str]]) -> None:
        tools, messages = result
        for message in messages:
            self.dashboard.log("INFO" if tools else "WARNING", message)
        if tools:
            self._apply_tools(tools)
        else:
            self._on_tools_failed("No working Platform-Tools found. Select the folder in Settings.")

    def _on_tools_failed(self, message: str) -> None:
        self._stop_detector()
        self._tools = None
        self.settings_page.show_error(message)
        self.dashboard.log("ERROR", message)
        self.dashboard.set_tools_missing()

    def _apply_tools(self, tools: PlatformTools) -> None:
        self._tools = tools
        self.settings_page.show_tools(tools)
        self.dashboard.log(
            "SUCCESS",
            f"Platform-Tools ready: {tools.directory} "
            f"(adb {tools.adb_version or 'version unknown'}; "
            f"fastboot {tools.fastboot_version or 'version unknown'})",
        )
        self._start_detection(tools)

    def _remember_directory(self, tools: PlatformTools) -> None:
        self._settings.platform_tools_dir = str(tools.directory)
        if not self._settings.save():
            self.dashboard.log("WARNING", f"Could not save settings to {self._settings.path}")

    def _on_directory_chosen(self, directory: str) -> None:
        self.settings_page.show_checking()

        def on_success(tools: PlatformTools) -> None:
            self._remember_directory(tools)
            self._apply_tools(tools)

        self._run_task(
            lambda: check_directory(Path(directory)),
            on_success,
            lambda message: self._on_tools_failed(message),
        )

    def _on_autodetect(self) -> None:
        self.settings_page.show_checking()

        def on_success(result: tuple[PlatformTools | None, list[str]]) -> None:
            tools, messages = result
            for message in messages:
                self.dashboard.log("INFO" if tools else "WARNING", message)
            if tools:
                self._remember_directory(tools)
                self._apply_tools(tools)
            else:
                self._on_tools_failed("No working Platform-Tools found. Select the folder manually.")

        self._run_task(
            lambda: locate(None),
            on_success,
            lambda message: self._on_tools_failed(f"Platform-Tools lookup failed: {message}"),
        )

    # ------------------------------------------------------------------ detection
    def _start_detection(self, tools: PlatformTools) -> None:
        self._stop_detector()
        self.dashboard.reset_devices()
        detector = DetectionWorker(tools)
        detector.devices_changed.connect(self.dashboard.show_poll_result)
        detector.log_message.connect(self.dashboard.log)
        self._detector = detector
        detector.start()

    def _stop_detector(self) -> None:
        if self._detector is not None:
            detector = self._detector
            self._detector = None
            detector.stop()
            detector.wait(8000)

    def _on_refresh(self) -> None:
        if self._detector is not None:
            self._detector.request_refresh()
        else:
            self.dashboard.log("WARNING", "Platform-Tools are not configured; nothing to refresh.")

    # ------------------------------------------------------------------- progress
    def _show_progress(self, percent: float, running: bool, operation: str) -> None:
        """Keep the Dashboard ring and the Install page ring in step."""
        self._last_percent = percent
        self.dashboard.set_progress(percent)
        self.dashboard.set_progress_running(running)
        self.dashboard.set_operation(operation)
        self.install_page.set_progress(percent)
        self.install_page.set_wavy(running)
        self.install_page.set_status(operation)

    # ------------------------------------------------- Fastboot jobs (flash / utilities)
    def _on_flash_requested(self) -> None:
        plan = self._plan
        if plan is None:
            return
        self._confirm_and_run(plan, "Review before flashing", "Start flashing", "flash")

    def _on_utility_requested(self, key: str, path: object) -> None:
        action = ACTIONS.get(key)
        if action is None:
            self.dashboard.log("ERROR", f"Unknown utility: {key}")
            return
        plan = build_utility_plan(self._device, key, Path(path) if path else None)
        self._confirm_and_run(plan, f"Review: {action.label}", "Run command", "utility")

    def _confirm_and_run(self, plan: FlashPlan, title: str, start_text: str, kind: str) -> None:
        if self._busy_name is not None:
            self.dashboard.log(
                "WARNING", f"Another operation is running ({self._busy_name}). Wait for it to finish."
            )
            return
        tools = self._tools
        if tools is None:
            self.dashboard.log("ERROR", "Fastboot needs Platform-Tools. Select them in Settings.")
            return

        dialog = PlanDialog(plan, title=title, start_text=start_text, parent=self)
        if not bool(dialog.exec()):  # 1 = accepted, 0 = rejected
            return

        # The device may have changed while the dialog was open: check again before running anything.
        device = self.dashboard.selected_device()
        if (
            device is None
            or device.serial != plan.device_serial
            or device.transport is not Transport.FASTBOOT
        ):
            self.dashboard.log(
                "ERROR", "The selected device changed or left Fastboot mode. Nothing was run."
            )
            return
<<<<<<< HEAD
=======
        current_identity = device_identity(device)
        planned_identity = {
            "device_serial": plan.device_serial,
            "device_label": plan.device_label,
            "mode_text": plan.mode_text,
            "scheme_text": plan.scheme_text,
            "slot_text": plan.slot_text,
        }
        if current_identity != planned_identity:
            self.dashboard.log(
                "WARNING",
                "The device details changed while the review was open. Nothing was run; review the updated plan and try again.",
            )
            return
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
        self._start_fastboot_job(tools, plan, kind)

    def _start_fastboot_job(self, tools: PlatformTools, plan: FlashPlan, kind: str) -> None:
        if plan.device_serial is None or not self._begin(kind, can_stop=(kind == "flash")):
            return
        self._job_kind = kind
        worker = FastbootWorker(tools, plan.device_serial, plan.steps)
        worker.step_started.connect(self._on_fastboot_step)
        worker.log_message.connect(self.dashboard.log)
        worker.run_finished.connect(self._on_fastboot_finished)
        self._fastboot_worker = worker
        if self._detector is not None:
            self._detector.pause()  # polling must not interfere with flashing
        if kind == "flash":
            start = overall_percent(Phase.PREPARE, 1.0)
            self._show_progress(start, True, "Starting...")
        else:
            self._show_progress(self._last_percent, True, "Starting...")
        self.dashboard.log("INFO", f"Starting {len(plan.steps)} step(s) on {plan.device_serial}.")
        worker.start()

    def _on_fastboot_step(self, index: int, total: int, description: str) -> None:
        text = f"Step {index + 1}/{total}: {description}"
        if self._job_kind == "flash":
            percent = overall_percent(Phase.FLASH, index / max(total, 1), include_flash=True)
            self._show_progress(percent, True, text)
        else:
            self._show_progress(self._last_percent, True, text)

    def _on_stop_requested(self) -> None:
        worker = self._fastboot_worker
        if worker is None:
            return
        worker.request_stop()
        self.dashboard.log(
            "WARNING", "Stop requested: the current step will finish, then nothing further is run."
        )

    def _on_fastboot_finished(self, result: FlashRunResult) -> None:
        worker = self._fastboot_worker
        self._fastboot_worker = None
        if worker is not None:
            worker.wait(5000)
        if self._detector is not None:
            self._detector.resume()
        kind = self._job_kind
        self._job_kind = ""
        self._end()

        if result.success:
            if kind == "flash":
                percent = overall_percent(Phase.FLASH, 1.0, include_flash=True)
                self._show_progress(percent, False, "Flashing finished. Next: recovery and sideload (Install page).")
            else:
                self._show_progress(self._last_percent, False, "Command finished.")
            self.dashboard.log("SUCCESS", result.message)
            QMessageBox.information(self, "Finished", result.message)
        elif result.stopped:
            self._show_progress(self._last_percent, False, "Stopped before finishing.")
            self.dashboard.log("WARNING", result.message)
            QMessageBox.warning(self, "Stopped", result.message)
        else:
            self._show_progress(self._last_percent, False, "Failed. See the log.")
            self.dashboard.log("ERROR", result.message)
            QMessageBox.warning(self, "Stopped because of an error", result.message)

    # ------------------------------------------------------------------ reboot
    def _on_reboot_requested(self, action: RebootAction) -> None:
        device = self.dashboard.selected_device()
        tools = self._tools
        if tools is None or device is None:
            self.dashboard.log("ERROR", "Reboot needs Platform-Tools and a selected device.")
            return
        usable, reason = availability(action, device)
        if not usable:
            self.dashboard.log("ERROR", f"'{action.label}' is not available: {reason}")
            return

        answer = QMessageBox.question(
            self,
            "Confirm reboot",
            f"Send '{action.label}' to {device.product_text()} ({device.serial})?\n\n{action.description}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not self._begin("reboot"):
            return
        self.dashboard.log("INFO", f"Sending '{action.label}' to {device.serial}...")

        def on_success(result) -> None:
            self._end()
            if result.args:
                self.dashboard.log("INFO", f"$ {result.command_line}")
            output = result.combined_output.strip()
            if output:
                self.dashboard.log("INFO", output)
            if result.ok:
                self.dashboard.log(
                    "SUCCESS",
                    f"'{action.label}' was accepted by {device.serial}. "
                    "Detection will pick the device up again when it reappears.",
                )
            else:
                self.dashboard.log("ERROR", f"'{action.label}' failed: {result.failure_reason()}")

        def on_failure(message: str) -> None:
            self._end()
            self.dashboard.log("ERROR", f"'{action.label}' failed: {message}")

        self._run_task(lambda: run_reboot(tools, device, action), on_success, on_failure)

    # -------------------------------------------------------------------- sideload
    def _on_sideload_requested(self, rom_path: Path) -> None:
        if self._busy_name is not None:
            self.dashboard.log(
                "WARNING", f"Another operation is running ({self._busy_name}). Wait for it to finish."
            )
            return
        tools = self._tools
        if tools is None:
            self.dashboard.log("ERROR", "Sideload needs Platform-Tools. Select them in Settings.")
            return
        check = validate_rom_zip(rom_path)  # re-check: the file may have changed since it was chosen
        if check.level == LEVEL_ERROR:
            self.dashboard.log("ERROR", f"The ROM file cannot be used: {check.message}")
            self.install_page.set_result(f"The ROM file cannot be used: {check.message}", "error")
            return

        # Guided dialog: instructions + live wait for sideload mode. It follows device changes.
        dialog = SideloadDialog(check, self.dashboard.selected_device(), self)
        self.dashboard.device_selected.connect(dialog.set_device)
        try:
            accepted = bool(dialog.exec())  # 1 = accepted, 0 = rejected
        finally:
            self.dashboard.device_selected.disconnect(dialog.set_device)
        if not accepted:
            return

        device = self.dashboard.selected_device()
        ready, text, _hint = sideload_readiness(device)
        if device is None or not ready:
            self.dashboard.log("ERROR", f"Sideload not started: {text}.")
            self.install_page.set_result(f"Sideload not started: {text}.", "error")
            return
        if not self._begin("sideload"):
            return

        self.install_page.set_result("", "info")
        worker = SideloadWorker(tools, device.serial, check.path)
        worker.progress.connect(self._on_sideload_progress)
        worker.log_message.connect(self.dashboard.log)
        worker.sideload_finished.connect(self._on_sideload_finished)
        self._sideload_worker = worker
        if self._detector is not None:
            self._detector.pause()
        self.install_page.set_busy(True)
        self._show_progress(overall_percent(Phase.PREPARE, 1.0), True, "Starting ADB sideload...")
        self.dashboard.log("INFO", f"Starting ADB sideload of {check.path.name} to {device.serial}.")
        worker.start()

    def _on_sideload_progress(self, percent: int) -> None:
        overall = overall_percent(Phase.SIDELOAD, percent / 100.0)
        self._show_progress(overall, True, f"Sending ROM to the device: {percent}%")

    def _on_sideload_cancel(self) -> None:
        worker = self._sideload_worker
        if worker is None:
            return
        answer = QMessageBox.question(
            self,
            "Cancel sideload",
            "Stop sending the ROM?\n\nThe ROM will not be installed. You may need to start ADB sideload "
            "again on the device.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.dashboard.log("WARNING", "Cancelling the sideload...")
            worker.cancel()

    def _on_sideload_finished(self, result: SideloadResult) -> None:
        worker = self._sideload_worker
        self._sideload_worker = None
        if worker is not None:
            worker.wait(5000)
        if self._detector is not None:
            self._detector.resume()
        self.install_page.set_busy(False)
        self._end()

        if result.output_tail and result.outcome is not SideloadOutcome.COMPLETED:
            self.dashboard.log("INFO", f"Last adb output:\n{result.output_tail}")

        if result.outcome is SideloadOutcome.COMPLETED:
            # Never 100% here: the real finish is the device booting Android (checked in a later stage).
            self._show_progress(overall_percent(Phase.FINISHING), False,
                                "Sideload finished. Final verification is still pending.")
            self.dashboard.log("SUCCESS", result.message)
            self.install_page.set_result(result.message, "success")
        elif result.outcome is SideloadOutcome.INCONCLUSIVE:
            last = result.last_percent or 0
            self._show_progress(overall_percent(Phase.SIDELOAD, last / 100.0), False,
                                "Transfer ended. Confirm the result on the phone.")
            self.dashboard.log("WARNING", result.message)
            self.install_page.set_result(result.message, "warning")
        elif result.outcome is SideloadOutcome.CANCELLED:
            self._show_progress(0.0, False, "Cancelled")
            self.dashboard.log("WARNING", result.message)
            self.install_page.set_result(result.message, "warning")
        else:
            last = result.last_percent or 0
            self._show_progress(overall_percent(Phase.SIDELOAD, last / 100.0) if last else 0.0, False,
                                "Sideload failed")
            self.dashboard.log("ERROR", result.message)
            self.install_page.set_result(result.message, "error")

    # ---------------------------------------------------------------------- close
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        fastboot_worker = self._fastboot_worker
        if fastboot_worker is not None and fastboot_worker.isRunning():
            QMessageBox.warning(
                self,
                "Flashing in progress",
                "A Fastboot operation is running. Closing now could leave a partition half-written.\n\n"
                "Wait until it finishes (or use 'Stop after current step' and wait).",
            )
            event.ignore()
            return
        worker = self._sideload_worker
        if worker is not None and worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Sideload in progress",
                "A sideload is still running. Cancel it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            worker.cancel()
            worker.wait(10000)
        self._stop_detector()
        for task in list(self._tasks):
            task.wait(8000)
        super().closeEvent(event)
