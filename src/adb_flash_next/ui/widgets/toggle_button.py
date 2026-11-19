"""A clearly visible on/off button: a drawn M3 pill that morphs when switched on."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from adb_flash_next.ui.m3.button import M3Button


class ToggleButton(M3Button):
    """Filled (red) with `on_text` when ON, tonal with `off_text` when OFF.

    Same basics as a checkbox: isChecked(), setChecked(), toggled(bool).
    """

    def __init__(
        self,
        on_text: str = "On",
        off_text: str = "Off",
        checked: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(off_text, "tonal", height=40, parent=parent)
        self._on_text = on_text
        self._off_text = off_text
        self.setCheckable(True)
        self.setMinimumWidth(128)
        self.toggled.connect(self._sync)
        self.setChecked(checked)
        self._sync(checked)

    def _sync(self, checked: bool) -> None:
        self.setText(self._on_text if checked else self._off_text)
        self.set_variant("filled" if checked else "tonal")
