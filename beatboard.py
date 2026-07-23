"""
beatboard.py — Beat board (major plot points) for FountainPad.

Developer notes
---------------
BeatBoard is a right-side panel (like SceneNavigator/CardNavigator).

Data flow
  MainWindow._refresh_beat_board()
    → editor.list_beats() → [(block_number, beat_type, beat_text, scene_heading), ...]
    → beat_board.set_beats(...)
  Click/Activate item
    → beatActivated(block_number)
    → MainWindow._on_beat_activated → editor.goto_block

Filter
  Client-side substring match on beat_type, beat_text, or scene_heading.
  Block numbers stay on QListWidgetItem UserRole so jumps stay correct.

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


class BeatBoard(QWidget):
    """Right-side list of major plot beats."""

    beatActivated = Signal(int)  # document block number

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("BeatBoard")
        self.setMinimumWidth(180)
        self.setMaximumWidth(420)

        title = QLabel("Beat Board")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter beats…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        self._list.setAlternatingRowColors(True)
        self._list.itemActivated.connect(self._emit_item)
        self._list.itemClicked.connect(self._emit_item)

        self._count = QLabel("0 beats")
        self._count.setObjectName("BeatBoardCount")

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

        self._all_beats: list[tuple[int, str, str, str]] = []
        self._updating = False

    def set_beats(self, beats: list[tuple[int, str, str, str]]) -> None:
        """Replace beat list. beats = [(block_number, beat_type, beat_text, scene_heading), ...]."""
        self._all_beats = list(beats)
        self._rebuild_list()

    def apply_theme(self, dark: bool) -> None:
        """Theme beat board chrome."""
        from PySide6.QtGui import QColor, QPalette

        pal = self._list.palette()
        if dark:
            highlight = QColor("#094771")
            highlighted_text = QColor("#ffffff")
            base = QColor("#1e1e1e")
            text = QColor("#dddddd")
            self.setStyleSheet(
                """
                QWidget#BeatBoard {
                    background-color: #252526;
                    color: #dddddd;
                    border-left: 1px solid #3e3e42;
                }
                QLineEdit {
                    background: #1e1e1e;
                    color: #dddddd;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    padding: 4px 6px;
                    selection-background-color: #094771;
                    selection-color: #ffffff;
                }
                QListWidget {
                    background: #1e1e1e;
                    color: #dddddd;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    outline: none;
                }
                QListWidget::item {
                    padding: 6px 8px;
                    color: #dddddd;
                    background: transparent;
                }
                QListWidget::item:hover {
                    background: #2a2d2e;
                    color: #ffffff;
                }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #094771;
                    color: #ffffff;
                }
                QLabel#BeatBoardCount { color: #999999; font-size: 11px; }
                """
            )
        else:
            highlight = QColor("#b3d7ff")
            highlighted_text = QColor("#000000")
            base = QColor("#ffffff")
            text = QColor("#1a1a1a")
            self.setStyleSheet(
                """
                QWidget#BeatBoard {
                    background-color: #f0f0f0;
                    color: #1a1a1a;
                    border-left: 1px solid #d0d0d0;
                }
                QLineEdit {
                    background: #ffffff;
                    color: #1a1a1a;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 6px;
                    selection-background-color: #b3d7ff;
                    selection-color: #000000;
                }
                QListWidget {
                    background: #ffffff;
                    color: #1a1a1a;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    outline: none;
                }
                QListWidget::item {
                    padding: 6px 8px;
                    color: #1a1a1a;
                    background: transparent;
                }
                QListWidget::item:hover {
                    background: #eef6ff;
                    color: #000000;
                }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #b3d7ff;
                    color: #000000;
                }
                QLabel#BeatBoardCount { color: #555555; font-size: 11px; }
                """
            )

        pal.setColor(QPalette.Base, base)
        pal.setColor(QPalette.Text, text)
        pal.setColor(QPalette.Highlight, highlight)
        pal.setColor(QPalette.HighlightedText, highlighted_text)
        pal.setColor(QPalette.Inactive, QPalette.Highlight, highlight)
        pal.setColor(QPalette.Inactive, QPalette.HighlightedText, highlighted_text)
        self._list.setPalette(pal)

    def _rebuild_list(self) -> None:
        needle = self._filter.text().strip().lower()
        self._updating = True
        self._list.clear()
        shown = 0
        for block_number, beat_type, beat_text, scene_heading in self._all_beats:
            if needle:
                search_text = f"{beat_type} {beat_text} {scene_heading}".lower()
                if needle not in search_text:
                    continue
            item = QListWidgetItem(f"{beat_type}: {beat_text}")
            item.setData(Qt.UserRole, block_number)
            item.setToolTip(f"Scene: {scene_heading}\nLine {block_number + 1}")
            self._list.addItem(item)
            shown += 1
        total = len(self._all_beats)
        if needle:
            self._count.setText(f"{shown}/{total} beats")
        else:
            self._count.setText(f"{total} beat" if total == 1 else f"{total} beats")
        self._updating = False

    def _apply_filter(self, _text: str) -> None:
        self._rebuild_list()

    def _emit_item(self, item: QListWidgetItem) -> None:
        if self._updating or item is None:
            return
        block_number = int(item.data(Qt.UserRole))
        self.beatActivated.emit(block_number)