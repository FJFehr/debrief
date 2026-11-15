# Plan: the interview follows the review form

To-dos collected from the reviewer's feedback while reviewing with Debrief, and what became of each. The first round is listed first; the second round changed some of it, as the table at the end of that section shows. Directions that are not being built yet are in [future-plans.md](future-plans.md).

## Principles the feedback set

- The interview is organised by what the review form needs: summary, strengths, weaknesses, comments.
- Every message opens with what the reviewer must answer. Material follows, labelled by source.
- Text for the review is plain and factual: no figures in the summary, no amplifiers or superlatives.
- The reviewer can see, reopen and reword anything already settled.
- Judgement stays with the reviewer: the model does not rank points and the software does not handle scores.
- Reviews and anything quoting a paper stay local.

## Built

**Sections and the index (server)**

- [x] Stages: brief, summary, strengths, weaknesses, comments, bias test, draft, final.
- [x] An index of entries, each with a fixed ID, a claim, the bullet as it will appear, its notes, its places in the paper and the reviewer's words.
- [x] IDs by kind: `S` strengths, `W` weaknesses, `C` comments, `O` Claude's observations. An entry that moves kind takes a new ID and keeps the old one as a pointer.
- [x] A weakness holds its claim, where it shows, which claim it undermines and what would resolve it. It cannot be accepted without a location and a fix. A strength needs a location.
- [x] Each section runs the same way: questions, outline, spoken or hand edits, accept.
- [x] A spoken edit makes the model write a plan first, one line per sentence or entry, with the reviewer's words behind it.
- [x] The record lists each section's exchange, the edit requests as spoken, the accepted summary and the index.

**The page**

- [x] The flow on the left with a tick per finished step; clicking one shows its result and the exchange behind it.
- [x] The index on the left, always visible, weaknesses in severity order.
- [x] Clicking an entry opens it: edit its parts by hand, move it, drop it, reorder it, or say what to change.
- [x] The severity order is set by the reviewer, with arrows on the index rows or in the open entry.
- [x] An ID in any message shows its claim on hover and opens the entry on click.
- [x] Each entry links to its notes; places in the paper are links.
- [x] Clicking a point's text beside its buttons makes it editable.
- [x] No Record or Restart buttons. `--restart` stays on the command line.

**The four sections**

- [x] Summary: five or six sentences, about 60 to 100 words, one job each, no figures, no amplifiers, method and benchmark names only, ending "The main contribution is", built only from the reviewer's description.
- [x] Strengths, weaknesses and comments, each from the notes, one question per candidate.
- [x] For a weakness with no location the model asks and lists the places that bear on it. For one with no fix it asks and does not propose one.
- [x] The reviewer's earlier preferences for the text carry over: locations at section or table level, only the reviewer's figures, the fix as a first-person sentence without a label, about 700 to 900 words in all.

**Bias test and scores**

- [x] One bias test after the four sections: one counterfactual question for each strength or weakness where a register signal is present.
- [x] No bias questions inside the sections.
- [x] Nothing about scores: no questions on what sets them, no scores block in the review or the venue template.
- [x] The register's three score-related entries are shown as fixed text on the final step.

**Check, draft and final**

- [x] The guidelines' checklist runs over the review before the draft.
- [x] The draft is assembled by the app from the accepted summary and the index, in severity order. No model writes it.
- [x] The trace lists, for each point, its notes and the reviewer's words, and marks a quote that is not found word for word.
- [x] Final step: the review as submitted is saved to `outputs/reviews/` and copied into `reviewing/my_reviews/` as an example.
- [x] Past reviews go into the interview prompt as examples of voice, the five most recent only.

**Checked**

- [x] Tests for stages, the index, the gate, the record, the draft and old-format sessions.
- [x] A full interview in a browser against the real server with a scripted model.
- [x] One full interview with a live model on a real annotated paper.

## Where the build differs from the plan

