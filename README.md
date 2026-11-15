# Paper Assistant

Turns a paper you have read and annotated into a drafted peer review, by interviewing you about your notes and writing the review from your answers.

## Why

Reading the paper is your job and stays your job: you read it and mark it up with highlights and margin notes. The slow part comes after, when the notes have to become a structured, fair review. This repo automates that part, the writing and the questioning around it.

- **It gets your judgement out of your head quickly.** The interview goes through your notes one question at a time, and you answer by voice or by typing.
- **It checks for bias.** Before anything is drafted, your points are tested against a register of your known reviewing biases.
- **It writes in the venue's form and your style.** The draft follows the venue's template and your own reviewing guidelines, and each point traces back to something you said.

The result is more reviews for the same reading: read, annotate, talk it through, edit, submit.

## Quick start

You need [uv](https://docs.astral.sh/uv/), [Claude Code](https://claude.com/claude-code) installed and logged in (the `claude` command), and a PDF annotated in macOS Preview or Okular.

```bash
git clone <this repository's URL>
cd research-assistant
uv sync
uv run interview --paper path/to/annotated-paper.pdf
```

A browser page opens with the interview on the left and your annotated paper on the right.

1. Click **Prepare the interview**, then answer the questions. Type, or use **Dictate**.
2. Click **Draft the review**.
3. Copy each section into the review form with its **Copy Markdown** button. Optionally click **Check the draft against your guidelines**. Scores are yours and are not asked for.

The draft is saved to `outputs/reviews/<paper>.review-draft.md`. Closing the page loses nothing: run the same command again to continue.

Three things to know before a real review:

- The review form is ARR's. Other venues are covered in [docs/review-interview.md](docs/review-interview.md).
- The guidelines and bias register in [reviewing/](reviewing/) are one reviewer's own. Replace them with yours.
- The paper's text is sent to Claude through your Claude Code login. Check that your venue allows this for confidential submissions.

## More

| Topic | Where |
|---|---|
| How the interview works, its output files, privacy, other venues | [docs/review-interview.md](docs/review-interview.md) |
| How highlights and notes are extracted from the PDF | [docs/annotation-format.md](docs/annotation-format.md) |
| Personal reading notes and BibTeX from an annotated paper | [docs/reading-notes.md](docs/reading-notes.md) |
| Folder layout, code layout, tests | [docs/development.md](docs/development.md) |
