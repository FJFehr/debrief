"""Test for src/pipeline.py: an annotated PDF goes in, extracted text and a prompt come out."""

import pymupdf

from src.pipeline import process_paper


def annotated_pdf(path):
    """A one-page paper with one highlight and one margin note."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "A Small Test Paper", fontsize=20)
    sentence = "The method uses a key phrase to find documents. "
    page.insert_textbox(pymupdf.Rect(72, 140, 520, 400), sentence * 6, fontsize=10)
    page.add_highlight_annot(page.search_for("key phrase", quads=True)[:1])
    page.add_text_annot((530, 150), "Why this phrase?")
    doc.save(path)


def test_pipeline_writes_extracted_text_and_prompt(tmp_path):
    pdf = tmp_path / "small.pdf"
    annotated_pdf(pdf)

    process_paper(str(pdf), include_bibtex=False, output_dir=tmp_path)

    extracted = (tmp_path / "extracted" / "small.md").read_text(encoding="utf-8")
    assert '[HIGHLIGHT yellow: "key phrase"]' in extracted
    assert "Why this phrase?" in extracted
    prompt = (tmp_path / "prompts" / "small.prompt.md").read_text(encoding="utf-8")
    assert extracted.strip() in prompt  # the paper is in the prompt, annotations included
    assert "<insert annotated text here>" not in prompt
    assert not (tmp_path / "bibtex" / "small.bib").exists()
