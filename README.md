# FountainPad

A clean, focused **Fountain** screenplay editor for desktop.

Write plain-text `.fountain` on the left, see a properly formatted screenplay preview on the right (via bundled [fountain.js](https://github.com/mattdaly/Fountain.js)). Built with **Python 3** and **PySide6**.

## Features

- Fountain text editor with monospace font and line numbers
- Syntax highlighting for scene headings, character cues, dialogue, parentheticals, transitions, sections, notes, and title-page keys
- **Live split preview** (editor | formatted page) with 300ms debounce
- **Detachable preview window**
- New / Open / Save / Save As for `.fountain` files
- Unsaved-changes tracking and window title indicator
- Light / Dark mode (editor + preview)
- Status bar: current scene + character/word counts
- Remembers window geometry, splitter sizes, and theme
- Offline-friendly: fountain.js is bundled — no network required at runtime

## Requirements

- Python **3.10+** recommended (3.9 may work)
- **PySide6** (includes Qt WebEngine for the preview)
- Desktop GUI session on **Windows**, **macOS**, or **Linux**

## Install & run

### macOS

```bash
git clone https://github.com/grahaminman/FountainPad.git
cd FountainPad
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If Python is missing: install from [python.org](https://www.python.org/downloads/) or `brew install python`.

### Windows

**Command Prompt**

```bat
git clone https://github.com/grahaminman/FountainPad.git
cd FountainPad
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

**PowerShell**

```powershell
git clone https://github.com/grahaminman/FountainPad.git
cd FountainPad
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Enable **Add python.exe to PATH** when installing Python. If script activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Linux (Ubuntu / Debian)

```bash
git clone https://github.com/grahaminman/FountainPad.git
cd FountainPad
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If Qt/WebEngine system libs are missing on older distros, install common dependencies:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libgl1 libxkbcommon0 \
  libegl1 libfontconfig1 libdbus-1-3 libxcb-cursor0
```

Exact package names vary by distro; PySide6 wheels bundle most of Qt.

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl/Cmd+N | New |
| Ctrl/Cmd+O | Open |
| Ctrl/Cmd+S | Save |
| Ctrl/Cmd+Shift+S | Save As |
| Ctrl/Cmd+P | Toggle split preview |
| Ctrl/Cmd+Shift+P | Detach preview window |
| Ctrl/Cmd+D | Toggle dark mode |
| Ctrl/Cmd+Q | Quit |

## Project layout

```
FountainPad/
├── main.py              # Entry point
├── editor.py            # Editor + Fountain highlighter + line numbers
├── preview.py           # QWebEngineView + fountain.js bridge
├── mainwindow.py        # Menus, splitter, files, theme, settings
├── resources/
│   ├── fountain.js      # Bundled parser (Matt Daly, MIT)
│   ├── preview.html
│   └── styles/
│       ├── preview-light.css
│       └── preview-dark.css
├── requirements.txt
├── README.md
└── LICENSE
```

## Fountain format

Fountain is a plain-text screenplay syntax. Learn more at [fountain.io](https://fountain.io).

FountainPad ships a short sample on first launch so you can see highlighting and preview immediately.

## Technical notes

- Preview updates call `fountain.parse()` inside the page via `runJavaScript`, with **300ms debounce** while typing.
- Themes toggle editor colours and swap preview CSS (`setTheme('light'|'dark')`).
- Window size, splitter position, dark mode, and split visibility are stored with `QSettings`.

## License

MIT — see [LICENSE](LICENSE).

`resources/fountain.js` is **fountain-js** by Matt Daly, also MIT-licensed.
