"""Tests for src/interview_app.py: the sections, the index of entries, the record and the draft.

The model is never called here; `ask_model` is replaced by a script of replies.
"""

import json
import threading
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from src import interview_app
from src import review as review_module
from src.interview_app import (
    InterviewApp,
    bullet,
    find_entry,
    gaps,
    index_text,
    is_local,
    model_message,
    move_entry,
    next_id,
    parse_register,
    parse_reply,
    wording,
)

# Dictated text is messy on purpose: the record must not tidy it.
RAW = "um  so the method is, like, hacky?? \"quotes\" & <tags>\n\nsecond paragraph — graph rag"

UNRANKED = "The reviewer has not ordered the weaknesses by severity."


def ask(*asks, **extra):
    return {"kind": "question", "message": "", "asks": list(asks), **extra}


def outline(**extra):
    return {"kind": "outline", "message": "", **extra}


def weakness(entry_id, claim, **parts):
    return {"id": entry_id, "kind": "weakness", "claim": claim, **parts}


S1 = {"id": "S1", "claim": "Lower cost at similar accuracy", "sources": ["A3"]}
S1_OUTLINED = {**S1, "body": "The method halves the number of calls.", "where": "Table 2", "said": "the cost one"}
W_PINNED = weakness("W1", "Single runs", body="Each setting is run once.", where="Table 2",
                    undermines="This weakens the cost claim.", resolve="I would like to see three seeds.")


# ---------------------------------------------------------------------------
# Model replies
# ---------------------------------------------------------------------------


def test_parse_reply_keeps_known_fields():
    f = parse_reply(
        {"kind": "outline", "message": " Filed. ", "sources": ["A3", "x", 7], "order": [" w2 ", "W1", 3],
         "follow_up": False, "heard_as": '"graph rag" = GraphRAG', "round": 4, "title": "T", "items": [1]}
    )
    assert f == {"kind": "outline", "message": "Filed.", "order": ["W2", "W1"], "sources": ["A3"],
                 "heard_as": '"graph rag" = GraphRAG'}
    assert parse_reply({"kind": "question", "message": "m", "follow_up": True, "asks": [], "entries": []}) == {
        "kind": "question", "message": "m", "follow_up": True}  # lists only when they hold something


@pytest.mark.parametrize(
    "raw,message",
    [
        ("just text, no structure", "just text, no structure"),
        ('{"kind": "nonsense", "message": "hello"}', "hello"),
        ('["a", "list"]', '["a", "list"]'),
        ({"message": "no kind"}, "no kind"),
        ({"kind": "end", "message": "an old kind"}, "an old kind"),
        ({"kind": "question"}, ""),
        (None, ""),
    ],
)
def test_parse_reply_degrades_to_a_plain_question(raw, message):
    f = parse_reply(raw)
    assert f == {"kind": "question", "message": message}


def test_parse_reply_keeps_what_is_asked_apart_from_its_material():
    f = parse_reply({"kind": "question", "message": "", "asks": [
        {"id": " W1 ", "question": " Which claim? ", "notes": "A26", "paper": "", "guide": 3, "register": "B6", "other": "x"},
        {"question": "  "}, {"notes": "no question"}, "junk"]})
    assert f["asks"] == [{"question": "Which claim?", "id": "W1", "notes": "A26", "register": "B6"}]


def test_parse_reply_normalises_sentences_entries_and_plan():
    f = parse_reply({"kind": "outline", "message": "", "sentences": [{"text": " It studies X. ", "job": "studies"}, {"job": "method"}],
                     "plan": [{"target": "W2", "action": "rewrite", "because": "make it shorter"}, {"action": "cut"}],
                     "entries": [
                         {"id": " w2 ", "claim": " Single runs ", "body": "", "where": 5, "sources": ["A12", "Table 2"],
                          "drop": True, "move": "comment", "kind": "strength"},
                         {"id": "S1", "move": "observation", "drop": "yes"},  # neither is a move or a drop
                         {"claim": "No ID given"}, {"id": ""}, "junk"]})
    assert f["sentences"] == [{"text": "It studies X.", "job": "studies"}]
    assert f["plan"] == [{"target": "W2", "action": "rewrite", "because": "make it shorter"}]
    assert f["entries"] == [
        {"id": "W2", "claim": "Single runs", "sources": ["A12"], "drop": True, "move": "comment"},
        {"id": "S1"},
        {"id": "", "claim": "No ID given"},
    ]


def test_reply_schema_asks_for_the_plan_before_the_text_it_governs():
    fields = list(interview_app.REPLY_SCHEMA["properties"])
    assert fields.index("plan") < fields.index("sentences") < fields.index("entries")
    assert interview_app.REPLY_SCHEMA["required"] == ["kind", "message"]


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"kind": "strength", "claim": "Lower cost at similar accuracy", "body": "The method halves the calls.", "where": "Table 2"},
         "**Lower cost at similar accuracy.** The method halves the calls (Table 2)."),
        (W_PINNED,
         "**Single runs.** Each setting is run once (Table 2). This weakens the cost claim. I would like to see three seeds."),
        # No doubled full stops, a question keeps its mark, and what is empty leaves no punctuation behind.
        (weakness("W2", "Why only one run?", body="No variance is reported", resolve="Report seeds"),
         "**Why only one run?** No variance is reported. Report seeds."),
        (weakness("W3", "Ends with a stop.", where="Section 4"), "**Ends with a stop.** (Section 4)."),
        ({"kind": "strength", "claim": "Only a claim"}, "**Only a claim.**"),
        # A strength shows no fix, even if it was a weakness before.
        ({"kind": "strength", "claim": "Clear", "body": "It is clear.", "resolve": "nothing", "undermines": "nothing"},
         "**Clear.** It is clear."),
        ({"kind": "comment", "claim": "Figure 2", "body": "Figure 2 is hard to read."}, "Figure 2 is hard to read."),
        ({"kind": "comment", "claim": "Typo in line 12"}, "Typo in line 12"),
        ({"kind": "comment", "id": "C2", "was": ["O1", "W3"], "body": "Budgets differ."}, "[Claude] Budgets differ."),
        ({"kind": "observation", "id": "O1", "claim": "Costs are not matched", "body": "Budgets differ.", "where": "Table 3"},
         "[Claude] **Costs are not matched.** Budgets differ (Table 3)."),
    ],
)
def test_bullet(entry, expected):
    assert bullet({"id": "X1", **entry}) == expected
    assert "To resolve" not in bullet({"id": "X1", **entry})  # the reviewer took that label out


def test_gaps_are_a_missing_location_or_fix():
    assert gaps(weakness("W1", "a")) == ["where", "resolve"]
    assert gaps(weakness("W1", "a", where=" ", resolve="Report seeds.")) == ["where"]
    assert gaps(weakness("W1", "a", nowhere=True)) == ["resolve"]  # marked as having no single location
    assert gaps(W_PINNED) == []
    assert gaps({"id": "S1", "kind": "strength"}) == ["where"]
    assert gaps({"id": "C1", "kind": "comment"}) == [] and gaps({"id": "O1", "kind": "observation"}) == []
    assert gaps(weakness("W1", "a", dropped=True)) == []


