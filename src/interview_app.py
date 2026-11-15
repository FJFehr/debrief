"""Browser page for the review interview: the interview beside the annotated paper.

Usage:
    uv run interview --paper reviews/foo.pdf
    uv run interview --paper reviews/foo.pdf --restart     (discard the saved interview)

Runs the process in reviewing/INTERVIEW.md, one section of the review form at a
time. The model is the installed `claude` command-line tool, used without tools.
This server keeps the state: the record, in which every answer is stored exactly
as it was sent, and the index of the reviewer's points, from which it assembles
the draft itself.

Writes, under outputs/reviews/:
    foo.session.json        interview state (reloading the page continues it)
    foo.answers.md          the interview record
    foo.review-check.md     the check of the review against the guidelines
    foo.review-text.md      the drafted review alone, ready to paste into the form
    foo.review-trace.md     for the reviewer only: where each point comes from
    foo.review-draft.md     the two above in one file
    foo.review-final.md     the review as submitted (copied to reviewing/my_reviews/)
    foo.usage.jsonl         what the reviewer did, one line per action, for the stock-take
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymupdf

from src import review as review_module
from src.extract import document_index, extract, front_matter, load_document
from src.review import load_interview_prompt

STATIC_DIR = Path(__file__).parent / "interview_static"
APP_ADDENDUM = Path("prompts/templates/interview_app.md")
MODEL_CWD = Path.home() / ".cache" / "debrief" / "interview"
MODEL_TIMEOUT_S = 900
PAGE_ZOOM = 2.0

SYSTEM_PROMPT = (
    "You are Claude, helping a researcher write a peer review. "
    "Follow the instructions given in the conversation. You have no tools in this session."
)

OBSERVATIONS_PLACEHOLDER = "<observations setting>"
OBSERVATIONS = {
    False: (
        "**Observations of your own are switched off for this session.** Do not offer points that "
        "the reviewer's notes did not raise, and do not create `O` entries. If you saw something "
        "the reviewer would plainly want to know, such as a note that the paper contradicts, it "
        "belongs in the facts you give under the reviewer's own point."
    ),
    True: (
        "**Observations of your own are switched on for this session.** In the weaknesses ask, "
        "offer at most three points that the reviewer's notes did not raise, as entries `O1`, "
        "`O2`, …: a claim, a body of one or two sentences, and its location in `where`. They are "
        "labelled as yours. The reviewer makes each one a weakness or a comment, or drops it."
    ),
}

# Which model does which step. Reading the paper against the notes and checking
# the review need real analysis and happen once each, so they get the strongest
# model. Interview turns follow a fixed format and are waited on ten or more
# times, so they get a faster setting. Measured on one real question turn:
# Fable at default effort 97 s, Opus at low effort 36 s, with the same number of
# points, register entries and verifiable figures in the result.
DEEP = {"model": "claude-fable-5-2", "effort": None}
FAST = {"model": "claude-opus-5-5", "effort": "low"}

SECTIONS = ("summary", "strengths", "weaknesses", "comments", "bias")
STAGES = ("brief",) + SECTIONS + ("draft", "final")  # the stage is "new" before the brief exists
LETTERS = {"S": "strength", "W": "weakness", "C": "comment", "O": "observation"}
SECTION_KIND = {"strengths": "strength", "weaknesses": "weakness", "comments": "comment"}
# The kinds a review holds. An observation becomes one of them or is dropped.
KINDS = tuple(SECTION_KIND.values())
# `text` is the bullet in the reviewer's own wording. Once it is set, it is what the review prints.
ENTRY_PARTS = ("claim", "body", "where", "undermines", "resolve", "text", "said")
# Register entries about scores: shown as fixed text on the final step, never asked.
SCORE_ENTRIES = ("B4", "B14", "B16")
ID_RE = re.compile(f"[{''.join(LETTERS)}]\\d+")
GAP_NAMES = {"where": "a location", "resolve": "a fix"}
# The material behind one thing the reviewer is asked, by where it comes from.
ASK_PARTS = (
    ("notes", "From the reviewer's notes"),
    ("paper", "From the paper"),
    ("guide", "Guide"),
    ("register", "Register"),
)
ASK_FIELDS = ("question", "id") + tuple(key for key, _ in ASK_PARTS)
PLAN_FIELDS = ("target", "action", "because")
SECTION_TITLES = {
    "brief": "Brief", "summary": "Summary", "strengths": "Strengths", "weaknesses": "Weaknesses",
    "comments": "Comments", "bias": "Bias test", "draft": "Review", "final": "Review",
}
INDEX_TITLES = {
    "strength": "Strengths", "weakness": "Weaknesses (most severe first)", "comment": "Comments",
    "observation": "Claude's observations",
}
LABELS = {"answer": "Answer", "skip": "Skipped", "accept": "Accepted", "change": "Change requested"}
RANKED = "The reviewer has ordered the weaknesses by severity, most severe first."
UNRANKED = "The reviewer has not ordered the weaknesses by severity."
LEGACY = (
    "This interview was saved by an earlier version and is read-only. "
    "Run again with --restart to begin a new one (the old one is kept as a .bak file)."
)
CHECK_PROMPT = (
    "This message is outside the interview: reply with the fields named here, not the interview's. "
    "Below is the review as the app assembles it from the accepted summary and the index, each "
    "point with its entry ID. Check it against the reviewer's guidelines: go through the checklist "
    "in section 7 item by item, and the bias checks in section 6 for each weakness. Return one "
    "finding for each thing that is not met, the most important first, and none if everything is "
    "met.\n\n"
    "- `target`: the entry ID it concerns (W2, S1) or Summary.\n"
    "- `problem`: what is not met, in one sentence.\n"
    "- `suggestion`: the whole point, or the whole summary, reworded so that it is met, in the "
    "form it has below and without its ID, ready to replace the current text. Build it only from "
    "the reviewer's notes, the reviewer's answers in this interview and the point as it stands: "
    "tie the point to the place in the paper that the notes are attached to, and state the reason "
    "the reviewer gave. Keep the reviewer's wording wherever it already does the job. Do not add "
    "a reason, a judgement, a figure or a request that the reviewer did not give. If the notes "
    "and answers do not hold what the fix needs, leave `suggestion` empty and say in `problem` "
    "what the reviewer has to supply.\n"
    "- `sources`: the note IDs the suggestion rests on.\n"
    "- `where`: the place in the paper it ties the point to, as references (Table 2; Section 5.2).\n\n"
    "The reviewer sets the scores in the review form, so leave the items about scores aside and "
    "do not suggest any."
)
FINDING_FIELDS = ("target", "problem", "suggestion", "where")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _strings(*names: str) -> dict:
    return {name: {"type": "string"} for name in names}


def _array(properties: dict, *required: str) -> dict:
    items = {"type": "object", "properties": properties, "required": list(required)}
    return {"type": "array", "items": items}


REPLY_SCHEMA = {
    "type": "object",
    # `plan` comes before the text it governs, so that the model fills it in first.
    "properties": {
        "kind": {"type": "string", "enum": ["brief", "question", "outline"]},
        "plan": _array(_strings(*PLAN_FIELDS), "target", "action"),
        "message": {"type": "string"},
        "asks": _array(_strings(*ASK_FIELDS), "question"),
        "sentences": _array(_strings("text", "job"), "text"),
        "entries": _array(
            {
                **_strings("id", *ENTRY_PARTS),
                "sources": {"type": "array", "items": {"type": "string"}},
                "drop": {"type": "boolean"},
                "move": {"type": "string", "enum": list(KINDS)},
            },
            "id",
        ),
        "order": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "string"}},
        "follow_up": {"type": "boolean"},
        "heard_as": {"type": "string"},
    },
    "required": ["kind", "message"],
}


CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": _array(
            {**_strings(*FINDING_FIELDS), "sources": {"type": "array", "items": {"type": "string"}}},
            "target",
            "problem",
        )
    },
    "required": ["findings"],
}


class Refused(Exception):
    """A request the interview cannot take as it stands. Raised before anything is changed."""


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def ask_model(
    prompt: str,
    session_id: str | None = None,
    schema: dict | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> tuple[object, str]:
    """Send one turn to the `claude` CLI. Returns (reply, session_id).

    The reply is a dict when a schema is given, otherwise the text.
    """
    # --tools "" removes the built-in tools only. The other two flags keep out the
    # user's settings (and with them plugins and their hooks) and every connector,
    # so nothing but this prompt shapes the review. The login is still used.
    cmd = ["claude", "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config",
           "--setting-sources", "", "--system-prompt", SYSTEM_PROMPT]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    if session_id:
        cmd += ["--resume", session_id]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    MODEL_CWD.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, cwd=MODEL_CWD, timeout=MODEL_TIMEOUT_S
        )
    except FileNotFoundError:
        raise RuntimeError("The `claude` command was not found. Install Claude Code and log in.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"The model did not answer within {MODEL_TIMEOUT_S // 60} minutes.")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError((proc.stderr or proc.stdout or "No output from the model.").strip()[:500])
    if proc.returncode != 0 or out.get("is_error"):
        raise RuntimeError(str(out.get("result") or proc.stderr or "The model call failed.")[:500])
    reply = out.get("structured_output") if schema else out.get("result", "")
    if schema and reply is None:
        reply = out.get("result", "")
    return reply, out.get("session_id", session_id or "")


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _row(raw: object, keys: tuple[str, ...]) -> dict:
    """One object from the model, cut down to its non-empty strings under `keys`."""
    return {k: _text(raw.get(k)) for k in keys if _text(raw.get(k))} if isinstance(raw, dict) else {}


def _rows(value: object, keys: tuple[str, ...]) -> list[dict]:
    """A list of objects from the model. The first key is required: a row without it is left out."""
    return [row for row in (_row(raw, keys) for raw in _list(value)) if keys[0] in row]


def _note_ids(value: object) -> list[str]:
    return [s for s in _list(value) if isinstance(s, str) and re.fullmatch(r"A\d+", s)]


def parse_reply(raw: object) -> dict:
    """Normalise a model reply into the fields the app relies on.

    Anything malformed degrades to a plain question, so the conversation can
    always continue. Lists are kept only when they hold something.
    """
    fields: dict = {}
    if isinstance(raw, dict):
        fields = raw
    elif isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            fields = loaded if isinstance(loaded, dict) else {"message": raw}
        except json.JSONDecodeError:
            fields = {"message": raw}
    entries = []
    for item in _list(fields.get("entries")):
        if not isinstance(item, dict):
            continue
        # An empty part is left out, so a reply cannot blank what the index holds.
        entry = {"id": _text(item.get("id")).upper(), **_row(item, ENTRY_PARTS)}
        if _note_ids(item.get("sources")):
            entry["sources"] = _note_ids(item["sources"])
        if item.get("drop") is True:
            entry["drop"] = True
        if item.get("move") in KINDS:
            entry["move"] = item["move"]
        if entry["id"] or len(entry) > 1:
            entries.append(entry)
    lists = {
        "asks": _rows(fields.get("asks"), ASK_FIELDS),
        "sentences": _rows(fields.get("sentences"), ("text", "job")),
        "entries": entries,
        "plan": _rows(fields.get("plan"), PLAN_FIELDS),
        "order": [_text(i).upper() for i in _list(fields.get("order")) if _text(i)],
        "sources": _note_ids(fields.get("sources")),
    }
    out: dict = {
        "kind": fields.get("kind") if fields.get("kind") in ("brief", "outline") else "question",
        "message": _text(fields.get("message")),
        **{key: value for key, value in lists.items() if value},
    }
    if fields.get("follow_up") is True:
        out["follow_up"] = True
    if _text(fields.get("heard_as")):
        out["heard_as"] = _text(fields["heard_as"])
    return out


# ---------------------------------------------------------------------------
# Entries (pure functions over the index)
# ---------------------------------------------------------------------------


def find_entry(entries: list[dict], entry_id: object) -> dict | None:
    """The entry with this ID, or the one that had it before it moved to another kind."""
    return next((e for e in entries if entry_id == e["id"] or entry_id in e.get("was", [])), None)


def next_id(entries: list[dict], kind: str) -> str:
    """The next free ID for a kind. Former IDs count as used: an ID never names two entries."""
    letter = next(letter for letter, k in LETTERS.items() if k == kind)
    used = [i for e in entries for i in (e["id"], *e.get("was", [])) if i[0] == letter]
    return f"{letter}{max((int(i[1:]) for i in used), default=0) + 1}"


def move_entry(entries: list[dict], entry: dict, kind: str) -> None:
    """Move an entry to another kind: a new ID, or its earlier one if it has been that kind before."""
    if kind == entry["kind"]:
        return
    was = entry.get("was", [])
    earlier = next((i for i in was if LETTERS[i[0]] == kind), None)
    new_id = earlier or next_id(entries, kind)
    entry["was"] = [i for i in was if i != earlier] + [entry["id"]]
    entry.update(id=new_id, kind=kind)


def from_claude(entry: dict) -> bool:
    """True if the entry began as an observation of the model's."""
    return any(i.startswith("O") for i in (entry["id"], *entry.get("was", [])))


