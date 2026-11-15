"""Extract an annotated PDF into Markdown with highlights and notes in place.

Usage:
    uv run extract papers/foo.pdf [--full]

Writes: outputs/extracted/foo.md and outputs/extracted/foo.annotations.json

Works on single- and two-column papers, and on review copies with margin line
numbers (ACL/ARR), whose numbers are stripped from the text and reported as
line references. Annotations from Preview and Okular are both read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from src.annotations import Annotation, assign_ids, mark_words, read_annotations
from src.floats import CAPTION_RE, Float, detect_floats, lines_of, text_lines
from src.layout import (
    Block,
    Line,
    PageLayout,
    build_vocab,
    merge_row_fragments,
    parse_page,
    reading_order,
)
from src.render import (
    annotations_records,
    annotations_table,
    flow,
    line_range,
    note_tag,
    plain_text,
)

pymupdf.TOOLS.mupdf_display_errors(False)  # malformed-object chatter from figures

# ---------------------------------------------------------------------------
# Structural regexes
# ---------------------------------------------------------------------------

_NUMBERED_HEADING_RE = re.compile(r"^((?:\d+|[A-Z])(?:\.\d+)*)\.?\s+\S")
_NAMED_HEADING_RE = re.compile(
    r"^(?:Abstract|Introduction|Related Work|Background|Method(?:ology)?|"
    r"Experiment(?:s|al Setup)?|Results?|Discussion|Conclusions?|"
    r"Limitations?|Ethic\w*|Acknowledge?ments?|Appendix|References|Bibliography)\b",
    re.IGNORECASE,
)
_REFERENCES_RE = re.compile(r"^(?:References|Bibliography)\s*$", re.IGNORECASE)

MATH_SYMBOLS = set("∈≤≥≠×∑∏∫πθφσλρεϕ→←∇∂≈")


def is_display_equation(text: str) -> bool:
    """Return True if text looks like a display equation block."""
    if len(text) > 120:
        return False
    math_count = sum(1 for ch in text if ch in MATH_SYMBOLS)
    if math_count >= 2:
        return True
    if re.search(r"\(\d+\)\s*$", text) and math_count >= 1:
        return True
    return False


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------


@dataclass
class Element:
    """One unit of output: a heading, paragraph, figure placeholder, …"""

    kind: str  # page | title | authors | heading | para | equation | footnote | figure | table | box
    page: int
    lines: list[Line] = field(default_factory=list)
    level: int = 0
    fl: Float | None = None
    notes: dict[int, list[Annotation]] = field(default_factory=dict)  # after line i
    after: list[Annotation] = field(default_factory=list)  # after the whole element
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    col: str = "full"

    @property
    def text(self) -> str:
        return " ".join(ln.text for ln in self.lines)

    def all_lines(self) -> list[Line]:
        if self.fl is None:
            return self.lines
        cap = self.fl.caption.lines if self.fl.caption else []
        return cap + lines_of(self.fl.inner)

    def is_annotated(self) -> bool:
        if self.notes or self.after:
            return True
        return any(w.anns for ln in self.all_lines() for w in ln.words)


@dataclass
class Context:
    body_size: float
    vocab: set[str]
    anns: dict[int, Annotation] = field(default_factory=dict)
    skipped: Counter = field(default_factory=Counter)
    seen_heading: bool = False


def _doc_context(layouts: list[PageLayout]) -> Context:
    sizes: dict[float, int] = {}
    words: list[str] = []
    for layout in layouts:
        for block in layout.blocks:
            broken = False  # previous line ended in a hyphen
            for ln in block.lines:
                sizes[ln.size] = sizes.get(ln.size, 0) + len(ln.text)
                texts = [w.text for w in ln.words]
                ends_broken = bool(texts) and texts[-1].endswith("-")
                # Halves of words split across lines are not vocabulary.
                words.extend(texts[(1 if broken else 0) : (-1 if ends_broken else None)])
                broken = ends_broken
    body = max(sizes, key=sizes.get) if sizes else 11.0
    return Context(body_size=body, vocab=build_vocab(words))


# ---------------------------------------------------------------------------
# Page -> elements
# ---------------------------------------------------------------------------


def _heading_level(block: Block, body_size: float) -> int:
    """Markdown heading level for a block, or 0 if it is not a heading."""
    text = block.text.strip()
    if not block.bold or len(block.lines) > 3 or len(text) >= 120:
        return 0
    m = _NUMBERED_HEADING_RE.match(text)
    if m and not text.endswith("."):
        return min(2 + m.group(1).count("."), 4)
    if _NAMED_HEADING_RE.match(text) and block.size >= body_size * 1.05:
        return 2
    return 0


def _continues(before: list[Line], after: list[Line]) -> bool:
    """True if `after` carries on the sentence that `before` leaves unfinished."""
    last, first = before[-1].text.strip(), after[0].text.strip()
    return bool(last and first) and last[-1] not in ".?!:" and first[0].islower()


def _element(kind: str, page: int, item, **kw) -> Element:
    return Element(
        kind=kind, page=page, x0=item.x0, y0=item.y0, x1=item.x1, y1=item.y1, col=item.col, **kw
    )


def _mostly_inside(block_rect: pymupdf.Rect, r: pymupdf.Rect) -> bool:
    inter = block_rect & r
    if inter.is_empty or block_rect.is_empty:
        return False
    return inter.get_area() > 0.5 * block_rect.get_area()


def build_page(page: pymupdf.Page, layout: PageLayout, page_num: int, ctx: Context) -> list[Element]:
    width, height = layout.width, layout.height
    anns, skipped = read_annotations(page, page_num, next_uid=len(ctx.anns))
    ctx.skipped.update(skipped)
    ctx.anns.update({a.uid: a for a in anns})

    # Free-text boxes can come back as page text as well; drop that copy. Note
    # text lies inside its box; body text merely overlapped by a note is kept.
    all_annots = list(page.annots() or [])
    freetext = [pymupdf.Rect(a.rect) for a in all_annots if a.type[0] == 2]
    blocks = [
        b
        for b in layout.blocks
        if not any(_mostly_inside(pymupdf.Rect(b.x0, b.y0, b.x1, b.y1), r) for r in freetext)
    ]
    mark_words([w for b in blocks for w in b.words], anns)

    ann_rects = [pymupdf.Rect(a.rect) for a in all_annots]
    floats, body = detect_floats(page, blocks, ann_rects, ctx.body_size, layout.has_linenos)
    body = merge_row_fragments(body)

    elements: list[Element] = [Element(kind="page", page=page_num, level=page_num)]
    title: Element | None = None
    authors: Element | None = None

    for item in reading_order(body + floats, width):
        if isinstance(item, Float):
            elements.append(_element(item.kind, page_num, item, fl=item))
            continue
        level = _heading_level(item, ctx.body_size)
        if page_num == 1 and not ctx.seen_heading and not level:
            if item.size >= ctx.body_size * 1.2:
                if title is None:
                    title = _element("title", page_num, item)
                    elements.append(title)
                title.lines.extend(item.lines)
                continue
            if title is not None:
                if authors is None:
                    authors = _element("authors", page_num, item)
                    elements.append(authors)
                authors.lines.extend(item.lines)
                continue
        if level:
            ctx.seen_heading = True
            elements.append(_element("heading", page_num, item, lines=item.lines, level=level))
        elif (
            item.size < 0.87 * ctx.body_size
            and item.y0 > 0.5 * height
            and not item.has_lineno
        ):
            elements.append(_element("footnote", page_num, item, lines=item.lines))
        elif len(item.lines) <= 4 and is_display_equation(item.text):
            elements.append(_element("equation", page_num, item, lines=item.lines))
        else:
            prev = elements[-1]
            if prev.kind == "para" and prev.col != item.col and _continues(prev.lines, item.lines):
                prev.lines = prev.lines + item.lines  # column break inside a paragraph
            else:
                elements.append(_element("para", page_num, item, lines=item.lines))

    elements = _group_equations(elements, review=layout.has_linenos)

    for el in elements:
        for ln in el.all_lines():
            for w in ln.words:
                if w.lineno is not None:
                    for uid in w.anns:
                        ctx.anns[uid].linenos.append(w.lineno)

    _anchor_notes(elements, [a for a in anns if not a.is_markup], width)
    return elements


_EQ_NUM_RE = re.compile(r"\((\d+)\)\s*$")


def _group_equations(elements: list[Element], review: bool) -> list[Element]:
    """Collect the pieces of each display equation into one equation element.

    A multi-line equation arrives as several blocks, some of them looking like
    short paragraphs. In a review copy the ruler helps: display maths is mostly
    left unnumbered, so a short unnumbered body block is part of an equation.
    """
    if review:
        for el in elements:
            unnumbered = not any(ln.lineno for ln in el.lines)
            if el.kind == "para" and unnumbered and len(el.lines) <= 4 and len(el.text) <= 200:
                el.kind = "equation"

    # A short numbered row ending in "(8)" next to equation pieces belongs to them.
    for i, el in enumerate(elements):
        near = [elements[j].kind for j in (i - 1, i + 1) if 0 <= j < len(elements)]
        if (
            el.kind == "para"
            and len(el.lines) <= 2
            and len(el.text) < 120
            and _EQ_NUM_RE.search(el.lines[-1].text)
            and ("equation" in near or "=" in el.text)
        ):
            el.kind = "equation"

    out: list[Element] = []
    for el in elements:
        prev = out[-1] if out else None
        if prev is not None and prev.kind == "equation" and prev.col == el.col:
            # The "(7)" label can come back as the first line of the next paragraph.
            if el.kind == "para" and len(el.lines) > 1 and re.fullmatch(r"\(\d+\)", el.lines[0].text.strip()):
                prev.lines = prev.lines + [el.lines[0]]
                el.lines = el.lines[1:]
            elif el.kind == "equation" and el.y0 - prev.y1 < 20:
                prev.lines = prev.lines + el.lines
                prev.y1 = max(prev.y1, el.y1)
                continue
        out.append(el)
    return out


def _anchor_notes(elements: list[Element], notes: list[Annotation], width: float) -> None:
    """Attach each point annotation to the nearest line or float on its side of the page."""
    targets: list[tuple[Element, int | None, float, float, str]] = []
    for el in elements:
        if el.fl is not None:
            targets.append((el, None, el.y0, el.y1, el.col))
            continue
        for i, ln in enumerate(el.lines):
            col = "full" if el.col == "full" else ("left" if (ln.x0 + ln.x1) / 2 < width / 2 else "right")
            targets.append((el, i, ln.y0, ln.y1, col))

    for ann in notes:
        cx = (ann.rect.x0 + ann.rect.x1) / 2
        cy = (ann.rect.y0 + ann.rect.y1) / 2
        side = "left" if cx < width / 2 else "right"
        cands = [t for t in targets if t[4] in (side, "full")] or targets
        if not cands:
            elements[0].after.append(ann)
            continue
        el, idx, *_ = min(cands, key=lambda t: max(t[2] - cy, cy - t[3], 0.0))
        if idx is None:
            el.after.append(ann)
            ann.anchor_text = f"{el.kind.upper()} {el.fl.label}".strip()
            continue
        el.notes.setdefault(idx, []).append(ann)
        line = el.lines[idx]
        ann.anchor_text = " ".join(w.text for w in line.words[:12])
        numbered = [(abs(j - idx), ln.lineno) for j, ln in enumerate(el.lines) if ln.lineno]
        if numbered:
            ann.linenos = [min(numbered)[1]]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _prefix(lines: list[Line]) -> str:
    rng = line_range([ln.lineno for ln in lines if ln.lineno is not None])
    return f"⟨{rng}⟩ " if rng else ""


def _all_notes(el: Element) -> list[str]:
    notes = [a for i in sorted(el.notes) for a in el.notes[i]] + el.after
    return [note_tag(a) for a in notes]


def render_element(el: Element, ctx: Context) -> str:
    v, anns = ctx.vocab, ctx.anns
    if el.kind == "page":
        return "\n".join([f"--- Page {el.level} ---"] + _all_notes(el))
    if el.kind == "title":
        return "\n".join(["# " + flow(el.lines, v, anns)] + _all_notes(el))
    if el.kind == "authors":
        text = flow(el.lines, v, anns)
        text = re.sub(r"(?<=[A-Za-z])[\d∗†]+(,\d+[\d∗†]*)*", "", text)
        return "\n".join([f'[AUTHORS: "{text}"]'] + _all_notes(el))
    if el.kind == "heading":
        return "\n".join(["#" * el.level + " " + flow(el.lines, v, anns)] + _all_notes(el))
    if el.kind == "para":
        return _prefix(el.lines) + flow(el.lines, v, anns, el.notes)
    if el.kind == "equation":
        text = flow(el.lines, v, anns)
        nums = [m.group(1) for ln in el.lines if (m := _EQ_NUM_RE.search(ln.text))]
        label = f"EQUATION {nums[-1]}" if nums else "EQUATION"
        return "\n".join([f'{_prefix(el.lines)}[{label}: "{text}"]'] + _all_notes(el))
    if el.kind == "footnote":
        return "\n".join([f'[FOOTNOTE: "{flow(el.lines, v, anns)}"]'] + _all_notes(el))

    # figure / table
    fl = el.fl
    head = f"{fl.kind.upper()} {fl.label}".strip()
    if fl.caption is not None:
        caption = CAPTION_RE.sub("", flow(fl.caption.lines, v, anns), count=1).strip()
        out = [f'[{head}: "{caption}"]']
    else:
        out = [f"[{head}]"]
    if fl.kind == "table" and fl.inner:
        out += ["```text"] + fl.rows() + ["```"]
    elif fl.kind == "box":
        out += ["```text"] + text_lines(fl.inner) + ["```"]
    marked = flow(lines_of(fl.inner), v, anns, only_marked=True)
    if marked:
        out.append(marked)
    return "\n".join(out + _all_notes(el))


def _drop_back_matter(elements: list[Element]) -> list[Element]:
    """Remove the reference list and appendix sections that carry no annotation."""
    out: list[Element] = []
    section: list[Element] = []
    mode = "body"

    def flush() -> None:
        nonlocal section
        if any(e.is_annotated() for e in section):
            out.extend(section)
        else:
            out.extend(e for e in section if e.kind == "page")
        section = []

    for el in elements:
        if el.kind == "heading":
            if mode == "body" and _REFERENCES_RE.match(el.text.strip()):
                mode = "refs"
                continue
            if mode != "body":  # first heading after the references starts the appendix
                flush()
                mode = "appendix"
        if mode == "body":
            out.append(el)
        elif mode == "refs":
            if el.kind == "page" or el.is_annotated():
                out.append(el)
        else:
            section.append(el)
    flush()

    # Page markers with nothing left under them
    return [
        el
        for i, el in enumerate(out)
        if not (el.kind == "page" and not el.after and (i + 1 == len(out) or out[i + 1].kind == "page"))
    ]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _count(ctx: Context) -> tuple[int, int]:
    highlights = sum(1 for a in ctx.anns.values() if a.is_markup and a.text_parts)
    notes = sum(1 for a in ctx.anns.values() if not a.is_markup and a.content)
    return highlights, notes


@dataclass
class Document:
    """A parsed PDF: its elements in reading order and the annotations found."""

    elements: list[Element]
    ctx: Context
    page_sizes: list[tuple[float, float]]
    annotations: list[Annotation]  # in paper order, with display IDs


def load_document(pdf_path: Path) -> Document:
    """Parse a PDF into elements and annotations (nothing is written)."""
    doc = pymupdf.open(pdf_path)
    layouts = [parse_page(page) for page in doc]
    ctx = _doc_context(layouts)
    elements: list[Element] = []
    for page_num, (page, layout) in enumerate(zip(doc, layouts), start=1):
        elements.extend(build_page(page, layout, page_num, ctx))
    ordered = assign_ids(list(ctx.anns.values()))  # before rendering: notes show their ID
    return Document(elements, ctx, [(pg.rect.width, pg.rect.height) for pg in doc], ordered)


def extract(pdf_path: Path, out_path: Path, full: bool = False) -> tuple[int, int, int]:
    """Extract pdf_path to Markdown at out_path, plus a JSON list of annotations.

    With full=False the reference list and unannotated appendix sections are
    left out. Returns (page_count, total_highlights, total_notes).
    """
    document = load_document(pdf_path)
    ctx, ordered = document.ctx, document.annotations
    elements = document.elements if full else _drop_back_matter(document.elements)

    parts = [render_element(el, ctx) for el in elements]
    for a in ordered:
        if a.is_markup and not a.text_parts:
            print(f"  WARNING: empty highlight text — page {a.page} ({a.id})", file=sys.stderr)
    if ctx.skipped:
        detail = ", ".join(f"{n} {why}" for why, n in sorted(ctx.skipped.items()))
        print(f"  NOTE: skipped annotations without usable content: {detail}", file=sys.stderr)

    text = "\n\n".join(p for p in parts if p)
    if ordered:
        text += "\n\n--- Annotations ---\n\n" + annotations_table(ordered)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n", encoding="utf-8")
    out_path.with_suffix(".annotations.json").write_text(
        json.dumps(
            {
                "pdf": Path(pdf_path).name,
                "pages": len(document.page_sizes),
                "skipped": dict(ctx.skipped),
                "annotations": annotations_records(ordered),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return (len(document.page_sizes), *_count(ctx))


# ---------------------------------------------------------------------------
# Lookups for viewers: where things are on the page, and the framing sections
# ---------------------------------------------------------------------------


def document_index(document: Document) -> dict:
    """Where each line number and each named part of the paper sits.

    Returns {"lines": {"267": [page, x0, y0, x1, y1]}, "anchors": {"table 2": [...]}}
    with boxes in PDF points. Anchor keys are lower-case: "figure 3", "table 2",
    "equation 6", "section 3.3.2", "appendix h.3".
    """
    lines: dict[str, list[float]] = {}
    anchors: dict[str, list[float]] = {}

    def box(page: int, x0: float, y0: float, x1: float, y1: float) -> list[float]:
        return [page, round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]

    for el in document.elements:
        for ln in el.all_lines():
            if ln.lineno is not None:
                lines.setdefault(str(ln.lineno), box(el.page, ln.x0, ln.y0, ln.x1, ln.y1))
        where = box(el.page, el.x0, el.y0, el.x1, el.y1)
        if el.fl is not None and el.fl.label not in ("", "?"):
            anchors.setdefault(f"{el.kind} {el.fl.label}".lower(), where)
        elif el.kind == "equation":
            nums = [m.group(1) for ln in el.lines if (m := _EQ_NUM_RE.search(ln.text))]
            if nums:
                anchors.setdefault(f"equation {nums[-1]}", where)
        elif el.kind == "heading":
            m = _NUMBERED_HEADING_RE.match(el.text.strip())
            if m:
                number = m.group(1).lower()
                anchors.setdefault(f"section {number}", where)
                if number[0].isalpha():
                    anchors.setdefault(f"appendix {number}", where)
    return {"lines": lines, "anchors": anchors}


def front_matter(document: Document) -> dict[str, str]:
    """The paper's own framing: abstract, stated contributions, conclusion (plain text)."""
    vocab = document.ctx.vocab
    sections: dict[str, list[Element]] = {}
    current = None
    for el in document.elements:
        if el.kind == "heading":
            name = re.sub(r"^[\dA-Z.]+\s+", "", el.text.strip()).lower()
            current = name if el.level == 2 else current
            continue
        if current and el.kind == "para":
            sections.setdefault(current, []).append(el)

    def text_of(paras: list[Element]) -> str:
        return "\n\n".join(plain_text(p.lines, vocab) for p in paras)

    def section(prefix: str) -> list[Element]:
        return next((v for k, v in sections.items() if k.startswith(prefix)), [])

    intro = section("introduction")
    start = next(
        (i for i, p in enumerate(intro) if re.search(r"contribution", p.text, re.IGNORECASE)), None
    )
    contributions = intro[start:] if start is not None else intro[-1:]
    return {
        "abstract": text_of(section("abstract")),
        "contributions": text_of(contributions),
        "conclusion": text_of(section("conclusion")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract an annotated PDF to Markdown with highlights and notes in place."
    )
    parser.add_argument("pdf_path", help='Path to the annotated PDF (e.g., "papers/foo.pdf")')
    parser.add_argument(
        "--full",
        action="store_true",
        help="Keep the reference list and unannotated appendix sections",
    )
    parser.add_argument(
        "--output-dir", default="outputs", help="Root directory for generated artifacts"
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output_dir) / "extracted" / (pdf_path.stem + ".md")
    n_pages, n_highlights, n_notes = extract(pdf_path, out_path, full=args.full)

    n_chars = len(out_path.read_text(encoding="utf-8"))
    print(f"Tokens:     ~{n_chars // 4:,} (≈ chars/4)")
    print(f"Pages:      {n_pages}")
    print(f"Highlights: {n_highlights}")
    print(f"Notes:      {n_notes}")
    print(f"Output:     {out_path}")

    if n_highlights == 0:
        print("WARNING: no highlights found — was the PDF annotated?", file=sys.stderr)
    if n_notes == 0:
        print("WARNING: no margin notes found — was the PDF annotated?", file=sys.stderr)


if __name__ == "__main__":
    main()
