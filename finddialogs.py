"""
finddialogs.py — Find in script + Find character dialogue.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import fountain_tools as ft


class FindDialog(QDialog):
    """Simple find next/previous in the source editor."""

    def __init__(
        self,
        editor,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find")
        self._editor = editor
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Find:"))
        self._needle = QLineEdit()
        self._needle.returnPressed.connect(self.find_next)
        row.addWidget(self._needle, 1)
        layout.addLayout(row)

        self._case = QCheckBox("Case sensitive")
        layout.addWidget(self._case)

        buttons = QHBoxLayout()
        btn_prev = QPushButton("Find Previous")
        btn_next = QPushButton("Find Next")
        btn_close = QPushButton("Close")
        btn_prev.clicked.connect(self.find_previous)
        btn_next.clicked.connect(self.find_next)
        btn_close.clicked.connect(self.close)
        buttons.addWidget(btn_prev)
        buttons.addWidget(btn_next)
        buttons.addStretch(1)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def set_needle(self, text: str) -> None:
        self._needle.setText(text or "")
        self._needle.selectAll()

    def _flags(self):
        flags = QTextDocument.FindFlag(0) if False else None  # placeholder
        return flags

    def find_next(self) -> None:
        self._find(forward=True)

    def find_previous(self) -> None:
        self._find(forward=False)

    def _find(self, forward: bool = True) -> None:
        from PySide6.QtGui import QTextDocument

        needle = self._needle.text()
        if not needle:
            self._status.setText("Enter text to find.")
            return
        flags = QTextDocument.FindFlags()
        if self._case.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if not forward:
            flags |= QTextDocument.FindBackward

        ed = self._editor
        found = ed.find(needle, flags)
        if not found:
            # Wrap around
            cursor = ed.textCursor()
            cursor.movePosition(QTextCursor.Start if forward else QTextCursor.End)
            ed.setTextCursor(cursor)
            found = ed.find(needle, flags)
        if found:
            self._status.setText("Found." if forward else "Found (backward).")
            ed.setFocus()
        else:
            self._status.setText("Not found.")


class FindCharacterDialog(QDialog):
    """List all dialogue blocks for a character; click to jump."""

    def __init__(
        self,
        editor,
        is_scene_heading: Callable[[str], bool],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find Character Dialogue")
        self._editor = editor
        self._is_scene = is_scene_heading
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Character:"))
        self._combo = QComboBox()
        self._combo.setEditable(True)
        row.addWidget(self._combo, 1)
        btn_refresh = QPushButton("List lines")
        btn_refresh.clicked.connect(self.refresh)
        row.addWidget(btn_refresh)
        layout.addLayout(row)

        self._list = QListWidget()
        self._list.itemActivated.connect(self._jump)
        self._list.itemDoubleClicked.connect(self._jump)
        layout.addWidget(self._list, 1)

        self._status = QLabel("")
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(lambda *_: self.close())
        layout.addWidget(buttons)

        self.reload_characters()

    def reload_characters(self) -> None:
        text = self._editor.toPlainText()
        names = ft.list_character_cues(text, self._is_scene)
        current = self._combo.currentText().strip()
        self._combo.clear()
        self._combo.addItems(names)
        if current:
            idx = self._combo.findText(current)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
            else:
                self._combo.setEditText(current)

    def refresh(self) -> None:
        self.reload_characters()
        name = self._combo.currentText().strip()
        self._list.clear()
        if not name:
            self._status.setText("Choose a character.")
            return
        hits = ft.find_character_dialogue_blocks(
            self._editor.toPlainText(), name, self._is_scene
        )
        for bn, scene, preview in hits:
            label = f"L{bn + 1}"
            if scene:
                label += f" · {scene}"
            if preview:
                label += f" — {preview}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, bn)
            self._list.addItem(item)
        n = len(hits)
        self._status.setText(f"{n} block" if n == 1 else f"{n} blocks")

    def _jump(self, item: QListWidgetItem) -> None:
        bn = item.data(Qt.UserRole)
        if bn is None:
            return
        if hasattr(self._editor, "goto_block"):
            self._editor.goto_block(int(bn))
        self._editor.setFocus()
