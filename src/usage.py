"""Stock-take after a paper: what the reviewer did in the interview, from its usage log.

Usage:
    uv run stocktake --paper reviews/foo.pdf
    uv run stocktake --log outputs/reviews/foo.usage.jsonl

The interview app writes the log (outputs/reviews/foo.usage.jsonl): one line for every
request with what it changed, and one for each thing done on the page that sends no
request, such as opening a point or unfolding a part. This prints a summary of it:
where the time went, what was changed by hand or by voice, what was refused, and which
parts of the page were used. The log quotes the reviewer and the paper, so it stays local.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

IDLE_S = 300  # a longer gap than this is a break, not time spent on a step
STEPS = ("new", "brief", "summary", "strengths", "weaknesses", "comments", "bias", "draft", "final")
ASKED = {"/api/reply", "/api/retry", "/api/start", "/api/check"}  # requests that wait for the model


def load(path: Path) -> list[dict]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return lines


def clip(text: object, limit: int = 110) -> str:
    text = " ".join(str(text if text is not None else "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def counted(counter: Counter) -> str:
    return ", ".join(f"{key} ×{n}" for key, n in counter.most_common()) or "none"


def summarise(lines: list[dict], name: str) -> str:
    """The stock-take as Markdown."""
    requests = [x for x in lines if x.get("event") == "request"]
    page = [x for x in lines if x.get("event") == "page"]
    out = [f"# Stock-take: {name}"]
    if not lines:
        return out[0] + "\n\nThe usage log is empty.\n"

    # Time: the gap after each line goes to the step the interview stood at, breaks left out.
    spent: Counter = Counter()
    times = [datetime.fromisoformat(x["t"]) for x in lines]
    for line, start, end in zip(lines, times, times[1:]):
        gap = (end - start).total_seconds()
        if 0 < gap <= IDLE_S:
            spent[line.get("stage") or "new"] += gap
    waited: Counter = Counter()
    rows: dict[str, Counter] = {step: Counter() for step in STEPS}
    for r in requests:
        before = (r.get("moved") or [f"{r.get('stage')}/"])[0].split("/")[0]  # the step it was sent from
        row = rows.setdefault(before, Counter())
        body = r.get("body") or {}
        if r["path"] in ASKED:
            waited[before] += r.get("ms", 0) / 1000
        if r.get("status") != 200:
            row["refused"] += 1
        elif r["path"] == "/api/reply" and body.get("action") in ("change", "apply"):
            row["spoken changes"] += 1  # a plan that was agreed is a change; the plan itself is not
        elif r["path"] == "/api/reply" and not body.get("action"):
            row["answers"] += 1
        elif r["path"] in ("/api/entry", "/api/summary", "/api/finding"):
            row["hand edits"] += 1
    out.append(
        f"{len(requests)} requests and {len(page)} page actions, "
        f"{times[0]:%Y-%m-%d %H:%M} to {times[-1]:%Y-%m-%d %H:%M}. "
        f"Active time {sum(spent.values()) / 60:.0f} min, of which {sum(waited.values()) / 60:.0f} min waiting for the model."
    )
    table = ["| Step | Minutes | Waiting for the model | Answers | Spoken changes | Hand edits | Refused |", "|---|---|---|---|---|---|---|"]
    for step in STEPS:
        row = rows[step]
        if spent[step] or row:
            table.append(
                f"| {step} | {spent[step] / 60:.1f} | {waited[step] / 60:.1f} | {row['answers']} | "
                f"{row['spoken changes']} | {row['hand edits']} | {row['refused']} |"
            )
    out.append("## Where the time went\n\n" + "\n".join(table))

    spoken = [f"- [{(r.get('moved') or [r.get('stage')])[0].split('/')[0]}] {clip(r['body'].get('text'))}"
              for r in requests if r.get("status") == 200 and (r.get("body") or {}).get("action") == "change"]
    out.append("## Changes asked for by voice or typing\n\n" + ("\n".join(spoken) or "None."))

    hand, parts = [], Counter()
    for r in requests:
        if r.get("status") != 200 or r["path"] not in ("/api/entry", "/api/summary", "/api/finding"):
            continue
        if "summary" in r:
            parts["summary"] += 1
            hand.append(f"- Summary: {clip(r['summary'][0], 60)} → {clip(r['summary'][1], 60)}")
        for edit in r.get("entries", []):
            changed = edit.get("set", {})
            if "kind" in changed:  # moved to another kind: its new ID and its former one say the same
                parts["moved"] += 1
                hand.append(f"- {edit['id']} moved: {changed['kind'][0]} → {changed['kind'][1]}")
            for part, (old, new) in changed.items():
                if part in ("by_hand", "kind", "id", "was") or (not old and not new):
                    continue
                parts[part] += 1
                hand.append(f"- {edit['id']} {part}: {clip(old, 60)} → {clip(new, 60)}")
        if "order" in r:
            parts["order"] += 1
            hand.append(f"- Order: {', '.join(r['order'])}")
    out.append(f"## Changes made by hand\n\nBy part: {counted(parts)}.\n\n" + ("\n".join(hand) or "None."))

    refused = [f"- [{r.get('stage')}] {r['path']}: {clip(r.get('error'))}" for r in requests if r.get("status") != 200]
    out.append("## Refused or failed\n\n" + ("\n".join(refused) or "None."))

    def data(x: dict) -> dict:
        return x.get("data") or {}

    opened = Counter(data(x)["entry"] for x in page if x.get("what") == "view" and data(x).get("entry"))
    steps = Counter(data(x)["step"] for x in page if x.get("what") == "view" and data(x).get("step"))
    unfolded = Counter(data(x).get("key", "?").split("-")[0] for x in page if x.get("what") == "fold" and data(x).get("open"))
    links = Counter(data(x).get("to", "?") for x in page if x.get("what") == "link")
    dictated = Counter(data(x).get("into", "?") for x in page if x.get("what") == "dictate" and data(x).get("on"))
    rail = Counter("hidden" if data(x).get("hidden") else "shown" for x in page if x.get("what") == "rail")
    discards = Counter("discarded" if data(x).get("discarded") else "kept" for x in page if x.get("what") == "discard")

    # Talk, plans and what the paper says otherwise: the parts added after the third round of use.
    def sent(action: str) -> Counter:
        return Counter((r.get("moved") or [r.get("stage") or "?"])[0].split("/")[0] for r in requests
                       if r["path"] == "/api/reply" and r.get("status") == 200 and (r.get("body") or {}).get("action") == action)

    raised = settled = 0
    for r in requests:
        for edit in r.get("entries", []):
            changed = edit.get("set", {})
            raised += bool((edit.get("new") or {}).get("counter")) + bool(changed.get("counter", [None, None])[1])
            settled += changed.get("counter_settled", [None, None])[1] is True
    saved = [x.get("unchanged") for x in lines if x.get("event") == "saved"]
    kept = any(r["path"] == "/api/final" and r.get("status") == 200 for r in requests)  # a log from before this was recorded
    final = ("the draft unchanged" if saved[-1] else "differs from the draft") if saved else "saved" if kept else "not saved"
    waits = [x.get("ms", 0) / 1000 for x in lines if x.get("event") == "check"]
    out.append("## Talk, plans and facts\n\n" + "\n".join([
        f"- Free talk filed, by step: {counted(sent('talk'))}",
        f"- Plans asked for, by step: {counted(sent('plan'))}",
        f"- Plans written out, by step: {counted(sent('apply'))}",
        f"- Facts from the paper put on a point: {raised}, settled by the reviewer: {settled}",
        f"- The check beside the page: {', '.join(f'{w:.0f} s' for w in waits) or 'not run'}",
        f"- The review saved as submitted: {final}",
    ]))
    findings = Counter((r.get("body") or {}).get("action", "?") for r in requests
                       if r["path"] == "/api/finding" and r.get("status") == 200)
    out.append("## What was used on the page\n\n" + "\n".join([
        f"- Points opened: {counted(opened)}",
        f"- Steps opened: {counted(steps)}",
        f"- Folded parts opened: {counted(unfolded)}",
        f"- Links followed into the paper: {counted(links)}",
        f"- Dictation started, by text box: {counted(dictated)}",
        f"- Left bar: {counted(rail)}",
        f"- Unsaved changes when leaving a point: {counted(discards)}",
        f"- Findings of the check: {counted(findings)}",
        f"- Copy buttons: {counted(Counter(data(x).get('what', '?') for x in page if x.get('what') == 'copy'))}",
    ]))
    return "\n\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock-take of one interview, from its usage log.")
    parser.add_argument("--paper", help="The annotated PDF the interview was about (e.g., reviews/foo.pdf)")
    parser.add_argument("--log", help="Path to a usage log, in place of --paper")
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()
    if not args.paper and not args.log:
        parser.error("give --paper or --log")
    path = Path(args.log) if args.log else Path(args.output_dir) / "reviews" / f"{Path(args.paper).stem}.usage.jsonl"
    if not path.exists():
        sys.exit(f"Error: no usage log at {path}. It is written while the interview runs.")
    print(summarise(load(path), path.name.removesuffix(".usage.jsonl")), end="")


if __name__ == "__main__":
    main()
