"""
cardnavigator.py — Index card navigator (jump-to-card).

Developer notes
---------------
CardNavigator is a left-side panel (like SceneNavigator).

Data flow
  MainWindow._refresh_navigator()
    → editor.list_cards() → [(block_number, card_type, card_text, scene_heading), ...]
    → navigator.set_cards(...)
  Click/Activate item
    → cardActivated(block_number)
    → MainWindow._on_card_activated → editor.goto_block

Filter
  Client-side substring match on card_type, card_text, or scene_heading.
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


class CardNavigator(QWidget):
    """Left-side list of index cards."""

    cardActivated = Signal(int)  # document block number
    cardTemplateRequested = Signal(str)  # card_type (e.g., "Goal")
    generateFromScenesRequested = Signal()  # P3: empty note stubs per scene
    applyCardRequested = Signal(int)  # Phase B: apply card → script

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardNavigator")
        self.setMinimumWidth(180)
        self.setMaximumWidth(420)

        title = QLabel("Index Cards")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)

        # Template buttons (Goal/Conflict/Turn) + optional scene stubs
        self._btn_goal = self._make_template_button("Goal")
        self._btn_conflict = self._make_template_button("Conflict")
        self._btn_turn = self._make_template_button("Turn")
        self._btn_from_scenes = self._make_from_scenes_button()
        self._btn_apply = self._make_apply_button()

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter cards…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        self._list.setAlternatingRowColors(True)
        self._list.itemActivated.connect(self._emit_item)
        self._list.itemClicked.connect(self._emit_item)

        self._count = QLabel("0 cards")
        self._count.setObjectName("CardNavCount")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title)
        header.addWidget(self._btn_goal)
        header.addWidget(self._btn_conflict)
        header.addWidget(self._btn_turn)
        header.addWidget(self._btn_from_scenes)
        header.addWidget(self._btn_apply)
        header.addStretch(1)
        header.addWidget(self._count)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._filter)
        layout.addWidget(self._list, 1)

        self._all_cards: list[tuple[int, str, str, str]] = []
        self._all_infos: list = []
        self._updating = False

    def _make_template_button(self, card_type: str) -> QWidget:
        """Create a button to insert a card template at the cursor."""
        from PySide6.QtWidgets import QToolButton

        btn = QToolButton()
        btn.setText(card_type)
        btn.setToolTip(f"Insert [[card: {card_type}]]")
        btn.setAutoRaise(True)
        btn.clicked.connect(lambda: self._insert_card_template(card_type))
        return btn

    def _insert_card_template(self, card_type: str) -> None:
        """Emit a signal to insert a card template at the cursor."""
        self.cardTemplateRequested.emit(card_type)

    def _make_from_scenes_button(self):
        from PySide6.QtWidgets import QToolButton

        btn = QToolButton()
        btn.setText("From scenes")
        btn.setToolTip(
            "Insert an empty card note under each scene that has none "
            "(optional planning notes — not instructions)."
        )
        btn.setAutoRaise(True)
        btn.clicked.connect(self.generateFromScenesRequested.emit)
        return btn

    def _make_apply_button(self):
        from PySide6.QtWidgets import QToolButton

        btn = QToolButton()
        btn.setText("Apply")
        btn.setToolTip(
            "Apply selected card to the script: if the first body line is a "
            "scene heading (INT./EXT.…), insert or update that slugline. "
            "Notes stay as card notes — not a forced compile."
        )
        btn.setAutoRaise(True)
        btn.clicked.connect(self._emit_apply)
        return btn

    def _emit_apply(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        block_number = int(item.data(Qt.UserRole))
        self.applyCardRequested.emit(block_number)

    def set_cards(self, cards: list[tuple[int, str, str, str]]) -> None:
        """Replace card list. cards = [(block_number, card_type, card_text, scene_heading), ...]."""
        self._all_cards = list(cards)
        self._rebuild_list()

    def set_card_infos(self, infos) -> None:
        """Preferred: list of CardInfo (ids + richer labels)."""
        self._all_infos = list(infos or [])
        # Keep tuple cache for filter fallback
        self._all_cards = [
            (
                i.block_number,
                i.card_type,
                (i.body.splitlines()[0] if i.body else ""),
                i.scene_heading,
            )
            for i in self._all_infos
        ]
        self._rebuild_list()

    def apply_theme(self, dark: bool) -> None:
        """
        Theme navigator chrome.
        """
        from PySide6.QtGui import QColor, QPalette

        pal = self._list.palette()
        if dark:
            highlight = QColor("#094771")
            highlighted_text = QColor("#ffffff")
            base = QColor("#1e1e1e")
            text = QColor("#dddddd")
            self.setStyleSheet(
                """
                QWidget#CardNavigator {
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
                QLabel#CardNavCount { color: #999999; font-size: 11px; }
                """
            )
        else:
            highlight = QColor("#b3d7ff")
            highlighted_text = QColor("#000000")
            base = QColor("#ffffff")
            text = QColor("#1a1a1a")
            self.setStyleSheet(
                """
                QWidget#CardNavigator {
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
                QLabel#CardNavCount { color: #555555; font-size: 11px; }
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
        if self._all_infos:
            rows = []
            for info in self._all_infos:
                label = info.display_label()
                rows.append(
                    (
                        info.block_number,
                        label,
                        info.scene_heading,
                        info.card_id,
                        info.body,
                    )
                )
        else:
            rows = [
                (bn, f"{ctype}: {ctext}", scene, "", ctext)
                for bn, ctype, ctext, scene in self._all_cards
            ]
        for block_number, label, scene_heading, card_id, body in rows:
            if needle:
                search_text = f"{label} {scene_heading} {card_id} {body}".lower()
                if needle not in search_text:
                    continue
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, block_number)
            tip = f"Scene: {scene_heading}\nLine {block_number + 1}"
            if card_id:
                tip = f"id={card_id}\n" + tip
            if body:
                tip += f"\n\n{body[:400]}"
            item.setToolTip(tip)
            self._list.addItem(item)
            shown += 1
        total = len(rows)
        if needle:
            self._count.setText(f"{shown}/{total} cards")
        else:
            self._count.setText(f"{total} card" if total == 1 else f"{total} cards")
        self._updating = False

    def _apply_filter(self, _text: str) -> None:
        self._rebuild_list()

    def _emit_item(self, item: QListWidgetItem) -> None:
        if self._updating or item is None:
            return
        block_number = int(item.data(Qt.UserRole))
        self.cardActivated.emit(block_number)