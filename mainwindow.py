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
  New / Open / Open Project Folder / Save / Save As / Close / Export PDF /
  Export/Import Card Pack (C7) / Export/Import Beat Pack / Quit.
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
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
)

from editor import FountainEditor
from navigator import SceneNavigator
from cardnavigator import CardNavigator
from beatboard import BeatBoard
from projectbinder import ProjectBinder
import project as project_mod
from preview import FountainPreview, PreviewWindow
import fountain_tools as fountain_tools
from titlepage import TitlePageDialog
from finddialogs import FindDialog, FindCharacterDialog

APP_ORG = "FountainPad"
APP_NAME = "FountainPad"

# First-run / New-from-sample text only. File → Close uses an empty buffer.
# Includes sections, cards, and beats so Outline / Index Cards / Beat Board demo live.
DEFAULT_FOUNTAIN = """Title: UNTITLED SCREENPLAY
Credit: written by
Author: Your Name
Draft date: 

==

FADE IN:

# Act One

[[beat: Opening Image | x=24 | y=24]]
A scarab on empty road — the world is watching.

## Highway

[[card: id=c001 | Goal | active=v1]]
@v1
Get across the desert before sundown.

EXT. DESERT HIGHWAY - DAY

Heat shimmers above the asphalt. A lone scarab crosses the road.

JULES
(squinting)
You ever get the feeling the dunes are watching?

She kicks the sand. Wind answers.

[[card: id=c002 | Conflict]]
@v1
The dunes feel hostile; Jules will not turn back.

CUT TO:

## Oasis

[[beat: Catalyst | x=200 | y=24]]
A stranger knows her name.

INT. OASIS CAFE - DAY

Ceiling fans chop the thick air. Jules slides into a booth.

MARCO
(without looking up)
You're late, Jules.

JULES
I don't know you.

MARCO
You will.

[[card: id=c003 | Turn]]
@v1
Marco drops a sealed envelope. Jules must open it or walk.

# Act Two

[[beat: Break into Two | x=24 | y=140]]
The envelope forces a choice — stay small or go under.

## The Bay

EXT. ARMOURED BAY - NIGHT

Floodlights carve white cones through the dust. A steel door rolls open.

JULES
(under her breath)
Okay. We're doing this.

She steps inside. The door seals behind her.

[[card: id=c004 | Goal]]
@v1
Secure the package and get out before the next shift.

[[beat: Midpoint | x=200 | y=140]]
The package is not what she was told.

## Safe House

INT. SAFE HOUSE - NIGHT

Maps on the wall. A single lamp. Jules empties the envelope onto the table.

JULES
This isn't money.

MARCO (V.O.)
It never was.

She stares at the photograph. Wind rattles the window.

[[card: id=c005 | Conflict]]
@v1
The photo shows someone she thought was dead.

[[beat: Climax Setup | x=376 | y=140]]
Dawn is coming — and so is the bay's second crew.

FADE OUT.

# End of sample
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
        self._project: Optional[project_mod.ProjectInfo] = None
        self._doc_kind: str = "fountain"  # fountain | markdown
        self._side_path: Optional[Path] = None
        self._dirty = False
        self._dark = False
        self._split_visible = True
        self._nav_visible = True
        self._cards_visible = True
        self._beats_visible = True
        self._binder_visible = False
        self._detached: Optional[PreviewWindow] = None
        self._pdf_busy = False
        # Remember non-zero splitter sizes so hide→show does not leave a 0-width pane.
        self._saved_editor_preview_sizes: list[int] = [
            _DEFAULT_EDITOR_WIDTH,
            _DEFAULT_SPLIT_PREVIEW_WIDTH,
        ]
        self._saved_main_splitter_sizes: list[int] = [
            200,
            _DEFAULT_NAV_WIDTH,
            _DEFAULT_CARD_NAV_WIDTH,
            900,
            _DEFAULT_NAV_WIDTH,
        ]

        self.editor = FountainEditor()
        self.preview = FountainPreview()
        self.navigator = SceneNavigator()
        self.card_navigator = CardNavigator()
        self.beat_board = BeatBoard()
        self.project_binder = ProjectBinder()
        self.side_editor = QPlainTextEdit()
        self.side_editor.setPlaceholderText("Project notes (markdown)…")
        mono = QFont("Menlo")
        if not mono.exactMatch():
            mono = QFont("Consolas")
        if not mono.exactMatch():
            mono = QFont("Courier New")
        mono.setStyleHint(QFont.Monospace)
        mono.setPointSize(12)
        self.side_editor.setFont(mono)

        # Centre stack: fountain workspace OR side markdown doc
        self._centre_stack = QStackedWidget()
        # Inner: editor | embedded preview
        self._editor_preview = QSplitter(Qt.Horizontal)
        self._editor_preview.addWidget(self.editor)
        self._editor_preview.addWidget(self.preview)
        self._editor_preview.setStretchFactor(0, 1)
        self._editor_preview.setStretchFactor(1, 1)
        self._editor_preview.setChildrenCollapsible(False)
        self._editor_preview.setSizes(self._saved_editor_preview_sizes)
        self._centre_stack.addWidget(self._editor_preview)  # index 0 = fountain
        self._centre_stack.addWidget(self.side_editor)  # index 1 = markdown notes

        # Outer: binder | outline | cards | centre | beat board
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.project_binder)
        self.splitter.addWidget(self.navigator)
        self.splitter.addWidget(self.card_navigator)
        self.splitter.addWidget(self._centre_stack)
        self.splitter.addWidget(self.beat_board)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setStretchFactor(3, 1)
        self.splitter.setStretchFactor(4, 0)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes(
            [200, _DEFAULT_NAV_WIDTH, _DEFAULT_NAV_WIDTH, 900, _DEFAULT_NAV_WIDTH]
        )
        self._saved_main_splitter_sizes = [
            200,
            _DEFAULT_NAV_WIDTH,
            _DEFAULT_NAV_WIDTH,
            900,
            _DEFAULT_NAV_WIDTH,
        ]
        self.setCentralWidget(self.splitter)
        # Binder hidden until a project is opened
        self.project_binder.setVisible(False)

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
        self.card_navigator.applyCardRequested.connect(self.apply_card_to_script)
        self.card_navigator.saveCardRequested.connect(self.save_card_from_panel)
        self.card_navigator.setActiveVersionRequested.connect(self.set_card_active_version)
        self.card_navigator.reorderCardRequested.connect(self.reorder_card_scene)
        self.card_navigator.reorderCardToSceneRequested.connect(
            self.reorder_card_scene_to_index
        )
        self.beat_board.beatActivated.connect(self._on_beat_activated)
        self.beat_board.beatMoved.connect(self._on_beat_moved)
        self.beat_board.layoutRequested.connect(self._layout_beats_grid)
        self.beat_board.newBeatRequested.connect(self._insert_beat_template)
        self.project_binder.fileActivated.connect(self._on_project_file_activated)
        self.project_binder.refreshRequested.connect(self._refresh_project_binder)
        self.project_binder.exportCardsRequested.connect(self.export_card_pack)
        self.project_binder.importCardsRequested.connect(self.import_card_pack)
        self.project_binder.exportBeatsRequested.connect(self.export_beat_pack)
        self.project_binder.importBeatsRequested.connect(self.import_beat_pack)
        self.side_editor.textChanged.connect(self._on_side_editor_changed)

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

        self.act_export_card_pack = QAction("Export &Card Pack…", self)
        self.act_export_card_pack.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.act_export_card_pack.setStatusTip(
            "Write cards.md from the script's [[card:]] markers (C7)"
        )
        self.act_export_card_pack.triggered.connect(self.export_card_pack)

        self.act_import_card_pack = QAction("Import C&ard Pack…", self)
        self.act_import_card_pack.setStatusTip(
            "Merge a cards.md pack into the script by card id (C7)"
        )
        self.act_import_card_pack.triggered.connect(self.import_card_pack)

        self.act_export_beat_pack = QAction("Export &Beat Pack…", self)
        self.act_export_beat_pack.setStatusTip(
            "Write beats.md from the script's [[beat:]] markers (C7)"
        )
        self.act_export_beat_pack.triggered.connect(self.export_beat_pack)

        self.act_import_beat_pack = QAction("Import B&eat Pack…", self)
        self.act_import_beat_pack.setStatusTip(
            "Merge a beats.md pack into the script by beat label (C7)"
        )
        self.act_import_beat_pack.triggered.connect(self.import_beat_pack)

        self.act_quit = QAction("&Quit", self)
        self.act_quit.setShortcut(QKeySequence.Quit)
        self.act_quit.setStatusTip("Quit FountainPad")
        self.act_quit.triggered.connect(self.close)

        self.act_open_project = QAction("Open &Project Folder…", self)
        self.act_open_project.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.act_open_project.setStatusTip("Open a project folder (Screenwriting OS structure)")
        self.act_open_project.triggered.connect(self.open_project)

        self.act_toggle_binder = QAction("Show Project &Binder", self)
        self.act_toggle_binder.setCheckable(True)
        self.act_toggle_binder.setChecked(False)
        self.act_toggle_binder.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_toggle_binder.setStatusTip(
            "Show or hide the project binder (open a project folder first)"
        )
        self.act_toggle_binder.triggered.connect(self.toggle_project_binder)
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

        self.act_find = QAction("&Find…", self)
        self.act_find.setShortcut(QKeySequence.Find)
        self.act_find.setStatusTip("Find text in the script")
        self.act_find.triggered.connect(self.show_find_dialog)

        self.act_find_next = QAction("Find &Next", self)
        self.act_find_next.setShortcut(QKeySequence.FindNext)
        self.act_find_next.setStatusTip("Find the next match")
        self.act_find_next.triggered.connect(self.find_next)

        self.act_find_character = QAction("Find C&haracter Dialogue…", self)
        self.act_find_character.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.act_find_character.setStatusTip(
            "List all dialogue blocks for a character and jump to one"
        )
        self.act_find_character.triggered.connect(self.show_find_character_dialog)

        self.act_title_page = QAction("&Title Page…", self)
        self.act_title_page.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.act_title_page.setStatusTip(
            "Edit Fountain title-page fields (Title, Author, …)"
        )
        self.act_title_page.triggered.connect(self.edit_title_page)

        self.act_dual_caret = QAction("Mark Dual Dialogue (^)", self)
        self.act_dual_caret.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.act_dual_caret.setStatusTip(
            "Add Fountain dual-dialogue caret (^) on the current character cue"
        )
        self.act_dual_caret.triggered.connect(self.insert_dual_dialogue_caret)

        self.act_cards_from_scenes = QAction("Generate Empty &Cards from Scenes…", self)
        self.act_cards_from_scenes.setStatusTip(
            "Insert optional empty card notes under scenes that have none"
        )
        self.act_cards_from_scenes.triggered.connect(self.generate_empty_cards_from_scenes)

        self.act_apply_card = QAction("&Apply Card to Script", self)
        self.act_apply_card.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.act_apply_card.setStatusTip(
            "Promote scene heading from the selected card into the screenplay"
        )
        self.act_apply_card.triggered.connect(self.apply_selected_card_to_script)

        self.act_ensure_card_ids = QAction("Ensure Card &IDs", self)
        self.act_ensure_card_ids.setStatusTip(
            "Assign stable id=cNNN to card markers that do not have one yet"
        )
        self.act_ensure_card_ids.triggered.connect(self.ensure_card_ids)

        self.act_card_up = QAction("Move Card Scene &Up", self)
        self.act_card_up.setShortcut(QKeySequence("Ctrl+Alt+Up"))
        self.act_card_up.setStatusTip(
            "Move the selected card's whole scene earlier in the script"
        )
        self.act_card_up.triggered.connect(lambda: self.reorder_selected_card_scene(-1))

        self.act_card_down = QAction("Move Card Scene &Down", self)
        self.act_card_down.setShortcut(QKeySequence("Ctrl+Alt+Down"))
        self.act_card_down.setStatusTip(
            "Move the selected card's whole scene later in the script"
        )
        self.act_card_down.triggered.connect(lambda: self.reorder_selected_card_scene(1))

        self.act_show_card_markers = QAction("Show Card &Markers in Editor", self)
        self.act_show_card_markers.setCheckable(True)
        self.act_show_card_markers.setChecked(True)
        self.act_show_card_markers.setStatusTip(
            "When off, dim [[card: …]] lines in the editor (still saved; never in preview/PDF)"
        )
        self.act_show_card_markers.triggered.connect(self.toggle_card_markers_in_editor)

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
        self.menu_file.addAction(self.act_export_card_pack)
        self.menu_file.addAction(self.act_import_card_pack)
        self.menu_file.addAction(self.act_export_beat_pack)
        self.menu_file.addAction(self.act_import_beat_pack)
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
        self.menu_edit.addAction(self.act_find)
        self.menu_edit.addAction(self.act_find_next)
        self.menu_edit.addAction(self.act_find_character)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.act_title_page)
        self.menu_edit.addAction(self.act_dual_caret)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.act_cards_from_scenes)
        self.menu_edit.addAction(self.act_apply_card)
        self.menu_edit.addAction(self.act_ensure_card_ids)
        self.menu_edit.addAction(self.act_card_up)
        self.menu_edit.addAction(self.act_card_down)

        self.menu_view = self.menuBar().addMenu("&View")
        self.menu_view.addAction(self.act_toggle_binder)
        self.menu_view.addAction(self.act_toggle_nav)
        self.menu_view.addAction(self.act_toggle_cards)
        self.menu_view.addAction(self.act_toggle_beats)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.act_toggle_preview)
        self.menu_view.addAction(self.act_detach)
        self.menu_view.addAction(self.act_reattach)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.act_show_card_markers)
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
        tb.addAction(self.act_toggle_binder)
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
        self._clear_project()
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
        self._clear_project()
        self._sync_previews(immediate=True)
        self._refresh_navigator()
        self._update_title()
        self._update_status()
        self.statusBar().showMessage("Closed", 2000)

    def open_project(self) -> None:
        """P1: open a project folder with binder + core files.

        Seeds missing core files:
          - script.fountain
          - canon.md
          - beats.md
          - cards.md
        Loads script.fountain into the Fountain editor and shows the binder.
        """
        if not self._maybe_save():
            return
        path = QFileDialog.getExistingDirectory(
            self,
            "Open Project Folder",
            str(
                self._project.root
                if self._project is not None
                else (self._path.parent if self._path else Path.home())
            ),
        )
        if not path:
            return
        self._load_project_folder(Path(path))

    def _load_project_folder(self, project_dir: Path) -> None:
        """Seed, bind, and open the project script (used by open_project + tests)."""
        info = project_mod.open_project_folder(project_dir, create_script=True)
        self._project = info
        self.project_binder.set_project(info)
        self._binder_visible = True
        self.project_binder.setVisible(True)
        self.act_toggle_binder.setChecked(True)
        self._ensure_main_splitter_sizes()

        script = info.script_path()
        if script.is_file():
            self._open_path_in_workspace(script, prefer_fountain=True)
        else:
            self._show_fountain_workspace()
            self.editor.blockSignals(True)
            self.editor.setPlainText("")
            self.editor.blockSignals(False)
            self._path = script
            self._doc_kind = "fountain"
            self._side_path = None
            self._dirty = False
            self._sync_previews(immediate=True)
            self._refresh_navigator()
            self._refresh_card_navigator()
            self._refresh_beat_board()

        self.project_binder.set_active_path(self._path)
        self._update_title()
        created = ", ".join(info.created) if info.created else "none"
        self.statusBar().showMessage(
            f"Project “{info.name}” · seeded: {created}", 6000
        )

    def _refresh_project_binder(self) -> None:
        if self._project is None:
            return
        root = self._project.root
        self._project = project_mod.ProjectInfo(
            root=root,
            files=project_mod.discover_project_files(root),
            created=[],
        )
        self.project_binder.set_project(self._project)
        self.project_binder.set_active_path(self._path)

    def _clear_project(self) -> None:
        self._project = None
        self.project_binder.set_project(None)
        self.project_binder.setVisible(False)
        self.act_toggle_binder.setChecked(False)
        self._binder_visible = False
        self._show_fountain_workspace()
        self._doc_kind = "fountain"
        self._side_path = None

    def _show_fountain_workspace(self) -> None:
        self._centre_stack.setCurrentIndex(0)

    def _show_side_workspace(self) -> None:
        self._centre_stack.setCurrentIndex(1)

    def _on_side_editor_changed(self) -> None:
        if self._doc_kind != "markdown":
            return
        self._dirty = True
        self._update_title()

    def _on_project_file_activated(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(self, "Missing file", f"Not found:\n{path}")
            self._refresh_project_binder()
            return
        if not self._maybe_save():
            return
        self._open_path_in_workspace(path)

    def _open_path_in_workspace(
        self, path: Path, *, prefer_fountain: bool = False
    ) -> None:
        """Open a project file as Fountain script or side markdown notes."""
        path = Path(path)
        is_fountain = project_mod.is_fountain_path(path) or (
            prefer_fountain and path.name.lower() == project_mod.SCRIPT_NAME
        )
        if is_fountain or (
            path.suffix.lower() == "" and path.name.endswith(".fountain")
        ):
            self._open_fountain_file(path)
            self._doc_kind = "fountain"
            self._side_path = None
            self._show_fountain_workspace()
        elif project_mod.is_markdown_path(path):
            try:
                text_body = path.read_text(encoding="utf-8")
            except OSError as exc:
                QMessageBox.critical(self, "Open failed", str(exc))
                return
            self.side_editor.blockSignals(True)
            self.side_editor.setPlainText(text_body)
            self.side_editor.blockSignals(False)
            self._path = path
            self._side_path = path
            self._doc_kind = "markdown"
            self._dirty = False
            self._show_side_workspace()
            self._update_title()
            self._update_status()
        else:
            # Unknown: try fountain
            self._open_fountain_file(path)
            self._doc_kind = "fountain"
            self._show_fountain_workspace()
        if self._project is not None:
            self.project_binder.set_active_path(self._path)

    def toggle_project_binder(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = self.act_toggle_binder.isChecked()
        else:
            self.act_toggle_binder.setChecked(checked)
        self._binder_visible = bool(checked)
        if self._project is None:
            self.project_binder.setVisible(False)
            self.act_toggle_binder.setChecked(False)
            self._binder_visible = False
            self.statusBar().showMessage(
                "Open a project folder to use the binder", 3000
            )
            return
        if self._binder_visible:
            self.project_binder.setVisible(True)
            self._ensure_main_splitter_sizes()
        else:
            self._remember_main_splitter_sizes()
            self.project_binder.setVisible(False)

    def _project_dir_for_packs(self) -> Path:
        """Prefer open project root, else folder of open file, else home."""
        if self._project is not None:
            return self._project.root
        if self._path is not None:
            return self._path.parent
        return Path.home()

    def _default_pack_path(self, filename: str) -> str:
        return str(self._project_dir_for_packs() / filename)

    def export_card_pack(self) -> None:
        """C7: write cards.md from current script card markers."""
        import cards as cards_mod

        # Flush pending card-panel typing so the pack matches the UI.
        if hasattr(self.card_navigator, "flush_pending_save"):
            try:
                self.card_navigator.flush_pending_save()
            except Exception:
                pass

        infos = self.editor.list_card_infos()
        # Ensure ids so round-trips can merge by id.
        if any(not (info.card_id or "").strip() for info in infos):
            self.editor.ensure_card_ids()
            infos = self.editor.list_card_infos()

        md = cards_mod.cards_to_markdown_pack(infos)
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Card Pack",
            self._default_pack_path("cards.md"),
            "Markdown (*.md);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            path.write_text(md, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export Card Pack failed", str(exc))
            return
        n = len(infos)
        self.statusBar().showMessage(
            f"Exported card pack ({n} card{'s' if n != 1 else ''}): {path.name}",
            5000,
        )

    def import_card_pack(self) -> None:
        """C7: merge cards.md into the open script by card id."""
        import cards as cards_mod

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import Card Pack",
            self._default_pack_path("cards.md"),
            "Markdown (*.md);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            md = path.read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Import Card Pack failed", str(exc))
            return

        pack_cards = cards_mod.parse_cards_markdown_pack(md)
        if not pack_cards:
            QMessageBox.information(
                self,
                "Import Card Pack",
                "No [[card:]] blocks found in that file.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Import Card Pack",
            (
                f"Merge {len(pack_cards)} card(s) from {path.name} into the script?\n\n"
                "• Matching id= updates the card body/versions in place.\n"
                "• New ids are inserted under their ## Scene heading when found.\n"
                "• Dialogue and non-card lines are not rewritten.\n\n"
                "The .fountain file remains the screenplay source of truth."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if hasattr(self.card_navigator, "flush_pending_save"):
            try:
                self.card_navigator.flush_pending_save()
            except Exception:
                pass

        new_text, msg = cards_mod.merge_card_pack_into_text(
            self.editor.toPlainText(),
            pack_cards,
            self.editor.is_scene_heading,
        )
        if new_text == self.editor.toPlainText():
            self.statusBar().showMessage(msg + " (no text change)", 5000)
            return

        self.editor.blockSignals(True)
        cursor_pos = self.editor.textCursor().position()
        self.editor.setPlainText(new_text)
        # Best-effort caret restore
        from PySide6.QtGui import QTextCursor

        cur = self.editor.textCursor()
        cur.setPosition(min(cursor_pos, len(new_text)))
        self.editor.setTextCursor(cur)
        self.editor.blockSignals(False)
        self._dirty = True
        self._sync_previews(immediate=True)
        self._refresh_navigator()
        self._refresh_card_navigator()
        self._refresh_beat_board()
        self._update_title()
        self._update_status()
        self.statusBar().showMessage(msg, 6000)

    def export_beat_pack(self) -> None:
        """C7: write beats.md from current script beat markers."""
        import cards as cards_mod

        beats = self.editor.list_beats()
        md = cards_mod.beats_to_markdown_pack(beats)
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Beat Pack",
            self._default_pack_path("beats.md"),
            "Markdown (*.md);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            path.write_text(md, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export Beat Pack failed", str(exc))
            return
        n = len(beats)
        self.statusBar().showMessage(
            f"Exported beat pack ({n} beat{'s' if n != 1 else ''}): {path.name}",
            5000,
        )

    def import_beat_pack(self) -> None:
        """C7: merge beats.md into the open script by beat label."""
        import cards as cards_mod

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import Beat Pack",
            self._default_pack_path("beats.md"),
            "Markdown (*.md);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            md = path.read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Import Beat Pack failed", str(exc))
            return

        pack_beats = cards_mod.parse_beats_markdown_pack(md)
        if not pack_beats:
            QMessageBox.information(
                self,
                "Import Beat Pack",
                "No [[beat:]] blocks found in that file.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Import Beat Pack",
            (
                f"Merge {len(pack_beats)} beat(s) from {path.name} into the script?\n\n"
                "• Matching [[beat: Label]] updates the note line.\n"
                "• New labels are inserted under their ## Scene heading when found.\n"
                "• Scene action and dialogue are not rewritten."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        new_text, msg = cards_mod.merge_beat_pack_into_text(
            self.editor.toPlainText(),
            pack_beats,
            self.editor.is_scene_heading,
        )
        if new_text == self.editor.toPlainText():
            self.statusBar().showMessage(msg + " (no text change)", 5000)
            return

        self.editor.blockSignals(True)
        cursor_pos = self.editor.textCursor().position()
        self.editor.setPlainText(new_text)
        from PySide6.QtGui import QTextCursor

        cur = self.editor.textCursor()
        cur.setPosition(min(cursor_pos, len(new_text)))
        self.editor.setTextCursor(cur)
        self.editor.blockSignals(False)
        self._dirty = True
        self._sync_previews(immediate=True)
        self._refresh_navigator()
        self._refresh_card_navigator()
        self._refresh_beat_board()
        self._update_title()
        self._update_status()
        self.statusBar().showMessage(msg, 6000)

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
        self._doc_kind = "fountain"
        self._side_path = None
        self._dirty = False
        self._show_fountain_workspace()
        self._sync_previews(immediate=True)
        self._refresh_navigator()
        self._refresh_card_navigator()
        self._refresh_beat_board()
        if self._project is not None:
            # Stay in project if the file lives under the project root
            try:
                path.resolve().relative_to(self._project.root.resolve())
            except ValueError:
                self._clear_project()
            else:
                self.project_binder.set_active_path(path)
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
        if self._doc_kind == "markdown":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Markdown",
                str(self._path or Path.home() / "notes.md"),
                "Markdown (*.md);;Text (*.txt);;All files (*.*)",
            )
            if not path:
                return False
            p = Path(path)
            if p.suffix == "":
                p = p.with_suffix(".md")
            return self._write_to(p)
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
        if self._doc_kind == "markdown":
            body = self.side_editor.toPlainText()
        else:
            body = self.editor.toPlainText()
        try:
            path.write_text(body, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        self._path = path
        if self._doc_kind == "markdown":
            self._side_path = path
        self._dirty = False
        self._update_title()
        if self._project is not None:
            self._refresh_project_binder()
            self.project_binder.set_active_path(self._path)
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

        # PDF must never show card/@vN planning chrome.
        text = self._preview_source_text()
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
            target.set_fountain_text(self._preview_source_text(), immediate=True)
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
                target.set_fountain_text(self._preview_source_text(), immediate=True)
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

    def _preview_source_text(self) -> str:
        """Fountain text for preview/PDF: strip cards/beats/sections (incl. @vN)."""
        import cards as cards_mod

        return cards_mod.strip_cards_for_preview(
            self.editor.toPlainText(),
            self.editor.is_scene_heading,
        )

    def _sync_previews(self, immediate: bool = False) -> None:
        """
        Push editor text to every live preview surface.

        Card/beat markers, version lines (@vN), and Fountain ``#`` sections are
        stripped so the page never shows planning/outline chrome. Embedded
        preview stays warm for PDF.
        """
        text = self._preview_source_text()
        self.preview.set_fountain_text(text, immediate=immediate)
        if self._detached is not None:
            self._detached.preview.set_fountain_text(text, immediate=immediate)

    def _refresh_navigator(self) -> None:
        # N4: sections (#) + scenes in one outline tree
        if hasattr(self.editor, "list_outline_nodes"):
            self.navigator.set_outline(self.editor.list_outline_nodes())
        else:
            self.navigator.set_scenes(self.editor.list_scene_headings())
        block_no = self.editor.textCursor().blockNumber()
        self.navigator.highlight_block(block_no)

    def _refresh_card_navigator(self) -> None:
        infos = self.editor.list_card_infos()
        self.card_navigator.set_card_infos(infos)
        block_no = self.editor.textCursor().blockNumber()
        # Highlight the card nearest to the cursor
        if infos:
            target_block = -1
            for info in infos:
                if info.block_number <= block_no:
                    target_block = info.block_number
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
        # C4: freeform board uses BeatInfo (label/note/scene + optional x/y)
        if hasattr(self.editor, "list_beat_infos"):
            self.beat_board.set_beat_infos(self.editor.list_beat_infos())
        else:
            self.beat_board.set_beats(self.editor.list_beats())
        block_no = self.editor.textCursor().blockNumber()
        self.beat_board.highlight_block(block_no)

    def _on_beat_activated(self, block_number: int) -> None:
        self.editor.goto_block(block_number)
        self._update_status()

    def _on_beat_moved(self, block_number: int, x: float, y: float) -> None:
        """Persist dragged beat card position onto the [[beat:]] marker."""
        changed = self.editor.set_beat_board_position(block_number, x, y)
        if changed:
            self._dirty = True
            self._update_title()
            # Soft refresh — keep selection; avoid full rebuild thrash if possible
            self._beats_refresh.start()
            self.statusBar().showMessage(
                f"Beat position saved ({int(x)}, {int(y)})", 1500
            )

    def _layout_beats_grid(self) -> None:
        """Write grid x/y onto every beat marker (C4 Layout grid)."""
        n = self.editor.auto_layout_beats(cols=3)
        if n:
            self._dirty = True
            self._update_title()
            self._refresh_beat_board()
            self._sync_previews(immediate=True)
            self.statusBar().showMessage(f"Laid out {n} beat(s) on grid", 2500)
        else:
            self.statusBar().showMessage("No beats to lay out", 2000)

    def _insert_beat_template(self) -> None:
        """Insert [[beat: Beat]] at cursor for the freeform board."""
        stub = self.editor.format_new_beat_marker("Beat") + "\n"
        cursor = self.editor.textCursor()
        if cursor.positionInBlock() > 0 and not cursor.atBlockStart():
            cursor.movePosition(cursor.MoveOperation.EndOfBlock)
            cursor.insertText("\n")
        cursor.insertText(stub)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus(Qt.OtherFocusReason)
        self._dirty = True
        self._update_title()
        self._refresh_beat_board()
        self.statusBar().showMessage("Inserted beat marker", 2000)

    def _insert_card_template(self, card_type: str) -> None:
        """Insert a [[card: id=… | Type]] stub at the cursor and refresh the card list."""
        label = (card_type or "Note").strip() or "Note"
        stub = self.editor.format_new_card_marker(label) + "\n"
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

    def ensure_card_ids(self) -> None:
        """Assign stable ids to any card markers missing id=."""
        assigned = self.editor.ensure_card_ids()
        if assigned:
            self._dirty = True
            self._update_title()
            self._refresh_card_navigator()
            self._sync_previews(immediate=True)
            self.statusBar().showMessage(f"Assigned {assigned} card id(s)", 3000)
        else:
            self.statusBar().showMessage("All card markers already have ids", 2500)

    def toggle_card_markers_in_editor(self, checked: Optional[bool] = None) -> None:
        """Show or dim [[card:]] lines in the editor only (file unchanged)."""
        if checked is None:
            checked = self.act_show_card_markers.isChecked()
        else:
            self.act_show_card_markers.setChecked(checked)
        # checked True = show markers; hide when unchecked
        self.editor.set_hide_card_markers(not bool(checked))
        self.statusBar().showMessage(
            "Card markers visible in editor"
            if checked
            else "Card markers dimmed in editor (still in file; never in preview/PDF)",
            3000,
        )

    def apply_selected_card_to_script(self) -> None:
        """Apply the card selected in the Index Cards list."""
        item = self.card_navigator._list.currentItem()
        if item is None:
            infos = self.editor.list_card_infos()
            if not infos:
                QMessageBox.information(
                    self,
                    "Apply card to script",
                    "No cards in this script.\n\n"
                    "Add a card first (Goal/Conflict/Turn, From scenes, or type [[card: …]]).",
                )
                return
            # Use card nearest cursor
            block_no = self.editor.textCursor().blockNumber()
            target = infos[0]
            for info in infos:
                if info.block_number <= block_no:
                    target = info
                else:
                    break
            self.apply_card_to_script(target.block_number)
            return
        self.apply_card_to_script(int(item.data(Qt.UserRole)))

    def apply_card_to_script(self, card_block: int) -> None:
        """Apply active card version: scene heading + leading action only (never dialogue)."""
        # Flush any debounced panel typing before reading working text / file.
        if hasattr(self.card_navigator, "flush_pending_save"):
            self.card_navigator.flush_pending_save()
        before = self.editor.toPlainText()
        # Prefer panel working text + snapshot so left-side edits win on Apply.
        info = None
        for c in self.editor.list_card_infos():
            if c.block_number == int(card_block):
                info = c
                break
        if info is not None and self.card_navigator.current_block() == int(card_block):
            versions = list(info.versions) if info.versions else []
            message = self.editor.apply_card_with_panel_state(
                int(card_block),
                info.card_id or "",
                self.card_navigator.working_type(),
                versions,
                info.active_version or "v1",
                do_snapshot_from=self.card_navigator.working_text(),
            )
        else:
            message = self.editor.apply_card_to_script(int(card_block))
        after = self.editor.toPlainText()
        if after != before:
            self._dirty = True
            self._update_title()
            self._refresh_card_navigator()
            self._refresh_navigator()
            self._sync_previews(immediate=True)
            self._update_status()
            if not self._cards_visible:
                self.toggle_card_navigator(True)
        self.statusBar().showMessage(message or "Apply card finished", 5000)
        self.editor.setFocus(Qt.OtherFocusReason)

    def save_card_from_panel(
        self,
        card_block: int,
        card_id: str,
        card_type: str,
        versions,
        active: str,
        make_snapshot: bool,
    ) -> None:
        """Write card detail/versions from the Index Cards panel into the Fountain file."""
        del make_snapshot  # versions already snapshotted by the panel when requested
        before = self.editor.toPlainText()
        # Ensure id exists
        if not card_id:
            existing = {c.card_id for c in self.editor.list_card_infos() if c.card_id}
            import cards as cards_mod

            card_id = cards_mod.next_card_id(existing)
        message = self.editor.write_card_block(
            int(card_block),
            card_id,
            card_type or "Note",
            versions,
            active or "v1",
        )
        after = self.editor.toPlainText()
        if after != before:
            self._dirty = True
            self._update_title()
            self._refresh_card_navigator()
            self._sync_previews(immediate=True)
        self.statusBar().showMessage(message or "Card saved", 3000)

    def reorder_selected_card_scene(self, direction: int) -> None:
        block = self.card_navigator.current_block()
        if block < 0:
            infos = self.editor.list_card_infos()
            if not infos:
                self.statusBar().showMessage("No cards to reorder", 2500)
                return
            block_no = self.editor.textCursor().blockNumber()
            target = infos[0]
            for info in infos:
                if info.block_number <= block_no:
                    target = info
                else:
                    break
            block = target.block_number
        self.reorder_card_scene(int(block), int(direction))

    def reorder_card_scene_to_index(self, card_block: int, target_scene_index: int) -> None:
        """Phase C2: drag-drop — move card's scene to an absolute scene index."""
        if hasattr(self.card_navigator, "flush_pending_save"):
            self.card_navigator.flush_pending_save()
        before = self.editor.toPlainText()
        message, new_block = self.editor.reorder_card_scene_to_scene_index(
            int(card_block), int(target_scene_index)
        )
        after = self.editor.toPlainText()
        if after != before:
            self._dirty = True
            self._update_title()
            self._refresh_card_navigator()
            self._refresh_navigator()
            self._sync_previews(immediate=True)
            self._update_status()
            if not self._cards_visible:
                self.toggle_card_navigator(True)
            if new_block >= 0:
                for row in range(self.card_navigator._list.count()):
                    item = self.card_navigator._list.item(row)
                    if item and int(item.data(Qt.UserRole)) == new_block:
                        self.card_navigator._updating = True
                        self.card_navigator._list.setCurrentRow(row)
                        self.card_navigator._updating = False
                        break
                self.editor.goto_block(new_block)
        else:
            # Drop may have shuffled the QListWidget visually — rebuild from file.
            self._refresh_card_navigator()
        self.statusBar().showMessage(message or "Reorder finished", 5000)

    def reorder_card_scene(self, card_block: int, direction: int) -> None:
        """Phase C: move the scene owned by this card up/down in the Fountain file."""
        if hasattr(self.card_navigator, "flush_pending_save"):
            self.card_navigator.flush_pending_save()
        before = self.editor.toPlainText()
        message, new_block = self.editor.reorder_card_scene(int(card_block), int(direction))
        after = self.editor.toPlainText()
        if after != before:
            self._dirty = True
            self._update_title()
            self._refresh_card_navigator()
            self._refresh_navigator()
            self._sync_previews(immediate=True)
            self._update_status()
            if not self._cards_visible:
                self.toggle_card_navigator(True)
            if new_block >= 0:
                # Reselect moved card in the panel
                for row in range(self.card_navigator._list.count()):
                    item = self.card_navigator._list.item(row)
                    if item and int(item.data(Qt.UserRole)) == new_block:
                        self.card_navigator._updating = True
                        self.card_navigator._list.setCurrentRow(row)
                        self.card_navigator._updating = False
                        break
                self.editor.goto_block(new_block)
        self.statusBar().showMessage(message or "Reorder finished", 5000)

    def set_card_active_version(self, card_block: int, version_id: str) -> None:
        """Make a historical version the active (top priority) version on a card."""
        infos = self.editor.list_card_infos()
        info = next((c for c in infos if c.block_number == int(card_block)), None)
        if info is None:
            self.statusBar().showMessage("Card not found", 2500)
            return
        import cards as cards_mod

        versions = list(info.versions) if info.versions else [cards_mod.CardVersion("v1", info.body)]
        versions, active, msg = cards_mod.set_active_version(versions, version_id)
        card_id = info.card_id or ""
        if not card_id:
            existing = {c.card_id for c in infos if c.card_id}
            card_id = cards_mod.next_card_id(existing)
        before = self.editor.toPlainText()
        self.editor.write_card_block(
            int(card_block),
            card_id,
            info.card_type or "Note",
            versions,
            active,
        )
        after = self.editor.toPlainText()
        if after != before:
            self._dirty = True
            self._update_title()
            self._refresh_card_navigator()
            self._sync_previews(immediate=True)
        self.statusBar().showMessage(msg or f"Active {active}", 3000)

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
            "Each stub looks like:\n[[card: id=cNNN | Note]]",
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
            # Leave a blank line under the slugline, then an id'd note stub.
            marker = self.editor.format_new_card_marker("Note")
            cursor.insertText(f"\n\n{marker}\n")
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
        win.preview.set_fountain_text(self._preview_source_text(), immediate=True)
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
        # P1 layout: binder | outline | cards | centre | beats (5 panes)
        if len(sizes) >= 5 and any(s > 40 for s in sizes):
            self._saved_main_splitter_sizes = list(sizes)

    def _ensure_main_splitter_sizes(self) -> None:
        """Restore sensible widths for visible side panes (binder/nav/cards/beats)."""
        default = [
            200,
            _DEFAULT_NAV_WIDTH,
            _DEFAULT_CARD_NAV_WIDTH,
            900,
            _DEFAULT_NAV_WIDTH,
        ]
        sizes = list(self.splitter.sizes())
        if len(sizes) < 5:
            sizes = (
                list(self._saved_main_splitter_sizes)
                if len(self._saved_main_splitter_sizes) >= 5
                else default
            )
        # Index: 0 binder, 1 outline, 2 cards, 3 centre, 4 beats
        if self._binder_visible and self._project is not None and sizes[0] < 40:
            sizes[0] = default[0]
        if self._nav_visible and sizes[1] < 40:
            sizes[1] = default[1]
        if self._cards_visible and sizes[2] < 40:
            sizes[2] = default[2]
        if sizes[3] < 120:
            sizes[3] = default[3]
        if self._beats_visible and sizes[4] < 40:
            sizes[4] = default[4]
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
        self.project_binder.apply_theme(self._dark)
        # Side markdown editor chrome
        if self._dark:
            self.side_editor.setStyleSheet(
                "QPlainTextEdit { background:#1e1e1e; color:#d4d4d4; selection-background-color:#264f78; border:none; }"
            )
        else:
            self.side_editor.setStyleSheet(
                "QPlainTextEdit { background:#fafafa; color:#1a1a1a; selection-background-color:#cde8ff; border:none; }"
            )
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
        if self._path is not None:
            name = self._path.name
        elif self._doc_kind == "markdown":
            name = "Untitled.md"
        else:
            name = "Untitled.fountain"
        dirty = " •" if self._dirty else ""
        if self._project is not None:
            self.setWindowTitle(
                f"{self._project.name} · {name}{dirty} — FountainPad"
            )
        else:
            self.setWindowTitle(f"{name}{dirty} — FountainPad")

    def _update_status(self) -> None:
        if self._doc_kind == "markdown":
            body = self.side_editor.toPlainText()
            chars = len(body)
            words = len(body.split()) if body.strip() else 0
            label = self._path.name if self._path else "notes"
            self._scene_label.setText(f"Notes: {label}")
            self._count_label.setText(f"{chars} chars · {words} words")
            return
        body = self.editor.toPlainText()
        chars = len(body)
        pages, minutes, _lines, words = fountain_tools.estimate_pages(body)
        scene = self.editor.current_scene_heading() or "—"
        if len(scene) > 60:
            scene = scene[:57] + "…"
        self._scene_label.setText(f"Scene: {scene}")
        # Rough screenplay estimate (~55 lines/page; ~1 min/page)
        self._count_label.setText(
            f"{chars} chars · {words} words · ~{pages:g} pp · ~{minutes:g} min"
        )
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

    def show_find_dialog(self) -> None:
        """Open Find dialog for the source editor."""
        if self._doc_kind == "markdown":
            self.statusBar().showMessage("Find works in the Fountain script view", 3000)
            return
        if not hasattr(self, "_find_dialog") or self._find_dialog is None:
            self._find_dialog = FindDialog(self.editor, self)
        # Seed with selection if any
        cur = self.editor.textCursor()
        if cur.hasSelection():
            self._find_dialog.set_needle(cur.selectedText().replace("\u2029", " "))
        self._find_dialog.show()
        self._find_dialog.raise_()
        self._find_dialog.activateWindow()
        self._find_dialog._needle.setFocus()

    def find_next(self) -> None:
        if self._doc_kind == "markdown":
            return
        if not hasattr(self, "_find_dialog") or self._find_dialog is None:
            self.show_find_dialog()
            return
        self._find_dialog.find_next()

    def show_find_character_dialog(self) -> None:
        if self._doc_kind == "markdown":
            self.statusBar().showMessage("Switch to the script to find character lines", 3000)
            return
        dlg = FindCharacterDialog(self.editor, self.editor.is_scene_heading, self)
        dlg.refresh()
        dlg.exec()

    def edit_title_page(self) -> None:
        """Edit Fountain title-page keys via a simple form."""
        if self._doc_kind == "markdown":
            self.statusBar().showMessage("Title page applies to the Fountain script", 3000)
            return
        text = self.editor.toPlainText()
        values, _end = fountain_tools.parse_title_page(text)
        dlg = TitlePageDialog(values, self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_text = fountain_tools.replace_title_page(text, dlg.values())
        if new_text != text:
            self.editor._replace_all_text(new_text)
            self._dirty = True
            self._update_title()
            self._sync_previews(immediate=True)
            self._update_status()
            self.statusBar().showMessage("Title page updated", 3000)
        else:
            self.statusBar().showMessage("Title page unchanged", 2000)

    def insert_dual_dialogue_caret(self) -> None:
        if self._doc_kind == "markdown":
            return
        self.editor.insert_dual_dialogue_caret()
        self.statusBar().showMessage(
            "Dual dialogue: second character cue ends with ^ (Fountain)", 4000
        )

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
        show_markers = s.value("showCardMarkers", True)
        show_markers_b = str(show_markers).lower() in ("1", "true", "yes")
        self.act_show_card_markers.setChecked(show_markers_b)
        self.editor.set_hide_card_markers(not show_markers_b)
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
        s.setValue("showCardMarkers", self.act_show_card_markers.isChecked())

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
