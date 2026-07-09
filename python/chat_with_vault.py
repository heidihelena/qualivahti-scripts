#!/usr/bin/env python3
"""Chat with your vault — a local second-opinion reader over YOUR files.

Unlike a plugin that sees one open note, this chat searches the whole vault
(the index from build_vault_index.py) and answers with sources you can check.
It runs entirely on your computer.

It is deliberately a SECOND OPINION: by default it uses a different model than
the one that suggested your codes — a second opinion from the same reader is
not a second opinion. It reads, cites, and challenges. It does not decide.

Memory, two kinds:
- short-term: this conversation (forgotten when you leave)
- long-term:  _scripts/memory/assistant_memory.md — a small file the assistant
  distills notes into when you say /bye. It is YOURS: read it, edit it, prune it.

Every session is logged to 11_Audit_Trail/chat_sessions/ so your AI use is auditable.

Typical use:

    python3 _scripts/python/chat_with_vault.py
    python3 _scripts/python/chat_with_vault.py --ask "What did P02 say about scan results?"
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
from pathlib import Path

from qv_common import (DEFAULT_CHAT_LLM, DEFAULT_LLM, audit, die, find_vault,
                       ok, ollama_chat, ollama_embed, require_model, step,
                       today, warn)

EMBED_MODEL = "nomic-embed-text"
HISTORY_LIMIT = 12          # short-term memory: last N messages kept
MEMORY_TAIL_CHARS = 6000    # how much long-term memory is loaded each session

STARTER_MEMORY = """---
type: assistant-memory
---

# Assistant long-term memory

This file belongs to you, not to the model. The chat assistant reads it at the
start of every session and appends short notes when a session ends. Edit or
delete anything, any time — pruning it IS part of using it well.

Good things to keep here: how you like answers (short? with quotes?), standing
questions you are chasing, your vigilance list. Wrong things to keep here:
conclusions about the data — those belong in memos, decided by you.

## About this researcher / study
(write a few lines here yourself — the assistant will use them)

## Standing questions

