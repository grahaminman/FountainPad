"""
navigator.py — Scene navigator list (jump-to-scene).

Developer notes
---------------
SceneNavigator is a left-side panel, not a QDockWidget (keeps layout simple
inside MainWindow's outer QSplitter).

Data flow
  MainWindow._refresh_navigator()
    → editor.list_scene_headings()  →  [(block_number, heading), ...]
    → navigator.set_scenes(...)
  Click/Activate item
    → sceneActivated(block_number)
    → MainWindow._on_scene_activated → editor.goto_block

Filter
  Client-side substring match on heading text (case-insensitive).
  Block numbers stay on QListWidgetItem UserRole so jumps stay correct
  after filtering.

Highlight
  highlight_block(n) selects the scene whose heading block is the greatest
  heading_block <= n (i.e. the scene containing the cursor). Uses _updating
  so programmatic selection does not re-emit jumps.

Theming
  apply_theme(dark) sets local stylesheets; MainWindow calls this with the
  global dark flag.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SceneNavigator(QWidget):
    """Left-side list of Fountain scene headings."""

    sceneActivated = Signal(int)  # document block number

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SceneNavigator")
        self.setMinimumWidth(180)
        self.setMaximumWidth(420)

        title = QLabel("Scenes")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter scenes…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        self._list.setAlternatingRowColors(True)
        self._list.itemActivated.connect(self._emit_item)
        self._list.itemClicked.connect(self._emit_item)

        self._count = QLabel("0 scenes")
        self._count.setObjectName("SceneNavCount")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._count)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._filter)
        layout.addWidget(self._list, 1)

        self._all_scenes: list[tuple[int, str]] = []
        self._updating = False

    def set_scenes(self, scenes: list[tuple[int, str]]) -> None:
        """Replace scene list. scenes = [(block_number, heading), ...]."""
        self._all_scenes = list(scenes)
        self._rebuild_list()

    def highlight_block(self, block_number: int) -> None:
        """Select the scene that contains the given block (nearest heading at/above)."""
        if not self._all_scenes:
            return
        target_row = -1
        target_block = -1
        for bn, _heading in self._all_scenes:
            if bn <= block_number:
                target_block = bn
            else:
                break
        if target_block < 0:
            return
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is None:
                continue
            if int(item.data(Qt.UserRole)) == target_block:
                target_row = row
                break
        if target_row < 0:
            return
        self._updating = True
        self._list.setCurrentRow(target_row)
        self._updating = False

    def apply_theme(self, dark: bool) -> None:
        if dark:
            self.setStyleSheet(
                """
                QWidget#SceneNavigator {
                    background-color: #252526;
                    color: #ddd;
                    border-right: 1px solid #3e3e42;
                }
                QLineEdit {
                    background: #1e1e1e;
                    color: #ddd;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    padding: 4px 6px;
                }
                QListWidget {
                    background: #1e1e1e;
                    color: #ddd;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    outline: none;
                }
                QListWidget::item { padding: 6px 8px; }
                QListWidget::item:selected { background: #094771; color: #fff; }
                QListWidget::item:hover { background: #2a2d2e; }
                QLabel#SceneNavCount { color: #999; font-size: 11px; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget#SceneNavigator {
                    background-color: #f0f0f0;
                    color: #222;
                    border-right: 1px solid #d0d0d0;
                }
                QLineEdit {
                    background: #fff;
                    color: #222;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 4px 6px;
                }
                QListWidget {
                    background: #fff;
                    color: #222;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    outline: none;
                }
                QListWidget::item { padding: 6px 8px; }
                QListWidget::item:selected { background: #cde8ff; color: #111; }
                QListWidget::item:hover { background: #eef6ff; }
                QLabel#SceneNavCount { color: #666; font-size: 11px; }
                """
            )

    def _rebuild_list(self) -> None:
        needle = self._filter.text().strip().lower()
        self._updating = True
        self._list.clear()
        shown = 0
        for block_number, heading in self._all_scenes:
            if needle and needle not in heading.lower():
                continue
            item = QListWidgetItem(heading)
            item.setData(Qt.UserRole, block_number)
            item.setToolTip(f"Line {block_number + 1}: {heading}")
            self._list.addItem(item)
            shown += 1
        total = len(self._all_scenes)
        if needle:
            self._count.setText(f"{shown}/{total} scenes")
        else:
            self._count.setText(f"{total} scene" if total == 1 else f"{total} scenes")
        self._updating = False

    def _apply_filter(self, _text: str) -> None:
        self._rebuild_list()

    def _emit_item(self, item: QListWidgetItem) -> None:
        if self._updating or item is None:
            return
        block_number = int(item.data(Qt.UserRole))
        self.sceneActivated.emit(block_number)