def gaps(entry: dict) -> list[str]:
    """What an entry is still without: "where", "resolve". The reviewer may accept it as it is."""
    if entry.get("dropped") or entry["kind"] not in ("strength", "weakness"):
        return []
    if _text(entry.get("text")):  # the reviewer's own wording: what it holds is theirs to judge
        return []
    missing = [] if _text(entry.get("where")) or entry.get("nowhere") else ["where"]
    if entry["kind"] == "weakness" and not _text(entry.get("resolve")):
        missing.append("resolve")
    return missing


def gap_lines(entries: list[dict]) -> list[str]:
    """One line for each entry that lacks something, for a refusal or the trace."""
    return [
        f"{e['id']} needs {' and '.join(GAP_NAMES[g] for g in gaps(e))}" for e in entries if gaps(e)
    ]


def _sentence(text: str) -> str:
    """The text closed with a full stop, unless it already ends a sentence."""
    return text if not text or text[-1] in ".?!" else text + "."


def wording(entry: dict) -> str:
    """The entry's text for the review: the reviewer's own wording, or else built from its parts.

    When it is built, empty parts and their punctuation are left out.
    """
    if _text(entry.get("text")):
        return _text(entry["text"])
    claim, body, where, undermines, resolve = (
        _text(entry.get(part)) for part in ("claim", "body", "where", "undermines", "resolve")
    )
    if entry["kind"] == "comment":
        text = body or claim
    else:
        if where:  # the location goes inside the body's last sentence
            body = f"{body.removesuffix('.')} ({where})".strip()
        parts = [f"**{_sentence(claim)}**" if claim else "", _sentence(body)]
        if entry["kind"] != "strength":  # the fix is the last sentence, without a label
            parts += [_sentence(undermines), _sentence(resolve)]
        text = " ".join(part for part in parts if part)
    return text


