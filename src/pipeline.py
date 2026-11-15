#!/usr/bin/env python3
"""
Pipeline: Extract annotations → Fetch BibTeX → Create Prompt → Summarise → Output

Usage:
    uv run pipeline --paper papers/foo.pdf --url https://arxiv.org/abs/...
    uv run pipeline --paper papers/foo.pdf --url 2601.07296
    uv run pipeline --paper papers/foo.pdf --url https://aclanthology.org/N19-1423/
    uv run pipeline --paper papers/foo.pdf --url https://openreview.net/forum?id=...

Options:
    --paper     Path to annotated PDF file (required)
    --url       Paper URL or arXiv ID (required)
    --no-bibtex Skip BibTeX fetching step

Outputs:
    outputs/extracted/foo.md       (annotated text, plus foo.annotations.json)
    outputs/bibtex/foo.bib         (fetched BibTeX, optional)
    outputs/prompts/foo.prompt.md  (prompt ready for manual or local model use)
"""

import sys
import argparse
from pathlib import Path

from src.extract import extract
from src.get_bibtex import get_bibtex_from_url
from src.summarise import summarise


def process_paper(
    pdf_path: str,
    paper_url: str | None = None,
    include_bibtex: bool = True,
    output_dir: Path = Path("outputs"),
    full: bool = False,
) -> None:
    """
    Complete pipeline: extract → fetch BibTeX → prepend to extracted → create prompt.

    Args:
        pdf_path: Path to annotated PDF file
        paper_url: URL or arXiv ID for BibTeX retrieval
        include_bibtex: Whether to fetch and include BibTeX
        full: Keep the reference list and unannotated appendix sections
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    paper_name = pdf_file.stem

    # ───────────────────────────────────────────────────────────────────────────
    # Step 1: Extract annotations from PDF
    # ───────────────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("STEP 1: EXTRACT ANNOTATIONS FROM PDF")
    print(f"{'=' * 70}")

    extracted_path = output_dir / "extracted" / f"{paper_name}.md"
    bibtex_path = output_dir / "bibtex" / f"{paper_name}.bib"
    prompt_output_path = output_dir / "prompts" / f"{paper_name}.prompt.md"

    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    bibtex_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_output_path.parent.mkdir(parents=True, exist_ok=True)

    n_pages, n_highlights, n_notes = extract(pdf_file, extracted_path, full=full)

    print(f"✓ Extracted from {n_pages} pages")
    print(f"  - {n_highlights} highlights")
    print(f"  - {n_notes} margin notes")
    print(f"✓ Written to: {extracted_path}")

    # ───────────────────────────────────────────────────────────────────────────
    # Step 2: Fetch BibTeX and store separately
    # ───────────────────────────────────────────────────────────────────────────
    bibtex_entry: str | None = None
    if include_bibtex and paper_url:
        print(f"\n{'=' * 70}")
        print("STEP 2: FETCH BIBTEX")
        print(f"{'=' * 70}")
        print(f"Fetching from: {paper_url}")

        bibtex_entry = get_bibtex_from_url(paper_url)
        if bibtex_entry:
            print("✓ BibTeX found")
            bibtex_path.write_text(bibtex_entry + "\n", encoding="utf-8")
            print(f"✓ BibTeX written to: {bibtex_path}")
        else:
            print("⚠ Could not fetch BibTeX (proceeding without)", file=sys.stderr)
    elif not paper_url:
        print("\n⚠ No URL provided, skipping BibTeX fetch")
    else:
        print("\n⚠ --no-bibtex flag set, skipping BibTeX fetch")

    # ───────────────────────────────────────────────────────────────────────────
    # Step 3: Create prompt from template and extracted content
    # ───────────────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("STEP 3: CREATE PROMPT WITH EXTRACTED CONTENT")
    print(f"{'=' * 70}")

    preface_text = ""
    if bibtex_entry:
        preface_text = f"--- Known BibTeX (fetched) ---\n\n{bibtex_entry}"

    summarise(extracted_path, prompt_output_path, preface_text=preface_text)

    print("✓ Prompt created from template and extracted content")

    # ───────────────────────────────────────────────────────────────────────────
    # Done
    # ───────────────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print(f"✓ Extracted:  {extracted_path}")
    if bibtex_entry:
        print(f"✓ BibTeX:     {bibtex_path}")
    print(f"✓ Prompt:     {prompt_output_path}")
    print(
        f"\n→ Copy the contents of {prompt_output_path} and paste into your selected model."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Complete pipeline: extract annotations → fetch BibTeX → summarise",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run pipeline --paper papers/LRAS.pdf --url 2601.07296
  uv run pipeline --paper papers/foo.pdf --url https://arxiv.org/abs/2301.12345
  uv run pipeline --paper papers/foo.pdf --url https://aclanthology.org/N19-1423/
  uv run pipeline --paper papers/foo.pdf --no-bibtex
        """,
    )

    parser.add_argument(
        "--paper",
        required=True,
        help='Path to annotated PDF file (e.g., "papers/paper.pdf")',
    )

    parser.add_argument(
        "--url",
        default=None,
        help="Paper URL or arXiv ID for BibTeX retrieval (e.g., 2601.07296 or https://arxiv.org/abs/2601.07296)",
    )

    parser.add_argument(
        "--no-bibtex",
        action="store_true",
        help="Skip BibTeX fetching (extract and summarise only)",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Keep the reference list and unannotated appendix sections",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Root directory for generated artifacts",
    )

    args = parser.parse_args()

    process_paper(
        pdf_path=args.paper,
        paper_url=args.url,
        include_bibtex=not args.no_bibtex,
        output_dir=Path(args.output_dir),
        full=args.full,
    )


if __name__ == "__main__":
    main()
