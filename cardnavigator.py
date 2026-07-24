"""
cardnavigator.py — Index cards list + editable card detail + versions.

UX:
  - Type in the card body → auto-saves into the active version (debounced).
  - New version = snapshot history; Use this version = choose active.
  - Apply → script pushes heading + action only (never dialogue).
  - Multi-row toolbars + multi-line list labels for narrow panes.
"""

from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import cards as cards_mod


class CardNavigator(QWidget):
    """Left-side index cards: list + editable detail with auto-save."""

    cardActivated = Signal(int)
    cardTemplateRequested = Signal(str)
    generateFromScenesRequested = Signal()
    applyCardRequested = Signal(int)
    saveCardRequested = Signal(int, str, str, object, str, bool)
    setActiveVersionRequested = Signal(int, str)
    reorderCardRequested = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardNavigator")
        self.setMinimumWidth(220)
        self.setMaximumWidth(560)

        title = QLabel("Index Cards")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)

        self._count = QLabel("0 cards")
        self._count.setObjectName("CardNavCount")

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self._count)

        # Row 1 — insert helpers (wrap-friendly; short labels)
        self._btn_goal = self._make_template_button("Goal")
        self._btn_conflict = self._make_template_button("Conflict")
        self._btn_turn = self._make_template_button("Turn")
        self._btn_from_scenes = self._make_tool_button(
            "From scenes",
            "Insert empty card notes under scenes that have none.",
            self.generateFromScenesRequested.emit,
        )
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(4)
        for w in (
            self._btn_goal,
            self._btn_conflict,
            self._btn_turn,
            self._btn_from_scenes,
        ):
            row1.addWidget(w)
        row1.addStretch(1)

        # Row 2 — card actions
        self._btn_apply = self._make_tool_button(
            "Apply → script",
            "Save this card text, then push scene heading + action into the "
            "screenplay. Dialogue is never changed.",
            self._emit_apply,
        )
        self._btn_save = self._make_tool_button(
            "New version",
            "Keep the old text as history and start a new version (v2, v3…).",
            self._emit_save_snapshot,
        )
        self._btn_up = self._make_tool_button(
            "Scene ↑",
            "Move this card's whole scene earlier in the script.",
            lambda: self._emit_reorder(-1),
        )
        self._btn_down = self._make_tool_button(
            "Scene ↓",
            "Move this card's whole scene later in the script.",
            lambda: self._emit_reorder(1),
        )
        # Compat alias (older tests / docs may mention Save inplace)
        self._btn_save_inplace = self._btn_apply

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(4)
        for w in (self._btn_apply, self._btn_save, self._btn_up, self._btn_down):
            row2.addWidget(w)
        row2.addStretch(1)

        self._hint = QLabel(
            "Select a card → type below. Text auto-saves to the card. "
            "Apply → script updates the page (action only)."
        )
        self._hint.setObjectName("CardHint")
        self._hint.setWordWrap(True)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter cards…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setWordWrap(True)
        self._list.setTextElideMode(Qt.ElideNone)
        self._list.setUniformItemSizes(False)
        self._list.setSpacing(3)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.itemActivated.connect(self._emit_item)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.currentItemChanged.connect(self._on_current_changed)

        # Detail pane
        self._detail_title = QLabel("Card (select one)")
        self._detail_title.setObjectName("CardDetailTitle")
        self._detail_title.setWordWrap(True)
        df = QFont()
        df.setBold(True)
        self._detail_title.setFont(df)

        self._type = QComboBox()
        self._type.setEditable(True)
        for t in ("Note", "Goal", "Conflict", "Turn"):
            self._type.addItem(t)
        self._type.setToolTip("Card type")
        self._type.currentTextChanged.connect(self._on_type_changed)

        self._id_label = QLabel("—")
        self._id_label.setObjectName("CardIdLabel")
        self._id_label.setWordWrap(True)

        type_row = QHBoxLayout()
        type_row.setContentsMargins(0, 0, 0, 0)
        type_row.addWidget(QLabel("Type"))
        type_row.addWidget(self._type, 1)
        type_row.addWidget(self._id_label, 1)

        self._body = QPlainTextEdit()
        self._body.setPlaceholderText(
            "Type the card note here.\n"
            "Line 1 can be a scene heading (INT. / EXT. …).\n"
            "More lines = action / planning notes.\n"
            "Auto-saves as you type. Use Apply → script to update the page."
        )
        self._body.setMinimumHeight(140)
        self._body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._body.textChanged.connect(self._on_body_changed)

        self._status = QLabel("")
        self._status.setObjectName("CardSaveStatus")
        self._status.setWordWrap(True)

        self._versions = QListWidget()
        self._versions.setMaximumHeight(110)
        self._versions.setWordWrap(True)
        self._versions.setTextElideMode(Qt.ElideNone)
        self._versions.setUniformItemSizes(False)
        self._versions.itemDoubleClicked.connect(self._on_version_make_top)

        self._btn_make_top = self._make_tool_button(
            "Use this version",
            "Make the selected history version active "
            "(then Apply to put it on the page).",
            self._emit_make_top,
        )
        self._btn_load_ver = self._make_tool_button(
            "Show in editor",
            "Load the selected version into the text box "
            "(does not change active until auto-save or Use this version).",
            self._load_selected_version_into_editor,
        )

        ver_row = QHBoxLayout()
        ver_row.setContentsMargins(0, 0, 0, 0)
        ver_lab = QLabel("History")
        ver_lab.setWordWrap(True)
        ver_row.addWidget(ver_lab)
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
        dlay.addWidget(self._status)
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
        layout.addLayout(title_row)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self._hint)
        layout.addWidget(self._filter)
        layout.addWidget(split, 1)

        self._all_cards: list = []
        self._all_infos: List[Any] = []
        self._updating = False
        self._loading_detail = False
        self._current_block: int = -1
        self._current_info: Any = None
        self._dirty_detail = False
        self._suppress_autosave = False

        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(450)
        self._autosave.timeout.connect(self._flush_autosave)

    def _make_template_button(self, card_type: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(card_type)
        btn.setToolTip(f"Insert a new {card_type} card at the cursor in the script")
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.clicked.connect(lambda: self.cardTemplateRequested.emit(card_type))
        return btn

    def _make_tool_button(self, text: str, tip: str, slot) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.clicked.connect(slot)
        return btn

    def set_cards(self, cards: list) -> None:
        self._all_cards = list(cards)
        self._all_infos = []
        self._rebuild_list()

    def set_card_infos(self, infos) -> None:
        """Refresh list from editor parse. Preserves in-progress typing."""
        prev_block = self._current_block
        keep_text = None
        keep_type = None
        if (
            self._dirty_detail
            and prev_block >= 0
            and self._current_info is not None
            and not self._loading_detail
        ):
            keep_text = self._body.toPlainText()
            keep_type = self.working_type()

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

        target_block = prev_block
        if target_block < 0 and self._list.count():
            target_block = int(self._list.item(0).data(Qt.UserRole))

        if target_block >= 0:
            for row in range(self._list.count()):
                item = self._list.item(row)
                if item and int(item.data(Qt.UserRole)) == target_block:
                    self._updating = True
                    self._list.setCurrentRow(row)
                    self._updating = False
                    info = self._info_for_block(target_block)
                    if info is not None:
                        # After autosave, panel matches file — don't re-dirty.
                        preserve = None
                        preserve_t = None
                        if keep_text is not None:
                            file_text = (info.active_text or "").strip()
                            if keep_text.strip() != file_text:
                                preserve = keep_text
                        if keep_type is not None and keep_type != (info.card_type or "Note"):
                            preserve_t = keep_type
                        self._load_detail(
                            info,
                            preserve_text=preserve,
                            preserve_type=preserve_t,
                        )
                    return
        if self._list.count() and self._list.currentRow() < 0:
            self._list.setCurrentRow(0)

    def current_block(self) -> int:
        item = self._list.currentItem()
        if item is None:
            return self._current_block
        return int(item.data(Qt.UserRole))

    def working_text(self) -> str:
        return self._body.toPlainText()

    def working_type(self) -> str:
        return (self._type.currentText() or "Note").strip() or "Note"

    def flush_pending_save(self) -> None:
        """Call before Apply / switch so the latest keystrokes are stored."""
        if self._autosave.isActive():
            self._autosave.stop()
        if self._dirty_detail:
            self._flush_autosave()

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
                QListWidget::item { padding: 8px; }
                QListWidget::item:hover { background: #2a2d2e; color: #ffffff; }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #094771; color: #ffffff;
                }
                QLabel#CardNavCount, QLabel#CardIdLabel, QLabel#CardHint,
                QLabel#CardSaveStatus { color: #999999; font-size: 11px; }
                QLabel#CardDetailTitle { color: #cccccc; }
                QToolButton {
                    color: #dddddd;
                    padding: 3px 6px;
                    border-radius: 3px;
                }
                QToolButton:hover { background: #2a2d2e; }
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
                QListWidget::item { padding: 8px; }
                QListWidget::item:hover { background: #eef6ff; color: #000000; }
                QListWidget::item:selected,
                QListWidget::item:selected:active,
                QListWidget::item:selected:!active {
                    background: #b3d7ff; color: #000000;
                }
                QLabel#CardNavCount, QLabel#CardIdLabel, QLabel#CardHint,
                QLabel#CardSaveStatus { color: #555555; font-size: 11px; }
                QLabel#CardDetailTitle { color: #333333; }
                QToolButton {
                    color: #1a1a1a;
                    padding: 3px 6px;
                    border-radius: 3px;
                }
                QToolButton:hover { background: #e8e8e8; }
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

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._resize_list_items()

    def _info_for_block(self, block: int):
        for info in self._all_infos:
            if info.block_number == block:
                return info
        return None

    def _item_size_hint(self, label: str) -> QSize:
        """Height for multi-line labels in a narrow pane."""
        width = max(120, self._list.viewport().width() - 16)
        metrics = self._list.fontMetrics()
        # Count explicit newlines + wrap estimate
        lines = label.split("\n") if label else [""]
        height = 0
        for line in lines:
            br = metrics.boundingRect(0, 0, width, 4000, Qt.TextWordWrap, line or " ")
            height += max(metrics.lineSpacing(), br.height())
        height += 16  # padding
        return QSize(width, height)

    def _resize_list_items(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            item.setSizeHint(self._item_size_hint(item.text()))
        self._list.doItemsLayout()

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
                (bn, f"{ctype}\n{ctext}", scene, "", ctext)
                for bn, ctype, ctext, scene in self._all_cards
            ]
        for block_number, label, scene_heading, card_id, body in rows:
            if needle:
                search_text = f"{label} {scene_heading} {card_id} {body}".lower()
                if needle not in search_text:
                    continue
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, block_number)
            tip_parts = [f"Line {block_number + 1}"]
            if card_id:
                tip_parts.insert(0, f"id={card_id}")
            if scene_heading:
                tip_parts.append(f"Scene: {scene_heading}")
            if body:
                tip_parts.append("")
                tip_parts.append(body[:400])
            item.setToolTip("\n".join(tip_parts))
            item.setSizeHint(self._item_size_hint(label))
            self._list.addItem(item)
            shown += 1
        total = len(rows)
        if needle:
            self._count.setText(f"{shown}/{total}")
        else:
            self._count.setText(f"{total} card" if total == 1 else f"{total} cards")
        self._updating = False
        self._resize_list_items()

    def _apply_filter(self, _text: str) -> None:
        self._rebuild_list()

    def _emit_item(self, item: QListWidgetItem) -> None:
        if self._updating or item is None:
            return
        block_number = int(item.data(Qt.UserRole))
        self.cardActivated.emit(block_number)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self._emit_item(item)

    def _on_current_changed(self, current, previous) -> None:
        if self._updating:
            return
        if previous is not None and self._dirty_detail:
            self.flush_pending_save()
        if current is None:
            return
        block_number = int(current.data(Qt.UserRole))
        info = self._info_for_block(block_number)
        if info is not None:
            self._load_detail(info)

    def _load_detail(
        self,
        info,
        preserve_text: Optional[str] = None,
        preserve_type: Optional[str] = None,
    ) -> None:
        self._loading_detail = True
        self._autosave.stop()
        self._current_block = info.block_number
        self._current_info = info
        cid = info.card_id or "—"
        self._id_label.setText(f"{cid}  ·  active {info.active_version}")
        self._detail_title.setText(f"Editing card {cid}")
        t = preserve_type if preserve_type is not None else (info.card_type or "Note")
        idx = self._type.findText(t)
        if idx >= 0:
            self._type.setCurrentIndex(idx)
        else:
            self._type.setEditText(t)
        body = preserve_text if preserve_text is not None else info.active_text
        self._body.setPlainText(body or "")
        self._versions.clear()
        for v in info.versions or []:
            mark = "● " if v.version_id == info.active_version else "○ "
            preview = (v.text or "").strip().splitlines()
            head = preview[0] if preview else "(empty)"
            extra = preview[1] if len(preview) > 1 else ""
            label = f"{mark}{v.version_id}\n{head}"
            if extra:
                label += f"\n{extra}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, v.version_id)
            item.setData(Qt.UserRole + 1, v.text)
            item.setToolTip(v.text[:800] if v.text else "(empty)")
            item.setSizeHint(self._item_size_hint(label))
            self._versions.addItem(item)
        self._dirty_detail = preserve_text is not None
        if self._dirty_detail:
            self._status.setText("Unsaved changes — will auto-save")
        else:
            self._status.setText("Editing — saves automatically")
        self._loading_detail = False

    def _on_body_changed(self) -> None:
        if self._loading_detail or self._suppress_autosave or self._current_info is None:
            return
        self._dirty_detail = True
        self._status.setText("Typing… will auto-save")
        self._autosave.start()

    def _on_type_changed(self, _text: str) -> None:
        if self._loading_detail or self._suppress_autosave or self._current_info is None:
            return
        self._dirty_detail = True
        self._status.setText("Type changed… will auto-save")
        self._autosave.start()

    def _flush_autosave(self) -> None:
        if self._loading_detail or not self._dirty_detail:
            return
        if self._current_info is None or self._current_block < 0:
            return
        self._emit_save(make_snapshot=False)
        self._dirty_detail = False
        self._status.setText("Saved to card")

    def _emit_apply(self) -> None:
        self.flush_pending_save()
        block = self.current_block()
        if block < 0:
            return
        self.applyCardRequested.emit(block)

    def _emit_reorder(self, direction: int) -> None:
        self.flush_pending_save()
        block = self.current_block()
        if block < 0:
            return
        self.reorderCardRequested.emit(block, int(direction))

    def _emit_save_snapshot(self) -> None:
        self.flush_pending_save()
        self._emit_save(make_snapshot=True)

    def _emit_save(self, make_snapshot: bool) -> None:
        info = self._current_info
        block = self._current_block if self._current_block >= 0 else self.current_block()
        if info is None or block < 0:
            return
        versions = (
            list(info.versions)
            if info.versions
            else [cards_mod.CardVersion("v1", info.body or "")]
        )
        active = info.active_version or "v1"
        card_id = info.card_id or ""
        card_type = self.working_type()
        text = self.working_text()
        if make_snapshot:
            versions, active, created = cards_mod.snapshot_version(
                versions, active, text
            )
            if created:
                self._status.setText(f"New version {active}")
        else:
            new_versions = []
            found = False
            for v in versions:
                if v.version_id == active:
                    new_versions.append(
                        cards_mod.CardVersion(v.version_id, text.strip())
                    )
                    found = True
                else:
                    new_versions.append(v)
            if not found:
                new_versions.append(
                    cards_mod.CardVersion(active or "v1", text.strip())
                )
            versions = new_versions
        self.saveCardRequested.emit(
            block, card_id, card_type, versions, active, make_snapshot
        )
        # Keep local model in sync so further typing doesn't fight refresh
        try:
            info.versions = versions
            info.active_version = active
            info.card_type = card_type
            if hasattr(cards_mod, "format_versions_body"):
                info.body = cards_mod.format_versions_body(versions, active)
            else:
                info.body = text.strip()
        except Exception:
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
        self._loading_detail = True
        self._body.setPlainText(text)
        self._loading_detail = False
        self._dirty_detail = True
        self._status.setText(
            "Loaded history into editor — will auto-save as active text"
        )
        self._autosave.start()

    def _emit_make_top(self) -> None:
        self.flush_pending_save()
        item = self._versions.currentItem()
        block = self.current_block()
        if item is None or block < 0:
            return
        vid = str(item.data(Qt.UserRole) or "")
        if not vid:
            return
        text = item.data(Qt.UserRole + 1) or ""
        self._loading_detail = True
        self._body.setPlainText(text)
        self._loading_detail = False
        self._dirty_detail = False
        self.setActiveVersionRequested.emit(block, vid)
