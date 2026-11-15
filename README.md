# Debrief: a paper review assistant

You read and annotate a paper. Debrief interviews you about your notes and drafts the review from your answers.

## Why

The aim is better paper reviews. Spend your time reading and making notes. Turning notes into a structured review is the slow part. A language model reads the paper and your notes together and helps with that part. The judgement stays yours.

- 🎙️ **Gets your judgement out quickly.** Five questions about your notes, by voice or typing.
- ⚖️ **Checks for bias and weak reasoning.** Each point is tested against the paper and your known biases.
- 📝 **Writes a structured review.** In the venue's template, each point traced to something you said.

Read, annotate, talk it through, edit, submit.

## Quick start

You need [uv](https://docs.astral.sh/uv/), [Claude Code](https://claude.com/claude-code) (logged in) and a PDF annotated in Preview or Okular.

```bash
git clone <this repository's URL>
cd debrief
uv sync
uv run interview --paper path/to/annotated-paper.pdf
```

A page opens: interview on the left, your paper on the right.

1. **Prepare the interview**, then answer by typing or **Dictate**.
2. **Draft the review**.
3. **Copy Markdown** for each section into the review form. You set the scores.

Drafts are saved in `outputs/reviews/`. Run the same command again to continue.

Before a real review:

- 📋 The form is ARR's; other venues are in the [interview docs](docs/review-interview.md).
- 🧭 The guidelines and biases in [reviewing/](reviewing/) are examples. Replace them with yours.
- 🔒 The paper is sent to Claude. Check that your venue allows this.

## More

| Topic | Where |
|---|---|
| The interview | [docs/review-interview.md](docs/review-interview.md) |
| Annotation format | [docs/annotation-format.md](docs/annotation-format.md) |
| Reading notes | [docs/reading-notes.md](docs/reading-notes.md) |
| Development | [docs/development.md](docs/development.md) |
