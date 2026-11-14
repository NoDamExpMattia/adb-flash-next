"""QApplication setup and main loop."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from adb_flash_next.config.constants import APP_NAME
from adb_flash_next.ui.main_window import MainWindow
from adb_flash_next.ui.theme import apply_theme


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()
