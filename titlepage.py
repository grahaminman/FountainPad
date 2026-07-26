"""
titlepage.py — Title page builder dialog (Fountain keys → file head).
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import fountain_tools as ft


class TitlePageDialog(QDialog):
    """Edit common Fountain title-page fields."""

    def __init__(self, values: Optional[Dict[str, str]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Title Page")
        self.setMinimumWidth(420)
        values = dict(values or {})

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "These fields become Fountain title-page keys at the top of the script. "
                "Leave a field blank to omit it."
            )
        )

        form = QFormLayout()
        self._fields: Dict[str, QWidget] = {}
        for key in ft.TITLE_PAGE_KEYS:
            if key == "Notes":
                w = QTextEdit()
                w.setAcceptRichText(False)
                w.setFixedHeight(72)
                w.setPlainText(values.get(key, ""))
            else:
                w = QLineEdit()
                w.setText(values.get(key, "").replace("\n", " "))
            self._fields[key] = w
            form.addRow(f"{key}:", w)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for key, w in self._fields.items():
            if isinstance(w, QTextEdit):
                val = w.toPlainText().strip()
            else:
                val = w.text().strip()  # type: ignore[attr-defined]
            if val:
                out[key] = val
        return out