def bullet(entry: dict) -> str:
    """The entry as it will read in the review, marked if the point began as the model's."""
    return ("[Claude] " if from_claude(entry) else "") + wording(entry)


def said_ok(said: str, turns: list[dict]) -> bool:
    """True if the quote is found word for word in something the reviewer sent."""
    def words(text: str) -> str:
        return " ".join(text.split())

    return any(words(said) in words(t["text"]) for t in turns if t["role"] == "reviewer")


# ---------------------------------------------------------------------------
# What the model is sent, and the record (pure functions over the state)
# ---------------------------------------------------------------------------


def index_text(entries: list[dict], ranked: bool) -> str:
    """The index as the model is shown it with every message."""
    if not entries:
        return "[Index]\n(empty)"
    lines = ["[Index]"]
    for kind in LETTERS.values():
        for e in entries:
            if e["kind"] != kind or e.get("dropped"):
                continue
            tags = [kind]
            if e.get("by_hand"):
                tags.append("reviewer's wording")
            if e.get("was"):
                tags.append("was " + ", ".join(e["was"]))
            lines.append(f"{e['id']} ({'; '.join(tags)}): {e.get('claim', '')}".rstrip())
            if _text(e.get("text")):  # the bullet as the reviewer wrote it: the parts no longer build it
                lines.append("  text: " + " ".join(e["text"].split()))
                continue
            lines += [f"  {p}: {e[p]}" for p in ("body", "where", "undermines", "resolve") if e.get(p)]
            if e.get("nowhere") and not e.get("where"):
                lines.append("  where: no single location")
    dropped = [e["id"] for e in entries if e.get("dropped")]
    if dropped:
        lines.append("Dropped: " + ", ".join(dropped))
    return "\n".join(lines + [RANKED if ranked else UNRANKED])


def model_message(turn: dict, state: dict) -> str:
    """What the model receives for a reviewer turn.

    A label with the reviewer's words exactly as sent, the index as it stands,
    and the step wanted next. It is built from the saved state alone, so a
    failed call can be sent again.
    """
    def named(stage: str) -> str:  # after the interview a change concerns the whole review
        return "review" if stage in ("draft", "final") else stage

    kind, text = turn["kind"], turn["text"]
    if kind == "brief":
        head = "[Brief] " + (text if text.strip() else "no corrections")
    else:
        if kind == "accept":  # settled as the index shows it; the summary is given as it stands
            text = state["summary"] if turn["section"] == "summary" else ""
        elif kind == "skip":
            text = ""
        head = f"[{LABELS[kind]} · {named(turn['section'])}]" + (f"\n{text}" if text.strip() else "")
        if kind == "change" and turn["section"] == "summary":  # hand edits included
            head += f"\n\n[Summary as it stands]\n{state['summary']}"
    step = {"answer": "outline", "change": "revise"}.get(kind, "ask")
    index = index_text(state["entries"], state["ranked"])
    return f"{head}\n\n{index}\n\n[Next: {step} · {named(state['stage'])}]"


def _turn_lines(turn: dict) -> list[str]:
    """The record's lines for one turn."""
    if turn["role"] == "reviewer":
        kind, text = turn["kind"], turn["text"]
        if kind == "brief":
            return ["", f"Corrections from the reviewer: {text}"] if text.strip() else []
        if kind == "answer":
            return ["Answer: " + (text if text.strip() else "(none: wording left to Claude)")]
        if kind == "change":
            return [f"Change requested: {text}"]
        return ["Accepted." if kind == "accept" else "Skipped."]
    f = turn["fields"]
    if turn["section"] == "brief":
        return [f["message"]]
    lines = [f"Heard as: {f['heard_as']}"] if f.get("heard_as") else []  # about the answer above
    if f.get("follow_up"):
        lines.append(f"Follow-up: {f['message']}".rstrip())
    if f.get("asks"):
        lines.append("Asked:")
        for n, ask in enumerate(f["asks"], 1):
            lines.append(f"{n}. " + (f"[{ask['id']}] " if ask.get("id") else "") + ask["question"])
            lines += [f"   {label}: {ask[key]}" for key, label in ASK_PARTS if ask.get(key)]
    elif f["kind"] != "outline" and f["message"] and not f.get("follow_up"):
        lines.append(f"Asked: {f['message']}")  # a question that came as plain text
    if f.get("plan"):
        lines.append("Plan:")
        for p in f["plan"]:
            because = f': "{p["because"]}"' if p.get("because") else ""
            lines.append(f"- {p['target']} {p.get('action', '')}".rstrip() + because)
    if f["kind"] == "outline":
        outlined = " ".join(s["text"] for s in f.get("sentences", [])) or ", ".join(
            e["id"] for e in f.get("entries", [])
        )
        lines.append(f"Outlined: {outlined or '(nothing changed)'}")
    return lines


