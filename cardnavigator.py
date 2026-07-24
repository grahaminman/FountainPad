"""
cardnavigator.py — Index cards list + editable card detail + versions.

Left panel:
  - list of cards (jump)
  - detail editor for selected card (type, body)
  - version list with Make top / load into editor
  - Save version, Apply (action-only to script)

Notes to the draft — not a forced compiler.
"""

from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import cards as cards_mod


class CardNavigator(QWidget):
    """Left-side index cards: list + editable detail."""

    cardActivated = Signal(int)
    cardTemplateRequested = Signal(str)
    generateFromScenesRequested = Signal()
    applyCardRequested = Signal(int)
    # Save working text into card store (optional snapshot) without apply
    saveCardRequested = Signal(int, str, str, object, str, bool)
    # (block, card_id, card_type, versions_list, active, make_snapshot)
    setActiveVersionRequested = Signal(int, str)  # block, version_id
    reorderCardRequested = Signal(int, int)  # block, direction (-1 up / +1 down)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardNavigator")
        self.setMinimumWidth(220)
        self.setMaximumWidth(520)

        title = QLabel("Index Cards")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)

        self._btn_goal = self._make_template_button("Goal")
        self._btn_conflict = self._make_template_button("Conflict")
        self._btn_turn = self._make_template_button("Turn")
        self._btn_from_scenes = self._make_tool_button(
            "From scenes",
            "Insert empty card notes under scenes that have none.",
            self.generateFromScenesRequested.emit,
        )
        self._btn_apply = self._make_tool_button(
            "Apply",
            "Apply active card version to the script: scene heading + action only. "
            "Dialogue is never changed.",
            self._emit_apply,
        )
        self._btn_save = self._make_tool_button(
            "Save ver",
            "Save the editor text as a new version if it changed (keeps older versions).",
            self._emit_save_snapshot,
        )
        self._btn_save_inplace = self._make_tool_button(
            "Save",
            "Write editor text into the active version without adding a new version.",
            self._emit_save_inplace,
        )
        self._btn_up = self._make_tool_button(
            "Up",
            "Move this card's scene earlier in the script (whole scene block travels with it).",
            lambda: self._emit_reorder(-1),
        )
        self._btn_down = self._make_tool_button(
            "Down",
            "Move this card's scene later in the script (whole scene block travels with it).",
            lambda: self._emit_reorder(1),
        )

        self._count = QLabel("0 cards")
        self._count.setObjectName("CardNavCount")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title)
        header.addWidget(self._btn_goal)
        header.addWidget(self._btn_conflict)
        header.addWidget(self._btn_turn)
        header.addWidget(self._btn_from_scenes)
        header.addWidget(self._btn_save_inplace)
        header.addWidget(self._btn_save)
        header.addWidget(self._btn_apply)
        header.addWidget(self._btn_up)
        header.addWidget(self._btn_down)
        header.addStretch(1)
        header.addWidget(self._count)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter cards…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.itemActivated.connect(self._emit_item)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.currentItemChanged.connect(self._on_current_changed)

        # Detail pane
        self._detail_title = QLabel("Card detail")
        self._detail_title.setObjectName("CardDetailTitle")
        df = QFont()
        df.setBold(True)
        self._detail_title.setFont(df)

        self._type = QComboBox()
        self._type.setEditable(True)
        for t in ("Note", "Goal", "Conflict", "Turn"):
            self._type.addItem(t)
        self._type.setToolTip("Card type label")

        self._id_label = QLabel("id —")
        self._id_label.setObjectName("CardIdLabel")

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type"))
        type_row.addWidget(self._type, 1)
        type_row.addWidget(self._id_label)

        self._body = QPlainTextEdit()
        self._body.setPlaceholderText(
            "Edit this card here.\n"
            "First line may be a scene heading (INT./EXT.…).\n"
            "Following lines = action/notes (Apply writes action only; never dialogue)."
        )
        self._body.setMinimumHeight(120)

        self._versions = QListWidget()
        self._versions.setMaximumHeight(110)
        self._versions.itemClicked.connect(self._on_version_clicked)
        self._versions.itemDoubleClicked.connect(self._on_version_make_top)

        self._btn_make_top = self._make_tool_button(
            "Make top",
            "Set the selected version as active (priority top). Then Apply to push to script.",
            self._emit_make_top,
        )
        self._btn_load_ver = self._make_tool_button(
            "Load",
            "Load the selected version text into the editor (does not change active until Save/Make top).",
            self._load_selected_version_into_editor,
        )

        ver_row = QHBoxLayout()
        ver_row.addWidget(QLabel("Versions"))
        ver_row.addStretch(1)
        ver_row.addWidget(self._btn_load_ver)
        ver_row.addWidget(self._btn_make_top)

        detail = QWidget()
        dlay = QVBoxLayout(detail)
        dlay.setContentsMargins(0, 0, 0, 0)
        dlay.setSpacing(4)
        dlay.addWidget(self._detail_title)
        dlay.addLayout(type_row)
        dlay.addWidget(self._body, 1)
        dlay.addLayout(ver_row)
        dlay.addWidget(self._versions)

        split = QSplitter(Qt.Vertical)
        split.addWidget(self._list)
        split.addWidget(detail)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._filter)
        layout.addWidget(split, 1)

        self._all_cards: list = []
        self._all_infos: List[Any] = []
        self._updating = False
        self._loading_detail = False
        self._current_block: int = -1
        self._current_info: Any = None

    def _make_template_button(self, card_type: str):
        from PySide6.QtWidgets import QToolButton

        btn = QToolButton()
        btn.setText(card_type)
        btn.setToolTip(f"Insert [[card: id=… | {card_type}]]")
        btn.setAutoRaise(True)
        btn.clicked.connect(lambda: self.cardTemplateRequested.emit(card_type))
        return btn

    def _make_tool_button(self, text: str, tip: str, slot):
        from PySide6.QtWidgets import QToolButton

        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setAutoRaise(True)
        btn.clicked.connect(slot)
        return btn

    def set_cards(self, cards: list) -> None:
        self._all_cards = list(cards)
        self._all_infos = []
        self._rebuild_list()

    def set_card_infos(self, infos) -> None:
        prev_block = self._current_block
        self._all_infos = list(infos or [])
        self._all_cards = [
            (
                i.block_number,
                i.card_type,
                (i.active_text.splitlines()[0] if i.active_text else ""),
                i.scene_heading,
            )
            for i in self._all_infos
        ]
        self._rebuild_list()
        # Reselect previous card if still present
        if prev_block >= 0:
            for row in range(self._list.count()):
                item = self._list.item(row)
                if item and int(item.data(Qt.UserRole)) == prev_block:
                    self._updating = True
                    self._list.setCurrentRow(row)
                    self._updating = False
                    info = self._info_for_block(prev_block)
                    if info is not None:
                        self._load_detail(info)
                    return
        # else clear or keep first
        if self._list.count() and self._list.currentRow() < 0:
            self._list.setCurrentRow(0)

    def current_block(self) -> int:
        item = self._list.currentItem()
        if item is None:
            return -1
        return int(item.data(Qt.UserRole))

    def working_text(self) -> str:
        return self._body.toPlainText()

    def working_type(self) -> str:
        return (self._type.currentText() or "Note").strip() or "Note"

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
                QWidget#CardNavigator {
                    background-color: #252526;
                    color: #dddddd;
                    border-right: 1px solid #3e3e42;
                }
                QLineEdit, QPlainTextEdit, QComboBox {
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
                QListWidget::item { padding: 6px 8px; }
                QListWidget::item:hover { background: #2a2d2e; color: #ffffff; }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #094771; color: #ffffff;
                }
                QLabel#CardNavCount, QLabel#CardIdLabel { color: #999999; font-size: 11px; }
                QLabel#CardDetailTitle { color: #cccccc; }
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
                QLineEdit, QPlainTextEdit, QComboBox {
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
                QListWidget::item { padding: 6px 8px; }
                QListWidget::item:hover { background: #eef6ff; color: #000000; }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #b3d7ff; color: #000000;
                }
                QLabel#CardNavCount, QLabel#CardIdLabel { color: #555555; font-size: 11px; }
                QLabel#CardDetailTitle { color: #333333; }
                """
            )
        pal.setColor(QPalette.Base, base)
        pal.setColor(QPalette.Text, text)
        pal.setColor(QPalette.Highlight, highlight)
        pal.setColor(QPalette.HighlightedText, highlighted_text)
        pal.setColor(QPalette.Inactive, QPalette.Highlight, highlight)
        pal.setColor(QPalette.Inactive, QPalette.HighlightedText, highlighted_text)
        self._list.setPalette(pal)
        self._versions.setPalette(pal)
        self._body.setPalette(pal)

    def _info_for_block(self, block: int):
        for info in self._all_infos:
            if info.block_number == block:
                return info
        return None

    def _rebuild_list(self) -> None:
        needle = self._filter.text().strip().lower()
        self._updating = True
        self._list.clear()
        shown = 0
        if self._all_infos:
            rows = []
            for info in self._all_infos:
                rows.append(
                    (
                        info.block_number,
                        info.display_label(),
                        info.scene_heading,
                        info.card_id,
                        info.active_text,
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

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self._emit_item(item)

    def _on_current_changed(self, current, _previous) -> None:
        if self._updating or current is None:
            return
        block_number = int(current.data(Qt.UserRole))
        info = self._info_for_block(block_number)
        if info is not None:
            self._load_detail(info)

    def _load_detail(self, info) -> None:
        self._loading_detail = True
        self._current_block = info.block_number
        self._current_info = info
        cid = info.card_id or "—"
        self._id_label.setText(f"id {cid} · {info.active_version}")
        self._detail_title.setText(f"Card {cid}")
        # type
        t = info.card_type or "Note"
        idx = self._type.findText(t)
        if idx >= 0:
            self._type.setCurrentIndex(idx)
        else:
            self._type.setEditText(t)
        self._body.setPlainText(info.active_text)
        self._versions.clear()
        for v in info.versions or []:
            mark = "★ " if v.version_id == info.active_version else "   "
            preview = (v.text or "").strip().splitlines()
            head = preview[0] if preview else "(empty)"
            item = QListWidgetItem(f"{mark}{v.version_id}: {head[:60]}")
            item.setData(Qt.UserRole, v.version_id)
            item.setData(Qt.UserRole + 1, v.text)
            tip = v.text[:800] if v.text else "(empty)"
            item.setToolTip(tip)
            self._versions.addItem(item)
        self._loading_detail = False

    def _emit_apply(self) -> None:
        block = self.current_block()
        if block < 0:
            return
        # MainWindow snapshots working text once, then applies action-only.
        self.applyCardRequested.emit(block)

    def _emit_reorder(self, direction: int) -> None:
        block = self.current_block()
        if block < 0:
            return
        self.reorderCardRequested.emit(block, int(direction))

    def _emit_save_snapshot(self) -> None:
        self._emit_save(make_snapshot=True)

    def _emit_save_inplace(self) -> None:
        self._emit_save(make_snapshot=False)

    def _emit_save(self, make_snapshot: bool) -> None:
        info = self._current_info
        block = self.current_block()
        if info is None or block < 0:
            return
        versions = list(info.versions) if info.versions else [
            cards_mod.CardVersion("v1", info.body or "")
        ]
        active = info.active_version or "v1"
        card_id = info.card_id or ""
        card_type = self.working_type()
        text = self.working_text()
        if make_snapshot:
            versions, active, _created = cards_mod.snapshot_version(versions, active, text)
        else:
            # overwrite active version text
            found = False
            new_versions = []
            for v in versions:
                if v.version_id == active:
                    new_versions.append(cards_mod.CardVersion(v.version_id, text.strip()))
                    found = True
                else:
                    new_versions.append(v)
            if not found:
                new_versions.append(cards_mod.CardVersion(active or "v1", text.strip()))
            versions = new_versions
        self.saveCardRequested.emit(block, card_id, card_type, versions, active, make_snapshot)

    def _on_version_clicked(self, item: QListWidgetItem) -> None:
        # single click: show tip already; optional load on double
        pass

    def _on_version_make_top(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        self._versions.setCurrentItem(item)
        self._emit_make_top()

    def _load_selected_version_into_editor(self) -> None:
        item = self._versions.currentItem()
        if item is None:
            return
        text = item.data(Qt.UserRole + 1) or ""
        self._body.setPlainText(text)

    def _emit_make_top(self) -> None:
        item = self._versions.currentItem()
        block = self.current_block()
        if item is None or block < 0:
            return
        vid = str(item.data(Qt.UserRole) or "")
        if not vid:
            return
        # Also load into editor so user sees it
        text = item.data(Qt.UserRole + 1) or ""
        self._body.setPlainText(text)
        self.setActiveVersionRequested.emit(block, vid)
