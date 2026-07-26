# FountainPad — User Guide

**Last updated:** 2026-07-26 (C7 markdown card/beat pack sync)  
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
| **Open Project Folder…** | **Partial.** Choose a folder. FountainPad creates missing `canon.md`, `beats.md`, and `cards.md` starter files, and opens `script.fountain` if that file exists. This is *not* a full multi-document binder yet. Use **Export/Import Card Pack** (and Beat Pack) to sync those markdown files with the script. |
| **Close** | Closes the current buffer (save prompt if needed). Does **not** quit the app. Leaves an empty untitled document. |
| **Save** / **Save As…** | Save the current editor text as UTF-8 `.fountain`. |
| **Export PDF…** | Exports the **formatted preview** as a PDF (Letter). Forces a light print look for readability. Fountain `[[notes]]` are hidden in the PDF via print CSS. |
| **Export Card Pack…** | **C7.** Writes a `cards.md` markdown pack from every `[[card:]]` in the script (ids, types, versions, scene groups). Default path is beside the open `.fountain`. Shortcut: Ctrl/Cmd+Shift+M. |
| **Import Card Pack…** | **C7.** Merges a `cards.md` pack into the open script: matching `id=` updates the card body/versions; new ids insert under their `## Scene:` heading when that scene exists. Dialogue is not rewritten. Confirm first. |
| **Export Beat Pack…** | **C7.** Writes `beats.md` from `[[beat:]]` markers. |
| **Import Beat Pack…** | **C7.** Merges `beats.md` by beat label (update note or insert). Confirm first. |
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
| **Move Card Scene Up / Down** | **Partial (Phase C).** Moves the **whole scene** owned by the selected card. **Scene ↑** / **Scene ↓**, Ctrl/Cmd+Alt+Up/Down, or **drag a card** in the Index Cards list. Card markers and dialogue travel with the scene. |

### View

