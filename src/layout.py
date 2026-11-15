"""Page layout: words, visual lines, review line numbers, blocks, reading order.

Everything here works on word boxes so that annotations can later be matched to
the exact words they cover.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

# Expand ligatures ("ﬁ" -> "fi"); keep everything else as for word extraction.
TEXT_FLAGS = pymupdf.TEXTFLAGS_WORDS & ~pymupdf.TEXT_PRESERVE_LIGATURES

_LINENO_RE = re.compile(r"^\d{3,4}$")
_MIN_LINENOS_PER_PAGE = 5  # fewer margin numbers than this: not a review ruler


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    anns: list[int] = field(default_factory=list)  # annotation uids covering it
    lineno: int | None = None


@dataclass
class Line:
    words: list[Word]
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool
    lineno: int | None = None

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class Block:
    lines: list[Line]
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    col: str = "full"  # "left" | "right" | "full"

    def __post_init__(self) -> None:
        self.refit()

    def refit(self) -> None:
        self.x0 = min(ln.x0 for ln in self.lines)
        self.y0 = min(ln.y0 for ln in self.lines)
        self.x1 = max(ln.x1 for ln in self.lines)
        self.y1 = max(ln.y1 for ln in self.lines)

    @property
    def text(self) -> str:
        return " ".join(ln.text for ln in self.lines)

    @property
    def n_words(self) -> int:
        return sum(len(ln.words) for ln in self.lines)

    @property
    def size(self) -> float:
        """Dominant font size, weighted by characters."""
        weights: dict[float, int] = {}
        for ln in self.lines:
            weights[ln.size] = weights.get(ln.size, 0) + len(ln.text)
        return max(weights, key=weights.get)

    @property
    def bold(self) -> bool:
        total = sum(len(ln.text) for ln in self.lines)
        bold = sum(len(ln.text) for ln in self.lines if ln.bold)
        return bold > total / 2 if total else False

    @property
    def has_lineno(self) -> bool:
        return any(ln.lineno is not None for ln in self.lines)

    @property
    def words(self) -> list[Word]:
        return [w for ln in self.lines for w in ln.words]


@dataclass
class PageLayout:
    width: float
    height: float
    blocks: list[Block]
    has_linenos: bool


# ---------------------------------------------------------------------------
# Raw lines -> visual lines
# ---------------------------------------------------------------------------


def _raw_line(dline: dict, words: list[Word]) -> Line:
    sizes: dict[float, int] = {}
    bold = total = 0
    for span in dline["spans"]:
        n = len(span["text"].strip())
        if not n:
            continue
        size = round(span["size"], 1)
        sizes[size] = sizes.get(size, 0) + n
        total += n
        if span["flags"] & 16:
            bold += n
    x0, y0, x1, y1 = dline["bbox"]
    return Line(
        words=words,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        size=max(sizes, key=sizes.get) if sizes else 0.0,
        bold=bold > total / 2 if total else False,
    )


def cluster_lines(raw: list[Line], strict: bool = False) -> list[Line]:
    """Merge raw lines that share a baseline row into visual lines.

    PyMuPDF splits one printed line into several "lines" when it contains
    wide gaps, superscripts or subscripts. Lines that overlap vertically are
    merged and their words ordered left to right.
    """
    clusters: list[list[Line]] = []
    extents: list[tuple[float, float, float]] = []  # y0, y1, size of main text
    for ln in sorted(raw, key=lambda r: ((r.y0 + r.y1) / 2, r.x0)):
        if clusters:
            cy0, cy1, csize = extents[-1]
            overlap = min(cy1, ln.y1) - max(cy0, ln.y0)
            # strict: a tall bracket spanning two equation rows must not weld them together
            centred = cy0 <= (ln.y0 + ln.y1) / 2 <= cy1
            if overlap >= 0.4 * min(ln.y1 - ln.y0, cy1 - cy0) and (centred or not strict):
                clusters[-1].append(ln)
                if ln.size >= 0.8 * csize:  # sub/superscripts do not stretch the row
                    extents[-1] = (min(cy0, ln.y0), max(cy1, ln.y1), max(csize, ln.size))
                continue
        clusters.append([ln])
        extents.append((ln.y0, ln.y1, ln.size))

    out: list[Line] = []
    for members in clusters:
        words = sorted((w for m in members for w in m.words), key=lambda w: w.x0)
        main = max(members, key=lambda m: len(m.text))
        out.append(
            Line(
                words=words,
                x0=min(m.x0 for m in members),
                y0=min(m.y0 for m in members),
                x1=max(m.x1 for m in members),
                y1=max(m.y1 for m in members),
                size=main.size,
                bold=main.bold,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Page parsing
# ---------------------------------------------------------------------------


def classify_col(x0: float, x1: float, page_width: float) -> str:
    mid = page_width / 2
    if x0 < mid - 10 and x1 > mid + 10:
        return "full"
    return "left" if (x0 + x1) / 2 < mid else "right"


def parse_page(page: pymupdf.Page) -> PageLayout:
    """Return the text blocks of a page with line numbers stripped and attached."""
    width, height = page.rect.width, page.rect.height
    tp = page.get_textpage(flags=TEXT_FLAGS)
    dict_blocks = page.get_text("dict", textpage=tp)["blocks"]

    by_line: dict[tuple[int, int], list[Word]] = {}
    for x0, y0, x1, y1, text, bno, lno, _ in page.get_text("words", textpage=tp):
        by_line.setdefault((bno, lno), []).append(Word(x0, y0, x1, y1, text))

    raw_blocks: list[list[Line]] = []
    numbers: list[tuple[str, float, int]] = []  # (side, y centre, value)
    for bno, block in enumerate(dict_blocks):
        if block["type"] != 0:
            continue
        raw: list[Line] = []
        for lno, dline in enumerate(block["lines"]):
            words = by_line.get((bno, lno))
            if not words:
                continue
            dx, dy = dline.get("dir", (1.0, 0.0))
            if abs(dy) > 0.1 or dx < 0:  # rotated text, e.g. the arXiv stamp
                continue
            ln = _raw_line(dline, words)
            text = ln.text.strip()
            in_margin = ln.x1 < 0.065 * width or ln.x0 > 0.935 * width
            if in_margin and _LINENO_RE.match(text):
                side = "left" if ln.x1 < width / 2 else "right"
                numbers.append((side, (ln.y0 + ln.y1) / 2, int(text)))
                continue
            raw.append(ln)
        if raw:
            raw_blocks.append(raw)

    has_linenos = len(numbers) >= _MIN_LINENOS_PER_PAGE
    blocks: list[Block] = []
    for raw in raw_blocks:
        block = Block(cluster_lines(raw))
        # Page-number footer
        if block.y0 > 0.9 * height and re.fullmatch(r"[\d\s]+", block.text):
            continue
        block.col = classify_col(block.x0, block.x1, width)
        blocks.append(block)

    if has_linenos:
        _attach_linenos(blocks, numbers, width)
    return PageLayout(width, height, blocks, has_linenos)


def _attach_linenos(
    blocks: list[Block], numbers: list[tuple[str, float, int]], width: float
) -> None:
    """Give each visual line the margin number printed at its height.

    Left-margin numbers belong to the left column, right-margin numbers to the
    right column. Each number is used once, by the closest line.
    """
    lines = [ln for b in blocks for ln in b.lines]
    used: set[int] = set()
    for side, yc, value in numbers:
        best, best_d = None, 3.5
        for i, ln in enumerate(lines):
            if i in used:
                continue
            ln_side = "left" if (ln.x0 + ln.x1) / 2 < width / 2 else "right"
            if ln_side != side:
                continue
            d = abs((ln.y0 + ln.y1) / 2 - yc)
            if d < best_d:
                best, best_d = i, d
        if best is not None:
            used.add(best)
            lines[best].lineno = value
            for w in lines[best].words:
                w.lineno = value


# ---------------------------------------------------------------------------
# Fragment merging and reading order
# ---------------------------------------------------------------------------


def merge_row_fragments(blocks: list[Block]) -> list[Block]:
    """Merge blocks of one column that sit side by side (display equations).

    PyMuPDF returns the pieces of a display equation as separate small blocks.
    Ordinary paragraphs in the same column never overlap vertically, so any
    real vertical overlap within a column marks fragments of one object.
    """
    out = sorted(blocks, key=lambda b: (b.col, b.y0, b.x0))
    merged_any = True
    while merged_any:
        merged_any = False
        for i, a in enumerate(out):
            for j in range(i + 1, len(out)):
                b = out[j]
                if a.col != b.col or a.col == "full":
                    continue
                overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
                side_by_side = overlap >= 0.3 * min(a.y1 - a.y0, b.y1 - b.y0)
                # e.g. the "q∈Q" set under a sum sign
                tiny = b.n_words <= 3 and not b.has_lineno and b.size <= 0.8 * a.size
                below = tiny and 0 <= b.y0 - a.y1 < 4 and a.x0 - 2 <= b.x0 <= a.x1
                if not (side_by_side or below):
                    continue
                sources = a.lines + b.lines
                a.lines = cluster_lines(sources, strict=True)
                _carry_linenos(a.lines, sources)
                a.refit()
                del out[j]
                merged_any = True
                break
            if merged_any:
                break
    return out


def _carry_linenos(merged: list[Line], sources: list[Line]) -> None:
    for ln in merged:
        for src in sources:
            if src.lineno is not None and src.y0 < ln.y1 and src.y1 > ln.y0:
                ln.lineno = src.lineno if ln.lineno is None else min(ln.lineno, src.lineno)
        for w in ln.words:
            w.lineno = ln.lineno


def reading_order(items: list, page_width: float) -> list:
    """Sort items (anything with x0/y0/x1/y1/col) into reading order.

    Full-width items split the page into horizontal bands. Inside a band the
    left column is read top to bottom, then the right column.
    """
    fulls = sorted((it for it in items if it.col == "full"), key=lambda it: it.y0)

    def key(it):
        if it.col == "full":
            return (2 * fulls.index(it) + 1, 0, it.y0, it.x0)
        yc = (it.y0 + it.y1) / 2
        band = sum(1 for f in fulls if (f.y0 + f.y1) / 2 < yc)
        return (2 * band, 0 if it.col == "left" else 1, it.y0, it.x0)

    return sorted(items, key=key)


# ---------------------------------------------------------------------------
# Hyphenation
# ---------------------------------------------------------------------------

_EDGE_PUNCT_RE = re.compile(r"^\W+|\W+$")


def build_vocab(words: list[str]) -> set[str]:
    """Lower-cased word forms of the document, used to undo line-end hyphens."""
    return {_EDGE_PUNCT_RE.sub("", w).lower() for w in words} - {""}


def join_hyphenated(head: str, tail: str, vocab: set[str]) -> str:
    """Join 'exter-' + 'nal' -> 'external', but 'training-' + 'free,' -> 'training-free,'.

    The document's own vocabulary decides: if the joined form occurs elsewhere
    it is a broken word; if the hyphenated form occurs it is a real compound.
    """
    stem = head[:-1]
    a = _EDGE_PUNCT_RE.sub("", stem).lower()
    b = _EDGE_PUNCT_RE.sub("", tail).lower()
    if a + b in vocab:
        return stem + tail
    if f"{a}-{b}" in vocab or "-" in stem or not tail[:1].islower():
        return head + tail
    if len(a) >= 4 and len(b) >= 4 and a in vocab and b in vocab:
        return head + tail  # two words of the paper: a compound such as relevance-weighted
    return stem + tail
