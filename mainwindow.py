"""Main window: menus, splitter, theming, file ops."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QWidget,
)

from editor import FountainEditor
from preview import FountainPreview, PreviewWindow

APP_ORG = "FountainPad"
APP_NAME = "FountainPad"
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FountainPad")
        self.resize(1280, 840)

        self._path: Optional[Path] = None
        self._dirty = False
        self._dark = False
        self._split_visible = True
        self._detached: Optional[PreviewWindow] = None

        self.editor = FountainEditor()
        self.preview = FountainPreview()

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([640, 640])
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

        self.editor.contentChanged.connect(self._on_editor_changed)
        self.editor.cursorPositionChanged.connect(self._update_status)

        self._load_settings()
        self.new_file(initial=True)
        self._update_title()
        self._update_status()
        self._apply_theme()

    # --- UI construction -------------------------------------------------
    def _build_actions(self) -> None:
        self.act_new = QAction("New", self)
        self.act_new.setShortcut(QKeySequence.New)
        self.act_new.triggered.connect(lambda: self.new_file(initial=False))

        self.act_open = QAction("Open…", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_file)

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.save_file)

        self.act_save_as = QAction("Save As…", self)
        self.act_save_as.setShortcut(QKeySequence.SaveAs)
        self.act_save_as.triggered.connect(self.save_file_as)

        self.act_quit = QAction("Quit", self)
        self.act_quit.setShortcut(QKeySequence.Quit)
        self.act_quit.triggered.connect(self.close)

        self.act_toggle_preview = QAction("Show Split Preview", self)
        self.act_toggle_preview.setCheckable(True)
        self.act_toggle_preview.setChecked(True)
        self.act_toggle_preview.setShortcut(QKeySequence("Ctrl+P"))
        self.act_toggle_preview.triggered.connect(self.toggle_split_preview)

        self.act_detach = QAction("Detach Preview Window", self)
        self.act_detach.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_detach.triggered.connect(self.detach_preview)

        self.act_dark = QAction("Dark Mode", self)
        self.act_dark.setCheckable(True)
        self.act_dark.setShortcut(QKeySequence("Ctrl+D"))
        self.act_dark.triggered.connect(self.toggle_dark_mode)

        self.act_about = QAction("About FountainPad", self)
        self.act_about.triggered.connect(self.show_about)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.act_new)
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.act_toggle_preview)
        view_menu.addAction(self.act_detach)
        view_menu.addSeparator()
        view_menu.addAction(self.act_dark)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self.act_new)
        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addSeparator()
        tb.addAction(self.act_toggle_preview)
        tb.addAction(self.act_detach)
        tb.addSeparator()
        tb.addAction(self.act_dark)

    # --- File ops --------------------------------------------------------
    def new_file(self, initial: bool = False) -> None:
        if not initial and not self._maybe_save():
            return
        self.editor.blockSignals(True)
        self.editor.setPlainText(DEFAULT_FOUNTAIN if initial else "")
        self.editor.blockSignals(False)
        self._path = None
        self._dirty = False
        self._sync_previews(immediate=True)
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
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self._path = p
        self._dirty = False
        self._sync_previews(immediate=True)
        self._update_title()
        self._update_status()

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
        if not self._dirty:
            return True
        name = self._path.name if self._path else "Untitled"
        res = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save changes to “{name}”?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if res == QMessageBox.Cancel:
            return False
        if res == QMessageBox.Save:
            return self.save_file()
        return True

    # --- Preview / theme -------------------------------------------------
    def _on_editor_changed(self) -> None:
        self._dirty = True
        self._update_title()
        self._sync_previews(immediate=False)
        self._update_status()

    def _sync_previews(self, immediate: bool = False) -> None:
        text = self.editor.toPlainText()
        if self._split_visible:
            self.preview.set_fountain_text(text, immediate=immediate)
        if self._detached is not None:
            self._detached.preview.set_fountain_text(text, immediate=immediate)

    def toggle_split_preview(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = self.act_toggle_preview.isChecked()
        else:
            self.act_toggle_preview.setChecked(checked)
        self._split_visible = bool(checked)
        self.preview.setVisible(self._split_visible)
        # Wrap editor text when split so lines aren't clipped by the preview pane.
        self.editor.set_word_wrap(self._split_visible)
        if self._split_visible:
            self._sync_previews(immediate=True)

    def detach_preview(self) -> None:
        if self._detached is not None and self._detached.isVisible():
            self._detached.raise_()
            self._detached.activateWindow()
            return
        win = PreviewWindow()
        win.set_theme = win.preview.set_theme  # type: ignore[attr-defined]
        win.preview.set_theme("dark" if self._dark else "light")
        win.preview.set_fountain_text(self.editor.toPlainText(), immediate=True)
        win.closed.connect(self._on_detached_closed)
        self._detached = win
        win.show()

    def _on_detached_closed(self) -> None:
        self._detached = None

    def toggle_dark_mode(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            self._dark = not self._dark
            self.act_dark.setChecked(self._dark)
        else:
            self._dark = bool(checked)
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = "dark" if self._dark else "light"
        self.editor.apply_theme(self._dark)
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
                    color: #ddd;
                }
                QMenuBar::item:selected, QMenu::item:selected {
                    background: #3e3e42;
                }
                QToolBar QToolButton {
                    color: #ddd;
                    padding: 4px 8px;
                }
                QStatusBar QLabel { color: #bbb; }
                QMessageBox { background: #2d2d30; color: #ddd; }
                """
            )
        else:
            app.setStyleSheet(
                """
                QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar {
                    background-color: #f3f3f3;
                    color: #222;
                }
                QStatusBar QLabel { color: #444; }
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

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About FountainPad",
            "<h3>FountainPad</h3>"
            "<p>A clean, focused Fountain screenplay editor.</p>"
            "<p>Preview powered by bundled <b>fountain.js</b> (Matt Daly).</p>"
            "<p>Python · PySide6 · offline-friendly.</p>",
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
                self.splitter.setSizes([int(x) for x in sizes])
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

    def _save_settings(self) -> None:
        s = QSettings(APP_ORG, APP_NAME)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())
        s.setValue("splitterSizes", self.splitter.sizes())
        s.setValue("darkMode", self._dark)
        s.setValue("splitVisible", self._split_visible)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._maybe_save():
            event.ignore()
            return
        self._save_settings()
        if self._detached is not None:
            self._detached.close()
        event.accept()