def test_a_moved_entry_gets_a_new_id_and_its_old_one_back_on_return():
    entries = [weakness("W1", "a"), weakness("W4", "b"), {"id": "C1", "kind": "comment", "was": ["W2"]}]
    moved = entries[1]
    move_entry(entries, moved, "comment")
    assert (moved["id"], moved["kind"], moved["was"]) == ("C2", "comment", ["W4"])
    assert find_entry(entries, "W4") is moved and find_entry(entries, "C2") is moved  # the old ID still finds it
    move_entry(entries, moved, "strength")
    assert (moved["id"], moved["was"]) == ("S1", ["W4", "C2"])
    move_entry(entries, moved, "weakness")
    assert (moved["id"], moved["was"]) == ("W4", ["C2", "S1"])
    move_entry(entries, moved, "weakness")  # already there
    assert moved["id"] == "W4"
    # Former IDs count as used: W2 and C2 are never given to another entry.
    assert next_id(entries, "weakness") == "W5" and next_id(entries, "comment") == "C3"
    assert next_id(entries, "observation") == "O1"
    assert find_entry(entries, "W9") is None


# ---------------------------------------------------------------------------
# What the model is sent
# ---------------------------------------------------------------------------


def test_index_as_the_model_sees_it():
    entries = [
        weakness("W2", "Single runs without significance testing", body="Each setting is run once.",
                 resolve="I would like to see three seeds.", by_hand=True, sources=["A12"], said="only once"),
        {"id": "S3", "kind": "strength", "claim": "Dropped strength", "dropped": True},
        {"id": "C1", "kind": "comment", "group": "minor", "was": ["W4"], "claim": "Figure 2 is hard to read"},
        {"id": "S1", "kind": "strength", "claim": "Lower cost at similar accuracy", "body": "Half the calls.", "where": "Table 2"},
        weakness("W5", "Dropped weakness", dropped=True),
        weakness("W6", "No single place", nowhere=True),
        {"id": "O1", "kind": "observation", "claim": "Costs are not matched"},
    ]
    assert index_text(entries, ranked=False) == (
        "[Index]\n"
        "S1 (strength): Lower cost at similar accuracy\n"
        "  body: Half the calls.\n"
        "  where: Table 2\n"
        "W2 (weakness; reviewer's wording): Single runs without significance testing\n"
        "  body: Each setting is run once.\n"
        "  resolve: I would like to see three seeds.\n"
        "W6 (weakness): No single place\n"
        "  where: no single location\n"
        "C1 (comment; was W4): Figure 2 is hard to read\n"
        "O1 (observation): Costs are not matched\n"
        "Dropped: S3, W5\n"
        "The reviewer has not ordered the weaknesses by severity."
    )
    assert index_text(entries, ranked=True).endswith(
        "\nThe reviewer has ordered the weaknesses by severity, most severe first.")
    assert index_text([], ranked=False) == "[Index]\n(empty)"


@pytest.mark.parametrize(
    "kind,section,text,stage,head,step",
    [
        ("brief", "brief", "", "summary", "[Brief] no corrections", "ask · summary"),
        ("brief", "brief", "claim 2 is wrong", "summary", "[Brief] claim 2 is wrong", "ask · summary"),
        ("answer", "weaknesses", RAW, "weaknesses", f"[Answer · weaknesses]\n{RAW}", "outline · weaknesses"),
        # No words: the wording is left to the model.
        ("answer", "comments", " ", "comments", "[Answer · comments]", "outline · comments"),
        ("skip", "comments", "not sent on", "bias", "[Skipped · comments]", "ask · bias"),
        ("accept", "summary", "as sent", "strengths", "[Accepted · summary]\nThe paragraph as it stands.", "ask · strengths"),
        ("accept", "strengths", "", "weaknesses", "[Accepted · strengths]", "ask · weaknesses"),
        ("change", "weaknesses", "W2 shorter", "weaknesses", "[Change requested · weaknesses]\nW2 shorter", "revise · weaknesses"),
        # After the interview a change is about the review as a whole.
        ("change", "draft", "drop S2", "draft", "[Change requested · review]\ndrop S2", "revise · review"),
        ("change", "final", "drop S2", "final", "[Change requested · review]\ndrop S2", "revise · review"),
    ],
)
def test_messages_sent_to_the_model(kind, section, text, stage, head, step):
    """A label with the reviewer's words, then the index, then the step wanted next."""
    turn = {"role": "reviewer", "section": section, "kind": kind, "text": text}
    state = {"stage": stage, "summary": "The paragraph as it stands.", "entries": [], "ranked": False}
    assert model_message(turn, state) == f"{head}\n\n[Index]\n(empty)\n\n[Next: {step}]"


def test_register_is_read_from_the_bias_tables():
    register = parse_register(
        "| ID | Bias | Signal | Interview question |\n|---|---|---|---|\n"
        '| B7 | **Novelty dismissed without a reference** (H3). Called a combination of known parts. | "Not novel" | "Which paper already did this?" |\n'
        "| not a row |\n"
    )
    assert register == {"B7": {"title": "Novelty dismissed without a reference", "how": "(H3). Called a combination of known parts.",
                               "signal": '"Not novel"', "question": "Which paper already did this?", "sources": []}}


def test_register_entries_carry_their_sources():
    register = parse_register(
        "| ID | Bias | Signal | Interview question | Source |\n|---|---|---|---|---|\n"
        '| B6 | **Extra experiments.** Asked often. | A request. | "Which claim?" | [ARR reviewer guidelines, H13](https://example.org/g#issues); Past reviews |\n'
        '| B13 | **Statistics by reflex.** | Seeds. | "How large?" | |\n'
    )
    assert register["B6"]["sources"] == [
        {"label": "ARR reviewer guidelines, H13", "url": "https://example.org/g#issues"}, {"label": "Past reviews"}]
    assert register["B13"]["sources"] == [] and register["B13"]["how"] == ""


# ---------------------------------------------------------------------------
# The app, with a scripted model
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path, monkeypatch):
    """An app whose model answers from `app.script`. What it was sent is in `app.calls`."""
    (tmp_path / "extracted").mkdir()
    a = InterviewApp(Path("foo.pdf"), tmp_path)
    a.extracted_path.write_text("PAPER TEXT", encoding="utf-8")
    a.script, a.calls, a.models = [], [], []

    def fake(prompt, session_id=None, schema=None, model=None, effort=None):
        a.calls.append({"prompt": prompt, "session_id": session_id, "schema": schema})
        a.models.append((model, effort))
        return a.script.pop(0), "sess-1"

    monkeypatch.setattr(interview_app, "ask_model", fake)
    monkeypatch.setattr(interview_app, "load_interview_prompt", lambda text, venue, path: f"INTERVIEW[{text}]")
    # The saved review is copied to reviewing/my_reviews/: keep that out of the real folder.
    monkeypatch.setattr(review_module, "REVIEWING_DIR", tmp_path / "reviewing")
    return a


def at(app, stage, phase, entries=(), **state):
    """Put the interview at a stage without playing the turns before it."""
    app.state.update(stage=stage, phase=phase, entries=[dict(e) for e in entries], session_id="sess-1", **state)


def where(app):
    return app.state["stage"], app.state["phase"]


def ids(app):
    return [e["id"] for e in app.state["entries"]]


def play_to_weaknesses(app):
    """Brief, summary and strengths, with one change to the summary and one follow-up.

    Returns where the interview stood after each step.
    """
    app.script += [
        {"kind": "brief", "message": "Claim map: one claim."},
        ask({"question": "What is the idea, in one sentence?", "guide": "One sentence."}),
        outline(heard_as='"graph rag" = GraphRAG',
                sentences=[{"text": "The paper studies cheap retrieval.", "job": "studies"},
                           {"text": "Results are very strong.", "job": "evaluation"}]),
        outline(plan=[{"target": "2", "action": "cut", "because": "drop 2"}],
                sentences=[{"text": "The paper studies cheap retrieval.", "job": "studies"}]),
        ask({"id": "S1", "question": "Is the lower cost a strength?", "notes": 'A3: "cheap!"',
             "paper": "Table 2 reports half the calls."}, entries=[S1]),
        ask({"id": "S1", "question": "Where does it show?"}, follow_up=True),
        outline(entries=[S1_OUTLINED]),
        ask({"id": "W1", "question": "Which claim does the single run undermine?"},
            entries=[{"id": "W1", "claim": "Single runs"}, {"id": "W2", "claim": "No stronger baseline"}]),
    ]
    app.start()
    stood = [where(app)]
    for payload in (
        {"text": "claim 2 is missing"},
        {"text": RAW},
        {"action": "change", "text": "drop 2"},
        {"action": "accept", "text": "The paper studies cheap retrieval,  my way."},
        {"text": ""},
        {"text": "the cost one"},
        {"action": "accept"},
    ):
        app.reply(payload)
        stood.append(where(app))
    return stood


