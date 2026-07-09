#!/usr/bin/env Rscript
# Theme × participant matrix — how each decided theme is grounded across participants.
#
# Themes are read from your notes in 07_Themes/: every note whose frontmatter has
# a `theme:` name and a `codes: [code1, code2]` list is included. The matrix counts
# excerpts (accepted/edited) whose code belongs to the theme.
#
# Run from the vault folder:   Rscript _scripts/r/theme_matrix.R
# Output: 12_Exports/theme_by_participant.csv and .png
#
# The matrix shows how a theme is spread across your data. It does not make the
# theme true, and thin cells do not make it false — a theme can rest on few but
# decisive excerpts. That argument is yours.

source(file.path(dirname(sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1])), "qv_common.R"))

vault <- find_vault()
themes <- read_theme_notes(vault)
if (length(themes) == 0) {
  die("No theme notes with codes found in 07_Themes/.",
      "Create theme notes from the Theme Template. The frontmatter needs a `theme:` name and a `codes: [code-a, code-b]` list. Come back when at least one theme has codes.")
}

rows <- read_reviewed(vault)
review_warnings(rows)
good <- usable_rows(rows)

theme_map <- bind_rows(lapply(themes, function(t)
  tibble(theme = t$name, theme_status = t$status, code = t$codes)))

unknown <- setdiff(theme_map$code, unique(good$code))
if (length(unknown) > 0) {
  note(paste0("These codes are listed in theme notes but not found in the reviewed coding: ",
              paste(unknown, collapse = ", "), ". Check the spelling in the theme frontmatter."))
}

long <- good |>
  inner_join(theme_map, by = "code", relationship = "many-to-many") |>
  group_by(theme, theme_status, participant_id) |>
  summarise(n = n_distinct(excerpt_id), .groups = "drop")

if (nrow(long) == 0) {
  die("No reviewed excerpts matched any theme's codes.",
      "Check that the codes in your theme notes are written exactly as in the coding (see 12_Exports/code_frequency.csv for the exact labels).")
}

wide <- long |>
  select(-theme_status) |>
  pivot_wider(names_from = participant_id, values_from = n, values_fill = 0)
save_csv(vault, wide, "theme_by_participant.csv")

p <- ggplot(long, aes(x = participant_id, y = theme, fill = n)) +
  geom_tile(colour = "white", linewidth = 0.6) +
  geom_text(aes(label = n), colour = "white", size = 3.4) +
  scale_fill_gradient(low = QV_LILAC, high = QV_PURPLE, guide = "none") +
  labs(
    title = "Themes by participant",
    subtitle = "Cell = excerpts whose codes belong to the theme",
    x = NULL, y = NULL,
    caption = "Spread describes grounding, not truth. Thin cells do not refute a theme;\nthe argument for each theme is made in its theme note and your results text."
  ) +
  qv_theme() +
  theme(panel.grid = element_blank())

save_plot(vault, p, "theme_by_participant.png",
          width = max(6, 2.5 + 1.1 * n_distinct(long$participant_id)),
          height = max(3, 1.2 + 0.5 * n_distinct(long$theme)))
audit(vault, "theme_matrix.R",
      paste(length(themes), "theme notes;", nrow(good), "reviewed rows"),
      "theme_by_participant.csv; theme_by_participant.png")

next_steps(
  "A theme resting on one participant needs either more data or a narrower claim — memo it.",
  "Check each theme note: does it list negative cases? The matrix cannot see those.",
  "For the results write-up tables: Rscript _scripts/r/qualitative_results_tables.R"
)