def render_record(state: dict, paper: str) -> str:
    """The interview record as Markdown. The reviewer's words appear exactly as they were sent."""
    turns, entries = state["turns"], state["entries"]
    sections: list[tuple[str, list[str]]] = []
    for turn in turns:
        title = SECTION_TITLES[turn["section"]]
        if not sections or sections[-1][0] != title:
            sections.append((title, []))
        sections[-1][1].extend(_turn_lines(turn))
    out = [f"# Interview record: {paper}"]
    out += [f"## {title}\n\n" + "\n".join(lines) for title, lines in sections]

    accepted = any(t["section"] == "summary" and t.get("kind") == "accept" for t in turns)
    if accepted and state["summary"].strip():
        out.append("## Summary (approved by the reviewer)\n\n" + state["summary"])

    groups = []
    for kind, title in INDEX_TITLES.items():
        lines = []
        for e in entries:
            if e["kind"] == kind and not e.get("dropped"):
                lines.append(f"- {e['id']}: {bullet(e)}")
                if e.get("sources"):
                    lines.append("  Notes: " + ", ".join(e["sources"]))
                if e.get("said"):
                    lines.append(f'  Said: "{e["said"]}"')
        if lines:
            groups.append("\n".join([f"### {title}"] + lines))
    dropped = [f"- {e['id']}: {e.get('claim', '')}".rstrip() for e in entries if e.get("dropped")]
    if dropped:
        groups.append("\n".join(["### Dropped"] + dropped))
    if groups:
        out.append("## Index\n\n" + "\n".join(groups))
    return "\n\n".join(out) + "\n"


def parse_register(text: str) -> dict[str, dict]:
    """Bias register rows, from the Markdown tables.

    {"B7": {"title": …, "how": …, "signal": …, "question": …, "sources": [{"label": …, "url": …}]}}.
    The fifth column, the sources, is optional: entries are separated by semicolons, and one
    that is not a Markdown link has no "url".
    """
    register = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"B\d+", cells[0]):
            m = re.match(r"\*\*(.+?)\*\*\s*(.*)", cells[1])
            sources = []
            for part in cells[4].split(";") if len(cells) > 4 else []:
                link = LINK_RE.search(part)
                label = (link.group(1) if link else part).strip()
                if label:
                    sources.append({"label": label, **({"url": link.group(2)} if link else {})})
            register[cells[0]] = {
                "title": (m.group(1) if m else cells[1]).rstrip("."),
                "how": m.group(2) if m else "",
                "signal": cells[2],
                "question": cells[3].strip('"'),
                "sources": sources,
            }
    return register


