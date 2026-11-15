# Reviewing guidelines

These apply to every review, at any venue. Read this file first, then the venue file in [venues/](venues/) for the form and anything venue-specific. Where the two disagree on format, the venue file wins; on judgement and style, this file wins.

The evidence behind these rules is an analysis of the past reviews in `my_reviews/`. Both are kept out of the repo, because they contain review text.

## 1. Purpose

A review answers two questions for the area chair and one for the authors:

1. Are the paper's claims supported by its evidence?
2. Is the result worth knowing?
3. What specifically would make the paper better, and what would raise my score?

Everything in the review should serve one of these.

## 2. Division of work

- The reviewer reads the paper, forms the judgement, and sets all scores.
- Claude prepares from the reviewer's notes and the paper, interviews him ([INTERVIEW.md](INTERVIEW.md)), drafts the text sections from his answers, and runs the checks in section 6.
- If Claude adds a point that is not in the reviewer's notes, it marks it as its own so the reviewer can accept or drop it.
- Claude does not propose scores unless asked. It does say when the drafted text and a score the reviewer has given do not match.

## 3. Reading order: idea first, writing last

Assess in this order, and do not let a later item substitute for an earlier one.

1. **The idea.** What is the claim, in one sentence? What is the closest prior work and how does this differ? Is the idea plausible, and would it matter if true?
2. **Soundness.** Does the evidence support the claim as stated? Baselines matched and appropriate, statistics adequate for the size of the effect, claims no broader than the experiments, costs reported where efficiency is claimed. If there is theory, is it correct and does it bear on the claim?
3. **Contribution.** What can someone else now do or know? Simple methods, negative results, replications, resources and narrow topics all count.
4. **Presentation.** Can a reader verify the claim from what is written?

Read the whole paper before judging it, including the method sections that are hard going. Check the appendix before asking for something that may be there.

## 4. Structure of a review

### Summary

One paragraph, 60–170 words: what the paper studies, how the method works, what it is evaluated on, the main finding. It may end with one sentence naming the paper's main contribution. No criticism here.

### Strengths

- Usually 3; as many as are real.
- Bold claim as the label, then what the paper does and why it matters.
- Specific to this paper, with a location. At least one strength should engage with the idea itself, not only the experiments.
- Strong enough that an area chair could use them to argue for acceptance.

### Weaknesses

A point is a **weakness** if it affects whether the claims are supported or whether the contribution stands. Everything lighter is a **comment**.

- Five or fewer as a guideline. Go over when there are more than five real ones; never pad, and merge related points first.
- Ordered by importance. Say which ones determine the score.
- Each one has:
  1. **Label:** a bold claim that reads alone ("The main comparison is not matched on training data.").
  2. **Evidence:** what the paper does and what is missing, with section, table, figure or line.
  3. **Consequence:** which claim it undermines.
  4. **To resolve:** the specific experiment, analysis, or rewrite that would address it.

### Comments, questions, suggestions, typos

- Minor issues: notation, a missing definition, figure or table placement, terminology, structure.
- Questions that are requests for clarification.
- Optional experiments and "nice to have" analyses.
- Typos, with locations.

Do not repeat a weakness here. If a point is already a weakness with its fix, it is done.

### After the author response

Two to four sentences: what in the response was valuable, what must still appear in the paper (say if the appendix is enough), and the score decision with the reason.

## 5. Voice

- Bold-claim labels; 2–4 sentences per item.
- Balanced: credit what the paper does before stating the gap.
- Plain and direct about severity. Hedge only where there is real uncertainty; a fatal problem should read as one.
- Impersonal by default, first person for judgements ("I think", "I suggest").
- Questions are welcome as labels ("Which component gives the improvement?").
- British spelling.
- Constructive and respectful: write the review I would want to receive.
- Blunt raw notes are softened, never copied. Remarks about how the paper was produced are dropped.

## 6. Bias checks

Run these on every draft before it is submitted. The full register, with the signal for each bias and the interview question it leads to, is in [BIASES.md](BIASES.md).

### Presentation versus substance

- **Name the fault.** A low soundness score needs at least one specific technical fault stated in the review. If the only problems are motivation and readability, soundness is not low; presentation or clarity is.
- **Hard to read is not wrong.** If I could not follow a method or proof, either work through it or lower confidence and say so. Do not call it unmotivated instead.
- **Presentation is a weakness only when it blocks verification** (undefined terms, missing setup, results not interpretable). If the paper is merely badly written, it is a comment.
- **First impressions.** If the first two pages were poor, check that the later sections got the same attention.

### Requests

- **Tie every requested experiment to a claim.** If the paper's claim needs it, it is a weakness and say which claim. If not, it is a suggestion.
- **Prefer narrowing the claim to adding experiments** when either would fix the problem.
- **Closed or proprietary baselines** are suggestions unless a claim directly depends on them.
- **Statistics:** ask for seeds and intervals when effects are small or the test set is small. Do not ask by reflex.

### My own preferences

These are things I like. They are weaknesses only under the stated condition.

| Preference | A weakness only if |
|---|---|
| Explain why the method works | The paper claims an explanation it does not support |
| Say when to use it; give a community takeaway | Never a soundness issue. Reflect it in excitement or significance. |
| Hypothesis → experiment → result structure | The actual structure makes the claims untestable |
| Depth over breadth | Breadth leaves the main claim unsupported |

### Common reviewer shortcuts

Do not use any of these as a weakness without the stated justification.

- **Not novel:** cite the prior work that did it.
- **Not better than the baseline or state of the art:** matching with other advantages can be the contribution.
- **Negative or unsurprising result:** these are publishable; asking "why would this work?" is not a criticism of a paper that tests whether it does.
- **Too simple, too niche, application of known methods to a new domain:** in scope.
- **I would have done it differently:** valid only if the choice prevents answering the paper's own question.
- **Acknowledged limitations:** not weaknesses by default.

### Calibration

- **Confidence** reflects how well I understood the paper and know the area, not how sure I am it is bad.
- **Familiarity:** for papers outside my own areas, check that I engaged with the idea and did not fall back on a checklist. For papers inside them, check that I was not more generous.
- **Strengths and weaknesses** should get comparable care.

## 7. Before submitting

- [ ] Summary would be recognised by the authors as their paper.
- [ ] Every weakness has a location, a consequence and a way to resolve it.
- [ ] Nothing in Weaknesses is minor; nothing is said twice.
- [ ] The weaknesses that decide the score are identified.
- [ ] Each score the reviewer has given is justified by text in the review.
- [ ] Section 6 checks done.
- [ ] Proofread: complete sentences, complete labels, typos listed if the form asks.
