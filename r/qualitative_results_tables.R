#!/usr/bin/env Rscript
# Publication-ready descriptive tables from YOUR reviewed coding.
#
# Run from the vault folder:   Rscript _scripts/r/qualitative_results_tables.R
# Output (12_Exports/):
#   results_table1_participants.csv — data overview per participant
#   results_table2_codes.csv        — codes with counts and one example quote
#   results_tables.md               — both tables formatted, with honest captions
#
# These are DESCRIPTIVE tables for a methods/results appendix. They report
# what was coded — they do not rank importance and they are not your findings.

source(file.path(dirname(sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1])), "qv_common.R"))

vault <- find_vault()
rows <- read_reviewed(vault)
review_warnings(rows)
good <- usable_rows(rows)

# ---- Table 1: overview per participant ----
t1 <- rows |>
  group_by(participant_id) |>
  summarise(
    transcripts = n_distinct(transcript_id),
    excerpts = n_distinct(excerpt_id),
    suggestions_reviewed = sum(review_status != "suggested"),
    codes_applied = n_distinct(code[review_status %in% c("accepted", "edited")]),
    .groups = "drop"
  ) |>
  arrange(participant_id)
save_csv(vault, t1, "results_table1_participants.csv")

# ---- Table 2: codes with an example quote ----
shorten <- function(x, n = 110) ifelse(nchar(x) > n, paste0(substr(x, 1, n), "…"), x)
t2 <- good |>
  group_by(code) |>
  summarise(
    participants = n_distinct(participant_id),
    excerpts = n_distinct(excerpt_id),
    example_quote = shorten(gsub("\n", " ", first(excerpt))),
    example_source = paste0(first(participant_id), ", ", first(excerpt_id)),
    .groups = "drop"
  ) |>
  arrange(desc(excerpts), code)
save_csv(vault, t2, "results_table2_codes.csv")

# ---- Markdown version with captions ----
md_table <- function(df) {
  esc <- function(x) gsub("\\|", "/", as.character(x))
  header <- paste0("| ", paste(names(df), collapse = " | "), " |")
  sep <- paste0("|", paste(rep("---", ncol(df)), collapse = "|"), "|")
  body <- apply(df, 1, function(r) paste0("| ", paste(esc(r), collapse = " | "), " |"))
  c(header, sep, body)
}

review_done <- sum(rows$review_status != "suggested")
md <- c(
  "---", "type: export", "generated: true",
  paste0("created: ", qv_today()), "---", "",
  "# Descriptive tables (results appendix)", "",
  "Generated file — edits here will be lost on the next run.",
  "All counts come from human-reviewed coding (accepted or edited rows).", "",
  "## Table 1 — Data and coding overview per participant", "",
  md_table(t1), "",
  paste0("*Caption: Coded data per participant. ", review_done, " of ", nrow(rows),
         " model suggestions were human-reviewed. Suggested codes were accepted, edited, ",
         "or rejected by the researcher(s); analytic decisions were made by the researcher(s).*"), "",
  "## Table 2 — Codes with example quotes", "",
  md_table(t2), "",
  paste0("*Caption: Codes applied in the reviewed coding, with one example quote each. ",
         "Counts describe how often a code was applied; frequency is not importance.*"), ""
)
writeLines(md, file.path(vault, "12_Exports", "results_tables.md"))
ok("Wrote 12_Exports/results_tables.md")

audit(vault, "qualitative_results_tables.R", paste(nrow(good), "reviewed rows"),
      "results_table1_participants.csv; results_table2_codes.csv; results_tables.md")

next_steps(
  "Check every example quote in Table 2 against its source before it goes anywhere.",
  "Use the Methods Draft template (09_Methods_Draft) — the caption numbers above belong in the AI-disclosure paragraph.",
  "The tables are appendix material. Your results text carries the meaning."
)
