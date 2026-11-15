# Development

## Folders

| Folder | Purpose |
|---|---|
| `reviews/` | Input: annotated submissions under review (gitignored) |
| `papers/` | Input: annotated papers for reading notes (gitignored) |
| `reviewing/` | Reviewing guidelines, bias register, interview process, venue forms. Past reviews (`my_reviews/`, which the interview's final step adds to) and their analysis are gitignored |
| `prompts/templates/` | Prompt templates used at run time |
| `outputs/` | Everything else that is generated; gitignored |
| `outputs/extracted/` | Extracted `.md` files and `.annotations.json` sidecars |
| `outputs/reviews/` | Saved interviews and their records, checks, review drafts, reviews as submitted, and usage logs |
| `outputs/prompts/` | Reading-note prompts |
| `outputs/bibtex/` | BibTeX sidecars |
| `docs/` | This documentation, plus venue guidance |
| `src/` | Source code |

## Code

| Module | Role |
|---|---|
| `src/extract.py` | Extraction: orchestration and the `extract` command |
| `src/layout.py` | Words, lines, review line numbers, column order |
| `src/floats.py` | Figures and tables |
| `src/annotations.py` | Reading annotations and matching them to text |
| `src/render.py` | Markdown output and the annotation table |
| `src/interview_app.py` | The browser interview (`interview` command); its page is `src/interview_static/index.html` |
| `src/usage.py` | The stock-take printed from an interview's usage log (`stocktake` command) |
| `src/review.py` | Review and interview prompt files (`review` command); loading of `reviewing/` documents |
| `src/pipeline.py`, `src/summarise.py`, `src/get_bibtex.py` | Reading-note pipeline (`pipeline` command) |

## Tests

```bash
uv run pytest
```

Every PDF in `reviews/` and `papers/` is run through extraction as a smoke test. The pipeline test builds its own small annotated PDF.

Tests that check exact text from a real annotated paper go in `tests/test_local_*.py`. That pattern is gitignored, because such tests quote a paper under review.

The BibTeX tests that fetch from live sites are left out by default. Run them with:

```bash
uv run pytest -m network
```

## Nothing confidential in the repo

The repo must not name the reviewer, a submission under review, or quote a review. `reviews/`, `papers/`, `outputs/`, `reviewing/my_reviews/` and `tests/test_local_*.py` are gitignored for that reason. Examples in code, prompts, tests and documents use invented names.
