"""Find figures and tables: a caption plus the graphics and labels it belongs to."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

from src.layout import Block, Line, classify_col, cluster_lines

CAPTION_RE = re.compile(r"^(Figure|Fig\.|Table|Algorithm|Listing)\s*(\d+)\s*[:.]", re.IGNORECASE)

_CHAIN_GAP = 40.0  # max vertical gap between a caption and its nearest graphic
_ADJACENT = 8.0  # labels this close outside the graphics still belong to the float
_CELL_GAP = 5.5  # horizontal gap that separates two table cells


@dataclass
class Float:
    kind: str  # "figure" | "table" | "box" (uncaptioned framed text)
    label: str  # "2", or "?" when no caption was matched
    caption: Block | None
    inner: list[Block] = field(default_factory=list)  # text inside the figure/table
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    col: str = "full"

    def rows(self) -> list[str]:
        """Table text as rows, cells separated by ' | '."""
        lines = cluster_lines([ln for b in self.inner for ln in b.lines])
        rows = []
        for ln in sorted(lines, key=lambda r: r.y0):
            cells, current = [], []
            for prev, w in zip([None] + ln.words[:-1], ln.words):
                if prev is not None and w.x0 - prev.x1 > _CELL_GAP:
                    cells.append(" ".join(current))
                    current = []
                current.append(w.text)
            cells.append(" ".join(current))
            rows.append(" | ".join(cells))
        return rows


def text_lines(blocks: list[Block]) -> list[str]:
    """Plain text of blocks, one printed line per entry."""
    return [ln.text for ln in lines_of(blocks)]


def caption_match(block: Block) -> re.Match | None:
    return CAPTION_RE.match(block.lines[0].text.strip()) if block.lines else None


def _graphics(page: pymupdf.Page, ann_rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Visible extent of vector drawings and images, excluding annotation appearances.

    Plots often draw shapes larger than the figure and clip them, so each
    drawing is cut to the clip regions that enclose it.
    """
    page_area = page.rect.width * page.rect.height
    rects: list[pymupdf.Rect] = []
    clips: list[tuple[int, tuple[float, float, float, float]]] = []  # (level, scissor)
    for d in page.get_drawings(extended=True):
        level = d.get("level", 0)
        while clips and clips[-1][0] >= level:
            clips.pop()
        if d.get("type") == "clip":
            box = _intersect(tuple(d["scissor"]), clips[-1][1] if clips else None)
            clips.append((level, box or (0.0, 0.0, 0.0, 0.0)))
            continue
        if "rect" not in d or d.get("type") == "group":
            continue
        box = _intersect(tuple(d["rect"]), clips[-1][1] if clips else None)
        if box is None:
            continue
        r = pymupdf.Rect(box)
        if r.width * r.height > 0.7 * page_area:
            continue
        if any((a + (-3, -3, 3, 3)).contains(r) for a in ann_rects):
            continue  # a highlight or note icon, not part of the paper
        rects.append(r)
    for info in page.get_image_info():
        rects.append(pymupdf.Rect(info["bbox"]))
    return rects


def _intersect(a: tuple, b: tuple | None) -> tuple | None:
    """Intersection of two boxes; zero-width or zero-height results (rules) are kept."""
    if b is None:
        return a
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return (x0, y0, x1, y1) if x1 >= x0 and y1 >= y0 else None


def _is_body(block: Block, has_linenos: bool, body_size: float, col_width: float) -> bool:
    """Running text of the paper, as opposed to labels inside a figure or table."""
    if has_linenos:
        return block.has_lineno  # the review ruler numbers body lines only
    return (
        block.n_words >= 12
        and (block.x1 - block.x0) >= 0.75 * col_width
        and block.size >= body_size - 0.7
    )


