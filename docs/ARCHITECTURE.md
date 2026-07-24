# FountainPad — architecture (developer)

**Audience:** anyone editing this codebase (including future-you / OpenClaw agents).  
**Locale:** en_GB  
**Updated:** 2026-07-23

## What it is

Desktop Fountain screenplay editor: plain-text source on the left, formatted preview via bundled **fountain.js**, optional scene navigator, PDF export. Stack: **Python 3 + PySide6 + Qt WebEngine**.

## Module map

| File | Role |
|---|---|
| `main.py` | Entry; set OpenGL-share attr → `QApplication` → `MainWindow` |
| `mainwindow.py` | Shell: menus, splitters, file ops, preview modes, PDF, project folder, settings |
| `editor.py` | `FountainEditor` + `FountainHighlighter` + scene / `list_cards` / `list_beats` helpers |
| `navigator.py` | Scene list + filter + jump signal |
| `cardnavigator.py` | Index cards list + Goal/Conflict/Turn template buttons + jump |
| `beatboard.py` | Beat list (linear) + filter + jump — not freeform canvas |
| `preview.py` | `FountainPreview` (WebEngine) + `PreviewWindow` + `print_to_pdf` |
| `resources/preview.html` | Offline HTML shell; JS API `setTheme` / `renderFountain` |
| `resources/fountain.js` | Matt Daly parser (MIT) — treat as vendor |
| `resources/styles/` | Light/dark CSS; print media hides `.note` when F5 CSS committed |
| `_smoke_test.py` | Regression checks — **fix working-tree rewrite if broken; prefer offscreen script** |
| `docs/` | Product planning (distribution, upgrade backlog) — not runtime |

## Layout (runtime)

```text
┌──────────────┬────────────────────────────┬─────────────────────┐
│ Scene nav    │ FountainEditor             │ FountainPreview     │
│ (optional)   │                            │ (split, optional)   │
└──────────────┴────────────────────────────┴─────────────────────┘
                              │
                              └── optional PreviewWindow (detached)
                                    own FountainPreview instance
```

Outer splitter: nav | (editor+preview). Inner splitter: editor | embedded preview.

## Preview modes (do not confuse)

| Action | What it does |
|---|---|
| **Show Split Preview** | Show/hide *embedded* right pane only |
| **Detach Preview Window** | Open *second* floating preview; does **not** destroy split |
| **Reattach Preview** | Close floating window **and** force split preview **on** |
| Close floating window (X) | Clears detach; leaves split preference as-is |

Both previews stay content-synced via `MainWindow._sync_previews()`.

## File lifecycle

- **New:** empty buffer (first launch only loads sample `DEFAULT_FOUNTAIN`)
- **Open / Save / Save As:** UTF-8 `.fountain`
- **Close:** prompt if dirty → empty untitled buffer (does not quit)
- **Quit / window close:** prompt if dirty → save settings → close detach

Dirty flag: any editor `contentChanged` after load/save/new/close.

## PDF

`File → Export PDF` → force light theme on a live `FountainPreview` → short timer → `QWebEnginePage.printToPdf` (Letter). Restores UI theme after.

## Settings (`QSettings` org/app FountainPad)

geometry, windowState, splitterSizes, editorPreviewSizes, darkMode, splitVisible, navVisible.

Splitter hide/show remembers non-zero widths so panes do not reopen at 0px.

## Smoke test

```bash
source .venv/bin/activate
python _smoke_test.py
```

## Known product gaps (not bugs)

See `docs/UPGRADE_BACKLOG.md`.

- Packaged AppImage / no-terminal distribution: **held**
- Phase 1 F5 (hide notes in print): implemented in working tree CSS; commit if still dirty
- Phase 2 shipped partial (2026-07-23 `c969fdf`): cards list, beat list, project folder seeds — not full FD cards/board or markdown pack sync
- Smoke test: restore reliable offscreen runner before relying on it