| Planned | Built |
|---|---|
| Old-format interviews can be finished | They open read-only. Both saved ones were already finished. |
| The draft button is disabled until the check passes | The check is the first button on the draft step, and the draft can be made without it. Entries with gaps turn the button into "Draft anyway". |
| A check after the draft confirms nothing was lost | Not needed: the draft is assembled from the index and follows every later edit. |
| Weaknesses renumbered in the draft | The review text carries no IDs; the bullets are in severity order. |
| Past summaries feed the summary stage, and so on | Whole past reviews are given once, and the model is told to match the same section. |

## Built: the look of the page

Decided with the reviewer. Colours come from the `mysterious_primary` palette of the reviewer's on-the-fly template, and the rules from their colour, layout and typography guides, adapted from a page that is read to a tool that is worked in.

**Colour**

- [x] The palette's warm neutrals for backgrounds, text and dividers, in light and dark.
- [x] One meaning for each hue. Teal: the reviewer's words, the current step, links, the main button. Gold: Claude's own observations, until they are adopted or dropped. Brick: what a section still needs before it can be accepted, and errors.
- [x] Strengths, weaknesses and comments get no colour of their own; their IDs and groups separate them.
- [x] "What I need from you" is neutral. The teal tint is kept for the reviewer's words.
- [x] Additions the palette lacks: the darker teal as the fill of the main button (white on the base teal is 3.9:1), and a border tone for inputs and buttons that reaches 3:1.
- [x] On the tints, text is the main text colour, not the muted one, and links use the darker teal; the muted and link colours fall below 4.5:1 there.
- [x] A light and dark switch in the top bar: one button, moon in light and sun in dark. It starts from the system setting and remembers the choice.
- [x] The paper stays white in dark mode. The marker that points to a place is an outline with no fill, so highlights keep their colour. Each colour tag shows a swatch beside the name.

**Type and spacing**

- [x] System sans everywhere; the only serif is in the paper itself. No fonts from the network.
- [x] Four sizes: 12 labels and tags, 14 lists and hints, 16 reading and writing, 20 titles.
- [x] Spacing in steps of 4 and 8. One corner radius of 8px; tags are pills.
- [x] The interview column is capped near 680px; the paper takes the rest.

**Alignment**

- [x] One top bar of one height across the three panes (paper name, step title, page number and theme switch), so the rule under it runs straight across.
- [x] Ticks in the flow, IDs in the index and IDs in an outline share one marker column.
- [x] One 16px gutter in every pane.
- [x] Notes under a page are laid out on one grid: ID, line, colour, text.
- [x] The order of the weaknesses sits beside their heading in the index, in small type, so the heading stays on one line.

**Behaviour**

- [x] One main button per state. When a section cannot be accepted yet, Revise is the main button.

**Checked**

- [x] The real page over an invented annotated paper with a scripted model, in a browser: light, dark, and a wide window.
- [ ] Not yet seen in use: the marker that points to a place, and the page number while scrolling.

## Built: second round of use

Feedback collected while the reviewer used the first build on a real paper, built after that review was finished. The main finding was that the page was too wordy and offered too much to edit, so most items below cut something or fold it away.

**One view per step**

- [x] A step shows only where it stands now: the questions, or the section as it will appear. Earlier messages are folded under "The exchange so far"; the record still holds all of them.
- [x] The questions of a section are gone once it has an outline. There is no "What I need from you" heading.
- [x] Each question shows the reviewer's notes under it. What the paper says and the guide to a complete answer are folded under "From the paper".
- [x] The model is told to ask in one sentence of 25 words or fewer, with about 60 words of material.
- [x] The summary is one paragraph in one box, in the step itself, with what changed under it. The numbered list of sentences is gone.
- [x] In the bias test the questions stay on screen, each marked once the reviewer's answer has settled it, with a count.
- [x] Text boxes are larger and grow with their text.

**A point is its text**