def detect_floats(
    page: pymupdf.Page,
    blocks: list[Block],
    ann_rects: list[pymupdf.Rect],
    body_size: float,
    has_linenos: bool,
) -> tuple[list[Float], list[Block]]:
    """Split blocks into floats and the remaining body blocks."""
    width = page.rect.width
    mid = width / 2
    col_width = 0.37 * width
    graphics = _graphics(page, ann_rects)
    claimed: set[int] = set()

    captions = sorted(
        (b for b in blocks if caption_match(b) and not (has_linenos and b.has_lineno)),
        key=lambda b: b.y0,
    )
    caption_ids = {id(b) for b in captions}
    taken: set[int] = set(caption_ids)
    floats: list[Float] = []

    for cap in captions:
        m = caption_match(cap)
        kind = "table" if m.group(1).lower() == "table" else "figure"
        sx0, sx1 = {"full": (0, width), "left": (0, mid), "right": (mid, width)}[cap.col]

        def in_span(x0: float, x1: float) -> bool:
            return sx0 - 2 <= (x0 + x1) / 2 <= sx1 + 2

        others = [b for b in blocks if id(b) not in taken and in_span(b.x0, b.x1)]
        barriers = [b for b in others if _is_body(b, has_linenos, body_size, col_width)]
        barrier_ids = {id(b) for b in barriers}
        barriers += [c for c in captions if c is not cap and in_span(c.x0, c.x1)]
        limit_up = max((b.y1 for b in barriers if b.y1 <= cap.y0 + 2), default=0.0)
        limit_down = min((b.y0 for b in barriers if b.y0 >= cap.y1 - 2), default=page.rect.height)

        cands = [
            (i, g)
            for i, g in enumerate(graphics)
            if i not in claimed and g.x0 >= sx0 - 5 and g.x1 <= sx1 + 5
        ]
        up = _chain(cands, cap.y0, limit_up, upward=True)
        down = _chain(cands, cap.y1, limit_down, upward=False)
        chosen, upward = (up, True) if up else (down, False)

        inner: list[Block] = []
        if chosen:
            claimed.update(i for i, _ in chosen)
            # min/max by hand: table rules have zero height and vanish in a Rect union
            lo = min(g.y0 for _, g in chosen) if upward else cap.y1
            hi = cap.y0 if upward else max(g.y1 for _, g in chosen)
            for b in others:
                if id(b) in barrier_ids:
                    continue
                yc = (b.y0 + b.y1) / 2
                if lo - _ADJACENT <= yc <= hi + _ADJACENT:
                    inner.append(b)
        else:
            # No graphics (e.g. a rule-less table): take the loose labels next to the caption.
            inner = _adjacent_labels(others, barrier_ids, cap, True, has_linenos)
            if not inner and kind == "table":
                inner = _adjacent_labels(others, barrier_ids, cap, False, has_linenos)

        taken.update(id(b) for b in inner)
        fl = Float(kind=kind, label=m.group(2), caption=cap, inner=inner)
        parts = [cap] + inner
        fl.x0 = min(p.x0 for p in parts)
        fl.y0 = min([p.y0 for p in parts] + [g.y0 for _, g in chosen])
        fl.x1 = max(p.x1 for p in parts)
        fl.y1 = max([p.y1 for p in parts] + [g.y1 for _, g in chosen])
        fl.col = cap.col if cap.col == "full" else classify_col(fl.x0, fl.x1, width)
        floats.append(fl)

    floats += _uncaptioned(page, blocks, taken, ann_rects, claimed, graphics, has_linenos,
                           body_size, col_width)
    remaining = [b for b in blocks if id(b) not in taken]
    return floats, remaining


def _uncaptioned(page, blocks, taken, ann_rects, claimed, graphics, has_linenos, body_size,
                 col_width) -> list[Float]:
    """Sizeable graphics that no caption claimed: kept as BOX (with text) or FIGURE ?."""
    left = [g for i, g in enumerate(graphics) if i not in claimed]
    drawings = [{"rect": g} for g in left if g.width > 0 or g.height > 0]
    if not drawings:
        return []
    try:
        clusters = page.cluster_drawings(drawings=drawings, x_tolerance=8, y_tolerance=8)
    except Exception:
        return []
    out: list[Float] = []
    free = [b for b in blocks if id(b) not in taken]
    for region in clusters:
        if region.width < 80 or region.height < 40:
            continue
        inside = [
            b for b in free
            if region.contains(pymupdf.Point((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2))
        ]
        if any(_is_body(b, has_linenos, body_size, col_width) for b in inside):
            continue  # a frame or shading around running text
        taken.update(id(b) for b in inside)
        # A frame around text (a prompt or code listing) keeps its text; a bare graphic does not.
        boxed_text = sum(b.n_words for b in inside) >= 5
        out.append(
            Float(
                kind="box" if boxed_text else "figure", label="" if boxed_text else "?",
                caption=None, inner=inside,
                x0=region.x0, y0=region.y0, x1=region.x1, y1=region.y1,
                col=classify_col(region.x0, region.x1, page.rect.width),
            )
        )
    return out


def _chain(
    cands: list[tuple[int, pymupdf.Rect]], start: float, limit: float, upward: bool
) -> list[tuple[int, pymupdf.Rect]]:
    """Graphics between the caption edge and the next body text or caption.

    The nearest one must be close to the caption; beyond that the body-text
    limit is what ends the float, because tables have long stretches without
    any rule. Graphics are cut at the caption edge: plots often contain shapes
    drawn larger than the figure and clipped.
    """
    chosen: list[tuple[int, pymupdf.Rect]] = []
    for i, g in cands:
        if upward and g.y0 >= limit - 2 and g.y0 < start:
            chosen.append((i, pymupdf.Rect(g.x0, g.y0, g.x1, min(g.y1, start))))
        elif not upward and g.y1 <= limit + 2 and g.y1 > start:
            chosen.append((i, pymupdf.Rect(g.x0, max(g.y0, start), g.x1, g.y1)))
    if not chosen:
        return []
    nearest = min(start - g.y1 if upward else g.y0 - start for _, g in chosen)
    return chosen if nearest <= _CHAIN_GAP else []


def _adjacent_labels(
    others: list[Block], barrier_ids: set[int], cap: Block, upward: bool, has_linenos: bool
) -> list[Block]:
    out: list[Block] = []
    edge = cap.y0 if upward else cap.y1
    ordered = sorted(others, key=lambda b: -b.y1 if upward else b.y0)
    for b in ordered:
        if (upward and b.y1 > cap.y0 + 2) or (not upward and b.y0 < cap.y1 - 2):
            continue
        gap = edge - b.y1 if upward else b.y0 - edge
        if id(b) in barrier_ids or gap > 25 or (not has_linenos and b.n_words >= 8):
            break
        out.append(b)
        edge = b.y0 if upward else b.y1
    return out


def lines_of(blocks: list[Block]) -> list[Line]:
    return [ln for b in sorted(blocks, key=lambda b: (b.y0, b.x0)) for ln in b.lines]
