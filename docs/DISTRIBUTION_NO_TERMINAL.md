# FountainPad — running without Terminal (distribution options)

**Captured:** 2026-07-21  
**Context:** People who might use FountainPad (writers) are less likely to run git/venv/pip. Graham still wants to improve the Python app for personal use.

## Bottom line

| Audience | Path |
|---|---|
| **Graham (dev)** | Keep source: venv + `python main.py` |
| **Non-technical writers** | Ship a **packaged desktop app** (dmg / exe / AppImage) — not “easier Python” |

**Yes, it is possible** to run without installing Python or opening Terminal.

---

## Options

| # | Option | User does | Pros | Cons | Fit |
|---|---|---|---|---|---|
| 1 | **Packaged desktop app** (PyInstaller / Briefcase / Nuitka / py2app) | Download `.dmg` / `.exe` / `.AppImage`, open | True no-terminal; real app feel | Per-OS builds; macOS notarisation; PySide6+WebEngine = large binary | **Best default** |
| 2 | **Portable folder build** | Unzip, double-click binary | No installer wizard | Less polished; Gatekeeper/SmartScreen if unsigned | Good interim |
| 3 | Store / Homebrew cask | Install from store/manager | Familiar for some | Still an install; publishing overhead | Later |
| 4 | **Web app** | Open URL | Zero install | UI rewrite; different save UX; hosting | Second product only |
| 5 | Tauri/Electron shell | Double-click app | Nice packaging if web-first | Big rewrite if staying PySide | Usually overkill |
| 6 | Embedded Python + `.command`/`.bat` | Double-click script | Closer to current code | Fragile; still feels techy | Weak |
| 7 | Source-only (current README) | Terminal venv | Best for Graham | Bad for target users | Keep for **dev** |

## OS realities

- **macOS:** `.app` in `.dmg` (ideally signed + notarised)  
- **Windows:** installer or portable `.exe` (SmartScreen until reputation/signing)  
- **Linux:** `.AppImage` common  

PySide6 + **Qt WebEngine** (preview) packages, but expect large downloads and CI per platform.

## Recommended split

1. **Dev forever:** current git workflow.  
2. **Users later:** GitHub Actions → build artefacts → GitHub Releases; README = “Download the app.”  

You do **not** need to change day-to-day development to plan this.

## When picked up

- [ ] Choose packager (likely PyInstaller one-folder first for WebEngine reliability)  
- [ ] macOS smoke: open fountain, preview offline, save  
- [ ] Windows smoke  
- [ ] Optional signing  
- [ ] Release notes + plain-language README section  

Related TODO: **FountainPad — no-terminal distribution for writers**.
