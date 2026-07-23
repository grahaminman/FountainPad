"""
editor.py — Fountain source editor + syntax highlighter.

Developer notes
---------------
FountainEditor
  QPlainTextEdit configured for screenplay source:
  - monospace font (Menlo → Consolas → Courier New fallback)
  - gutter line numbers (LineNumberArea)
  - current-line highlight
  - contentChanged signal (used by MainWindow for dirty flag + preview sync)
  - word wrap toggled by MainWindow when split preview is shown/hidden

Scene helpers (used by navigator + status bar)
  is_scene_heading(text)     INT/EXT/EST/I/E or forced ".HEADING"
  list_scene_headings()      [(block_number, heading), ...] document order
  goto_block(n)              jump + centre + focus
  current_scene_heading()    walk upward from cursor to nearest heading

FountainHighlighter
  Line-oriented Fountain rules (not a full parser). Block state 1 = dialogue
  context after a character cue until a blank line.
  Shared regexes (re_scene, re_scene_dot, …) are public so navigator/status
  can reuse the same definitions via editor.highlighter().

Not responsible for
  File I/O, menus, PDF, or preview HTML — those live in mainwindow/preview.
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
    QTextFormat,
    QTextOption,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


class FountainHighlighter(QSyntaxHighlighter):
    """Lightweight Fountain syntax highlighting (line rules + dialogue state)."""

    def __init__(self, document: QTextDocument, dark: bool = False) -> None:
        super().__init__(document)
        self._dark = dark
        self._rebuild_formats()

    def set_dark(self, dark: bool) -> None:
        if self._dark == dark:
            return
        self._dark = dark
        self._rebuild_formats()
        self.rehighlight()

    def _fmt(self, color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Bold)
        if italic:
            f.setFontItalic(True)
        return f

    def _rebuild_formats(self) -> None:
        if self._dark:
            self.fmt_scene = self._fmt("#7eb6ff", bold=True)
            self.fmt_character = self._fmt("#f0c674", bold=True)
            self.fmt_parenthetical = self._fmt("#b5bd68", italic=True)
            self.fmt_dialogue = self._fmt("#c5c8c6")
            self.fmt_transition = self._fmt("#de935f", bold=True)
            self.fmt_section = self._fmt("#b294bb", bold=True)
            self.fmt_synopsis = self._fmt("#8abeb7", italic=True)
            self.fmt_note = self._fmt("#969896", italic=True)
            self.fmt_title_key = self._fmt("#81a2be", bold=True)
            self.fmt_boneyard = self._fmt("#5a5f66", italic=True)
            self.fmt_page_break = self._fmt("#969896")
        else:
            self.fmt_scene = self._fmt("#0b57d0", bold=True)
            self.fmt_character = self._fmt("#8a5a00", bold=True)
            self.fmt_parenthetical = self._fmt("#3d6b1e", italic=True)
            self.fmt_dialogue = self._fmt("#222222")
            self.fmt_transition = self._fmt("#a24700", bold=True)
            self.fmt_section = self._fmt("#6a1b9a", bold=True)
            self.fmt_synopsis = self._fmt("#00695c", italic=True)
            self.fmt_note = self._fmt("#6d6d6d", italic=True)
            self.fmt_title_key = self._fmt("#1565c0", bold=True)
            self.fmt_boneyard = self._fmt("#9e9e9e", italic=True)
            self.fmt_page_break = self._fmt("#757575")

        # Scene: INT./EXT./EST./I/E… or forced scene via leading "."
        self.re_scene = re.compile(
            r"^(?:\s*)((?:INT|EXT|EST|I/?E|INT\./EXT|INT/EXT)[\.\s].+)$",
            re.IGNORECASE,
        )
        self.re_scene_dot = re.compile(r"^(?:\s*)\.(?!\.)(.+)$")
        self.re_transition = re.compile(
            r"^(?:\s*)((?:FADE (?:TO BLACK|OUT)|CUT TO BLACK)\.?|.+ TO:)$",
            re.IGNORECASE,
        )
        self.re_transition_gt = re.compile(r"^(?:\s*)>(?!.*>)(.+)$")
        self.re_section = re.compile(r"^(?:\s*)(#{1,6})\s+(.*)$")
        self.re_synopsis = re.compile(r"^(?:\s*)=(?!=)\s*(.*)$")
        self.re_note = re.compile(r"^(?:\s*)\[\[(.*)\]\]\s*$")
        self.re_parenthetical = re.compile(r"^(?:\s*)(\(.+\))\s*$")
        self.re_character = re.compile(
            r"^(?:\s*)([A-Z][A-Z0-9 \.\-'\(\)]+?)(\s*\^)?\s*$"
        )
        self.re_title_key = re.compile(
            r"^(Title|Credit|Author|Authors|Source|Notes|Draft date|Date|Contact|Copyright)\s*:",
            re.IGNORECASE,
        )
        self.re_page_break = re.compile(r"^(?:\s*)={3,}\s*$")
        self.re_boneyard_line = re.compile(r"^(?:\s*)(/\*|\*/)")

    def highlightBlock(self, text: str) -> None:
        stripped = text.strip()
        if not stripped:
            # Blank line ends dialogue context (state 1 → 0).
            prev = self.previousBlockState()
            self.setCurrentBlockState(1 if prev == 1 else 0)
            # Actually blank should clear dialogue — Fountain dialogue stops at blank.
            self.setCurrentBlockState(0)
            return

        if self.re_boneyard_line.match(text):
            self.setFormat(0, len(text), self.fmt_boneyard)
            self.setCurrentBlockState(0)
            return

        if self.re_page_break.match(text):
            self.setFormat(0, len(text), self.fmt_page_break)
            self.setCurrentBlockState(0)
            return

        if self.re_title_key.match(text):
            self.setFormat(0, len(text), self.fmt_title_key)
            self.setCurrentBlockState(0)
            return

        if self.re_section.match(text):
            self.setFormat(0, len(text), self.fmt_section)
            self.setCurrentBlockState(0)
            return

        if self.re_synopsis.match(text):
            self.setFormat(0, len(text), self.fmt_synopsis)
            self.setCurrentBlockState(0)
            return

        if self.re_note.match(text):
            self.setFormat(0, len(text), self.fmt_note)
            self.setCurrentBlockState(0)
            return

        if self.re_scene.match(text) or self.re_scene_dot.match(text):
            self.setFormat(0, len(text), self.fmt_scene)
            self.setCurrentBlockState(0)
            return

        if self.re_transition.match(text) or (
            text.lstrip().startswith(">") and not text.rstrip().endswith("<")
        ):
            # Avoid centered text: > like this <
            if not (text.strip().startswith(">") and text.strip().endswith("<")):
                self.setFormat(0, len(text), self.fmt_transition)
                self.setCurrentBlockState(0)
                return

        if self.re_parenthetical.match(text):
            self.setFormat(0, len(text), self.fmt_parenthetical)
            prev = self.previousBlockState()
            self.setCurrentBlockState(1 if prev == 1 else 0)
            return

        # Character cue → next non-blank lines are dialogue (block state 1).
        prev_state = self.previousBlockState()
        if self.re_character.match(stripped) and not stripped.endswith(":"):
            if len(stripped) <= 40 and not stripped.startswith("[["):
                self.setFormat(0, len(text), self.fmt_character)
                self.setCurrentBlockState(1)
                return

        if prev_state == 1:
            self.setFormat(0, len(text), self.fmt_dialogue)
            self.setCurrentBlockState(1)
            return

        self.setCurrentBlockState(0)


class LineNumberArea(QWidget):
    """Gutter painted by FountainEditor.line_number_area_paint_event."""

    def __init__(self, editor: "FountainEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self.editor.line_number_area_paint_event(event)


class FountainEditor(QPlainTextEdit):
    """Monospace Fountain editor with line numbers and scene helpers."""

    contentChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        font = QFont("Menlo")
        if not font.exactMatch():
            font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Courier New")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(12)
        self.setFont(font)
        # Default: no wrap (full-width). MainWindow enables wrap in split view.
        self.set_word_wrap(False)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self.contentChanged.emit)

        self._dark = False
        self._highlighter = FountainHighlighter(self.document(), dark=False)
        self.update_line_number_area_width(0)
        self.apply_theme(False)

    def highlighter(self) -> FountainHighlighter:
        return self._highlighter

    def set_word_wrap(self, enabled: bool) -> None:
        """Wrap long lines to the editor width (useful in split view)."""
        if enabled:
            self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        else:
            self.setLineWrapMode(QPlainTextEdit.NoWrap)

    def apply_theme(self, dark: bool) -> None:
        self._dark = dark
        self._highlighter.set_dark(dark)
        if dark:
            self.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    selection-background-color: #264f78;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #fafafa;
                    color: #1a1a1a;
                    border: none;
                    selection-background-color: #cde8ff;
                }
                """
            )
        self.highlight_current_line()

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        space = 12 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def update_line_number_area_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            cr.left(), cr.top(), self.line_number_area_width(), cr.height()
        )

    def line_number_area_paint_event(self, event) -> None:
        from PySide6.QtGui import QPainter

        painter = QPainter(self._line_number_area)
        bg = QColor("#252526" if self._dark else "#ececec")
        fg = QColor("#858585" if self._dark else "#888888")
        painter.fillRect(event.rect(), bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(fg)
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self) -> None:
        if self.isReadOnly():
            return
        selection = QTextEdit.ExtraSelection()
        line_color = QColor("#2a2d2e" if self._dark else "#fff8d6")
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def is_scene_heading(self, text: str) -> bool:
        """True if a line is a Fountain scene heading (INT/EXT or forced .heading)."""
        stripped = text.strip()
        if not stripped:
            return False
        return bool(
            self._highlighter.re_scene.match(stripped)
            or self._highlighter.re_scene_dot.match(stripped)
        )

    def list_scene_headings(self) -> list[tuple[int, str]]:
        """Return (block_number, heading_text) for every scene heading in order."""
        scenes: list[tuple[int, str]] = []
        block = self.document().firstBlock()
        while block.isValid():
            text = block.text()
            if self.is_scene_heading(text):
                scenes.append((block.blockNumber(), text.strip()))
            block = block.next()
        return scenes

    def goto_block(self, block_number: int) -> None:
        """Move cursor to the start of a document block and centre it in view."""
        block = self.document().findBlockByNumber(block_number)
        if not block.isValid():
            return
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus(Qt.OtherFocusReason)

    def current_scene_heading(self) -> str:
        """Walk upward from cursor to find nearest scene heading."""
        cursor = self.textCursor()
        block = cursor.block()
        while block.isValid():
            text = block.text().strip()
            if self.is_scene_heading(text):
                return text
            block = block.previous()
        return ""

    def list_cards(self) -> list[tuple[int, str, str, str]]:
        """
        Parse Fountain for [[card: Type]] blocks and link to nearest scene.
        Returns: [(block_number, card_type, card_text, scene_heading), ...]
        
        Handles:
          - Nested brackets: [[card: Goal (Midpoint)]]
          - Malformed cards: [[card:Goal]] (no space after colon)
          - Valid card types: Goal, Conflict, Turn, or custom
        """
        cards: list[tuple[int, str, str, str]] = []
        scene_heading = "Untitled Scene"
        block = self.document().firstBlock()
        while block.isValid():
            text = block.text().strip()
            if self.is_scene_heading(text):
                scene_heading = text
            elif text.startswith("[[card:") and text.endswith("]]"):
                # Extract inner text: [[card: Goal (Midpoint)]] → "Goal (Midpoint)"
                inner = text[7:-2].strip()
                card_type = "Card"
                card_text = inner
                
                # Split on first colon or space (handle malformed cards).
                if ":" in inner:
                    parts = inner.split(":", 1)
                    card_type = parts[0].strip()
                    card_text = parts[1].strip()
                elif " " in inner:
                    parts = inner.split(" ", 1)
                    card_type = parts[0]
                    card_text = parts[1].strip()
                
                # Validate card type (Goal/Conflict/Turn or custom).
                valid_types = {"Goal", "Conflict", "Turn"}
                if card_type not in valid_types:
                    card_type = "Card"
                
                # Check if the next line is indented (card content).
                next_block = block.next()
                if next_block.isValid():
                    next_text = next_block.text().strip()
                    if next_text and not self.is_scene_heading(next_text) and not next_text.startswith("[[card:"):
                        card_text = f"{card_text} {next_text}" if card_text else next_text
                
                cards.append((block.blockNumber(), card_type, card_text, scene_heading))
            block = block.next()
        return cards

    def list_beats(self) -> list[tuple[int, str, str, str]]:
        """
        Parse Fountain for [[beat: Type]] blocks and link to nearest scene.
        Returns: [(block_number, beat_type, beat_text, scene_heading), ...]
        
        Handles:
          - Nested brackets: [[beat: Act 1 Climax (Midpoint)]]
          - Malformed beats: [[beat:Act1]] (no space after colon)
        """
        beats: list[tuple[int, str, str, str]] = []
        scene_heading = "Untitled Scene"
        block = self.document().firstBlock()
        while block.isValid():
            text = block.text().strip()
            if self.is_scene_heading(text):
                scene_heading = text
            elif text.startswith("[[beat:") and text.endswith("]]"):
                # Extract inner text: [[beat: Act 1 Climax]] → "Act 1 Climax"
                inner = text[7:-2].strip()
                beat_type = "Beat"
                beat_text = inner
                
                # Split on first colon or space (handle malformed beats).
                if ":" in inner:
                    parts = inner.split(":", 1)
                    beat_type = parts[0].strip()
                    beat_text = parts[1].strip()
                elif " " in inner:
                    parts = inner.split(" ", 1)
                    beat_type = parts[0]
                    beat_text = parts[1].strip()
                
                # Check if the next line is indented (beat content).
                next_block = block.next()
                if next_block.isValid():
                    next_text = next_block.text().strip()
                    if next_text and not self.is_scene_heading(next_text) and not next_text.startswith("[[beat:"):
                        beat_text = f"{beat_text} {next_text}" if beat_text else next_text
                
                beats.append((block.blockNumber(), beat_type, beat_text, scene_heading))
            block = block.next()
        return beats
