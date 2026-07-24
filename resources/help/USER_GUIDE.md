# FountainPad — User Guide

**Last updated:** 2026-07-24 (P3 empty cards from scenes)  
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
| **Generate Empty Cards from Scenes…** | **Partial (P3).** Optional empty `[[card: Note]]` stubs under scenes that do not already have a card. Confirm dialog first. Notes to the draft — not instructions. Same action as the **From scenes** button on the Index Cards panel. |

### View

| Command | What it does |
|---|---|
| **Show Scene Navigator** | Toggle the left scene list. Click a scene to jump. Filter box narrows the list. |
| **Show Index Cards** | Toggle the index-cards panel. **Partial** — see [Index cards](#index-cards-partial) below. |
| **Show Beat Board** | Toggle the beat list panel. **Partial** — see [Beat board](#beat-board-partial) below. |
| **Show Split Preview** | Show/hide the **in-window** preview pane only. Independent of a detached window. |
| **Detach Preview Window** | Open a **second** live preview in its own window. Does not remove the split preview. If already detached, focuses that window. |
| **Reattach Preview** | Close the floating preview **and** turn the split preview **on** so you are not left without a preview. |
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

- Markers in the script of the form:

  ```fountain
  [[card: Goal]]
  Optional body line under the marker.

  [[card: Conflict]]
  Something goes wrong.

  [[card: Turn]]
  ```

- The **Index Cards** panel lists those markers, linked to the nearest scene heading above them.
- **Goal / Conflict / Turn** buttons insert a template marker at the cursor.
- **From scenes** (panel) or **Edit → Generate Empty Cards from Scenes…** inserts one empty `[[card: Note]]` under each scene that has **no** card yet. Scenes that already have a card are skipped. You get a confirm dialog first.
- Click a card in the list to jump to it.
- Filter box narrows by type, text, or scene.

### What is *not* finished

- Cards are **markers inside the Fountain file**, not a separate visual card canvas.
- No drag-to-reorder scenes from cards yet.
- No rich per-card fields UI (goal/conflict/turn are insert helpers, not a form).
- Project `cards.md` is only a **seed file** on disk — not a live two-way pack editor inside the app.
- One card per marker line; body is a simple following line, not a full freeform card face.
- “From scenes” does **not** invent summaries — stubs are empty notes for you to fill (or ignore).

### How you are meant to use it (for now)

While drafting, drop `[[card: …]]` notes near scenes as planning breadcrumbs. Use **From scenes** when you want a blank note under each slugline without typing markers by hand. Use the panel to jump. These are **notes toward the draft**, not a forced outline the script must obey. Treat this as a bridge toward a fuller cards workflow, not the final design.

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
| — | Generate empty cards from scenes (Edit menu / Index Cards → From scenes) |
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
