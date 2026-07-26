"""
fountain_tools.py — shared helpers for craft UX (stats, title page, characters).

Used by editor autocomplete, status bar page estimates, title-page dialog,
and find-character flows. Keep pure/functions where possible (easy to test).
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# Standard Fountain title-page keys (order used by the builder UI).
TITLE_PAGE_KEYS: Tuple[str, ...] = (
    "Title",
    "Credit",
    "Author",
    "Source",
    "Draft date",
    "Date",
    "Contact",
    "Copyright",
    "Notes",
)

RE_TITLE_KEY = re.compile(
    r"^(Title|Credit|Author|Authors|Source|Notes|Draft date|Date|Contact|Copyright)\s*:\s*(.*)$",
    re.IGNORECASE,
)

RE_CHARACTER_CUE = re.compile(
    r"^(?:\s*)([A-Z][A-Z0-9 \.\-'\(\)]+?)(?:\s*\^)?\s*$"
)

RE_SCENE = re.compile(
    r"^(?:\s*)((?:INT|EXT|EST|I/?E|INT\./EXT|INT/EXT)[\.\s].+)$",
    re.IGNORECASE,
)
RE_SCENE_DOT = re.compile(r"^(?:\s*)\.(?!\.)(.+)$")
RE_TRANSITION = re.compile(
    r"^(?:\s*)((?:FADE (?:TO BLACK|OUT)|CUT TO BLACK)\.?|.+ TO:)$",
    re.IGNORECASE,
)
RE_PAREN = re.compile(r"^(?:\s*)(\(.+\))\s*$")
RE_SECTION = re.compile(r"^(?:\s*)#{1,6}(?:\s|$)")
RE_NOTE = re.compile(r"^(?:\s*)\[\[")
RE_VERSION = re.compile(r"^(?:\s*)@v\d+\s*$", re.IGNORECASE)

STATIC_SCENE_PREFIXES = ("INT. ", "EXT. ", "I/E. ", "EST. ", ". ")
STATIC_TRANSITIONS = (
    "CUT TO:",
    "FADE TO:",
    "SMASH CUT TO:",
    "MATCH CUT TO:",
    "FADE IN:",
    "FADE OUT.",
    "DISSOLVE TO:",
)
STATIC_EXTENSIONS = (
    "(CONT'D)",
    "(V.O.)",
    "(O.S.)",
    "(O.C.)",
    "(CONTINUOUS)",
)
STATIC_TITLE_KEYS = tuple(f"{k}: " for k in TITLE_PAGE_KEYS)

# Rough US Letter screenplay estimate: ~55 lines/page after title page chrome.
LINES_PER_PAGE = 55
# Common rule of thumb: ~1 page ≈ 1 minute.
MINUTES_PER_PAGE = 1.0


def is_scene_heading_line(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    return bool(RE_SCENE.match(stripped) or RE_SCENE_DOT.match(stripped))


def clean_character_name(raw: str) -> str:
    """Strip dual-caret and trailing extensions from a character cue."""
    name = (raw or "").strip()
    if name.endswith("^"):
        name = name[:-1].rstrip()
    # Drop parenthetical extensions: ALICE (V.O.) -> ALICE
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    return name


def list_character_cues(
    text: str,
    is_scene_heading: Optional[Callable[[str], bool]] = None,
) -> List[str]:
    """Unique character names in document order (no CONT'D variants)."""
    scene_fn = is_scene_heading or is_scene_heading_line
    seen: set[str] = set()
    out: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or RE_NOTE.match(stripped) or RE_SECTION.match(stripped):
            continue
        if RE_VERSION.match(stripped):
            continue
        if scene_fn(stripped):
            continue
        if RE_TRANSITION.match(stripped) or stripped.startswith(">"):
            continue
        if RE_PAREN.match(stripped):
            continue
        m = RE_CHARACTER_CUE.match(stripped)
        if not m:
            continue
        name = clean_character_name(m.group(1))
        if not name or len(name) > 40 or "  " in name:
            continue
        # Avoid ALL CAPS multi-word action mistaken as cues when very long
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def list_locations(
    text: str,
    is_scene_heading: Optional[Callable[[str], bool]] = None,
) -> List[str]:
    scene_fn = is_scene_heading or is_scene_heading_line
    seen: set[str] = set()
    out: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not scene_fn(stripped):
            continue
        m = RE_SCENE.match(stripped)
        if not m:
            continue
        heading = m.group(1)
        loc_m = re.match(
            r"^(?:INT|EXT|EST|I/?E|INT\./EXT|INT/EXT)[\.\s]+(.+?)(?:\s*-\s*.+)?$",
            heading,
            re.IGNORECASE,
        )
        if not loc_m:
            continue
        loc = loc_m.group(1).strip(" .")
        if loc and loc not in seen:
            seen.add(loc)
            out.append(loc)
    return out


def list_scene_headings_text(
    text: str,
    is_scene_heading: Optional[Callable[[str], bool]] = None,
) -> List[str]:
    scene_fn = is_scene_heading or is_scene_heading_line
    return [ln.strip() for ln in (text or "").splitlines() if scene_fn(ln)]


def parse_title_page(text: str) -> Tuple[Dict[str, str], int]:
    """Return (key->value map, end_line_index exclusive of title block).

    Title page is lines from start until a blank line after at least one key,
    or until ``==`` / non-key content. Values may be multi-line until next key.
    """
    lines = (text or "").splitlines()
    if not lines:
        return {}, 0

    values: Dict[str, str] = {}
    # Canonical key casing from TITLE_PAGE_KEYS
    canon = {k.lower(): k for k in TITLE_PAGE_KEYS}
    canon["authors"] = "Author"

    i = 0
    # Skip leading blanks
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not RE_TITLE_KEY.match(lines[i].strip()):
        return {}, 0

    current_key: Optional[str] = None
    start = i
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if stripped == "==" or stripped.startswith("==="):
            break
        m = RE_TITLE_KEY.match(stripped)
        if m:
            key_raw, val = m.group(1), (m.group(2) or "").strip()
            key = canon.get(key_raw.lower(), key_raw)
            values[key] = val
            current_key = key
            i += 1
            continue
        if not stripped:
            # Blank after title keys ends title page (Fountain convention)
            i += 1
            break
        # Continuation of previous value
        if current_key is not None:
            prev = values.get(current_key, "")
            values[current_key] = (prev + "\n" + stripped).strip() if prev else stripped
            i += 1
            continue
        break

    # If we never saw a blank and hit content, end at first non-title line
    return values, i


def format_title_page(values: Dict[str, str]) -> str:
    """Build Fountain title-page block (no trailing ==)."""
    lines: List[str] = []
    for key in TITLE_PAGE_KEYS:
        val = (values.get(key) or "").strip()
        if not val and key not in values:
            continue
        if "\n" in val:
            parts = val.splitlines()
            lines.append(f"{key}: {parts[0]}")
            for extra in parts[1:]:
                lines.append(extra)
        else:
            lines.append(f"{key}: {val}")
    return "\n".join(lines)


def replace_title_page(text: str, values: Dict[str, str]) -> str:
    """Replace or insert title page keys; preserve body after title block."""
    _old, end = parse_title_page(text)
    lines = (text or "").splitlines()
    ends_nl = (text or "").endswith("\n")
    body_lines = lines[end:]
    # Drop a single leading blank from body (we'll add our own)
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]
    title_block = format_title_page(values)
    if title_block:
        new_text = title_block + "\n\n" + "\n".join(body_lines)
    else:
        new_text = "\n".join(body_lines)
    if ends_nl and new_text and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text


