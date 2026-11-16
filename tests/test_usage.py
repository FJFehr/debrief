"""Tests for src/usage.py: the stock-take printed from an interview's usage log."""

import json

from src.usage import load, summarise

LOG = [
    {"t": "2026-01-01T10:00:00.000", "event": "request", "stage": "summary", "phase": "ask", "path": "/api/reply",
     "body": {"text": ""}, "status": 200, "ms": 60000, "moved": ["brief/None", "summary/ask"]},
    {"t": "2026-01-01T10:02:00.000", "event": "request", "stage": "summary", "phase": "outline", "path": "/api/reply",
     "body": {"text": "it is about retrieval"}, "status": 200, "ms": 30000, "moved": ["summary/ask", "summary/outline"]},
    {"t": "2026-01-01T10:03:00.000", "event": "request", "stage": "summary", "phase": "outline", "path": "/api/reply",
     "body": {"action": "change", "text": "drop  the third\nsentence"}, "status": 200, "ms": 30000, "summary": ["Old.", "New."]},
    # A long gap is a break, not time spent on the step.
    {"t": "2026-01-01T11:30:00.000", "event": "page", "stage": "weaknesses", "phase": "outline", "what": "view",
     "at": "2026-01-01T10:30:00Z", "data": {"entry": "W1"}},
    {"t": "2026-01-01T11:31:00.000", "event": "request", "stage": "weaknesses", "phase": "outline", "path": "/api/entry",
     "body": {"id": "W1", "set": {"text": "Mine."}}, "status": 200, "ms": 3,
     "entries": [{"id": "W1", "set": {"by_hand": [None, True], "text": [None, "Mine."]}}]},
    {"t": "2026-01-01T11:31:30.000", "event": "request", "stage": "weaknesses", "phase": "outline", "path": "/api/entry",
     "body": {"id": "W2", "move": "comment", "dropped": False}, "status": 200, "ms": 2,
     "entries": [{"id": "C1", "set": {"id": ["W2", "C1"], "kind": ["weakness", "comment"], "was": [None, ["W2"]],
                                      "dropped": [None, False]}}]},
    {"t": "2026-01-01T11:32:00.000", "event": "request", "stage": "weaknesses", "phase": "outline", "path": "/api/reply",
     "body": {"action": "accept"}, "status": 400, "ms": 1, "error": "O1 is still an observation."},
    {"t": "2026-01-01T11:32:10.000", "event": "page", "stage": "weaknesses", "phase": "outline", "what": "fold",
     "at": "2026-01-01T10:32:10Z", "data": {"key": "parts-W1", "open": True}},
    {"t": "2026-01-01T11:32:20.000", "event": "page", "stage": "weaknesses", "phase": "outline", "what": "dictate",
     "at": "2026-01-01T10:32:20Z", "data": {"on": True, "into": "#entryText"}},
]


def test_stock_take_says_where_the_time_went_and_what_was_changed(tmp_path):
    path = tmp_path / "foo.usage.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in LOG) + "\nnot json\n", encoding="utf-8")
    text = summarise(load(path), "foo")
    assert text.startswith("# Stock-take: foo\n\n6 requests and 3 page actions, 2026-01-01 10:00 to 2026-01-01 11:32.")
    assert "Active time 5 min, of which 2 min waiting for the model." in text  # the break is left out
    # Step, minutes, waiting, answers, spoken changes, hand edits, refused.
    assert "| brief | 0.0 | 1.0 | 1 | 0 | 0 | 0 |" in text
    assert "| summary | 3.0 | 1.0 | 1 | 1 | 0 | 0 |" in text
    assert "| weaknesses | 2.3 | 0.0 | 0 | 0 | 2 | 1 |" in text
    assert "- [summary] drop the third sentence" in text
    assert "By part: text ×1, moved ×1." in text
    assert "- W1 text:  → Mine." in text and "- C1 moved: weakness → comment" in text
    assert "by_hand" not in text and "dropped" not in text and "C1 was" not in text
    assert "- [weaknesses] /api/reply: O1 is still an observation." in text
    assert "- Points opened: W1 ×1" in text and "- Folded parts opened: parts ×1" in text
    assert "- Dictation started, by text box: #entryText ×1" in text


def test_stock_take_of_an_empty_log():
    assert summarise([], "foo") == "# Stock-take: foo\n\nThe usage log is empty.\n"


def test_stock_take_counts_talk_plans_facts_and_the_saved_review():
    def reply(t, stage, action, **extra):
        return {"t": f"2026-01-01T10:0{t}:00.000", "event": "request", "stage": stage, "phase": "outline",
                "path": "/api/reply", "body": {"action": action, "text": "x"}, "status": 200, "ms": 1000, **extra}

    text = summarise([
        reply(0, "brief", "talk"), reply(1, "brief", "talk"), reply(2, "summary", "plan"),
        reply(3, "summary", "apply"),
        reply(4, "comments", "change", entries=[{"id": "C1", "set": {"counter": [None, "Section 4 reports it."]}}]),
        {"t": "2026-01-01T10:05:00.000", "event": "request", "stage": "comments", "phase": "outline", "path": "/api/entry",
         "body": {"id": "C1", "counter": "settled"}, "status": 200, "ms": 2,
         "entries": [{"id": "C1", "set": {"counter_settled": [None, True]}}]},
        {"t": "2026-01-01T10:06:00.000", "event": "check", "stage": "draft", "phase": None, "ms": 61000},
        {"t": "2026-01-01T10:07:00.000", "event": "saved", "stage": "final", "phase": None, "unchanged": True},
    ], "foo")
    assert "- Free talk filed, by step: brief ×2" in text
    assert "- Plans asked for, by step: summary ×1" in text and "- Plans written out, by step: summary ×1" in text
    assert "| summary | 2.0 | 0.0 | 0 | 1 | 0 | 0 |" in text  # the plan agreed counts as the change; asking for it does not
    assert "- Facts from the paper put on a point: 1, settled by the reviewer: 1" in text
    assert "- The check beside the page: 61 s" in text and "- The review saved as submitted: the draft unchanged" in text
