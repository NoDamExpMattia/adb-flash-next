"""QApplication setup and main loop."""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from adb_flash_next.config.constants import ASSETS_DIR, APP_NAME
from adb_flash_next.config.settings import Settings
from adb_flash_next.ui.main_window import MainWindow
from adb_flash_next.ui.theme import apply_theme

_APP_ID = "NoDamExpMattia.ADBFlashNext"


def _load_app_icon() -> QIcon:
    """The window/taskbar icon: assets/logo.png, else assets/app.ico, else assets/logo.svg."""
    for name in ("logo.png", "app.ico", "logo.svg"):
        path = ASSETS_DIR / name
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    return QIcon()


def _set_windows_app_id() -> None:
    """Lets Windows group the taskbar button under this app's own icon (cosmetic only)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except Exception:  # purely cosmetic: never stop the app because of it
        pass


def run() -> int:
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = _load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    settings = Settings()
    settings.load()
    apply_theme(app, settings.theme_seed, settings.theme_mode == "dark")

    window = MainWindow()
    window.show()
    return app.exec()
