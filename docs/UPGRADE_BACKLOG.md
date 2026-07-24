# FountainPad — upgrade backlog (pipeline + industry + forums)

**Captured:** 2026-07-21  
**Status:** Research / ideas only — not a build commitment  
**Locale:** en_GB  
**App today:** Python 3 + PySide6 + bundled fountain.js — focused Fountain editor + live preview (see root README)

---

## 1. Why this list exists

Two inputs:

1. **Our AI screenplay process** (designed + planned; factory not fully executed yet)  
   - `projects/screenwriting/SCREENWRITING_OS_DESIGN.md`  
   - `projects/screenwriting/CONVERSATION_LEDGER.md`  
   - Creative OS private templates; hero project **Cash In Transit** planned  
   - Stages: idea → lock canon → beats → **cards** → pages → pressure/revise → assemble → continuity  

2. **What writers already pay for / ask for**  
   - Final Draft: Beat Board, Index Cards, Outline Editor, Navigator, Revision Mode  
   - WriterDuet: cards view, mind map, outline/sequences, collab  
   - Fade In: solid Fountain import/export, lighter cards  
   - Highland: Fountain-native, minimalist, focus tools, share-for-notes (Fling)  
   - r/Screenwriting: demand for a **solid cross-platform Fountain app** (esp. Windows), scene nav, outline tied to Fountain, export without FD tax  

FountainPad’s wedge: stay **Fountain-first, offline-friendly, writer-simple** — steal *workflows*, not bloat. Optional AI stays **file/agent-shaped** (OpenClaw), not a locked SaaS brain inside the editor unless Graham chooses that later.

---

## 2. Our pipeline → editor features map

```text
IMPORT / LOCK canon     → project binder, title page, constraints notes pane
PLAN beats / sequences  → beat board + outline lanes
CARDS                   → index card pack (bidirectional with scenes)
PAGES (Fountain)        → current core editor + preview  ✅ already
PRESSURE / revise       → notes, issues panel, revision marks, compare
ASSEMBLE                → multi-file project, export PDF/FDX, scene order
CONTINUITY              → characters/locations lists, “last seen” from script parse
AI factory (OpenClaw)   → open folder, watch files, send slice to agent, accept patch
```

| Pipeline need | FountainPad upgrade idea | Priority guess |
|---|---|---|
| Scene cards before pages | **Card pack / index cards** synced to `INT./EXT.` scenes | **P0** |
| Beats / sequences | Beat board or lighter “sequence strip” | **P0–P1** |
| Canon / constraints visible while writing | Side panel: logline, must-hits, open questions (markdown) | **P1** |
| One CURRENT draft | Project mode: binder + “current” fountain file | **P1** |
| Specialist pressure notes | Inline `[[notes]]` + Issues dock (import from report md) | **P1** |
| Continuity | Auto character/location index from parse; jump-to | **P1** |
| Assemble | Concat scenes / sections; PDF print; optional FDX export | **P1** |
| Cold-start / status | Read-only STATUS.md strip or project dashboard | **P2** |
| AI co-writer | “Send selection/scene to agent” + apply diff; no mandatory cloud | **P2** |
| Non-technical users | Packaged app (see `DISTRIBUTION_NO_TERMINAL.md`) | **P0 product** |

---

## 3. Feature backlog (detailed)

### UX / docs hygiene (standing)
- [x] Traditional menu bar **File · Edit · View · Help** (2026-07-24)
- [x] In-app Help → `resources/help/USER_GUIDE.md` (living; update with features)
- [x] Local `build-notes/` gitignored (process ledger off GitHub)
- [ ] Keep USER_GUIDE honest as cards/beats/project mature

### A. Distribution & trust (product)

| ID | Feature | Notes | Source |
|---|---|---|---|
| D1 | **Packaged builds** (Mac/Win/Linux) | Double-click; no Terminal | Graham audience |
| D2 | Code signing / notarisation path | Reduces Gatekeeper/SmartScreen fear | Industry baseline |
| D3 | One-click sample `.fountain` | First-run less blank-page terror | UX |
| D4 | Plain-language “For writers” README | Separate from dev install | Forums: Fountain opportunity |

### B. Navigation & structure (every pro app has this)

| ID | Feature | Notes | Source |
|---|---|---|---|
| N1 | **Scene navigator** | List of scene headings; click → jump; filter INT/EXT/time | **DONE 2026-07-23** (list + filter + jump; View toggle) |
| N2 | This-scene / this-character stats | Extend status bar | Highland-ish / FD |
| N3 | Go to scene / character palette | Cmd/Ctrl+P style | General editor UX |
| N4 | Section/`#` outline tree | Fountain sections as binder | Fountain native |
| N5 | Page count estimate in preview | Writers obsess over pages | Universal |

