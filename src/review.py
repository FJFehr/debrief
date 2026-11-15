"""Generate review prompts (COLM, ICLR or ARR) from an annotated PDF.

Usage:
    uv run review --paper reviews/foo.pdf
    uv run review --paper reviews/foo.pdf --venue iclr
    uv run review --paper reviews/foo.pdf --output-dir outputs
    uv run review --paper reviews/foo.pdf --full   (keep references and whole appendix)

ARR follows the process in reviewing/INTERVIEW.md, in two steps, because the
reviewer's own words must be the first draft:
    uv run review --paper reviews/foo.pdf --venue arr --interview
        -> outputs/reviews/foo.interview.md   a model interviews you
    uv run review --paper reviews/foo.pdf --venue arr
        -> outputs/reviews/foo.review.md      a model drafts from your answers
(`uv run interview --paper reviews/foo.pdf` runs both in a browser page.)

Writes: outputs/reviews/foo.review.md (ready to paste into a model)
"""

import argparse
import re
import sys
from pathlib import Path

from src.extract import extract

REVIEW_TEMPLATES = {
    "arr": Path("prompts/templates/review_arr.md"),
    "colm": Path("prompts/templates/review.md"),
    "iclr": Path("prompts/templates/review_iclr.md"),
}
INTERVIEW_TEMPLATES = {
    "arr": Path("prompts/templates/review_arr_interview.md"),
}

# The reviewer's own process documents.
REVIEWING_DIR = Path("reviewing")
REVIEWING_FILES = {
    "<insert reviewing guidelines here>": "REVIEWING_GUIDELINES.md",
    "<insert bias register here>": "BIASES.md",
    "<insert interview process here>": "INTERVIEW.md",
}
VENUE_FILES = {"arr": "venues/ARR.md"}
PAST_REVIEW_GLOBS = {"arr": "my_reviews/ACL_ARR_*.md"}
# Every review saved at the end of an interview lands in my_reviews/. Only the latest go into a
# prompt, so the prompt does not grow with each paper reviewed.
PAST_REVIEWS_KEPT = 5

TEXT_PLACEHOLDER = "<insert annotated text here>"
ANSWERS_PLACEHOLDER = "<insert reviewer answers here>"
ANSWERS_PATH_PLACEHOLDER = "<answers file path>"
VENUE_PLACEHOLDER = "<insert venue file here>"
PAST_REVIEWS_PLACEHOLDER = "<insert past reviews here>"

_ANSWER_RE = re.compile(r"^Answer:", re.MULTILINE)


PASTE = "Copy the contents and paste into Claude (claude.ai) or your local model."


def load_template(template_path: Path) -> str:
    """A prompt template with a place for the annotated text. Used for every prompt this repo writes."""
    if not template_path.exists():
        print(f"Error: prompt template not found at {template_path}", file=sys.stderr)
        sys.exit(1)
    template = template_path.read_text(encoding="utf-8")
    if TEXT_PLACEHOLDER not in template:
        print(
            f"Error: prompt template {template_path} missing '{TEXT_PLACEHOLDER}' placeholder",
            file=sys.stderr,
        )
        sys.exit(1)
    return template


def write_prompt(prompt: str, output_path: Path, name: str, then: str = PASTE) -> None:
    """Write a finished prompt to a file and say what to do with it."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")
    print(f"✓ {name} written to {output_path}")
    print(f"\n{then}\n")


def _read_reviewing(relative: str) -> str:
    path = REVIEWING_DIR / relative
    if not path.exists():
        print(
            f"Error: {path} not found. The reviewing documents belong in {REVIEWING_DIR}/ "
            f"(see docs/review-interview.md).",
            file=sys.stderr,
        )
        sys.exit(1)
    return path.read_text(encoding="utf-8").strip()


def fill_reviewing_files(template: str, venue: str) -> str:
    """Insert the reviewer's process documents wherever the template asks for them."""
    for placeholder, relative in REVIEWING_FILES.items():
        if placeholder in template:
            template = template.replace(placeholder, _read_reviewing(relative))
    if VENUE_PLACEHOLDER in template:
        template = template.replace(VENUE_PLACEHOLDER, _read_reviewing(VENUE_FILES[venue]))
    if PAST_REVIEWS_PLACEHOLDER in template:
        found = REVIEWING_DIR.glob(PAST_REVIEW_GLOBS.get(venue, ""))
        paths = sorted(sorted(found, key=lambda p: p.stat().st_mtime)[-PAST_REVIEWS_KEPT:])
        past = "\n\n".join(
            f'<review file="{p.name}">\n{p.read_text(encoding="utf-8").strip()}\n</review>'
            for p in paths
        )
        template = template.replace(PAST_REVIEWS_PLACEHOLDER, past or "(none available)")
    return template