def test_the_interview_follows_the_review_form(app):
    assert where(app) == ("new", None)
    assert play_to_weaknesses(app) == [
        ("brief", None),
        ("summary", "ask"),
        ("summary", "outline"),
        ("summary", "outline"),  # a revision is looked at again
        ("strengths", "ask"),
        ("strengths", "ask"),  # a follow-up question leaves the answer owed
        ("strengths", "outline"),
        ("weaknesses", "ask"),
    ]
    first = app.calls[0]
    assert first["prompt"].startswith("INTERVIEW[PAPER TEXT]") and "Running inside the interview app" in first["prompt"]
    assert first["session_id"] is None and first["schema"] == interview_app.REPLY_SCHEMA
    assert all(c["session_id"] == "sess-1" and c["schema"] == interview_app.REPLY_SCHEMA for c in app.calls[1:])

    listed = f"[Index]\nS1 (strength): Lower cost at similar accuracy\n{UNRANKED}"
    outlined = ("[Index]\nS1 (strength): Lower cost at similar accuracy\n"
                f"  body: The method halves the number of calls.\n  where: Table 2\n{UNRANKED}")
    assert [c["prompt"] for c in app.calls[1:]] == [
        "[Brief] claim 2 is missing\n\n[Index]\n(empty)\n\n[Next: ask · summary]",
        f"[Answer · summary]\n{RAW}\n\n[Index]\n(empty)\n\n[Next: outline · summary]",
        "[Change requested · summary]\ndrop 2\n\n[Summary as it stands]\n"
        "The paper studies cheap retrieval. Results are very strong.\n\n[Index]\n(empty)\n\n[Next: revise · summary]",
        # The summary goes back as the reviewer left it, typed by hand.
        "[Accepted · summary]\nThe paper studies cheap retrieval,  my way.\n\n[Index]\n(empty)\n\n[Next: ask · strengths]",
        f"[Answer · strengths]\n\n{listed}\n\n[Next: outline · strengths]",
        f"[Answer · strengths]\nthe cost one\n\n{listed}\n\n[Next: outline · strengths]",
        f"[Accepted · strengths]\n\n{outlined}\n\n[Next: ask · weaknesses]",
    ]
    assert app.state["summary"] == "The paper studies cheap retrieval,  my way."
    assert [(t["role"], t["section"], t.get("kind") or t["fields"]["kind"]) for t in app.state["turns"]] == [
        ("claude", "brief", "brief"), ("reviewer", "brief", "brief"),
        ("claude", "summary", "question"), ("reviewer", "summary", "answer"),
        ("claude", "summary", "outline"), ("reviewer", "summary", "change"),
        ("claude", "summary", "outline"), ("reviewer", "summary", "accept"),
        ("claude", "strengths", "question"), ("reviewer", "strengths", "answer"),
        ("claude", "strengths", "question"), ("reviewer", "strengths", "answer"),
        ("claude", "strengths", "outline"), ("reviewer", "strengths", "accept"),
        ("claude", "weaknesses", "question"),
    ]
    assert app.state["turns"][3] == {"role": "reviewer", "section": "summary", "kind": "answer", "text": RAW}
    assert app.state["entries"] == [
        {"id": "S1", "kind": "strength", **{k: v for k, v in S1_OUTLINED.items() if k != "id"}},
        {"id": "W1", "kind": "weakness", "claim": "Single runs"},  # candidates are in the index as soon as they are put
        {"id": "W2", "kind": "weakness", "claim": "No stronger baseline"},
    ]


def test_the_summary_follows_the_models_sentences_until_it_is_accepted(app):
    at(app, "summary", "ask")
    app.script += [outline(sentences=[{"text": "The paper studies cheap retrieval."}, {"text": "Results are very strong."}]),
                   ask({"question": "Strengths?"}), outline(sentences=[{"text": "Something else."}])]
    app.reply({"text": "it is about retrieval"})
    assert app.state["summary"] == "The paper studies cheap retrieval. Results are very strong."
    app.reply({"action": "accept"})  # no text of the reviewer's own: the paragraph stands as proposed
    assert app.state["summary"] == "The paper studies cheap retrieval. Results are very strong."
    app.reply({"text": "x"})  # sentences in a later section do not touch it
    assert where(app) == ("strengths", "outline") and app.state["summary"].endswith("very strong.")


def test_a_model_reply_is_applied_to_the_index(app):
    app.observations = True
    at(app, "weaknesses", "ask", [
        weakness("W1", "Single runs", body="Old body.", where="Table 2"),
        {"id": "C1", "kind": "comment", "claim": "Figure 2 is hard to read", "was": ["W4"]},
        {"id": "S1", "kind": "strength", "claim": "Clear"},
    ])
    app.script.append(outline(order=["W9", "W1", "W9", "Z1"], entries=[
        {"id": "W1", "body": "New body.", "where": "", "resolve": "Report seeds."},  # an empty part blanks nothing
        {"id": "W4", "group": "minor"},  # a former ID still finds its entry
        {"id": "W9", "claim": "A new one", "sources": ["A7"]},  # new: its kind comes from its letter
        {"id": "next", "claim": "No usable ID"},  # gets the next free ID of the open section
        {"id": "S1", "move": "comment"},
        {"id": "O1", "claim": "An observation", "drop": True},
    ]))
    app.reply({"text": "x"})
    assert app.state["entries"] == [
        {"id": "W9", "kind": "weakness", "claim": "A new one", "sources": ["A7"]},  # the order said aloud
        {"id": "C1", "kind": "comment", "claim": "Figure 2 is hard to read", "was": ["W4"]},  # a group is no longer kept
        {"id": "C2", "kind": "comment", "claim": "Clear", "was": ["S1"]},
        {"id": "W1", "kind": "weakness", "claim": "Single runs", "body": "New body.", "where": "Table 2", "resolve": "Report seeds."},
        {"id": "W10", "kind": "weakness", "claim": "No usable ID"},  # W4 is taken, by the entry that was W4
        {"id": "O1", "kind": "observation", "claim": "An observation", "dropped": True},
    ]
    assert app.state["ranked"] is True  # weaknesses were ordered aloud
    assert [e["id"] for e in app.state["turns"][-1]["fields"]["entries"]] == ["W1", "W4", "W9", "W10", "S1", "O1"]