def parse_check(raw: object) -> list[dict] | None:
    """The findings of a check, or None if the model answered in plain text."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, dict) or not isinstance(raw.get("findings"), list):
        return None
    findings = []
    for item in raw["findings"]:
        row = _row(item, FINDING_FIELDS)
        if "target" in row and "problem" in row:
            if _note_ids(item.get("sources")):
                row["sources"] = _note_ids(item["sources"])
            findings.append(row)
    return findings


def render_check(findings: list[dict]) -> str:
    """The check as Markdown, for its file."""
    if not findings:
        return "Nothing found: the review meets the checklist."
    lines = []
    for f in findings:
        lines.append(f"- **{f['target']}**: {f['problem']}")
        if f.get("suggestion"):
            basis = ", ".join(f.get("sources", []) + ([f["where"]] if f.get("where") else []))
            lines.append(f"  - Suggested{f' (from {basis})' if basis else ''}: {f['suggestion']}")
    return "\n".join(lines)


def new_state() -> dict:
    return {
        "version": 2, "stage": "new", "phase": None, "turns": [], "session_id": None, "annotations": "",
        "summary": "", "entries": [], "ranked": False, "check": "", "findings": [], "draft": "", "final": "",
    }


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------


class InterviewApp:
    def __init__(
        self,
        pdf_path: Path,
        output_dir: Path,
        venue: str = "arr",
        fast: dict | None = None,
        deep: dict | None = None,
        observations: bool = False,
    ):
        self.pdf_path = pdf_path
        self.venue = venue
        self.fast = fast or dict(FAST)  # the turns of the interview
        self.deep = deep or dict(DEEP)  # the brief and the check
        self.observations = observations  # whether the model may offer points of its own
        name = pdf_path.stem
        self.extracted_path = output_dir / "extracted" / f"{name}.md"
        reviews = output_dir / "reviews"
        self.session_path = reviews / f"{name}.session.json"
        self.answers_path = reviews / f"{name}.answers.md"
        self.draft_path = reviews / f"{name}.review-draft.md"
        self.review_text_path = reviews / f"{name}.review-text.md"
        self.trace_path = reviews / f"{name}.review-trace.md"
        self.check_path = reviews / f"{name}.review-check.md"
        self.final_path = reviews / f"{name}.review-final.md"
        self.usage_path = reviews / f"{name}.usage.jsonl"
        self.usage_lock = threading.Lock()
        self.busy = threading.Lock()  # one request at a time
        self.pdf_lock = threading.Lock()  # PyMuPDF is not thread-safe
        self.page_cache: dict[int, bytes] = {}
        self.state: dict = new_state()
        self.paper: dict = {}
        self.fingerprint = ""  # of the annotations as numbered now; set by prepare()

    @property
    def legacy(self) -> bool:
        """True for an interview saved before the section-based flow: shown, never changed."""
        return self.state.get("version") != 2

    # -- preparation ---------------------------------------------------------

    def prepare(self) -> None:
        """Extract the paper and build what the page needs to show it."""
        n_pages, n_highlights, n_notes = extract(self.pdf_path, self.extracted_path, full=True)
        document = load_document(self.pdf_path)
        sidecar = json.loads(
            self.extracted_path.with_suffix(".annotations.json").read_text(encoding="utf-8")
        )
        # Note IDs (A1, A2, …) follow position, so they are only stable while
        # the set of annotations and their places stay the same.
        numbering = [(a["id"], a["page"], a["bbox"]) for a in sidecar["annotations"]]
        self.fingerprint = hashlib.sha256(json.dumps(numbering).encode()).hexdigest()[:16]
        register_file = review_module.REVIEWING_DIR / "BIASES.md"
        register = parse_register(register_file.read_text(encoding="utf-8")) if register_file.exists() else {}
        self.paper = {
            "name": self.pdf_path.name,
            "pages": [{"width": w, "height": h} for w, h in document.page_sizes],
            "annotations": sidecar["annotations"],
            "front_matter": front_matter(document),
            "register": register,
            "score_reminders": [{"id": i, **register[i]} for i in SCORE_ENTRIES if i in register],
            "counts": {"pages": n_pages, "highlights": n_highlights, "notes": n_notes},
            **document_index(document),
        }

    def restore(self) -> bool:
        if not self.session_path.exists():
            return False
        state = json.loads(self.session_path.read_text(encoding="utf-8"))
        saved = state.get("annotations")
        if saved and self.fingerprint and saved != self.fingerprint:
            raise SystemExit(
                f"Error: the annotations in {self.pdf_path.name} changed after this interview "
                "started, so the note numbers (A1, A2, …) in the saved record no longer match "
                "the paper.\nRun again with --restart to begin a new interview (the old record "
                "is kept as a .bak file), or put the PDF back as it was."
            )
        self.state = state
        return True

    def save(self) -> None:
        drafted = self.state["stage"] == "final"
        if drafted:  # the draft follows every edit made after it, so it never shows an old wording
            review, trace = self.review_text(), self.trace()
            # A line of --- parts the review from what is for the reviewer only.
            self.state["draft"] = f"{review}\n\n---\n\n{trace}"
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        # Written to one side and moved into place, so a stop mid-write leaves the old file whole.
        tmp = self.session_path.with_name(self.session_path.name + ".tmp")
        tmp.write_text(json.dumps(self.state, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.session_path)
        self.answers_path.write_text(render_record(self.state, self.pdf_path.name), encoding="utf-8")
        if drafted:
            self.review_text_path.write_text(review + "\n", encoding="utf-8")
            self.trace_path.write_text(trace + "\n", encoding="utf-8")
            self.draft_path.write_text(self.state["draft"] + "\n", encoding="utf-8")

    def restart(self) -> None:
        """Start again. The previous session and record are kept once, as .bak files."""
        # Only a session with content is worth keeping: restarting twice must not
        # replace the backup with an empty one.
        on_disk = self.session_path.exists() and json.loads(
            self.session_path.read_text(encoding="utf-8")
        ).get("turns")
        if on_disk:
            for path in (self.session_path, self.answers_path):
                if path.exists():
                    path.replace(path.with_name(path.name + ".bak"))
        self.state = new_state()
        self.save()

    # -- the interview -------------------------------------------------------

    @staticmethod
    def _call(tier: dict, prompt: str, session_id: str | None, schema: dict | None):
        extra = {"effort": tier["effort"]} if tier.get("effort") else {}
        return ask_model(prompt, session_id, schema, tier.get("model"), **extra)

    def _model_turn(self, prompt: str, tier: dict, section: str) -> dict:
        """Ask the model for one turn of the interview. Returns its fields."""
        raw, session_id = self._call(tier, prompt, self.state["session_id"], REPLY_SCHEMA)
        fields = parse_reply(raw)
        self.state["session_id"] = session_id
        self._apply(fields)
        self.state["turns"].append({"role": "claude", "section": section, "fields": fields})
        return fields

    def _apply(self, fields: dict) -> None:
        """Put what the model proposed into the summary and the index."""
        state, entries = self.state, self.state["entries"]
        spoken = bool(state["turns"]) and state["turns"][-1].get("kind") in ("answer", "change")
        if fields.get("sentences") and state["stage"] == "summary":
            state["summary"] = " ".join(s["text"] for s in fields["sentences"])
        for proposal in fields.get("entries", []):
            entry = find_entry(entries, proposal["id"])
            if entry is None:
                # A new entry takes its kind from its letter. One without a usable ID belongs
                # to the open section (a comment where the section has no kind of its own).
                if ID_RE.fullmatch(proposal["id"]):
                    kind = LETTERS[proposal["id"][0]]
                else:
                    kind = SECTION_KIND.get(state["stage"], "comment")
                    proposal["id"] = next_id(entries, kind)
                # Switched off means off: the prompt asks for no points of the model's own, and
                # one that arrives anyway is not taken. (A session saved before the setting was
                # stored goes by the flag of this run.)
                if kind == "observation" and not state.get("observations", self.observations):
                    continue
                entry = {"id": proposal["id"], "kind": kind}
                entries.append(entry)
            parts = {k: proposal[k] for k in (*ENTRY_PARTS, "sources") if k in proposal}
            if _text(entry.get("text")):
                # The reviewer's own wording stands. Only a new text replaces it, never the
                # parts, and only in reply to something the reviewer said.
                if "text" not in parts or not spoken:
                    parts = {k: v for k, v in parts.items() if k in ("sources", "said")}
            else:
                parts.pop("text", None)  # the model writes parts; only the reviewer starts a text
            entry.update(parts)
            if "move" in proposal:
                move_entry(entries, entry, proposal["move"])
            if proposal.get("drop"):
                entry["dropped"] = True
        # An order given aloud rearranges the entries it names among themselves.
        chosen: list[dict] = []
        for entry_id in fields.get("order", []):
            entry = find_entry(entries, entry_id)
            if entry and entry not in chosen:
                chosen.append(entry)
        for slot, entry in zip(sorted(entries.index(e) for e in chosen), chosen):
            entries[slot] = entry
        if any(e["kind"] == "weakness" for e in chosen):
            state["ranked"] = True

    def start(self) -> None:
        if self.state["stage"] != "new":
            return
        paper_text = self.extracted_path.read_text(encoding="utf-8")
        prompt = load_interview_prompt(paper_text, self.venue, self.answers_path)
        addendum = APP_ADDENDUM.read_text(encoding="utf-8")
        prompt += "\n" + addendum.replace(OBSERVATIONS_PLACEHOLDER, OBSERVATIONS[self.observations])
        self.state["observations"] = self.observations  # kept with the session: it is set once, here
        self._model_turn(prompt, self.deep, "brief")  # the brief is where the paper gets read
        self.state.update(stage="brief", annotations=self.fingerprint)
        self.save()

    def reply(self, payload: dict) -> None:
        """One step of the interview: what the page sent, read by where the interview stands."""
        state = self.state
        stage, phase = state["stage"], state["phase"]
        action = payload.get("action") or ""
        text = payload.get("text") if isinstance(payload.get("text"), str) else ""
        if self.pending():
            raise Refused("Claude has not replied to your last message yet. Ask Claude again first.")
        if stage == "brief" and not action:
            kind = "brief"
        elif phase == "ask" and action in ("", "skip"):
            kind = "skip" if action else "answer"
        elif phase == "outline" and action == "accept":
            kind = "accept"
            self._gate(stage, force=payload.get("force") is True)
            if stage == "summary" and text.strip():
                state["summary"] = text  # the paragraph as the reviewer left it
        elif action == "change" and (phase in ("ask", "outline") or stage in ("draft", "final")):
            # During the questions a change concerns an entry the reviewer has opened.
            kind = "change"
            if not text.strip():
                raise Refused("Say what to change.")
            if stage == "summary" and _text(payload.get("summary")):
                state["summary"] = payload["summary"]  # the box as the reviewer left it
        else:
            raise Refused("That step is not open at this point of the interview.")
        if kind == "skip":
            # Candidates that were never written out would block the bias test and the draft.
            for e in state["entries"]:
                undecided = stage == "weaknesses" and e["kind"] == "observation"
                if undecided or (e["kind"] == SECTION_KIND.get(stage) and gaps(e)):
                    e["dropped"] = True
        state["turns"].append({"role": "reviewer", "section": stage, "kind": kind, "text": text})
        if kind in ("brief", "accept", "skip"):  # the section is done: on to the next
            state["stage"] = STAGES[STAGES.index(stage) + 1]
            state["phase"] = "ask" if state["stage"] in SECTIONS else None
        self.save()  # the reviewer's words are on disk before the model is asked
        self.ask_claude()

    def _gate(self, stage: str, force: bool = False) -> None:
        """Refuse to accept a section while an entry is without its location or fix.

        With `force` the reviewer accepts those as they are. An observation of the model's
        has to be decided either way.
        """
        entries = self.state["entries"]
        kinds = ("strength", "weakness") if stage == "bias" else (SECTION_KIND.get(stage),)
        problems = [] if force else gap_lines([e for e in entries if e["kind"] in kinds])
        if stage == "weaknesses":
            problems += [
                f"{e['id']} is still an observation: make it a weakness or a comment, or drop it"
                for e in entries
                if e["kind"] == "observation" and not e.get("dropped")
            ]
        if problems:
            raise Refused("; ".join(problems) + ".")

    def pending(self) -> bool:
        """True if the reviewer's last message is saved and the model still owes a reply to it."""
        turns = self.state["turns"]
        return (
            bool(turns)
            and turns[-1]["role"] == "reviewer"
            and (self.state["stage"] in SECTIONS or turns[-1].get("kind") == "change")
        )

    def ask_claude(self) -> None:
        """Get the model's reply to the reviewer's last message, if one is due.

        Also the retry after a failed or interrupted call.
        """
        if not self.pending():
            return
        turn = self.state["turns"][-1]
        fields = self._model_turn(model_message(turn, self.state), self.fast, self.state["stage"])
        if turn["kind"] == "answer" and fields["kind"] == "outline":
            self.state["phase"] = "outline"  # a follow-up question leaves the answer owed
        self.save()

    # -- hand edits ----------------------------------------------------------

    def edit_entry(self, payload: dict) -> None:
        """The reviewer's own change to one entry: reword, move, drop or restore, reorder."""
        entries = self.state["entries"]
        entry = find_entry(entries, payload.get("id"))
        changes = payload.get("set") if isinstance(payload.get("set"), dict) else {}
        move = payload.get("move")
        if entry is None:
            raise Refused(f"There is no entry {payload.get('id')}.")
        if move is not None and move not in KINDS:
            raise Refused(f"An entry cannot be moved to {move}.")
        edits = {k: v for k, v in changes.items() if k in ENTRY_PARTS and isinstance(v, str)}  # as typed
        if "text" in edits and not edits["text"].strip():
            entry.pop("text", None)  # an emptied text: the bullet is built from the parts again
            del edits["text"]
        if edits:
            entry.update(edits, by_hand=True)
        if "nowhere" in changes:
            entry["nowhere"] = changes["nowhere"] is True
        if move:
            move_entry(entries, entry, move)
        if "dropped" in payload:
            entry["dropped"] = payload["dropped"] is True
        if payload.get("shift") in (-1, 1):
            # Up or down among the entries of its kind that are still in the review.
            peers = [i for i, e in enumerate(entries) if e["kind"] == entry["kind"] and not e.get("dropped")]
            here = entries.index(entry)
            rank = peers.index(here) + payload["shift"] if here in peers else -1
            if 0 <= rank < len(peers):
                entries[here], entries[peers[rank]] = entries[peers[rank]], entries[here]
                if entry["kind"] == "weakness":
                    self.state["ranked"] = True
        self.save()

    def set_summary(self, text: object) -> None:
        if not isinstance(text, str):
            raise Refused("There is no summary text.")
        self.state["summary"] = text
        self.save()

    # -- check, draft, final -------------------------------------------------

    def _live(self, kind: str) -> list[dict]:
        return [e for e in self.state["entries"] if e["kind"] == kind and not e.get("dropped")]

    def review_text(self, ids: bool = False) -> str:
        """The review in the ARR form, from the summary and the index. `ids` labels each point."""
        def listed(entries: list[dict]) -> str:
            return "\n".join("* " + (f"[{e['id']}] " if ids else "") + bullet(e) for e in entries)

        parts = [
            f"# Review: {self.pdf_path.stem}",
            "## Paper Summary",
            self.state["summary"].strip() or "[Reviewer to add]",
            "## Summary Of Strengths",
            listed(self._live("strength")),
            "## Summary Of Weaknesses",
            listed(self._live("weakness")),
            "## Comments Suggestions And Typos",
            listed(self._live("comment")),
        ]
        return "\n\n".join(part for part in parts if part)

    def trace(self) -> str:
        """For the reviewer only: where each point of the draft comes from."""
        entries, turns = self.state["entries"], self.state["turns"]
        notes = {a["id"]: a.get("note") or a.get("text") for a in self.paper.get("annotations", [])}
        sourced = []
        for e in (e for kind in KINDS for e in self._live(kind)):
            was = f" (was {', '.join(e['was'])})" if e.get("was") else ""
            sourced.append(f"- **{e['id']}**{was}: {e.get('claim') or bullet(e)}")
            for n in e.get("sources", []):
                sourced.append(f'  - {n}: "{notes[n]}"' if notes.get(n) else f"  - {n}")
            if e.get("said"):
                found = "" if said_ok(e["said"], turns) else " (not found word for word in your answers)"
                sourced.append(f'  - You said: "{e["said"]}"{found}')
        sections = {
            "Where each point comes from": sourced,
            "From Claude": [
                f"- {e['id']}: {e.get('claim', '')}"
                + (" (still an observation: not in the review)" if e["kind"] == "observation" else "")
                for e in entries
                if from_claude(e) and not e.get("dropped")
            ],
            "Dropped": [f"- {e['id']}: {e.get('claim', '')}" for e in entries if e.get("dropped")],
            "Drafted with gaps": [f"- {line}" for line in gap_lines(entries)],
        }
        return "\n\n".join(
            f"**{title}**\n\n" + "\n".join(lines) for title, lines in sections.items() if lines
        )

    def _after_interview(self, what: str) -> None:
        if self.state["stage"] not in ("draft", "final"):
            raise Refused(f"{what} comes after the bias test.")

    def check(self) -> None:
        """Run the guidelines' checklist over the review as it stands. Scores are not asked for."""
        self._after_interview("The check")
        prompt = f"{CHECK_PROMPT}\n\n<review>\n{self.review_text(ids=True)}\n</review>"
        raw, self.state["session_id"] = self._call(self.deep, prompt, self.state["session_id"], CHECK_SCHEMA)
        findings = parse_check(raw)
        self.state["findings"] = findings or []
        self.state["check"] = str(raw) if findings is None else render_check(findings)
        self.save()
        self.check_path.write_text(self.state["check"].rstrip() + "\n", encoding="utf-8")

    def settle_finding(self, payload: dict) -> None:
        """Take a finding's suggestion as the text of its point, or set the finding aside."""
        self._after_interview("The check")
        findings = self.state.get("findings", [])
        n = payload.get("n")
        if type(n) is not int or not 0 <= n < len(findings):
            raise Refused("There is no such finding.")
        finding = findings[n]
        if payload.get("action") == "dismiss":
            finding["status"] = "dismissed"
        elif payload.get("action") != "use":
            raise Refused("A finding is used or dismissed.")
        elif not finding.get("suggestion"):
            raise Refused("This finding has no suggestion to take.")
        elif finding["target"].lower() == "summary":
            self.state["summary"] = finding["suggestion"]
            finding["status"] = "used"
        else:
            entry = find_entry(self.state["entries"], finding["target"].upper())
            if entry is None:
                raise Refused(f"There is no entry {finding['target']}.")
            entry.update(text=finding["suggestion"], by_hand=True)  # taken by the reviewer: it stands
            finding["status"] = "used"
        self.save()

    def draft(self, force: bool = False) -> None:
        """Assemble the review from the accepted summary and the index. No model is involved."""
        self._after_interview("The draft")
        problems = gap_lines(self.state["entries"])
        if problems and not force:
            raise Refused("; ".join(problems) + ".")
        self.state["stage"] = "final"
        self.save()  # writes the draft

    def finish(self, text: object) -> None:
        """Save the review as the reviewer submitted it, with a copy as an example for later reviews."""
        if self.state["stage"] != "final":
            raise Refused("Draft the review first.")
        if not isinstance(text, str) or not text.strip():
            raise Refused("There is no review text to save.")
        self.state["final"] = text
        self.save()
        # Named like the past reviews, so the drafting examples pick it up.
        name = f"ACL_ARR_{date.today():%Y_%B}_{self.pdf_path.stem}.md"
        example = review_module.REVIEWING_DIR / "my_reviews" / name
        example.parent.mkdir(parents=True, exist_ok=True)
        for path in (self.final_path, example):
            path.write_text(text, encoding="utf-8")

    # -- requests and views --------------------------------------------------

    def post(self, path: str, body: dict) -> tuple[int, dict]:
        """One POST from the page: (status, the view or an error)."""
        action = ACTIONS.get(path)
        if action is None:
            return 404, {"error": "Not found"}
        if not self.busy.acquire(blocking=False):
            return 409, {"error": "The previous request is still being worked on."}
        started, before, status, error = time.monotonic(), self._snapshot(), 200, ""
        try:
            if self.legacy:
                raise Refused(LEGACY)
            action(self, body)
        except Refused as exc:
            status, error = 400, str(exc)
        except Exception as exc:  # shown on the page; what was saved before the failure stays
            status, error = 500, str(exc) or "The request failed."
        finally:
            self.busy.release()
        took = round((time.monotonic() - started) * 1000)
        failed = {"error": error} if status != 200 else {}
        self.log("request", path=path, body=body, status=status, ms=took, **failed, **self._changes(before))
        return status, failed or self.view()

    # -- the usage log -------------------------------------------------------

    def log(self, event: str, **data) -> None:
        """Add one line to the usage log. A failure to write it never stops the interview."""
        line = {
            "t": datetime.now().isoformat(timespec="milliseconds"),
            "event": event,
            "stage": self.state.get("stage"),
            "phase": self.state.get("phase"),
            **data,
        }
        try:
            with self.usage_lock:
                self.usage_path.parent.mkdir(parents=True, exist_ok=True)
                with self.usage_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def page_events(self, body: dict) -> None:
        """What the reviewer did on the page that no request shows: opened, folded, followed."""
        for item in _list(body.get("events"))[:200]:
            if isinstance(item, dict) and isinstance(item.get("event"), str):
                rest = {k: v for k, v in item.items() if k not in ("event", "at")}
                self.log("page", what=item["event"], at=item.get("at"), **({"data": rest} if rest else {}))

    def _snapshot(self) -> dict:
        """The summary and the index as they stand, to tell afterwards what a request changed."""
        state = self.state
        return {
            "where": f"{state.get('stage')}/{state.get('phase')}",
            "summary": state.get("summary", ""),
            "entries": [(e, dict(e)) for e in state.get("entries", [])],
        }

    def _changes(self, before: dict) -> dict:
        """What a request changed: the step, the summary, and each entry part as [before, after]."""
        state, out = self.state, {}
        now = f"{state.get('stage')}/{state.get('phase')}"
        if now != before["where"]:
            out["moved"] = [before["where"], now]
        if state.get("summary", "") != before["summary"]:
            out["summary"] = [before["summary"], state.get("summary", "")]
        known = {id(entry): old for entry, old in before["entries"]}
        edits = []
        for e in state.get("entries", []):
            old = known.get(id(e))
            if old is None:
                edits.append({"id": e["id"], "new": dict(e)})
                continue
            diff = {k: [old.get(k), e.get(k)] for k in sorted(set(old) | set(e)) if old.get(k) != e.get(k)}
            if diff:
                edits.append({"id": e["id"], "set": diff})
        if edits:
            out["entries"] = edits
        was, order = [old["id"] for _, old in before["entries"]], [e["id"] for e in state.get("entries", [])]
        if was != order and sorted(was) == sorted(order):
            out["order"] = order
        return out

    def view(self) -> dict:
        state = new_state() | self.state  # a legacy session lacks the newer keys
        shown = ("stage", "phase", "turns", "summary", "ranked", "check", "findings", "draft", "final")
        session = {key: state[key] for key in shown}
        session["legacy"] = self.legacy
        session["entries"] = [
            e
            | {"bullet": bullet(e), "wording": wording(e), "gaps": gaps(e)}
            | ({"said_ok": said_ok(e["said"], state["turns"])} if e.get("said") else {})
            for e in state["entries"]
        ]
        return {
            "paper": self.paper,
            "session": session,
            "busy": self.busy.locked(),
            "pending": self.pending() and not self.busy.locked(),
            "files": {
                "answers": str(self.answers_path),
                "review_text": str(self.review_text_path),
                "trace": str(self.trace_path),
                "check": str(self.check_path),
                "final": str(self.final_path),
            },
        }

    def page_png(self, number: int) -> bytes:
        with self.pdf_lock:
            if number not in self.page_cache:
                doc = pymupdf.open(self.pdf_path)
                pix = doc[number - 1].get_pixmap(matrix=pymupdf.Matrix(PAGE_ZOOM, PAGE_ZOOM))
                self.page_cache[number] = pix.tobytes("png")
            return self.page_cache[number]


