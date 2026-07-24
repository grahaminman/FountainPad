# FountainPad — User Guide

**Last updated:** 2026-07-24 (card scene reorder Up/Down)  
**Audience:** someone using the app (not building it)  
**Honesty rule:** features marked **Partial** work today but are not finished products. If something feels unclear, that is a real UX signal — this guide should explain what to expect.

---

## What FountainPad is

FountainPad is a desktop **Fountain** screenplay editor:

- You write plain-text `.fountain` on the left (and centre).
- A formatted **preview** shows how the page looks (via bundled fountain.js).
- Side panels help you jump around scenes, cards, and beats.
- Everything is meant to stay **offline-friendly** — no account required.

Fountain is a plain-text screenplay format. Learn more at [fountain.io](https://fountain.io).

---

## The window layout

From left to right (when all panels are shown):

1. **Scene Navigator** — list of scene headings  
2. **Index Cards** — list of `[[card: …]]` markers in the script  
3. **Editor** — your Fountain source  
4. **Split Preview** (optional) — formatted page beside the editor  
5. **Beat Board** — list of `[[beat: …]]` markers  

You can hide any side panel or the split preview from the **View** menu.  
There is also an optional **floating preview window** (detached).

---

## Menus (traditional layout)

### File

| Command | What it does |
|---|---|
| **New** | Starts a new screenplay. First launch / New may show a short sample; after **Close**, New is an empty untitled buffer (you will be asked to save if the current file is dirty). |
| **Open…** | Open a `.fountain` (or text) file. |
| **Open Project Folder…** | **Partial.** Choose a folder. FountainPad creates missing `canon.md`, `beats.md`, and `cards.md` starter files, and opens `script.fountain` if that file exists. This is *not* a full multi-document binder yet — those markdown files are not edited inside the app in a special UI. |
| **Close** | Closes the current buffer (save prompt if needed). Does **not** quit the app. Leaves an empty untitled document. |
| **Save** / **Save As…** | Save the current editor text as UTF-8 `.fountain`. |
| **Export PDF…** | Exports the **formatted preview** as a PDF (Letter). Forces a light print look for readability. Fountain `[[notes]]` are hidden in the PDF via print CSS. |
| **Quit** | Exit the app (save prompt if dirty). |

### Edit

Standard text editing against the **source editor** (not the preview):

| Command | Notes |
|---|---|
| Undo / Redo | Editor history |
| Cut / Copy / Paste | Clipboard |
| Select All | Select all source text |
| **Generate Empty Cards from Scenes…** | **Partial (P3).** Optional empty card stubs under scenes with no card yet. Confirm first. Same as **From scenes** on the Index Cards panel. |
| **Apply Card to Script** | **Partial.** Pushes the **active card version** into the screenplay: scene heading + **leading action only**. **Dialogue is never changed.** Explicit action — not a silent compile. Ctrl/Cmd+Shift+A. |
| **Ensure Card IDs** | Assign stable `id=cNNN` on markers that do not have one yet. |
| **Move Card Scene Up / Down** | **Partial (Phase C).** Moves the **whole scene** owned by the selected card (heading through the line before the next scene). Card markers and dialogue in that scene travel with it. Index Cards **Up** / **Down**, or Ctrl/Cmd+Alt+Up/Down. |

### View

| Command | What it does |
|---|---|
| **Show Scene Navigator** | Toggle the left scene list. Click a scene to jump. Filter box narrows the list. |
| **Show Index Cards** | Toggle the index-cards panel. **Partial** — see [Index cards](#index-cards-partial) below. |
| **Show Beat Board** | Toggle the beat list panel. **Partial** — see [Beat board](#beat-board-partial) below. |
| **Show Split Preview** | Show/hide the **in-window** preview pane only. Independent of a detached window. |
| **Detach Preview Window** | Open a **second** live preview in its own window. Does not remove the split preview. If already detached, focuses that window. |
| **Reattach Preview** | Close the floating preview **and** turn the split preview **on** so you are not left without a preview. |
| **Show Card Markers in Editor** | When **on** (default), `[[card: …]]` lines are easy to see in the source. When **off**, those lines are **dimmed** in the editor only (still saved). Card/note markers **never** show in the formatted **preview** or **PDF**. |
| **Dark Mode** | Toggle dark theme for editor chrome and preview. |

### Help

| Command | What it does |
|---|---|
| **FountainPad Help** | Opens this guide inside the app (Help → FountainPad Help, or **F1**). |
| **About FountainPad** | Short credits / stack blurb. |

---

## Writing Fountain (basics)

FountainPad highlights common Fountain elements:

- **Scene headings** — lines like `INT. KITCHEN - DAY` or `EXT. STREET - NIGHT`
- **Character cues** — typically `NAME` alone on a line before dialogue
- **Dialogue** and **parentheticals**
- **Transitions** — e.g. `CUT TO:`
- **Sections** — `#` / `##` style (Fountain sections)
- **Notes** — `[[like this]]` (also used for cards/beats — see below)
- **Title page** keys at the top — `Title:`, `Author:`, etc.

The preview updates shortly after you stop typing (debounced).  
If the split preview is hidden, the editor uses full width (word wrap off for long lines is intentional when preview is closed).

---

## Scene Navigator

**Status:** Available

- Lists `INT.` / `EXT.` / related scene headings in document order.
- **Filter** box: type to narrow the list.
- **Click** a row to jump the editor there and centre the line.
- Status bar shows the **current scene** under the cursor (walks upward to the nearest heading).

**How to use it:** outline navigation while writing pages — jump without scrolling.

---

## Index cards (Partial)

**Status:** Partial — useful now, not a full Final Draft–style card pack yet.

### What works today

- **Editable card on the left:** select a card → edit type and full text in the **Card detail** pane (not only in the script).
- Markers in the Fountain file (stable ids + optional versions):

  ```fountain
  [[card: id=c001 | Note | active=v2]]
  @v1
  EXT. YARD - DAY
  Dogs bark.
  @v2
  EXT. YARD - DUSK
  Dogs go quiet.
  ```

  Single-version cards stay simple (no `@vN` until you save a second version).

- **Versions (primitive progress):**
  - **Save** — write editor text into the **active** version.
  - **Save ver** — if the text changed, append a **new** version and make it active (keeps older ones).
  - Version list shows history; **Load** puts an old version in the editor; **Make top** (or double-click) sets that version as active.
  - **Apply** snapshots changed text if needed, then pushes the **active** version to the script.
- **Apply rules (important):** updates **scene heading** + **leading action** only. **Character cues and dialogue are never modified.** You can still edit anything in the script afterward.
- **Goal / Conflict / Turn**, **From scenes**, stable ids, preview/PDF hide markers, editor dim toggle — as before.
- Click a card to jump the script; filter by id/type/text/scene.

### What is *not* finished

- **Drag-and-drop reorder** — not yet; use **Up** / **Down** for now.
- Multi-card scenes: moving one card moves the **whole shared scene** (all cards in that scene travel together).
- No separate visual corkboard; storage is still inside the Fountain file.
- Apply does not rewrite dialogue (by design) and does not replace a whole scene body.
- Project `cards.md` is still only a seed file (not live pack sync).
- Version UI is primitive (no timestamps/authors).

### How you are meant to use it (for now) — cards first

1. Capture / edit the idea **on the left** (first line can be `INT.`/`EXT.` …; rest = action notes).  
2. **Save ver** when you want a progress snapshot.  
3. **Apply** when you want that active version’s slug + action on the page (dialogue stays yours).  
4. To roll back an idea: **Make top** on an older version → **Apply** again (or copy from the version tooltip/editor).  
5. **Up** / **Down** on a card moves that card’s **scene block** in the script (not just the list row).  
6. Keep writing dialogue and pages freely in the script.

These are **notes toward the draft**, not instructions the script must obey.

---

## Beat board (Partial)

**Status:** Partial — **list**, not a freeform board.

### What works today

- Markers:

  ```fountain
  [[beat: Act 1 Climax]]
  Optional note on the next line.
  ```

- The **Beat Board** panel lists them with filter + click-to-jump.
- Labels are freeform (`Midpoint`, `Act 2 Break`, etc.).

### What is *not* finished

- Not a spatial / drag canvas (Final Draft Beat Board style).
- No linking UI from beat → multiple scenes beyond “nearest scene above marker”.
- Project `beats.md` is a seed file only.

### How you are meant to use it (for now)

Mark major plot turns in the script text and jump via the list. Expect a richer board later if we build one.

---

## Project folder (Partial)

**Status:** Partial

**File → Open Project Folder…**

1. Pick a folder.  
2. If missing, FountainPad creates:

   - `canon.md` — story world / rules notes  
   - `beats.md` — beat notes  
   - `cards.md` — card notes  
   - and opens `script.fountain` **if it already exists**

3. If there is no `script.fountain`, you get a message that the folder was opened / seeded — you still work in the editor as a normal Fountain file until you create/open one.

**Not yet:** multi-tab binder, editing canon/beats/cards as docked documents, auto-sync between panel cards and `cards.md`.

**How to use it now:** a convenient folder convention aligned with a future screenwriting workflow — keep notes beside the script on disk.

---

## Preview & PDF

### Split preview

- **View → Show Split Preview** (or toolbar): in-window formatted page.
- Updates live while you type (short delay).
- Independent of the detached window.

### Detach / reattach

- **Detach** = second window with its own live preview.  
- **Reattach** = close float **and** force split preview on.  
- Closing the float with the window **X** keeps your split on/off preference (does not force split on).

### Export PDF

- **File → Export PDF…**
- Uses the preview engine; Letter page; light appearance for print.
- **Notes** (`[[…]]` that render as notes) are **hidden in PDF** so planning markers do not clutter the page.
- If export fails, try ensuring the preview has loaded (show split preview once).

---

## Dark mode

**View → Dark Mode** toggles editor, panels, and preview theme. Preference is remembered next launch.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Ctrl/Cmd+N | New |
| Ctrl/Cmd+O | Open |
| Ctrl/Cmd+Shift+O | Open project folder |
| Ctrl/Cmd+W | Close |
| Ctrl/Cmd+S | Save |
| Ctrl/Cmd+Shift+S | Save As |
| Ctrl/Cmd+Shift+E | Export PDF |
| Ctrl/Cmd+Z / Ctrl/Cmd+Shift+Z (platform) | Undo / Redo |
| Ctrl/Cmd+X / C / V | Cut / Copy / Paste |
| Ctrl/Cmd+A | Select All |
| — | Generate empty cards from scenes (Edit / From scenes) |
| Ctrl/Cmd+Shift+A | Apply selected card to script |
| — | Ensure card ids (Edit menu) |
| Ctrl/Cmd+\\ | Scene navigator |
| Ctrl/Cmd+Shift+C | Index cards |
| Ctrl/Cmd+Shift+B | Beat board |
| Ctrl/Cmd+P | Split preview |
| Ctrl/Cmd+Shift+P | Detach preview |
| Ctrl/Cmd+Alt+P | Reattach preview |
| Ctrl/Cmd+D | Dark mode |
| F1 | This help |
| Ctrl/Cmd+Q | Quit |

*(On macOS, use Cmd where the system uses the Command key.)*

---

## Status bar

- **Scene:** nearest scene heading above the cursor  
- **Counts:** characters and words in the whole document  

---

## What is remembered between sessions

Window size, panel widths, which panels were visible, dark mode, and split-preview on/off are stored locally for this user account (app settings). They are not stored inside your `.fountain` file.

---

## If something feels unfinished

You are not missing a secret mode. Several features are **intentionally partial** while FountainPad grows:

| Area | Today | Direction (not a promise of date) |
|---|---|---|
| Index cards | Markers + list + templates | Richer cards / markdown pack / reorder |
| Beat board | Linear list | Possible true board later |
| Project folder | Seed files + open script | Binder / side docs |
| Distribution | Run from Python source | Packaged app for non-technical writers |

This Help file should be updated whenever behaviour changes. If the UI and this guide disagree, trust the UI and treat the guide as needing an update.

---

## About the technology (short)

- Python 3 + PySide6 (Qt)  
- Preview: bundled **fountain.js** (Matt Daly, MIT)  
- No network required for normal editing/preview  

---

*End of user guide.*
