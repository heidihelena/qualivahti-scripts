#!/usr/bin/env Rscript
# Coding summary — where does the coding stand?
#
# Reads every reviewed_*.csv in 04_Coding/ and shows, per transcript:
# how many excerpts, how many rows in each review status, and how many
# distinct codes so far. Good for a quick "am I done reviewing?" check.
#
# Run from the vault folder:   Rscript _scripts/r/coding_summary.R
# Output: 12_Exports/coding_summary.csv (+ what it prints on screen)

source(file.path(dirname(sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1])), "qv_common.R"))

vault <- find_vault()
rows <- read_reviewed(vault)

summary_tbl <- rows |>
  group_by(transcript_id, participant_id) |>
  summarise(
    excerpts = n_distinct(excerpt_id),
    suggestions = n(),
    accepted = sum(review_status == "accepted"),
    edited = sum(review_status == "edited"),
    rejected = sum(review_status == "rejected"),
    unclear = sum(review_status == "unclear"),
    waiting_for_review = sum(review_status == "suggested"),
    distinct_codes = n_distinct(code[review_status %in% c("accepted", "edited")]),
    .groups = "drop"
  ) |>
  arrange(transcript_id)

cat("\nCoding summary, per transcript:\n\n")
print(as.data.frame(summary_tbl), row.names = FALSE)

total_wait <- sum(summary_tbl$waiting_for_review)
cat("\n")
if (total_wait > 0) {
  note(paste(total_wait, "rows are still waiting for your review. Reviewed = every row has a status other than 'suggested'."))
} else {
  ok("Every suggestion has been reviewed. The review work is done for these transcripts.")
}

save_csv(vault, summary_tbl, "coding_summary.csv")
audit(vault, "coding_summary.R", paste(n_distinct(rows$source_file), "reviewed files"), "coding_summary.csv")

next_steps(
  "If rows are waiting: open the reviewed_*.csv files in 04_Coding/ and finish the review.",
  "If review is done: run Rscript _scripts/r/code_frequency_table.R for the frequency table and chart.",
  "Update your Saturation Log after each analyzed interview (template in _templates/)."
)
