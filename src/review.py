"""Generate a review draft prompt (COLM or ICLR) from an annotated PDF.

Usage:
    uv run review --paper reviews/foo.pdf
    uv run review --paper reviews/foo.pdf --venue iclr
    uv run review --paper reviews/foo.pdf --output-dir outputs

Writes: outputs/reviews/foo.review.md (ready to paste into a model)
"""

import sys
import argparse
from pathlib import Path

from src.extract import extract

REVIEW_TEMPLATES = {
    "colm": Path("prompts/templates/review.md"),
    "iclr": Path("prompts/templates/review_iclr.md"),
}


def load_review_prompt(annotated_text: str, venue: str = "colm") -> str:
    template_path = REVIEW_TEMPLATES[venue]
    if not template_path.exists():
        print(f"Error: review template not found at {template_path}", file=sys.stderr)
        sys.exit(1)
    template = template_path.read_text(encoding="utf-8")
    if "<insert annotated text here>" not in template:
        print(
            "Error: review template missing '<insert annotated text here>' placeholder",
            file=sys.stderr,
        )
        sys.exit(1)
    return template.replace("<insert annotated text here>", annotated_text)


def review(input_path: Path, output_path: Path, venue: str = "colm") -> None:
    annotated_text = input_path.read_text(encoding="utf-8")
    prompt = load_review_prompt(annotated_text, venue)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")
    print(f"✓ Review prompt written to {output_path}")
    print("\nCopy the contents and paste into Claude (claude.ai) or your local model.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract annotations from a PDF and generate a review draft prompt.",
    )
    parser.add_argument(
        "--paper",
        required=True,
        help="Path to the PDF file (e.g., reviews/foo.pdf)",
    )
    parser.add_argument(
        "--venue",
        choices=sorted(REVIEW_TEMPLATES),
        default="colm",
        help="Review template to use (default: colm)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Root directory for generated artifacts (default: outputs)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.paper)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    paper_name = pdf_path.stem
    extracted_path = output_dir / "extracted" / f"{paper_name}.txt"
    review_output_path = output_dir / "reviews" / f"{paper_name}.review.md"

    extracted_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 70}")
    print("STEP 1: EXTRACT ANNOTATIONS FROM PDF")
    print(f"{'=' * 70}")
    n_pages, n_highlights, n_notes = extract(pdf_path, extracted_path)
    print(f"✓ Extracted from {n_pages} pages — {n_highlights} highlights, {n_notes} notes")
    print(f"✓ Written to: {extracted_path}")

    print(f"\n{'=' * 70}")
    print("STEP 2: GENERATE REVIEW PROMPT")
    print(f"{'=' * 70}")
    review(extracted_path, review_output_path, args.venue)

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")
    print(f"✓ Extracted:     {extracted_path}")
    print(f"✓ Review prompt: {review_output_path}")


if __name__ == "__main__":
    main()
