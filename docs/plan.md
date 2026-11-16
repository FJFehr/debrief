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

## Third round of use: notes

Collected while a review is in progress. Nothing here is built until that review is finished and its stock-take is read.

| # | What the reviewer noticed | Proposed change |
|---|---|---|
| 1 | The button that hides the left column is three lines (☰) and does not say what it does | A panel icon with an arrow that points the way the column will move: in when the column is shown, out when it is hidden. The tooltip names the one action ("Hide the steps and index" / "Show the steps and index") |
| 2 | The heading over the middle column reads "Brief", which looks like the app's name cut short. The app's name is nowhere on the page | Put "Debrief" on the page as the app's name, and in the tab title. Rename the step: the reviewer's later note is that it should not be called "Brief" at all. Their candidates: "Overview of notes", "Overview", "Debriefing". Proposed: "Overview" in the flow and "Overview of your notes" as the heading. "Debriefing" would again sit too close to the app's name, and the whole interview is the debriefing, not its first step. The rename goes through the page, the prompts and the docs |
| 3 | After reading the brief, the reviewer wanted to talk their thoughts through before the summary. The brief only offers "correct it or go on", so there was nowhere to put them and the start felt bogged down | An open turn between the brief and the summary: "Talk it through". The reviewer says whatever is on their mind, in any order, as many times as they like. The model sorts each remark: onto the note or candidate point it belongs with, or as a new candidate (strength, weakness or comment). It adds nothing of its own. The candidates are then waiting in their sections, to keep, merge or drop there. The answer is stored word for word like any other. The turn can be skipped |
| 4 | In the summary, the reviewer wanted to direct the work, not dictate the text: "I am happy with the content; now plan it sentence by sentence and shrink it to the key points". This is a technique they use often. The section does not allow it: a change request goes straight to a rewritten paragraph, and the plan is only shown afterwards as "what changed" | A "Plan first" way to revise the summary. The model answers with the plan alone, one line for each sentence: its job, the key point it carries, and keep, cut, merge or shorten. The reviewer edits the plan by hand or by voice, as many rounds as they like, and the paragraph is written only when they say so. The sentences already carry a `job`, so the page can show the paragraph sentence by sentence. The rule stays that the content is only what the reviewer described; the instruction is about how to shape it. Worth offering in the other sections too if it works here |
| 5 | Hovering over a note shows its text too small, in a plain box, and after a wait. The reviewer wants a large block they can read at a glance | The hover is the browser's own tooltip (the `title` attribute), which is why it is small, grey and about a second late. Replace it with the page's own card: shown at once, body-size text or larger, dark ink on the note's own colour (yellow where the note has none), wide enough to hold the whole note. Use the same card for the hover on an entry ID, which is also a `title` today |
| 6 | The end is not clear. The last step shows a save button and nothing says the review is done. The reviewer wants to be told it is complete and saved, to see the sections with the ways to use them (copy as Markdown, edit in place), and to be able to talk to the model about the review there: "change this, change that order" | A closing screen for the Draft and Final steps. First line: "Your review is drafted and saved", with where. Then the sections, each with Copy Markdown and editable in place. Then one conversation box over the whole review: the reviewer says what to change, in any section and in any number at once (reword, reorder, move, drop), the model answers with its plan and the changed points, and the draft is put together again. Today a change at the end has to be made one entry at a time from the index, and the summary cannot be changed by voice at all (see Still open). Scores stay out of this conversation |

Notes 3, 4 and 6 are one request seen three times: the reviewer wants to talk freely with the model about the paper, the notes and the review, at the start, inside a section and at the end, and not only answer the questions a step puts to them.

## Third round of use: stock-take

From the usage log of one review (`uv run stocktake`), read next to the notes above. One paper, so each figure is a single sample.

| Step | Minutes | Of which waiting | What happened |
|---|---|---|---|
| Overview (brief) | 1.0 | 0.2 | Read for about 25 seconds, then the reviewer started talking |
| Summary | 11.1 | 0.9 | Three free remarks, then a summary typed by hand, then one request to shorten |
| Strengths | 5.7 | 0.4 | One answer, dictated in four pieces |
| Weaknesses | 10.9 | 1.2 | One answer and five spoken changes, about 8 seconds each |
| Comments | 2.2 | 0.3 | Two kept and one dropped with the buttons, no spoken answer |
| Bias test | 2.8 | 0.1 | One answer; "Why is this asked?" opened three times |
| Draft | 1.6 | 1.2 | The check ran for 70 seconds and was read for 22 |
| Final | 4.0 | 0.0 | Four copies; "Save as submitted" pressed twice |