## Session notes (assistant-appended)
"""


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def load_index(vault: Path) -> list[dict]:
    index_file = vault / "_scripts" / "index" / "vault_index.jsonl"
    if not index_file.exists():
        die("The vault index does not exist yet.",
            "First run: python3 _scripts/python/build_vault_index.py")
    return [json.loads(line) for line in
            index_file.read_text(encoding="utf-8").splitlines()]


def retrieve(index: list[dict], query: str, top: int) -> list[dict]:
    qvec = ollama_embed(EMBED_MODEL, ["search_query: " + query])[0]
    # Embedding similarity + a bonus for RARE literal terms (ids like "P02",
    # code names, unusual words). Common words get no bonus — they would just
    # reward every chunk about the same topic equally.
    terms = {w.strip(".,;:!?()[]\"'") for w in query.lower().split()}
    terms = {t for t in terms if len(t) > 2}
    lowered = [(c["text"] + " " + c["path"]).lower() for c in index]
    rare_cutoff = max(3, len(index) // 12)
    rare = {t for t in terms
            if 0 < sum(1 for txt in lowered if t in txt) <= rare_cutoff}

    def score(i: int) -> float:
        matched = sum(1 for t in rare if t in lowered[i])
        return cosine(qvec, index[i]["embedding"]) + 0.12 * min(matched, 2)

    order = sorted(range(len(index)), key=score, reverse=True)

    # Identifier guarantee: a term with a digit (P02, FG01, e003) names something
    # specific — the two best chunks containing it are always included, so
    # "what did P02 say about X" cannot come back without P02's own data.
    ids = {t for t in terms if any(ch.isdigit() for ch in t)}
    reserved: list[int] = []
    for t in sorted(ids):
        holders = [i for i in range(len(index)) if t in lowered[i]]
        # prefer primary data (transcripts, coding) over notes that mention the id
        holders.sort(key=lambda i: cosine(qvec, index[i]["embedding"])
                     + (0.06 if index[i]["path"][:2] in ("02", "03", "04") else 0),
                     reverse=True)
        reserved += [i for i in holders[:2] if i not in reserved]

    chosen = reserved[: max(2, top // 2)]
    chosen += [i for i in order if i not in chosen][: top - len(chosen)]
    return [index[i] for i in chosen]


def context_block(hits: list[dict]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"[{i}] {h['path']} § {h['heading']}\n{h['text']}")
    return "\n\n".join(parts)


def load_memory(vault: Path) -> tuple[Path, str]:
    mem_file = vault / "_scripts" / "memory" / "assistant_memory.md"
    if not mem_file.exists():
        mem_file.parent.mkdir(parents=True, exist_ok=True)
        mem_file.write_text(STARTER_MEMORY, encoding="utf-8")
    text = mem_file.read_text(encoding="utf-8")
    return mem_file, text[-MEMORY_TAIL_CHARS:]


def answer(model: str, system: str, memory: str, history: list[dict],
           question: str, hits: list[dict]) -> str:
    sys_full = (system
                + "\n\n# Long-term memory (researcher-owned; background, not data)\n"
                + memory)
    user = (f"Context pieces retrieved from the vault:\n\n{context_block(hits)}\n\n"
            f"Researcher's message: {question}\n\n"
            "Answer using ONLY the context pieces and the conversation so far. "
            "Cite pieces like [1], [2] after each claim. If the context does not "
            "contain the answer, say so plainly.")
    return ollama_chat(model, sys_full, user, fmt=None, history=history,
                       temperature=0.3)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ask", default=None, help="One question, one answer, no chat loop.")
    ap.add_argument("--model", default=DEFAULT_CHAT_LLM,
                    help=f"Chat model (default {DEFAULT_CHAT_LLM} — on purpose not the "
                         f"coding default {DEFAULT_LLM}; see --help text above).")
    ap.add_argument("--top", type=int, default=10, help="How many vault pieces to retrieve per question.")
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    vault = find_vault(args.vault)
    system = (vault / "_scripts" / "prompts" / "second_opinion_chat.md")
    if not system.exists():
        die("Prompt file is missing: _scripts/prompts/second_opinion_chat.md",
            "It ships with the vault. Restore it from your download or from git.")
    system = system.read_text(encoding="utf-8")

    index = load_index(vault)
    require_model(args.model)
    require_model(EMBED_MODEL)
    mem_file, memory = load_memory(vault)

    # ---- one-shot mode ----
    if args.ask:
        hits = retrieve(index, args.ask, args.top)
        reply = answer(args.model, system, memory, [], args.ask, hits)
        print(f"\n{reply}\n\nSources:")
        for i, h in enumerate(hits, 1):
            print(f"  [{i}] {h['path']} § {h['heading']}")
        return

    # ---- interactive chat ----
    print(f"\nSecond-opinion chat over your vault ({len(index)} indexed pieces).")
    print(f"Model: {args.model} (reader) + {EMBED_MODEL} (search). All local.")
    print("Commands: /sources (where the last answer came from), /remember <note>,")
    print("          /help, /bye (leave — the assistant saves 2-3 memory bullets)\n")

    history: list[dict] = []
    last_hits: list[dict] = []
    log_lines: list[str] = []
    exchanges = 0

    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            q = "/bye"
            print()
        if not q:
            continue

        if q == "/help":
            print("  /sources — list the vault pieces behind the last answer")
            print("  /remember <note> — save a note straight to long-term memory")
            print("  /bye — end; the assistant distills the session into memory")
            continue
        if q == "/sources":
            if not last_hits:
                print("  (no answer yet)")
            for i, h in enumerate(last_hits, 1):
                print(f"  [{i}] {h['path']} § {h['heading']}")
            continue
        if q.startswith("/remember"):
            note = q[len("/remember"):].strip()
            if not note:
                print("  Write the note after the command: /remember prefer short answers")
                continue
            with mem_file.open("a", encoding="utf-8") as fh:
                fh.write(f"- ({today()}, saved by researcher) {note}\n")
            ok("Saved to _scripts/memory/assistant_memory.md")
            continue
        if q in ("/bye", "/quit", "/exit"):
            break

        hits = retrieve(index, q, args.top)
        last_hits = hits
        reply = answer(args.model, system, memory, history, q, hits)
        print(f"\n{reply}\n")
        history += [{"role": "user", "content": q},
                    {"role": "assistant", "content": reply}]
        history = history[-HISTORY_LIMIT:]
        src = "; ".join(f"[{i}] {h['path']} § {h['heading']}" for i, h in enumerate(hits, 1))
        log_lines += [f"**you:** {q}", "", reply, "", f"*sources: {src}*", "", "---", ""]
        exchanges += 1

    # ---- session end: long-term memory + audit ----
    if exchanges >= 2:
        step("Distilling 2-3 memory bullets from this session...")
        summary = ollama_chat(
            args.model,
            "You write at most 3 short bullets for a researcher's assistant-memory file. "
            "Only durable things: preferences about how to answer, standing questions, "
            "things to watch for. NEVER conclusions about the data. Plain text bullets "
            "starting with '- '. Nothing else.",
            "The session:\n" + "\n".join(
                m["content"] if m["role"] == "user" else f"(assistant) {m['content'][:300]}"
                for m in history),
            fmt=None, temperature=0.2)
        bullets = [l for l in summary.splitlines() if l.strip().startswith("-")][:3]
        if bullets:
            with mem_file.open("a", encoding="utf-8") as fh:
                fh.write(f"\n### {today()} ({args.model})\n" + "\n".join(bullets) + "\n")
            print("Remembered:")
            for b in bullets:
                print(f"  {b}")
            print("(edit or delete any of this: _scripts/memory/assistant_memory.md)")

    if exchanges >= 1:
        log_dir = vault / "11_Audit_Trail" / "chat_sessions"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M")
        log_file = log_dir / f"chat_{stamp}.md"
        log_file.write_text(
            f"---\ntype: chat-session\ngenerated: true\nmodel: {args.model}\n"
            f"date: {today()}\nexchanges: {exchanges}\n---\n\n"
            f"# Chat session {stamp}\n\n" + "\n".join(log_lines), encoding="utf-8")
        audit(vault, "chat_with_vault.py", f"{exchanges} exchanges",
              f"{args.model} + {EMBED_MODEL}", f"chat_sessions/{log_file.name}")
        ok(f"Session logged: 11_Audit_Trail/chat_sessions/{log_file.name}")


if __name__ == "__main__":
    main()