ACTIONS = {
    "/api/start": lambda app, body: app.start(),
    "/api/reply": InterviewApp.reply,
    "/api/entry": InterviewApp.edit_entry,
    "/api/summary": lambda app, body: app.set_summary(body.get("text")),
    "/api/retry": lambda app, body: app.ask_claude(),
    "/api/check": lambda app, body: app.check(),
    "/api/finding": InterviewApp.settle_finding,
    "/api/draft": lambda app, body: app.draft(force=body.get("force") is True),
    "/api/final": lambda app, body: app.finish(body.get("text")),
}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def is_local(host: str | None, origin: str | None, port: int) -> bool:
    """True if a request comes from this app's own page.

    A page on another site sends its own Origin; a site that points its domain
    name at this machine sends that name as Host. Both are refused, so no other
    site can read the paper or change the interview.
    """
    ours = {f"127.0.0.1:{port}", f"localhost:{port}"}
    return host in ours and (origin is None or origin.split("//")[-1] in ours)


def make_handler(app: InterviewApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # keep the terminal quiet
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

        def _refused(self) -> bool:
            port = self.server.server_address[1]
            if is_local(self.headers.get("Host"), self.headers.get("Origin"), port):
                return False
            self._json(403, {"error": "Forbidden"})
            return True

        def do_GET(self) -> None:
            if self._refused():
                return
            path = self.path.split("?")[0]
            page = re.fullmatch(r"/page/(\d+)\.png", path)
            if path == "/":
                self._send(200, (STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._json(200, app.view())
            elif page and 1 <= int(page.group(1)) <= len(app.paper["pages"]):
                self._send(200, app.page_png(int(page.group(1))), "image/png")
            else:
                self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            if self._refused():
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                body = None
            if isinstance(body, dict) and self.path == "/api/event":
                app.page_events(body)  # answered at once, even while the model is working
                self._json(200, {})
            elif isinstance(body, dict):
                self._json(*app.post(self.path, body))
            else:
                self._json(400, {"error": "Request body is not a JSON object"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Review interview in the browser.")
    parser.add_argument(
        "--paper", required=True, help="Path to the annotated PDF (e.g., reviews/foo.pdf)"
    )
    parser.add_argument("--restart", action="store_true", help="Discard the saved interview")
    parser.add_argument(
        "--observations",
        action="store_true",
        help="Let Claude offer up to three points of its own (off by default; set when an interview starts)",
    )
    parser.add_argument("--port", type=int, default=8765)
    efforts = ["default", "low", "medium", "high", "xhigh", "max"]
    parser.add_argument(
        "--model", default=FAST["model"], help=f"Model for the interview turns (default: {FAST['model']})"
    )
    parser.add_argument(
        "--effort", default=FAST["effort"], choices=efforts,
        help=f"Thinking effort for the interview turns; lower is faster (default: {FAST['effort']})",
    )
    parser.add_argument(
        "--deep-model", default=DEEP["model"],
        help=f"Model for the brief and the check (default: {DEEP['model']})",
    )
    parser.add_argument(
        "--deep-effort", default="default", choices=efforts,
        help="Thinking effort for the brief and the check (default: the model's own)",
    )
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the page")
    args = parser.parse_args()

    pdf_path = Path(args.paper)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    def tier(model: str, effort: str) -> dict:
        return {"model": model, "effort": None if effort == "default" else effort}

    app = InterviewApp(
        pdf_path,
        Path(args.output_dir),
        fast=tier(args.model, args.effort),
        deep=tier(args.deep_model, args.deep_effort),
        observations=args.observations,
    )
    print(f"Models: interview turns on {app.fast['model']} ({app.fast['effort'] or 'default'} effort); "
          f"brief and check on {app.deep['model']} ({app.deep['effort'] or 'default'} effort)")
    # Build the first prompt once now. A missing template or reviewing document then stops the
    # launch with its own message, instead of closing the connection when the interview starts.
    load_interview_prompt("", app.venue, app.answers_path)
    if not APP_ADDENDUM.exists():
        sys.exit(f"Error: {APP_ADDENDUM} not found. Run the command from the repository folder.")
    print(f"Reading {pdf_path.name} …")
    app.prepare()
    counts = app.paper["counts"]
    print(f"✓ {counts['pages']} pages, {counts['highlights']} highlights, {counts['notes']} notes")
    if args.restart:
        app.restart()
    elif app.restore():
        turns = len(app.state["turns"])
        print(LEGACY if app.legacy else f"✓ Continuing the saved interview ({turns} messages)")
    app.log("server", what="started", turns=len(app.state["turns"]), fast=app.fast, deep=app.deep)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"\nInterview page: {url}   (Ctrl+C to stop)")
    print(f"Record:         {app.answers_path}")
    print(f"Usage log:      {app.usage_path}")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. The interview is saved and continues next time.")


if __name__ == "__main__":
    main()
