"""Browser page for the review interview: questions on the left, annotated paper on the right.

Usage:
    uv run interview --paper reviews/foo.pdf
    uv run interview --paper reviews/foo.pdf --restart     (discard the saved interview)

Runs the process in reviewing/INTERVIEW.md. The model is the installed `claude`
command-line tool, used without tools; this server keeps the record, so every
answer is stored exactly as it was sent.

Writes, under outputs/reviews/:
    foo.session.json        conversation state (reloading the page continues it)
    foo.answers.md          the interview record
    foo.review-draft.md     the model's whole drafting output
    foo.review-text.md      the review alone, ready to paste into the form
    foo.review-trace.md     for you only: changes from the notes, Claude's
                            additions, open items, source trace
    foo.review-check.md     the check of the draft against your guidelines
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymupdf

from src import review as review_module
from src.extract import document_index, extract, front_matter, load_document
from src.review import has_answers, load_interview_prompt, load_review_prompt

STATIC_DIR = Path(__file__).parent / "interview_static"
APP_ADDENDUM = Path("prompts/templates/interview_app.md")
MODEL_CWD = Path.home() / ".cache" / "debrief" / "interview"
MODEL_TIMEOUT_S = 900
PAGE_ZOOM = 2.0

SYSTEM_PROMPT = (
    "You are Claude, helping a researcher write a peer review. "
    "Follow the instructions given in the conversation. You have no tools in this session."
)

# Which model does which step. Reading the paper against the notes, drafting and
# checking need real analysis and happen once each, so they get the strongest
# model. Question turns follow a fixed format and are waited on five to eight
# times, so they get a faster setting. Measured on one real question turn:
# Fable at default effort 97 s, Opus at low effort 36 s, with the same number of
# points, register entries and verifiable figures in the result.
OBSERVATIONS_PLACEHOLDER = "<observations setting>"
OBSERVATIONS = {
    False: (
        "**Observations of your own are switched off for this session.** The reviewer dropped all of them "
        "last time. Do not offer points that his notes did not raise, and do not use the "
        "`observation` item type. If you saw something he would plainly want to know, such as a "
        "note that the paper contradicts, that belongs in the facts you give under his own point."
    ),
    True: (
        "**Observations of your own are switched on for this session.** In question 3, offer at "
        "most three points that his notes did not raise, each one or two sentences with its "
        "location, as items of type `observation`. They are labelled as yours and he accepts or "
        "drops each."
    ),
}

DEEP = {"model": "claude-fable-5-2", "effort": None}
FAST = {"model": "claude-opus-5-5", "effort": "low"}

KINDS = ("brief", "question", "summary", "end")
ROUNDS = {1: "The idea", 2: "Soundness", 3: "Gaps", 4: "Triage", 5: "Strengths", 6: "Deciders"}
# What the reviewer can decide about an item the model puts to him, by item type.
ITEM_CHOICES = {
    "point": ("weakness", "comment", "dropped"),
    "observation": ("accepted", "dropped"),
    "strength": ("strength", "dropped"),
}
MAX_EXCHANGES = 8  # questions plus follow-ups; the reviewer asked for five dense questions

REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "message": {"type": "string"},
        "round": {"type": "integer"},
        "title": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
        "register": {"type": "string"},
        "follow_up": {"type": "boolean"},
        "summary_question": {"type": "boolean"},
        "heard_as": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "type": {"type": "string"},
                    "register": {"type": "string"},
                },
                "required": ["id", "text"],
            },
        },
    },
    "required": ["kind", "message"],
}


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


def parse_reply(raw: object) -> dict:
    """Normalise a model reply into the fields the app relies on.

    Anything malformed degrades to a plain question, so the conversation can
    always continue.
    """
    fields: dict = {}
    if isinstance(raw, dict):
        fields = dict(raw)
    elif isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            fields = loaded if isinstance(loaded, dict) else {"message": raw}
        except json.JSONDecodeError:
            fields = {"message": raw}
    message = fields.get("message")
    out: dict = {
        "kind": fields.get("kind") if fields.get("kind") in KINDS else "question",
        "message": message.strip() if isinstance(message, str) else "",
    }
    rnd = fields.get("round")
    if isinstance(rnd, int) and rnd in ROUNDS:
        out["round"] = rnd
    for key in ("title", "register", "heard_as"):
        if isinstance(fields.get(key), str) and fields[key].strip():
            out[key] = fields[key].strip()
    sources = fields.get("sources")
    if isinstance(sources, list):
        out["sources"] = [s for s in sources if isinstance(s, str) and re.fullmatch(r"A\d+", s)]
    for key in ("follow_up", "summary_question"):
        if fields.get(key) is True:
            out[key] = True
    items = fields.get("items")
    if isinstance(items, list):
        out["items"] = []
        for i in items:
            if isinstance(i, dict) and i.get("id") and i.get("text"):
                item = {k: str(i[k]) for k in ("id", "text", "register") if i.get(k)}
                item["type"] = i.get("type") if i.get("type") in ITEM_CHOICES else "point"
                out["items"].append(item)
    return out


# ---------------------------------------------------------------------------
# Conversation bookkeeping (pure functions over the list of turns)
# ---------------------------------------------------------------------------


def question_number(turns: list[dict]) -> int:
    """Number of the question currently open (follow-ups share their question's number)."""
    return sum(
        1
        for t in turns
        if t["role"] == "claude" and t["fields"]["kind"] == "question" and not t["fields"].get("follow_up")
    )


def last_claude(turns: list[dict]) -> dict | None:
    return next((t["fields"] for t in reversed(turns) if t["role"] == "claude"), None)


def build_user_turn(turns: list[dict], payload: dict) -> dict:
    """Turn what the page sent into a stored turn, according to what was asked."""
    text = payload.get("text") or ""
    action = payload.get("action") or ""
    asked = last_claude(turns) or {"kind": "question"}
    turn: dict = {"role": "reviewer", "text": text}
    if action == "wrap_up":
        turn["kind"] = "wrap_up"
    elif asked["kind"] == "brief":
        turn["kind"] = "brief"
    elif asked["kind"] == "summary":
        turn["kind"] = "summary_accept" if action == "summary_accept" else "summary_change"
    else:
        turn["kind"] = "answer"
        turn["q"] = question_number(turns)
        turn["exchange"] = 1 + sum(1 for t in turns if t["role"] == "reviewer" and t["kind"] == "answer")
        allowed = {i["id"]: ITEM_CHOICES[i["type"]] for i in asked.get("items") or []}
        decisions = {
            k: v for k, v in (payload.get("decisions") or {}).items() if v in allowed.get(k, ())
        }
        if decisions:
            turn["decisions"] = decisions
        if action in ("skip", "you_decide"):
            turn["action"] = action
    return turn


def format_for_model(turn: dict) -> str:
    """The labelled message the model receives for a stored turn. The text is not altered."""
    kind, text = turn["kind"], turn.get("text", "")
    if kind == "wrap_up":
        return "[Wrap up]" + (f"\n{text}" if text.strip() else "")
    if kind == "brief":
        return "[Brief] " + (text if text.strip() else "no corrections")
    if kind == "summary_accept":
        return f"[Summary accepted]\n{text}"
    if kind == "summary_change":
        return f"[Summary change requested]\n{text}"
    used = turn.get("exchange", 0)
    label = f"[Answer to Q{turn.get('q', '?')} · exchange {used} of {MAX_EXCHANGES}]"
    if used >= MAX_EXCHANGES:
        label += " (the budget is used up: reply with kind end)"
    if turn.get("action") == "skip":
        return f"{label} (skipped)"
    if turn.get("action") == "you_decide":
        label += " (you decide the wording)"
    lines = [label]
    if turn.get("decisions"):
        lines.append("(decisions: " + "; ".join(f"{k} {v}" for k, v in turn["decisions"].items()) + ")")
    if text.strip() or len(lines) == 1:
        lines.append(text)
    return "\n".join(lines)


def render_record(turns: list[dict], paper: str) -> str:
    """The interview record as Markdown. Answers appear exactly as they were sent."""
    out = [f"# Interview record: {paper}"]
    entry: list[str] = []
    summary = ""
    points: dict[str, dict] = {}  # every item put to the reviewer, with his latest decision

    def close_entry() -> None:
        nonlocal entry
        if entry:
            out.append("\n".join(entry))
        entry = []

    n = 0
    for turn in turns:
        if turn["role"] == "claude":
            f = turn["fields"]
            if f.get("heard_as") and entry:
                entry.append(f"Heard as: {f['heard_as']}")
            if f["kind"] == "brief":
                out.append("## Brief\n\n" + f["message"])
            elif f["kind"] == "question":
                if f.get("follow_up") and entry:
                    entry.append(f"Follow-up: {f['message']}")
                else:
                    close_entry()
                    n += 1
                    entry = [f"## Q{n} — {f.get('title') or 'Question'}"]
                    if f.get("round"):
                        entry.append(f"Round: {f['round']} {ROUNDS[f['round']]}")
                    entry.append("Sources: " + (", ".join(f.get("sources") or []) or "none"))
                    entry.append(f"Question: {f['message']}")
                items = f.get("items") or []
                registers = sorted({r for r in [f.get("register")] + [i.get("register") for i in items] if r})
                if registers:
                    entry.append("Register: " + ", ".join(registers))
                if items:
                    entry.append("Points put to the reviewer:")
                for item in items:
                    known = points.setdefault(item["id"], {"decision": ""})
                    known.update(text=item["text"], type=item["type"])
                    entry.append(f"- {item['id']} ({item['type']}): {item['text']}")
            else:
                close_entry()
            continue

        kind, text = turn["kind"], turn.get("text", "")
        if kind == "brief" and text.strip():
            out.append(f"Corrections from the reviewer: {text}")
        elif kind == "answer":
            if turn.get("action") == "skip":
                entry.append("Answer: (skipped)")
            elif turn.get("action") == "you_decide":
                entry.append("Answer: (you decide the wording)" + (f" {text}" if text.strip() else ""))
            else:
                entry.append(f"Answer: {text}")
            if turn.get("decisions"):
                entry.append("Decisions: " + "; ".join(f"{k} {v}" for k, v in turn["decisions"].items()))
                for item_id, decision in turn["decisions"].items():
                    points.setdefault(item_id, {"text": "", "type": "point"})["decision"] = decision
        elif kind == "summary_accept":
            summary = text
        elif kind == "wrap_up":
            close_entry()
            out.append("(The reviewer wrapped up the interview here.)" + (f" {text}" if text.strip() else ""))
    close_entry()

    if summary:
        out.append("## Summary (approved by the reviewer)\n\n" + summary)
    if points:
        listed = [
            f"- {item_id} ({p.get('decision') or 'undecided'}; put as {p['type']}): {p['text']}"
            for item_id, p in points.items()
        ]
        out.append("## Points as decided by the reviewer\n\n" + "\n".join(listed))
    return "\n\n".join(out) + "\n"


def split_draft(text: str) -> tuple[str, str]:
    """Split the drafting output into (the review, the part for the reviewer only).

    The drafting prompt puts a line containing only --- between the two.
    """
    parts = re.split(r"^\s*---+\s*$", text, maxsplit=1, flags=re.MULTILINE)
    review = parts[0].strip()
    notes = parts[1].strip() if len(parts) > 1 else ""
    return review, notes


def parse_register(text: str) -> dict[str, dict[str, str]]:
    """Bias register rows: {"B7": {"title": …, "question": …}} from the Markdown tables."""
    register = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"B\d+", cells[0]):
            m = re.match(r"\*\*(.+?)\*\*", cells[1])
            register[cells[0]] = {
                "title": (m.group(1) if m else cells[1]).rstrip("."),
                "question": cells[3].strip('"'),
            }
    return register


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
        self.fast = fast or dict(FAST)  # question turns and the summary
        self.deep = deep or dict(DEEP)  # brief, draft, check
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
        self.busy = threading.Lock()  # one model call at a time
        self.pdf_lock = threading.Lock()  # PyMuPDF is not thread-safe
        self.page_cache: dict[int, bytes] = {}
        self.state: dict = {"stage": "new", "turns": [], "session_id": None}
        self.paper: dict = {}
        self.fingerprint = ""  # of the annotations as numbered now; set by prepare()

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
        self.paper = {
            "name": self.pdf_path.name,
            "pages": [{"width": w, "height": h} for w, h in document.page_sizes],
            "annotations": sidecar["annotations"],
            "front_matter": front_matter(document),
            "register": parse_register(register_file.read_text(encoding="utf-8"))
            if register_file.exists()
            else {},
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
        self.write_draft_files()  # drafts made before the files were split
        return True

    def save(self) -> None:
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        # Written to one side and moved into place, so a stop mid-write leaves the old file whole.
        tmp = self.session_path.with_name(self.session_path.name + ".tmp")
        tmp.write_text(json.dumps(self.state, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.session_path)
        self.answers_path.write_text(self.record(), encoding="utf-8")

    def record(self) -> str:
        return render_record(self.state["turns"], self.pdf_path.name)

    # -- conversation --------------------------------------------------------

    @staticmethod
    def _call(tier: dict, prompt: str, session_id: str | None, schema: dict | None):
        extra = {"effort": tier["effort"]} if tier.get("effort") else {}
        return ask_model(prompt, session_id, schema, tier.get("model"), **extra)

    def _model_turn(self, prompt: str, tier: dict | None = None) -> None:
        raw, session_id = self._call(
            tier or self.fast, prompt, self.state.get("session_id"), REPLY_SCHEMA
        )
        fields = parse_reply(raw)
        self.state["session_id"] = session_id
        self.state["turns"].append({"role": "claude", "fields": fields})
        self.state["stage"] = "ended" if fields["kind"] == "end" else "interview"

    def start(self) -> None:
        if self.state["turns"]:
            return
        paper_text = self.extracted_path.read_text(encoding="utf-8")
        prompt = load_interview_prompt(paper_text, self.venue, self.answers_path)
        addendum = APP_ADDENDUM.read_text(encoding="utf-8")
        self.state["annotations"] = self.fingerprint
        prompt += "\n" + addendum.replace(OBSERVATIONS_PLACEHOLDER, OBSERVATIONS[self.observations])
        self._model_turn(prompt, self.deep)  # the brief is where the paper gets read
        self.save()

    def reply(self, payload: dict) -> None:
        turn = build_user_turn(self.state["turns"], payload)
        self.state["turns"].append(turn)
        self.save()  # the answer is on disk before the model is asked
        self._model_turn(format_for_model(turn))
        self.save()

    def pending(self) -> bool:
        """True if the last answer is saved but the model has not replied to it."""
        turns = self.state["turns"]
        return bool(turns) and turns[-1]["role"] == "reviewer"

    def retry(self) -> None:
        """Ask the model again about an answer it never replied to (failed or interrupted call)."""
        if self.pending():
            self._model_turn(format_for_model(self.state["turns"][-1]))
            self.save()

    def draft(self) -> None:
        record = self.record()
        if not has_answers(record):
            raise RuntimeError("There are no answers yet to draft from.")
        paper_text = self.extracted_path.read_text(encoding="utf-8")
        prompt = load_review_prompt(paper_text, self.venue, record)
        text, session_id = self._call(self.deep, prompt, None, None)
        self.state.update(draft=str(text), draft_session_id=session_id, stage="drafted")
        self.state.pop("check", None)
        self.write_draft_files()
        self.save()

    def write_draft_files(self) -> None:
        """Save the draft whole, and as its two parts: the review and the notes for the reviewer."""
        draft = self.state.get("draft", "")
        if not draft:
            return
        review, notes = split_draft(draft)
        self.draft_path.parent.mkdir(parents=True, exist_ok=True)
        self.draft_path.write_text(draft + "\n", encoding="utf-8")
        self.review_text_path.write_text(review + "\n", encoding="utf-8")
        self.trace_path.write_text(notes + "\n", encoding="utf-8")

    def check(self) -> None:
        """Run the reviewer's own checklist over the draft. Scores are his and are not asked for."""
        if not self.state.get("draft_session_id"):
            raise RuntimeError("Draft the review before checking it.")
        prompt = (
            "Check the draft you just wrote against the reviewer's guidelines: go through the checklist "
            "in section 7 item by item, and the bias checks in section 6 for each weakness. Say "
            "what is not met and where. The reviewer sets his scores himself in the review form, so "
            "leave the items about scores aside and do not suggest any. Keep it short, as a list."
        )
        text, _ = self._call(self.deep, prompt, self.state["draft_session_id"], None)
        self.state["check"] = str(text)
        self.check_path.write_text(str(text) + "\n", encoding="utf-8")
        self.save()

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
        self.state = {"stage": "new", "turns": [], "session_id": None}
        self.save()

    # -- views ---------------------------------------------------------------

    def view(self) -> dict:
        return {
            "paper": self.paper,
            "session": {
                "stage": self.state["stage"],
                "turns": self.state["turns"],
                "draft": self.state.get("draft", ""),
                "check": self.state.get("check", ""),
            },
            "busy": self.busy.locked(),
            "pending": self.pending() and not self.busy.locked(),
            "files": {
                "answers": str(self.answers_path),
                "draft": str(self.draft_path),
                "review_text": str(self.review_text_path),
                "trace": str(self.trace_path),
                "check": str(self.check_path),
            },
        }

    def page_png(self, number: int) -> bytes:
        with self.pdf_lock:
            if number not in self.page_cache:
                doc = pymupdf.open(self.pdf_path)
                pix = doc[number - 1].get_pixmap(matrix=pymupdf.Matrix(PAGE_ZOOM, PAGE_ZOOM))
                self.page_cache[number] = pix.tobytes("png")
            return self.page_cache[number]


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
    actions = {
        "/api/start": lambda body: app.start(),
        "/api/reply": lambda body: app.reply(body),
        "/api/retry": lambda body: app.retry(),
        "/api/draft": lambda body: app.draft(),
        "/api/check": lambda body: app.check(),
        "/api/restart": lambda body: app.restart(),
    }

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
            elif path == "/api/record":
                self._send(200, app.record().encode("utf-8"), "text/plain; charset=utf-8")
            elif page and 1 <= int(page.group(1)) <= len(app.paper["pages"]):
                self._send(200, app.page_png(int(page.group(1))), "image/png")
            else:
                self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            if self._refused():
                return
            action = actions.get(self.path)
            if action is None:
                self._json(404, {"error": "Not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "Request body is not JSON"})
                return
            if not app.busy.acquire(blocking=False):
                self._json(409, {"error": "The model is still answering the previous message."})
                return
            try:
                action(body)
                self._json(200, app.view() | {"busy": False})
            except Exception as exc:  # shown on the page; the session is unchanged
                self._json(500, {"error": str(exc)})
            finally:
                app.busy.release()

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
        "--model", default=FAST["model"], help=f"Model for the question turns (default: {FAST['model']})"
    )
    parser.add_argument(
        "--effort", default=FAST["effort"], choices=efforts,
        help=f"Thinking effort for the question turns; lower is faster (default: {FAST['effort']})",
    )
    parser.add_argument(
        "--deep-model", default=DEEP["model"],
        help=f"Model for the brief, the draft and the check (default: {DEEP['model']})",
    )
    parser.add_argument(
        "--deep-effort", default="default", choices=efforts,
        help="Thinking effort for the brief, the draft and the check (default: the model's own)",
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
    print(f"Models: questions on {app.fast['model']} ({app.fast['effort'] or 'default'} effort); "
          f"brief, draft and check on {app.deep['model']} ({app.deep['effort'] or 'default'} effort)")
    print(f"Reading {pdf_path.name} …")
    app.prepare()
    counts = app.paper["counts"]
    print(f"✓ {counts['pages']} pages, {counts['highlights']} highlights, {counts['notes']} notes")
    if args.restart:
        app.restart()
    elif app.restore():
        print(f"✓ Continuing the saved interview ({len(app.state['turns'])} messages)")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"\nInterview page: {url}   (Ctrl+C to stop)")
    print(f"Record:         {app.answers_path}")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. The interview is saved and continues next time.")


if __name__ == "__main__":
    main()
