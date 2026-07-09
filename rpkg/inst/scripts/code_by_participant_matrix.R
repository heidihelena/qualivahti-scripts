#!/usr/bin/env Rscript
# Code × participant matrix — which codes appear in whose interviews.
#
# Run from the vault folder:   Rscript _scripts/r/code_by_participant_matrix.R
# Output: 12_Exports/code_by_participant.csv (wide table)
#         12_Exports/code_by_participant.png (heat map)
#
# Read it as coverage, not as scores: an empty cell means "this code was not
# applied in this interview" — it does not mean the participant has nothing
# to say about it.

source(file.path(dirname(sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1])), "qv_common.R"))

vault <- find_vault()
rows <- read_reviewed(vault)
review_warnings(rows)
good <- usable_rows(rows)

long <- good |>
  group_by(code, participant_id) |>
  summarise(n = n_distinct(excerpt_id), .groups = "drop")

wide <- long |>
  pivot_wider(names_from = participant_id, values_from = n, values_fill = 0) |>
  arrange(code)
save_csv(vault, wide, "code_by_participant.csv")

code_order <- long |> group_by(code) |> summarise(t = sum(n)) |> arrange(t) |> pull(code)
p <- ggplot(long, aes(x = participant_id, y = factor(code, levels = code_order), fill = n)) +
  geom_tile(colour = "white", linewidth = 0.6) +
  geom_text(aes(label = n), colour = "white", size = 3.2) +
  scale_fill_gradient(low = QV_LILAC, high = QV_PURPLE, guide = "none") +
  labs(
    title = "Codes by participant",
    subtitle = "Cell = excerpts with this code, per participant",
    x = NULL, y = NULL,
    caption = paste("An empty cell means the code was not applied there -\nnot that it does not apply.",
                    FREQ_CAPTION, sep = "\n")
  ) +
  qv_theme() +
  theme(panel.grid = element_blank())

save_plot(vault, p, "code_by_participant.png",
          width = max(6, 2.5 + 1.1 * n_distinct(long$participant_id)),
          height = max(3.5, 1 + 0.35 * n_distinct(long$code)))
audit(vault, "code_by_participant_matrix.R", paste(nrow(good), "reviewed rows"),
      "code_by_participant.csv; code_by_participant.png")

next_steps(
  "Codes concentrated in one participant are worth a memo: personal, or a sampling gap?",
  "Codes spread across everyone may be candidates for categories — your call, in a memo.",
  "Next: Rscript _scripts/r/cooccurrence_network.R to see which codes travel together."
)
