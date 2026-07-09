#!/usr/bin/env python3
"""Build the Evidence Map — a Canvas where every node is a live note, not a drawing.

What it draws, from YOUR reviewed coding and YOUR theme notes:
- one column per theme: the theme note itself (click to open), with a grounding
  card above it — codes, quotes, participants, negative cases, memos, signed or not
- under each theme: its code notes (live counts from export_obsidian_notes.py)
- negative cases attached in red, memos in cyan
- codes that belong to no theme yet, grouped honestly at the right

Grounding, not confidence: the map shows how much evidence sits under each
theme and whether anyone has looked for counter-evidence. It never scores
whether a theme is "right" — that is not a number.

Output: 08_Graph_View/Evidence Map (generated).canvas — a machine file,
overwritten on every run. Arranged a copy by hand? Rename it first.

Typical use (run export_obsidian_notes.py first so code notes exist):

    python3 _scripts/python/build_evidence_canvas.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qv_common import (audit, effective_code, find_vault, next_steps, ok,
                       read_frontmatter, read_reviewed, review_warnings, slug,
                       step, usable_rows, warn)


def parse_fm_list(value: str) -> list[str]:
    return [x.strip().strip('"').strip("'")
            for x in value.strip("[]").split(",") if x.strip()]


def collect_notes(vault: Path, folders: list[str], note_type: str) -> list[dict]:
    out = []
    for folder in folders:
        for f in sorted((vault / folder).glob("*.md")):
            meta, _ = read_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            if meta.get("type") == note_type:
                meta["_path"] = str(f.relative_to(vault))
                meta["_stem"] = f.stem
                out.append(meta)
    return out


class Canvas:
    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self._n = 0

    def _id(self) -> str:
        self._n += 1
        return f"qv{self._n:04d}"

    def file(self, path: str, x: int, y: int, w: int, h: int, color: str = "") -> str:
        nid = self._id()
        node = {"id": nid, "type": "file", "file": path, "x": x, "y": y,
                "width": w, "height": h}
        if color:
            node["color"] = color
        self.nodes.append(node)
        return nid

    def text(self, text: str, x: int, y: int, w: int, h: int, color: str = "") -> str:
        nid = self._id()
        node = {"id": nid, "type": "text", "text": text, "x": x, "y": y,
                "width": w, "height": h}
        if color:
            node["color"] = color
        self.nodes.append(node)
        return nid

    def group(self, label: str, x: int, y: int, w: int, h: int, color: str = "") -> str:
        nid = self._id()
        node = {"id": nid, "type": "group", "label": label, "x": x, "y": y,
                "width": w, "height": h}
        if color:
            node["color"] = color
        self.nodes.append(node)
        return nid

    def edge(self, a: str, b: str, color: str = "", label: str = "",
             from_side: str = "bottom", to_side: str = "top") -> None:
        e = {"id": self._id(), "fromNode": a, "fromSide": from_side,
             "toNode": b, "toSide": to_side}
        if color:
            e["color"] = color
        if label:
            e["label"] = label
        self.edges.append(e)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="Only show what would happen.")
    args = ap.parse_args()

    vault = find_vault(args.vault)
    rows, counts = read_reviewed(vault)
    review_warnings(counts)
    good = usable_rows(rows)

    # per-code stats from the reviewed coding
    code_stats: dict[str, dict] = {}
    for r in good:
        code = effective_code(r)
        if not code:
            continue
        s = code_stats.setdefault(code, {"excerpts": set(), "participants": set()})
        s["excerpts"].add(r.get("excerpt_id", ""))
        s["participants"].add(r.get("participant_id", "?"))

    themes = collect_notes(vault, ["07_Themes"], "theme")
    negcases = collect_notes(vault, ["06_Memos", "07_Themes"], "negative-case")
    if not themes:
        warn("No theme notes in 07_Themes yet — the map will show only ungrouped codes.")

    out_path = vault / "08_Graph_View" / "Evidence Map (generated).canvas"
    if args.dry_run:
        step(f"Would draw {len(themes)} themes, {len(code_stats)} codes, "
             f"{len(negcases)} negative cases -> {out_path.name}")
        ok("Dry run only. Nothing was changed.")
        return

    cv = Canvas()
    col_w, col_gap = 480, 200
    placed_codes: set[str] = set()

    header = ("# Evidence map\n"
              "Every node is a real note — click one to open it. Counts show "
              "**grounding, not confidence**: how much sits under a theme, and "
              "whether anyone has hunted counter-evidence.\n\n"
              "Machine file — regenerate any time: "
              "`python3 _scripts/python/build_evidence_canvas.py`")
    cv.text(header, 0, -560, 2 * (col_w + col_gap), 220)

    for i, t in enumerate(themes):
        x = i * (col_w + col_gap)
        t_codes = [c for c in parse_fm_list(t.get("codes", "")) if c]
        t_memos = parse_fm_list(t.get("memos", ""))
        t_negs = [n for n in negcases
                  if t.get("theme", "") in parse_fm_list(n.get("theme", ""))
                  or t.get("theme", "") == n.get("theme", "")]
        quote_ids: set[str] = set()
        participants: set[str] = set()
        for c in t_codes:
            if c in code_stats:
                quote_ids |= code_stats[c]["excerpts"]
                participants |= code_stats[c]["participants"]
        signed = "yes" if t.get("decided_by", "").strip() else "NOT SIGNED"
        neg_line = (f"{len(t_negs)} linked" if t_negs
                    else "none linked — searched?")
        stats = (f"## Grounding\n"
                 f"- codes: **{len(t_codes)}** · quotes: **{len(quote_ids)}** · "
                 f"participants: **{len(participants)}**\n"
                 f"- negative cases: **{neg_line}**\n"
                 f"- memos: **{len(t_memos)}** · status: **{t.get('status', '?')}** · "
                 f"signed: **{signed}**")
        stats_id = cv.text(stats, x, -300, col_w, 240, color="6")
        theme_id = cv.file(t["_path"], x, 0, col_w, 400, color="6")
        cv.edge(stats_id, theme_id)

        y = 480
        for c in t_codes:
            code_note = vault / "08_Graph_View" / "Codes" / f"{slug(c)}.md"
            if code_note.exists():
                cid = cv.file(str(code_note.relative_to(vault)), x, y, col_w, 200)
            else:
                st = code_stats.get(c)
                body = (f"**{c}**\n{len(st['excerpts'])} excerpts, "
                        f"{len(st['participants'])} participant(s)" if st else
                        f"**{c}**\n(not found in reviewed coding — check the "
                        f"spelling in the theme note)")
                cid = cv.text(body, x, y, col_w, 200)
            cv.edge(theme_id, cid)
            placed_codes.add(c)
            y += 240

        for n in t_negs:
            nid = cv.file(n["_path"], x, y, col_w, 240, color="1")
            cv.edge(nid, theme_id, color="1", label="complicates",
                    from_side="top", to_side="bottom")
            y += 280

        for m in t_memos:
            m_path = vault / "06_Memos" / f"{m}.md"
            if m_path.exists():
                mid = cv.file(str(m_path.relative_to(vault)), x, y, col_w, 200, color="5")
                cv.edge(mid, theme_id, color="5", from_side="top", to_side="bottom")
                y += 240

    orphans = sorted(set(code_stats) - placed_codes)
    if orphans:
        gx = len(themes) * (col_w + col_gap) + 100
        gh = 160 + 240 * len(orphans)
        cv.group("Codes not yet in any theme — honest leftovers, not failures",
                 gx - 40, -60, col_w + 80, gh, color="3")
        y = 0
        for c in orphans:
            code_note = vault / "08_Graph_View" / "Codes" / f"{slug(c)}.md"
            st = code_stats[c]
            if code_note.exists():
                cv.file(str(code_note.relative_to(vault)), gx, y, col_w, 200)
            else:
                cv.text(f"**{c}**\n{len(st['excerpts'])} excerpts, "
                        f"{len(st['participants'])} participant(s)", gx, y, col_w, 200)
            y += 240

    out_path.parent.mkdir(parents=True, exist_ok=True)
    replaced = out_path.exists()
    out_path.write_text(json.dumps({"nodes": cv.nodes, "edges": cv.edges},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    if replaced:
        warn("Old evidence map replaced (it is a machine file — rename hand-arranged copies).")
    ok(f"Wrote 08_Graph_View/{out_path.name} "
       f"({len(themes)} themes, {len(placed_codes)} placed codes, {len(orphans)} ungrouped).")
    audit(vault, "build_evidence_canvas.py",
          f"{len(good)} reviewed rows, {len(themes)} theme notes", "(no model)",
          out_path.name)

    next_steps(
        "Open the canvas in Obsidian (08_Graph_View) and double-click any node to read the real note.",
        "A theme with 'negative cases: none linked' is a to-do, not a clean bill.",
        "Re-run after coding sessions; run export_obsidian_notes.py first so code notes are fresh.",
    )


if __name__ == "__main__":
    main()
