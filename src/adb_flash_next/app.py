"""QApplication setup and main loop."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from adb_flash_next.config.constants import APP_NAME
<<<<<<< HEAD
from adb_flash_next.config.settings import Settings
=======
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b
from adb_flash_next.ui.main_window import MainWindow
from adb_flash_next.ui.theme import apply_theme


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
<<<<<<< HEAD
    settings = Settings()
    settings.load()
    apply_theme(app, settings.theme_seed, settings.theme_mode == "dark")
=======
    apply_theme(app)
>>>>>>> e279f909c2b000f4fe73d0efad7a15caaf8d285b

    window = MainWindow()
    window.show()
    return app.exec()
