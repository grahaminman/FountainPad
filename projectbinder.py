"""
projectbinder.py — Project binder list (P1).

Left-side list of files in the open project folder:
  Script · Canon · Beats pack · Cards pack · (other .md / .fountain)

Signals
  fileActivated(path_str)  — open / focus this project file
  refreshRequested()       — rescan folder
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import project as project_mod

ROLE_BLOCK = Qt.UserRole
ROLE_PATH = Qt.UserRole + 1
ROLE_ROLE = Qt.UserRole + 2


class ProjectBinder(QWidget):
    """Binder list for a FountainPad project folder."""

    fileActivated = Signal(str)  # absolute path
    refreshRequested = Signal()
    exportCardsRequested = Signal()
    exportBeatsRequested = Signal()
    importCardsRequested = Signal()
    importBeatsRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProjectBinder")
        self.setMinimumWidth(160)
        self.setMaximumWidth(320)

        self._title = QLabel("Project")
        title_font = QFont()
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._subtitle = QLabel("No folder open")
        self._subtitle.setObjectName("ProjectBinderSub")
        self._subtitle.setWordWrap(True)

        self._btn_refresh = QToolButton()
        self._btn_refresh.setText("↻")
        self._btn_refresh.setToolTip("Rescan project folder")
        self._btn_refresh.clicked.connect(self.refreshRequested.emit)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setUniformItemSizes(True)
        self._list.itemActivated.connect(self._emit_item)
        self._list.itemClicked.connect(self._emit_item)

        self._btn_export_cards = QToolButton()
        self._btn_export_cards.setText("↓ Cards")
        self._btn_export_cards.setToolTip("Export Card Pack into this project")
        self._btn_export_cards.clicked.connect(self.exportCardsRequested.emit)

        self._btn_import_cards = QToolButton()
        self._btn_import_cards.setText("↑ Cards")
        self._btn_import_cards.setToolTip("Import Card Pack from this project")
        self._btn_import_cards.clicked.connect(self.importCardsRequested.emit)

        self._btn_export_beats = QToolButton()
        self._btn_export_beats.setText("↓ Beats")
        self._btn_export_beats.setToolTip("Export Beat Pack into this project")
        self._btn_export_beats.clicked.connect(self.exportBeatsRequested.emit)

        self._btn_import_beats = QToolButton()
        self._btn_import_beats.setText("↑ Beats")
        self._btn_import_beats.setToolTip("Import Beat Pack from this project")
        self._btn_import_beats.clicked.connect(self.importBeatsRequested.emit)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._title)
        head.addStretch(1)
        head.addWidget(self._btn_refresh)

        pack_row = QHBoxLayout()
        pack_row.setContentsMargins(0, 0, 0, 0)
        pack_row.setSpacing(4)
        pack_row.addWidget(self._btn_export_cards)
        pack_row.addWidget(self._btn_import_cards)
        pack_row.addWidget(self._btn_export_beats)
        pack_row.addWidget(self._btn_import_beats)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(head)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._list, 1)
        layout.addLayout(pack_row)

        self._project: Optional[project_mod.ProjectInfo] = None
        self._active_path: Optional[Path] = None
        self._updating = False
        self._set_pack_enabled(False)

    def set_project(self, info: Optional[project_mod.ProjectInfo]) -> None:
        self._project = info
        if info is None:
            self._title.setText("Project")
            self._subtitle.setText("No folder open")
            self._list.clear()
            self._set_pack_enabled(False)
            return
        self._title.setText("Project")
        self._subtitle.setText(info.name)
        self._set_pack_enabled(True)
        self._rebuild()

    def set_active_path(self, path: Optional[Path]) -> None:
        self._active_path = Path(path) if path else None
        if self._project is None:
            return
        self._updating = True
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is None:
                continue
            p = Path(str(item.data(ROLE_PATH) or ""))
            if self._active_path and p.resolve() == self._active_path.resolve():
                self._list.setCurrentRow(row)
                break
        self._updating = False

    def apply_theme(self, dark: bool) -> None:
        from PySide6.QtGui import QColor, QPalette

        pal = self._list.palette()
        if dark:
            highlight = QColor("#094771")
            highlighted_text = QColor("#ffffff")
            base = QColor("#1e1e1e")
            text = QColor("#dddddd")
            self.setStyleSheet(
                """
                QWidget#ProjectBinder {
                    background-color: #252526;
                    color: #dddddd;
                    border-right: 1px solid #3e3e42;
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
                }
                QListWidget::item:hover { background: #2a2d2e; color: #ffffff; }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #094771; color: #ffffff;
                }
                QLabel#ProjectBinderSub { color: #999999; font-size: 11px; }
                QToolButton {
                    background: #3e3e42; color: #dddddd;
                    border: 1px solid #555555; border-radius: 4px; padding: 2px 6px;
                }
                QToolButton:hover { background: #4a4a4e; }
                QToolButton:disabled { color: #666666; }
                """
            )
        else:
            highlight = QColor("#b3d7ff")
            highlighted_text = QColor("#000000")
            base = QColor("#ffffff")
            text = QColor("#1a1a1a")
            self.setStyleSheet(
                """
                QWidget#ProjectBinder {
                    background-color: #f0f0f0;
                    color: #1a1a1a;
                    border-right: 1px solid #d0d0d0;
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
                }
                QListWidget::item:hover { background: #eef6ff; color: #000000; }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #b3d7ff; color: #000000;
                }
                QLabel#ProjectBinderSub { color: #555555; font-size: 11px; }
                QToolButton {
                    background: #ffffff; color: #1a1a1a;
                    border: 1px solid #cccccc; border-radius: 4px; padding: 2px 6px;
                }
                QToolButton:hover { background: #eef6ff; }
                QToolButton:disabled { color: #999999; }
                """
            )
        pal.setColor(QPalette.Base, base)
        pal.setColor(QPalette.Text, text)
        pal.setColor(QPalette.Highlight, highlight)
        pal.setColor(QPalette.HighlightedText, highlighted_text)
        pal.setColor(QPalette.Inactive, QPalette.Highlight, highlight)
        pal.setColor(QPalette.Inactive, QPalette.HighlightedText, highlighted_text)
        self._list.setPalette(pal)

    def _set_pack_enabled(self, on: bool) -> None:
        for b in (
            self._btn_export_cards,
            self._btn_import_cards,
            self._btn_export_beats,
            self._btn_import_beats,
            self._btn_refresh,
        ):
            b.setEnabled(on)

    def _rebuild(self) -> None:
        self._updating = True
        self._list.clear()
        if self._project is None:
            self._updating = False
            return
        for pf in self._project.files:
            if pf.role == project_mod.ROLE_SCRIPT:
                text = f"📄 {pf.label}"
            elif pf.role == project_mod.ROLE_CANON:
                text = f"📘 {pf.label}"
            elif pf.role == project_mod.ROLE_BEATS:
                text = f"🎯 {pf.label}"
            elif pf.role == project_mod.ROLE_CARDS:
                text = f"🗂️ {pf.label}"
            else:
                text = f"📎 {pf.label}"
            if not pf.exists:
                text += " (missing)"
            item = QListWidgetItem(text)
            item.setData(ROLE_PATH, str(pf.path))
            item.setData(ROLE_ROLE, pf.role)
            tip = str(pf.path)
            if pf.role == project_mod.ROLE_BEATS:
                tip += "\nUse Export/Import Beat Pack to sync with script markers."
            elif pf.role == project_mod.ROLE_CARDS:
                tip += "\nUse Export/Import Card Pack to sync with script markers."
            elif pf.role == project_mod.ROLE_CANON:
                tip += "\nStory bible / constraints — edit here; not auto-merged into script."
            item.setToolTip(tip)
            if not pf.exists:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self._list.addItem(item)
        self._updating = False
        if self._active_path is not None:
            self.set_active_path(self._active_path)

    def _emit_item(self, item: QListWidgetItem) -> None:
        if self._updating or item is None:
            return
        path = str(item.data(ROLE_PATH) or "")
        if path:
            self.fileActivated.emit(path)
