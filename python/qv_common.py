"""Shared helpers for QualiVahti Local scripts.

The rule, enforced here in code:
- Scripts SUGGEST and PREPARE. They never overwrite a file a human may have edited.
- Every run is written to the audit trail.
- Everything runs on this computer. The only network address allowed is localhost (Ollama).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
import sys
from pathlib import Path

DEFAULT_LLM = "qwen3:14b"
FALLBACK_LLM = "hermes3:8b"
# The second-opinion chat deliberately defaults to a DIFFERENT model than the
# coding default: a second opinion from the same reader is not a second opinion.
DEFAULT_CHAT_LLM = "hermes3:8b"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://localhost:11434"  # local only — never a cloud address

# The data contract between Python and R. Do not change one side only.
SUGGESTED_FIELDS = [
    "excerpt_id", "transcript_id", "participant_id", "speaker", "timestamp",
    "excerpt", "suggested_code", "rationale", "model_confidence",
    "uncertainty_note", "model_name", "model_version", "run_date",
]
REVIEWED_FIELDS = SUGGESTED_FIELDS + [
    "review_status", "final_code", "reviewer", "review_date", "review_note",
]
REVIEW_STATUSES = ("suggested", "accepted", "edited", "rejected", "unclear")


# ---------------- talking to the user ----------------

def step(msg: str) -> None:
    print(f"-> {msg}")


def ok(msg: str) -> None:
    print(f"[done] {msg}")


def warn(msg: str) -> None:
    print(f"[note] {msg}")


def die(problem: str, fix: str | None = None) -> None:
    print(f"\n[stopped] {problem}")
    if fix:
        print(f"How to fix it: {fix}")
    sys.exit(1)


def next_steps(*lines: str) -> None:
    print("\nWhat to do next:")
    for i, line in enumerate(lines, 1):
        print(f"  {i}. {line}")


# ---------------- vault paths ----------------

def find_vault(override: str | None = None) -> Path:
    """The scripts live in <vault>/_scripts/python/, so the vault is two folders up."""
    if override:
        v = Path(override).expanduser().resolve()
        if not v.is_dir():
            die(f"The vault folder does not exist: {v}",
                "Check the --vault path for typing mistakes.")
        return v
    return Path(__file__).resolve().parents[2]


def today() -> str:
    return _dt.date.today().isoformat()


# ---------------- overwrite protection ----------------

def refuse_overwrite(path: Path, what: str) -> None:
    if path.exists():
        die(f"{what} already exists: {path}",
            "Scripts never overwrite files. If you want a fresh one, "
            "rename or move the old file first, then run this again.")


GENERATED_MARK = "generated: true"


def is_generated(path: Path) -> bool:
    """True if this file was made by a script (it says 'generated: true' near the top)."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return False
    return GENERATED_MARK in head


