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
  - autocomplete (QCompleter): characters, scenes/locations, common elements;
    Ctrl/Cmd+Space force; auto-popup on scene prefixes / uppercase cues

Scene helpers (used by navigator + status bar)
  is_scene_heading(text)     INT/EXT/EST/I/E or forced ".HEADING"
  list_scene_headings()      [(block_number, heading), ...] document order
  list_outline_nodes()       N4: sections (#) + scenes for outline tree
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

from PySide6.QtCore import QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextOption,
)
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

import cards as cards_mod


class FountainHighlighter(QSyntaxHighlighter):
    """Lightweight Fountain syntax highlighting (line rules + dialogue state)."""

    def __init__(self, document: QTextDocument, dark: bool = False) -> None:
        super().__init__(document)
        self._dark = dark
        self._hide_card_markers = False
        self._rebuild_formats()

    def set_dark(self, dark: bool) -> None:
        if self._dark == dark:
            return
        self._dark = dark
        self._rebuild_formats()
        self.rehighlight()

    def set_hide_card_markers(self, hide: bool) -> None:
        """Dim [[card: …]] lines in the editor (markers stay in the file)."""
        hide = bool(hide)
        if getattr(self, "_hide_card_markers", False) == hide:
            return
        self._hide_card_markers = hide
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
        hide_cards = getattr(self, "_hide_card_markers", False)
        if self._dark:
            self.fmt_scene = self._fmt("#7eb6ff", bold=True)
            self.fmt_character = self._fmt("#f0c674", bold=True)
            self.fmt_parenthetical = self._fmt("#b5bd68", italic=True)
            self.fmt_dialogue = self._fmt("#c5c8c6")
            self.fmt_transition = self._fmt("#de935f", bold=True)
            self.fmt_section = self._fmt("#b294bb", bold=True)
            self.fmt_synopsis = self._fmt("#8abeb7", italic=True)
            self.fmt_note = self._fmt("#969896", italic=True)
            # Near-background when hiding card markers in the editor only.
            self.fmt_card_marker = self._fmt("#2a2a2a" if hide_cards else "#9a86fd", italic=True)
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
            self.fmt_card_marker = self._fmt("#f0f0f0" if hide_cards else "#5c4bb6", italic=True)
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
            if text.lstrip().lower().startswith("[[card:"):
                self.setFormat(0, len(text), self.fmt_card_marker)
            else:
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

        # Autocomplete (character names + scene prefixes + common elements)
        self._completer = QCompleter(self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)

        self._completion_model = QStringListModel(self)
        self._completer.setModel(self._completion_model)

        # Debounced completion list refresh
        self._completion_timer = QTimer(self)
        self._completion_timer.setSingleShot(True)
        self._completion_timer.setInterval(400)
        self._completion_timer.timeout.connect(self.update_completions)
        self.textChanged.connect(self._schedule_completion_update)

        self.update_completions()  # initial population

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
        # Stylesheets can reset viewport margins on Qt/macOS — re-apply gutter inset
        # so the first characters are never drawn under the line-number column.
        self.update_line_number_area_width()
        self.highlight_current_line()

    def line_number_area_width(self) -> int:
        digits = max(3, len(str(max(1, self.blockCount()))))
        # Extra padding so numbers + gap never crowd the first glyph of the line.
        space = 16 + self.fontMetrics().horizontalAdvance("9") * digits + 8
        return space

    def update_line_number_area_width(self, _count: int = 0) -> None:
        width = self.line_number_area_width()
        self.setViewportMargins(width, 0, 0, 0)
        # Keep the gutter widget in sync immediately (not only on resize).
        cr = self.contentsRect()
        self._line_number_area.setGeometry(cr.left(), cr.top(), width, cr.height())

    def update_line_number_area(self, rect, dy) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Re-assert margins after geometry changes (stylesheet/layout races).
        self.update_line_number_area_width()

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

    # ------------------------------------------------------------------
    # Autocomplete support
    # ------------------------------------------------------------------

    def _schedule_completion_update(self) -> None:
        self._completion_timer.start()

    def update_completions(self) -> None:
        """Rebuild the completion list from the current document."""
        text = self.toPlainText()
        suggestions: list[str] = []

        # Static common prefixes (always useful)
        suggestions.extend(
            [
                "INT. ",
                "EXT. ",
                "I/E. ",
                "EST. ",
                ".HEADING ",
                "CUT TO:",
                "FADE TO:",
                "SMASH CUT TO:",
                "MATCH CUT TO:",
                "FADE IN:",
                "FADE OUT.",
                "DISSOLVE TO:",
                "(CONT'D)",
                "(V.O.)",
                "(O.S.)",
                "(O.C.)",
                "(CONTINUOUS)",
            ]
        )

        # Full scene headings + bare locations for reuse
        for _bn, heading in self.list_scene_headings():
            if heading not in suggestions:
                suggestions.append(heading)
            m = re.match(
                r"^(?:INT|EXT|EST|I/?E|INT\./EXT|INT/EXT)[\.\s]+(.+?)(?:\s*-\s*.+)?$",
                heading,
                re.IGNORECASE,
            )
            if m:
                loc = m.group(1).strip(" .")
                if loc and loc not in suggestions:
                    suggestions.append(loc)

        # Character names (skip scene headings / transitions / notes)
        re_char = self._highlighter.re_character
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("[[") or stripped.startswith("#"):
                continue
            if self.is_scene_heading(stripped):
                continue
            if self._highlighter.re_transition.match(
                stripped
            ) or self._highlighter.re_transition_gt.match(stripped):
                continue
            if self._highlighter.re_parenthetical.match(stripped):
                continue
            m = re_char.match(stripped)
            if not m:
                continue
            name = m.group(1).strip()
            if not name or name in suggestions:
                continue
            # Avoid all-caps action lines that look like sentences
            if "  " in name or len(name) > 40:
                continue
            suggestions.append(name)
            cont = f"{name} (CONT'D)"
            if cont not in suggestions:
                suggestions.append(cont)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)

        self._completion_model.setStringList(unique)

    def _completion_prefix(self) -> str:
        """Text from start of current line (or last word) used as completer prefix."""
        cursor = self.textCursor()
        block_text = cursor.block().text()[: cursor.positionInBlock()]
        # Prefer whole line prefix for scene/character lines; fall back to last token.
        stripped_line = block_text.lstrip()
        if not stripped_line:
            return ""
        # If line looks like a partial scene heading / transition / paren, use full line content
        upper = stripped_line.upper()
        if (
            upper.startswith(("INT", "EXT", "EST", "I/E", "I/E.", "CUT", "FADE", "SMASH", "MATCH", "."))
            or stripped_line.startswith("(")
        ):
            return stripped_line
        # Character-ish: last run of word chars / spaces / apostrophes on the line
        m = re.search(r"([A-Za-z0-9 .'()\-]+)$", stripped_line)
        return m.group(1) if m else stripped_line

    def _insert_completion(self, completion: str) -> None:
        """Replace the active prefix with the chosen completion."""
        cursor = self.textCursor()
        prefix = self._completion_prefix()
        if prefix:
            # Move back over the prefix characters actually present before the cursor
            block_text = cursor.block().text()[: cursor.positionInBlock()]
            if block_text.endswith(prefix):
                for _ in range(len(prefix)):
                    cursor.deletePreviousChar()
            else:
                # Fallback: delete only the trailing token length
                token = prefix.split()[-1] if prefix.split() else prefix
                if block_text.upper().endswith(token.upper()):
                    for _ in range(len(token)):
                        cursor.deletePreviousChar()
        cursor.insertText(completion)
        self.setTextCursor(cursor)

    def _show_completions(self, force: bool = False) -> None:
        """Show popup filtered by the current line/token prefix."""
        prefix = self._completion_prefix()
        self._completer.setCompletionPrefix(prefix)
        cr = self.cursorRect()
        cr.setWidth(
            self._completer.popup().sizeHintForColumn(0)
            + self._completer.popup().verticalScrollBar().sizeHint().width()
            + 24
        )
        if force or self._completer.completionCount() > 0:
            self._completer.complete(cr)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # Ctrl/Cmd+Space — force completer (handle before super so no space is inserted)
        ctrl_or_cmd = bool(event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier))
        if ctrl_or_cmd and event.key() == Qt.Key_Space:
            self._show_completions(force=True)
            event.accept()
            return

        if self._completer.popup().isVisible():
            # Let the completer handle navigation / accept / dismiss
            if event.key() in (
                Qt.Key_Enter,
                Qt.Key_Return,
                Qt.Key_Escape,
                Qt.Key_Tab,
                Qt.Key_Backtab,
            ):
                event.ignore()
                return

        super().keyPressEvent(event)

        # Don't auto-popup while modifiers-only / navigation
        if event.text() and not ctrl_or_cmd:
            cursor = self.textCursor()
            block_text = cursor.block().text()[: cursor.positionInBlock()]
            stripped = block_text.strip()
            upper = stripped.upper()
            # Scene prefixes, forced heading, or typing uppercase character-ish line
            if (
                upper.endswith(("INT.", "EXT.", "I/E.", "EST.", "INT", "EXT"))
                or stripped == "."
                or (len(stripped) >= 2 and stripped.isupper() and stripped.replace(" ", "").isalnum())
            ):
                self._show_completions(force=False)

    def is_scene_heading(self, text: str) -> bool:
        """True if a line is a Fountain scene heading (INT/EXT or forced .heading)."""
        stripped = text.strip()
        if not stripped:
            return False
        return bool(
            self._highlighter.re_scene.match(stripped)
            or self._highlighter.re_scene_dot.match(stripped)
        )

    def _card_body_skip_blocks(self) -> set[int]:
        """Block numbers inside card bodies (draft slugs, @vN text) — not real scenes."""
        text = self.toPlainText()
        skip: set[int] = set()
        lines = text.splitlines()
        for info in cards_mod.list_cards_from_text(text, self.is_scene_heading):
            start = info.block_number + 1
            end = cards_mod._body_end(lines, start, self.is_scene_heading)
            for bn in range(start, end):
                skip.add(bn)
        return skip

    def list_scene_headings(self) -> list[tuple[int, str]]:
        """Return (block_number, heading_text) for every scene heading in order.

        Draft sluglines stored inside card version bodies are skipped so the
        scene navigator only shows real screenplay scenes.
        """
        skip = self._card_body_skip_blocks()
        scenes: list[tuple[int, str]] = []
        block = self.document().firstBlock()
        while block.isValid():
            bn = block.blockNumber()
            line = block.text()
            if bn not in skip and self.is_scene_heading(line):
                scenes.append((bn, line.strip()))
            block = block.next()
        return scenes

    def list_outline_nodes(self) -> list[tuple[str, int, int, str]]:
        """N4 outline: Fountain sections + real scenes in document order.

        Each node is ``(kind, block_number, level, title)``:

        - kind: ``"section"`` or ``"scene"``
        - level: section depth 1–6 (number of ``#``); scenes use 0
        - title: section label or scene heading text

        Section lines inside card bodies are ignored (same skip rules as scenes).
        """
        skip = self._card_body_skip_blocks()
        re_section = self._highlighter.re_section
        nodes: list[tuple[str, int, int, str]] = []
        block = self.document().firstBlock()
        while block.isValid():
            bn = block.blockNumber()
            line = block.text()
            stripped = line.strip()
            if bn in skip or not stripped:
                block = block.next()
                continue
            m = re_section.match(line)
            if m:
                hashes, title = m.group(1), (m.group(2) or "").strip()
                level = len(hashes)
                nodes.append(("section", bn, level, title or "(untitled section)"))
            elif self.is_scene_heading(line):
                nodes.append(("scene", bn, 0, stripped))
            block = block.next()
        return nodes

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

    def list_card_infos(self) -> list[cards_mod.CardInfo]:
        """Parse [[card: …]] markers via cards.py (ids, body, parent scene)."""
        return cards_mod.list_cards_from_text(
            self.toPlainText(),
            self.is_scene_heading,
        )

    def list_cards(self) -> list[tuple[int, str, str, str]]:
        """
        Compatibility tuple for the navigator:
        (block_number, card_type, card_text, scene_heading).

        card_text is a short body preview (first line).
        Prefer list_card_infos() for full CardInfo (ids, multi-line body).
        """
        out: list[tuple[int, str, str, str]] = []
        for info in self.list_card_infos():
            preview = info.body.splitlines()[0] if info.body else ""
            out.append((info.block_number, info.card_type, preview, info.scene_heading))
        return out

    def ensure_card_ids(self) -> int:
        """Assign missing id=cNNN on card markers. Returns how many assigned."""
        text = self.toPlainText()
        new_text, assigned = cards_mod.ensure_ids_in_text(text, self.is_scene_heading)
        if assigned and new_text != text:
            self._replace_all_text(new_text)
        return assigned

    def apply_card_to_script(self, card_block: int) -> str:
        """Apply active card version: scene heading + leading action only."""
        text = self.toPlainText()
        new_text, message = cards_mod.apply_card_to_script_text(
            text,
            card_block,
            self.is_scene_heading,
        )
        if new_text != text:
            self._replace_all_text(new_text)
        return message

    def write_card_block(
        self,
        card_block: int,
        card_id: str,
        card_type: str,
        versions,
        active: str,
    ) -> str:
        """Persist card marker + version body into the Fountain file."""
        text = self.toPlainText()
        new_text, message = cards_mod.write_card_block(
            text,
            card_block,
            card_id,
            card_type,
            versions,
            active,
            self.is_scene_heading,
        )
        if new_text != text:
            self._replace_all_text(new_text)
        return message

    def apply_card_with_panel_state(
        self,
        card_block: int,
        card_id: str,
        card_type: str,
        versions,
        active: str,
        *,
        do_snapshot_from: Optional[str] = None,
    ) -> str:
        """Save panel state (optional snapshot) then apply action-only to script."""
        text = self.toPlainText()
        new_text, message, _vers, _act = cards_mod.apply_with_panel_state(
            text,
            card_block,
            card_id,
            card_type,
            versions,
            active,
            self.is_scene_heading,
            do_snapshot_from=do_snapshot_from,
        )
        if new_text != text:
            self._replace_all_text(new_text)
        return message

    def format_new_card_marker(self, card_type: str = "Note") -> str:
        """Marker line with a fresh id (does not mutate the document)."""
        existing = {c.card_id for c in self.list_card_infos() if c.card_id}
        cid = cards_mod.next_card_id(existing)
        return cards_mod.format_card_marker(cid, card_type or "Note")

    def reorder_card_scene(self, card_block: int, direction: int) -> tuple[str, int]:
        """Move the scene owned by this card up (-1) or down (+1).

        Returns (status_message, new_card_block_or_-1).
        """
        text = self.toPlainText()
        new_text, message, new_block = cards_mod.reorder_card_scene(
            text,
            int(card_block),
            int(direction),
            self.is_scene_heading,
        )
        if new_text != text:
            self._replace_all_text(new_text)
        return message, int(new_block) if new_block is not None else -1

    def reorder_card_scene_to_scene_index(
        self, card_block: int, target_scene_index: int
    ) -> tuple[str, int]:
        """Move the scene owned by this card to an absolute scene index."""
        text = self.toPlainText()
        new_text, message, new_block = cards_mod.reorder_card_scene_to_scene_index(
            text,
            int(card_block),
            int(target_scene_index),
            self.is_scene_heading,
        )
        if new_text != text:
            self._replace_all_text(new_text)
        return message, int(new_block) if new_block is not None else -1

    def set_hide_card_markers(self, hide: bool) -> None:
        self._highlighter.set_hide_card_markers(hide)

    def _replace_all_text(self, new_text: str) -> None:
        """Replace document text in one edit block (supports undo)."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def list_beat_infos(self) -> list[cards_mod.BeatInfo]:
        """Parse [[beat: …]] markers (label, note, scene, optional board x/y)."""
        return cards_mod.list_beats_from_text(
            self.toPlainText(),
            self.is_scene_heading,
        )

    def list_beats(self) -> list[tuple[int, str, str, str]]:
        """
        Compatibility tuples for packs / older UI:
        [(block_number, beat_type, beat_text, scene_heading), ...]

        Prefer list_beat_infos() for board coordinates (C4).
        """
        return [
            (b.block_number, b.label, b.beat_text, b.scene_heading)
            for b in self.list_beat_infos()
        ]

    def set_beat_board_position(self, block_number: int, x: float, y: float) -> bool:
        """Persist freeform board coords on the beat marker. Returns True if text changed."""
        text = self.toPlainText()
        new_text, changed = cards_mod.set_beat_position_in_text(
            text, block_number, x, y
        )
        if changed and new_text != text:
            self._replace_all_text(new_text)
        return changed

    def auto_layout_beats(self, cols: int = 3) -> int:
        """Assign grid positions to all beats. Returns how many markers updated."""
        infos = self.list_beat_infos()
        if not infos:
            return 0
        layout = cards_mod.auto_layout_beat_positions(infos, cols=cols)
        text = self.toPlainText()
        n = 0
        for bn, x, y in layout:
            text, changed = cards_mod.set_beat_position_in_text(text, bn, x, y)
            if changed:
                n += 1
        if n:
            self._replace_all_text(text)
        return n

    def format_new_beat_marker(self, label: str = "Beat") -> str:
        """Fresh [[beat: Label]] line (no coords until placed on the board)."""
        return cards_mod.format_beat_marker(label)
