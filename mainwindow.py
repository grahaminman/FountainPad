"""
mainwindow.py — FountainPad shell / orchestration.

Developer notes
---------------
Owns the QMainWindow and wires the rest of the app together:

  navigator | editor | (optional split preview)
                 \\--> optional detached PreviewWindow

State model
  _path            Path of open file, or None for untitled
  _dirty           True when editor text differs from last save/open/new/close
  _dark            UI + preview theme
  _split_visible   Embedded (right-hand) preview pane shown in main window
  _nav_visible     Scene navigator shown on the left
  _detached        PreviewWindow instance while floating preview is open, else None
  _pdf_busy        Guards concurrent PDF exports

Preview UX (important)
  - "Show Split Preview" only controls the *embedded* pane. It always works,
    whether or not a detached window exists.
  - "Detach Preview Window" opens a *second* live preview in its own window.
    Detach does not destroy the embedded preview.
  - "Reattach Preview" closes the floating window. If the embedded pane was
    hidden, reattach turns it back on so the user is never left without a
    preview after reattach.
  - Closing the floating window via the window chrome is the same as Reattach
    (without forcing the split on — we restore split only from the menu action
    if split was off; window-close keeps the user's split preference).

Persistence
  Geometry, splitter sizes, theme, nav/split visibility via QSettings
  (org/app: FountainPad/FountainPad).

File ops
  New / Open / Open Project Folder / Save / Save As / Close / Export PDF / Quit.
  Close prompts to save if dirty, then clears to an empty untitled buffer
  (not the first-run sample).

Help
  Help → FountainPad Help opens resources/help/USER_GUIDE.md in a dialog.
  Keep that guide updated when behaviour changes. Local build-notes/ is
  gitignored process documentation — not shipped via Help.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QMarginsF, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence, QPageLayout, QPageSize
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
)

from editor import FountainEditor
from navigator import SceneNavigator
from cardnavigator import CardNavigator
from beatboard import BeatBoard
from preview import FountainPreview, PreviewWindow

APP_ORG = "FountainPad"
APP_NAME = "FountainPad"

# First-run / New-from-sample text only. File → Close uses an empty buffer.
DEFAULT_FOUNTAIN = """Title: UNTITLED SCREENPLAY
Credit: written by
Author: Your Name
Draft date: 

==

FADE IN:

EXT. DESERT HIGHWAY - DAY

Heat shimmers above the asphalt. A lone scarab crosses the road.

JULES
(squinting)
You ever get the feeling the dunes are watching?

She kicks the sand. Wind answers.

CUT TO:

INT. OASIS CAFE - DAY

Ceiling fans chop the thick air.