def write_generated(path: Path, text: str, what: str) -> None:
    """Overwrite is allowed ONLY for files a script made earlier (marked generated: true)."""
    if path.exists() and not is_generated(path):
        die(f"{what} exists and was not made by a script: {path}",
            "It may hold your own edits, so the script will not touch it. "
            "Rename it if you want the script to make a fresh one.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------- audit trail ----------------

_AUDIT_INTRO = """---
type: audit-trail-machine-log
generated: true
---

# Machine log — script runs

Scripts add one row here every time they run. Do not edit rows.
Your own decisions go in your Audit Trail note (see `_templates/Audit Trail Template.md`).

| Date | Script | Inputs | Model + version | Outputs |
|---|---|---|---|---|
"""


def audit(vault: Path, script: str, inputs: str, model: str, outputs: str) -> None:
    log = vault / "11_Audit_Trail" / "audit_log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(_AUDIT_INTRO, encoding="utf-8")
    clean = [str(x).replace("|", "/").replace("\n", " ") for x in (inputs, model, outputs)]
    with log.open("a", encoding="utf-8") as f:
        f.write(f"| {today()} | {script} | {clean[0]} | {clean[1]} | {clean[2]} |\n")
    ok("Audit trail updated (11_Audit_Trail/audit_log.md).")


# ---------------- transcripts ----------------

# A line that starts a speaker turn, e.g.:
#   [00:01:23] P01: text     or     **[00:01:23] Interviewer:** text     or     P01: text
_TURN = re.compile(
    r"^\s*\*{0,2}(?:\[(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\])?\s*\*{0,2}"
    r"(?P<sp>[^:\[\]/*][^:\[\]/]{0,38}?)\s*\*{0,2}:\s*(?P<tx>.+?)\s*$"
)


def read_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Very simple 'key: value' parsing."""
    meta: dict[str, str] = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"')
            return meta, parts[2]
    return meta, text


def parse_transcript(path: Path) -> tuple[dict, list[dict]]:
    """Return (frontmatter, turns). Each turn: {timestamp, speaker, text}."""
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = read_frontmatter(text)
    turns: list[dict] = []
    for line in body.splitlines():
        m = _TURN.match(line)
        if m:
            turns.append({
                "timestamp": m.group("ts") or "",
                "speaker": m.group("sp").strip(),
                "text": m.group("tx").strip(),
            })
        elif line.strip() and turns:
            # A plain line continues the previous speaker's turn.
            turns[-1]["text"] += " " + line.strip()
    return meta, turns


def transcript_id_from(path: Path, meta: dict) -> str:
    tid = meta.get("transcript_id", "")
    if tid:
        return tid
    return re.sub(r"_(raw|clean)$", "", path.stem)


def make_excerpts(turns: list[dict], transcript_id: str,
                  target_words: int = 110, max_words: int = 240) -> list[dict]:
    """Group consecutive turns into excerpts of roughly target_words words.

    An excerpt is a unit shown to the coding model and to the human reviewer.
    We never split in the middle of a turn unless the turn alone is longer
    than max_words.
    """
    excerpts: list[dict] = []
    bucket: list[dict] = []
    count = 0

    def flush() -> None:
        nonlocal bucket, count
        if not bucket:
            return
        speakers = []
        for t in bucket:
            if t["speaker"] not in speakers:
                speakers.append(t["speaker"])
        excerpts.append({
            "excerpt_id": f"{transcript_id}-e{len(excerpts) + 1:03d}",
            "transcript_id": transcript_id,
            "speaker": "+".join(speakers),
            "timestamp": bucket[0]["timestamp"],
            "text": "\n".join(f'{t["speaker"]}: {t["text"]}' for t in bucket),
        })
        bucket, count = [], 0

    for turn in turns:
        words = len(turn["text"].split())
        if words > max_words:
            flush()
            # Split a very long turn on sentence ends.
            pieces = re.split(r"(?<=[.!?])\s+", turn["text"])
            chunk: list[str] = []
            cw = 0
            for piece in pieces:
                chunk.append(piece)
                cw += len(piece.split())
                if cw >= target_words:
                    bucket.append({**turn, "text": " ".join(chunk)})
                    flush()
                    chunk, cw = [], 0
            if chunk:
                bucket.append({**turn, "text": " ".join(chunk)})
                count = cw
            continue
        bucket.append(turn)
        count += words
        if count >= target_words:
            flush()
    flush()
    return excerpts


# ---------------- Ollama (local LLM) ----------------

def _requests():
    try:
        import requests  # noqa: PLC0415
        return requests
    except ImportError:
        die("The Python package 'requests' is missing.",
            "In Terminal, run: pip3 install requests")


def ollama_tags() -> dict:
    requests = _requests()
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        die("Ollama is not answering on this computer.",
            "Open the Ollama app (or run 'ollama serve' in Terminal), then try again.")


def require_model(model: str) -> str:
    """Check the model exists locally. Return a short version id for the audit trail."""
    tags = ollama_tags()
    for m in tags.get("models", []):
        if m.get("name") == model or m.get("name") == f"{model}:latest":
            return m.get("digest", "")[:12]
    have = ", ".join(m.get("name", "?") for m in tags.get("models", [])) or "none"
    die(f"Ollama does not have the model '{model}'. Models on this computer: {have}",
        f"In Terminal, run: ollama pull {model}")
    return ""  # unreachable


def strip_think(text: str) -> str:
    """qwen3 may add <think>...</think> blocks. Remove them before parsing."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def ollama_chat(model: str, system: str, user: str, timeout: int = 600,
                fmt: str | None = "json", history: list[dict] | None = None,
                temperature: float = 0.2) -> str:
    requests = _requests()
    messages = [{"role": "system", "content": system}]
    messages += history or []
    messages.append({"role": "user", "content": user})
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature},
        "messages": messages,
    }
    if fmt:
        payload["format"] = fmt
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    if r.status_code == 400:
        # Older Ollama versions do not know the 'think' switch. Try without it.
        payload.pop("think", None)
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return strip_think(r.json().get("message", {}).get("content", ""))


