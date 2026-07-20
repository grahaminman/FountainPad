"""QWebEngineView preview powered by bundled fountain.js."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, QUrl, Signal
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
        # Re-apply theme + last content after load/reload
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
        # json.dumps gives a safe JS string literal
        payload = json.dumps(text)
        self._run_js(f"renderFountain({payload});")

    def _run_js(self, script: str) -> None:
        self.view.page().runJavaScript(script)


class PreviewWindow(QWidget):
    """Detached preview window hosting its own FountainPreview."""

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
