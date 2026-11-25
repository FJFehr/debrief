# Review interview

How a review gets written in this workspace: the reviewer brings notes on a paper, Claude prepares, the two go through an interview that follows the review form, and the review is assembled from the sections the reviewer accepted.

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

Step 1 ends with a short overview for the reviewer: how the notes were sorted, anything the notes ask for that the paper already contains, the parts without notes, and the claim map in a few lines. The reviewer then talks the paper through, as much or as little as they like, before the first section opens.

## Step 2: Interview

### Order

The interview follows the review form, one section at a time, and ends with the bias test. Before the first section, and at any point after it, the reviewer can talk freely about the paper: Claude files what is said onto the points it belongs with and adds nothing. Talk never moves the interview on.

| Section | What Claude asks | What is settled |
|---|---|---|
| 1. Summary | The reviewer's description of the paper, in their own words | The summary paragraph |
| 2. Strengths | Each positive remark in the notes; anything else that argues for acceptance | The strengths |
| 3. Weaknesses | Each concern in the notes, related ones merged; the parts of the paper with no notes | The weaknesses |
| 4. Comments | Everything left in the notes: questions, suggestions, minor issues, typos | The comments |
| 5. Bias test | One question for each strength or weakness where a signal from the register is present | Each tested point is kept, reworded, moved to comments or dropped. The weaknesses are in order of severity. |

Each section runs the same way:

1. **Ask.** Claude puts the section's questions.
2. **Outline.** From the answers, Claude writes the section as it will appear in the review.
3. **Revise.** The reviewer edits the outline or says what to change, and Claude revises it. The reviewer can ask for the plan first: Claude sets out what each sentence or point will carry, and writes only once the plan is agreed.
4. **Accept.** The reviewer accepts the section and the next one opens.

Two things the register calls for are part of the sections for every paper: the case for acceptance (B15) in the strengths, and the parts with no notes (B3) in the weaknesses. They are not asked again in the bias test.

The summary is the reviewer's own description of the paper. Claude does not summarise the paper: it words the paragraph from what the reviewer said and leaves out what they did not say.

### Rules for questions

- **Grounded.** Each question cites the note or the place in the paper it is about.
- **Question first, then the material behind it.** Claude asks the one thing it needs, then gives what the question rests on, labelled by source: the reviewer's note, and what Claude found in the paper ("Table 3 reports three seeds; no variance is shown").
- **Not leading.** Ask what the reviewer thinks, not whether he agrees.
- **Bias questions only in the bias test.** One counterfactual question for each point where a signal is present: state the condition under which the point would not stand, and ask whether that condition holds. Use the wording in the register as a starting point and adapt it to the paper. Do not name the bias in the question unless the reviewer asks why it is being asked.
- **One challenge per point.** If the reviewer gives a reason, record it and move on.
- **No questions about scores.** Scores, confidence and the recommendation are the reviewer's. The register's entries about them (B4, B14, B16) are not asked.
- **Short answers are fine.** So are "skip", "drop it" and "you decide the wording".
- **No points from Claude.** Claude does not offer a strength, a weakness, a comment or a question for the authors that the reviewer did not raise.

### What each section settles

Before a section is accepted:

- Every point in it is a strength, a weakness or a comment, or is dropped.
- A strength has a location.
- A weakness is pinned: it has a location and a fix, and names the claim it undermines. The fix is the reviewer's to give. Claude asks what would resolve the weakness and does not propose it.
- A requested experiment names the claim that needs it, or it is a suggestion and goes to the comments.

Where the paper states something that cuts against a point (the point says a detail is missing and the paper gives it), Claude puts that fact on the point, with its location and without a view. It stays there until the reviewer rewords the point or says it stands.

The order of the weaknesses, most severe first, is the reviewer's to set. Claude does not rank them.

## Step 3: Check

1. Claude runs the checklist in section 7 of the guidelines and the bias checks in section 6 over the accepted sections, and says what is not met and where, starting with anything the paper's text contradicts. Claude does not check or suggest a score.
2. The reviewer fixes what is not met, in the section concerned.

## Step 4: Draft

The review is assembled from the accepted sections, in the venue's form: the summary as accepted, then the strengths, the weaknesses (most severe first) and the comments as they stand. No new text is written at this step. Along with the draft, the reviewer gets:

- **Sources:** for each point, the notes and the reviewer's words it came from.
- **Claude's additions:** any point not from the notes, marked.
- **Changes from the notes:** points moved to another section, and points dropped.
- **Open items:** anything the interview did not settle.

The reviewer edits the draft, sets the scores in the review form, and submits.

## After the author response

A short second interview: for each weakness, most severe first, did the response deliver what was asked? Then draft the two-to-four sentence reply described in the guidelines, leaving the score decision for the reviewer to add.
