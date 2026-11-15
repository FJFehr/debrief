# Reading notes

The repo's other use: turning an annotated paper into a prompt for a personal reading note, with its BibTeX. This is for papers you read for your own research, not for reviewing.

No API key is needed. The pipeline does not call a hosted model; it writes a prompt you paste into a model of your choice.

```bash
uv run pipeline --paper papers/<name>.pdf --url <paper-url-or-arxiv-id>
```

`papers/` is gitignored.

## Steps

```text
Input PDF (papers/*.pdf)
	↓
[STEP 1: extract.py] → outputs/extracted/<paper>.md
	↓
[STEP 2: get_bibtex.py] → outputs/bibtex/<paper>.bib (optional)
	↓
[STEP 3: summarise.py + template] → outputs/prompts/<paper>.prompt.md
```

1. **Extraction** parses highlights and margin notes and keeps them in place in the text (see [annotation-format.md](annotation-format.md)).
2. **BibTeX retrieval** fetches the entry from an arXiv or venue URL.
3. **Prompt generation** inserts the extracted text into the template `prompts/templates/summary.md`.

Writing the summary itself is a fourth, manual step: paste the prompt into a model.

## Options

| Option | Effect |
|---|---|
| `--paper` | Path to input PDF |
| `--url` | URL or arXiv ID for BibTeX fetching |
| `--no-bibtex` | Skip BibTeX retrieval |
| `--full` | Keep references and unannotated appendix sections |
| `--output-dir` | Output root directory (default: `outputs`) |

Examples:

```bash
uv run pipeline --paper papers/LRAS.pdf --url 2601.07296                 # arXiv ID
uv run pipeline --paper papers/LRAS.pdf --no-bibtex                      # skip BibTeX
```

## Example: ContextualJudge

ContextualJudge is a benchmark paper from ACL 2025. The PDF and its outputs are not in the repo; this shows what a run produces.

```bash
uv run pipeline --paper papers/ContextualJudge.pdf --url https://aclanthology.org/2025.acl-long.470/
```

This generates:

1. **Extracted text** (`outputs/extracted/ContextualJudge.md`): the source text with margin notes and highlights in place.
   ```
   [TITLE: "Does Context Matter? ContextualJudgeBench for Evaluating LLM-based Judges in Contextual Settings"]
   [AUTHORS: "Austin Xu⋆, Srijan Bansal⋆, Yifei Ming, Semih Yavuz, Shafiq Joty Salesforce AI Research"]
   ...
   The large language model (LLM)-as-judge paradigm has been used to meet the demand for a cheap, reliable, and fast evaluation of model outputs...
   [HIGHLIGHT yellow: "approach"]
   [NOTE right: "Evaluated from externally provided context."]
   ...
   ```

2. **BibTeX entry** (`outputs/bibtex/ContextualJudge.bib`), fetched from ACL Anthology:
   ```bibtex
   @inproceedings{xu-etal-2025-context,
       title = "Does Context Matter? {C}ontextual{J}udge{B}ench for Evaluating {LLM}-based Judges in Contextual Settings",
       author = "Xu, Austin and Bansal, Srijan and Ming, Yifei and Yavuz, Semih and Joty, Shafiq",
       booktitle = "Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics",
       year = "2025",
       url = "https://aclanthology.org/2025.acl-long.470/",
       pages = "9541--9564"
   }
   ```

3. **Model-ready prompt** (`outputs/prompts/ContextualJudge.prompt.md`): the template with the annotated text inserted.

The summary the prompt asks for has these sections:

- What was the paper about?
- What problem did they solve?
- How did they solve it?
- Models and data
- Experimental results
- What did they conclude?
- Limitations
- My take
- Summary (exactly 5 sentences)
- BibTeX
