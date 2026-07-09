#!/usr/bin/env python3
"""Build the code co-occurrence network from YOUR reviewed coding.

Two codes "co-occur" when they are applied to the same excerpt, or to excerpts
close together in the same transcript (within --window steps, default 2).
Co-occurrence shows which codes travel together in the talk. It does not show
cause, and it does not show importance.

Output (in 12_Exports/):
- code_cooccurrence_edges.csv  — code_a, code_b, weight
- code_cooccurrence_nodes.csv  — code, n_excerpts, n_participants
- code_cooccurrence.graphml    — the same network for Gephi/yEd/R

The picture (PNG) is drawn by the R script cooccurrence_network.R.

Typical use:

    python3 _scripts/python/build_code_cooccurrence_network.py
"""

from __future__ import annotations

import argparse
import csv
import re
from xml.sax.saxutils import escape

from qv_common import (audit, effective_code, find_vault, next_steps, ok,
                       read_reviewed, review_warnings, step, today,
                       usable_rows, warn)


def excerpt_index(excerpt_id: str) -> int:
    m = re.search(r"-e(\d+)$", excerpt_id or "")
    return int(m.group(1)) if m else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window", type=int, default=2,
                    help="How close two excerpts must be to count as co-occurring (default 2; 0 = same excerpt only).")
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="Only show what would happen.")
    args = ap.parse_args()

    vault = find_vault(args.vault)
    rows, counts = read_reviewed(vault)
    review_warnings(counts)
    good = usable_rows(rows)
    if not good:
        warn("No accepted or edited rows yet — nothing to build a network from.")
        return

    # Collect: per transcript, a list of (excerpt index, code); per code, its excerpts/participants.
    per_transcript: dict[str, list[tuple[int, str]]] = {}
    code_excerpts: dict[str, set[str]] = {}
    code_participants: dict[str, set[str]] = {}
    for r in good:
        code = effective_code(r)
        if not code:
            continue
        tid = r.get("transcript_id", "?")
        per_transcript.setdefault(tid, []).append((excerpt_index(r.get("excerpt_id", "")), code))
        code_excerpts.setdefault(code, set()).add(r.get("excerpt_id", ""))
        code_participants.setdefault(code, set()).add(r.get("participant_id", "?"))

    if len(code_excerpts) < 2:
        warn("Fewer than two distinct codes so far — a network needs at least two. "
             "Come back after more coding.")
        return

    edges: dict[tuple[str, str], int] = {}
    for items in per_transcript.values():
        items.sort()
        for i, (idx_a, code_a) in enumerate(items):
            for idx_b, code_b in items[i + 1:]:
                if idx_b - idx_a > args.window:
                    break
                if code_a == code_b:
                    continue
                pair = tuple(sorted((code_a, code_b)))
                edges[pair] = edges.get(pair, 0) + 1

    out_dir = vault / "12_Exports"
    out_edges = out_dir / "code_cooccurrence_edges.csv"
    out_nodes = out_dir / "code_cooccurrence_nodes.csv"
    out_graphml = out_dir / "code_cooccurrence.graphml"

    if args.dry_run:
        step(f"Would write {len(code_excerpts)} nodes and {len(edges)} edges "
             f"(window {args.window}) to {out_edges.name}, {out_nodes.name}, {out_graphml.name}.")
        ok("Dry run only. Nothing was changed.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    with out_nodes.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "n_excerpts", "n_participants"])
        for code in sorted(code_excerpts):
            w.writerow([code, len(code_excerpts[code]), len(code_participants[code])])

    with out_edges.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["code_a", "code_b", "weight"])
        for (a, b), weight in sorted(edges.items(), key=lambda x: -x[1]):
            w.writerow([a, b, weight])

    node_ids = {code: f"n{i}" for i, code in enumerate(sorted(code_excerpts))}
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="n_excerpts" for="node" attr.name="n_excerpts" attr.type="int"/>',
        '  <key id="weight" for="edge" attr.name="weight" attr.type="int"/>',
        '  <graph id="code_cooccurrence" edgedefault="undirected">',
    ]
    for code, nid in node_ids.items():
        xml.append(f'    <node id="{nid}">'
                   f'<data key="label">{escape(code)}</data>'
                   f'<data key="n_excerpts">{len(code_excerpts[code])}</data></node>')
    for j, ((a, b), weight) in enumerate(sorted(edges.items())):
        xml.append(f'    <edge id="e{j}" source="{node_ids[a]}" target="{node_ids[b]}">'
                   f'<data key="weight">{weight}</data></edge>')
    xml += ["  </graph>", "</graphml>", ""]
    out_graphml.write_text("\n".join(xml), encoding="utf-8")

    ok(f"Wrote {out_nodes.name} ({len(node_ids)} codes), {out_edges.name} ({len(edges)} links), "
       f"and {out_graphml.name}.")
    audit(vault, "build_code_cooccurrence_network.py",
          f"{len(good)} reviewed rows, window {args.window}", "(no model)",
          f"{out_nodes.name}; {out_edges.name}; {out_graphml.name}")

    next_steps(
        "Draw the picture: Rscript _scripts/r/cooccurrence_network.R",
        "Codes that always travel together may be one code — or a candidate category. "
        "That call is yours; write it as a memo.",
        "The .graphml file opens in Gephi or yEd if you want to explore by hand.",
    )


if __name__ == "__main__":
    main()
