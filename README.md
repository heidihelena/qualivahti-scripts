# QualiVahti analysis scripts

Open-source Python and R scripts for local-first qualitative analysis: transcription on your own machine, AI-suggested coding under full human review, and publication-ready qualitative summaries. Apache-2.0 — include them freely in journal supplements, review packages, and repositories.

These scripts are the analysis engine of **[QualiVahti Local](https://vahtian.com/qualivahti-local/)**, a paid Obsidian vault (forskai by Vahtian) that packages them with templates, dashboards, an evidence-aware Canvas, and a complete demo study. The scripts are open so that any study using them can meet journal code-availability requirements and so reviewers can inspect exactly what the AI was allowed to do. The rule throughout: **models suggest structure; the researcher decides interpretation.**

## What is here

| Folder | Contents |
|---|---|
| `python/` | local Whisper transcription (+ folder watcher), transcript cleaning, AI code suggestion via a local Ollama model, quote extraction, co-occurrence network, Obsidian note export, evidence-map canvas builder, local RAG chat with cited sources |
| `r/` | coding summary, code frequency table + chart, code × participant matrix, theme × participant matrix, co-occurrence network drawing, descriptive tables with honest captions |
| `prompts/` | the AI prompt files, each with hard provenance rules (only provided text, no invented details, uncertainty marked, contradictions reported, human judgment named) |

Design invariants a reviewer can check in the code:

- The only network address anywhere is `localhost` (the scripts talk to a local Ollama). No research data can leave the machine.
- Scripts never overwrite human-reviewed files; suggestions and reviews live in separate files, and only rows a human marked `accepted` or `edited` are counted in any output.
- Every run appends to an audit trail with the model name and version.
- Frequency outputs carry the caption "frequency is not importance" in the output itself.

## Requirements

Python ≥ 3.10 (`pip install -r python/requirements.txt` — faster-whisper, requests), [Ollama](https://ollama.com) with any local model, and R with tidyverse + igraph (ggraph and ragg used when present). The scripts expect the QualiVahti vault folder layout; standalone use mostly works with `--vault <folder>` pointing at a folder using the same structure.

## How to cite

> Andersén HH. QualiVahti analysis scripts (version 1.0) [computer software]. Apache-2.0. DOI: *(Zenodo DOI appears here after the first archived release)*

See `CITATION.cff` — GitHub's "Cite this repository" button uses it.

## License

Apache License 2.0 (see `LICENSE`). The QualiVahti Local vault that packages these scripts is sold separately under a personal license at [vahtian.com/qualivahti-local](https://vahtian.com/qualivahti-local/).
