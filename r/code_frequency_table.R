#!/usr/bin/env Rscript
# Code frequency table and bar chart — from YOUR reviewed coding only.
#
# Counts how often each code was applied (rows you marked accepted or edited)
# and how many participants it appears in.
#
# Run from the vault folder:   Rscript _scripts/r/code_frequency_table.R
# Output: 12_Exports/code_frequency.csv and 12_Exports/code_frequency.png
#
# The chart carries the caption "Frequency is not importance" on purpose.
# It belongs in your appendix or your own overview — the argument for what
# matters is made in your results text, not by bar length.

source(file.path(dirname(sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1])), "qv_common.R"))

vault <- find_vault()
rows <- read_reviewed(vault)
review_warnings(rows)
good <- usable_rows(rows)

freq <- good |>
  group_by(code) |>
  summarise(
    n_excerpts = n_distinct(excerpt_id),
    n_participants = n_distinct(participant_id),
    n_transcripts = n_distinct(transcript_id),
    .groups = "drop"
  ) |>
  arrange(desc(n_excerpts), code)

save_csv(vault, freq, "code_frequency.csv")

p <- ggplot(freq, aes(x = n_excerpts, y = reorder(code, n_excerpts))) +
  geom_col(fill = QV_PURPLE, width = 0.7) +
  geom_text(aes(label = n_excerpts), hjust = -0.4, colour = QV_INK, size = 3.2) +
  scale_x_continuous(breaks = int_breaks, expand = expansion(mult = c(0, 0.12))) +
  labs(
    title = "Code frequency",
    subtitle = paste0("Human-reviewed coding (accepted or edited rows), ",
                      n_distinct(good$participant_id), " participant(s), ",
                      n_distinct(good$transcript_id), " transcript(s)"),
    x = "Excerpts the code was applied to", y = NULL,
    caption = FREQ_CAPTION
  ) +
  qv_theme()

save_plot(vault, p, "code_frequency.png",
          height = max(3, 0.8 + 0.32 * nrow(freq)))
audit(vault, "code_frequency_table.R", paste(nrow(good), "reviewed rows"),
      "code_frequency.csv; code_frequency.png")

next_steps(
  "Codes applied only once are not noise — check them before merging or dropping anything.",
  "Next: Rscript _scripts/r/code_by_participant_matrix.R to see who says what.",
  "A crowded chart usually means codebook work (merge/split), not a bigger chart."
)