END OF SAMPLE
"""

# Fallback widths when a splitter pane was collapsed to 0 and we show it again.
_DEFAULT_NAV_WIDTH = 240
_DEFAULT_CARD_NAV_WIDTH = 240
_DEFAULT_SPLIT_PREVIEW_WIDTH = 520
_DEFAULT_EDITOR_WIDTH = 640


class MainWindow(QMainWindow):
    """Application main window: menus, layout, files, preview modes, PDF."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FountainPad")
        self.resize(1280, 840)

        self._path: Optional[Path] = None
        self._dirty = False
        self._dark = False
        self._split_visible = True
        self._nav_visible = True
        self._cards_visible = True
        self._beats_visible = True
        self._detached: Optional[PreviewWindow] = None
        self._pdf_busy = False
        # Remember non-zero splitter sizes so hide→show does not leave a 0-width pane.
        self._saved_editor_preview_sizes: list[int] = [
            _DEFAULT_EDITOR_WIDTH,
            _DEFAULT_SPLIT_PREVIEW_WIDTH,
        ]
        self._saved_main_splitter_sizes: list[int] = [
            _DEFAULT_NAV_WIDTH,
            _DEFAULT_CARD_NAV_WIDTH,
            1040,
            _DEFAULT_NAV_WIDTH,
        ]

        self.editor = FountainEditor()
        self.preview = FountainPreview()
        self.navigator = SceneNavigator()
        self.card_navigator = CardNavigator()
        self.beat_board = BeatBoard()

        # Inner: editor | embedded preview
        self._editor_preview = QSplitter(Qt.Horizontal)
        self._editor_preview.addWidget(self.editor)
        self._editor_preview.addWidget(self.preview)
        self._editor_preview.setStretchFactor(0, 1)
        self._editor_preview.setStretchFactor(1, 1)
        self._editor_preview.setChildrenCollapsible(False)
        self._editor_preview.setSizes(self._saved_editor_preview_sizes)

        # Outer: navigator | card_navigator | (editor+preview) | beat_board
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.navigator)
        self.splitter.addWidget(self.card_navigator)
        self.splitter.addWidget(self._editor_preview)
        self.splitter.addWidget(self.beat_board)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setStretchFactor(3, 0)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([_DEFAULT_NAV_WIDTH, _DEFAULT_NAV_WIDTH, 1040, _DEFAULT_NAV_WIDTH])
        self._saved_main_splitter_sizes = [_DEFAULT_NAV_WIDTH, _DEFAULT_NAV_WIDTH, 1040, _DEFAULT_NAV_WIDTH]
        self.setCentralWidget(self.splitter)

        self._scene_label = QLabel("Scene: —")
        self._count_label = QLabel("0 chars · 0 words")
        status = QStatusBar()
        status.addWidget(self._scene_label, 1)
        status.addPermanentWidget(self._count_label)
        self.setStatusBar(status)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._update_preview_action_states()

        self.editor.contentChanged.connect(self._on_editor_changed)
        self.editor.cursorPositionChanged.connect(self._update_status)
        self.navigator.sceneActivated.connect(self._on_scene_activated)
        self.card_navigator.cardActivated.connect(self._on_card_activated)
        self.card_navigator.cardTemplateRequested.connect(self._insert_card_template)
        self.card_navigator.generateFromScenesRequested.connect(
            self.generate_empty_cards_from_scenes
        )
        self.beat_board.beatActivated.connect(self._on_beat_activated)

        # Debounce navigator rebuild while typing (cheap, but no need every keystroke).
        self._nav_refresh = QTimer(self)
        self._nav_refresh.setSingleShot(True)
        self._nav_refresh.setInterval(250)
        self._nav_refresh.timeout.connect(self._refresh_navigator)
        self._cards_refresh = QTimer(self)
        self._cards_refresh.setSingleShot(True)
        self._cards_refresh.setInterval(250)
        self._cards_refresh.timeout.connect(self._refresh_card_navigator)

        self._beats_refresh = QTimer(self)
        self._beats_refresh.setSingleShot(True)
        self._beats_refresh.setInterval(250)
        self._beats_refresh.timeout.connect(self._refresh_beat_board)

        self._load_settings()
        self.new_file(initial=True)
        self._update_title()
        self._update_status()
        self._apply_theme()
        self._refresh_navigator()
        self._refresh_card_navigator()
        self._refresh_beat_board()
        self._update_preview_action_states()

    # --- UI construction -------------------------------------------------
    def _build_actions(self) -> None:
        self.act_new = QAction("&New", self)
        self.act_new.setShortcut(QKeySequence.New)
        self.act_new.setStatusTip("Create a new empty screenplay (prompts if unsaved)")
        self.act_new.triggered.connect(lambda: self.new_file(initial=False))

        self.act_open = QAction("&Open…", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.setStatusTip("Open a .fountain file")
        self.act_open.triggered.connect(self.open_file)

        self.act_close = QAction("&Close", self)
        self.act_close.setShortcut(QKeySequence.Close)
        self.act_close.setStatusTip("Close the current file (prompts if unsaved)")
        self.act_close.triggered.connect(self.close_file)

        self.act_save = QAction("&Save", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.setStatusTip("Save the current file")
        self.act_save.triggered.connect(self.save_file)

        self.act_save_as = QAction("Save &As…", self)
        self.act_save_as.setShortcut(QKeySequence.SaveAs)
        self.act_save_as.setStatusTip("Save the current file under a new name")
        self.act_save_as.triggered.connect(self.save_file_as)

        self.act_export_pdf = QAction("Export &PDF…", self)
        self.act_export_pdf.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.act_export_pdf.setStatusTip("Export the formatted preview as a PDF")
        self.act_export_pdf.triggered.connect(self.export_pdf)

        self.act_quit = QAction("&Quit", self)
        self.act_quit.setShortcut(QKeySequence.Quit)
        self.act_quit.setStatusTip("Quit FountainPad")
        self.act_quit.triggered.connect(self.close)

        self.act_open_project = QAction("Open &Project Folder…", self)
        self.act_open_project.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.act_open_project.setStatusTip("Open a project folder (Screenwriting OS structure)")
        self.act_open_project.triggered.connect(self.open_project)

        self.act_toggle_nav = QAction("Show &Scene Navigator", self)
        self.act_toggle_nav.setCheckable(True)
        self.act_toggle_nav.setChecked(True)
        self.act_toggle_nav.setShortcut(QKeySequence("Ctrl+\\"))
        self.act_toggle_nav.setStatusTip("Show or hide the scene list")
        self.act_toggle_nav.triggered.connect(self.toggle_navigator)

        self.act_toggle_cards = QAction("Show &Index Cards", self)
        self.act_toggle_cards.setCheckable(True)
        self.act_toggle_cards.setChecked(True)
        self.act_toggle_cards.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.act_toggle_cards.setStatusTip("Show or hide the index cards")
        self.act_toggle_cards.triggered.connect(self.toggle_card_navigator)

        self.act_toggle_beats = QAction("Show &Beat Board", self)
        self.act_toggle_beats.setCheckable(True)
        self.act_toggle_beats.setChecked(True)
        self.act_toggle_beats.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.act_toggle_beats.setStatusTip("Show or hide the beat board")
        self.act_toggle_beats.triggered.connect(self.toggle_beat_board)

        # Embedded preview only — independent of detached window.
        self.act_toggle_preview = QAction("Show Split Pre&view", self)
        self.act_toggle_preview.setCheckable(True)
        self.act_toggle_preview.setChecked(True)
        self.act_toggle_preview.setShortcut(QKeySequence("Ctrl+P"))
        self.act_toggle_preview.setStatusTip(
            "Show or hide the preview pane inside the main window"
        )
        self.act_toggle_preview.triggered.connect(self.toggle_split_preview)

        self.act_detach = QAction("&Detach Preview Window", self)
        self.act_detach.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_detach.setStatusTip(
            "Open a floating preview window (split preview stays available)"
        )
        self.act_detach.triggered.connect(self.detach_preview)

        self.act_reattach = QAction("&Reattach Preview", self)
        self.act_reattach.setShortcut(QKeySequence("Ctrl+Alt+P"))
        self.act_reattach.setStatusTip(
            "Close the floating preview and show the split preview in the main window"
        )
        self.act_reattach.triggered.connect(self.reattach_preview)
        self.act_reattach.setEnabled(False)

        self.act_dark = QAction("&Dark Mode", self)
        self.act_dark.setCheckable(True)
        self.act_dark.setShortcut(QKeySequence("Ctrl+D"))
        self.act_dark.setStatusTip("Toggle dark theme")
        self.act_dark.triggered.connect(self.toggle_dark_mode)

        # Edit menu — standard editor commands (source pane, not preview).
        self.act_undo = QAction("&Undo", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setStatusTip("Undo the last edit in the script")
        self.act_undo.triggered.connect(self.editor.undo)

        self.act_redo = QAction("&Redo", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.setStatusTip("Redo the last undone edit")
        self.act_redo.triggered.connect(self.editor.redo)

        self.act_cut = QAction("Cu&t", self)
        self.act_cut.setShortcut(QKeySequence.Cut)
        self.act_cut.setStatusTip("Cut the selection to the clipboard")
        self.act_cut.triggered.connect(self.editor.cut)

        self.act_copy = QAction("&Copy", self)
        self.act_copy.setShortcut(QKeySequence.Copy)
        self.act_copy.setStatusTip("Copy the selection to the clipboard")
        self.act_copy.triggered.connect(self.editor.copy)

        self.act_paste = QAction("&Paste", self)
        self.act_paste.setShortcut(QKeySequence.Paste)
        self.act_paste.setStatusTip("Paste from the clipboard into the script")
        self.act_paste.triggered.connect(self.editor.paste)

        self.act_select_all = QAction("Select &All", self)
        self.act_select_all.setShortcut(QKeySequence.SelectAll)
        self.act_select_all.setStatusTip("Select all script text")
        self.act_select_all.triggered.connect(self.editor.selectAll)

        self.act_cards_from_scenes = QAction("Generate Empty &Cards from Scenes…", self)
        self.act_cards_from_scenes.setStatusTip(
            "Insert optional empty card notes under scenes that have none"
        )
        self.act_cards_from_scenes.triggered.connect(self.generate_empty_cards_from_scenes)

        self.act_help = QAction("FountainPad &Help", self)
        self.act_help.setShortcut(QKeySequence.HelpContents)
        self.act_help.setStatusTip("Open the user guide (how menus and panels work)")
        self.act_help.triggered.connect(self.show_help)

        self.act_about = QAction("&About FountainPad", self)
        self.act_about.setStatusTip("Version and credits")
        self.act_about.triggered.connect(self.show_about)

    def _build_menus(self) -> None:
        """Traditional desktop order: File · Edit · View · Help.

        Keep QMenu instances on self so Qt/macOS does not garbage-collect them.
        """
        self.menu_file = self.menuBar().addMenu("&File")
        self.menu_file.addAction(self.act_new)
        self.menu_file.addAction(self.act_open)
        self.menu_file.addAction(self.act_open_project)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_close)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_save)
        self.menu_file.addAction(self.act_save_as)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_export_pdf)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_quit)

        self.menu_edit = self.menuBar().addMenu("&Edit")
        self.menu_edit.addAction(self.act_undo)
        self.menu_edit.addAction(self.act_redo)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.act_cut)
        self.menu_edit.addAction(self.act_copy)
        self.menu_edit.addAction(self.act_paste)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.act_select_all)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.act_cards_from_scenes)

        self.menu_view = self.menuBar().addMenu("&View")
        self.menu_view.addAction(self.act_toggle_nav)
        self.menu_view.addAction(self.act_toggle_cards)
        self.menu_view.addAction(self.act_toggle_beats)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.act_toggle_preview)
        self.menu_view.addAction(self.act_detach)
        self.menu_view.addAction(self.act_reattach)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.act_dark)

        # Help last — platform convention.
        self.menu_help = self.menuBar().addMenu("&Help")
        self.menu_help.addAction(self.act_help)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self.act_new)
        tb.addAction(self.act_open)
        tb.addAction(self.act_close)
        tb.addAction(self.act_save)
        tb.addAction(self.act_export_pdf)
        tb.addSeparator()
        tb.addAction(self.act_toggle_nav)
        tb.addAction(self.act_toggle_cards)
        tb.addAction(self.act_toggle_beats)
        tb.addAction(self.act_toggle_preview)
        tb.addAction(self.act_detach)
        tb.addAction(self.act_reattach)
        tb.addSeparator()
        tb.addAction(self.act_dark)
        tb.addSeparator()
        tb.addAction(self.act_help)

    def _update_preview_action_states(self) -> None:
        """Enable/disable detach vs reattach based on floating window presence."""
        detached = self._detached is not None and self._detached.isVisible()
        self.act_reattach.setEnabled(detached)
        # Detach stays enabled so a second click can raise an existing window.
        self.act_detach.setEnabled(True)
        if detached:
            self.act_detach.setText("Focus Detached Preview")
            self.act_detach.setStatusTip("Bring the floating preview window to the front")
        else:
            self.act_detach.setText("Detach Preview Window")
            self.act_detach.setStatusTip(
                "Open a floating preview window (split preview stays available)"
            )

    # --- File ops --------------------------------------------------------
    def new_file(self, initial: bool = False) -> None:
        """Create a new buffer. initial=True loads the sample without dirty flag."""
        if not initial and not self._maybe_save():
            return
        self.editor.blockSignals(True)
        # First launch shows sample so preview/highlighter are obvious; later New is blank.
        self.editor.setPlainText(DEFAULT_FOUNTAIN if initial else "")
        self.editor.blockSignals(False)
        self._path = None
        self._dirty = False
        self._sync_previews(immediate=True)
        self._refresh_navigator()
        self._update_title()
        self._update_status()

    def close_file(self) -> None:
        """
        Close the current document (File → Close).

        Prompts to save if dirty, then clears path + editor to an empty untitled
        buffer. Does not quit the app (use Quit for that).
        """
        if not self._maybe_save():
            return
        self.editor.blockSignals(True)
        self.editor.setPlainText("")
        self.editor.blockSignals(False)
        self._path = None
        self._dirty = False
        self._sync_previews(immediate=True)
        self._refresh_navigator()
        self._update_title()
        self._update_status()
        self.statusBar().showMessage("Closed", 2000)

    def open_project(self) -> None:
        """Open a project folder and auto-load script.fountain if it exists.
        
        Auto-creates missing Screenwriting OS files:
          - canon.md
          - beats.md
          - cards.md
        """
        if not self._maybe_save():
            return
        path = QFileDialog.getExistingDirectory(
            self,
            "Open Project Folder",
            str(self._path.parent if self._path else Path.home()),
        )
        if not path:
            return
        project_dir = Path(path)
        
        # Auto-create missing Screenwriting OS files.
        missing_files = []
        for name, template in [
            ("canon.md", "# Canon\n\nStory world, rules, lore."),
            ("beats.md", "# Beats\n\nMajor plot points."),
            ("cards.md", "# Index Cards\n\n[[card: Goal]]\n[[card: Conflict]]\n[[card: Turn]]"),
        ]:
            file = project_dir / name
            if not file.exists():
                try:
                    file.write_text(template, encoding="utf-8")
                    missing_files.append(name)
                except OSError as exc:
                    QMessageBox.warning(
                        self,
                        "File creation failed",
                        f"Could not create {name}:\n{exc}",
                    )
        
        fountain_file = project_dir / "script.fountain"
        if fountain_file.exists():
            self._open_fountain_file(fountain_file)
        else:
            msg = f"Project folder opened: {project_dir.name}"
            if missing_files:
                msg += f"\nAuto-created: {', '.join(missing_files)}"
            QMessageBox.information(self, "Project Opened", msg)

    def _open_fountain_file(self, path: Path) -> None:
        """Open a .fountain file and update UI."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self._path = path
        self._dirty = False
        self._sync_previews(immediate=True)
        self._refresh_navigator()
        self._refresh_card_navigator()
        self._refresh_beat_board()
        self._update_title()
        self._update_status()

    def open_file(self) -> None:
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Fountain Screenplay",
            str(self._path.parent if self._path else Path.home()),
            "Fountain (*.fountain);;Text (*.txt);;All files (*.*)",
        )
        if not path:
            return
        self._open_fountain_file(Path(path))

    def save_file(self) -> bool:
        if self._path is None:
            return self.save_file_as()
        return self._write_to(self._path)

    def save_file_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Fountain Screenplay",
            str(self._path or Path.home() / "untitled.fountain"),
            "Fountain (*.fountain);;All files (*.*)",
        )
        if not path:
            return False
        p = Path(path)
        if p.suffix == "":
            p = p.with_suffix(".fountain")
        return self._write_to(p)

    def _write_to(self, path: Path) -> bool:
        try:
            path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        self._path = path
        self._dirty = False
        self._update_title()
        self.statusBar().showMessage(f"Saved {path.name}", 3000)
        return True

    def _maybe_save(self) -> bool:
        """Return False if the user cancelled a dirty-buffer prompt."""
        if not self._dirty:
            return True
        name = self._path.name if self._path else "Untitled"
        # Build explicitly so we can force readable light-mode colours on macOS.
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"Save changes to “{name}”?")
        box.setInformativeText("Your changes will be lost if you don't save them.")
        box.setStandardButtons(
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )
        box.setDefaultButton(QMessageBox.Save)
        self._style_message_box(box)
        res = box.exec()
        if res == QMessageBox.Cancel:
            return False
        if res == QMessageBox.Save:
            return self.save_file()
        return True

    def _style_message_box(self, box: QMessageBox) -> None:
        """Ensure dialog body + buttons stay readable in the active theme."""
        from PySide6.QtGui import QColor, QPalette

        pal = box.palette()
        if self._dark:
            bg, fg = QColor("#2d2d30"), QColor("#dddddd")
            btn_bg, btn_fg = QColor("#3e3e42"), QColor("#ffffff")
        else:
            bg, fg = QColor("#f5f5f5"), QColor("#000000")
            btn_bg, btn_fg = QColor("#ffffff"), QColor("#000000")
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            pal.setColor(group, QPalette.Window, bg)
            pal.setColor(group, QPalette.WindowText, fg)
            pal.setColor(group, QPalette.Text, fg)
            pal.setColor(group, QPalette.Button, btn_bg)
            pal.setColor(group, QPalette.ButtonText, btn_fg)
            pal.setColor(group, QPalette.Base, bg)
        box.setPalette(pal)
        # Also paint child labels (message text lives in QLabel children).
        for label in box.findChildren(QLabel):
            label.setPalette(pal)
            label.setStyleSheet(
                f"color: {'#dddddd' if self._dark else '#000000'}; background: transparent;"
            )

    # --- PDF export ------------------------------------------------------
    def export_pdf(self) -> None:
        """
        Export formatted preview to PDF via Qt WebEngine printToPdf.

        Always prints with the light theme so dark UI colours do not end up
        on paper. Prefers the embedded preview; falls back to the detached
        preview if the split pane is hidden and a floating window exists.
        """
        if self._pdf_busy:
            self.statusBar().showMessage("PDF export already in progress…", 2000)
            return

        default_name = "untitled.pdf"
        if self._path is not None:
            default_name = self._path.with_suffix(".pdf").name
        start = str(
            (self._path.parent / default_name)
            if self._path is not None
            else Path.home() / default_name
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            start,
            "PDF (*.pdf);;All files (*.*)",
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != ".pdf":
            out = out.with_suffix(".pdf")

        text = self.editor.toPlainText()
        target = self._pdf_target_preview()
        if target is None:
            QMessageBox.warning(
                self,
                "PDF export",
                "No preview is available.\n"
                "Turn on View → Show Split Preview, or detach a preview window.",
            )
            return

        self._pdf_busy = True
        self.act_export_pdf.setEnabled(False)
        self.statusBar().showMessage(f"Exporting PDF… {out.name}")

        def _on_done(ok: bool, pdf_path: str) -> None:
            self._pdf_busy = False
            self.act_export_pdf.setEnabled(True)
            theme = "dark" if self._dark else "light"
            target.set_theme(theme)
            target.set_fountain_text(text, immediate=True)
            if ok:
                self.statusBar().showMessage(f"Exported PDF: {Path(pdf_path).name}", 5000)
            else:
                QMessageBox.critical(
                    self,
                    "PDF export failed",
                    f"Could not write PDF:\n{pdf_path}",
                )
                self.statusBar().showMessage("PDF export failed", 4000)

        target.set_theme("light")
        target.set_fountain_text(text, immediate=True)

        # QPageLayout requires margins in this PySide build — bare
        # (pageSize, orientation) raises TypeError and kills export.
        layout = QPageLayout(
            QPageSize(QPageSize.Letter),
            QPageLayout.Portrait,
            QMarginsF(0.5, 0.5, 0.5, 0.5),
            QPageLayout.Inch,
        )

        def _run_print() -> None:
            try:
                target.print_to_pdf(str(out), _on_done, layout)
            except Exception as exc:  # noqa: BLE001 — surface to user
                self._pdf_busy = False
                self.act_export_pdf.setEnabled(True)
                theme = "dark" if self._dark else "light"
                target.set_theme(theme)
                target.set_fountain_text(text, immediate=True)
                QMessageBox.critical(
                    self,
                    "PDF export failed",
                    f"Could not start PDF export:\n{exc}",
                )
                self.statusBar().showMessage("PDF export failed", 4000)

        # Brief delay so WebEngine can paint after theme/content apply.
        QTimer.singleShot(500, _run_print)

    def _pdf_target_preview(self) -> Optional[FountainPreview]:
        """Pick a live preview widget for PDF rendering."""
        if self._split_visible:
            return self.preview
        if self._detached is not None and self._detached.isVisible():
            return self._detached.preview
        # Embedded widget still exists even if hidden — usable for print.
        return self.preview

    # --- Preview / theme / navigator -------------------------------------
    def _on_editor_changed(self) -> None:
        self._dirty = True
        self._update_title()
        self._sync_previews(immediate=False)
        self._update_status()
        self._nav_refresh.start()
        self._cards_refresh.start()
        self._beats_refresh.start()

    def _sync_previews(self, immediate: bool = False) -> None:
        """
        Push editor text to every live preview surface.

        Embedded preview is updated whenever the split is visible *or* we need
        it warm for PDF. Detached preview is updated only while it exists.
        """
        text = self.editor.toPlainText()
        # Keep embedded preview in sync even when hidden so show/PDF are instant.
        self.preview.set_fountain_text(text, immediate=immediate)
        if self._detached is not None:
            self._detached.preview.set_fountain_text(text, immediate=immediate)

    def _refresh_navigator(self) -> None:
        scenes = self.editor.list_scene_headings()
        self.navigator.set_scenes(scenes)
        block_no = self.editor.textCursor().blockNumber()
        self.navigator.highlight_block(block_no)

    def _refresh_card_navigator(self) -> None:
        cards = self.editor.list_cards()
        self.card_navigator.set_cards(cards)
        block_no = self.editor.textCursor().blockNumber()
        # Highlight the card nearest to the cursor
        if cards:
            target_block = -1
            for block_number, _, _, _ in cards:
                if block_number <= block_no:
                    target_block = block_number
                else:
                    break
            if target_block >= 0:
                for row in range(self.card_navigator._list.count()):
                    item = self.card_navigator._list.item(row)
                    if item and int(item.data(Qt.UserRole)) == target_block:
                        self.card_navigator._updating = True
                        self.card_navigator._list.setCurrentRow(row)
                        self.card_navigator._updating = False

    def _on_scene_activated(self, block_number: int) -> None:
        self.editor.goto_block(block_number)
        self._update_status()

    def _on_card_activated(self, block_number: int) -> None:
        self.editor.goto_block(block_number)
        self._update_status()

    def toggle_navigator(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = self.act_toggle_nav.isChecked()
        else:
            self.act_toggle_nav.setChecked(checked)
        self._nav_visible = bool(checked)
        if self._nav_visible:
            self.navigator.setVisible(True)
            self._ensure_main_splitter_sizes()
            self._refresh_navigator()
        else:
            self._remember_main_splitter_sizes()
            self.navigator.setVisible(False)

    def toggle_card_navigator(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = self.act_toggle_cards.isChecked()
        else:
            self.act_toggle_cards.setChecked(checked)
        self._cards_visible = bool(checked)
        if self._cards_visible:
            self.card_navigator.setVisible(True)
            self._ensure_main_splitter_sizes()
            self._refresh_card_navigator()
        else:
            self._remember_main_splitter_sizes()
            self.card_navigator.setVisible(False)

    def toggle_beat_board(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = self.act_toggle_beats.isChecked()
        else:
            self.act_toggle_beats.setChecked(checked)
        self._beats_visible = bool(checked)
        if self._beats_visible:
            self.beat_board.setVisible(True)
            self._ensure_main_splitter_sizes()
            self._refresh_beat_board()
        else:
            self._remember_main_splitter_sizes()
            self.beat_board.setVisible(False)

    def _refresh_beat_board(self) -> None:
        beats = self.editor.list_beats()
        self.beat_board.set_beats(beats)
        block_no = self.editor.textCursor().blockNumber()
        if beats:
            target_block = -1
            for block_number, _, _, _ in beats:
                if block_number <= block_no:
                    target_block = block_number
                else:
                    break
            if target_block >= 0:
                for row in range(self.beat_board._list.count()):
                    item = self.beat_board._list.item(row)
                    if item and int(item.data(Qt.UserRole)) == target_block:
                        self.beat_board._updating = True
                        self.beat_board._list.setCurrentRow(row)
                        self.beat_board._updating = False

    def _on_beat_activated(self, block_number: int) -> None:
        self.editor.goto_block(block_number)
        self._update_status()

    def _insert_card_template(self, card_type: str) -> None:
        """Insert a [[card: Type]] stub at the cursor and refresh the card list."""
        label = (card_type or "Card").strip() or "Card"
        stub = f"[[card: {label}]]\n"
        cursor = self.editor.textCursor()
        if cursor.positionInBlock() > 0 and not cursor.atBlockStart():
            cursor.movePosition(cursor.MoveOperation.EndOfBlock)
            cursor.insertText("\n")
        cursor.insertText(stub)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus(Qt.OtherFocusReason)
        self._dirty = True
        self._update_title()
        self._refresh_card_navigator()
        self.statusBar().showMessage(f"Inserted card template: {label}", 2000)

    def generate_empty_cards_from_scenes(self) -> None:
        """P3: insert empty [[card: Note]] stubs under scenes that have no cards.

        Notes to the draft — optional scaffolding, not instructions. Scenes that
        already have at least one linked card are skipped.
        """
        scenes = self.editor.list_scene_headings()
        if not scenes:
            QMessageBox.information(
                self,
                "Generate empty cards",
                "No scene headings found in this script.\n\n"
                "Add INT./EXT. (or equivalent) scene headings first.",
            )
            return

        cards = self.editor.list_cards()
        scenes_with_cards = {scene for _bn, _t, _txt, scene in cards}
        missing = [(bn, heading) for bn, heading in scenes if heading not in scenes_with_cards]

        if not missing:
            QMessageBox.information(
                self,
                "Generate empty cards",
                "Every scene already has at least one card note.\n\n"
                "Nothing to insert.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Generate empty cards",
            f"Insert an empty card note under {len(missing)} scene(s) that have none?\n\n"
            "These are optional planning notes (not instructions). "
            "Scenes that already have a card are skipped.\n\n"
            "Each stub looks like:\n[[card: Note]]",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Bottom-up so earlier block numbers stay valid while inserting.
        inserted = 0
        for block_number, _heading in reversed(missing):
            block = self.editor.document().findBlockByNumber(block_number)
            if not block.isValid():
                continue
            cursor = self.editor.textCursor()
            cursor.setPosition(block.position())
            cursor.movePosition(cursor.MoveOperation.EndOfBlock)
            # Leave a blank line under the slugline, then the note stub.
            cursor.insertText("\n\n[[card: Note]]\n")
            inserted += 1

        if inserted:
            self._dirty = True
            self._update_title()
            self._refresh_card_navigator()
            self._refresh_navigator()
            self._sync_previews(immediate=True)
            self._update_status()
            # Show cards panel so the user sees what was added.
            if not self._cards_visible:
                self.toggle_card_navigator(True)
            self.editor.setFocus(Qt.OtherFocusReason)
            self.statusBar().showMessage(
                f"Inserted {inserted} empty card note(s) from scenes",
                4000,
            )
        else:
            self.statusBar().showMessage("No card notes inserted", 3000)

    def toggle_split_preview(self, checked: Optional[bool] = None) -> None:
        """
        Show or hide the *embedded* preview pane.

        Independent of the detached window. Restores a non-zero splitter width
        if the pane had collapsed to 0 when last hidden.
        """
        if checked is None:
            checked = self.act_toggle_preview.isChecked()
        else:
            self.act_toggle_preview.setChecked(checked)
        self._split_visible = bool(checked)

        if self._split_visible:
            self.preview.setVisible(True)
            self._ensure_editor_preview_sizes()
            self.editor.set_word_wrap(True)
            self._sync_previews(immediate=True)
        else:
            self._remember_editor_preview_sizes()
            self.preview.setVisible(False)
            # Full-width editor is nicer without the split.
            self.editor.set_word_wrap(False)

        self.statusBar().showMessage(
            "Split preview on" if self._split_visible else "Split preview off",
            2000,
        )

    def detach_preview(self) -> None:
        """
        Open (or focus) a floating preview window.

        Does *not* hide the split preview. User can run both, or hide split
        via Show Split Preview while keeping the floating window.
        """
        if self._detached is not None:
            if self._detached.isVisible():
                self._detached.raise_()
                self._detached.activateWindow()
                self._update_preview_action_states()
                return
            # Stale reference — clean up and create fresh.
            self._detached = None

        win = PreviewWindow()
        win.preview.set_theme("dark" if self._dark else "light")
        win.preview.set_fountain_text(self.editor.toPlainText(), immediate=True)
        win.closed.connect(self._on_detached_closed)
        self._detached = win
        win.show()
        win.raise_()
        win.activateWindow()
        self._update_preview_action_states()
        self.statusBar().showMessage(
            "Detached preview open — use Reattach Preview or close that window",
            4000,
        )

    def reattach_preview(self) -> None:
        """
        Close the floating preview and ensure the embedded split preview is on.

        This is the explicit path back from “I only see the detached window”.
        """
        if self._detached is not None:
            # Block the closed handler from racing; we manage state here.
            try:
                self._detached.closed.disconnect(self._on_detached_closed)
            except (TypeError, RuntimeError):
                pass
            self._detached.close()
            self._detached = None

        # Always restore embedded preview on explicit reattach.
        if not self._split_visible:
            self.toggle_split_preview(True)
        else:
            self._ensure_editor_preview_sizes()
            self._sync_previews(immediate=True)

        self._update_preview_action_states()
        self.statusBar().showMessage("Preview reattached to main window", 3000)

    def _on_detached_closed(self) -> None:
        """Floating window closed via chrome — keep user's split preference."""
        self._detached = None
        self._update_preview_action_states()
        # If split was already on, nothing to do. If off, user chose that —
        # do not force it back on (use Reattach for that).
        self.statusBar().showMessage(
            "Detached preview closed"
            + ("" if self._split_visible else " — enable Show Split Preview to show it in-window"),
            4000,
        )

    def _remember_editor_preview_sizes(self) -> None:
        sizes = self._editor_preview.sizes()
        if len(sizes) >= 2 and sizes[1] > 50:
            self._saved_editor_preview_sizes = list(sizes)

    def _ensure_editor_preview_sizes(self) -> None:
        """After showing the preview pane, avoid a 0-width ghost column."""
        sizes = self._editor_preview.sizes()
        if len(sizes) < 2 or sizes[1] < 80:
            saved = self._saved_editor_preview_sizes
            if len(saved) >= 2 and saved[1] >= 80:
                self._editor_preview.setSizes(saved)
            else:
                self._editor_preview.setSizes(
                    [_DEFAULT_EDITOR_WIDTH, _DEFAULT_SPLIT_PREVIEW_WIDTH]
                )

    def _remember_main_splitter_sizes(self) -> None:
        sizes = self.splitter.sizes()
        if len(sizes) >= 3 and sizes[0] > 40 and sizes[1] > 40:
            self._saved_main_splitter_sizes = list(sizes)

    def _ensure_main_splitter_sizes(self) -> None:
        """Restore sensible widths for visible side panes (nav/cards/beats)."""
        default = [
            _DEFAULT_NAV_WIDTH,
            _DEFAULT_CARD_NAV_WIDTH,
            1040,
            _DEFAULT_NAV_WIDTH,
        ]
        sizes = list(self.splitter.sizes())
        if len(sizes) < 4:
            sizes = (
                list(self._saved_main_splitter_sizes)
                if len(self._saved_main_splitter_sizes) >= 4
                else default
            )
        # Index: 0 nav, 1 cards, 2 editor+preview, 3 beats
        if self._nav_visible and sizes[0] < 40:
            sizes[0] = default[0]
        if self._cards_visible and sizes[1] < 40:
            sizes[1] = default[1]
        if sizes[2] < 120:
            sizes[2] = default[2]
        if self._beats_visible and sizes[3] < 40:
            sizes[3] = default[3]
        self.splitter.setSizes(sizes)
        self._saved_main_splitter_sizes = sizes

    def toggle_dark_mode(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            self._dark = not self._dark
            self.act_dark.setChecked(self._dark)
        else:
            self._dark = bool(checked)
        self._apply_theme()

    def _apply_theme(self) -> None:
        """
        Apply editor/preview themes and chrome stylesheets.

        Light mode must set explicit dark text on menu bar, toolbar buttons,
        and status labels. Without QToolButton/QMenuBar::item colours, macOS
        (and some Qt styles) keep light/white glyphs on the light banner so
        labels only read where they sit on a dark patch.
        """
        theme = "dark" if self._dark else "light"
        self.editor.apply_theme(self._dark)
        self.navigator.apply_theme(self._dark)
        self.card_navigator.apply_theme(self._dark)
        self.beat_board.apply_theme(self._dark)
        self.preview.set_theme(theme)
        if self._detached is not None:
            self._detached.preview.set_theme(theme)

        app = QApplication.instance()
        if app is None:
            return
        if self._dark:
            app.setStyleSheet(
                """
                QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar, QSplitter {
                    background-color: #2d2d30;
                    color: #dddddd;
                }
                QMenuBar::item {
                    color: #dddddd;
                    background: transparent;
                    padding: 4px 10px;
                }
                QMenuBar::item:selected, QMenu::item:selected {
                    background: #3e3e42;
                    color: #ffffff;
                }
                QMenu {
                    background-color: #2d2d30;
                    color: #dddddd;
                }
                QMenu::item {
                    color: #dddddd;
                    padding: 4px 24px 4px 12px;
                }
                QToolBar {
                    background-color: #2d2d30;
                    border: none;
                    spacing: 4px;
                }
                QToolBar QToolButton {
                    color: #dddddd;
                    background: transparent;
                    padding: 4px 8px;
                }
                QToolBar QToolButton:hover {
                    background: #3e3e42;
                    color: #ffffff;
                }
                QStatusBar {
                    background-color: #2d2d30;
                    color: #bbbbbb;
                }
                QStatusBar QLabel {
                    color: #bbbbbb;
                    background: transparent;
                }
                QMessageBox {
                    background: #2d2d30;
                    color: #dddddd;
                }
                QMessageBox QLabel { color: #dddddd; }
                """
            )
        else:
            # Light chrome: black/near-black text on light grey banners.
            app.setStyleSheet(
                """
                QMainWindow, QSplitter {
                    background-color: #f3f3f3;
                    color: #1a1a1a;
                }
                QMenuBar {
                    background-color: #f3f3f3;
                    color: #1a1a1a;
                }
                QMenuBar::item {
                    color: #1a1a1a;
                    background: transparent;
                    padding: 4px 10px;
                }
                QMenuBar::item:selected {
                    background: #dcdcdc;
                    color: #000000;
                }
                QMenu {
                    background-color: #ffffff;
                    color: #1a1a1a;
                }
                QMenu::item {
                    color: #1a1a1a;
                    padding: 4px 24px 4px 12px;
                }
                QMenu::item:selected {
                    background: #cde8ff;
                    color: #000000;
                }
                QToolBar {
                    background-color: #f3f3f3;
                    border: none;
                    border-bottom: 1px solid #d0d0d0;
                    spacing: 4px;
                    color: #1a1a1a;
                }
                QToolBar QToolButton {
                    color: #1a1a1a;
                    background: transparent;
                    padding: 4px 8px;
                }
                QToolBar QToolButton:hover {
                    background: #e4e4e4;
                    color: #000000;
                }
                QToolBar QToolButton:pressed {
                    background: #d0d0d0;
                    color: #000000;
                }
                QStatusBar {
                    background-color: #f3f3f3;
                    color: #333333;
                    border-top: 1px solid #d0d0d0;
                }
                QStatusBar QLabel {
                    color: #333333;
                    background: transparent;
                }
                /* Save / discard / error dialogs — force black text on light chrome.
                   QMessageBox text often inherits a light WindowText on macOS. */
                QMessageBox {
                    background-color: #f5f5f5;
                    color: #000000;
                }
                QMessageBox QLabel {
                    color: #000000;
                    background: transparent;
                }
                QMessageBox QPushButton {
                    color: #000000;
                    background-color: #ffffff;
                    border: 1px solid #b0b0b0;
                    border-radius: 4px;
                    padding: 4px 14px;
                    min-width: 64px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #e8e8e8;
                    color: #000000;
                }
                QMessageBox QPushButton:default {
                    background-color: #dceeff;
                    border: 1px solid #6aa9e8;
                    color: #000000;
                }
                QDialog {
                    background-color: #f5f5f5;
                    color: #000000;
                }
                QDialog QLabel {
                    color: #000000;
                }
                """
            )

    def _update_title(self) -> None:
        name = self._path.name if self._path else "Untitled.fountain"
        dirty = " •" if self._dirty else ""
        self.setWindowTitle(f"{name}{dirty} — FountainPad")

    def _update_status(self) -> None:
        text = self.editor.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        scene = self.editor.current_scene_heading() or "—"
        if len(scene) > 60:
            scene = scene[:57] + "…"
        self._scene_label.setText(f"Scene: {scene}")
        self._count_label.setText(f"{chars} chars · {words} words")
        self.navigator.highlight_block(self.editor.textCursor().blockNumber())

    def _help_guide_path(self) -> Path:
        """Resolve shipped user guide (dev tree or frozen bundle)."""
        candidates = [
            Path(__file__).resolve().parent / "resources" / "help" / "USER_GUIDE.md",
        ]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.insert(0, Path(meipass) / "resources" / "help" / "USER_GUIDE.md")
        for p in candidates:
            if p.is_file():
                return p
        return candidates[-1]

    def show_help(self) -> None:
        """Open the in-app user guide (Help menu / F1)."""
        path = self._help_guide_path()
        dlg = QDialog(self)
        dlg.setWindowTitle("FountainPad Help")
        dlg.resize(720, 560)
        layout = QVBoxLayout(dlg)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        body = QFont()
        body.setPointSize(12)
        browser.setFont(body)

        if path.is_file():
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError as exc:
                raw = f"Could not read help file:\n{path}\n\n{exc}"
            browser.setMarkdown(raw)
        else:
            browser.setPlainText(
                "Help file not found.\n\n"
                f"Expected:\n{path}\n\n"
                "Reinstall or restore resources/help/USER_GUIDE.md."
            )

        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        close_btn = buttons.button(QDialogButtonBox.Close)
        if close_btn is not None:
            close_btn.clicked.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About FountainPad",
            "<h3>FountainPad</h3>"
            "<p>A clean, focused Fountain screenplay editor.</p>"
            "<p>Preview powered by bundled <b>fountain.js</b> (Matt Daly).</p>"
            "<p>Python · PySide6 · offline-friendly.</p>"
            "<p>Open <b>Help → FountainPad Help</b> (or press <b>F1</b>) "
            "for menus, panels, and how partial features are meant to be used.</p>"
            "<p>Split preview and detached preview are independent — "
            "use <b>Reattach Preview</b> to close a floating window and "
            "restore the in-window pane.</p>",
        )

    # --- Settings / close ------------------------------------------------
    def _load_settings(self) -> None:
        s = QSettings(APP_ORG, APP_NAME)
        geo = s.value("geometry")
        if isinstance(geo, QByteArray) and not geo.isEmpty():
            self.restoreGeometry(geo)
        state = s.value("windowState")
        if isinstance(state, QByteArray) and not state.isEmpty():
            self.restoreState(state)
        sizes = s.value("splitterSizes")
        if sizes:
            try:
                parsed = [int(x) for x in sizes]
                self.splitter.setSizes(parsed)
                self._saved_main_splitter_sizes = parsed
            except Exception:
                pass
        ep_sizes = s.value("editorPreviewSizes")
        if ep_sizes:
            try:
                parsed = [int(x) for x in ep_sizes]
                self._editor_preview.setSizes(parsed)
                self._saved_editor_preview_sizes = parsed
            except Exception:
                pass
        dark = s.value("darkMode", False)
        self._dark = str(dark).lower() in ("1", "true", "yes")
        self.act_dark.setChecked(self._dark)
        split = s.value("splitVisible", True)
        self._split_visible = str(split).lower() in ("1", "true", "yes")
        self.act_toggle_preview.setChecked(self._split_visible)
        self.preview.setVisible(self._split_visible)
        self.editor.set_word_wrap(self._split_visible)
        if self._split_visible:
            self._ensure_editor_preview_sizes()
        nav = s.value("navVisible", True)
        self._nav_visible = str(nav).lower() in ("1", "true", "yes")
        self.act_toggle_nav.setChecked(self._nav_visible)
        self.navigator.setVisible(self._nav_visible)
        cards = s.value("cardsVisible", True)
        self._cards_visible = str(cards).lower() in ("1", "true", "yes")
        self.act_toggle_cards.setChecked(self._cards_visible)
        self.card_navigator.setVisible(self._cards_visible)
        beats = s.value("beatsVisible", True)
        self._beats_visible = str(beats).lower() in ("1", "true", "yes")
        self.act_toggle_beats.setChecked(self._beats_visible)
        self.beat_board.setVisible(self._beats_visible)
        if self._nav_visible or self._cards_visible or self._beats_visible:
            self._ensure_main_splitter_sizes()

    def _save_settings(self) -> None:
        # Capture live sizes while panes are visible.
        if self._split_visible:
            self._remember_editor_preview_sizes()
        if self._nav_visible or self._cards_visible or self._beats_visible:
            self._remember_main_splitter_sizes()
        s = QSettings(APP_ORG, APP_NAME)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())
        s.setValue("splitterSizes", self._saved_main_splitter_sizes)
        s.setValue("editorPreviewSizes", self._saved_editor_preview_sizes)
        s.setValue("darkMode", self._dark)
        s.setValue("splitVisible", self._split_visible)
        s.setValue("navVisible", self._nav_visible)
        s.setValue("cardsVisible", self._cards_visible)
        s.setValue("beatsVisible", self._beats_visible)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._maybe_save():
            event.ignore()
            return
        self._save_settings()
        if self._detached is not None:
            try:
                self._detached.closed.disconnect(self._on_detached_closed)
            except (TypeError, RuntimeError):
                pass
            self._detached.close()
            self._detached = None
        event.accept()
