"""
project.py — FountainPad project folder helpers (P1).

A project is a directory that holds:
  - script.fountain   (primary draft; SoT for pages)
  - canon.md          (world / rules / constraints notes)
  - beats.md          (planning pack; sync via C7)
  - cards.md          (planning pack; sync via C7)

Optional extras in the same folder (other .fountain / .md) appear in the binder
but are not auto-created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

SCRIPT_NAME = "script.fountain"
CANON_NAME = "canon.md"
BEATS_NAME = "beats.md"
CARDS_NAME = "cards.md"

CORE_FILES: Tuple[str, ...] = (SCRIPT_NAME, CANON_NAME, BEATS_NAME, CARDS_NAME)

ROLE_SCRIPT = "script"
ROLE_CANON = "canon"
ROLE_BEATS = "beats"
ROLE_CARDS = "cards"
ROLE_OTHER = "other"

SEED_CANON = """# Canon

Story world, rules, lore, and hard constraints.

## Logline

## Must-hits

## Open questions
"""

SEED_BEATS = """# Beats

Planning labels for the draft. Prefer **File → Export/Import Beat Pack**
so this file stays in sync with `[[beat:]]` markers in the script.

<!-- FountainPad beat pack seed. Replace via Export Beat Pack. -->
"""

SEED_CARDS = """# Index Cards

Planning cards for the draft. Prefer **File → Export/Import Card Pack**
so this file stays in sync with `[[card:]]` markers in the script.

<!-- FountainPad card pack seed. Replace via Export Card Pack. -->
"""

SEED_SCRIPT = """Title: Untitled
Credit: Written by
Author: 
Draft date: 

= 

INT. SOMEWHERE - DAY

We begin.
"""


@dataclass
class ProjectFile:
    """One entry in the project binder."""

    path: Path
    role: str  # script | canon | beats | cards | other
    label: str
    exists: bool = True


@dataclass
class ProjectInfo:
    """Open project folder state."""

    root: Path
    files: List[ProjectFile] = field(default_factory=list)
    created: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.root.name

    def path_for_role(self, role: str) -> Optional[Path]:
        for f in self.files:
            if f.role == role:
                return f.path
        return None

    def script_path(self) -> Path:
        p = self.path_for_role(ROLE_SCRIPT)
        return p if p is not None else self.root / SCRIPT_NAME


def _role_for_name(name: str) -> str:
    low = name.lower()
    if low == SCRIPT_NAME:
        return ROLE_SCRIPT
    if low == CANON_NAME:
        return ROLE_CANON
    if low == BEATS_NAME:
        return ROLE_BEATS
    if low == CARDS_NAME:
        return ROLE_CARDS
    return ROLE_OTHER


def _label_for(role: str, name: str) -> str:
    return {
        ROLE_SCRIPT: "Script",
        ROLE_CANON: "Canon",
        ROLE_BEATS: "Beats pack",
        ROLE_CARDS: "Cards pack",
    }.get(role, name)


def seed_template(name: str) -> str:
    low = name.lower()
    if low == SCRIPT_NAME:
        return SEED_SCRIPT
    if low == CANON_NAME:
        return SEED_CANON
    if low == BEATS_NAME:
        return SEED_BEATS
    if low == CARDS_NAME:
        return SEED_CARDS
    return ""


def ensure_project_files(
    root: Path,
    *,
    create_script: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Create missing core files. Returns (created_names, errors).
    """
    root = Path(root)
    created: List[str] = []
    errors: List[str] = []
    targets = [CANON_NAME, BEATS_NAME, CARDS_NAME]
    if create_script:
        targets = [SCRIPT_NAME] + targets
    for name in targets:
        path = root / name
        if path.exists():
            continue
        try:
            path.write_text(seed_template(name), encoding="utf-8")
            created.append(name)
        except OSError as exc:
            errors.append(f"{name}: {exc}")
    return created, errors


def discover_project_files(root: Path) -> List[ProjectFile]:
    """Core files first (even if missing), then other .fountain / .md in root."""
    root = Path(root)
    out: List[ProjectFile] = []
    seen: set[str] = set()

    for name in CORE_FILES:
        path = root / name
        role = _role_for_name(name)
        out.append(
            ProjectFile(
                path=path,
                role=role,
                label=_label_for(role, name),
                exists=path.is_file(),
            )
        )
        seen.add(name.lower())

    extras: List[Path] = []
    if root.is_dir():
        for p in sorted(root.iterdir(), key=lambda x: x.name.lower()):
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            if p.suffix.lower() not in {".fountain", ".md", ".markdown", ".txt"}:
                continue
            if p.name.lower() in seen:
                continue
            extras.append(p)

    for p in extras:
        out.append(
            ProjectFile(
                path=p,
                role=ROLE_OTHER,
                label=p.name,
                exists=True,
            )
        )
    return out


def open_project_folder(root: Path, *, create_script: bool = True) -> ProjectInfo:
    """Seed core files and return binder listing."""
    root = Path(root).resolve()
    created, _errors = ensure_project_files(root, create_script=create_script)
    files = discover_project_files(root)
    return ProjectInfo(root=root, files=files, created=created)


def is_markdown_path(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown", ".txt"}


def is_fountain_path(path: Path) -> bool:
    return path.suffix.lower() in {".fountain", ".spmd"}