def test_a_section_is_not_accepted_while_an_entry_lacks_its_location_or_fix(app):
    at(app, "weaknesses", "outline", [
        {"id": "S1", "kind": "strength", "claim": "Another section's gap"},
        weakness("W1", "a", where="Table 2"), weakness("W2", "b"), weakness("W3", "c", dropped=True),
        {"id": "O1", "kind": "observation", "claim": "o"},
    ])
    status, body = app.post("/api/reply", {"action": "accept"})
    assert status == 400 and body == {"error": (
        "W1 needs a fix; W2 needs a location and a fix; "
        "O1 is still an observation: make it a weakness or a comment, or drop it.")}
    assert where(app) == ("weaknesses", "outline") and app.state["turns"] == [] and app.calls == []
    # The reviewer may accept a point as it is, but an observation has to be decided either way.
    assert app.post("/api/reply", {"action": "accept", "force": True}) == (400, {"error": (
        "O1 is still an observation: make it a weakness or a comment, or drop it.")})

    # The reviewer fills the gap, marks the point as having no single location, or moves it.
    app.edit_entry({"id": "W1", "set": {"resolve": "Report seeds."}})
    app.edit_entry({"id": "W2", "set": {"nowhere": True, "resolve": "Narrow the claim."}})
    app.edit_entry({"id": "O1", "move": "comment"})
    app.script.append(ask({"question": "Anything to add?"}))
    assert app.post("/api/reply", {"action": "accept"})[0] == 200
    assert where(app) == ("comments", "ask")

    # The bias test is the last gate: it looks at strengths and weaknesses alike.
    app.state["phase"] = "outline"
    app.script += [ask({"question": "Bias?"}), outline()]
    app.reply({"action": "accept"})
    app.reply({"text": ""})
    assert where(app) == ("bias", "outline")
    assert app.post("/api/reply", {"action": "accept"}) == (400, {"error": "S1 needs a location."})
    calls = len(app.calls)
    app.reply({"action": "accept", "force": True})  # accepted as it is
    assert where(app) == ("draft", None)
    assert len(app.calls) == calls and not app.pending()  # the interview is over: nothing to ask the model


def test_skipping_a_section_moves_on(app):
    at(app, "comments", "ask", [weakness("W1", "a")])
    app.script.append(ask({"question": "Bias?"}))
    app.reply({"action": "skip", "text": "not sent on"})
    assert where(app) == ("bias", "ask")
    assert app.calls[-1]["prompt"] == f"[Skipped · comments]\n\n[Index]\nW1 (weakness): a\n{UNRANKED}\n\n[Next: ask · bias]"
    app.reply({"action": "skip"})
    assert where(app) == ("draft", None) and len(app.calls) == 1


def test_skipping_a_section_drops_the_candidates_it_never_wrote_out(app):
    moved_in = weakness("W3", "moved in, complete", body="b", where="Table 1", resolve="I would like x.")
    at(app, "weaknesses", "ask", [weakness("W1", "bare candidate"), moved_in,
                                  {"id": "O1", "kind": "observation", "claim": "Claude's"}, {"id": "S1", "kind": "strength"}])
    app.script.append(ask({"question": "Comments?"}))
    app.reply({"action": "skip"})
    assert [e["id"] for e in app.state["entries"] if e.get("dropped")] == ["W1", "O1"]


def test_a_change_to_the_summary_carries_the_paragraph_as_the_reviewer_left_it(app):
    at(app, "summary", "outline", summary="The model's version.")
    app.script.append(outline(sentences=[{"text": "Revised."}]))
    app.reply({"action": "change", "text": "drop the last bit", "summary": "My hand-edited version."})
    assert app.calls[-1]["prompt"].startswith(
        "[Change requested · summary]\ndrop the last bit\n\n[Summary as it stands]\nMy hand-edited version.\n\n[Index]")
    assert app.state["summary"] == "Revised."


@pytest.mark.parametrize(
    "stage,phase,payload,error",
    [
        ("new", None, {"text": "hello"}, "not open"),
        ("brief", None, {"action": "skip"}, "not open"),
        ("summary", "ask", {"action": "accept"}, "not open"),
        ("brief", None, {"action": "change", "text": "shorter"}, "not open"),
        ("summary", "ask", {"action": "change", "text": " "}, "Say what to change"),
        ("summary", "outline", {"text": "an answer"}, "not open"),
        ("summary", "outline", {"action": "skip"}, "not open"),
        ("summary", "outline", {"action": "change", "text": " "}, "Say what to change"),
        ("draft", None, {"text": "an answer"}, "not open"),
        ("final", None, {"action": "accept"}, "not open"),
    ],
)
def test_a_step_out_of_turn_is_refused(app, stage, phase, payload, error):
    at(app, stage, phase)
    status, body = app.post("/api/reply", payload)
    assert status == 400 and error in body["error"]
    assert app.state["turns"] == [] and app.calls == [] and where(app) == (stage, phase)


def test_hand_edits_change_the_index_without_a_turn_or_a_model_call(app):
    at(app, "weaknesses", "ask", [weakness("W1", "a"), weakness("W2", "b", dropped=True), weakness("W3", "c"),
                                  {"id": "S1", "kind": "strength", "claim": "s"}])
    app.edit_entry({"id": "W3", "set": {"claim": "  My  wording ", "where": "", "junk": "x", "kind": "strength", "nowhere": True}})
    assert app.state["entries"][2] == {"id": "W3", "kind": "weakness", "claim": "  My  wording ", "where": "",
                                       "nowhere": True, "by_hand": True}  # as typed
    assert "W3 (weakness; reviewer's wording):" in index_text(app.state["entries"], False)

    assert app.state["ranked"] is False
    app.edit_entry({"id": "W3", "shift": -1})  # up, past the dropped one
    assert ids(app) == ["W3", "W2", "W1", "S1"] and app.state["ranked"] is True
    app.edit_entry({"id": "W3", "shift": -1})  # already first
    app.edit_entry({"id": "W1", "shift": 1})  # already last of its kind
    assert ids(app) == ["W3", "W2", "W1", "S1"]

    app.edit_entry({"id": "W1", "move": "comment", "set": {"body": "My comment.", "group": "question"}})
    assert app.state["entries"][2] == {"id": "C1", "kind": "comment", "claim": "a", "body": "My comment.",
                                       "by_hand": True, "was": ["W1"]}  # a group is not a part any more
    app.edit_entry({"id": "W1", "move": "weakness"})  # the page may still hold the old ID
    assert ids(app) == ["W3", "W2", "W1", "S1"] and app.state["entries"][2]["was"] == ["C1"]
    app.edit_entry({"id": "W2", "dropped": False})
    app.edit_entry({"id": "S1", "dropped": True})
    assert [e.get("dropped") for e in app.state["entries"]] == [None, False, None, True]

    assert app.post("/api/summary", {"text": " My paragraph.\n"})[0] == 200
    assert app.state["summary"] == " My paragraph.\n"
    assert app.post("/api/entry", {"id": "W9", "set": {"claim": "x"}}) == (400, {"error": "There is no entry W9."})
    assert app.post("/api/entry", {"id": "W3", "move": "observation"})[0] == 400
    assert app.post("/api/summary", {})[0] == 400

    assert app.state["turns"] == [] and app.calls == []
    saved = json.loads(app.session_path.read_text(encoding="utf-8"))
    assert [e["id"] for e in saved["entries"]] == ["W3", "W2", "W1", "S1"] and saved["summary"] == " My paragraph.\n"
    assert "- W3: **My  wording.**" in app.answers_path.read_text(encoding="utf-8")  # the record follows the index


def test_a_change_after_the_interview_concerns_the_whole_review(app):
    at(app, "draft", None, [W_PINNED])
    app.script.append(outline(plan=[{"target": "W1", "action": "cut", "because": "drop the seeds one"}],
                              entries=[{"id": "W1", "drop": True}]))
    app.reply({"action": "change", "text": "drop the seeds one"})
    assert app.calls[-1]["prompt"].startswith("[Change requested · review]\ndrop the seeds one\n\n[Index]\nW1 (weakness): Single runs\n")
    assert app.calls[-1]["prompt"].endswith("\n\n[Next: revise · review]")
    assert where(app) == ("draft", None) and app.state["entries"][0]["dropped"] is True
    assert app.state["turns"][-1]["section"] == "draft"


