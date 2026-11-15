# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A reviewing assistant. It turns a PDF that the reviewer has annotated (highlights and margin notes) into a drafted peer review, in three steps:

1. **Extraction**: the PDF becomes Markdown with every highlight and note in place.
2. **Interview**: a browser page where a model asks the reviewer about their notes, one question at a time, and tests their points against a bias register.
3. **Draft**: a model writes the review in the venue's form from the interview record.

The reviewer's notes and spoken answers are the source of every judgement. The model asks, organises and rephrases; it does not supply opinions of its own.

An older second use, a prompt for a personal reading note with BibTeX (`uv run pipeline`), is still there but is not the focus.

## Where things are

| Topic | File |
|---|---|
| How to run it, quick start | [README.md](README.md) |
| The interview, its stages, output files, options | [docs/review-interview.md](docs/review-interview.md) |
| The annotated-text format | [docs/annotation-format.md](docs/annotation-format.md) |
| Folder layout, code layout, tests | [docs/development.md](docs/development.md) |
| Reading notes and BibTeX | [docs/reading-notes.md](docs/reading-notes.md) |
| Reviewing guidelines, bias register, interview process, venue form | [reviewing/](reviewing/) |
| Prompt templates used at run time | [prompts/templates/](prompts/templates/) |

## Rules

**Nothing confidential in the repo.** Tracked files must not name the reviewer, name or quote a submission under review, or quote a past review. Use "the reviewer" and invented examples. Annotated PDFs (`reviews/`, `papers/`), everything generated (`outputs/`), past reviews (`reviewing/my_reviews/`) and tests that quote a real paper (`tests/test_local_*.py`) are gitignored and stay that way.

**Only files in this repo.** The reviewing documents are read from `reviewing/` and PDFs from `reviews/`. Nothing is copied in from other folders.

**Extraction keeps annotations exact.**

- Highlights are marked inline; their text comes from the highlight quads, never the bounding box.
- Notes are placed after the line they are anchored to, in the same column as the note, not collected at the end.
- Highlight and note colour is always kept.
- Review line numbers (ACL/ARR margins) are stripped from the text and kept as `⟨L…⟩` and `@L…` references.
- Each page boundary is marked: `--- Page 3 ---`.

**The reviewer's words are stored as sent.** The interview record is written by the server, not the model, and answers are never tidied.

**Tests.** `uv run pytest` must pass before a commit. Tests that fetch from live sites are opt-in: `uv run pytest -m network`.
