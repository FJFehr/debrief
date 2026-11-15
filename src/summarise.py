"""Generate a prompt ready for manual pasting into Claude or a local model.

Usage:
    uv run summarise outputs/extracted/foo.md

Writes: outputs/prompts/foo.prompt.md (ready to paste into a model)
"""

import sys
from pathlib import Path

from src.review import TEXT_PLACEHOLDER, load_template, write_prompt

PROMPT_PATH = Path("prompts/templates/summary.md")


def load_prompt(annotated_text: str, preface_text: str = "") -> str:
    full_input = annotated_text
    if preface_text.strip():
        full_input = preface_text.strip() + "\n\n" + annotated_text
    return load_template(PROMPT_PATH).replace(TEXT_PLACEHOLDER, full_input)


def summarise(input_path: Path, output_path: Path, preface_text: str = "") -> None:
    annotated_text = input_path.read_text(encoding="utf-8")
    write_prompt(load_prompt(annotated_text, preface_text=preface_text), output_path, "Prompt")


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: uv run summarise outputs/extracted/foo.md",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path("outputs/prompts") / f"{input_path.stem}.prompt.md"
    summarise(input_path, output_path)


if __name__ == "__main__":
    main()
