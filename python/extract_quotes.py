#!/usr/bin/env python3
"""Build the quote evidence table from YOUR reviewed coding.

Only rows you marked 'accepted' or 'edited' are used. Rows still waiting for
review, and rows you rejected or marked unclear, never appear in any output.

Output (in 12_Exports/):
- quote_evidence_table.csv — one row per quote, grouped by code
- quote_evidence_table.md  — readable version for Obsidian

Typical use:

    python3 _scripts/python/extract_quotes.py
"""

from __future__ import annotations

import argparse
import csv

from qv_common import (audit, effective_code, find_vault, next_steps, ok,
                       read_reviewed, review_warnings, step, today,
                       usable_rows, warn)

OUT_FIELDS = ["code", "excerpt_id", "transcript_id", "participant_id", "speaker",
              "timestamp", "quote", "review_status", "reviewer"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="Only show what would happen.")
    args = ap.parse_args()

    vault = find_vault(args.vault)
    rows, counts = read_reviewed(vault)
    review_warnings(counts)
    good = usable_rows(rows)
    if not good:
        warn("No rows are marked 'accepted' or 'edited' yet, so there is nothing to export.")
        next_steps("Open your reviewed_*.csv files in 04_Coding/ and review the rows first.")
        return

    out_csv = vault / "12_Exports" / "quote_evidence_table.csv"
    out_md = vault / "12_Exports" / "quote_evidence_table.md"

    if args.dry_run:
        step(f"Would export {len(good)} quotes to {out_csv.name} and {out_md.name}.")
        ok("Dry run only. Nothing was changed.")
        return

    by_code: dict[str, list[dict]] = {}
    for r in good:
        by_code.setdefault(effective_code(r), []).append(r)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    replaced = out_csv.exists() or out_md.exists()
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        for code in sorted(by_code):
            for r in by_code[code]:
                w.writerow({
                    "code": code,
                    "excerpt_id": r.get("excerpt_id", ""),
                    "transcript_id": r.get("transcript_id", ""),
                    "participant_id": r.get("participant_id", ""),
                    "speaker": r.get("speaker", ""),
                    "timestamp": r.get("timestamp", ""),
                    "quote": r.get("excerpt", ""),
                    "review_status": r.get("review_status", ""),
                    "reviewer": r.get("reviewer", ""),
                })

    md = [
        "---",
        "type: export",
        "generated: true",
        f"created: {today()}",
        "---",
        "",
        "# Quote evidence table",
        "",
        "Generated file — edits here will be lost on the next export.",
        "Only human-reviewed rows (accepted or edited) are included.",
        "",
    ]
    for code in sorted(by_code):
        quotes = by_code[code]
        participants = sorted({q.get("participant_id", "?") for q in quotes})
        md.append(f"## {code}")
        md.append(f"*{len(quotes)} quotes, from {len(participants)} participant(s): "
                  f"{', '.join(participants)}*")
        md.append("")
        for q in quotes:
            ts = f" [{q['timestamp']}]" if q.get("timestamp") else ""
            md.append("> " + q.get("excerpt", "").strip().replace("\n", "\n> "))
            md.append(f"> — {q.get('participant_id', '?')}{ts} ({q.get('excerpt_id', '')})")
            md.append("")
    md.append("---")
    md.append("**Frequency is not importance.** A code with many quotes is common, "
              "not necessarily meaningful; a code with one quote can matter most. "
              "Importance is argued in your analysis, not counted here.")
    md.append("")
    out_md.write_text("\n".join(md), encoding="utf-8")

    if replaced:
        warn("Old export replaced (exports are machine files and safe to regenerate).")
    ok(f"Wrote 12_Exports/{out_csv.name} ({len(good)} quotes, {len(by_code)} codes).")
    ok(f"Wrote 12_Exports/{out_md.name}")
    audit(vault, "extract_quotes.py",
          f"{counts.get('accepted', 0)} accepted + {counts.get('edited', 0)} edited rows",
          "(no model)", f"{out_csv.name}; {out_md.name}")

    next_steps(
        "Open 12_Exports/quote_evidence_table.md in Obsidian and read it per code.",
        "Weak or crowded codes are codebook work: split, merge, or sharpen definitions.",
        "For tables and matrices, run the R scripts in _scripts/r/ (see the how-to note).",
    )


if __name__ == "__main__":
    main()