def test_session_survives_a_restart_of_the_server(app, tmp_path):
    play_to_weaknesses(app)
    again = InterviewApp(Path("foo.pdf"), tmp_path)
    assert again.restore() and not again.legacy
    assert again.state == app.state and again.state["session_id"] == "sess-1" and len(again.state["turns"]) == 15


def test_answer_is_on_disk_before_the_model_replies_and_can_be_retried(app, monkeypatch, tmp_path):
    app.script += [{"kind": "brief", "message": "Brief."}, ask({"question": "What is the idea?"}),
                   outline(entries=[{"id": "W1", "drop": True}])]
    app.start()
    real = interview_app.ask_model

    def boom(*a, **k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(interview_app, "ask_model", boom)
    assert app.post("/api/reply", {"text": RAW}) == (500, {"error": "model unavailable"})
    # The failed call lost nothing: a new server finds the answer and knows it is unanswered.
    again = InterviewApp(Path("foo.pdf"), tmp_path)
    assert again.restore() and again.pending()
    assert again.state["turns"][-1]["text"] == RAW and where(again) == ("summary", "ask")
    assert again.view()["pending"] is True
    assert again.post("/api/reply", {"text": "again"})[0] == 400  # not a second answer: ask the model again

    monkeypatch.setattr(interview_app, "ask_model", real)
    assert again.post("/api/retry", {})[0] == 200
    assert not again.pending()
    assert [t["role"] for t in again.state["turns"]] == ["claude", "reviewer", "claude"]  # sent once, not twice
    assert app.calls[-1]["prompt"] == f"[Brief] {RAW}\n\n[Index]\n(empty)\n\n[Next: ask · summary]"
    again.ask_claude()  # nothing is owed now
    assert len(app.calls) == 2

    # A change asked for after the interview is owed a reply too.
    at(again, "draft", None, [W_PINNED])
    monkeypatch.setattr(interview_app, "ask_model", boom)
    assert again.post("/api/reply", {"action": "change", "text": "drop W1"})[0] == 500
    assert again.pending()
    monkeypatch.setattr(interview_app, "ask_model", real)
    again.ask_claude()
    assert not again.pending() and again.state["entries"][0]["dropped"] is True


def test_each_step_uses_its_own_model(app):
    """The brief and the check go to the strong model; the turns of the interview to the fast one."""
    deep = (interview_app.DEEP["model"], interview_app.DEEP["effort"])
    fast = (interview_app.FAST["model"], interview_app.FAST["effort"])
    assert deep != fast
    app.script += [{"kind": "brief", "message": "b"}, ask({"question": "q"}), outline(), "- all met"]
    app.start()
    app.reply({"text": ""})
    app.reply({"text": "an answer"})
    app.state["stage"] = "draft"
    app.check()
    app.draft()
    assert app.models == [deep, fast, fast, deep]  # the draft is assembled here, without a model


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
    app.script += [{"kind": "brief", "message": "b"}] * 2
    app.start()
    prompt = app.calls[0]["prompt"]
    assert "switched off for this session" in prompt and "do not create `O` entries" in prompt
    assert interview_app.OBSERVATIONS_PLACEHOLDER not in prompt

    (tmp_path / "on" / "extracted").mkdir(parents=True)
    on = InterviewApp(Path("foo.pdf"), tmp_path / "on", observations=True)
    on.extracted_path.write_text("PAPER TEXT", encoding="utf-8")
    on.start()
    assert "switched on for this session" in app.calls[-1]["prompt"] and "`O1`" in app.calls[-1]["prompt"]
    assert "switched off" not in app.calls[-1]["prompt"]


def test_addendum_has_exactly_one_place_for_the_observations_setting():
    text = interview_app.APP_ADDENDUM.read_text(encoding="utf-8")
    assert text.count(interview_app.OBSERVATIONS_PLACEHOLDER) == 1


def test_saved_interview_refuses_a_pdf_whose_annotations_changed(app, tmp_path):
    """Note IDs follow position, so one added note would shift every ID in the record."""
    app.script.append({"kind": "brief", "message": "b"})
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
    app.script += [{"kind": "brief", "message": "b"}, ask({"question": "q"})]
    app.start()
    app.reply({"text": "the second claim is missing"})
    app.restart()
    app.restart()  # a second restart must not replace the backup with an empty record
    backup = app.answers_path.with_name(app.answers_path.name + ".bak")
    assert "the second claim is missing" in backup.read_text(encoding="utf-8")
    assert app.session_path.with_name(app.session_path.name + ".bak").exists()
    assert app.state == interview_app.new_state()
    assert "the second claim" not in app.answers_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


def test_record_holds_the_reviewers_words_byte_for_byte(app):
    play_to_weaknesses(app)
    app.script.append(outline(entries=[{"id": "W1", "said": "the cost one"}]))
    app.reply({"action": "skip"})  # nothing to add to the weaknesses
    record = app.answers_path.read_text(encoding="utf-8")
    for said in ("claim 2 is missing", RAW, "drop 2", "The paper studies cheap retrieval,  my way.", "the cost one"):
        assert said in record
    assert f"Answer: {RAW}\n" in record
    assert "Scores" not in record  # scores are set in the review form, not here


def test_record_structure(app):
    play_to_weaknesses(app)
    app.edit_entry({"id": "W2", "dropped": True})
    app.edit_entry({"id": "W1", "set": {"where": "Table 2"}})
    assert app.answers_path.read_text(encoding="utf-8") == f"""# Interview record: foo.pdf

## Brief

Claim map: one claim.

Corrections from the reviewer: claim 2 is missing

## Summary

Asked:
1. What is the idea, in one sentence?
   Guide: One sentence.
Answer: {RAW}
Heard as: "graph rag" = GraphRAG
Outlined: The paper studies cheap retrieval. Results are very strong.
Change requested: drop 2
Plan:
- 2 cut: "drop 2"
Outlined: The paper studies cheap retrieval.
Accepted.

## Strengths

Asked:
1. [S1] Is the lower cost a strength?
   From the reviewer's notes: A3: "cheap!"
   From the paper: Table 2 reports half the calls.
Answer: (none: wording left to Claude)
Follow-up:
Asked:
1. [S1] Where does it show?
Answer: the cost one
Outlined: S1
Accepted.

## Weaknesses

Asked:
1. [W1] Which claim does the single run undermine?

## Summary (approved by the reviewer)

The paper studies cheap retrieval,  my way.

## Index

### Strengths
- S1: **Lower cost at similar accuracy.** The method halves the number of calls (Table 2).
  Notes: A3
  Said: "the cost one"
### Weaknesses (most severe first)
- W1: **Single runs.** (Table 2).
### Dropped
- W2: No stronger baseline
"""


def test_record_of_a_skipped_section_a_plain_question_and_the_bias_test(app):
    at(app, "comments", "ask", [{"id": "C1", "kind": "comment", "body": "Figure 2 is hard to read."},
                                {"id": "O1", "kind": "observation", "claim": "Costs are not matched"}])
    app.script += [
        ask({"id": "S1", "question": "If the results only match, is this still a strength?", "register": "B9"}),
        "Plain text, not the fields.",  # a malformed reply is still a question to answer
        outline(plan=[{"target": "S1", "action": "keep", "because": "it is about cost"}]),
    ]
    app.reply({"action": "skip"})
    app.reply({"text": "it is about cost"})
    app.reply({"text": "yes"})
    app.reply({"action": "accept"})
    record = app.answers_path.read_text(encoding="utf-8")
    assert record == """# Interview record: foo.pdf

## Comments

Skipped.

## Bias test

Asked:
1. [S1] If the results only match, is this still a strength?
   Register: B9
Answer: it is about cost
Asked: Plain text, not the fields.
Answer: yes
Plan:
- S1 keep: "it is about cost"
Outlined: (nothing changed)
Accepted.

## Index

### Comments
- C1: Figure 2 is hard to read.
### Claude's observations
- O1: [Claude] **Costs are not matched.**
"""
    assert "## Summary (approved" not in record  # none was accepted


# ---------------------------------------------------------------------------
# Check, draft and final
# ---------------------------------------------------------------------------


REVIEWED = [
    weakness("W2", "No stronger baseline", body="Only two systems are compared.", nowhere=True,
             resolve="I think one recent system should be added.", sources=["A9", "A4"], said="they need a real baseline"),
    {"id": "C1", "kind": "comment", "body": "Why is the budget fixed at ten?", "group": "question"},
    {"id": "S1", "kind": "strength", **{k: v for k, v in S1_OUTLINED.items() if k != "id"}},
    {"id": "C2", "kind": "comment", "claim": "Figure 2 is hard to read", "group": "typo", "was": ["O1"]},
    W_PINNED,
    weakness("W3", "Dropped point", dropped=True),
    {"id": "C3", "kind": "comment", "body": "Line 12: 'teh'.", "group": "minor"},
]
REVIEW = """# Review: foo

## Paper Summary

The paper studies cheap retrieval.

## Summary Of Strengths

* **Lower cost at similar accuracy.** The method halves the number of calls (Table 2).

## Summary Of Weaknesses

* **No stronger baseline.** Only two systems are compared. I think one recent system should be added.
* **Single runs.** Each setting is run once (Table 2). This weakens the cost claim. I would like to see three seeds.

## Comments Suggestions And Typos

* Why is the budget fixed at ten?
* [Claude] Figure 2 is hard to read
* Line 12: 'teh'."""
TRACE = """**Where each point comes from**

- **S1**: Lower cost at similar accuracy
  - A3: "cheap!"
  - You said: "the cost one"
- **W2**: No stronger baseline
  - A9
  - A4: "key phrase"
  - You said: "they need a real baseline" (not found word for word in your answers)
- **W1**: Single runs
- **C1**: Why is the budget fixed at ten?
- **C2** (was O1): Figure 2 is hard to read
- **C3**: Line 12: 'teh'.

**From Claude**

- C2: Figure 2 is hard to read

**Dropped**

- W3: Dropped point"""


def reviewed(app, stage="draft"):
    at(app, stage, None, REVIEWED, summary="The paper studies cheap retrieval.\n",
       turns=[{"role": "reviewer", "section": "strengths", "kind": "answer", "text": "yes,  the cost\none is real"}])
    app.paper = {"annotations": [{"id": "A3", "type": "note", "note": "cheap!", "text": None},
                                 {"id": "A4", "type": "highlight", "note": None, "text": "key phrase"}]}


def test_draft_is_assembled_from_the_summary_and_the_index(app):
    reviewed(app)
    assert app.post("/api/draft", {})[0] == 200
    assert app.calls == []  # no model writes the draft
    assert where(app) == ("final", None)
    assert app.state["draft"] == f"{REVIEW}\n\n---\n\n{TRACE}"
    assert app.review_text_path.read_text(encoding="utf-8") == REVIEW + "\n"  # paste-ready
    assert app.trace_path.read_text(encoding="utf-8") == TRACE + "\n"  # kept, but apart
    assert app.draft_path.read_text(encoding="utf-8") == f"{REVIEW}\n\n---\n\n{TRACE}\n"
    assert "Scores" not in REVIEW and "/5" not in REVIEW

    # The draft follows a change made after it, with no need to draft again.
    app.edit_entry({"id": "W1", "shift": -1})
    assert app.state["draft"].index("**Single runs.**") < app.state["draft"].index("**No stronger baseline.**")
    app.set_summary("A new summary.")
    assert "A new summary." in app.review_text_path.read_text(encoding="utf-8")
    assert "A new summary." in app.draft_path.read_text(encoding="utf-8")


def test_draft_without_a_summary_or_comments_says_what_is_missing(app):
    at(app, "draft", None, [W_PINNED])
    app.draft()
    assert app.review_text_path.read_text(encoding="utf-8") == (
        "# Review: foo\n\n## Paper Summary\n\n[Reviewer to add]\n\n## Summary Of Strengths\n\n"
        "## Summary Of Weaknesses\n\n* **Single runs.** Each setting is run once (Table 2). "
        "This weakens the cost claim. I would like to see three seeds.\n\n## Comments Suggestions And Typos\n")


def test_draft_is_refused_while_an_entry_has_gaps_unless_forced(app):
    at(app, "draft", None, [weakness("W1", "a", where="Table 2"), {"id": "S1", "kind": "strength", "claim": "s"},
                            {"id": "O1", "kind": "observation", "claim": "Left as an observation"}])
    assert app.post("/api/draft", {}) == (400, {"error": "W1 needs a fix; S1 needs a location."})
    assert where(app) == ("draft", None) and app.state["draft"] == ""
    assert app.post("/api/draft", {"force": True})[0] == 200
    assert where(app) == ("final", None)
    trace = app.trace_path.read_text(encoding="utf-8")
    assert "**Drafted with gaps**\n\n- W1 needs a fix\n- S1 needs a location" in trace
    assert "- O1: Left as an observation (still an observation: not in the review)" in trace
    assert "Left as an observation" not in app.review_text_path.read_text(encoding="utf-8")

    at(app, "bias", "ask")
    assert app.post("/api/draft", {"force": True})[0] == 400  # the interview comes first
    assert app.post("/api/check", {})[0] == 400


def test_check_runs_the_guidelines_over_the_review_as_it_stands(app):
    reviewed(app)
    suggested = "**No stronger baseline.** Only two systems are compared (Table 2)."
    app.script.append({"findings": [
        {"target": "W2", "problem": "No location.", "suggestion": suggested, "sources": ["A9", "Table 2"],
         "where": "Table 2", "other": 1},
        {"target": "Summary", "problem": "Too short.", "suggestion": "A longer summary."},
        {"target": "W1", "problem": "The fix is not the reviewer's."},
        {"problem": "no target"}, "junk"]})
    app.check()
    call = app.calls[-1]
    assert call["session_id"] == "sess-1" and call["schema"] is interview_app.CHECK_SCHEMA  # in the interview's session
    assert "section 7" in call["prompt"] and "section 6" in call["prompt"] and "do not suggest any" in call["prompt"]
    assert "Do not add a reason" in call["prompt"]  # a suggestion is built from the reviewer's own material
    assert "<review>\n# Review: foo\n" in call["prompt"]
    assert "* [W2] **No stronger baseline.**" in call["prompt"] and "* [C2] [Claude] Figure 2" in call["prompt"]
    assert app.state["findings"] == [
        {"target": "W2", "problem": "No location.", "suggestion": suggested, "where": "Table 2", "sources": ["A9"]},
        {"target": "Summary", "problem": "Too short.", "suggestion": "A longer summary."},
        {"target": "W1", "problem": "The fix is not the reviewer's."}]
    assert where(app) == ("draft", None) and app.view()["session"]["findings"] == app.state["findings"]
    assert app.check_path.read_text(encoding="utf-8") == (
        f"- **W2**: No location.\n  - Suggested (from A9, Table 2): {suggested}\n"
        "- **Summary**: Too short.\n  - Suggested: A longer summary.\n"
        "- **W1**: The fix is not the reviewer's.\n")

    # A suggestion is taken with one click, or the finding is set aside. Nothing changes before that.
    w2 = find_entry(app.state["entries"], "W2")
    assert "text" not in w2
    assert app.post("/api/finding", {"n": 0, "action": "use"})[0] == 200
    assert w2["text"] == suggested and w2["by_hand"] is True and bullet(w2) == suggested
    assert app.post("/api/finding", {"n": 1, "action": "use"})[0] == 200 and app.state["summary"] == "A longer summary."
    assert app.post("/api/finding", {"n": 2, "action": "use"}) == (400, {"error": "This finding has no suggestion to take."})
    assert app.post("/api/finding", {"n": 2, "action": "dismiss"})[0] == 200
    assert [f.get("status") for f in app.state["findings"]] == ["used", "used", "dismissed"]
    for bad in ({"n": 3, "action": "use"}, {"n": True, "action": "use"}, {"n": 0, "action": "other"}, {}):
        assert app.post("/api/finding", bad)[0] == 400
    assert len(app.calls) == 1  # no model is asked when a finding is settled

    # A check that comes back as plain text, or with nothing to report, is shown as it is.
    app.script += ["- W2: no location\n", {"findings": []}]
    app.check()
    assert app.state["findings"] == [] and app.state["check"] == "- W2: no location\n"
    assert app.check_path.read_text(encoding="utf-8") == "- W2: no location\n"
    app.check()
    assert app.state["check"] == "Nothing found: the review meets the checklist."
    at(app, "bias", "ask")
    assert app.post("/api/finding", {"n": 0, "action": "use"})[0] == 400  # the check comes after the interview


def test_the_reviewers_own_text_of_a_point_stands(app):
    at(app, "weaknesses", "outline", [weakness("W1", "Single runs", body="Each setting is run once.")])
    assert gaps(app.state["entries"][0]) == ["where", "resolve"]
    app.edit_entry({"id": "W1", "set": {"text": " Each setting is run once, so I cannot  tell.\n"}})
    w1 = app.state["entries"][0]
    assert w1["text"] == " Each setting is run once, so I cannot  tell.\n" and w1["by_hand"] is True  # as typed
    assert wording(w1) == bullet(w1) == "Each setting is run once, so I cannot  tell."
    assert gaps(w1) == []  # what the reviewer's own wording holds is theirs to judge
    index = index_text(app.state["entries"], False)
    assert "  text: Each setting is run once, so I cannot tell." in index and "  body:" not in index

    # Parts from the model do not replace it.
    app.script.append(outline(entries=[{"id": "W1", "claim": "Runs", "body": "Rewritten.", "sources": ["A2"]}]))
    app.reply({"action": "change", "text": "tidy the others"})
    assert bullet(w1).startswith("Each setting is run once, so") and w1["claim"] == "Single runs" and w1["sources"] == ["A2"]
    # A new text does, when the reviewer asked for a change.
    app.script.append(outline(entries=[{"id": "W1", "claim": "One run", "text": "Each setting is run once."}]))
    app.reply({"action": "change", "text": "W1: shorter"})
    assert bullet(w1) == "Each setting is run once." and w1["claim"] == "One run"
    # It does not when the reviewer said nothing, as in the questions of the next section.
    app.script.append(ask({"question": "Anything to add?"}, entries=[{"id": "W1", "text": "The model's own."}]))
    app.reply({"action": "accept"})
    assert where(app) == ("comments", "ask") and bullet(w1) == "Each setting is run once."

    # The model cannot start a text: its entries are written as parts.
    at(app, "weaknesses", "outline", [weakness("W2", "b", body="Body.")])
    app.script.append(outline(entries=[{"id": "W2", "text": "Model text."}]))
    app.reply({"action": "change", "text": "x"})
    w2 = app.state["entries"][0]
    assert "text" not in w2 and "by_hand" not in w2
    # An emptied text gives the bullet back to the parts.
    app.edit_entry({"id": "W2", "set": {"text": "Mine."}})
    assert bullet(w2) == "Mine."
    app.edit_entry({"id": "W2", "set": {"text": "  "}})
    assert "text" not in w2 and bullet(w2) == "**b.** Body."


def test_a_change_to_one_entry_can_be_asked_for_while_the_questions_are_open(app):
    at(app, "strengths", "ask", [{**S1, "kind": "strength"}])
    app.script.append(outline(plan=[{"target": "S1", "action": "rewrite", "because": "it is Table 4"}],
                              entries=[{"id": "S1", "where": "Table 4"}]))
    app.reply({"action": "change", "text": "S1: it is Table 4"})
    assert where(app) == ("strengths", "ask")  # the answer to the questions is still owed
    assert app.state["entries"][0]["where"] == "Table 4"
    assert app.calls[-1]["prompt"].endswith("[Next: revise · strengths]")


def test_the_usage_log_holds_each_request_and_what_it_changed(app):
    at(app, "weaknesses", "outline", [weakness("W1", "a", where="Table 2"), weakness("W2", "b")])
    app.post("/api/entry", {"id": "W1", "set": {"text": "My  own text."}})
    app.post("/api/entry", {"id": "W2", "shift": -1})
    app.post("/api/reply", {"action": "accept"})  # refused: W2 has gaps
    app.post("/api/summary", {"text": "A summary."})
    app.script.append(ask({"question": "Anything to add?"}))
    app.post("/api/reply", {"action": "accept", "force": True})
    app.page_events({"events": [{"event": "view", "at": "2026-01-01T10:00:00Z", "entry": "W1"}, {"no": "event"}, "junk"]})
    lines = [json.loads(line) for line in app.usage_path.read_text(encoding="utf-8").splitlines()]
    assert [line["event"] for line in lines] == ["request"] * 5 + ["page"]
    assert all(line["t"] and isinstance(line["ms"], int) for line in lines[:5])
    assert [(line["stage"], line["phase"]) for line in lines] == [("weaknesses", "outline")] * 4 + [("comments", "ask")] * 2
    assert lines[0]["path"] == "/api/entry" and lines[0]["status"] == 200
    assert lines[0]["body"] == {"id": "W1", "set": {"text": "My  own text."}}  # as sent
    assert lines[0]["entries"] == [{"id": "W1", "set": {"by_hand": [None, True], "text": [None, "My  own text."]}}]
    assert lines[1]["order"] == ["W2", "W1"] and "entries" not in lines[1]
    assert lines[2]["status"] == 400 and lines[2]["error"] == "W2 needs a location and a fix."
    assert "moved" not in lines[2] and "entries" not in lines[2]
    assert lines[3]["summary"] == ["", "A summary."]
    assert lines[4]["moved"] == ["weaknesses/outline", "comments/ask"]
    assert {k: lines[5][k] for k in ("what", "at", "data")} == {
        "what": "view", "at": "2026-01-01T10:00:00Z", "data": {"entry": "W1"}}


def test_final_saves_the_review_as_submitted_and_keeps_it_as_an_example(app, tmp_path):
    reviewed(app)
    submitted = "# Review\n\nWhat I  sent in, edited by hand."
    assert app.post("/api/final", {"text": submitted})[0] == 400  # there is no draft yet
    app.draft()
    assert app.post("/api/final", {"text": "  "})[0] == 400
    status, view = app.post("/api/final", {"text": submitted})
    assert status == 200 and view["session"]["final"] == submitted and view["session"]["stage"] == "final"
    assert app.final_path.read_text(encoding="utf-8") == submitted
    assert view["files"]["final"] == str(tmp_path / "reviews" / "foo.review-final.md")
    example = tmp_path / "reviewing" / "my_reviews" / f"ACL_ARR_{date.today():%Y_%B}_foo.md"
    assert example.read_text(encoding="utf-8") == submitted  # the reviewer's text, never the draft
    app.finish("Second thoughts.")  # saving again overwrites
    assert example.read_text(encoding="utf-8") == "Second thoughts."
    assert sorted(review_module.REVIEWING_DIR.glob(review_module.PAST_REVIEW_GLOBS["arr"])) == [example]


# ---------------------------------------------------------------------------
# The view and the requests
# ---------------------------------------------------------------------------


def test_view_gives_each_entry_its_bullet_gaps_and_whether_its_quote_was_said(app):
    reviewed(app)
    app.state["entries"][2]["said"] = "yes, the cost one"  # words in order; spacing does not count
    view = app.view()
    assert set(view) == {"paper", "session", "busy", "pending", "files"}
    assert set(view["session"]) == {"legacy", "stage", "phase", "turns", "summary", "entries", "ranked", "check",
                                    "findings", "draft", "final"}
    assert set(view["files"]) == {"answers", "review_text", "trace", "check", "final"}
    assert (view["session"]["legacy"], view["busy"], view["pending"]) == (False, False, False)
    entries = {e["id"]: e for e in view["session"]["entries"]}
    assert entries["W2"]["bullet"] == "**No stronger baseline.** Only two systems are compared. I think one recent system should be added."
    assert entries["W2"]["gaps"] == [] and entries["W2"]["said_ok"] is False
    assert entries["W2"]["wording"] == entries["W2"]["bullet"]  # what the reviewer edits
    assert entries["C2"]["wording"] == "Figure 2 is hard to read"  # without the mark for a point of Claude's
    assert entries["S1"]["said_ok"] is True and entries["S1"]["kind"] == "strength"
    assert "said_ok" not in entries["C1"] and entries["C2"]["bullet"].startswith("[Claude] ")
    app.edit_entry({"id": "W2", "set": {"nowhere": False}})
    assert find_entry(app.view()["session"]["entries"], "W2")["gaps"] == ["where"]
    assert "bullet" not in app.state["entries"][0]  # worked out for the page, not stored


def test_paper_view_carries_the_register_and_the_fixed_score_reminders(tmp_path, monkeypatch):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(72, 140, 520, 400), "The method uses a key phrase to find documents. " * 6, fontsize=10)
    page.add_text_annot((530, 150), "Why this phrase?")
    doc.save(tmp_path / "small.pdf")
    (tmp_path / "reviewing").mkdir()
    (tmp_path / "reviewing" / "BIASES.md").write_text(
        '| B4 | **Confidence not tracking understanding.** More. | Signal | "How well do you understand it?" |\n'
        '| B6 | **Extra experiments not tied to a claim** (H13). | Signal | "Which claim fails without it?" |\n',
        encoding="utf-8")
    monkeypatch.setattr(review_module, "REVIEWING_DIR", tmp_path / "reviewing")
    a = InterviewApp(tmp_path / "small.pdf", tmp_path)
    a.prepare()
    paper = a.view()["paper"]
    assert paper["name"] == "small.pdf" and paper["counts"] == {"pages": 1, "highlights": 0, "notes": 1}
    assert set(paper["register"]) == {"B4", "B6"}
    assert paper["score_reminders"] == [  # B14 and B16 are not in this register
        {"id": "B4", "title": "Confidence not tracking understanding", "how": "More.", "signal": "Signal",
         "question": "How well do you understand it?", "sources": []}]
    assert paper["annotations"][0]["note"] == "Why this phrase?" and a.fingerprint


