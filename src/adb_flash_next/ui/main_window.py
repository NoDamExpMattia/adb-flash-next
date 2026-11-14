"""Main window: left sidebar navigation + stacked pages + background tasks."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from adb_flash_next.config.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_SIZE,
    MIN_WINDOW_SIZE,
)
from adb_flash_next.config.settings import Settings
from adb_flash_next.core.platform_tools import PlatformTools, check_directory, locate
from adb_flash_next.ui.pages.dashboard_page import DashboardPage
from adb_flash_next.ui.pages.placeholder_page import PlaceholderPage
from adb_flash_next.ui.pages.settings_page import SettingsPage
from adb_flash_next.ui.widgets.logo import LogoWidget
from adb_flash_next.workers.base_worker import FunctionWorker
from adb_flash_next.workers.detection_worker import DetectionWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(*MIN_WINDOW_SIZE)

        self._settings = Settings()
        self._settings.load()
        self._tools: PlatformTools | None = None
        self._detector: DetectionWorker | None = None
        self._tasks: list[FunctionWorker] = []

        self.dashboard = DashboardPage()
        self.settings_page = SettingsPage()
        self._pages: list[tuple[str, QWidget]] = [
            ("Dashboard", self.dashboard),
            ("Images", PlaceholderPage(
                "Images", "Image selection and partition mapping arrive in Stage 4.")),
            ("Flash", PlaceholderPage(
                "Flash", "Flash plan review, dry run and flashing arrive in Stages 4-5.")),
            ("Install", PlaceholderPage(
                "Install", "Recovery guidance and ROM ZIP sideload arrive in Stage 6.")),
            ("Settings", self.settings_page),
        ]

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        for _label, page in self._pages:
            self._stack.addWidget(page)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self.settings_page.directory_chosen.connect(self._on_directory_chosen)
        self.settings_page.autodetect_requested.connect(self._on_autodetect)
        self.dashboard.refresh_requested.connect(self._on_refresh)

        self.dashboard.log("INFO", f"{APP_NAME} {APP_VERSION} started.")
        QTimer.singleShot(0, self._startup)

    # ------------------------------------------------------------------ sidebar
    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 18, 0, 14)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(16, 0, 16, 0)
        header.setSpacing(10)
        header.addWidget(LogoWidget(40))
        brand = QLabel("ADB Flash\nNext")
        brand.setObjectName("BrandName")
        header.addWidget(brand)
        header.addStretch()
        layout.addLayout(header)
        layout.addSpacing(18)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        for index, (label, _page) in enumerate(self._pages):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, i=index: self._stack.setCurrentIndex(i))
            group.addButton(button)
            layout.addWidget(button)
            self._nav_buttons.append(button)
            if index == 0:
                button.setChecked(True)

        layout.addStretch()
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("Muted")
        version.setContentsMargins(18, 0, 0, 0)
        layout.addWidget(version)
        return sidebar

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
            self._on_tools_failed(
                "No working Platform-Tools found. Select the folder in Settings."
            )

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

    # ---------------------------------------------------------------------- close
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        self._stop_detector()
        for task in list(self._tasks):
            task.wait(8000)
        super().closeEvent(event)
