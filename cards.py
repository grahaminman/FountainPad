"""
cards.py — Card markers, versions, and apply-to-script helpers.

Fountain markers (notes to the draft, not instructions):

  [[card: id=c001 | Note | active=v2]]
  @v1
  INT. OLD BAY - NIGHT
  Driver is calm.
  @v2
  INT. ARMOURED BAY - NIGHT
  Driver checks the seal.

Legacy single-body cards (no @vN) become one active version (v1).

Apply-to-script
  - Promotes the active version scene heading (if any).
  - Writes/replaces leading action under that scene only.
  - Never touches character cues, parentheticals, or dialogue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set, Tuple

RE_CARD_LINE = re.compile(r"^(?:\s*)\[\[card:\s*(.*?)\]\]\s*$", re.IGNORECASE)
RE_BEAT_LINE = re.compile(r"^(?:\s*)\[\[beat:\s*(.*?)\]\]\s*$", re.IGNORECASE)
RE_ID = re.compile(r"^id\s*=\s*([A-Za-z0-9_-]+)$", re.IGNORECASE)
RE_ID_TOKEN = re.compile(r"id\s*=\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
RE_ACTIVE_TOKEN = re.compile(r"active\s*=\s*(v?\d+)", re.IGNORECASE)
RE_VER_MARK = re.compile(r"^@v(\d+)\s*$", re.IGNORECASE)
RE_CHARACTER = re.compile(r"^(?:\s*)([A-Z][A-Z0-9 \.\-'\(\)]+?)(\s*\^)?\s*$")
RE_PAREN = re.compile(r"^(?:\s*)(\(.+\))\s*$")
RE_TRANSITION = re.compile(
    r"^(?:\s*)((?:FADE|CUT|SMASH|MATCH|DISSOLVE|WIPE).+TO:|>.+)$",
    re.IGNORECASE,
)
RE_SECTION = re.compile(r"^(?:\s*)#{1,6}\s+")
RE_NOTE_ANY = re.compile(r"^(?:\s*)\[\[.+\]\]\s*$")
RE_SCENE_SHAPE = re.compile(
    r"^(?:INT|EXT|EST|I/?E|INT\./EXT|INT/EXT)[\.\s].+",
    re.IGNORECASE,
)

VALID_TYPES = frozenset({"Goal", "Conflict", "Turn", "Note", "Card"})


@dataclass
class CardVersion:
    """One snapshot of a card planning text."""

    version_id: str
    text: str


@dataclass
class CardInfo:
    """One card marker + versions in document order."""

    block_number: int
    card_id: str
    card_type: str
    body: str
    scene_heading: str
    scene_block: int
    active_version: str = "v1"
    versions: List[CardVersion] = field(default_factory=list)

    @property
    def active_text(self) -> str:
        if not self.versions:
            return (self.body or "").strip()
        for v in self.versions:
            if v.version_id == self.active_version:
                return (v.text or "").strip()
        return (self.versions[-1].text or "").strip()

    @property
    def draft_slug(self) -> str:
        text = self.active_text
        if not text:
            return ""
        first = text.splitlines()[0].strip()
        return first if looks_like_scene(first) else ""

    @property
    def action_text(self) -> str:
        text = self.active_text
        if not text:
            return ""
        lines = text.splitlines()
        if lines and looks_like_scene(lines[0].strip()):
            return "\n".join(lines[1:]).strip()
        return text.strip()

    def display_label(self) -> str:
        """Short multi-line label for the Index Cards list (narrow pane)."""
        active = self.active_text
        lines = [ln.strip() for ln in active.splitlines() if ln.strip()] if active else []
        slug = self.draft_slug
        note = ""
        if slug:
            note = lines[1] if len(lines) > 1 else ""
        elif lines:
            note = lines[0]
        cid = self.card_id or "?"
        ver = self.active_version or "v1"
        if len(self.versions) > 1:
            head = f"{cid} · {self.card_type} · {ver}/{len(self.versions)}"
        else:
            head = f"{cid} · {self.card_type}"
        parts = [head]
        if slug:
            parts.append(slug)
        if note and note != slug:
            parts.append(note)
        return "\n".join(parts)


def looks_like_scene(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith(".") and not t.startswith(".."):
        return True
    return bool(RE_SCENE_SHAPE.match(t))


def looks_like_character(text: str) -> bool:
    s = (text or "").strip()
    if not s or s.endswith(":"):
        return False
    if looks_like_scene(s) or is_card_line(s) or is_beat_line(s):
        return False
    if RE_PAREN.match(s) or RE_TRANSITION.match(s) or RE_SECTION.match(s):
        return False
    if RE_NOTE_ANY.match(s):
        return False
    m = RE_CHARACTER.match(s)
    if not m:
        return False
    name = m.group(1).strip()
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper == len(letters) and 1 <= len(name) <= 40


def _norm_ver(token: str) -> str:
    t = (token or "").strip().lower()
    if not t:
        return "v1"
    if t.startswith("v"):
        return t
    if t.isdigit():
        return f"v{t}"
    return t


def parse_card_inner(inner: str) -> Tuple[str, str, str, str]:
    raw = (inner or "").strip()
    if not raw:
        return "", "Note", "", "v1"

    card_id = ""
    active = "v1"
    rest = raw

    am = RE_ACTIVE_TOKEN.search(rest)
    if am:
        active = _norm_ver(am.group(1))
        rest = (rest[: am.start()] + rest[am.end() :]).strip(" |")

    if "|" in rest:
        left, _, right = rest.partition("|")
        left, right = left.strip(), right.strip()
        m = RE_ID.match(left)
        if m:
            card_id = m.group(1)
            rest = right
        else:
            m2 = RE_ID_TOKEN.search(left)
            if m2:
                card_id = m2.group(1)
                rest = right
            else:
                m3 = RE_ID_TOKEN.search(right)
                if m3:
                    card_id = m3.group(1)
                    rest = (left + " " + (right[: m3.start()] + right[m3.end() :])).strip(" |")
    else:
        m2 = RE_ID_TOKEN.search(rest)
        if m2:
            card_id = m2.group(1)
            rest = (rest[: m2.start()] + rest[m2.end() :]).strip(" |")

    rest = rest.strip(" |")
    if not rest:
        return card_id, "Note", "", active

    first, _, more = rest.partition(" ")
    if first in VALID_TYPES:
        return card_id, first, more.strip(), active
    if (
        not more
        and len(first) <= 24
        and first[:1].isupper()
        and first.replace("-", "").isalnum()
    ):
        return card_id, first, "", active
    if first[:1].isupper() and first.isalpha() and len(first) <= 16:
        return card_id, first, more.strip(), active
    return card_id, "Note", rest, active


def parse_versions(body: str, active_hint: str = "v1") -> Tuple[str, List[CardVersion]]:
    raw = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    has_mark = any(RE_VER_MARK.match(ln.strip()) for ln in lines)
    if not has_mark:
        return "v1", [CardVersion("v1", raw.strip())]

    versions: List[CardVersion] = []
    cur_id: Optional[str] = None
    buf: List[str] = []
    preamble: List[str] = []

    def flush() -> None:
        nonlocal cur_id, buf
        if cur_id is None:
            buf = []
            return
        text = "\n".join(buf).strip()
        versions.append(CardVersion(cur_id, text))
        cur_id = None
        buf = []

    for ln in lines:
        m = RE_VER_MARK.match(ln.strip())
        if m:
            flush()
            cur_id = f"v{int(m.group(1))}"
            continue
        if cur_id is None:
            preamble.append(ln)
        else:
            buf.append(ln)
    flush()

    if preamble and not versions:
        return "v1", [CardVersion("v1", "\n".join(preamble).strip())]
    if preamble and versions:
        first = versions[0]
        merged = ("\n".join(preamble).strip() + "\n" + first.text).strip()
        versions[0] = CardVersion(first.version_id, merged)

    if not versions:
        versions = [CardVersion("v1", "")]

    active = _norm_ver(active_hint)
    ids = {v.version_id for v in versions}
    if active not in ids:
        active = versions[-1].version_id
    return active, versions


def format_versions_body(versions: List[CardVersion], active: str) -> str:
    del active
    if not versions:
        return ""
    if len(versions) == 1 and versions[0].version_id == "v1":
        return (versions[0].text or "").strip()
    parts: List[str] = []
    for v in versions:
        parts.append(f"@{v.version_id}")
        t = (v.text or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def format_card_marker(
    card_id: str,
    card_type: str,
    inline: str = "",
    active: str = "",
    multi_version: bool = False,
) -> str:
    ctype = (card_type or "Note").strip() or "Note"
    cid = (card_id or "").strip()
    inline = (inline or "").strip()
    label = f"{ctype} {inline}".strip() if inline else ctype
    act = _norm_ver(active) if active else ""
    if cid and multi_version and act:
        return f"[[card: id={cid} | {label} | active={act}]]"
    if cid:
        return f"[[card: id={cid} | {label}]]"
    if multi_version and act:
        return f"[[card: {label} | active={act}]]"
    return f"[[card: {label}]]"


def next_card_id(existing: Set[str], start: int = 1) -> str:
    n = start
    while True:
        cand = f"c{n:03d}"
        if cand not in existing:
            return cand
        n += 1


def next_version_id(versions: List[CardVersion]) -> str:
    nums: List[int] = []
    for v in versions:
        m = re.match(r"v(\d+)$", v.version_id, re.I)
        if m:
            nums.append(int(m.group(1)))
    n = max(nums) + 1 if nums else 1
    return f"v{n}"


def is_card_line(text: str) -> bool:
    return bool(RE_CARD_LINE.match(text or ""))


def is_beat_line(text: str) -> bool:
    return bool(RE_BEAT_LINE.match(text or ""))


def _body_end(lines: List[str], start: int, is_scene_heading: Callable[[str], bool]) -> int:
    """End index of card body starting at *start* (line after marker).

    Plain cards: first line may be a draft slug; a *later* scene heading ends the body.
    Versioned cards (@vN): scene headings stay inside the body until the next card/beat
    or a blank line after content (so each version can carry its own INT./EXT. line).
    """
    j = start
    body_seen = 0
    version_mode = False
    while j < len(lines):
        nxt = lines[j]
        ns = nxt.strip()
        if not ns:
            if body_seen:
                break
            j += 1
            continue
        if is_card_line(nxt) or is_beat_line(nxt):
            break
        if RE_VER_MARK.match(ns):
            version_mode = True
            body_seen += 1
            j += 1
            continue
        if is_scene_heading(ns) and body_seen and not version_mode:
            break
        body_seen += 1
        j += 1
    return j

def list_cards_from_text(
    text: str,
    is_scene_heading: Callable[[str], bool],
) -> List[CardInfo]:
    lines = text.splitlines()
    cards: List[CardInfo] = []
    scene_heading = "Untitled Scene"
    scene_block = -1
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if is_scene_heading(stripped):
            scene_heading = stripped
            scene_block = i
            i += 1
            continue
        m = RE_CARD_LINE.match(raw)
        if m:
            card_id, card_type, inline, active_hint = parse_card_inner(m.group(1))
            body_lines: List[str] = []
            if inline:
                body_lines.append(inline)
            j = _body_end(lines, i + 1, is_scene_heading)
            for k in range(i + 1, j):
                body_lines.append(lines[k].rstrip("\n"))
            while body_lines and not body_lines[0].strip():
                body_lines.pop(0)
            while body_lines and not body_lines[-1].strip():
                body_lines.pop()
            body = "\n".join(body_lines).strip()
            active, versions = parse_versions(body, active_hint)
            cards.append(
                CardInfo(
                    block_number=i,
                    card_id=card_id,
                    card_type=card_type,
                    body=body,
                    scene_heading=scene_heading,
                    scene_block=scene_block,
                    active_version=active,
                    versions=versions,
                )
            )
            i = j
            continue
        i += 1
    return cards


def ensure_ids_in_text(
    text: str,
    is_scene_heading: Callable[[str], bool],
) -> Tuple[str, int]:
    plain = text.splitlines()
    ends_with_nl = text.endswith("\n")
    existing: Set[str] = set()
    for info in list_cards_from_text(text, is_scene_heading):
        if info.card_id:
            existing.add(info.card_id)

    assigned = 0
    out_lines: List[str] = []
    i = 0
    while i < len(plain):
        line = plain[i]
        m = RE_CARD_LINE.match(line)
        if not m:
            out_lines.append(line)
            i += 1
            continue
        card_id, card_type, inline, active = parse_card_inner(m.group(1))
        j = _body_end(plain, i + 1, is_scene_heading)
        body = "\n".join(plain[i + 1 : j]).strip()
        if inline:
            body = f"{inline}\n{body}".strip() if body else inline
        active, versions = parse_versions(body, active)
        multi = len(versions) > 1
        if not card_id:
            card_id = next_card_id(existing)
            existing.add(card_id)
            assigned += 1
        out_lines.append(
            format_card_marker(card_id, card_type, active=active, multi_version=multi)
        )
        body_out = format_versions_body(versions, active)
        if body_out:
            out_lines.extend(body_out.split("\n"))
        i = j

    new_text = "\n".join(out_lines)
    if ends_with_nl:
        new_text += "\n"
    return new_text, assigned


def write_card_block(
    text: str,
    card_block: int,
    card_id: str,
    card_type: str,
    versions: List[CardVersion],
    active: str,
    is_scene_heading: Callable[[str], bool],
) -> Tuple[str, str]:
    plain = text.splitlines()
    ends_with_nl = text.endswith("\n")
    if card_block < 0 or card_block >= len(plain) or not RE_CARD_LINE.match(plain[card_block]):
        return text, "Card not found."

    end = _body_end(plain, card_block + 1, is_scene_heading)
    active = _norm_ver(active)
    if not versions:
        versions = [CardVersion("v1", "")]
    ids = {v.version_id for v in versions}
    if active not in ids:
        active = versions[-1].version_id
    multi = len(versions) > 1
    marker = format_card_marker(card_id, card_type, active=active, multi_version=multi)
    body_out = format_versions_body(versions, active)
    new_block = [marker]
    if body_out:
        new_block.extend(body_out.split("\n"))

    out = plain[:card_block] + new_block + plain[end:]
    new_text = "\n".join(out)
    if ends_with_nl:
        new_text += "\n"
    return new_text, "Card saved"


def snapshot_version(
    versions: List[CardVersion],
    active: str,
    new_text: str,
) -> Tuple[List[CardVersion], str, bool]:
    active = _norm_ver(active)
    new_text = (new_text or "").strip()
    if not versions:
        return [CardVersion("v1", new_text)], "v1", True

    cur = next((v for v in versions if v.version_id == active), versions[-1])
    if (cur.text or "").strip() == new_text:
        return list(versions), cur.version_id, False

    versions = list(versions)
    vid = next_version_id(versions)
    versions.append(CardVersion(vid, new_text))
    return versions, vid, True


def set_active_version(
    versions: List[CardVersion],
    version_id: str,
) -> Tuple[List[CardVersion], str, str]:
    vid = _norm_ver(version_id)
    ids = {v.version_id for v in versions}
    if vid not in ids:
        fallback = versions[-1].version_id if versions else "v1"
        return versions, fallback, "Version not found."
    return versions, vid, f"Active version set to {vid}"


def _scene_range(
    lines: List[str],
    scene_block: int,
    is_scene_heading: Callable[[str], bool],
) -> Tuple[int, int]:
    if scene_block < 0 or scene_block >= len(lines):
        return -1, -1
    end = scene_block + 1
    while end < len(lines):
        if is_scene_heading(lines[end].strip()):
            break
        end += 1
    return scene_block, end


def _find_card_span_in_range(
    lines: List[str],
    start: int,
    end: int,
    card_id: str,
    card_block_hint: int,
    is_scene_heading: Callable[[str], bool],
) -> Tuple[int, int]:
    if 0 <= card_block_hint < len(lines) and start <= card_block_hint < end:
        if RE_CARD_LINE.match(lines[card_block_hint]):
            return card_block_hint, _body_end(lines, card_block_hint + 1, is_scene_heading)
    for i in range(start, end):
        m = RE_CARD_LINE.match(lines[i])
        if not m:
            continue
        cid, _, _, _ = parse_card_inner(m.group(1))
        if card_id and cid == card_id:
            return i, _body_end(lines, i + 1, is_scene_heading)
    return -1, -1


def _replace_leading_action(
    lines: List[str],
    scene_start: int,
    scene_end: int,
    card_span: Tuple[int, int],
    action_lines: List[str],
    is_scene_heading: Callable[[str], bool],
) -> List[str]:
    del is_scene_heading
    out = list(lines)
    c0, c1 = card_span

    i = scene_start + 1
    zone_start = -1
    zone_end = -1
    in_dialogue = False

    while i < scene_end and i < len(out):
        if c0 >= 0 and c0 <= i < c1:
            i = c1
            in_dialogue = False
            continue

        raw = out[i]
        s = raw.strip()
        if not s:
            if in_dialogue:
                in_dialogue = False
            if zone_start >= 0:
                zone_end = i
                break
            i += 1
            continue

        if is_card_line(raw) or is_beat_line(raw):
            if zone_start >= 0:
                zone_end = i
                break
            i += 1
            continue

        if looks_like_character(s):
            if zone_start >= 0:
                zone_end = i
                break
            in_dialogue = True
            i += 1
            continue

        if in_dialogue:
            i += 1
            continue

        if RE_PAREN.match(s) or RE_TRANSITION.match(s) or RE_SECTION.match(s):
            if zone_start >= 0:
                zone_end = i
                break
            i += 1
            continue

        if zone_start < 0:
            zone_start = i
        zone_end = i + 1
        i += 1

    action_clean = [ln.rstrip() for ln in action_lines]
    while action_clean and not action_clean[-1].strip():
        action_clean.pop()
    action_clean = [ln for ln in action_clean if ln.strip()]

    if zone_start >= 0:
        out[zone_start:zone_end] = action_clean
        return out

    insert_at = scene_start + 1
    if c0 >= 0:
        insert_at = c1

    block: List[str] = []
    if action_clean:
        if insert_at > 0 and insert_at <= len(out) and out[insert_at - 1].strip():
            block.append("")
        block.extend(action_clean)
        block.append("")
    out[insert_at:insert_at] = block
    return out


def apply_card_to_script_text(
    text: str,
    card_block: int,
    is_scene_heading: Callable[[str], bool],
    *,
    snapshot: bool = True,
) -> Tuple[str, str]:
    del snapshot
    plain = text.splitlines()
    ends_with_nl = text.endswith("\n")
    if card_block < 0 or card_block >= len(plain):
        return text, "Card not found."
    if not RE_CARD_LINE.match(plain[card_block]):
        return text, "No card marker on that line."

    cards = list_cards_from_text(text, is_scene_heading)
    info = next((c for c in cards if c.block_number == card_block), None)
    if info is None:
        return text, "Card not found."

    existing = {c.card_id for c in cards if c.card_id}
    card_id = info.card_id or next_card_id(existing)
    card_type = info.card_type or "Note"
    versions = list(info.versions) if info.versions else [CardVersion("v1", info.body)]
    active = info.active_version or "v1"

    multi = len(versions) > 1
    marker = format_card_marker(card_id, card_type, active=active, multi_version=multi)
    body_out = format_versions_body(versions, active)

    out = list(plain)
    end_body = _body_end(out, card_block + 1, is_scene_heading)
    new_block = [marker]
    if body_out:
        new_block.extend(body_out.split("\n"))
    out = out[:card_block] + new_block + out[end_body:]

    marker_at = card_block
    active_text = ""
    for v in versions:
        if v.version_id == active:
            active_text = (v.text or "").strip()
            break
    if not active_text and versions:
        active_text = (versions[-1].text or "").strip()
        active = versions[-1].version_id

    draft_slug = ""
    action_lines: List[str] = []
    if active_text:
        al = active_text.splitlines()
        if al and is_scene_heading(al[0].strip()):
            draft_slug = al[0].strip()
            action_lines = al[1:]
        else:
            action_lines = al

    msg_parts: List[str] = []
    scene_block = info.scene_block

    if draft_slug:
        if scene_block >= 0 and scene_block < marker_at:
            if out[scene_block].strip() != draft_slug:
                out[scene_block] = draft_slug
                msg_parts.append(f"Updated scene heading to {draft_slug}")
            else:
                msg_parts.append("Scene heading already matched card")
        else:
            out.insert(marker_at, "")
            out.insert(marker_at, draft_slug)
            scene_block = marker_at
            marker_at += 2
            msg_parts.append(f"Inserted scene {draft_slug}")
    elif scene_block < 0:
        msg_parts.append(
            "No scene heading on card or above it — set INT./EXT. as first line "
            "of the active version."
        )
        new_text = "\n".join(out)
        if ends_with_nl:
            new_text += "\n"
        return new_text, " · ".join(msg_parts)

    if scene_block < 0:
        new_text = "\n".join(out)
        if ends_with_nl:
            new_text += "\n"
        return new_text, " · ".join(msg_parts) if msg_parts else "Nothing to apply."

    s0, s1 = _scene_range(out, scene_block, is_scene_heading)
    c_span = _find_card_span_in_range(out, s0, s1, card_id, marker_at, is_scene_heading)

    before_join = "\n".join(out)
    out = _replace_leading_action(
        out,
        s0,
        s1 if s1 > 0 else len(out),
        c_span,
        action_lines,
        is_scene_heading,
    )
    after_join = "\n".join(out)

    if action_lines:
        if before_join != after_join:
            msg_parts.append("Updated scene action (dialogue left untouched)")
        else:
            msg_parts.append("Action already matched card")
    else:
        msg_parts.append("No action lines on active version (slug only / notes empty)")

    msg_parts.append(f"active {active}")

    new_text = after_join
    if ends_with_nl:
        new_text += "\n"
    new_text, _ = ensure_ids_in_text(new_text, is_scene_heading)
    return new_text, " · ".join(msg_parts)


def apply_with_panel_state(
    text: str,
    card_block: int,
    card_id: str,
    card_type: str,
    versions: List[CardVersion],
    active: str,
    is_scene_heading: Callable[[str], bool],
    *,
    do_snapshot_from: Optional[str] = None,
) -> Tuple[str, str, List[CardVersion], str]:
    versions = list(versions) if versions else [CardVersion("v1", "")]
    active = _norm_ver(active)
    created = False
    if do_snapshot_from is not None:
        versions, active, created = snapshot_version(versions, active, do_snapshot_from)

    text2, _ = write_card_block(
        text, card_block, card_id, card_type, versions, active, is_scene_heading
    )
    text3, msg = apply_card_to_script_text(
        text2, card_block, is_scene_heading, snapshot=False
    )
    if created:
        msg = f"Saved {active} · " + msg
    return text3, msg, versions, active


def _real_scene_starts(
    lines: List[str],
    is_scene_heading: Callable[[str], bool],
) -> List[int]:
    """Scene heading line indexes that are not inside a card body."""
    skip: Set[int] = set()
    i = 0
    while i < len(lines):
        if RE_CARD_LINE.match(lines[i]):
            end = _body_end(lines, i + 1, is_scene_heading)
            for bn in range(i + 1, end):
                skip.add(bn)
            i = end
            continue
        i += 1
    starts: List[int] = []
    for i, line in enumerate(lines):
        if i in skip:
            continue
        if is_scene_heading(line.strip()):
            starts.append(i)
    return starts


def _owned_scene_block_for_card(
    lines: List[str],
    info: CardInfo,
    is_scene_heading: Callable[[str], bool],
) -> Tuple[int, int, str]:
    """
    Return (start, end, reason) for the scene range owned by this card.

    Ownership rules (v1):
    - Prefer the nearest real scene heading *above* the card (info.scene_block).
    - That range is exclusive of the next real scene heading.
    - If the card has no parent scene, refuse (need Apply first / attach to scene).
    - If multiple cards share the same scene, moving still moves the whole scene
      (all cards in that scene travel together).
    """
    starts = _real_scene_starts(lines, is_scene_heading)
    if info.scene_block < 0 or info.scene_block not in starts:
        # Card may sit before any scene, or scene_block points at a draft slug inside body
        # Try nearest real scene above card marker.
        parent = -1
        for s in starts:
            if s < info.block_number:
                parent = s
            else:
                break
        if parent < 0:
            return -1, -1, (
                "Card has no parent scene yet. Put a scene heading above it "
                "(or Apply a draft INT./EXT. first), then reorder."
            )
        scene_block = parent
    else:
        scene_block = info.scene_block

    # end = next real scene start, or EOF
    end = len(lines)
    for s in starts:
        if s > scene_block:
            end = s
            break
    # Include trailing blank lines that sit before next scene? keep tight to next start.
    return scene_block, end, ""


def reorder_card_scene(
    text: str,
    card_block: int,
    direction: int,
    is_scene_heading: Callable[[str], bool],
) -> Tuple[str, str, int]:
    """
    Move the scene block owned by the card at card_block up (-1) or down (+1).

    Returns (new_text, message, new_card_block).
    new_card_block is the marker line index after the move (-1 if unchanged/failed).
    """
    if direction not in (-1, 1):
        return text, "Invalid reorder direction.", -1

    plain = text.splitlines()
    ends_with_nl = text.endswith("\n")
    cards = list_cards_from_text(text, is_scene_heading)
    info = next((c for c in cards if c.block_number == card_block), None)
    if info is None:
        return text, "Card not found.", -1

    starts = _real_scene_starts(plain, is_scene_heading)
    if len(starts) < 2:
        return text, "Need at least two scenes to reorder.", -1

    s0, s1, err = _owned_scene_block_for_card(plain, info, is_scene_heading)
    if err:
        return text, err, -1
    if s0 < 0:
        return text, "Could not resolve scene for this card.", -1

    # Index of this scene among real scenes
    try:
        idx = starts.index(s0)
    except ValueError:
        return text, "Scene not in document order list.", -1

    target_idx = idx + direction
    if target_idx < 0:
        return text, "Already the first scene.", -1
    if target_idx >= len(starts):
        return text, "Already the last scene.", -1

    # Build ranges for each scene: [start, end)
    ranges: List[Tuple[int, int]] = []
    for i, st in enumerate(starts):
        en = starts[i + 1] if i + 1 < len(starts) else len(plain)
        ranges.append((st, en))

    # Optional preface before first scene (title page etc.)
    preface = plain[: starts[0]] if starts else []
    chunks = [plain[a:b] for a, b in ranges]

    # Swap chunk with neighbor
    j = target_idx
    chunks[idx], chunks[j] = chunks[j], chunks[idx]

    out: List[str] = list(preface)
    for ch in chunks:
        out.extend(ch)

    # Normalize: ensure a blank line between scene chunks if both sides have content
    # (keep simple — preserve original internal spacing)

    new_text = "\n".join(out)
    if ends_with_nl:
        new_text += "\n"

    # Find new card block by id if possible, else by relative search
    new_cards = list_cards_from_text(new_text, is_scene_heading)
    new_block = -1
    if info.card_id:
        for c in new_cards:
            if c.card_id == info.card_id:
                new_block = c.block_number
                break
    if new_block < 0:
        # fallback: same type + body start
        for c in new_cards:
            if c.card_type == info.card_type and c.body == info.body:
                new_block = c.block_number
                break

    moved = "up" if direction < 0 else "down"
    heading = plain[s0].strip() if 0 <= s0 < len(plain) else "scene"
    return new_text, f"Moved scene {moved}: {heading}", new_block


def strip_cards_for_preview(
    text: str,
    is_scene_heading: Callable[[str], bool],
) -> str:
    """Remove card markers and their bodies (incl. @vN lines) for preview/PDF.

    Beat markers are also removed so planning chrome never hits the page.
    Scene headings, action, and dialogue outside card blocks are kept.
    """
    plain = text.splitlines()
    ends_with_nl = text.endswith("\n")
    out: List[str] = []
    i = 0
    while i < len(plain):
        line = plain[i]
        if RE_CARD_LINE.match(line) or RE_BEAT_LINE.match(line):
            i = _body_end(plain, i + 1, is_scene_heading)
            # Drop one following blank if we would double-space awkwardly
            if out and out[-1].strip() == "" and i < len(plain) and not plain[i].strip():
                i += 1
            continue
        out.append(line)
        i += 1
    # Collapse runs of 3+ blank lines to 2
    cleaned: List[str] = []
    blank_run = 0
    for ln in out:
        if not ln.strip():
            blank_run += 1
            if blank_run <= 2:
                cleaned.append(ln)
        else:
            blank_run = 0
            cleaned.append(ln)
    new_text = "\n".join(cleaned)
    if ends_with_nl and new_text and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text