def test_requests_get_a_status(app):
    app.script.append({"kind": "brief", "message": "b"})
    for gone in ("/api/record", "/api/restart", "/api/nothing"):
        assert app.post(gone, {}) == (404, {"error": "Not found"})
    status, view = app.post("/api/start", {})
    assert status == 200 and view["session"]["stage"] == "brief" and view["busy"] is False
    assert app.post("/api/start", {})[0] == 200 and len(app.calls) == 1  # starting twice asks once
    with app.busy:  # one request at a time
        assert app.post("/api/reply", {"text": "x"})[0] == 409
        assert app.view()["busy"] is True
    assert app.state["turns"][-1]["role"] == "claude"


def test_a_session_from_the_earlier_flow_is_shown_read_only(app):
    old = {"stage": "drafted", "session_id": "old", "draft": "# Review\n\ntext\n\n---\n\ntrace", "check": "- fine",
           "turns": [{"role": "claude", "fields": {"kind": "question", "message": "Idea?", "round": 1,
                                                    "items": [{"id": "P1", "type": "point", "text": "Weak baselines"}]}},
                     {"role": "reviewer", "kind": "answer", "text": RAW, "q": 1, "exchange": 1}]}
    app.session_path.parent.mkdir(parents=True)
    app.session_path.write_text(json.dumps(old), encoding="utf-8")
    app.answers_path.write_text("the old record", encoding="utf-8")
    assert app.restore() and app.legacy
    session = app.view()["session"]
    assert session["legacy"] is True and session["turns"] == old["turns"]
    assert (session["draft"], session["check"], session["stage"]) == (old["draft"], "- fine", "drafted")
    assert (session["entries"], session["summary"], session["phase"], session["final"]) == ([], "", None, "")
    assert app.view()["pending"] is False

    for path, body in (("/api/reply", {"text": "more"}), ("/api/start", {}), ("/api/draft", {"force": True}),
                       ("/api/entry", {"id": "P1", "dropped": True}), ("/api/final", {"text": "x"})):
        status, answer = app.post(path, body)
        assert status == 400 and "earlier version" in answer["error"] and "--restart" in answer["error"]
    assert json.loads(app.session_path.read_text(encoding="utf-8")) == old  # nothing is written
    assert app.answers_path.read_text(encoding="utf-8") == "the old record" and app.calls == []

    app.restart()
    assert not app.legacy and app.view()["session"]["legacy"] is False
    assert json.loads(app.session_path.with_name(app.session_path.name + ".bak").read_text(encoding="utf-8")) == old
    assert app.answers_path.with_name(app.answers_path.name + ".bak").read_text(encoding="utf-8") == "the old record"


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


