"""Fountain text editor widget and syntax highlighter."""

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
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


class FountainHighlighter(QSyntaxHighlighter):
    """Lightweight Fountain syntax highlighting."""

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
            # Still track previous block state for dialogue context
            prev = self.previousBlockState()
            self.setCurrentBlockState(1 if prev == 1 else 0)
            return

        # Boneyard markers
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
            # avoid centered > text <
            if not (text.strip().startswith(">") and text.strip().endswith("<")):
                self.setFormat(0, len(text), self.fmt_transition)
                self.setCurrentBlockState(0)
                return

        if self.re_parenthetical.match(text):
            self.setFormat(0, len(text), self.fmt_parenthetical)
            # stay in dialogue context if we were in one
            prev = self.previousBlockState()
            self.setCurrentBlockState(1 if prev == 1 else 0)
            return

        # Character cue: all-caps line, not a scene/transition, previous blank-ish
        prev_state = self.previousBlockState()
        if self.re_character.match(stripped) and not stripped.endswith(":"):
            # Avoid matching action that happens to be caps if too long with lowercase — already caps-only
            if len(stripped) <= 40 and not stripped.startswith("[["):
                self.setFormat(0, len(text), self.fmt_character)
                self.setCurrentBlockState(1)  # next lines may be dialogue
                return

        if prev_state == 1:
            # Dialogue block until blank line (blank handled above)
            self.setFormat(0, len(text), self.fmt_dialogue)
            self.setCurrentBlockState(1)
            return

        self.setCurrentBlockState(0)


class LineNumberArea(QWidget):
    def __init__(self, editor: "FountainEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self.editor.line_number_area_paint_event(event)


class FountainEditor(QPlainTextEdit):
    """Monospace Fountain editor with line numbers."""

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
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
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

    def current_scene_heading(self) -> str:
        """Walk upward from cursor to find nearest scene heading."""
        cursor = self.textCursor()
        block = cursor.block()
        while block.isValid():
            text = block.text().strip()
            if self._highlighter.re_scene.match(text) or self._highlighter.re_scene_dot.match(
                text
            ):
                return text
            block = block.previous()
        return ""
