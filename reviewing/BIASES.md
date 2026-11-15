# Bias register

Biases found in the reviewer's past reviews, each with the signal that shows it may be active and the question to ask in the review interview ([INTERVIEW.md](INTERVIEW.md)).

- **Evidence** for every entry comes from an analysis of 13 past reviews. That analysis quotes the reviews, so it is kept out of the repo. Each entry is a suspicion to test, not a verdict.
- **A triggered bias produces a question, never a change.** The reviewer may well be right that the paper is unsound or the experiment is needed. The question asks him to state the reason; his answer decides.
- **H numbers** refer to the reviewer shortcuts in the [ARR reviewer guidelines](https://aclrollingreview.org/reviewerguidelines).
- **Source** says where an entry comes from, and the interview shows it under "Why is this asked?". Separate several with semicolons; write one as a Markdown link where there is a page to open. "Past reviews" is the analysis above.
- **To add a bias,** add a row with the next free ID. The interview reads this file each time it starts.
- Revise this file when new reviews confirm, weaken or add a bias.

## A. Presentation over substance

| ID | Bias, and how it showed | Signal in the notes or draft | Interview question | Source |
|---|---|---|---|---|
| B1 | **Presentation standing in for soundness.** Low soundness scores given with no technical fault named. | Low soundness intended, but every candidate weakness is about motivation, writing or structure. | "Which specific result or argument in the paper is wrong or unsupported? If none, is this a soundness problem or a clarity one?" | Past reviews |
| B2 | **Hard maths judged on readability.** Proofs and dense method sections skipped, then called unmotivated. | Notes say "hard to follow", "unclear why we need this", or stop at a technical section. | "You marked §X as hard to follow. Here is what it does in plain terms: … Does it hold up? Does it bear on the main claim?" | Past reviews |
| B3 | **First-impression halo and uneven coverage.** Most notes on the first two pages, few after; appendix unread. | Note density drops sharply after the introduction; pages or the appendix have no notes; a note asks for something the paper contains. | "There are no notes on pp. X–Y. I read them: … Does that change anything? Your note asks for Z; it is in Appendix C." | Past reviews |
| B4 | **Confidence not tracking understanding.** High confidence given with the method section not followed. | High confidence intended alongside notes showing part of the method was not understood. | "How well do you understand the core method, separately from how sure you are of the verdict?" | Past reviews |
| B5 | **The idea itself is under-examined.** No past review names the closest prior work or argues that a mechanism is wrong. | Notes contain no statement of the core idea, its novelty, or the nearest prior work. | "In one sentence, what is the idea? What is the closest prior work, and what is new here? Would it matter if it is true?" | Past reviews |

## B. Requests and standards

| ID | Bias, and how it showed | Signal in the notes or draft | Interview question | Source |
|---|---|---|---|---|
| B6 | **Extra experiments not tied to a claim** (H13, H14). More modalities or a proprietary baseline asked for as a weakness. | A request for more domains, models, languages, hops or a closed model, with no claim named. | "Which claim in the paper fails without this experiment? Could the authors narrow the claim instead?" | [ARR reviewer guidelines, H13 and H14](https://aclrollingreview.org/reviewerguidelines#review-issues); Past reviews |
| B7 | **Novelty dismissed without a reference** (H3, H7, H9). A method called a combination of existing techniques, with no citation. | "Not novel", "incremental", "just applies X to Y", with no citation. | "Which paper already did this? If none, is applying known methods to this setting a contribution here?" | [ARR reviewer guidelines, H3, H7 and H9](https://aclrollingreview.org/reviewerguidelines#review-issues); Past reviews |
| B8 | **Negative or unexpected results penalised** (H2, H4, H6). A paper faulted for not motivating why its idea should work. | The paper tests whether something holds, and the notes ask why anyone would expect it to. | "The paper's question is whether X holds. Is the answer it gives reliable, whichever way it came out?" | [ARR reviewer guidelines, H2, H4 and H6](https://aclrollingreview.org/reviewerguidelines#review-issues); Past reviews |
| B9 | **Not better than the baseline** (H5). Results that only match the baseline listed as a weakness. | Comparable or mixed results listed as a weakness. | "Does the paper claim to be better, or to offer something else at similar performance? Is that other thing shown?" | [ARR reviewer guidelines, H5](https://aclrollingreview.org/reviewerguidelines#review-issues); Past reviews |
| B13 | **Statistics by reflex.** Asked in 6 of 13 reviews. | Seeds or intervals requested where effects are large and consistent. | "How large are the gains against the likely run-to-run variation? Does the conclusion depend on it?" | Past reviews |

## C. Personal preferences treated as requirements

| ID | Bias, and how it showed | Signal in the notes or draft | Interview question | Source |
|---|---|---|---|---|
| B10 | **"Why does it work?" as a weakness.** 10 of 13 reviews. | Missing mechanism or ablation listed as a weakness. | "Does the paper claim to explain why it works? If not, is showing that it works enough for this paper?" | Past reviews |
| B11 | **Usefulness leaking into soundness.** When to use the method, or a takeaway for the community, asked for in 6 of 13. | Takeaway or practical value listed as a weakness. | "Is this about whether the claims are supported, or about how interesting the result is to you?" | Past reviews |
| B12 | **Structural preference** (H15). Hypothesis-first structure, depth over breadth, short background. | Notes object to how the paper is organised or what kind of paper it is. | "Does the structure stop the paper answering its own question, or is this how you would have written it?" | [ARR reviewer guidelines, H15](https://aclrollingreview.org/reviewerguidelines#review-issues); Past reviews |

## D. How the review reads

| ID | Bias, and how it showed | Signal in the notes or draft | Interview question | Source |
|---|---|---|---|---|
| B14 | **Flat severity.** Fatal and minor issues share the same hedged tone; weaknesses are unranked. | Draft weaknesses all read "not fully…", "may not…". | "Which one or two weaknesses decide your score? What would the authors have to do for it to go up?" | Past reviews |
| B15 | **Thin strengths.** Strengths a fraction of the length of the weaknesses. | Notes contain few or generic positives. | "If you had to argue for accepting this paper, what would you say?" | Past reviews |
| B16 | **Familiarity.** Highest scores in own areas, lowest outside them. Cannot be separated from paper quality at this sample size. | Paper is clearly inside or clearly outside looped models, code retrieval, agents, interpretability. | Outside: "Is there anything here you would want an expert to check?" Inside: "Would you accept this evidence from a paper in a field you know less well?" | Past reviews |

## Biases to watch in Claude

The interview can introduce its own distortions.

- **Over-correction.** Asking these questions on every point pushes towards leniency. Ask only when a signal is present, and accept a clear answer.
- **Leading questions.** Report what the paper says and ask; do not suggest the answer.
- **Supplying the judgement.** Claude can describe what a section does and where something is. Whether it is convincing is the reviewer's call.
- **Agreeing with the notes.** Claude should check each note against the paper, and say when the paper does not support it.