def estimate_pages(text: str) -> Tuple[float, float, int, int]:
    """Return (pages, minutes, body_lines, word_count).

    Uses stripped preview-ish body: skips title page, section markers,
    card/beat markers, and @vN lines. Rough screenplay estimate only.
    """
    _title, end = parse_title_page(text)
    lines = (text or "").splitlines()[end:]
    body: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            body.append("")
            continue
        if RE_SECTION.match(s) or RE_NOTE.match(s) or RE_VERSION.match(s):
            continue
        if s.startswith("=="):
            continue
        body.append(ln)
    # Count non-empty lines for page estimate
    content_lines = sum(1 for ln in body if ln.strip())
    words = len(re.findall(r"\S+", "\n".join(body)))
    pages = max(content_lines / float(LINES_PER_PAGE), 0.0)
    # Round to 1 decimal for UI
    pages_r = round(pages, 1)
    minutes = round(pages_r * MINUTES_PER_PAGE, 1)
    return pages_r, minutes, content_lines, words


def find_character_dialogue_blocks(
    text: str,
    character: str,
    is_scene_heading: Optional[Callable[[str], bool]] = None,
) -> List[Tuple[int, str, str]]:
    """Find dialogue blocks for a character.

    Returns list of (cue_block_number, scene_heading, preview_text).
    """
    scene_fn = is_scene_heading or is_scene_heading_line
    target = clean_character_name(character).upper()
    lines = (text or "").splitlines()
    hits: List[Tuple[int, str, str]] = []
    current_scene = ""
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if scene_fn(stripped):
            current_scene = stripped
            i += 1
            continue
        m = RE_CHARACTER_CUE.match(stripped)
        if m and clean_character_name(m.group(1)).upper() == target:
            cue_bn = i
            # Collect following dialogue until blank or next element
            j = i + 1
            dialogue_parts: List[str] = []
            while j < len(lines):
                nxt = lines[j]
                ns = nxt.strip()
                if not ns:
                    break
                if scene_fn(ns) or RE_CHARACTER_CUE.match(ns) or RE_TRANSITION.match(ns):
                    break
                if RE_SECTION.match(ns) or RE_NOTE.match(ns):
                    break
                dialogue_parts.append(ns)
                j += 1
            preview = " ".join(dialogue_parts)
            if len(preview) > 120:
                preview = preview[:117] + "…"
            hits.append((cue_bn, current_scene, preview))
            i = j
            continue
        i += 1
    return hits


