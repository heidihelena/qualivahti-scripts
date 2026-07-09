#!/usr/bin/env python3
"""Ask a local AI model to SUGGEST first-cycle codes for a cleaned transcript.

What this script does:
- splits the cleaned transcript into short excerpts
- asks your local Ollama model for up to 3 code suggestions per excerpt,
  each with a rationale, a confidence number, and a note on uncertainty
- saves the suggestions to 04_Coding/suggested_<id>.csv (machine file)
- starts 04_Coding/reviewed_<id>.csv for you — your review file
- writes a readable review sheet you can open in Obsidian

What it will NEVER do: touch a reviewed file that already exists. Your review is yours.

Remember: the model's confidence is a self-report. The model agreeing with you
is not evidence a code is right. You review every row.

Typical use:

    python3 _scripts/python/suggest_codes_local_llm.py interview1
    python3 _scripts/python/suggest_codes_local_llm.py --all
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from qv_common import (DEFAULT_LLM, REVIEWED_FIELDS, SUGGESTED_FIELDS, audit,
                       die, find_vault, json_from, make_excerpts, next_steps,
                       ok, ollama_chat, parse_transcript, read_prompt,
                       refuse_overwrite, require_model, step, today,
                       transcript_id_from, warn, write_generated)

PROMPT_FILE = "suggest_first_cycle_codes.md"


def find_cleaned(vault: Path, names: list[str], take_all: bool) -> list[Path]:
    folder = vault / "03_Cleaned_Transcripts"
    if take_all:
        files = sorted(folder.glob("*_clean.md"))
        if not files:
            die("No cleaned transcripts found in 03_Cleaned_Transcripts/.",
                "Run clean_transcript.py first.")
        return files
    out = []
    for name in names:
        p = Path(name).expanduser()
        if p.exists():
            out.append(p.resolve())
            continue
        for candidate in (folder / f"{name}_clean.md", folder / f"{name}.md"):
            if candidate.exists():
                out.append(candidate)
                break
        else:
            die(f"Could not find a cleaned transcript called '{name}'.",
                "Use the name without '_clean.md' — for example: interview1. "
                "Or run with --all to take every cleaned transcript.")
    return out


def ask_model(model: str, system: str, excerpt: dict, max_codes: int) -> dict | None:
    user = (
        f"Excerpt id: {excerpt['excerpt_id']}\n"
        f"Speaker(s): {excerpt['speaker']}\n"
        f"Excerpt:\n<<<\n{excerpt['text']}\n>>>\n\n"
        f"Suggest 1 to {max_codes} first-cycle codes for this excerpt. "
        "Reply with JSON only, exactly this shape:\n"
        '{"codes": [{"code": "short-label", '
        '"rationale": "why — quote the words that triggered it", '
        '"confidence": 0.0, '
        '"uncertainty": "what makes you unsure, or what a human must judge"}]}'
    )
    reply = ollama_chat(model, system, user)
    data = json_from(reply)
    if data is None or "codes" not in data or not isinstance(data["codes"], list):
        retry = user + "\n\nYour last reply could not be read as JSON. Send ONLY the JSON object."
        data = json_from(ollama_chat(model, system, retry))
    if data is None or not isinstance(data.get("codes"), list):
        return None
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("transcripts", nargs="*", help="Cleaned transcript name(s), e.g. interview1")
    ap.add_argument("--all", action="store_true", help="Take every cleaned transcript that has no suggestions yet.")
    ap.add_argument("--model", default=DEFAULT_LLM, help=f"Ollama model (default: {DEFAULT_LLM})")
    ap.add_argument("--max-codes", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="Only the first N excerpts (for a quick test).")
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="Only show what would happen.")
    args = ap.parse_args()

    if not args.transcripts and not args.all:
        die("Tell me which transcript to code, or use --all.",
            "Example: python3 _scripts/python/suggest_codes_local_llm.py interview1")

    vault = find_vault(args.vault)
    files = find_cleaned(vault, args.transcripts, args.all)
    system = read_prompt(vault, PROMPT_FILE)

    for path in files:
        meta, turns = parse_transcript(path)
        tid = transcript_id_from(path, meta)
        pid = meta.get("participant_id", tid)
        sug_path = vault / "04_Coding" / f"suggested_{tid}.csv"
        rev_path = vault / "04_Coding" / f"reviewed_{tid}.csv"
        sheet_path = vault / "04_Coding" / f"{tid} — code review sheet.md"

        if args.all and sug_path.exists():
            warn(f"Skipping {tid} — suggestions already exist ({sug_path.name}).")
            continue
        refuse_overwrite(sug_path, "Suggestions file")

        if meta.get("cleaning_done", "false").lower() != "true":
            warn(f"{tid}: the transcript does not say 'cleaning_done: true' yet. "
                 "Suggestions on an uncleaned transcript can chase transcription errors.")

        if not turns:
            die(f"No speaker turns found in {path.name}.",
                "Lines must look like:  [00:01:23] P01: what was said "
                "(speaker name, colon, text). Check the transcript format.")

        excerpts = make_excerpts(turns, tid)
        if args.limit:
            excerpts = excerpts[: args.limit]

        if args.dry_run:
            step(f"{tid}: would send {len(excerpts)} excerpts to '{args.model}' "
                 f"and write {sug_path.name} + {rev_path.name} + a review sheet.")
            continue

        digest = require_model(args.model)
        model_label = f"{args.model} ({digest})" if digest else args.model
        step(f"{tid}: {len(excerpts)} excerpts to code with {args.model}. "
             "This is local and can be slow — progress prints per excerpt.")

        rows: list[dict] = []
        for i, ex in enumerate(excerpts, 1):
            data = ask_model(args.model, system, ex, args.max_codes)
            base = {
                "excerpt_id": ex["excerpt_id"],
                "transcript_id": tid,
                "participant_id": pid,
                "speaker": ex["speaker"],
                "timestamp": ex["timestamp"],
                "excerpt": ex["text"],
                "model_name": args.model,
                "model_version": digest,
                "run_date": today(),
            }
            if data is None:
                rows.append({**base,
                             "suggested_code": "(model reply unreadable)",
                             "rationale": "The model did not return usable JSON for this excerpt.",
                             "model_confidence": "",
                             "uncertainty_note": "Code this excerpt yourself."})
                warn(f"  excerpt {i}/{len(excerpts)}: model reply unreadable — marked for you.")
                continue
            codes = data["codes"][: args.max_codes] or [{}]
            for c in codes:
                rows.append({**base,
                             "suggested_code": str(c.get("code", "")).strip() or "(no suggestion)",
                             "rationale": str(c.get("rationale", "")).strip(),
                             "model_confidence": c.get("confidence", ""),
                             "uncertainty_note": str(c.get("uncertainty", "")).strip()})
            labels = ", ".join(str(c.get("code", "?")) for c in codes)
            print(f"  excerpt {i}/{len(excerpts)}: {labels}")

        with sug_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=SUGGESTED_FIELDS)
            w.writeheader()
            w.writerows(rows)
        ok(f"Wrote {sug_path.name} ({len(rows)} suggestions, machine file — do not edit).")

        if rev_path.exists():
            warn(f"{rev_path.name} already exists — left completely untouched. Your review is yours.")
        else:
            with rev_path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=REVIEWED_FIELDS)
                w.writeheader()
                for r in rows:
                    w.writerow({**r, "review_status": "suggested", "final_code": "",
                                "reviewer": "", "review_date": "", "review_note": ""})
            ok(f"Wrote {rev_path.name} — THIS is your file. Scripts will never change it again.")

        sheet = [
            "---",
            "type: code-review-sheet",
            f"transcript_id: {tid}",
            "generated: true",
            f"created: {today()}",
            f"model: {model_label}",
            "---",
            "",
            f"# Code review sheet — {tid}",
            "",
            f"Suggestions from **{model_label}** on {today()}. "
            "The model suggests; you decide.",
            "",
            f"Do your actual review in `04_Coding/{rev_path.name}`: set `review_status` on every row to "
            "`accepted`, `edited` (then fill `final_code`), `rejected`, or `unclear`, and put your name in `reviewer`.",
            "",
            "Confidence numbers below are the model's self-report — not evidence the code is right.",
            "",
        ]
        current = None
        for r in rows:
            if r["excerpt_id"] != current:
                current = r["excerpt_id"]
                ts = f" [{r['timestamp']}]" if r["timestamp"] else ""
                sheet += [f"## {r['excerpt_id']}{ts} — {r['speaker']}", "",
                          "> " + r["excerpt"].replace("\n", "\n> "), ""]
            conf = f" (self-reported confidence {r['model_confidence']})" if r["model_confidence"] != "" else ""
            sheet.append(f"- **{r['suggested_code']}**{conf} — {r['rationale']}")
            if r["uncertainty_note"]:
                sheet.append(f"    - uncertainty: {r['uncertainty_note']}")
        sheet.append("")
        write_generated(sheet_path, "\n".join(sheet), "Review sheet")
        ok(f"Wrote {sheet_path.name} (readable version, for Obsidian).")

        audit(vault, "suggest_codes_local_llm.py", path.name, model_label,
              f"{sug_path.name}; {rev_path.name}; {sheet_path.name}")

    next_steps(
        "Open the code review sheet in Obsidian and read the suggestions against the transcript.",
        "Open reviewed_<id>.csv (Excel, Numbers, or LibreOffice) and give EVERY row a review_status: "
        "accepted / edited / rejected / unclear.",
        "For 'edited' rows, write your better label in final_code. Add your name in reviewer.",
        "New codes that will recur deserve a codebook entry (template in _templates/).",
        "Then run: python3 _scripts/python/extract_quotes.py",
    )


if __name__ == "__main__":
    main()
