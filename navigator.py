"""
navigator.py — Outline navigator (Fountain sections + scenes).

Developer notes
---------------
SceneNavigator is a left-side panel, not a QDockWidget (keeps layout simple
inside MainWindow's outer QSplitter).

N4 (2026-07-26)
  Tree of Fountain ``#`` / ``##`` … sections plus real scene headings.
  Sections nest by hash depth; scenes attach under the nearest open section
  whose level is shallower. Document-order scenes with no prior section sit
  at the root (or under an implicit top-level group only if needed — v1 uses
  root).

Data flow
  MainWindow._refresh_navigator()
    → editor.list_outline_nodes()  →  [(kind, block, level, title), ...]
    → navigator.set_outline(...)
  Fallback: set_scenes([(block, heading), ...]) still works (scenes only).
  Click/Activate item
    → sceneActivated(block_number)  (name kept for MainWindow compatibility)
    → MainWindow._on_scene_activated → editor.goto_block

Filter
  Client-side substring match on title text (case-insensitive).
  Matching section keeps its scene children visible; matching scene promotes
  ancestor sections into view.

Highlight
  highlight_block(n) selects the outline node whose block is the greatest
  block_number <= n (section or scene). Uses _updating so programmatic
  selection does not re-emit jumps.

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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# UserRole keys on tree items
ROLE_BLOCK = Qt.UserRole
ROLE_KIND = Qt.UserRole + 1
ROLE_LEVEL = Qt.UserRole + 2
ROLE_TITLE = Qt.UserRole + 3


class SceneNavigator(QWidget):
    """Left-side outline: Fountain sections (#) and scene headings."""

    sceneActivated = Signal(int)  # document block number (sections or scenes)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SceneNavigator")
        self.setMinimumWidth(180)
        self.setMaximumWidth(420)

        title = QLabel("Outline")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter outline…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setRootIsDecorated(True)
        self._tree.setItemsExpandable(True)
        self._tree.itemActivated.connect(self._emit_item)
        self._tree.itemClicked.connect(self._emit_item)

        # Compat alias — older smoke tests / notes may touch _list
        self._list = self._tree

        self._count = QLabel("0 items")
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
        layout.addWidget(self._tree, 1)

        # (kind, block_number, level, title)
        self._all_nodes: list[tuple[str, int, int, str]] = []
        self._updating = False

    # --- public API -------------------------------------------------------

    def set_outline(self, nodes: list[tuple[str, int, int, str]]) -> None:
        """Replace outline. nodes = [(kind, block_number, level, title), ...]."""
        self._all_nodes = list(nodes)
        self._rebuild_tree()

    def set_scenes(self, scenes: list[tuple[int, str]]) -> None:
        """Backward-compatible: scenes-only outline (no sections)."""
        self.set_outline([("scene", bn, 0, heading) for bn, heading in scenes])

    def highlight_block(self, block_number: int) -> None:
        """Select the outline node that contains the given block."""
        if not self._all_nodes:
            return
        target_block = -1
        for _kind, bn, _level, _title in self._all_nodes:
            if bn <= block_number:
                target_block = bn
            else:
                break
        if target_block < 0:
            return
        item = self._find_item_by_block(target_block)
        if item is None:
            return
        self._updating = True
        # Expand ancestors so the selection is visible
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self._tree.setCurrentItem(item)
        self._tree.scrollToItem(item)
        self._updating = False

    def apply_theme(self, dark: bool) -> None:
        """Theme outline chrome (readable selection on macOS)."""
        from PySide6.QtGui import QColor, QPalette

        pal = self._tree.palette()
        if dark:
            highlight = QColor("#094771")
            highlighted_text = QColor("#ffffff")
            base = QColor("#1e1e1e")
            text = QColor("#dddddd")
            self.setStyleSheet(
                """
                QWidget#SceneNavigator {
                    background-color: #252526;
                    color: #dddddd;
                    border-right: 1px solid #3e3e42;
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
                QTreeWidget {
                    background: #1e1e1e;
                    color: #dddddd;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    outline: none;
                }
                QTreeWidget::item {
                    padding: 4px 6px;
                    color: #dddddd;
                    background: transparent;
                }
                QTreeWidget::item:hover {
                    background: #2a2d2e;
                    color: #ffffff;
                }
                QTreeWidget::item:selected,
                QTreeWidget::item:selected:active,
                QTreeWidget::item:selected:!active {
                    background: #094771;
                    color: #ffffff;
                }
                QLabel#SceneNavCount { color: #999999; font-size: 11px; }
                """
            )
        else:
            highlight = QColor("#b3d7ff")
            highlighted_text = QColor("#000000")
            base = QColor("#ffffff")
            text = QColor("#1a1a1a")
            self.setStyleSheet(
                """
                QWidget#SceneNavigator {
                    background-color: #f0f0f0;
                    color: #1a1a1a;
                    border-right: 1px solid #d0d0d0;
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
                QTreeWidget {
                    background: #ffffff;
                    color: #1a1a1a;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    outline: none;
                }
                QTreeWidget::item {
                    padding: 4px 6px;
                    color: #1a1a1a;
                    background: transparent;
                }
                QTreeWidget::item:hover {
                    background: #eef6ff;
                    color: #000000;
                }
                QTreeWidget::item:selected,
                QTreeWidget::item:selected:active,
                QTreeWidget::item:selected:!active {
                    background: #b3d7ff;
                    color: #000000;
                }
                QLabel#SceneNavCount { color: #555555; font-size: 11px; }
                """
            )

        pal.setColor(QPalette.Base, base)
        pal.setColor(QPalette.Text, text)
        pal.setColor(QPalette.Highlight, highlight)
        pal.setColor(QPalette.HighlightedText, highlighted_text)
        pal.setColor(QPalette.Inactive, QPalette.Highlight, highlight)
        pal.setColor(QPalette.Inactive, QPalette.HighlightedText, highlighted_text)
        self._tree.setPalette(pal)

    # --- internals --------------------------------------------------------

    def _make_item(self, kind: str, block_number: int, level: int, title: str) -> QTreeWidgetItem:
        if kind == "section":
            label = title
            tip = f"Section (level {level}) · line {block_number + 1}"
            font = QFont()
            font.setBold(True)
        else:
            label = title
            tip = f"Scene · line {block_number + 1}"
            font = QFont()
            font.setBold(False)

        item = QTreeWidgetItem([label])
        item.setData(0, ROLE_BLOCK, int(block_number))
        item.setData(0, ROLE_KIND, kind)
        item.setData(0, ROLE_LEVEL, int(level))
        item.setData(0, ROLE_TITLE, title)
        item.setToolTip(0, tip)
        item.setFont(0, font)
        return item

    def _rebuild_tree(self) -> None:
        needle = self._filter.text().strip().lower()
        self._updating = True
        self._tree.clear()

        # Stack of (level, QTreeWidgetItem) for open sections
        stack: list[tuple[int, QTreeWidgetItem]] = []
        section_count = 0
        scene_count = 0
        shown_sections = 0
        shown_scenes = 0

        # When filtering: build full tree first into memory, then prune —
        # simpler: build full tree always, then hide non-matching.
        # For large scripts, filter during build is better.

        def parent_for_section(level: int) -> Optional[QTreeWidgetItem]:
            while stack and stack[-1][0] >= level:
                stack.pop()
            return stack[-1][1] if stack else None

        def parent_for_scene() -> Optional[QTreeWidgetItem]:
            return stack[-1][1] if stack else None

        def add_item(item: QTreeWidgetItem, parent: Optional[QTreeWidgetItem]) -> None:
            if parent is None:
                self._tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

        for kind, bn, level, title in self._all_nodes:
            if kind == "section":
                section_count += 1
                parent = parent_for_section(level)
                item = self._make_item(kind, bn, level, title)
                add_item(item, parent)
                stack.append((level, item))
                item.setExpanded(True)
            else:
                scene_count += 1
                parent = parent_for_scene()
                item = self._make_item("scene", bn, 0, title)
                add_item(item, parent)

        if needle:
            self._apply_filter_visibility(needle)
            shown_sections, shown_scenes = self._count_visible()
            self._count.setText(
                f"{shown_sections + shown_scenes}/"
                f"{section_count + scene_count} · "
                f"{shown_sections}§ {shown_scenes}sc"
            )
        else:
            if section_count:
                self._count.setText(
                    f"{section_count} section"
                    f"{'' if section_count == 1 else 's'} · "
                    f"{scene_count} scene"
                    f"{'' if scene_count == 1 else 's'}"
                )
            else:
                self._count.setText(
                    f"{scene_count} scene" if scene_count == 1 else f"{scene_count} scenes"
                )

        self._updating = False

    def _iter_items(self, root: Optional[QTreeWidgetItem] = None):
        if root is None:
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item is not None:
                    yield from self._iter_items(item)
            return
        yield root
        for i in range(root.childCount()):
            child = root.child(i)
            if child is not None:
                yield from self._iter_items(child)

    def _apply_filter_visibility(self, needle: str) -> None:
        """Show items that match; keep ancestors of matches expanded/visible."""

        def title_of(item: QTreeWidgetItem) -> str:
            return str(item.data(0, ROLE_TITLE) or item.text(0) or "")

        def matches(item: QTreeWidgetItem) -> bool:
            return needle in title_of(item).lower()

        # Bottom-up: item visible if it matches or any descendant matches
        def mark(item: QTreeWidgetItem) -> bool:
            child_hit = False
            for i in range(item.childCount()):
                ch = item.child(i)
                if ch is not None and mark(ch):
                    child_hit = True
            hit = matches(item) or child_hit
            item.setHidden(not hit)
            if hit and child_hit:
                item.setExpanded(True)
            return hit

        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if top is not None:
                mark(top)

    def _count_visible(self) -> tuple[int, int]:
        sec = scn = 0
        for item in self._iter_items():
            if item.isHidden():
                continue
            kind = item.data(0, ROLE_KIND)
            if kind == "section":
                sec += 1
            else:
                scn += 1
        return sec, scn

    def _find_item_by_block(self, block_number: int) -> Optional[QTreeWidgetItem]:
        for item in self._iter_items():
            if int(item.data(0, ROLE_BLOCK)) == int(block_number):
                return item
        return None

    def _apply_filter(self, _text: str) -> None:
        self._rebuild_tree()

    def _emit_item(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        if self._updating or item is None:
            return
        block_number = int(item.data(0, ROLE_BLOCK))
        self.sceneActivated.emit(block_number)

    # Smoke / test helpers (list-like API)
    def count(self) -> int:
        """Total visible outline nodes (compat with QListWidget.count)."""
        n = 0
        for item in self._iter_items():
            if not item.isHidden():
                n += 1
        return n