def completion_suggestions(
    text: str,
    context: str,
    is_scene_heading: Optional[Callable[[str], bool]] = None,
) -> List[str]:
    """Context-aware autocomplete candidates.

    context: one of ``title``, ``scene``, ``character``, ``extension``,
    ``transition``, ``general``.
    """
    scene_fn = is_scene_heading or is_scene_heading_line
    chars = list_character_cues(text, scene_fn)
    locs = list_locations(text, scene_fn)
    scenes = list_scene_headings_text(text, scene_fn)

    if context == "title":
        return list(STATIC_TITLE_KEYS)

    if context == "extension":
        return list(STATIC_EXTENSIONS)

    if context == "transition":
        return list(STATIC_TRANSITIONS)

    if context == "scene":
        out: List[str] = list(STATIC_SCENE_PREFIXES)
        for s in scenes:
            if s not in out:
                out.append(s)
        for loc in locs:
            # Offer bare location and common INT/EXT wraps
            if loc not in out:
                out.append(loc)
            for pref in ("INT. ", "EXT. "):
                cand = f"{pref}{loc} - DAY"
                if cand not in out:
                    out.append(cand)
        return out

    if context == "character":
        out = []
        for name in chars:
            out.append(name)
            cont = f"{name} (CONT'D)"
            if cont not in out:
                out.append(cont)
            dual = f"{name} ^"
            if dual not in out:
                out.append(dual)
        out.extend(STATIC_EXTENSIONS)
        return out

    # general: mix of useful starters
    out = list(STATIC_SCENE_PREFIXES) + list(STATIC_TRANSITIONS)
    out.extend(chars)
    out.extend(scenes)
    out.extend(locs)
    return out


def detect_completion_context(line_before_cursor: str, in_title_page: bool) -> str:
    """Guess completion context from the current line prefix."""
    raw = line_before_cursor or ""
    stripped = raw.strip()
    upper = stripped.upper()

    if in_title_page and (not stripped or RE_TITLE_KEY.match(stripped) or ":" not in stripped):
        # Empty line or typing a key in title page
        if not stripped or (stripped and not stripped.endswith(":") and ":" not in stripped):
            return "title"

    if stripped.startswith("(") or upper.endswith("("):
        return "extension"

    if upper.endswith(" TO") or upper.endswith(" TO:") or any(
        upper.startswith(t.split()[0]) for t in ("CUT", "FADE", "SMASH", "MATCH", "DISSOLVE")
    ):
        if "TO" in upper or upper.startswith("FADE"):
            return "transition"

    if (
        upper.startswith(("INT", "EXT", "EST", "I/E"))
        or stripped.startswith(".")
        or upper in ("I", "IN", "E", "EX")
    ):
        return "scene"

    # All-caps character-ish line
    if stripped and stripped.upper() == stripped and re.match(r"^[A-Z0-9 \.\-'\(\)\^]+$", stripped):
        return "character"

    if not stripped:
        return "general"

    return "general"
