# ARR review format

Read [REVIEWING_GUIDELINES.md](../REVIEWING_GUIDELINES.md) first. This file only covers what is specific to ACL Rolling Review. Official guidance: <https://aclrollingreview.org/reviewerguidelines>.

## Form fields

| Field | Who | Notes |
|---|---|---|
| Paper Summary | Claude drafts | As in the general guidelines. |
| Summary Of Strengths | Claude drafts | |
| Summary Of Weaknesses | Claude drafts | Only points that affect the claims or the contribution. |
| Comments Suggestions And Typos | Claude drafts | Questions, minor issues, optional experiments, typos. |
| Confidence | The reviewer | 1–5 |
| Soundness | The reviewer | 1–5, half points allowed |
| Excitement | The reviewer | 1–5, half points allowed |
| Overall Assessment | The reviewer | 1–5, half points allowed |
| Reproducibility, Datasets, Software | The reviewer | 1–5 each |
| Ethics, author identity, prior knowledge of the paper, certification | The reviewer | |
| Publication Ethics Policy Compliance | The reviewer | Declares any AI tool use. |

## ARR-specific rules

- **Soundness and Excitement are separate.** Soundness is whether the claims are supported. Excitement is personal interest and does not need justifying. "When would I use this" and "what is the takeaway" belong to Excitement.
- **A low Soundness score must be justified by a named fault in the review text.**
- **Overall Assessment** is a recommendation for an \*ACL venue. A sound, reproducible paper can merit acceptance even if it does not excite me.
- **Missing references** are a weakness only if the work was published at least three months before the submission deadline. Preprints go in Comments.
- **Extra experiments** beyond what the paper's claims need go in Comments.
- **Language errors** are not a weakness if the paper is clear enough to assess.
- **Resubmissions:** do not raise new issues unless the revision introduced them.
- ARR's list of reviewer shortcuts (H1–H17) is covered by section 6 of the general guidelines.

## Template

```markdown
# Review: <paper ID> <short title>

## Paper Summary

<one paragraph>

## Summary Of Strengths

* **<claim>.** <what the paper does, where, and why it matters>

## Summary Of Weaknesses

* **<claim>.** <what is missing, with location>. <which claim this undermines>. <what would resolve it, as a first-person sentence>.

## Comments Suggestions And Typos

* <one line for each question, suggestion, minor issue or typo, as one list>
```
