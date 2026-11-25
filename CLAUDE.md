# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

Debrief, a paper review assistant. It turns a PDF that the reviewer has annotated (highlights and margin notes) into a drafted review, in three steps:

1. **Extraction**: the PDF becomes Markdown with every highlight and note in place.
2. **Interview**: a browser page where the reviewer talks their notes through and a model asks about them, following the review form section by section (summary, strengths, weaknesses, comments). It builds an index of the reviewer's points, which the reviewer can edit at any time, and tests them against a bias register.
3. **Draft**: the app assembles the review in the venue's form from the sections the reviewer accepted. No model writes at this step.

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

**Talk never moves the interview on.** The reviewer can say anything at any step. It is stored as sent and filed onto points; a filed reply or a plan cannot write or change text, and the server enforces that, not the prompt. Only a button ends a step.

**The model never summarises the paper and raises no points of its own.** The summary is the reviewer's description in their own words, which the model only tidies. Every strength, weakness, comment and question for the authors comes from the reviewer. There is no setting that lets the model offer one. This keeps Debrief inside ICML 2026's Policy B ([docs/review-interview.md](docs/review-interview.md#icml)); do not add a feature that crosses it.

**A fact from the paper is not an opinion.** Where the paper states something that cuts against a point, the model puts that fact on the point with its location. It stays until the reviewer rewords the point or says it stands.

**Scores stay with the reviewer.** Scores, confidence and the recommendation are set by the reviewer in the review form. They never pass through the software: it does not ask for them, suggest them or comment on them.

**README style.** Short: only the wording a new reader needs, with detail left to `docs/`. Bullets lead with an emoji and a bold label. Say "paper review", not "peer review".

**Tests.** `uv run pytest` must pass before a commit. Tests that fetch from live sites are opt-in: `uv run pytest -m network`.
