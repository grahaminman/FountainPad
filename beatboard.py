"""
beatboard.py — Freeform beat board (C4) for FountainPad.

Developer notes
---------------
BeatBoard is a right-side panel (like SceneNavigator/CardNavigator).

C4 (2026-07-26)
  Spatial canvas of [[beat: Label | x=… | y=…]] markers.
  Drag cards on the board; positions write back into the Fountain marker
  (debounced). Beats without coords get a temporary auto-grid layout until
  the user runs Layout Grid or drags them (drag persists coords).

Data flow
  MainWindow._refresh_beat_board()
    → editor.list_beat_infos() → BeatInfo list
    → beat_board.set_beat_infos(...)
  Click card
    → beatActivated(block_number)
  Drag finished
    → beatMoved(block_number, x, y)
    → MainWindow persists via editor.set_beat_board_position
  Layout Grid / New Beat buttons → signals for MainWindow

Theming
  apply_theme(dark) styles chrome + canvas; MainWindow passes global dark flag.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import cards as cards_mod

CARD_W = 148.0
CARD_H = 88.0
GRID = 8.0


class BeatCardItem(QGraphicsItem):
    """Draggable beat sticky on the freeform board."""

    def __init__(
        self,
        info: cards_mod.BeatInfo,
        dark: bool,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)
        self.info = info
        self.block_number = info.block_number
        self._dark = dark
        self._selected = False
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.OpenHandCursor)
        self._dragging = False
        tip = f"{info.label}\nScene: {info.scene_heading}\nLine {info.block_number + 1}"
        self.setToolTip(tip)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(0, 0, CARD_W, CARD_H)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        del option, widget
        r = self.boundingRect().adjusted(0.5, 0.5, -0.5, -0.5)
        if self._dark:
            fill = QColor("#3a2f1a") if not self._selected else QColor("#5a4820")
            border = QColor("#d4a017") if self._selected else QColor("#8a7340")
            title_c = QColor("#f5e6b8")
            body_c = QColor("#c8b98a")
            scene_c = QColor("#9a8b6a")
        else:
            fill = QColor("#fff8dc") if not self._selected else QColor("#ffe9a8")
            border = QColor("#c9a227") if self._selected else QColor("#c4b48a")
            title_c = QColor("#3a2f10")
            body_c = QColor("#5a4a28")
            scene_c = QColor("#7a6a48")

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(border, 1.5 if self._selected else 1.0))
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(r, 6, 6)

        # Title
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        painter.setFont(title_font)
        painter.setPen(title_c)
        title = self.info.label or "Beat"
        painter.drawText(
            QRectF(8, 6, CARD_W - 16, 22),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
            title,
        )

        # Note (if different from label)
        body_font = QFont()
        body_font.setPointSize(9)
        painter.setFont(body_font)
        painter.setPen(body_c)
        note = (self.info.note or "").strip()
        if note and note != title:
            painter.drawText(
                QRectF(8, 28, CARD_W - 16, 34),
                Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                note,
            )

        # Parent scene footer
        scene_font = QFont()
        scene_font.setPointSize(8)
        painter.setFont(scene_font)
        painter.setPen(scene_c)
        scene = (self.info.scene_heading or "").strip()
        if len(scene) > 28:
            scene = scene[:25] + "…"
        painter.drawText(
            QRectF(8, CARD_H - 22, CARD_W - 16, 16),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
            scene,
        )

    def set_selected_look(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.LeftButton:
            self._dragging = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self.setCursor(Qt.OpenHandCursor)
        was_drag = self._dragging
        self._dragging = False
        super().mouseReleaseEvent(event)
        # Snap to grid
        pos = self.pos()
        nx = round(pos.x() / GRID) * GRID
        ny = round(pos.y() / GRID) * GRID
        if nx < 0:
            nx = 0
        if ny < 0:
            ny = 0
        self.setPos(nx, ny)
        scene = self.scene()
        board = scene.board if scene is not None else None  # type: ignore[attr-defined]
        if board is None:
            return
        if was_drag:
            board._on_card_moved(self)
        else:
            board._on_card_clicked(self)


class BeatGraphicsScene(QGraphicsScene):
    """Scene that knows its parent BeatBoard."""

    def __init__(self, board: "BeatBoard") -> None:
        super().__init__(board)
        self.board = board


class BeatBoard(QWidget):
    """Right-side freeform beat canvas (C4)."""

    beatActivated = Signal(int)  # document block number
    beatMoved = Signal(int, float, float)  # block, x, y
    layoutRequested = Signal()
    newBeatRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("BeatBoard")
        self.setMinimumWidth(200)
        self.setMaximumWidth(560)

        title = QLabel("Beat Board")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter beats…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._btn_layout = QToolButton()
        self._btn_layout.setText("Layout grid")
        self._btn_layout.setToolTip("Assign a grid of x/y positions to all beats")
        self._btn_layout.clicked.connect(self.layoutRequested.emit)

        self._btn_new = QToolButton()
        self._btn_new.setText("+ Beat")
        self._btn_new.setToolTip("Insert a [[beat: …]] marker at the cursor")
        self._btn_new.clicked.connect(self.newBeatRequested.emit)

        self._count = QLabel("0 beats")
        self._count.setObjectName("BeatBoardCount")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._count)

        tools = QHBoxLayout()
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(4)
        tools.addWidget(self._btn_new)
        tools.addWidget(self._btn_layout)
        tools.addStretch(1)

        self._scene = BeatGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing
        )
        self._view.setDragMode(QGraphicsView.RubberBandDrag)
        self._view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._view.setFrameShape(QFrame.NoFrame)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Compat: smoke tests used _list.count() — expose count()
        self._list = self  # type: ignore[assignment]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._filter)
        layout.addLayout(tools)
        layout.addWidget(self._view, 1)

        self._all_beats: list[cards_mod.BeatInfo] = []
        self._items: dict[int, BeatCardItem] = {}
        self._dark = False
        self._updating = False
        self._selected_block = -1

    # --- public API -------------------------------------------------------

    def count(self) -> int:
        """Visible beat cards (filter-aware)."""
        n = 0
        for item in self._items.values():
            if item.isVisible():
                n += 1
        return n

    def set_beat_infos(self, beats: list[cards_mod.BeatInfo]) -> None:
        """Replace board contents from BeatInfo list."""
        self._all_beats = list(beats)
        self._rebuild()

    def set_beats(self, beats: list[tuple[int, str, str, str]]) -> None:
        """Compat: tuples without coordinates (auto-grid display only)."""
        infos = [
            cards_mod.BeatInfo(
                block_number=bn,
                label=bt,
                note=txt,
                scene_heading=scene,
            )
            for bn, bt, txt, scene in beats
        ]
        self.set_beat_infos(infos)

    def highlight_block(self, block_number: int) -> None:
        """Select the beat at/above the cursor block."""
        if not self._all_beats:
            return
        target = -1
        for b in self._all_beats:
            if b.block_number <= block_number:
                target = b.block_number
            else:
                break
        if target < 0:
            return
        self._selected_block = target
        for bn, item in self._items.items():
            item.set_selected_look(bn == target)
            if bn == target:
                self._view.ensureVisible(item, 20, 20)

    def apply_theme(self, dark: bool) -> None:
        """Theme board chrome + canvas."""
        self._dark = dark
        if dark:
            canvas = "#1a1a1a"
            self.setStyleSheet(
                f"""
                QWidget#BeatBoard {{
                    background-color: #252526;
                    color: #dddddd;
                    border-left: 1px solid #3e3e42;
                }}
                QLineEdit {{
                    background: #1e1e1e;
                    color: #dddddd;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    padding: 4px 6px;
                    selection-background-color: #094771;
                    selection-color: #ffffff;
                }}
                QToolButton {{
                    background: #3e3e42;
                    color: #dddddd;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 3px 8px;
                }}
                QToolButton:hover {{ background: #4a4a4e; }}
                QGraphicsView {{
                    background: {canvas};
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                }}
                QLabel#BeatBoardCount {{ color: #999999; font-size: 11px; }}
                """
            )
            self._view.setBackgroundBrush(QBrush(QColor(canvas)))
        else:
            canvas = "#f4f1e8"
            self.setStyleSheet(
                f"""
                QWidget#BeatBoard {{
                    background-color: #f0f0f0;
                    color: #1a1a1a;
                    border-left: 1px solid #d0d0d0;
                }}
                QLineEdit {{
                    background: #ffffff;
                    color: #1a1a1a;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 6px;
                    selection-background-color: #b3d7ff;
                    selection-color: #000000;
                }}
                QToolButton {{
                    background: #ffffff;
                    color: #1a1a1a;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 3px 8px;
                }}
                QToolButton:hover {{ background: #eef6ff; }}
                QGraphicsView {{
                    background: {canvas};
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }}
                QLabel#BeatBoardCount {{ color: #555555; font-size: 11px; }}
                """
            )
            self._view.setBackgroundBrush(QBrush(QColor(canvas)))
        # Restyle existing cards
        for item in self._items.values():
            item._dark = dark
            item.update()

    # --- internals --------------------------------------------------------

    def _default_positions(
        self, beats: list[cards_mod.BeatInfo]
    ) -> dict[int, tuple[float, float]]:
        """Positions for display: saved x/y, else auto-grid (not written until layout/drag)."""
        pos: dict[int, tuple[float, float]] = {}
        missing = [b for b in beats if b.x is None or b.y is None]
        laid = {
            bn: (x, y)
            for bn, x, y in cards_mod.auto_layout_beat_positions(missing)
        }
        for b in beats:
            if b.x is not None and b.y is not None:
                pos[b.block_number] = (float(b.x), float(b.y))
            else:
                pos[b.block_number] = laid.get(b.block_number, (24.0, 24.0))
        return pos

    def _rebuild(self) -> None:
        needle = self._filter.text().strip().lower()
        self._updating = True
        self._scene.clear()
        self._items.clear()

        visible = []
        for b in self._all_beats:
            if needle:
                blob = f"{b.label} {b.note} {b.scene_heading}".lower()
                if needle not in blob:
                    continue
            visible.append(b)

        positions = self._default_positions(visible)
        max_x = max_y = 200.0
        for b in visible:
            item = BeatCardItem(b, self._dark)
            x, y = positions[b.block_number]
            item.setPos(x, y)
            if b.block_number == self._selected_block:
                item.set_selected_look(True)
            self._scene.addItem(item)
            self._items[b.block_number] = item
            max_x = max(max_x, x + CARD_W + 40)
            max_y = max(max_y, y + CARD_H + 40)

        self._scene.setSceneRect(0, 0, max_x, max_y)

        total = len(self._all_beats)
        shown = len(visible)
        if needle:
            self._count.setText(f"{shown}/{total} beats")
        else:
            self._count.setText(f"{total} beat" if total == 1 else f"{total} beats")
        self._updating = False

    def _apply_filter(self, _text: str) -> None:
        self._rebuild()

    def _on_card_clicked(self, item: BeatCardItem) -> None:
        if self._updating:
            return
        self._selected_block = item.block_number
        for bn, it in self._items.items():
            it.set_selected_look(bn == item.block_number)
        self.beatActivated.emit(item.block_number)

    def _on_card_moved(self, item: BeatCardItem) -> None:
        if self._updating:
            return
        pos = item.pos()
        self._selected_block = item.block_number
        for bn, it in self._items.items():
            it.set_selected_look(bn == item.block_number)
        # Expand scene if needed
        br = self._scene.itemsBoundingRect().adjusted(0, 0, 40, 40)
        self._scene.setSceneRect(self._scene.sceneRect().united(br))
        self.beatMoved.emit(item.block_number, float(pos.x()), float(pos.y()))
