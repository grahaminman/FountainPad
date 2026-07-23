"""
preview.py — Formatted screenplay preview + detached window + PDF.

Developer notes
---------------
FountainPreview
  Hosts a QWebEngineView that loads resources/preview.html (local file URL).
  That page bundles fountain.js and exposes JS:
    setTheme('light'|'dark')
    renderFountain(sourceString)

  Python → JS bridge:
    set_fountain_text(text, immediate=False)
      Debounced 300ms while typing; immediate=True for open/save/theme/PDF.
    set_theme(theme)
    print_to_pdf(path, callback, page_layout)
      Uses QWebEnginePage.printToPdf. Finished signal arg order varies by
      binding — _finished normalises (path, ok) vs (ok, path).

  Readiness
    Page load is async. Text/theme applied before loadFinished are queued
    (_pending_text / _pending_theme) and flushed when ready.

PreviewWindow
  Thin QWidget shell around its own FountainPreview instance (separate
  WebEngine page from the embedded one). Emits closed when the window
  chrome closes so MainWindow can clear _detached.

Architecture choice
  Embedded + detached are *two* previews (two WebEngine instances), not one
  widget reparented. Simpler lifecycle; small memory cost. MainWindow keeps
  both in sync via _sync_previews().

Resources
  resources/preview.html
  resources/fountain.js          (Matt Daly, MIT — do not minify-break API)
  resources/styles/preview-*.css
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMarginsF, QTimer, QUrl, Signal
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PySide6 QtWebEngine is required. Install with:\n"
        "  pip install PySide6\n"
        f"Original error: {exc}"
    ) from exc


RESOURCES = Path(__file__).resolve().parent / "resources"
PREVIEW_HTML = RESOURCES / "preview.html"


class FountainPreview(QWidget):
    """Renders Fountain source via local HTML + fountain.js."""

    readyChanged = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.view = QWebEngineView(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self._ready = False
        self._pending_text: Optional[str] = None
        self._pending_theme: Optional[str] = None
        self._theme = "light"
        self._last_text = ""

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._flush)

        self.view.loadFinished.connect(self._on_load_finished)
        self.reload_page()

    def reload_page(self) -> None:
        if not PREVIEW_HTML.exists():
            raise FileNotFoundError(f"Missing preview template: {PREVIEW_HTML}")
        self._ready = False
        url = QUrl.fromLocalFile(str(PREVIEW_HTML.resolve()))
        self.view.load(url)

    def _on_load_finished(self, ok: bool) -> None:
        self._ready = bool(ok)
        self.readyChanged.emit(self._ready)
        if not ok:
            return
        # Re-apply theme + last content after load/reload.
        self._run_js(f"setTheme({json.dumps(self._theme)});")
        if self._pending_text is not None:
            text = self._pending_text
            self._pending_text = None
            self._apply_text(text)
        elif self._last_text:
            self._apply_text(self._last_text)
        if self._pending_theme is not None:
            theme = self._pending_theme
            self._pending_theme = None
            self.set_theme(theme)

    def set_theme(self, theme: str) -> None:
        theme = "dark" if theme == "dark" else "light"
        self._theme = theme
        if not self._ready:
            self._pending_theme = theme
            return
        self._run_js(f"setTheme({json.dumps(theme)});")

    def set_fountain_text(self, text: str, immediate: bool = False) -> None:
        """Push Fountain source into the HTML preview (debounced unless immediate)."""
        self._last_text = text
        if immediate:
            self._debounce.stop()
            self._apply_text(text)
            return
        self._debounce.start()

    def _flush(self) -> None:
        self._apply_text(self._last_text)

    def _apply_text(self, text: str) -> None:
        if not self._ready:
            self._pending_text = text
            return
        # json.dumps → safe JS string literal (handles quotes/newlines).
        payload = json.dumps(text)
        self._run_js(f"renderFountain({payload});")

    def _run_js(self, script: str) -> None:
        self.view.page().runJavaScript(script)

    def print_to_pdf(
        self,
        path: str,
        callback: Optional[Callable[[bool, str], None]] = None,
        page_layout: Optional[QPageLayout] = None,
    ) -> None:
        """
        Export the current preview page to a PDF file via Qt WebEngine.

        callback(ok: bool, path: str) is invoked when printing finishes.
        Caller should force light theme before print if desired (MainWindow does).
        """
        # PySide6 requires margins in the QPageLayout(page, orientation, …) form.
        if page_layout is not None and page_layout.isValid():
            layout = page_layout
        else:
            layout = QPageLayout(
                QPageSize(QPageSize.Letter),
                QPageLayout.Portrait,
                QMarginsF(0.5, 0.5, 0.5, 0.5),
                QPageLayout.Inch,
            )

        def _finished(*args) -> None:
            # Qt emits pdfPrintingFinished(filePath: str, success: bool)
            # Some bindings historically flipped order — accept both.
            pdf_path = path
            ok = False
            if len(args) >= 2:
                a0, a1 = args[0], args[1]
                if isinstance(a0, str):
                    pdf_path, ok = a0, bool(a1)
                elif isinstance(a1, str):
                    ok, pdf_path = bool(a0), a1
                else:
                    ok = bool(a1)
            elif len(args) == 1:
                ok = bool(args[0])
            try:
                self.view.page().pdfPrintingFinished.disconnect(_finished)
            except (TypeError, RuntimeError):
                pass
            if callback is not None:
                callback(bool(ok), str(pdf_path))

        try:
            self.view.page().pdfPrintingFinished.connect(_finished)
        except Exception:
            self.view.page().printToPdf(path, layout)
            if callback is not None:

                def _fallback() -> None:
                    p = Path(path)
                    callback(p.exists() and p.stat().st_size > 0, path)

                QTimer.singleShot(800, _fallback)
            return

        self.view.page().printToPdf(path, layout)


class PreviewWindow(QWidget):
    """
    Detached preview window hosting its own FountainPreview.

    Closing this window (title-bar X) emits closed so MainWindow can clear
    its _detached reference. Reattach is handled in MainWindow (closes us
    and restores the embedded split pane).
    """

    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FountainPad Preview")
        self.resize(720, 900)
        self.preview = FountainPreview(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)