The whole review took 41 minutes of active time, 5 of them waiting for the model.

What the log shows:

1. **Free talk was taken as answers.** The reviewer's first three messages were a comment, a strength and a weakness. None answered the question on screen. The first, sent from the overview, moved the interview on to the summary. The next two were read as answers to the summary questions. After its one permitted follow-up the model had to write a summary, and it wrote one from the notes, which the rules do not allow. The reviewer then typed their own summary, which took five minutes. About nine of the eleven minutes in the summary come from this (notes 3 and 4).
2. **Directing the model already works where the step allows it.** In the weaknesses the reviewer asked to group the candidates into fewer points, to fold one into another, to set one out under sub-headings and to turn one into a question for the comments. All five were done in one round each. This is the technique of note 4. What is missing is a plan that can be agreed before the text is rewritten, and any of it in the summary.
3. **The reviewer works by voice.** Twenty dictations and eight spoken changes, against no hand edit to any text. Three points were opened and none was edited. The order arrows, "Move to" and "Parts" were not used. The keep and drop buttons were used three times.
4. **The left column was hidden for most of the review.** It was toggled nine times in the first minute (note 1), then stayed hidden through the summary, strengths and weaknesses, and was shown again from the comments on.
5. **Facts from the paper that cut against a point did not reach the reviewer.** The check listed six findings. Two said that a point states the paper does not explain something that the paper does explain, and the paper's text bears both out. None of the six was taken or set aside, and both points went into the saved review as they were. The model had mentioned one of the two facts 35 minutes earlier, in a line about how it had filed an answer. So the fact was shown twice and missed twice.
6. **The check is the longest wait and the least read.** 70 seconds, at the moment the reviewer wants to finish.
7. **The end gave no confirmation.** "Save as submitted" was pressed twice in five seconds. The text saved is the draft unchanged, so the example kept for later reviews may not be what was submitted. Dictation was started twice in the box on the last step and nothing was sent (note 6).
8. **Used a little:** links into the paper (2), "From the paper" (2), the bias test's question about the order of severity (not answered).

## Built: third round of use

Built on 2026-11-16, from the plan below as the reviewer decided it. Where the build differs, the line says so.

Four principles follow from the stock-take:

- **The reviewer talks, the app files.** Every step accepts free talk. What is said is stored word for word and sorted onto the points it belongs with.
- **Only a button moves the interview on.** Sending text never ends a step.
- **A fact stays on its point.** Where the paper states something that cuts against a point, that fact is shown on the point until the reviewer settles it.
- **Voice first.** The box and the microphone are the centre of each step. Hand controls stay, in second place.

### A. Talk and file (notes 3 and 6)

- [x] **A new kind of turn, `talk`.** Allowed at every step after the overview is prepared: the overview, a section's questions, a section's outline, the draft and the final step. It never changes the step. The model's message ends `[Next: file · <step>]`. The page offers it at the overview and beside a section's questions. Where a section is written out, and after the interview, the one box takes a change request, and the prompt has the model file a remark that is about something else.
- [x] **The model's reply, `kind: filed`.** One line for each remark: where it went. A remark that belongs with an existing point is attached to it as a quote. A remark that belongs nowhere becomes a candidate strength, weakness or comment, with a label and the quote only. The server drops anything else from a `filed` reply: no summary sentences, no body, no fix.
- [x] **Remarks are kept on the point.** Each point gets a list of the reviewer's remarks. They are shown under the point and sent to the model with the index, so the section's outline is written from them. Not built: a remark is not yet checked against the record the way `said` is.
- [x] **The overview step.** The box reads "Talk it through: anything on your mind about the paper". Two buttons: **File this**, and **Go on to the summary**. An empty box goes on; text is filed and the step stays open.
- [x] **A section's questions.** Two buttons: **Send answer** and **File a thought**. As a backstop the prompt changes: an answer that does not address the section's questions is filed and the questions are put again. The limit of one follow-up no longer forces an outline.
- [x] **The summary no longer waits on a description.** It is drafted from the paper (decision 1), so free talk in the summary step is filed and the draft stands.
- [x] **The draft and final steps.** The change box becomes "Talk about the review: say what to change, anywhere". One message may reword, reorder, move and drop several points. The summary can be changed here by voice too: the server applies summary sentences on a change at these steps, which closes an item under Still open.

### B. Plan first (note 4)

