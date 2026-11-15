"""Read PDF annotations (highlights, notes) and tie them to words and lines."""

from __future__ import annotations

import colorsys
import sys
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

from src.layout import Word

MARKUP_TYPES = {8: "highlight", 9: "underline", 10: "squiggly", 11: "strikeout"}
NOTE_TYPES = {0: "note", 2: "freetext"}
_POPUP = 16


@dataclass
class Annotation:
    uid: int
    page: int
    kind: str  # highlight | underline | squiggly | strikeout | note | freetext | <other>
    colour: str
    rgb: tuple | None
    rect: pymupdf.Rect
    quads: list[pymupdf.Rect] = field(default_factory=list)
    content: str = ""  # the reader's own words
    position: str = ""  # left | right | inline (point annotations)
    text_parts: list[str] = field(default_factory=list)  # covered words, reading order
    linenos: list[int] = field(default_factory=list)
    anchor_text: str = ""  # what a note sits next to
    id: str = ""  # display id, assigned at the end

    @property
    def is_markup(self) -> bool:
        return self.kind in MARKUP_TYPES.values()

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)

    @property
    def hex(self) -> str | None:
        if not self.rgb:
            return None
        return "#" + "".join(f"{round(c * 255):02x}" for c in self.rgb[:3])


# ---------------------------------------------------------------------------
# Colour and position
# ---------------------------------------------------------------------------


def rgb_to_colour(rgb: tuple | None) -> str:
    """Map an RGB float tuple (0–1 each) to a human-readable colour name.

    Works by hue so that the pastel shades used by Preview and the saturated
    ones used by Okular land on the same names.
    """
    if rgb is None or len(rgb) < 3:
        return "yellow"
    r, g, b = rgb[:3]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360
    if v < 0.2:
        return "black"
    if s < 0.12:
        return "grey"
    if hue < 15 or hue >= 350:
        return "red"
    if hue < 38:
        return "orange"
    if hue < 75:
        return "yellow"
    if hue < 170:
        return "green"
    if hue < 260:
        return "blue"
    if hue <= 310:
        return "purple"
    return "pink"


def note_position(rect: pymupdf.Rect, page_width: float) -> str:
    """Classify a note's horizontal position as left, right, or inline."""
    if rect.x0 < page_width * 0.35:
        return "left"
    if rect.x0 > page_width * 0.65:
        return "right"
    return "inline"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def read_annotations(
    page: pymupdf.Page, page_num: int, next_uid: int = 0
) -> tuple[list[Annotation], Counter]:
    """Return the usable annotations on a page and a count of skipped ones."""
    anns: list[Annotation] = []
    skipped: Counter = Counter()
    by_xref: dict[int, Annotation] = {}
    replies: list[tuple[int, str]] = []

    for i, annot in enumerate(page.annots() or []):
        try:
            atype, aname = annot.type[0], annot.type[1]
            if atype == _POPUP:
                continue
            rect = pymupdf.Rect(annot.rect)
            content = (annot.info.get("content") or "").strip()
            if annot.irt_xref:
                if content:
                    replies.append((annot.irt_xref, content))
                continue
            if not rect.intersects(page.rect):
                skipped["off-page"] += 1  # Preview parks abandoned notes here
                continue
            colours = annot.colors or {}
            rgb = colours.get("stroke") or colours.get("fill") or None

            if atype in MARKUP_TYPES:
                verts = annot.vertices or []
                quads = [pymupdf.Quad(verts[k : k + 4]).rect for k in range(0, len(verts) - 3, 4)]
                ann = Annotation(
                    uid=next_uid + len(anns),
                    page=page_num,
                    kind=MARKUP_TYPES[atype],
                    colour=rgb_to_colour(rgb),
                    rgb=tuple(rgb) if rgb else None,
                    rect=rect,
                    quads=quads or [rect],
                    content=content,
                )
            else:
                kind = NOTE_TYPES.get(atype, aname.lower())
                if kind in ("note", "freetext") and not content:
                    skipped["empty"] += 1
                    continue
                if atype not in NOTE_TYPES:
                    print(
                        f"  WARNING: unclassified annotation type {atype} ({aname}) "
                        f"on page {page_num} — listed without text",
                        file=sys.stderr,
                    )
                ann = Annotation(
                    uid=next_uid + len(anns),
                    page=page_num,
                    kind=kind,
                    colour=rgb_to_colour(rgb) if rgb else "uncoloured",
                    rgb=tuple(rgb) if rgb else None,
                    rect=rect,
                    content=content,
                    position=note_position(rect, page.rect.width),
                )
            anns.append(ann)
            by_xref[annot.xref] = ann
        except Exception as exc:
            print(
                f"  WARNING: failed to extract annotation index {i} on page {page_num}: {exc}",
                file=sys.stderr,
            )

    for xref, content in replies:
        parent = by_xref.get(xref)
        if parent is not None:
            parent.content = (parent.content + "\n↳ " + content).strip()
    return anns, skipped


def mark_words(words: list[Word], anns: list[Annotation]) -> None:
    """Record on each word which markup annotations cover its centre."""
    for ann in anns:
        if not ann.is_markup:
            continue
        hit = False
        for quad in ann.quads:
            for w in words:
                cx, cy = (w.x0 + w.x1) / 2, (w.y0 + w.y1) / 2
                if quad.x0 <= cx <= quad.x1 and quad.y0 - 1 <= cy <= quad.y1 + 1:
                    hit = True
                    if ann.uid not in w.anns:
                        w.anns.append(ann.uid)
        if not hit:
            # A mark narrower than a word (one symbol): take the word it overlaps most.
            def overlap(w: Word) -> float:
                return max(
                    max(0.0, min(w.x1, q.x1) - max(w.x0, q.x0))
                    * max(0.0, min(w.y1, q.y1) - max(w.y0, q.y0))
                    for q in ann.quads
                )

            best = max(words, key=overlap, default=None)
            if best is not None and overlap(best) > 0:
                best.anns.append(ann.uid)


def assign_ids(anns: list[Annotation]) -> list[Annotation]:
    """Sort annotations by position in the paper and number them A1, A2, …"""
    ordered = sorted(
        anns,
        key=lambda a: (a.page, min(a.linenos) if a.linenos else 10**6, a.rect.y0, a.rect.x0),
    )
    for n, ann in enumerate(ordered, start=1):
        ann.id = f"A{n}"
    return ordered
