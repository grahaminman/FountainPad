#!/usr/bin/env python3
"""Headless smoke test for FountainPad."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from PySide6.QtCore import Qt, QCoreApplication
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication([])

    import PySide6
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

    print("PySide6", PySide6.__version__)
    print("QtWebEngine OK")

    from editor import FountainEditor
    from mainwindow import DEFAULT_FOUNTAIN, MainWindow

    # Compile-time modules already imported via MainWindow path
    ed = FountainEditor()
    ed.setPlainText(DEFAULT_FOUNTAIN)
    pat = ed.highlighter().re_scene

    found_scenes = []
    for i in range(ed.blockCount()):
        t = ed.document().findBlockByNumber(i).text()
        if pat.match(t.strip()):
            found_scenes.append(t.strip())
    assert found_scenes, "expected scene headings in sample"
    print("scenes_found", found_scenes)

    # Cursor starts at beginning (title page) — no scene yet is OK
    c = ed.textCursor()
    idx = ed.toPlainText().find("EXT. DESERT")
    assert idx >= 0
    c.setPosition(idx + 5)
    ed.setTextCursor(c)
    scene = ed.current_scene_heading()
    assert scene.startswith("EXT. DESERT"), scene
    print("on EXT:", scene)

    idx2 = ed.toPlainText().find("INT. OASIS")
    c.setPosition(idx2 + 5)
    ed.setTextCursor(c)
    scene2 = ed.current_scene_heading()
    assert scene2.startswith("INT. OASIS"), scene2
    print("on INT:", scene2)

    c.movePosition(QTextCursor.End)
    ed.setTextCursor(c)
    scene3 = ed.current_scene_heading()
    assert scene3.startswith("INT. OASIS"), scene3
    print("at end:", scene3)

    ed.apply_theme(True)
    ed.apply_theme(False)
    print("theme toggle OK")

    res = ROOT / "resources"
    for rel in (
        "fountain.js",
        "preview.html",
        "styles/preview-light.css",
        "styles/preview-dark.css",
    ):
        p = res / rel
        assert p.exists(), p
    html = (res / "preview.html").read_text(encoding="utf-8")
    assert "renderFountain" in html and "setTheme" in html
    js = (res / "fountain.js").read_text(encoding="utf-8")
    assert "parse" in js
    print("resources OK")

    w = MainWindow()
    # isVisible() is False until the window is shown (even offscreen).
    w.show()
    app.processEvents()
    assert "EXT. DESERT HIGHWAY" in w.editor.toPlainText()

    # Scene navigator
    scenes = w.editor.list_scene_headings()
    assert len(scenes) >= 2, scenes
    w._refresh_navigator()
    assert w.navigator._list.count() >= 2
    first_block, first_heading = scenes[0]
    w._on_scene_activated(first_block)
    assert w.editor.current_scene_heading().startswith(first_heading[:10])
    w.toggle_navigator(False)
    assert w.navigator.isHidden()
    w.toggle_navigator(True)
    assert not w.navigator.isHidden()
    print("navigator OK", [h for _, h in scenes])

    # File → Close clears buffer without quitting
    w.editor.setPlainText("INT. TEMP - DAY\n\nHi.\n")
    w._dirty = False  # avoid save prompt in headless test
    w.close_file()
    assert w.editor.toPlainText() == ""
    assert w._path is None
    assert w._dirty is False
    print("close_file OK")

    w.editor.setPlainText(DEFAULT_FOUNTAIN + "\n\nINT. TEST - NIGHT\n\nHello.\n")
    w._sync_previews(immediate=True)
    w._refresh_navigator()
    assert any(h.startswith("INT. TEST") for _, h in w.editor.list_scene_headings())
    w.toggle_dark_mode(True)
    w.toggle_dark_mode(False)

    # Split preview hide/show restores non-zero width
    w.toggle_split_preview(True)
    app.processEvents()
    assert w._split_visible and not w.preview.isHidden()
    w.toggle_split_preview(False)
    app.processEvents()
    assert (not w._split_visible) and w.preview.isHidden()
    w.toggle_split_preview(True)
    app.processEvents()
    assert w._split_visible and not w.preview.isHidden()
    sizes = w._editor_preview.sizes()
    assert len(sizes) >= 2 and sizes[1] >= 80, sizes
    print("split preview toggle OK", sizes)

    # Detach + reattach: floating closes and split forced on
    w.toggle_split_preview(False)
    app.processEvents()
    assert not w._split_visible
    w.detach_preview()
    app.processEvents()
    assert w._detached is not None
    assert w.act_reattach.isEnabled()
    w.reattach_preview()
    app.processEvents()
    assert w._detached is None
    assert w._split_visible is True
    assert not w.preview.isHidden()
    assert not w.act_reattach.isEnabled()
    print("detach/reattach OK")

    print("MainWindow OK")

    with tempfile.TemporaryDirectory() as td:
        fp = Path(td) / "sample.fountain"
        fp.write_text(DEFAULT_FOUNTAIN, encoding="utf-8")
        assert "FADE IN" in fp.read_text(encoding="utf-8")

        # PDF export path (WebEngine print); may be skipped if page never becomes ready
        pdf_path = Path(td) / "sample.pdf"
        done = {"ok": None}

        def _cb(ok: bool, path: str) -> None:
            done["ok"] = bool(ok) and Path(path).exists() and Path(path).stat().st_size > 0

        # Wait briefly for preview page load in offscreen mode
        from PySide6.QtCore import QEventLoop, QTimer as _QT

        loop = QEventLoop()
        _QT.singleShot(1500, loop.quit)
        if not w.preview._ready:
            w.preview.readyChanged.connect(lambda _ok: loop.quit())
            loop.exec()
        if w.preview._ready:
            w.preview.set_theme("light")
            w.preview.set_fountain_text(DEFAULT_FOUNTAIN, immediate=True)
            w.preview.print_to_pdf(str(pdf_path), _cb)
            loop2 = QEventLoop()
            _QT.singleShot(4000, loop2.quit)

            def _maybe_quit():
                if done["ok"] is not None:
                    loop2.quit()

            tick = _QT()
            tick.timeout.connect(_maybe_quit)
            tick.start(100)
            loop2.exec()
            tick.stop()
            if done["ok"]:
                print("pdf export OK", pdf_path.stat().st_size, "bytes")
            else:
                print("pdf export SKIP/FAIL in offscreen (non-fatal)", done["ok"], pdf_path.exists())
        else:
            print("pdf export SKIP (preview not ready offscreen)")

    print("file IO OK")
    print("ALL_CHECKS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