### C. Cards & boards (explicit Graham ask + FD/WriterDuet)

| ID | Feature | Notes | Source |
|---|---|---|---|
| C1 | **Index card view** | One card per scene: slugline + summary side + optional script peek | **DONE 2026-07-23** (inline `[[card: Type]]` list + filter + jump; View toggle) |
| C2 | Drag reorder cards → reorder scenes in Fountain | Hard but high value; careful with dual dialogue/notes | FD / WriterDuet |
| C3 | Color tags (plot A/B, POV, day/night) | Metadata in Fountain notes or sidecar JSON | FD Beat Board habits |
| C4 | **Beat board** (freeform canvas) | Beats not 1:1 scenes; link beat → scene(s) | **Partial 2026-07-23** — linear list of `[[beat: …]]` + jump (not freeform canvas) |
| C5 | Outline lane (linear) | Horizontal/vertical sequence of beats; lighter than full board | FD Outline Editor — list UI is a first step via C4 partial |
| C6 | Card templates | Goal / conflict / turn / image / “must hit” fields | **Partial 2026-07-23** — Goal/Conflict/Turn insert buttons in CardNavigator |
| C7 | Import/export cards as Markdown | Matches OpenClaw `cards/` folder grammar | **Partial 2026-07-23** — project folder seeds `cards.md`; full bidirectional pack still open |
| C8 | Mind-map lite | Optional links between cards — don’t boil ocean v1 | WriterDuet |

**Shipped v1 cards (2026-07-23 evening):** C1 list + jump, C6 template buttons, C4-as-list beats, project folder seeds (`canon.md` / `beats.md` / `cards.md`).  
**Still open:** C2 reorder, true freeform C4, rich C7 markdown pack sync, scene-summary cards (not only inline markers).

### D. Fountain craft & export

| ID | Feature | Notes | Source |
|---|---|---|---|
| F1 | Stronger Fountain compliance / edge cases | Forced action `!`, lyrics, etc. | johnaugust.com / Highland |
| F2 | PDF export (paginated) | From preview engine or print CSS | **DONE 2026-07-23** (WebEngine printToPdf, Letter, light theme) |
| F3 | FDX import/export (best effort) | Collaboration with FD users | Industry |
| F4 | Title page editor | Structured fields → Fountain title page | Universal |
| F5 | Hide/show `[[notes]]` in preview/print | Common Fountain need | **DONE 2026-07-23** (print CSS) |
| F6 | Find in script / find character cues | | Universal |
| F7 | Snapshot / version sidebar | Local copies dated — not full Git UI | Process / revise |
| F8 | Dark mode polish + focus mode | Distraction-free | Highland sprint culture |

### E. Planning docs beside the script (pipeline glue)

| ID | Feature | Notes | Source |
|---|---|---|---|
| P1 | **Project folder mode** | Open directory: script + `beats/` + `cards/` + `CANON.md` | **Partial 2026-07-23** — File → Open Project Folder… seeds `canon.md` / `beats.md` / `cards.md` + loads `script.fountain` if present (flat files, not full binder UI) |
| P2 | Multi-tab or split: script \| canon \| beats | | Our OS |
| P3 | Generate cards from scene headings | Empty summaries for fill-in | Speed |
| P4 | Generate scene skeleton from card | Insert Fountain stub under cursor | Cards → pages |
| P5 | Sequence markers | e.g. sections `## SEQ 01` with progress | Our seq machine |
| P6 | Constraints checklist panel | Budget/cast/must-hits checkboxes | Magic/Grok lessons |

### F. Revision, notes, collaboration (lightweight)

| ID | Feature | Notes | Source |
|---|---|---|---|
| R1 | Revision colours / marks (local) | Production revision is heavy; start with “edit session” highlight | FD Revision Mode (lite) |
| R2 | Comments dock | Fountain notes index | Highland notes / Fling spirit |
| R3 | Diff two `.fountain` files | | Process |
| R4 | Share read-only preview (optional later) | Web link is Highland Fling territory — only if wanted | JA/Highland |
| R5 | Export “notes only” or “action only” | Coverage / budget helpers | Production-adjacent |

### G. AI / OpenClaw integration (differentiator — careful)

| ID | Feature | Notes | Source |
|---|---|---|---|
| A1 | “Copy scene bundle for agent” | Scene + card + relevant canon slice → clipboard/file | Our factory |
| A2 | Watch folder / open from `projects/screenwriting/...` | | OpenClaw |
| A3 | Apply patch from unified diff | Agent writes file; user accepts in UI | Safer than silent overwrite |
| A4 | Optional local/cloud LLM panel | **Do not block offline core**; keep optional | Market trend |
| A5 | Specialist checklists in UI | Continuity / critic / producer prompts as runbooks | Our modes |
| A6 | Goldmine / premise scratchpad | Separate from script body | Newsletter/Skool adjacency |