def ollama_embed(model: str, texts: list[str], timeout: int = 300) -> list[list[float]]:
    """Embed a batch of texts with a local embedding model (e.g. nomic-embed-text)."""
    requests = _requests()
    r = requests.post(f"{OLLAMA_URL}/api/embed",
                      json={"model": model, "input": texts}, timeout=timeout)
    if r.status_code == 404:
        die(f"Ollama does not have the embedding model '{model}'.",
            f"In Terminal, run: ollama pull {model}   (small download, ~270 MB)")
    r.raise_for_status()
    return r.json().get("embeddings", [])


def json_from(text: str) -> dict | None:
    """Best effort: read a JSON object out of a model reply."""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            return None
    return None


# ---------------- reviewed coding (human-owned, read-only here) ----------------

def read_reviewed(vault: Path) -> tuple[list[dict], dict]:
    """Read every 04_Coding/reviewed_*.csv. Return (rows, counts by status)."""
    coding = vault / "04_Coding"
    files = sorted(coding.glob("reviewed_*.csv")) + sorted(coding.glob("DEMO_reviewed_*.csv"))
    if not files:
        die("No reviewed coding files found in 04_Coding/.",
            "First run suggest_codes_local_llm.py, then open the reviewed_*.csv file "
            "and set review_status on every row (accepted / edited / rejected / unclear).")
    rows: list[dict] = []
    counts: dict[str, int] = {}
    for f in files:
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                row["_file"] = f.name
                status = (row.get("review_status") or "suggested").strip().lower()
                row["review_status"] = status
                counts[status] = counts.get(status, 0) + 1
                rows.append(row)
    return rows, counts


def usable_rows(rows: list[dict]) -> list[dict]:
    """Only human-approved rows count: accepted or edited."""
    return [r for r in rows if r["review_status"] in ("accepted", "edited")]


def effective_code(row: dict) -> str:
    """The code that counts: the human's final_code if given, else the suggestion."""
    return (row.get("final_code") or "").strip() or (row.get("suggested_code") or "").strip()


def review_warnings(counts: dict) -> None:
    pending = counts.get("suggested", 0)
    unclear = counts.get("unclear", 0)
    if pending:
        warn(f"{pending} rows still have status 'suggested' — nobody has reviewed them yet. "
             "They are NOT included in any output.")
    if unclear:
        warn(f"{unclear} rows are marked 'unclear'. They are not included. "
             "Revisit them when you can.")


def slug(code: str) -> str:
    """A safe file name for a code."""
    s = re.sub(r"[^\w\s\-äöåÄÖÅ]", "", code, flags=re.UNICODE).strip()
    return re.sub(r"\s+", "-", s).lower() or "unnamed-code"


def read_prompt(vault: Path, name: str) -> str:
    p = vault / "_scripts" / "prompts" / name
    if not p.exists():
        die(f"Prompt file is missing: {p}",
            "It ships with the vault in _scripts/prompts/. Restore it from your download or from git.")
    return p.read_text(encoding="utf-8")