| Command | What it does |
|---|---|
| **Show Scene Navigator** | Toggle the left scene list. Click a scene to jump. Filter box narrows the list. |
| **Show Index Cards** | Toggle the index-cards panel. **Partial** — see [Index cards](#index-cards-partial) below. |
| **Show Beat Board** | Toggle the beat list panel. **Partial** — see [Beat board](#beat-board-partial) below. |
| **Show Split Preview** | Show/hide the **in-window** preview pane only. Independent of a detached window. |
| **Detach Preview Window** | Open a **second** live preview in its own window. Does not remove the split preview. If already detached, focuses that window. |
| **Reattach Preview** | Close the floating preview **and** turn the split preview **on** so you are not left without a preview. |
| **Show Card Markers in Editor** | When **on** (default), `[[card: …]]` lines are easy to see in the source. When **off**, those lines are **dimmed** in the editor only (still saved). Card/beat markers, card bodies, and `@vN` version lines are **removed** from the formatted **preview** and **PDF** (not just dimmed). |
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

- **Editable card on the left:** select a card → type in the detail pane. **Text auto-saves** into the card in the Fountain file (no separate Save button required). Status line under the editor says when it is saving.
- **Narrow panel layout:** buttons sit on **two rows**; card list labels are **multi-line** (id · type, then slug, then first note line) and wrap so a thin cards column stays readable.
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

  Single-version cards stay simple (no `@vN` until you create a second version). Those `@vN` lines are **source-only** — they do **not** appear in preview/PDF.

- **Panel buttons:**
  - **Goal / Conflict / Turn** — insert a new card at the cursor.
  - **From scenes** — empty stubs under scenes that have no card yet.
  - **Apply → script** — flush any pending typing, then push the **active** version to the page.
  - **New version** — keep the old text as history and start `v2`, `v3`, …
  - **Scene ↑ / Scene ↓** — move the card’s whole scene earlier/later (same as drag-drop).
  - **Drag a card** in the list — drop near another card to place this card’s scene there.
- **History (versions):**
  - List shows prior snapshots; **Show in editor** loads one into the text box (then auto-saves as active text if you leave it).
  - **Use this version** (or double-click) makes that history entry the **active** version.
- **Apply rules (important):** updates **scene heading** + **leading action** only. **Character cues and dialogue are never modified.** You can still edit anything in the script afterward.
- Click a card to jump the script; filter by id/type/text/scene.

### Drag / reorder rules

- Drag targets the **scene** of the card (not a free corkboard).
- Dropping among cards that share one scene does nothing.
- Cards without a parent scene cannot drag-reorder until they sit under a heading (or you Apply a draft slug).
- Multi-card scenes: moving one card moves the **whole shared scene** (all cards in that scene travel together).

### What is *not* finished

- No separate visual corkboard; live planning storage is still inside the Fountain file (markdown packs are an export/import bridge).
- Apply does not rewrite dialogue (by design) and does not replace a whole scene body.
- Pack sync is **explicit** (File menu) — not auto-watch / silent background sync.
- Version UI is primitive (no timestamps/authors).

### How you are meant to use it (for now) — cards first

1. Capture / edit the idea **on the left** (first line can be `INT.`/`EXT.` …; rest = action notes). Typing **auto-saves** to the card.  
2. **New version** when you want a progress snapshot.  
3. **Apply → script** when you want that active version’s slug + action on the page (dialogue stays yours).  
4. To roll back an idea: **Use this version** on an older history row → **Apply → script** again.  
5. **Scene ↑** / **Scene ↓**, or **drag the card** in the list, moves that card’s **scene block** in the script.  
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
- Beat pack sync is label-based (not stable beat ids yet).

### How you are meant to use it (for now)

Mark major plot turns in the script text and jump via the list. Use **Export/Import Beat Pack** when you want a `beats.md` file beside the project. Expect a richer board later if we build one.

---

## Card & beat packs (C7)

**Status:** Available (explicit export/import)

The **screenplay source of truth** is still the `.fountain` file. Markdown packs are a portable bridge for notes, OpenClaw folders, and git diffs.

### Card pack (`cards.md`)

**File → Export Card Pack…** writes something like:

```markdown
# Index Cards

## Scene: INT. BAY - NIGHT

[[card: id=c001 | Goal | active=v2]]
@v1
Old plan.
@v2
Driver checks the seal.
```

**File → Import Card Pack…**

1. Opens a `.md` file (defaults to `cards.md` next to the script).
2. Asks before merging.
3. Updates cards with the same `id=`; inserts new ones under the matching scene when possible.
4. Does **not** rewrite dialogue or non-card action.

### Beat pack (`beats.md`)

Same idea for `[[beat: Label]]` markers — export the list, edit in markdown if you like, import to update notes or add labels.

### How to use it

1. Plan in the Index Cards panel (or in the script).  
2. **Export Card Pack** when you want a markdown snapshot beside the project.  
3. Edit `cards.md` externally if needed (keep the `[[card: id=…]]` markers).  
4. **Import Card Pack** to pull changes back.  
5. Still **Save** the `.fountain` to keep the draft.

---

## Project folder (Partial)

**Status:** Partial

**File → Open Project Folder…**

1. Pick a folder.  
2. If missing, FountainPad creates:

   - `canon.md` — story world / rules notes  
   - `beats.md` — beat notes (seed; use Export/Import Beat Pack for live content)  
   - `cards.md` — card notes (seed; use Export/Import Card Pack for live content)  
   - and opens `script.fountain` **if it already exists**

3. If there is no `script.fountain`, you get a message that the folder was opened / seeded — you still work in the editor as a normal Fountain file until you create/open one.

**Not yet:** multi-tab binder, docked editors for canon/beats/cards, or auto-watch sync on every keystroke.

**How to use it now:** folder convention for a screenwriting project; keep the draft in `script.fountain` and sync packs on purpose via the File menu.

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
| Ctrl/Cmd+Shift+M | Export Card Pack |
| — | Import Card Pack / Export·Import Beat Pack (File menu) |
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
