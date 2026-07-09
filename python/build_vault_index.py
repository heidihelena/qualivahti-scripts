#!/usr/bin/env python3
"""Build a local search index of your vault, so you can chat with your files.

What it does:
- reads your notes (transcripts, review sheets, codebook, memos, themes, drafts)
  and your reviewed coding CSVs
- cuts them into small pieces and turns each piece into numbers ("embeddings")
  using a local embedding model (nomic-embed-text) via Ollama
- saves the index in _scripts/index/ — a file on YOUR computer, nothing leaves it

Run it again whenever your vault has grown; unchanged files are skipped.

Typical use:

    python3 _scripts/python/build_vault_index.py

Then chat:  python3 _scripts/python/chat_with_vault.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from qv_common import (DEFAULT_EMBED_MODEL, audit, die, find_vault, next_steps,
                       ok, ollama_embed, read_frontmatter, require_model, step,
                       warn)

INDEX_FOLDERS = ["02_Transcripts", "03_Cleaned_Transcripts", "04_Coding",
                 "05_Codebook", "06_Memos", "07_Themes", "08_Graph_View",
                 "09_Methods_Draft", "10_Results_Draft", "11_Audit_Trail"]
CHUNK_WORDS = 250
OVERLAP_WORDS = 40
BATCH = 32


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def split_words(text: str, heading: str) -> list[tuple[str, str]]:
    words = text.split()
    if len(words) <= CHUNK_WORDS:
        return [(heading, text)] if words else []
    chunks, start = [], 0
    while start < len(words):
        piece = " ".join(words[start:start + CHUNK_WORDS])
        chunks.append((heading, piece))
        start += CHUNK_WORDS - OVERLAP_WORDS
    return chunks


def chunk_markdown(path: Path, vault: Path) -> list[dict]:
    _, body = read_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    rel = str(path.relative_to(vault))
    chunks, heading, buf = [], path.stem, []

    def flush() -> None:
        text = "\n".join(buf).strip()
        for h, piece in split_words(text, heading):
            chunks.append({"path": rel, "heading": h, "text": piece})
        buf.clear()

    for line in body.splitlines():
        if re.match(r"^#{1,6}\s", line):
            flush()
            heading = line.lstrip("# ").strip() or heading
        else:
            buf.append(line)
    flush()
    return chunks


def chunk_reviewed_csv(path: Path, vault: Path) -> list[dict]:
    rel = str(path.relative_to(vault))
    by_excerpt: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            by_excerpt.setdefault(row.get("excerpt_id", "?"), []).append(row)
    chunks = []
    for eid, rows in by_excerpt.items():
        r0 = rows[0]
        codes = "; ".join(
            f"{(r.get('final_code') or r.get('suggested_code') or '?')} "
            f"[{r.get('review_status', '?')}]"
            + (f" — note: {r['review_note']}" if r.get("review_note") else "")
            for r in rows)
        text = (f"Excerpt {eid} ({r0.get('participant_id', '?')}, "
                f"{r0.get('timestamp', '')}): {r0.get('excerpt', '')}\n"
                f"Codes: {codes}")
        chunks.append({"path": rel, "heading": eid, "text": text})
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="Only show what would happen.")
    args = ap.parse_args()

    vault = find_vault(args.vault)
    index_dir = vault / "_scripts" / "index"
    index_file = index_dir / "vault_index.jsonl"
    manifest_file = index_dir / "index_manifest.json"

    files: list[Path] = []
    for folder in INDEX_FOLDERS:
        d = vault / folder
        if d.is_dir():
            files += sorted(d.rglob("*.md"))
    files += sorted((vault / "04_Coding").glob("reviewed_*.csv"))
    files = [f for f in files if f.name != "audit_log.md"]
    if not files:
        die("Found nothing to index.",
            "Index-worthy files live in the numbered folders (transcripts, memos, codebook...).")

    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    old_chunks: dict[str, list[dict]] = {}
    if index_file.exists():
        for line in index_file.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            old_chunks.setdefault(rec["path"], []).append(rec)

    todo, kept, new_manifest = [], [], {}
    for f in files:
        rel = str(f.relative_to(vault))
        h = file_hash(f)
        new_manifest[rel] = h
        if manifest.get(rel) == h and rel in old_chunks:
            kept += old_chunks[rel]
        else:
            todo.append(f)

    if args.dry_run:
        step(f"{len(files)} files total; {len(todo)} new or changed would be embedded, "
             f"{len(files) - len(todo)} unchanged would be kept.")
        ok("Dry run only. Nothing was changed.")
        return

    if not todo and index_file.exists():
        ok(f"Index is already up to date ({len(kept)} pieces from {len(files)} files).")
        return

    digest = require_model(args.embed_model)
    fresh: list[dict] = []
    for f in todo:
        chunks = (chunk_reviewed_csv(f, vault) if f.suffix == ".csv"
                  else chunk_markdown(f, vault))
        fresh += chunks
    step(f"Embedding {len(fresh)} pieces from {len(todo)} new/changed files "
         f"with {args.embed_model} (locally)...")

    for i in range(0, len(fresh), BATCH):
        batch = fresh[i:i + BATCH]
        vecs = ollama_embed(args.embed_model,
                            ["search_document: " + c["text"] for c in batch])
        if len(vecs) != len(batch):
            die("The embedding model returned the wrong number of results.",
                "Restart the Ollama app and run this again.")
        for c, v in zip(batch, vecs):
            c["embedding"] = v
        if len(fresh) > BATCH:
            print(f"  {min(i + BATCH, len(fresh))}/{len(fresh)}")

    all_chunks = kept + fresh
    index_dir.mkdir(parents=True, exist_ok=True)
    with index_file.open("w", encoding="utf-8") as fh:
        for c in all_chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    manifest_file.write_text(json.dumps(new_manifest, indent=1), encoding="utf-8")

    ok(f"Index ready: {len(all_chunks)} pieces from {len(files)} files "
       f"({len(fresh)} newly embedded, {len(kept)} kept).")
    audit(vault, "build_vault_index.py", f"{len(files)} files",
          f"{args.embed_model} ({digest})", f"_scripts/index/ ({len(all_chunks)} pieces)")

    next_steps(
        "Chat with your vault: python3 _scripts/python/chat_with_vault.py",
        "Re-run this script whenever the vault has grown — unchanged files are skipped.",
    )


if __name__ == "__main__":
    main()
