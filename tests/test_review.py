"""Tests for src/review.py: review and interview prompt generation."""

import sys
from pathlib import Path

import pytest

from src import review as review_module
from src.review import (
    ANSWERS_PATH_PLACEHOLDER,
    ANSWERS_PLACEHOLDER,
    INTERVIEW_TEMPLATES,
    REVIEW_TEMPLATES,
    TEXT_PLACEHOLDER,
    fill_reviewing_files,
    has_answers,
    load_interview_prompt,
    load_review_prompt,
    needs_answers,
    write_prompt,
)

ANNOTATED = '⟨L1–2⟩ Some text.\n[NOTE A1 left yellow @L2: "Why?"]'
ANSWERS = "## Summary\n\nAsked:\n1. What is it about?\nAnswer: It is about tools.\nOutlined: The paper studies tools.\nAccepted."


@pytest.fixture(autouse=True)
def reviewing_dir(tmp_path, monkeypatch):
    """A stand-in for reviewing/, which holds the reviewer's own (untracked) documents."""
    root = tmp_path / "reviewing"
    (root / "venues").mkdir(parents=True)
    (root / "my_reviews").mkdir()
    (root / "REVIEWING_GUIDELINES.md").write_text("GUIDELINES-TEXT", encoding="utf-8")
    (root / "BIASES.md").write_text("REGISTER-TEXT", encoding="utf-8")
    (root / "INTERVIEW.md").write_text("PROCESS-TEXT", encoding="utf-8")
    (root / "venues" / "ARR.md").write_text("VENUE-TEXT", encoding="utf-8")
    (root / "my_reviews" / "ACL_ARR_2026_May_1.md").write_text("PAST-ARR-REVIEW", encoding="utf-8")
    (root / "my_reviews" / "ICLR_2027_Conference_2.md").write_text("PAST-ICLR-REVIEW", encoding="utf-8")
    monkeypatch.setattr(review_module, "REVIEWING_DIR", root)
    return root


@pytest.mark.parametrize("venue", sorted(REVIEW_TEMPLATES))
def test_review_templates_have_one_text_placeholder(venue):
    template = REVIEW_TEMPLATES[venue].read_text(encoding="utf-8")
    assert template.count(TEXT_PLACEHOLDER) == 1


@pytest.mark.parametrize(
    "path", sorted({*REVIEW_TEMPLATES.values(), *INTERVIEW_TEMPLATES.values()}), ids=lambda p: p.stem
)
def test_templates_describe_the_extraction_format(path):
    """Every template explains the markers the extractor writes."""
    template = path.read_text(encoding="utf-8")
    for marker in ("[HIGHLIGHT", "[NOTE <id>", "⟨L29–42⟩", "[FIGURE N:", "[TABLE N:"):
        assert marker in template, marker


@pytest.mark.parametrize("venue", sorted(REVIEW_TEMPLATES))
def test_load_review_prompt_fills_every_placeholder(venue):
    prompt = load_review_prompt(ANNOTATED, venue, ANSWERS)
    assert ANNOTATED in prompt
    assert "<insert " not in prompt


def test_review_writes_prompt_file(tmp_path):
    src = tmp_path / "paper.md"
    src.write_text("## 1 Introduction\n\n⟨L1⟩ Body.", encoding="utf-8")
    out = tmp_path / "reviews" / "paper.review.md"
    write_prompt(load_review_prompt(src.read_text(encoding="utf-8"), "colm"), out, "Review prompt")
    assert "⟨L1⟩ Body." in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ARR: built from the reviewer's own process documents
# ---------------------------------------------------------------------------


def test_arr_review_needs_answers_but_others_do_not():
    assert needs_answers("arr")
    assert not needs_answers("colm")
    assert not needs_answers("iclr")


def test_has_answers():
    assert has_answers(ANSWERS)
    assert has_answers("## Q1 — Summary\nQuestion: What is it about?\nAnswer: It is about tools.")  # an older record
    assert not has_answers("")
    assert not has_answers("# Interview record: foo.pdf\n\n## Brief\n\nNo Answer: yet\n\n## Summary\n\nAsked:\n1. Why?\n")


def test_arr_interview_prompt_is_built_from_the_reviewing_files():
    prompt = load_interview_prompt(ANNOTATED, "arr", Path("outputs/reviews/foo.answers.md"))
    for inserted in ("GUIDELINES-TEXT", "REGISTER-TEXT", "PROCESS-TEXT", "VENUE-TEXT"):
        assert prompt.count(inserted) == 1, inserted
    assert f"<annotated_paper>\n{ANNOTATED}\n</annotated_paper>" in prompt
    assert "outputs/reviews/foo.answers.md" in prompt
    assert "<insert " not in prompt and ANSWERS_PATH_PLACEHOLDER not in prompt


def test_only_the_latest_past_reviews_go_into_a_prompt(reviewing_dir, monkeypatch):
    import os

    monkeypatch.setattr(review_module, "PAST_REVIEWS_KEPT", 2)
    for age, name in enumerate(("oldest", "middle", "newest")):
        path = reviewing_dir / "my_reviews" / f"ACL_ARR_2026_June_{name}.md"
        path.write_text(f"REVIEW-{name}", encoding="utf-8")
        os.utime(path, (2_000_000_000 + age, 2_000_000_000 + age))
    prompt = load_review_prompt(ANNOTATED, "arr", ANSWERS)
    assert "REVIEW-newest" in prompt and "REVIEW-middle" in prompt
    assert "REVIEW-oldest" not in prompt and "PAST-ARR-REVIEW" not in prompt


def test_arr_review_prompt_contains_documents_record_and_voice_examples():
    prompt = load_review_prompt(ANNOTATED, "arr", ANSWERS)
    for inserted in ("GUIDELINES-TEXT", "PROCESS-TEXT", "VENUE-TEXT"):
        assert inserted in prompt, inserted
    assert f"<interview_record>\n{ANSWERS}\n</interview_record>" in prompt
    assert "PAST-ARR-REVIEW" in prompt  # same venue only
    assert "PAST-ICLR-REVIEW" not in prompt
    assert ANSWERS_PLACEHOLDER not in prompt


def test_missing_reviewing_file_stops_with_a_hint(reviewing_dir, capsys):
    (reviewing_dir / "BIASES.md").unlink()
    with pytest.raises(SystemExit):
        fill_reviewing_files("<insert bias register here>", "arr")
    assert "BIASES.md not found" in capsys.readouterr().err


def test_interview_template_and_cli_agree_on_the_record_format():
    """The chat-mode record holds 'Answer:' lines; the CLI looks for exactly those."""
    template = INTERVIEW_TEMPLATES["arr"].read_text(encoding="utf-8")
    assert "\nAnswer: " in template
    drafting = REVIEW_TEMPLATES["arr"].read_text(encoding="utf-8")
    for part in ("## Summary (approved by the reviewer)", "## Index", "### Weaknesses (most severe first)"):
        assert part in template and part in drafting, part


def test_arr_review_refuses_to_run_without_answers(tmp_path, monkeypatch, capsys):
    pdf = tmp_path / "foo.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")  # never opened: the answers check comes first
    monkeypatch.setattr(
        sys, "argv", ["review", "--paper", str(pdf), "--venue", "arr", "--output-dir", str(tmp_path)]
    )
    monkeypatch.setattr(review_module, "extract", lambda *a, **k: pytest.fail("extract was called"))
    with pytest.raises(SystemExit) as exc:
        review_module.main()
    assert exc.value.code == 1
    assert "Run the interview first" in capsys.readouterr().err
