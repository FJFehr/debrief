"""Tests for the extraction step (src/extract.py and its helper modules).

Unit tests cover the pure helper functions, and invented pages cover the rules
for annotations. Every PDF found in reviews/ and papers/ is also run through
extraction as a smoke test. Tests that check exact
text from a real annotated paper are in tests/test_local_*.py, which is
gitignored.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from src.extract import extract, is_display_equation
from src.annotations import note_position, rgb_to_colour
from src.layout import build_vocab, join_hyphenated, reading_order
from src.render import clean_note, line_range

PDF_DIRS = (Path("reviews"), Path("papers"))  # both are gitignored
ALL_PDFS = sorted(pdf for d in PDF_DIRS for pdf in d.glob("*.pdf"))


# ---------------------------------------------------------------------------
# Unit tests: colours and positions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rgb,expected",
    [
        ((1.0, 1.0, 0.0), "yellow"),
        ((1.0, 0.9, 0.1), "yellow"),
        ((0.0, 0.8, 0.0), "green"),
        ((0.2, 0.7, 0.1), "green"),
        ((0.9, 0.1, 0.1), "red"),
        ((0.7, 0.0, 0.0), "red"),
        ((0.0, 0.0, 0.9), "blue"),
        ((0.1, 0.2, 0.8), "blue"),
        ((0.8, 0.0, 0.8), "purple"),
        ((0.6, 0.1, 0.7), "purple"),
        ((1.0, 0.5, 0.0), "orange"),
        ((0.9, 0.4, 0.6), "pink"),
        (None, "yellow"),  # fallback for missing colour
        # Shades written by macOS Preview
        ((0.98, 0.80, 0.35), "yellow"),  # highlight
        ((1.0, 0.92, 0.42), "yellow"),  # sticky note
        ((0.98, 0.36, 0.54), "pink"),  # highlight
        ((1.0, 0.69, 0.79), "pink"),  # sticky note
    ],
)
def test_rgb_to_colour(rgb, expected):
    assert rgb_to_colour(rgb) == expected


@pytest.mark.parametrize(
    "x0,page_width,expected",
    [(30, 600, "left"), (550, 600, "right"), (300, 600, "inline")],
)
def test_note_position(x0, page_width, expected):
    assert note_position(SimpleNamespace(x0=x0), page_width) == expected


# ---------------------------------------------------------------------------
# Unit tests: text helpers
# ---------------------------------------------------------------------------


def test_join_hyphenated_broken_word():
    vocab = build_vocab(["external", "tools"])
    assert join_hyphenated("exter-", "nal", vocab) == "external"


def test_join_hyphenated_real_compound():
    vocab = build_vocab(["training-free", "method"])
    assert join_hyphenated("training-", "free,", vocab) == "training-free,"


def test_join_hyphenated_keeps_existing_compound_hyphens():
    assert join_hyphenated("retrieve-then-", "rerank", set()) == "retrieve-then-rerank"


def test_join_hyphenated_capitalised_name():
    assert join_hyphenated("Tool-", "Bench", build_vocab(["ToolBench"])) == "ToolBench"


def test_reading_order_two_columns_with_full_width_figure():
    def box(name, x0, y0, x1, y1, col):
        return SimpleNamespace(name=name, x0=x0, y0=y0, x1=x1, y1=y1, col=col)

    items = [
        box("right-low", 306, 400, 526, 700, "right"),
        box("left-low", 71, 420, 291, 700, "left"),
        box("figure", 71, 70, 526, 300, "full"),
        box("right-top", 306, 40, 526, 60, "right"),
        box("left-top", 71, 40, 291, 60, "left"),
    ]
    order = [it.name for it in reading_order(items, 595)]
    assert order == ["left-top", "right-top", "figure", "left-low", "right-low"]


def test_line_range():
    assert line_range([]) == ""
    assert line_range([7]) == "L7"
    assert line_range([31, 29, 42]) == "L29–42"


def test_clean_note_keeps_paragraph_breaks_on_one_line():
    assert clean_note("first\nline\n\nsecond") == "first line ¶ second"


def test_is_display_equation_two_math_symbols():
    assert is_display_equation("x ∈ X, y ≥ 0")


def test_is_display_equation_with_equation_number():
    assert is_display_equation("L = ∑ loss (3)")


def test_is_display_equation_too_long():
    assert not is_display_equation("∈ ≥ " + "word " * 40)


def test_is_display_equation_plain_text():
    assert not is_display_equation("This is an ordinary sentence.")


# ---------------------------------------------------------------------------
# Smoke test: every PDF in reviews/ and papers/
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pdf", ALL_PDFS, ids=lambda p: p.stem[:24])
def test_every_paper_extracts(pdf, tmp_path):
    out = tmp_path / "out.md"
    n_pages, _, _ = extract(pdf, out, full=True)
    text = out.read_text(encoding="utf-8")
    assert n_pages > 0
    assert text.count("--- Page ") == n_pages
    assert re.search(r"^# \S", text, flags=re.MULTILINE), "no title found"
    assert len(re.findall(r"^## ", text, flags=re.MULTILINE)) >= 5


# ---------------------------------------------------------------------------
# The rules for annotations, on invented pages
# ---------------------------------------------------------------------------


def review_copy(path):
    """A two-column review copy: a ruler of line numbers in both margins, a highlight
    that runs over a line break, and a sticky note beside the right column."""
    left = ["Retrieval systems call a reranker for", "every query they receive and this is",
            "slow when the queries repeat often.", "We cache the output of the reranker",
            "and reuse it across similar queries,", "which halves the number of calls."]
    right = ["We evaluate on a held-out split of", "the benchmark and compare against",
             "three baselines trained on the same", "data as our own model. The split is",
             "released together with the code and", "the evaluation script that we used."]
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80), "1 Introduction", fontsize=12, fontname="hebo")
    for x, ruler_x, first, lines in ((72, 18, 1, left), (318, 566, 51, right)):
        for i, text in enumerate(lines):
            y = 110 + 13 * i
            page.insert_text((x, y), text, fontsize=10)
            page.insert_text((ruler_x, y), f"{first + i:03d}", fontsize=8)
    # The end of one line and the start of the next: the box around both covers two whole lines.
    page.add_highlight_annot(page.search_for("and this is", quads=True) + page.search_for("slow when", quads=True))
    page.add_text_annot((545, page.search_for("three baselines")[0].y0), "why only three?")
    doc.save(path)


def test_annotations_stay_exact_on_a_two_column_review_copy(tmp_path):
    review_copy(tmp_path / "two.pdf")
    extract(tmp_path / "two.pdf", tmp_path / "two.md")
    body = (tmp_path / "two.md").read_text(encoding="utf-8").partition("--- Annotations ---")[0]

    assert body.startswith("--- Page 1 ---")
    # The highlight is the marked words only, not everything inside its bounding box.
    assert 'receive [HIGHLIGHT yellow: "and this is slow when"] the queries' in body
    # The ruler is stripped from the text and kept as references, one column after the other.
    assert "⟨L1–6⟩ Retrieval systems call a reranker for every query" in body
    assert "⟨L51–56⟩ We evaluate on a held-out split" in body
    assert not re.search(r"\b0\d\d\b", body)
    # The note follows the line it sits beside, in its own column.
    assert 'trained on the same\n[NOTE A2 right yellow @L53: "why only three?"]\ndata as our own model.' in body


def test_a_note_on_the_references_heading_stays_in_place(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    rows = [("1 Introduction", True), ("We study retrieval at half the usual cost with a cached reranker.", False),
            ("References", True), ("A. Author. 2020. A paper about retrieval. In Proceedings of a venue.", False)]
    for i, (text, heading) in enumerate(rows):
        page.insert_text((72, 80 + 40 * i), text, fontsize=12 if heading else 10, fontname="hebo" if heading else "helv")
    hit = page.search_for("References")[0]
    page.add_text_annot((hit.x1 + 6, hit.y0), "the 2019 baseline paper is missing")
    doc.save(tmp_path / "refs.pdf")

    extract(tmp_path / "refs.pdf", tmp_path / "refs.md")  # without --full: the unannotated references go
    body = (tmp_path / "refs.md").read_text(encoding="utf-8").partition("--- Annotations ---")[0]
    assert '## References\n[NOTE A1 left yellow: "the 2019 baseline paper is missing"]' in body
    assert "A paper about retrieval" not in body
