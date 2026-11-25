# Annotation format

What extraction produces from an annotated PDF. Every other command in this repo starts with this step.

```bash
uv run extract papers/<name>.pdf --full
```

Extraction writes two files per paper:

- `outputs/extracted/<paper>.md`: the paper as Markdown with annotations in place, followed by a table of all annotations.
- `outputs/extracted/<paper>.annotations.json`: the same annotations as records (page, lines, type, colour, text, note, bounding box).

## Example

```
--- Page 4 ---

[FIGURE 2: "The router and its two stages."]
[NOTE A31 left yellow: "Which box is the input?"]

#### 3.2.1 Routing Score

⟨L258–267⟩ The router scores each tool against the query before [HIGHLIGHT yellow: "the final ranking."] Tools below the threshold are dropped.
[NOTE A35 right yellow @L267: "Is the threshold tuned on the test set?"]

⟨L268⟩ [EQUATION 6: "s(q, t) = cos(e_q, e_t) ≥ τ , (6)"]
```

## Markers

- `[HIGHLIGHT <colour>: "..."]` marks highlighted words at their position in the sentence. The text is taken from the highlight's quads, so multi-line highlights are exact. `UNDERLINE` and `STRIKEOUT` use the same shape.
- `[NOTE <id> <position> <colour> @L<line>: "..."]` is a sticky note or free-text box, placed after the line it sits next to. `<id>` (A1, A2, …) is its row in the annotation table and JSON file. Position is `left`, `right`, or `inline`. A note beside a figure or table follows that placeholder.
- `#`, `##`, `###` are the title and section headings, detected from font size, boldness and numbering.
- `[FIGURE N: "caption"]` and `[TABLE N: "caption"]` replace floats. Table cells are kept as raw rows in a fenced block; text inside figures is dropped. `[BOX]` is an uncaptioned framed listing, with its text kept.
- `[EQUATION N: "..."]` holds the raw text of a display equation; `[FOOTNOTE: "..."]` a footnote.
- `⟨L29–42⟩` gives the review line numbers a paragraph covers. Review copies (ACL/ARR) print these in the margins; they are removed from the text and used as references. Papers without them have no prefix.
- `--- Page 3 ---` marks each page boundary.

## Behaviour

- Two-column pages are read left column first; a paragraph that continues in the next column is joined.
- By default the References section is removed and appendix sections without annotations are dropped. Pass `--full` to keep everything (useful when reviewing).
- Annotations made in macOS Preview and in Okular are both read. Empty notes and notes Preview leaves outside the page are skipped and counted on stderr.