**Principle:** FountainPad remains useful **with AI off**. AI is a power-up for Graham’s OS, not a hostage feature.

### H. Quality-of-life already half-there

| ID | Feature | Notes |
|---|---|---|
| Q1 | Better autocomplete for character names | From seen cues |
| Q2 | Smart tab / element cycling | FD-style Tab between element types — controversial in Fountain world; optional |
| Q3 | Goal / sprint timer | Highland |
| Q4 | Gender / character frequency report | Highland-style analytics lite |
| Q5 | Custom preview CSS / page size | |

---

## 4. What forums / market signal says (summary)

| Signal | Implication for FountainPad |
|---|---|
| “Opportunity for a solid Fountain app” (r/Screenwriting) | Cross-platform packaged app + great preview is already a story |
| Windows Fountain pain (Highland Mac-tilted historically) | Windows build matters |
| Fade In praised for Fountain paste/import | FDX/Fountain round-trip worth doing eventually |
| FD Beat Board loved but often laggy/hated in threads | Prefer **fast simple cards** over a sluggish infinite canvas v1 |
| WriterDuet cards + collab | Collab is a trap early; cards are not |
| Highland: plain text, notes, focus, share | Don’t destroy Fountain purity; add boards as views on text/sidecar |

Sources sampled 2026-07-21 (non-exhaustive): Final Draft KB/blog (Beat Board, Index Cards, Outline, Navigator, Revision); WriterDuet cards/mind map/outline docs; johnaugust.com Fountain/Highland; r/Screenwriting threads on Fountain apps and feature wishes.

---

## 5. Suggested product phases

### Phase 0 — still great personal tool
- Keep improving editor/preview stability  
- Your workflow only  

### Phase 1 — “writers can open it”
- D1 packaged builds  
- N1 scene navigator ✅ (2026-07-23)  
- F2 PDF export ✅ (2026-07-23)  
- F5 notes hide in print ✅ (2026-07-23)  

### Phase 2 — “cards + pipeline”
- C1 index cards list + jump ✅ (2026-07-23)  
- C6 Goal/Conflict/Turn template buttons ✅ partial  
- C4 beat list (not freeform canvas) ✅ partial  
- P1 project folder seed files ✅ partial  
- C7 full markdown card-pack exchange — still open  
- P3/P4 card ↔ scene helpers — still open  
- N4 section outline — still open  
- **Uncommitted 2026-07-23 night:** F5 print CSS for notes hide (light+dark); smoke test rewrite incomplete  

### Phase 3 — “board + industry exchange”
- C2 reorder  
- C4/C5 beat board or outline lane  
- F3 FDX  
- R1/R3 revision lite  

### Phase 4 — “AI factory cockpit”
- A1–A3 OpenClaw bridges  
- A5 specialist runbooks  
- Optional A4  

---

## 6. Explicit non-goals (for now)

- Real-time Google-Docs-style collab (WriterDuet’s moat; expensive)  
- Full production revision sets / locked page colors day one  
- Replacing Final Draft for studio production accounting  
- Mandatory cloud accounts  
- Eating OpenClaw’s job (agent orchestration stays outside or thinly bridged)

---

## 7. Ties to Screenwriting OS files

When project mode exists, prefer these names (already in design handbook):

```text
CANON.md  CONSTRAINTS.md  STATUS.md
beats/BEATS.CURRENT.md
cards/           ← card pack files
scenes/ or single draft.fountain
reports/         ← importable issues
```

FountainPad can treat that folder as a **project root** without implementing the whole agent runtime.

---

## 8. Decision prompts for Graham (when prioritising)

1. Personal-only vs ship-to-others first? (D1 vs cards)  
2. Cards as **view on one Fountain file** vs **markdown files in a project**? (recommend: both, markdown is SoT for AI)  
3. Beat board freeform or linear outline first? (recommend: linear + cards before freeform)  
4. Any AI inside the app, or clipboard/folder only?  

---

## Related

- App: repo `grahaminman/FountainPad` · local `projects/FountainPad`  
- Distribution: [DISTRIBUTION_NO_TERMINAL.md](./DISTRIBUTION_NO_TERMINAL.md)  
- Pipeline design: `projects/screenwriting/SCREENWRITING_OS_DESIGN.md`  
- Ledger: `projects/screenwriting/CONVERSATION_LEDGER.md`  
