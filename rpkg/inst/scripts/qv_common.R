# Shared helpers for QualiVahti Local R scripts.
#
# The same rules as the Python side, enforced here too:
# - Only human-reviewed rows count (review_status accepted or edited).
# - Every run is written to the audit trail.
# - Everything runs on this computer. No internet calls anywhere.

suppressWarnings(suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tidyr)
  library(ggplot2)
}))

# ---------------- talking to the user ----------------

step <- function(msg) cat("->", msg, "\n")
ok   <- function(msg) cat("[done]", msg, "\n")
note <- function(msg) cat("[note]", msg, "\n")

die <- function(problem, fix = NULL) {
  cat("\n[stopped]", problem, "\n")
  if (!is.null(fix)) cat("How to fix it:", fix, "\n")
  quit(save = "no", status = 1)
}

next_steps <- function(...) {
  cat("\nWhat to do next:\n")
  lines <- c(...)
  for (i in seq_along(lines)) cat(sprintf("  %d. %s\n", i, lines[i]))
}

# ---------------- vault paths ----------------

find_vault <- function() {
  # Allow:  Rscript script.R --vault /some/path   (used for testing)
  args <- commandArgs(trailingOnly = TRUE)
  v <- which(args == "--vault")
  if (length(v) == 1 && length(args) > v) {
    p <- normalizePath(args[v + 1], mustWork = FALSE)
    if (!dir.exists(p)) die(paste("The vault folder does not exist:", p),
                            "Check the --vault path for typing mistakes.")
    return(p)
  }
  # Normal case: the script lives in <vault>/_scripts/r/
  full <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(full) == 1) {
    return(normalizePath(file.path(dirname(sub("^--file=", "", full)), "..", "..")))
  }
  normalizePath(".")
}

qv_today <- function() format(Sys.Date(), "%Y-%m-%d")

# ---------------- the data contract (same as Python) ----------------

read_reviewed <- function(vault) {
  coding <- file.path(vault, "04_Coding")
  files <- list.files(coding, pattern = "^(DEMO_)?reviewed_.*\\.csv$", full.names = TRUE)
  if (length(files) == 0) {
    die("No reviewed coding files found in 04_Coding/.",
        "First run the Python script suggest_codes_local_llm.py, then review the rows (set review_status). Then come back.")
  }
  rows <- bind_rows(lapply(files, function(f) {
    read_csv(f, col_types = cols(.default = col_character()), progress = FALSE) |>
      mutate(source_file = basename(f))
  }))
  rows |>
    mutate(review_status = tolower(trimws(coalesce(review_status, "suggested"))),
           code = coalesce(na_if(trimws(coalesce(final_code, "")), ""),
                           trimws(coalesce(suggested_code, ""))))
}

review_warnings <- function(rows) {
  pending <- sum(rows$review_status == "suggested")
  unclear <- sum(rows$review_status == "unclear")
  if (pending > 0) note(paste(pending, "rows still have status 'suggested' — nobody has reviewed them yet. They are NOT included in any output."))
  if (unclear > 0) note(paste(unclear, "rows are marked 'unclear'. They are not included. Revisit them when you can."))
}

usable_rows <- function(rows) {
  good <- rows |> filter(review_status %in% c("accepted", "edited"), code != "")
  if (nrow(good) == 0) {
    die("No rows are marked 'accepted' or 'edited' yet, so there is nothing to count.",
        "Open your reviewed_*.csv files in 04_Coding/ and review the rows first.")
  }
  good
}

# ---------------- audit trail (same file as the Python side) ----------------

audit <- function(vault, script, inputs, outputs) {
  log <- file.path(vault, "11_Audit_Trail", "audit_log.md")
  dir.create(dirname(log), showWarnings = FALSE, recursive = TRUE)
  if (!file.exists(log)) {
    writeLines(c("---", "type: audit-trail-machine-log", "generated: true", "---", "",
                 "# Machine log — script runs", "",
                 "Scripts add one row here every time they run. Do not edit rows.",
                 "Your own decisions go in your Audit Trail note (see `_templates/Audit Trail Template.md`).",
                 "",
                 "| Date | Script | Inputs | Model + version | Outputs |",
                 "|---|---|---|---|---|"), log)
  }
  row <- sprintf("| %s | %s | %s | (no model) | %s |",
                 qv_today(), script, gsub("[|\n]", "/", inputs), gsub("[|\n]", "/", outputs))
  cat(row, "\n", sep = "", file = log, append = TRUE)
  ok("Audit trail updated (11_Audit_Trail/audit_log.md).")
}

# ---------------- Vahtian look for plots ----------------

QV_PURPLE  <- "#5b4b8a"
QV_LILAC   <- "#8d7bbf"
QV_MIST    <- "#e9e5f5"
QV_INK     <- "#2b2640"

qv_theme <- function() {
  theme_minimal(base_size = 12) +
    theme(
      text = element_text(colour = QV_INK),
      plot.title = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(colour = QV_LILAC),
      plot.caption = element_text(colour = QV_LILAC, size = 9),
      panel.grid.minor = element_blank(),
      plot.background = element_rect(fill = "white", colour = NA)
    )
}

# Plot text must stay ASCII-only: the macOS png device draws characters like
# the multiplication sign or em-dash as ".." — so "by" instead of "x", "-" instead of "—".
FREQ_CAPTION <- "Frequency is not importance. Counts describe how often\na code was applied - meaning is argued, not counted."

int_breaks <- function(lims) unique(floor(pretty(c(0, lims[2]))))

save_plot <- function(vault, plot, name, width = 8, height = 5) {
  out <- file.path(vault, "12_Exports", name)
  dir.create(dirname(out), showWarnings = FALSE, recursive = TRUE)
  # ragg renders text more crisply than the default device; used when installed.
  if (requireNamespace("ragg", quietly = TRUE)) {
    ggsave(out, plot, width = width, height = height, dpi = 150, bg = "white",
           device = ragg::agg_png)
  } else {
    ggsave(out, plot, width = width, height = height, dpi = 150, bg = "white")
  }
  ok(paste0("Wrote 12_Exports/", name))
  invisible(out)
}

save_csv <- function(vault, df, name) {
  out <- file.path(vault, "12_Exports", name)
  dir.create(dirname(out), showWarnings = FALSE, recursive = TRUE)
  write_csv(df, out)
  ok(paste0("Wrote 12_Exports/", name, " (", nrow(df), " rows)"))
  invisible(out)
}

# ---------------- themes (read from 07_Themes notes) ----------------

read_theme_notes <- function(vault) {
  files <- list.files(file.path(vault, "07_Themes"), pattern = "\\.md$", full.names = TRUE)
  themes <- list()
  for (f in files) {
    lines <- readLines(f, warn = FALSE)
    fm_end <- which(lines == "---")
    if (length(fm_end) < 2) next
    fm <- lines[(fm_end[1] + 1):(fm_end[2] - 1)]
    get_field <- function(key) {
      hit <- grep(paste0("^", key, ":"), fm, value = TRUE)
      if (length(hit) == 0) return("")
      trimws(sub(paste0("^", key, ":"), "", hit[1]))
    }
    name <- get_field("theme")
    codes_raw <- get_field("codes")
    if (name == "" || codes_raw == "" || codes_raw == "[]") next
    codes <- trimws(strsplit(gsub("[][\"]", "", codes_raw), ",")[[1]])
    codes <- codes[codes != ""]
    if (length(codes) == 0) next
    themes[[name]] <- list(name = name, codes = codes,
                           status = get_field("status"), file = basename(f))
  }
  themes
}
