# Review interview

How a review gets written in this workspace: the reviewer brings his notes on a paper, Claude prepares, the two go through a short interview, and Claude drafts the review from the answers.

The interview exists to get the reviewer's judgement stated clearly and to test it against the biases in [BIASES.md](BIASES.md). It does not replace his reading or his decision.

## Inputs

- The paper (PDF in this folder).
- The reviewer's notes: annotated PDF, margin notes, or a rough review.
- The venue, so the right file in [venues/](venues/) is used.

## Step 1: Preparation (Claude, before asking anything)

1. Read [REVIEWING_GUIDELINES.md](REVIEWING_GUIDELINES.md), the venue file, and [BIASES.md](BIASES.md).
2. Read the whole paper, including the appendix.
3. **Claim map.** List the paper's main claims, and for each the evidence offered and where it is.
4. **Sort the notes.** Put each note into one of: weakness candidate, comment, question, strength, or a note-to-self about understanding.
5. **Check the notes against the paper.** For each question or request, look for the answer in the paper or appendix. Record where it is, or that it is absent.
6. **Coverage.** Record which sections and pages have no notes.
7. **Bias signals.** Go through the register and record which signals are present, with the note or location that triggered each.

Step 1 ends with a short brief to the reviewer: the claim map in a few lines, how the notes were sorted, anything the notes ask for that the paper already contains, and what the interview will cover. The reviewer can correct the brief before the questions start.

## Step 2: Interview

### Order

Questions follow the reading order in the guidelines, so the idea is settled before the writing is discussed.

| Round | Purpose | Source of the questions |
|---|---|---|
| 1. The idea | State the core idea, what is new, whether it matters | Always asked. B5. |
| 2. Soundness | For each weakness candidate: what is missing, where, which claim it undermines | Claim map and notes. B1, B2, B6–B9, B13 where triggered. |
| 3. Gaps | Sections with no notes; requests the paper already answers | Coverage and note check. B3. |
| 4. Triage | Weakness or comment, for each remaining point | Guidelines section 4. B10–B12 where triggered. |
| 5. Strengths | What argues for acceptance | Always asked. B15. |
| 6. Deciders | Which weaknesses set the score, what would raise it, confidence | Always asked. B4, B14, B16. |

### Rules for questions

- **Small rounds.** Two to four questions at a time, about ten to fifteen in total. Fewer for a short or clear-cut paper.
- **Grounded.** Each question cites the note or the place in the paper it is about.
- **Facts first, then the question.** Claude says what it found ("Table 3 reports three seeds; no variance is shown") and then asks.
- **Not leading.** Ask what the reviewer thinks, not whether he agrees.
- **Bias questions only when triggered.** Use the wording in the register as a starting point and adapt it to the paper. Do not name the bias in the question unless the reviewer asks why it is being asked.
- **One challenge per point.** If the reviewer gives a reason, record it and move on.
- **Short answers are fine.** So are "skip", "drop it" and "you decide the wording".
- **Claude's own observations** are offered separately from the questions and labelled as Claude's. The reviewer accepts or drops each.

### What each answer settles

For every point, by the end of the interview:

- Is it a weakness, a comment, or dropped?
- For a weakness: location, the claim it undermines, what would resolve it.
- For a requested experiment: the claim that needs it, or that it is a suggestion.

## Step 3: Draft (Claude)

Write the review in the venue's form, following the guidelines. Along with the draft, give the reviewer:

- **Changes from the notes:** points moved to comments, merged, or dropped, each with the reason from the interview.
- **Claude's additions:** any point not from the notes, marked.
- **Open items:** anything the interview did not settle.

## Step 4: Check

1. Run the checklist in section 7 of the guidelines.
2. When the reviewer gives his scores, compare them with the text: a low soundness score needs a named fault; the weaknesses marked as deciders should account for the overall score. Say where they do not match. Do not suggest a score.
3. The reviewer edits and submits.

## After the author response

A short second interview: for each decider weakness, did the response deliver what was asked? Then draft the two-to-four sentence reply described in the guidelines.
