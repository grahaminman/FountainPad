"""
cards.py — Card marker parse/format, ids, and apply-to-script helpers.

Fountain markers (notes to the draft, not instructions):

  [[card: id=c001 | Note]]
  Optional body lines until the next scene heading, card, beat, or blank.

Legacy markers without id still parse:

  [[card: Goal]]
  [[card: Goal body text]]

Apply-to-script (Phase B first cut)
  If the card body starts with a scene-heading-shaped line, that slug is
  promoted into the screenplay (insert or update the parent scene heading).
  Remaining body lines stay as card notes under the marker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

RE_CARD_LINE = re.compile(r"^(?:\s*)\[\[card:\s*(.*?)\]\]\s*$", re.IGNORECASE)
RE_BEAT_LINE = re.compile(r"^(?:\s*)\[\[beat:\s*(.*?)\]\]\s*$", re.IGNORECASE)
RE_ID = re.compile(r"^id\s*=\s*([A-Za-z0-9_-]+)$", re.IGNORECASE)
RE_ID_TOKEN = re.compile(r"id\s*=\s*([A-Za-z0-9_-]+)", re.IGNORECASE)

VALID_TYPES = frozenset({"Goal", "Conflict", "Turn", "Note", "Card"})


@dataclass
class CardInfo:
    """One card marker + body in document order."""

    block_number: int
    card_id: str
    card_type: str
    body: str
    scene_heading: str
    scene_block: int  # -1 if none above

    @property
    def draft_slug(self) -> str:
        """First body line if it looks like a scene heading; else empty."""
        if not self.body:
            return ""
        return self.body.splitlines()[0].strip()

    def display_label(self) -> str:
        slug = self.draft_slug
        if slug and looks_like_scene(slug):
            rest = "\n".join(self.body.splitlines()[1:]).strip()
            bit = rest.splitlines()[0] if rest else ""
            core = f"{self.card_type}: {slug}" + (f" — {bit}" if bit else "")
        else:
            bit = self.body.splitlines()[0] if self.body else ""
            core = f"{self.card_type}: {bit}" if bit else self.card_type
        if self.card_id:
            return f"[{self.card_id}] {core}"
        return core


def looks_like_scene(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith(".") and not t.startswith(".."):
        return True
    return bool(
        re.match(
            r"^(?:INT|EXT|EST|I/?E|INT\./EXT|INT/EXT)[\.\s].+",
            t,
            re.IGNORECASE,
        )
    )


def parse_card_inner(inner: str) -> tuple[str, str, str]:
    """Parse marker interior. Returns (card_id, card_type, inline_text)."""
    raw = (inner or "").strip()
    if not raw:
        return "", "Note", ""

    card_id = ""
    rest = raw

    if "|" in raw:
        left, _, right = raw.partition("|")
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
                rest = raw
    else:
        m2 = RE_ID_TOKEN.search(raw)
        if m2:
            card_id = m2.group(1)
            rest = (raw[: m2.start()] + raw[m2.end() :]).strip(" |")

    rest = rest.strip()
    if not rest:
        return card_id, "Note", ""

    first, _, more = rest.partition(" ")
    if first in VALID_TYPES:
        return card_id, first, more.strip()
    if not more and len(first) <= 24 and first[:1].isupper() and first.replace("-", "").isalnum():
        return card_id, first, ""
    if first[:1].isupper() and first.isalpha() and len(first) <= 16:
        return card_id, first, more.strip()
    return card_id, "Note", rest


def format_card_marker(card_id: str, card_type: str, inline: str = "") -> str:
    """Build a single marker line (no trailing newline)."""
    ctype = (card_type or "Note").strip() or "Note"
    cid = (card_id or "").strip()
    inline = (inline or "").strip()
    label = f"{ctype} {inline}".strip() if inline else ctype
    if cid:
        return f"[[card: id={cid} | {label}]]"
    return f"[[card: {label}]]"


def next_card_id(existing: set[str], start: int = 1) -> str:
    n = start
    while True:
        cand = f"c{n:03d}"
        if cand not in existing:
            return cand
        n += 1


def is_card_line(text: str) -> bool:
    return bool(RE_CARD_LINE.match(text or ""))


def is_beat_line(text: str) -> bool:
    return bool(RE_BEAT_LINE.match(text or ""))


def list_cards_from_text(
    text: str,
    is_scene_heading: Callable[[str], bool],
) -> list[CardInfo]:
    """Parse full document text into CardInfo list (0-based line = block number)."""
    lines = text.splitlines()
    cards: list[CardInfo] = []
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
            card_id, card_type, inline = parse_card_inner(m.group(1))
            body_lines: list[str] = []
            if inline:
                body_lines.append(inline)
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                ns = nxt.strip()
                if not ns:
                    if body_lines:
                        break
                    j += 1
                    continue
                if is_card_line(nxt) or is_beat_line(nxt):
                    break
                # First body line may be a draft scene slug (cards-first).
                # A later scene heading ends the body (next real scene).
                if is_scene_heading(ns) and body_lines:
                    break
                body_lines.append(ns)
                j += 1
            body = "\n".join(body_lines).strip()
            cards.append(
                CardInfo(
                    block_number=i,
                    card_id=card_id,
                    card_type=card_type,
                    body=body,
                    scene_heading=scene_heading,
                    scene_block=scene_block,
                )
            )
            i = j
            continue
        i += 1
    return cards


def ensure_ids_in_text(
    text: str,
    is_scene_heading: Callable[[str], bool],
) -> tuple[str, int]:
    """Rewrite card markers missing ids. Returns (new_text, number_assigned)."""
    plain = text.splitlines()
    ends_with_nl = text.endswith("\n")
    existing: set[str] = set()
    for info in list_cards_from_text(text, is_scene_heading):
        if info.card_id:
            existing.add(info.card_id)

    assigned = 0
    out_lines: list[str] = []
    for line in plain:
        m = RE_CARD_LINE.match(line)
        if not m:
            out_lines.append(line)
            continue
        card_id, card_type, inline = parse_card_inner(m.group(1))
        if not card_id:
            card_id = next_card_id(existing)
            existing.add(card_id)
            assigned += 1
        out_lines.append(format_card_marker(card_id, card_type, inline))
    new_text = "\n".join(out_lines)
    if ends_with_nl:
        new_text += "\n"
    return new_text, assigned


def apply_card_to_script_text(
    text: str,
    card_block: int,
    is_scene_heading: Callable[[str], bool],
) -> tuple[str, str]:
    """
    Promote draft slug from card body into the screenplay.

    Returns (new_text, status_message).
    """
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

    body_lines = [ln for ln in info.body.splitlines() if ln.strip()] if info.body else []
    draft_slug = ""
    note_lines: list[str] = []
    if body_lines and is_scene_heading(body_lines[0].strip()):
        draft_slug = body_lines[0].strip()
        note_lines = body_lines[1:]
    else:
        note_lines = list(body_lines)

    out = list(plain)
    out[card_block] = format_card_marker(card_id, card_type)

    # Remove old body under marker (same rules as list_cards_from_text:
    # first line may be a draft scene slug; later scenes end the body).
    end = card_block + 1
    body_seen = 0
    while end < len(out):
        ns = out[end].strip()
        if not ns:
            if body_seen:
                break
            end += 1
            continue
        if is_card_line(out[end]) or is_beat_line(out[end]):
            break
        if is_scene_heading(ns) and body_seen:
            break
        body_seen += 1
        end += 1
    del out[card_block + 1 : end]
    for offset, nl in enumerate(note_lines):
        out.insert(card_block + 1 + offset, nl)

    msg_parts: list[str] = []
    # After body rewrite, card still at card_block (unless we insert above later)
    marker_at = card_block

    if draft_slug:
        if info.scene_block >= 0 and info.scene_block < marker_at:
            sb = info.scene_block
            if out[sb].strip() != draft_slug:
                out[sb] = draft_slug
                msg_parts.append(f"Updated scene heading to {draft_slug}")
            else:
                msg_parts.append("Scene heading already matched card")
        else:
            out.insert(marker_at, "")
            out.insert(marker_at, draft_slug)
            msg_parts.append(f"Inserted scene {draft_slug}")
    else:
        msg_parts.append(
            "No scene-heading line on the card — ensured id only. "
            "Put INT./EXT. ... as the first body line, then Apply again."
        )

    new_text = "\n".join(out)
    if ends_with_nl:
        new_text += "\n"
    new_text, _ = ensure_ids_in_text(new_text, is_scene_heading)
    return new_text, " · ".join(msg_parts)

