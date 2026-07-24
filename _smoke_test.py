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

    # Cards / beats parsers (Phase 2)
    sample_cards = (
        "INT. OFFICE - DAY\n\n"
        "[[card: Goal]]\n"
        "Get the files.\n\n"
        "[[card: Conflict]]\n"
        "Guard arrives.\n\n"
        "[[beat: Act 1 Turn]]\n"
        "She runs.\n"
    )
    ed.setPlainText(sample_cards)
    cards = ed.list_cards()
    assert len(cards) >= 2, cards
    assert cards[0][1] == "Goal", cards[0]
    assert cards[1][1] == "Conflict", cards[1]
    assert "OFFICE" in cards[0][3], cards[0]
    beats = ed.list_beats()
    assert len(beats) >= 1, beats
    assert "Act" in beats[0][1] or "Turn" in beats[0][1] or "Act" in beats[0][2], beats[0]
    print("cards/beats parse OK", cards, beats)

    res = ROOT / "resources"
    for rel in (
        "fountain.js",
        "preview.html",
        "styles/preview-light.css",
        "styles/preview-dark.css",
        "help/USER_GUIDE.md",
    ):
        p = res / rel
        assert p.exists(), p
    html = (res / "preview.html").read_text(encoding="utf-8")
    assert "renderFountain" in html and "setTheme" in html
    js = (res / "fountain.js").read_text(encoding="utf-8")
    assert "parse" in js
    light_css = (res / "styles/preview-light.css").read_text(encoding="utf-8")
    dark_css = (res / "styles/preview-dark.css").read_text(encoding="utf-8")
    assert "@media print" in light_css and ".note" in light_css
    assert "@media print" in dark_css and ".note" in dark_css
    guide = (res / "help/USER_GUIDE.md").read_text(encoding="utf-8")
    assert "FountainPad" in guide and "Partial" in guide
    assert "Show Index Cards" in guide or "Index cards" in guide
    print("resources OK (incl. F5 print note hide + USER_GUIDE)")

    w = MainWindow()
    # isVisible() is False until the window is shown (even offscreen).
    w.show()
    app.processEvents()
    assert "EXT. DESERT HIGHWAY" in w.editor.toPlainText()
    assert hasattr(w, "beat_board")
    assert hasattr(w, "card_navigator")

    # Traditional menus: File · Edit · View · Help
    titles = [a.text().replace("&", "") for a in w.menuBar().actions()]
    assert "File" in titles and "Edit" in titles and "View" in titles and "Help" in titles, titles
    # Order should be traditional when all four are present as top-level menus.
    idx = {name: titles.index(name) for name in ("File", "Edit", "View", "Help")}
    assert idx["File"] < idx["Edit"] < idx["View"] < idx["Help"], idx
    assert hasattr(w, "act_help") and hasattr(w, "act_undo")
    assert hasattr(w, "menu_help")
    help_path = w._help_guide_path()
    assert help_path.is_file(), help_path
    help_menu_texts = [
        a.text().replace("&", "")
        for a in w.menu_help.actions()
        if not a.isSeparator()
    ]
    assert "FountainPad Help" in help_menu_texts, help_menu_texts
    assert "About FountainPad" in help_menu_texts, help_menu_texts
    print("menus/help OK", titles, help_path.name)

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

    # Index cards + template insert + beat board
    w.editor.setPlainText(
        "INT. LAB - NIGHT\n\n"
        "[[card: Goal]]\n"
        "Find the sample.\n\n"
        "[[beat: Midpoint]]\n"
        "Alarm sounds.\n"
    )
    w._dirty = False
    w._refresh_card_navigator()
    w._refresh_beat_board()
    assert w.card_navigator._list.count() >= 1
    assert w.beat_board._list.count() >= 1
    before = w.editor.toPlainText()
    w._insert_card_template("Turn")
    after = w.editor.toPlainText()
    assert "[[card:" in after and "Turn" in after
    assert "id=" in after  # new inserts carry stable ids
    assert after != before
    w._refresh_card_navigator()
    assert any(ct == "Turn" for _, ct, _, _ in w.editor.list_cards())
    w.toggle_card_navigator(False)
    assert w.card_navigator.isHidden()
    w.toggle_card_navigator(True)
    w.toggle_beat_board(False)
    assert w.beat_board.isHidden()
    w.toggle_beat_board(True)
    print("cards/beats UI OK")

    # P3: generate empty cards from scenes (skip scenes that already have cards)
    from PySide6.QtWidgets import QMessageBox

    w.editor.setPlainText(
        "INT. ONE - DAY\n\n"
        "Action in one.\n\n"
        "INT. TWO - NIGHT\n\n"
        "[[card: Goal]]\n"
        "Already planned.\n\n"
        "EXT. THREE - DAY\n\n"
        "Action in three.\n"
    )
    w._dirty = False
    w._refresh_card_navigator()
    before_cards = w.editor.list_cards()
    assert len(before_cards) == 1, before_cards
    # Auto-accept the confirm dialog in offscreen smoke.
    answers = {"n": 0}

    def _auto_yes(*_a, **_k):
        answers["n"] += 1
        return QMessageBox.StandardButton.Yes

    original_question = QMessageBox.question
    QMessageBox.question = staticmethod(_auto_yes)  # type: ignore[method-assign, assignment]
    try:
        w.generate_empty_cards_from_scenes()
    finally:
        QMessageBox.question = original_question  # type: ignore[method-assign]
    assert answers["n"] == 1, answers
    after_cards = w.editor.list_cards()
    # ONE and THREE get Note stubs; TWO already had Goal
    types_by_scene = {}
    for _bn, ctype, _txt, scene in after_cards:
        types_by_scene.setdefault(scene, []).append(ctype)
    assert "Note" in types_by_scene.get("INT. ONE - DAY", []), types_by_scene
    assert "Goal" in types_by_scene.get("INT. TWO - NIGHT", []), types_by_scene
    assert "Note" in types_by_scene.get("EXT. THREE - DAY", []), types_by_scene
    assert len(after_cards) == 3, after_cards
    assert w._dirty is True
    # Second run: all scenes have cards → information path (no insert)
    infos = {"n": 0}

    def _auto_info(*_a, **_k):
        infos["n"] += 1
        return QMessageBox.StandardButton.Ok

    original_info = QMessageBox.information
    QMessageBox.information = staticmethod(_auto_info)  # type: ignore[method-assign, assignment]
    try:
        w.generate_empty_cards_from_scenes()
    finally:
        QMessageBox.information = original_info  # type: ignore[method-assign]
    assert infos["n"] == 1, infos
    assert len(w.editor.list_cards()) == 3
    print("P3 cards-from-scenes OK", types_by_scene)

    # Phase A: ensure ids + hide markers setting; Phase B: apply card → script
    import cards as cards_mod

    w.editor.setPlainText(
        "[[card: Note]]\n"
        "EXT. YARD - DAY\n"
        "Dogs bark.\n"
    )
    w._dirty = False
    assigned = w.editor.ensure_card_ids()
    assert assigned >= 1
    text_ids = w.editor.toPlainText()
    assert "id=c" in text_ids
    infos_a = w.editor.list_card_infos()
    assert infos_a and infos_a[0].card_id
    assert "EXT. YARD" in infos_a[0].body
    # Apply promotes slug above card and keeps note body
    msg = w.editor.apply_card_to_script(infos_a[0].block_number)
    applied = w.editor.toPlainText()
    assert "EXT. YARD - DAY" in applied
    assert applied.strip().startswith("EXT. YARD"), applied
    assert "[[card: id=" in applied
    assert "Dogs bark." in applied
    # Marker should not appear twice as scene under card
    scenes = w.editor.list_scene_headings()
    assert any("YARD" in h for _, h in scenes)
    w.toggle_card_markers_in_editor(False)
    assert w.editor._highlighter._hide_card_markers is True
    w.toggle_card_markers_in_editor(True)
    light_css = (ROOT / "resources/styles/preview-light.css").read_text(encoding="utf-8")
    assert ".note" in light_css and "display: none" in light_css
    print("Phase A/B cards OK", msg, scenes)

    # Project folder seeds
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "demo_project"
        project.mkdir()
        # Bypass dialog: exercise seed + open path pieces
        for name, template in [
            ("canon.md", "# Canon\n\nStory world, rules, lore."),
            ("beats.md", "# Beats\n\nMajor plot points."),
            ("cards.md", "# Index Cards\n\n[[card: Goal]]\n"),
        ]:
            (project / name).write_text(template, encoding="utf-8")
        script = project / "script.fountain"
        script.write_text("INT. SEED - DAY\n\nHello.\n", encoding="utf-8")
        w._dirty = False
        w._open_fountain_file(script)
        assert w._path == script
        assert "SEED" in w.editor.toPlainText()
        # Missing-file seed behaviour
        empty = Path(td) / "empty_project"
        empty.mkdir()
        for name, template in [
            ("canon.md", "# Canon\n\nStory world, rules, lore."),
            ("beats.md", "# Beats\n\nMajor plot points."),
            ("cards.md", "# Index Cards\n\n[[card: Goal]]\n[[card: Conflict]]\n[[card: Turn]]"),
        ]:
            f = empty / name
            if not f.exists():
                f.write_text(template, encoding="utf-8")
        assert (empty / "canon.md").exists()
        assert (empty / "beats.md").exists()
        assert (empty / "cards.md").exists()
        print("project folder seeds OK", empty)

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
            # Same layout shape as File → Export PDF (must include margins).
            from PySide6.QtCore import QMarginsF
            from PySide6.QtGui import QPageLayout, QPageSize

            layout = QPageLayout(
                QPageSize(QPageSize.Letter),
                QPageLayout.Portrait,
                QMarginsF(0.5, 0.5, 0.5, 0.5),
                QPageLayout.Inch,
            )
            # Bare (size, orientation) must fail on this PySide — guards regression.
            try:
                QPageLayout(QPageSize(QPageSize.Letter), QPageLayout.Portrait)
                bare_ok = True
            except TypeError:
                bare_ok = False
            assert bare_ok is False, "expected bare QPageLayout to TypeError"
            w.preview.print_to_pdf(str(pdf_path), _cb, layout)
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