- [x] **A second button on every change box: "Plan it first".** The model replies with the plan alone (`kind: plan`): one row for each sentence or point, with the key point it will carry in a dozen words, and keep, cut, merge, shorten or rewrite. The server drops any text sent with a plan.
- [x] **The plan is talked over.** The reviewer says what to change and presses "Plan it first" again, as often as they like. **Write it from this plan** applies it and changes nothing the plan does not list.
- [x] **The summary is shown one numbered sentence to a line** while it is being revised, and as one paragraph once accepted.
- [x] **The summary step opens with the drafted paragraph,** written from the abstract, contributions, introduction and conclusion (decision 1), with no questions: the box under it takes what to add, correct or change.

### C. Facts that cut against a point (stock-take 5 and 6)

- [x] **A new part of a point, `counter`.** When the model writes or revises a point and the paper states otherwise, it adds the fact and its location. A fact with a location, never a view.
- [x] **Shown on the point,** in brick: "The paper says: …", with a link to the place. Two buttons: **Reword** and **It stands**. A section with an open counter is accepted with "Accept … anyway", as with a missing location, and the draft says so in the same way.
- [x] **The check leads with facts.** Findings about what the paper states come first. Each finding is two lines, with its suggestion folded.
- [x] **The check starts when the bias test is accepted,** so its findings are there when the Draft step opens. See decision 2.

### D. A clear end (note 6, stock-take 7)

- [x] **The Final step opens with "Your review is drafted and saved"** and the name of the file.
- [x] **Then the sections,** each with Copy Markdown, and the conversation box of part A.
- [x] **Then "After you submit":** the box and **Save as submitted**. After saving, the page says so, with the time and where the example was kept. The button is disabled until the text changes.
- [x] **A draft saved unchanged is named as such:** "This is the draft as drafted. If you edited it in the form, paste the submitted text here."

### E. The page (notes 1, 2 and 5; stock-take 3 and 4)

- [x] **"Brief" becomes "Overview"** in the flow, and "Overview of your notes" as the heading. The stored name of the step stays `brief`, so saved interviews still open.
- [x] **"Debrief" is on the page** and in the tab title.
- [x] **The bar beside the left column is dragged** to resize the column or to slide it away to the left; a slim handle with an arrow brings it back (decision 3). The ☰ button goes.
- [x] **The heading shows the step and its number** ("2 of 8 · Summary"), so progress is visible with the column hidden.
- [x] **Note and point hovers** are the page's own card: shown at once, large text, dark ink on the note's colour, yellow where it has none.
- [ ] **Nothing is cut yet.** The order arrows, "Move to" and "Parts" went unused in this review. One paper is not enough to remove them. If the next stock-take shows the same, they go behind one "More" control.

### F. So the next stock-take can tell

- [x] The usage log records `talk`, `plan` and `apply` turns, and each counter settled, with how.
- [x] `stocktake` prints: remarks filed by step, plans made and applied, counters raised and how each was settled, and whether the saved final differs from the draft.
- [x] Tests for each of A to D: a `talk` turn never moves the step; a `filed` or `plan` reply cannot change text; an open counter gates acceptance; the summary changes by voice at the end.
- [x] Docs: `docs/review-interview.md`, `reviewing/INTERVIEW.md`, `prompts/templates/interview_app.md` and the README's four steps.

What would show it worked, on the next paper: the summary takes under five minutes; every counter is settled before the draft; the saved final differs from the draft or is marked as unchanged.

### Decisions the reviewer made

1. **The summary is written from the paper.** It should be objective, so its source is the paper's own account of itself: the abstract, the contributions, the introduction and the conclusion. The reviewer's notes matter less here. The model drafts the paragraph from those parts, the reviewer directs the shaping (part B) and may add or correct. The summary describes and does not judge: no criticism, no praise, and nothing from the reviewer's notes that is an opinion. This replaces the earlier rule that the summary holds only what the reviewer described, and the summary step has no questions. The docs say plainly that a model drafts this one section, since a venue may not allow that.
2. **The check runs by itself** when the bias test is accepted.
3. **The left column starts shown.** The bar between it and the interview can be dragged: to any width, and all the way to the left to put the column away. A slim handle with an arrow stays at the edge to bring it back, by a click or a drag. The width and the state are remembered. This replaces the ☰ button of note 1.

## Still open

- [ ] The second interview after the author response.
- [ ] An anonymised export of a saved review that can be shared.
- [ ] A remark filed from talk is not checked against the record word for word, as `said` is.
- [ ] The summary is drafted by the faster model at low effort. Whether that is good enough for an objective summary is to be judged on the next paper; if not, it moves to the overview call, which already reads the whole paper.
- [ ] The page has no test of its own in the suite. It was checked by driving it in headless Chrome through eleven scripted states.
- [ ] A suggestion taken from the check cannot be undone with one click; the point has to be edited back.