- [x] Opening a point shows its text as it will appear in the review, and the reviewer edits it directly.
- [x] A text the reviewer wrote stands. The parts the model sends do not replace it; the model can only send a new text, and only in reply to something the reviewer said. This closes the open item on hand-written wording.
- [x] The parts (label, body, location, claim undermined, fix) are folded under "Parts". "Build it from the parts again" gives the text back to them.
- [x] A point can be spoken to at any time after the brief, not only once its section has an outline.
- [x] Dictation writes into the text box last clicked in, so a point's text can be dictated.
- [x] Under "From your notes" each note shows the words of the paper it is attached to.
- [x] A point with no location offers the places its notes sit in (section, table or figure, line) to take with one click.
- [x] A gap no longer blocks. The section can be accepted as it is ("Accept … anyway"). An observation of Claude's still has to be decided.
- [x] The group on a comment is gone: from the page, the model's instructions, the record and the review, where comments are now one list. A saved interview that carries groups still opens.

**The left bar**

- [x] A button hides it and brings it back. The choice is remembered.
- [x] The index is in the order of the form: summary, strengths, weaknesses, comments. The summary is one row that opens the paragraph.

**Bias register**

- [x] "Why is this asked?" shows the entry, how the bias showed, what set it off and its source, with a link where the source is a page.
- [x] The register has a Source column. Entries that rest on an ARR reviewer shortcut link to the list of shortcuts in the ARR guidelines; that page has one anchor for the list, not one for each shortcut.
- [x] Adding a row to `reviewing/BIASES.md` adds a bias. No code changes.

**The check**

- [x] One finding for each point, each with buttons: use the suggestion, edit the point, or set the finding aside.
- [x] A suggestion is the point reworded from the reviewer's notes, answers and the point itself, tied to the place the notes sit in. The model is told to add no reason, judgement, figure or request, and to leave the suggestion empty when the notes do not hold what the fix needs.
- [x] Nothing changes until the reviewer takes a suggestion.

**Type**

- [x] Titles and labels are in the serif of the reviewer's template, in sentence case. Text stays in the sans. The small grey capitals are gone.

**Dictation**

- [x] The note about the browser's speech service is gone from the page. The guide still says where dictation audio goes.
- [ ] Speech-to-text on the machine. See [future-plans.md](future-plans.md).

**Stock-take after each paper**

- [x] The app keeps a usage log for each paper: every request with what it changed, refusals included, and what the reviewer did on the page (opened, unfolded, followed, dictated).
- [x] `uv run stocktake --paper …` prints a summary of it: time per step, changes by voice and by hand, refusals, and what was used.

**Checked**

- [x] Tests for the text of a point, accepting with gaps, a change during the questions, the check's findings, the register's sources, the usage log and the stock-take.
- [x] A full interview in Chrome against the real server, with a scripted model and an invented annotated paper.
- [ ] Not yet run with a live model: the shorter questions, the check's suggestions, a change during the questions, and the model revising a text the reviewer wrote. The next real paper is the test.

**Decisions made while building, for the reviewer to confirm**

| Question | Decided |
|---|---|
| The Dictate button sends audio to the browser's service. Remove it with the note? | Kept. It is how the reviewer dictates, and there is no replacement on the machine yet. |
| May a suggestion from the check add a reason found in the paper? | No. It only connects what the reviewer wrote to where it shows. |
| Which links to add to a point? | The paper's words under each note, and one-click locations. The other candidates were left out to keep the point short. |
| Is a location or a fix still required? | No. The gap is shown and can be accepted. |
| Does the serif cover the notes and quotes too? | No. Labels and titles only, as in the template. |

**Where the second round changed the first**

| First round | Now |
|---|---|
| A weakness cannot be accepted without a location and a fix | It can, with the gap shown |
| The index lists weaknesses first | Summary, strengths, weaknesses, comments |
| System sans everywhere | Serif for titles and labels |
| A step shows its whole exchange | A step shows where it stands; the exchange is folded |
| The check is a block of text that changes nothing | Findings with suggestions the reviewer can take |
| Comments in three groups | One list |

## Still open

- [ ] The second interview after the author response.
- [ ] An anonymised export of a saved review that can be shared.
- [ ] After the interview, the summary can be changed by hand but not by voice.
- [ ] A suggestion taken from the check cannot be undone with one click; the point has to be edited back.
