"""Turn lines and annotations into Markdown text and the annotation tables."""

from __future__ import annotations

import re

from src.annotations import Annotation
from src.layout import Line, Word, join_hyphenated

_TAG_FOR_KIND = {
    "highlight": "HIGHLIGHT",
    "underline": "UNDERLINE",
    "squiggly": "UNDERLINE",
    "strikeout": "STRIKEOUT",
}


def clean_note(content: str) -> str:
    """One-line form of a note; paragraph breaks become ' ¶ '."""
    content = re.sub(r"\s*\n\s*\n\s*", " ¶ ", content.strip())
    return re.sub(r"\s+", " ", content)


def line_range(linenos: list[int]) -> str:
    if not linenos:
        return ""
    lo, hi = min(linenos), max(linenos)
    return f"L{lo}" if lo == hi else f"L{lo}–{hi}"


def note_tag(ann: Annotation) -> str:
    """[NOTE A12 right yellow @L58: "…"] for a sticky note or free-text box."""
    head = "NOTE" if ann.kind in ("note", "freetext") else ann.kind.upper()
    parts = [head, ann.id, ann.position, ann.colour]
    if ann.linenos:
        parts.append("@" + line_range(ann.linenos))
    label = " ".join(p for p in parts if p)
    return f'[{label}: "{clean_note(ann.content)}"]' if ann.content else f"[{label}]"


def flow(
    lines: list[Line],
    vocab: set[str],
    anns: dict[int, Annotation],
    notes: dict[int, list[Annotation]] | None = None,
    only_marked: bool = False,
) -> str:
    """Join lines into running text with annotations marked inline.

    Line-end hyphens are undone. Words covered by a highlight become
    [HIGHLIGHT colour: "…"] at their position; notes anchored to a line follow
    that line. With only_marked, just the marked runs are returned.
    """
    notes = notes or {}
    segs: list[list] = []  # ["w", text, [uids]] or ["n", Annotation]
    held: list[Annotation] = []  # notes waiting for a hyphenated word to finish
    hyphen_open = False

    for i, line in enumerate(lines):
        for w in line.words:
            if hyphen_open:
                last = next(s for s in reversed(segs) if s[0] == "w")
                last[1] = join_hyphenated(last[1], w.text, vocab)
                last[2] = last[2] + [u for u in w.anns if u not in last[2]]
                hyphen_open = False
                segs.extend(["n", a] for a in held)
                held = []
                continue
            segs.append(["w", w.text, list(w.anns)])
        nxt = lines[i + 1].words if i + 1 < len(lines) else []
        last_word = line.words[-1].text if line.words else ""
        hyphen_open = bool(
            nxt
            and len(last_word) > 1
            and last_word.endswith("-")
            and nxt[0].text[:1].isalnum()
        )
        if hyphen_open:
            held.extend(notes.get(i, []))
        else:
            segs.extend(["n", a] for a in notes.get(i, []))
    segs.extend(["n", a] for a in held)

    out: list[str] = []
    run: list[str] = []
    run_key: tuple | None = None
    run_uids: list[int] = []

    def close_run() -> None:
        nonlocal run, run_key, run_uids
        if run_key is not None:
            tag, colour = run_key
            out.append(f'[{tag} {colour}: "{" ".join(run)}"]')
            for uid in run_uids:
                if anns[uid].content:  # a comment attached to the highlight itself
                    a = anns[uid]
                    label = " ".join(p for p in ("NOTE", a.id, "on-highlight", a.colour) if p)
                    out.append(f'[{label}: "{clean_note(a.content)}"]')
        run, run_key, run_uids = [], None, []

    for seg in segs:
        if seg[0] == "n":
            close_run()
            out.append("\n" + note_tag(seg[1]) + "\n")
            continue
        _, text, uids = seg
        for uid in uids:
            anns[uid].text_parts.append(text)
        key = None
        if uids:
            first = anns[uids[0]]
            key = (_TAG_FOR_KIND.get(first.kind, "HIGHLIGHT"), first.colour)
        if key != run_key:
            close_run()
        if key is None:
            if not only_marked:
                out.append(text)
        else:
            run_key = key
            run.append(text)
            run_uids.extend(u for u in uids if u not in run_uids)
    close_run()

    text = " ".join(out)
    return re.sub(r" ?\n ?", "\n", text).strip()


def plain_text(lines: list[Line], vocab: set[str]) -> str:
    """Running text of lines with hyphens undone and no annotation markers."""
    bare = [
        Line([Word(w.x0, w.y0, w.x1, w.y1, w.text) for w in ln.words], ln.x0, ln.y0, ln.x1, ln.y1, ln.size, ln.bold)
        for ln in lines
    ]
    return flow(bare, vocab, {})


# ---------------------------------------------------------------------------
# Annotation listing
# ---------------------------------------------------------------------------


def _cell(text: str) -> str:
    return clean_note(text).replace("|", "\\|")


def annotations_table(anns: list[Annotation]) -> str:
    """Markdown table of every annotation, in paper order."""
    rows = [
        "| ID | Page | Line | Type | Colour | Text | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in anns:
        text = a.text if a.is_markup else (f"near: {a.anchor_text}" if a.anchor_text else "")
        rows.append(
            f"| {a.id} | {a.page} | {line_range(a.linenos)} | {a.kind} | {a.colour} "
            f"| {_cell(text)} | {_cell(a.content)} |"
        )
    return "\n".join(rows)


def annotations_records(anns: list[Annotation]) -> list[dict]:
    """JSON-ready records, one per annotation."""
    return [
        {
            "id": a.id,
            "page": a.page,
            "lines": [min(a.linenos), max(a.linenos)] if a.linenos else None,
            "type": a.kind,
            "colour": a.colour,
            "hex": a.hex,
            "text": a.text if a.is_markup else None,
            "note": a.content or None,
            "position": a.position or None,
            "anchor": a.anchor_text or None,
            "bbox": [round(v, 1) for v in a.rect],
        }
        for a in anns
    ]