def test_an_observation_is_not_taken_while_observations_are_off(app):
    """The prompt asks for none; one that arrives anyway does not reach the index."""
    reply = ask({"id": "W1", "question": "q"}, entries=[
        {"id": "W1", "claim": "The reviewer's own"},
        {"id": "O1", "claim": "The model's own", "body": "b", "where": "Table 2"},
    ])
    at(app, "weaknesses", "ask", [])
    app.script += [reply, reply]
    app.reply({"text": "x"})
    assert ids(app) == ["W1"]

    # The setting is kept with the session: started with observations, it holds on a later run without the flag.
    at(app, "weaknesses", "ask", [], turns=[], observations=True)
    app.reply({"text": "x"})
    assert ids(app) == ["W1", "O1"]


def test_the_server_refuses_a_request_from_another_site(app):
    """`is_local` through the real handler, for a read and for a write."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), interview_app.make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    def status(path, data=None, **headers):
        request = urllib.request.Request(url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code

    try:
        assert status("/api/state") == 200
        assert status("/api/state", Origin="https://other.example") == 403
        assert status("/api/state", Host="other.example") == 403
        summary = json.dumps({"text": "Changed from elsewhere."}).encode()
        assert status("/api/summary", summary, Origin="https://other.example") == 403
        assert app.state["summary"] == ""
        assert status("/api/summary", summary, Origin=url) == 200
        assert app.state["summary"] == "Changed from elsewhere."
    finally:
        server.shutdown()
        server.server_close()
