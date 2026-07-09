#!/usr/bin/env python3
"""Prepare a cleaned copy of a raw transcript, plus a cleaning log that records every change.

The script only does mechanical, auditable work:
- copies the raw transcript into 03_Cleaned_Transcripts/
- tidies whitespace
- applies YOUR replacement list (for example real name -> pseudonym), counting each change
- starts a cleaning log note where the replacements are already written down

The judgment work — listening, correcting, pseudonymizing — is yours.

Typical use:

    python3 _scripts/python/clean_transcript.py interview1
    python3 _scripts/python/clean_transcript.py interview1 --replacements my_names.csv

The replacements file is a small CSV with a header row: old,new,reason
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from qv_common import (audit, die, find_vault, next_steps, ok, read_frontmatter,
                       refuse_overwrite, step, today, warn)


def find_raw(vault: Path, name: str) -> Path:
    p = Path(name).expanduser()
    if p.exists():
        return p.resolve()
    for candidate in (vault / "02_Transcripts" / f"{name}_raw.md",
                      vault / "02_Transcripts" / f"{name}.md"):
        if candidate.exists():
            return candidate
    die(f"Could not find a transcript called '{name}' in 02_Transcripts/.",
        "Use the file name without '_raw.md' — for example: interview1")
    raise SystemExit  # unreachable


def load_replacements(path: str | None) -> list[dict]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        die(f"Replacements file not found: {p}",
            "Make a small CSV with a header row 'old,new,reason', one replacement per line.")
    with p.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if not (r.get("old") and r.get("new")):
            die("The replacements file needs columns named: old, new, reason",
                "First line of the file must be exactly: old,new,reason")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("transcript", help="Transcript name (e.g. interview1) or path.")
    ap.add_argument("--replacements", default=None, help="CSV file: old,new,reason")
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="Only show what would happen.")
    args = ap.parse_args()

    vault = find_vault(args.vault)
    raw = find_raw(vault, args.transcript)
    text = raw.read_text(encoding="utf-8", errors="replace")
    meta, body = read_frontmatter(text)
    tid = meta.get("transcript_id") or re.sub(r"_raw$", "", raw.stem)

    if meta.get("speakers_checked", "false").lower() != "true":
        warn("The raw transcript still says 'speakers_checked: false'. "
             "If you have not yet replaced the '?' marks with real speakers, do that first — "
             "coding needs to know who says what.")

    out = vault / "03_Cleaned_Transcripts" / f"{tid}_clean.md"
    log = vault / "03_Cleaned_Transcripts" / f"{tid} — cleaning log.md"
    refuse_overwrite(out, "Cleaned transcript")
    refuse_overwrite(log, "Cleaning log")

    replacements = load_replacements(args.replacements)

    if args.dry_run:
        step(f"Would create 03_Cleaned_Transcripts/{out.name} and {log.name}")
        step(f"Would apply {len(replacements)} replacements from your list.")
        ok("Dry run only. Nothing was changed.")
        return

    # Mechanical tidy-up: no words are changed.
    cleaned = "\n".join(line.rstrip() for line in body.splitlines())
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    applied: list[tuple[str, str, str, int]] = []
    for r in replacements:
        n = cleaned.count(r["old"])
        if n:
            cleaned = cleaned.replace(r["old"], r["new"])
        applied.append((r["old"], r["new"], r.get("reason", ""), n))
        if n == 0:
            warn(f"'{r['old']}' was not found in the transcript — check the spelling.")

    out.write_text(
        "---\n"
        "type: transcript\n"
        "stage: cleaned\n"
        f"transcript_id: {tid}\n"
        f"participant_id: {meta.get('participant_id', tid)}\n"
        f"cleaned_from: 02_Transcripts/{raw.name}\n"
        f"cleaning_log: \"[[{log.stem}]]\"\n"
        f"cleaning_started: {today()}\n"
        "cleaning_done: false\n"
        "---\n\n"
        f"{cleaned}\n",
        encoding="utf-8",
    )

    rep_rows = "\n".join(
        f"| (whole text) | {old} | {new} | {reason or 'replacement list'} — {n} times, by script |"
        for old, new, reason, n in applied
    ) or "| | | | |"
    log.write_text(
        "---\n"
        "type: cleaning-log\n"
        f"transcript_id: {tid}\n"
        f"source_file: 02_Transcripts/{raw.name}\n"
        f"cleaned_file: 03_Cleaned_Transcripts/{out.name}\n"
        "cleaner: \n"
        f"cleaning_date: {today()}\n"
        f"transcription_model: {meta.get('transcription_model', '')}\n"
        "status: in-progress\n"
        "---\n\n"
        f"# Cleaning log — {tid}\n\n"
        "## Changes made\n\n"
        "| Location (timestamp) | Original | Changed to | Reason |\n"
        "|---|---|---|---|\n"
        f"{rep_rows}\n\n"
        "Add one row for every change you make by hand. Every change is auditable.\n\n"
        "## Pseudonym key\n"
        "Stored **outside this vault**. Note here only *where* it is kept:\n\n"
        "## Deliberately NOT changed\n"
        "<!-- Dialect, hesitations, repetitions — note what you kept as-is and why. -->\n",
        encoding="utf-8",
    )

    ok(f"Wrote 03_Cleaned_Transcripts/{out.name}")
    ok(f"Wrote 03_Cleaned_Transcripts/{log.name}")
    audit(vault, "clean_transcript.py", raw.name, "(no model)",
          f"{out.name}; {log.name}; {len([a for a in applied if a[3]])} replacements applied")

    next_steps(
        "Open the cleaned transcript and the recording side by side.",
        "Fix what the machine got wrong: names, terms, speaker mix-ups. Pseudonymize.",
        "Write EVERY change you make into the cleaning log (one table row each).",
        "Do not tidy how people speak — hesitations and repairs are often data.",
        "When finished, set 'cleaning_done: true' and the log's 'status: done'.",
        f"Then run: python3 _scripts/python/suggest_codes_local_llm.py {tid}",
    )


if __name__ == "__main__":
    main()
