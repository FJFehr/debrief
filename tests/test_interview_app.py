"""Tests for src/interview_app.py: the record, the conversation bookkeeping and the paper index.

The model is never called here; `ask_model` is replaced by a script of replies.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import interview_app
from src.interview_app import (
    InterviewApp,
    build_user_turn,
    format_for_model,
    is_local,
    parse_register,
    parse_reply,
    question_number,
    render_record,
)

# Dictated text is messy on purpose: the record must not tidy it.
RAW = "um  so the method is, like, hacky?? \"quotes\" & <tags>\n\nsecond paragraph — graph rag"


def claude(**fields):
    return {"role": "claude", "fields": parse_reply(fields)}


POINTS = [
    {"id": "P1", "type": "point", "text": "No stronger baseline", "register": "B6"},
    {"id": "P2", "type": "point", "text": "Weights look hand-set"},
    {"id": "C1", "type": "observation", "text": "Main comparison is not matched"},
    {"id": "S1", "type": "strength", "text": "Clear error analysis"},
]


def question(title="Concerns", **extra):
    return claude(kind="question", message=f"About {title}?", title=title, round=2, sources=["A26"], **extra)


# ---------------------------------------------------------------------------
# Model replies
# ---------------------------------------------------------------------------


def test_parse_reply_keeps_known_fields():
    f = parse_reply(
        {"kind": "question", "message": " Why? ", "round": 4, "title": "T", "sources": ["A3", "x", 7],
         "register": "B7", "follow_up": False, "heard_as": '"graph rag" = GraphRAG', "extra": 1}
    )
    assert f == {"kind": "question", "message": "Why?", "round": 4, "title": "T", "sources": ["A3"],
                 "register": "B7", "heard_as": '"graph rag" = GraphRAG'}


@pytest.mark.parametrize(
    "raw,message",
    [
        ("just text, no structure", "just text, no structure"),
        ('{"kind": "nonsense", "message": "hello"}', "hello"),
        ('["a", "list"]', '["a", "list"]'),
        ({"message": "no kind"}, "no kind"),
        ({"kind": "question"}, ""),
        (None, ""),
    ],
)
def test_parse_reply_degrades_to_a_plain_question(raw, message):
    f = parse_reply(raw)
    assert f["kind"] == "question" and f["message"] == message


def test_parse_reply_items_get_a_known_type():
    f = parse_reply({"kind": "question", "message": "m", "items": [
        {"id": "P1", "text": "weak baselines", "type": "weakness", "register": "B6"},
        {"id": "C1", "text": "no seeds", "type": "observation"},
        {"id": "S1", "text": "clear problem", "type": "strength"}, {"text": "no id"}, "junk"]})
    assert f["items"] == [
        {"id": "P1", "text": "weak baselines", "register": "B6", "type": "point"},
        {"id": "C1", "text": "no seeds", "type": "observation"},
        {"id": "S1", "text": "clear problem", "type": "strength"},
    ]


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------


def test_question_numbers_skip_follow_ups():
    turns = [claude(kind="brief", message="b"), question("One"), question("One again", follow_up=True), question("Two")]
    assert question_number(turns) == 2


def test_answer_carries_decisions_question_number_and_budget():
    turns = [question("One"), {"role": "reviewer", "kind": "answer", "text": "x", "q": 1, "exchange": 1},
             question("Two", items=POINTS)]
    turn = build_user_turn(turns, {"text": RAW, "decisions": {"P1": "weakness", "C1": "accepted", "S1": "strength"}})
    assert turn == {"role": "reviewer", "text": RAW, "kind": "answer", "q": 2, "exchange": 2,
                    "decisions": {"P1": "weakness", "C1": "accepted", "S1": "strength"}}
    assert format_for_model(turn) == (
        f"[Answer to Q2 · exchange 2 of 8]\n(decisions: P1 weakness; C1 accepted; S1 strength)\n{RAW}"
    )


def test_decisions_must_fit_the_item_they_are_for():
    turn = build_user_turn([question(items=POINTS)], {"text": "x", "decisions": {
        "P1": "accepted",   # not a choice for a point
        "C1": "weakness",   # not a choice for an observation
        "P2": "comment", "ZZ": "weakness"}})
    assert turn["decisions"] == {"P2": "comment"}


def test_model_is_told_when_the_budget_is_used_up():
    turns = []
    for n in range(1, 9):
        turns.append(question(f"Q{n}"))
        turns.append(build_user_turn(turns, {"text": "a"}))
    assert format_for_model(turns[-1]).startswith("[Answer to Q8 · exchange 8 of 8] (the budget is used up")
    assert "used up" not in format_for_model(turns[-3])


@pytest.mark.parametrize(
    "asked,payload,expected",
    [
        (claude(kind="brief", message="b"), {"text": ""}, "[Brief] no corrections"),
        (claude(kind="brief", message="b"), {"text": "claim 2 is wrong"}, "[Brief] claim 2 is wrong"),
        (question(), {"action": "skip", "text": "ignored"}, "[Answer to Q1 · exchange 1 of 8] (skipped)"),
        (question(items=POINTS), {"action": "you_decide", "decisions": {"P1": "comment"}},
         "[Answer to Q1 · exchange 1 of 8] (you decide the wording)\n(decisions: P1 comment)"),
        (question(), {"text": "plain"}, "[Answer to Q1 · exchange 1 of 8]\nplain"),
        (claude(kind="summary", message="s"), {"action": "summary_accept", "text": "final"}, "[Summary accepted]\nfinal"),
        (claude(kind="summary", message="s"), {"text": "shorter"}, "[Summary change requested]\nshorter"),
        (question(), {"action": "wrap_up"}, "[Wrap up]"),
    ],
)
def test_messages_sent_to_the_model(asked, payload, expected):
    assert format_for_model(build_user_turn([asked], payload)) == expected


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


def full_conversation():
    turns = [claude(kind="brief", message="Claim map: one claim.")]
    turns.append(build_user_turn(turns, {"text": "the second claim is missing"}))
    turns.append(claude(kind="question", message="Idea, prior work, describe it.", title="The paper", round=1,
                        register="B5", summary_question=True))
    turns.append(build_user_turn(turns, {"text": RAW}))
    turns.append(claude(kind="summary", message="Model paragraph.", heard_as='"graph rag" = GraphRAG'))
    turns.append(build_user_turn(turns, {"action": "summary_accept", "text": "My edited paragraph."}))
    turns.append(question("Your concerns", items=POINTS[:2]))
    turns.append(build_user_turn(turns, {"text": "they should retrieve more", "decisions": {"P1": "weakness"}}))
    turns.append(question("Which claim", follow_up=True))
    turns.append(build_user_turn(turns, {"text": "ok it is a suggestion", "decisions": {}}))
    turns.append(claude(kind="question", message="What the notes missed.", title="Gaps", round=3, items=POINTS[2:3]))
    turns.append(build_user_turn(turns, {"action": "skip"}))
    turns.append(claude(kind="question", message="All points again.", title="Test and deciders", round=6, items=POINTS))
    turns.append(build_user_turn(turns, {"text": "P1 decides it", "decisions": {"P1": "comment", "S1": "strength", "C1": "dropped"}}))
    turns.append(claude(kind="end", message="Done."))
    return turns


def test_record_holds_every_answer_byte_for_byte():
    record = render_record(full_conversation(), "paper.pdf")
    for said in (RAW, "they should retrieve more", "ok it is a suggestion", "P1 decides it", "the second claim is missing"):
        assert said in record
    assert f"Answer: {RAW}\n" in record


def test_record_structure():
    record = render_record(full_conversation(), "paper.pdf")
    assert record.startswith("# Interview record: paper.pdf\n\n## Brief\n\nClaim map: one claim.")
    assert "Corrections from the reviewer: the second claim is missing" in record
    q1 = record[record.index("## Q1 — The paper"):record.index("## Q2")]
    assert "Round: 1 The idea\nSources: none\nQuestion: Idea, prior work, describe it.\nRegister: B5" in q1
    assert 'Heard as: "graph rag" = GraphRAG' in q1  # attached to the answer it corrects
    q2 = record[record.index("## Q2 — Your concerns"):record.index("## Q3")]
    assert "Register: B6\nPoints put to the reviewer:\n- P1 (point): No stronger baseline\n- P2 (point): Weights look hand-set" in q2
    assert "Answer: they should retrieve more\nDecisions: P1 weakness" in q2
    assert "Follow-up: About Which claim?\nAnswer: ok it is a suggestion" in q2
    assert "## Q3 — Gaps" in record and "Answer: (skipped)" in record
    assert "## Summary (approved by the reviewer)\n\nMy edited paragraph." in record
    assert "Model paragraph." not in record  # only what he accepted
    # The closing list carries his latest decision for every point ever put to him.
    assert record.split("## Points as decided by the reviewer\n\n")[1].strip() == (
        "- P1 (comment; put as point): No stronger baseline\n"
        "- P2 (undecided; put as point): Weights look hand-set\n"
        "- C1 (dropped; put as observation): Main comparison is not matched\n"
        "- S1 (strength; put as strength): Clear error analysis"
    )
    assert "Scores" not in record  # scores are set in the review form, not here


def test_split_draft():
    review, notes = interview_app.split_draft("# R\n\n## Paper Summary\n\nA --- dash inside a line.\n\n---\n\n**Open items**\n\n- x\n\n---\n\nmore")
    assert review == "# R\n\n## Paper Summary\n\nA --- dash inside a line."
    assert notes == "**Open items**\n\n- x\n\n---\n\nmore"  # only the first rule separates
    assert interview_app.split_draft("no separator") == ("no separator", "")


def test_register_is_read_from_the_bias_tables():
    register = parse_register(
        "| ID | Bias | Signal | Interview question |\n|---|---|---|---|\n"
        '| B7 | **Novelty dismissed without a reference** (H3). Called a combination of known parts. | "Not novel" | "Which paper already did this?" |\n'
        "| not a row |\n"
    )
    assert register == {"B7": {"title": "Novelty dismissed without a reference", "question": "Which paper already did this?"}}


# ---------------------------------------------------------------------------
# The app, with a scripted model
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path, monkeypatch):
    (tmp_path / "extracted").mkdir()
    a = InterviewApp(Path("foo.pdf"), tmp_path)
    a.extracted_path.write_text("PAPER TEXT", encoding="utf-8")
    script = iter([
        ({"kind": "brief", "message": "Brief."}, "sess-1"),
        ({"kind": "question", "message": "Idea?", "title": "Idea", "round": 1}, "sess-1"),
        ({"kind": "end", "message": "Done."}, "sess-1"),
        ("# Review\n\ntext\n\n---\n\ntrace", "draft-1"),
        ("- all fine", "draft-1"),
    ])
    calls, models = [], []

    def fake(prompt, session_id=None, schema=None, model=None, effort=None):
        calls.append({"prompt": prompt, "session_id": session_id, "schema": schema})
        models.append((model, effort))
        return next(script)

    monkeypatch.setattr(interview_app, "ask_model", fake)
    monkeypatch.setattr(interview_app, "load_interview_prompt", lambda text, venue, path: f"INTERVIEW[{text}]")
    monkeypatch.setattr(interview_app, "load_review_prompt", lambda text, venue, record: f"DRAFT[{record}]")
    a.calls, a.models = calls, models
    return a


def test_full_session_writes_record_draft_and_check(app):
    app.start()
    assert app.calls[0]["prompt"].startswith("INTERVIEW[PAPER TEXT]") and "Running inside the interview app" in app.calls[0]["prompt"]
    assert app.calls[0]["session_id"] is None and app.calls[0]["schema"]
    app.reply({"text": ""})
    app.reply({"text": RAW})
    assert app.calls[2] == {"prompt": f"[Answer to Q1 · exchange 1 of 8]\n{RAW}", "session_id": "sess-1",
                            "schema": interview_app.REPLY_SCHEMA}
    assert app.state["stage"] == "ended"
    assert f"Answer: {RAW}\n" in app.answers_path.read_text(encoding="utf-8")

    app.draft()
    assert app.calls[3]["session_id"] is None and app.calls[3]["schema"] is None
    assert f"Answer: {RAW}" in app.calls[3]["prompt"]  # the draft is written from the record
    assert app.draft_path.read_text(encoding="utf-8") == "# Review\n\ntext\n\n---\n\ntrace\n"
    assert app.review_text_path.read_text(encoding="utf-8") == "# Review\n\ntext\n"  # paste-ready
    assert app.trace_path.read_text(encoding="utf-8") == "trace\n"  # kept, but apart

    app.check()
    assert app.calls[4]["session_id"] == "draft-1"  # continues the drafting conversation
    assert "section 7" in app.calls[4]["prompt"] and "do not suggest any" in app.calls[4]["prompt"]
    assert app.check_path.read_text(encoding="utf-8").strip() == "- all fine"
    assert "scores" not in app.view()["session"] and "score_fields" not in app.view()["paper"]


def test_session_survives_a_restart_of_the_server(app, tmp_path):
    app.start()
    app.reply({"text": "no corrections"})
    again = InterviewApp(Path("foo.pdf"), tmp_path)
    assert again.restore()
    assert again.state["session_id"] == "sess-1" and len(again.state["turns"]) == 3


def test_restore_writes_the_split_files_for_an_existing_draft(app, tmp_path):
    app.start()
    app.state["draft"] = "# Review\n\nbody\n\n---\n\ntrace"
    app.save()
    again = InterviewApp(Path("foo.pdf"), tmp_path)
    again.restore()
    assert again.review_text_path.read_text(encoding="utf-8") == "# Review\n\nbody\n"
    assert again.trace_path.read_text(encoding="utf-8") == "trace\n"


def test_answer_is_on_disk_before_the_model_replies_and_can_be_retried(app, monkeypatch, tmp_path):
    app.start()
    real = interview_app.ask_model

    def boom(*a, **k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(interview_app, "ask_model", boom)
    with pytest.raises(RuntimeError):
        app.reply({"text": RAW})
    # The failed call lost nothing: a new server finds the answer and knows it is unanswered.
    again = InterviewApp(Path("foo.pdf"), tmp_path)
    assert again.restore() and again.pending()
    assert again.state["turns"][-1]["text"] == RAW
    assert again.view()["pending"] is True

    monkeypatch.setattr(interview_app, "ask_model", real)
    again.retry()
    assert not again.pending()
    assert [t["role"] for t in again.state["turns"]] == ["claude", "reviewer", "claude"]  # sent once, not twice
    assert app.calls[-1]["prompt"] == f"[Brief] {RAW}"


def test_each_step_uses_its_own_model(app):
    """Analysis steps (brief, draft, check) go to the strong model; question turns to the fast one."""
    deep = (interview_app.DEEP["model"], interview_app.DEEP["effort"])
    fast = (interview_app.FAST["model"], interview_app.FAST["effort"])
    assert deep != fast
    app.start()
    app.reply({"text": ""})
    app.reply({"text": "an answer"})
    app.draft()
    app.check()
    assert app.models == [deep, fast, fast, deep, deep]


def test_models_can_be_overridden(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(interview_app, "ask_model",
                        lambda *a, **k: (seen.append((a[3], k)), ({"kind": "brief", "message": "b"}, "s"))[1])
    monkeypatch.setattr(interview_app, "load_interview_prompt", lambda *a: "P")
    (tmp_path / "extracted").mkdir()
    a = InterviewApp(Path("foo.pdf"), tmp_path, fast={"model": "m-fast", "effort": None},
                     deep={"model": "m-deep", "effort": "medium"})
    a.extracted_path.write_text("x", encoding="utf-8")
    a.start()
    a.reply({"text": ""})
    assert seen == [("m-deep", {"effort": "medium"}), ("m-fast", {})]


def test_observations_are_off_unless_asked_for(app, tmp_path):
    app.start()
    prompt = app.calls[0]["prompt"]
    assert "switched off for this session" in prompt
    assert interview_app.OBSERVATIONS_PLACEHOLDER not in prompt

    (tmp_path / "on" / "extracted").mkdir(parents=True)
    on = InterviewApp(Path("foo.pdf"), tmp_path / "on", observations=True)
    on.extracted_path.write_text("PAPER TEXT", encoding="utf-8")
    on.start()
    assert "switched on for this session" in app.calls[-1]["prompt"]
    assert "switched off" not in app.calls[-1]["prompt"]


def test_addendum_has_exactly_one_place_for_the_observations_setting():
    text = interview_app.APP_ADDENDUM.read_text(encoding="utf-8")
    assert text.count(interview_app.OBSERVATIONS_PLACEHOLDER) == 1


def test_draft_needs_answers(app):
    app.start()
    with pytest.raises(RuntimeError, match="no answers"):
        app.draft()


def test_saved_interview_refuses_a_pdf_whose_annotations_changed(app, tmp_path):
    """Note IDs follow position, so one added note would shift every ID in the record."""
    app.fingerprint = "as-read"
    app.start()
    again = InterviewApp(Path("foo.pdf"), tmp_path)
    again.fingerprint = "one-note-added"
    with pytest.raises(SystemExit, match="--restart"):
        again.restore()
    assert again.state["turns"] == []
    again.fingerprint = "as-read"
    assert again.restore() and len(again.state["turns"]) == 1


def test_restart_keeps_the_last_interview_as_a_backup(app):
    app.start()
    app.reply({"text": "the second claim is missing"})
    app.restart()
    app.restart()  # a second restart must not replace the backup with an empty record
    backup = app.answers_path.with_name(app.answers_path.name + ".bak")
    assert "the second claim is missing" in backup.read_text(encoding="utf-8")
    assert app.session_path.with_name(app.session_path.name + ".bak").exists()
    assert app.state["turns"] == [] and "the second claim" not in app.answers_path.read_text(encoding="utf-8")


def test_only_the_apps_own_page_may_call_the_server():
    assert is_local("127.0.0.1:8765", None, 8765)
    assert is_local("localhost:8765", "http://localhost:8765", 8765)
    assert not is_local("127.0.0.1:8765", "https://other.example", 8765)  # another site's page
    assert not is_local("other.example:8765", None, 8765)  # another name pointed at this machine
    assert not is_local(None, None, 8765)


def test_model_is_called_without_settings_plugins_or_connectors(monkeypatch):
    seen = {}

    def run(cmd, **kwargs):
        seen["cmd"] = cmd
        return SimpleNamespace(stdout='{"result": "ok", "session_id": "s"}', stderr="", returncode=0)

    monkeypatch.setattr(interview_app.subprocess, "run", run)
    monkeypatch.setattr(interview_app, "MODEL_CWD", Path("."))
    assert interview_app.ask_model("hi") == ("ok", "s")
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "" and cmd[cmd.index("--setting-sources") + 1] == ""
    assert "--strict-mcp-config" in cmd