def needs_answers(venue: str) -> bool:
    """True if the venue's review template is built from interview answers."""
    path = REVIEW_TEMPLATES[venue]
    return path.exists() and ANSWERS_PLACEHOLDER in path.read_text(encoding="utf-8")


def has_answers(answers_text: str) -> bool:
    """True if the text holds at least one recorded answer (a line starting "Answer:")."""
    return bool(_ANSWER_RE.search(answers_text))


def load_review_prompt(annotated_text: str, venue: str = "colm", answers: str = "") -> str:
    template = fill_reviewing_files(load_template(REVIEW_TEMPLATES[venue]), venue)
    # The paper goes in last: its text is the only part not written by the reviewer.
    template = template.replace(ANSWERS_PLACEHOLDER, answers.strip())
    return template.replace(TEXT_PLACEHOLDER, annotated_text)


def load_interview_prompt(annotated_text: str, venue: str, answers_path: Path) -> str:
    template = fill_reviewing_files(load_template(INTERVIEW_TEMPLATES[venue]), venue)
    template = template.replace(ANSWERS_PATH_PLACEHOLDER, str(answers_path))
    return template.replace(TEXT_PLACEHOLDER, annotated_text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract annotations from a PDF and generate a review prompt.",
    )
    parser.add_argument("--paper", required=True, help="Path to the PDF file (e.g., reviews/foo.pdf)")
    parser.add_argument(
        "--venue",
        choices=sorted(REVIEW_TEMPLATES),
        default="colm",
        help="Review template to use (default: colm)",
    )
    parser.add_argument(
        "--interview",
        action="store_true",
        help="Write the interview prompt instead of the review prompt (venues: "
        + ", ".join(sorted(INTERVIEW_TEMPLATES))
        + ")",
    )
    parser.add_argument(
        "--answers",
        default=None,
        help="File holding your interview answers (default: outputs/reviews/<paper>.answers.md)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Root directory for generated artifacts (default: outputs)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Keep the reference list and unannotated appendix sections",
    )
    args = parser.parse_args()

    pdf_path = Path(args.paper)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    if args.interview and args.venue not in INTERVIEW_TEMPLATES:
        print(f"Error: no interview template for venue '{args.venue}'", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    paper_name = pdf_path.stem
    extracted_path = output_dir / "extracted" / f"{paper_name}.md"
    review_output_path = output_dir / "reviews" / f"{paper_name}.review.md"
    interview_output_path = output_dir / "reviews" / f"{paper_name}.interview.md"
    answers_path = (
        Path(args.answers) if args.answers else output_dir / "reviews" / f"{paper_name}.answers.md"
    )

    # Check the answers before doing any work: an ARR review prompt without the
    # reviewer's answers would ask the model to write the first draft itself.
    answers = ""
    if not args.interview and needs_answers(args.venue):
        answers = answers_path.read_text(encoding="utf-8") if answers_path.exists() else ""
        if not has_answers(answers):
            print(
                f"Error: no interview answers found in {answers_path}.\n"
                f"Run the interview first:\n"
                f"  uv run review --paper {pdf_path} --venue {args.venue} --interview",
                file=sys.stderr,
            )
            sys.exit(1)

    extracted_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 70}")
    print("STEP 1: EXTRACT ANNOTATIONS FROM PDF")
    print(f"{'=' * 70}")
    n_pages, n_highlights, n_notes = extract(pdf_path, extracted_path, full=args.full)
    print(f"✓ Extracted from {n_pages} pages — {n_highlights} highlights, {n_notes} notes")
    print(f"✓ Written to: {extracted_path}")

    print(f"\n{'=' * 70}")
    print("STEP 2: GENERATE INTERVIEW PROMPT" if args.interview else "STEP 2: GENERATE REVIEW PROMPT")
    print(f"{'=' * 70}")
    annotated_text = extracted_path.read_text(encoding="utf-8")
    if args.interview:
        write_prompt(
            load_interview_prompt(annotated_text, args.venue, answers_path),
            interview_output_path,
            "Interview prompt",
            f"Give it to a model and answer its questions. Your answers belong in {answers_path}.",
        )
    else:
        write_prompt(load_review_prompt(annotated_text, args.venue, answers), review_output_path, "Review prompt")

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")
    print(f"✓ Extracted:        {extracted_path}")
    if args.interview:
        print(f"✓ Interview prompt: {interview_output_path}")
        print(f"→ Answers go in:    {answers_path}")
    else:
        print(f"✓ Review prompt:    {review_output_path}")


if __name__ == "__main__":
    main()
