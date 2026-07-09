#!/usr/bin/env python3
"""Turn YOUR reviewed coding into linked Obsidian notes, so the graph view shows your codes.

What it makes:
- 08_Graph_View/Codes/<code>.md — one note per code, linking to its transcripts (machine files, regenerated each run)
- 08_Graph_View/Code Map.md — an index of all codes
- 05_Codebook/Code — <code>.md — a codebook DRAFT for any code that has none yet
  (made once, then never touched again: codebook entries are yours)

Only rows you marked 'accepted' or 'edited' are used.

Typical use:

    python3 _scripts/python/export_obsidian_notes.py
"""

from __future__ import annotations

import argparse

from qv_common import (audit, effective_code, find_vault, next_steps, ok,
                       read_reviewed, review_warnings, slug, step, today,
                       usable_rows, warn, write_generated)


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
        warn("No accepted or edited rows yet — nothing to export.")
        return

    by_code: dict[str, list[dict]] = {}
    for r in good:
        code = effective_code(r)
        if code:
            by_code.setdefault(code, []).append(r)

    codes_dir = vault / "08_Graph_View" / "Codes"
    map_path = vault / "08_Graph_View" / "Code Map.md"
    codebook_dir = vault / "05_Codebook"

    # A codebook entry is found by its `code:` frontmatter, not its file name —
    # so renamed or DEMO_-prefixed entries are recognized and never duplicated.
    entry_by_code: dict[str, str] = {}
    for entry in codebook_dir.glob("*.md"):
        head = entry.read_text(encoding="utf-8", errors="replace")[:400]
        for line in head.splitlines():
            if line.startswith("code:"):
                entry_by_code.setdefault(line.split(":", 1)[1].strip(), entry.stem)
                break

    if args.dry_run:
        step(f"Would write {len(by_code)} code notes, refresh the Code Map, "
             "and draft missing codebook entries.")
        ok("Dry run only. Nothing was changed.")
        return

    new_entries = 0
    for code in sorted(by_code):
        quotes = by_code[code]
        transcripts = sorted({q.get("transcript_id", "?") for q in quotes})
        participants = sorted({q.get("participant_id", "?") for q in quotes})
        entry_name = entry_by_code.get(code, f"Code — {code}")

        note = [
            "---",
            "type: code-node",
            f"code: {code}",
            "generated: true",
            f"updated: {today()}",
            f"n_excerpts: {len(quotes)}",
            f"n_participants: {len(participants)}",
            "---",
            "",
            f"# {code}",
            "",
            f"Codebook entry: [[{entry_name}]]",
            f"Applied to {len(quotes)} excerpt(s) across {len(participants)} participant(s).",
            "",
            "## Appears in",
        ]
        note += [f"- [[{tid}_clean|{tid}]]" for tid in transcripts]
        note += ["", "## Excerpts"]
        for q in quotes:
            short = q.get("excerpt", "").replace("\n", " ")
            if len(short) > 140:
                short = short[:140] + "…"
            note.append(f"- `{q.get('excerpt_id', '')}` ({q.get('participant_id', '?')}): {short}")
        note.append("")
        write_generated(codes_dir / f"{slug(code)}.md", "\n".join(note), f"Code note for '{code}'")

        entry_path = codebook_dir / f"{entry_name}.md"
        if code not in entry_by_code and not entry_path.exists():
            anchor = quotes[0]
            entry_path.parent.mkdir(parents=True, exist_ok=True)
            entry_path.write_text(
                "---\n"
                "type: codebook-entry\n"
                f"code: {code}\n"
                "status: candidate\n"
                f"created: {today()}\n"
                f"last_revised: {today()}\n"
                "merged_into:\n"
                "---\n\n"
                f"# Code — {code}\n\n"
                "> Draft made by a script from your reviewed coding. From now on this file is yours —\n"
                "> scripts will never touch it again. Fill the definition to make the code usable\n"
                "> by someone other than you, on a day other than today.\n\n"
                "## Definition\n\n\n"
                "## Use when (inclusion)\n\n\n"
                "## Do NOT use when (exclusion)\n\n\n"
                "## Anchor example\n"
                f"> {anchor.get('excerpt', '').strip()}\n"
                f"> — {anchor.get('participant_id', '?')} ({anchor.get('excerpt_id', '')})\n\n"
                "## Boundary example\n\n\n"
                "## Revision history\n"
                "| Date | Change | Reason |\n"
                "|---|---|---|\n"
                f"| {today()} | drafted from reviewed coding | first appearance |\n",
                encoding="utf-8",
            )
            new_entries += 1

    map_note = [
        "---",
        "type: code-map",
        "generated: true",
        f"updated: {today()}",
        "---",
        "",
        "# Code map",
        "",
        "One line per code in your reviewed coding (accepted or edited rows only).",
        "Open Obsidian's graph view and filter with `path:08_Graph_View` to see the network.",
        "",
        "| Code | Excerpts | Participants | Codebook |",
        "|---|---|---|---|",
    ]
    for code in sorted(by_code):
        quotes = by_code[code]
        participants = {q.get("participant_id", "?") for q in quotes}
        map_note.append(f"| [[{slug(code)}\\|{code}]] | {len(quotes)} | {len(participants)} "
                        f"| [[Code — {code}]] |")
    map_note += ["", "Counts describe how often a code was applied. **Frequency is not importance.**", ""]
    write_generated(map_path, "\n".join(map_note), "Code Map")

    ok(f"Wrote {len(by_code)} code notes in 08_Graph_View/Codes/ and refreshed the Code Map.")
    if new_entries:
        ok(f"Drafted {new_entries} new codebook entr{'y' if new_entries == 1 else 'ies'} in 05_Codebook/ — they are yours now.")
    audit(vault, "export_obsidian_notes.py", f"{len(good)} reviewed rows", "(no model)",
          f"{len(by_code)} code notes; Code Map; {new_entries} codebook drafts")

    next_steps(
        "In Obsidian, open the graph view and filter: path:08_Graph_View",
        "Open the Code Map note for the table version.",
        "Fill in the drafted codebook entries in 05_Codebook/ — definition, inclusion, exclusion.",
        "Re-run this script any time; code notes refresh, your codebook entries are never touched.",
    )


if __name__ == "__main__":
    main()
