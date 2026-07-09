# Runners for the QualiVahti analysis scripts.
#
# The scripts are plain Rscript files shipped in inst/scripts/ (they also live
# and run inside the QualiVahti Local vault). These wrappers execute them
# against a vault folder. Only rows a human reviewer marked accepted or edited
# are ever counted; every run appends to the vault's audit trail.

qv_scripts_path <- function() {
  system.file("scripts", package = "qualivahti")
}

qv_run <- function(script, vault = ".", args = character()) {
  path <- file.path(qv_scripts_path(), script)
  if (!file.exists(path)) {
    stop("Unknown script: ", script, "\nAvailable: ",
         paste(list.files(qv_scripts_path(), pattern = "\\.R$"), collapse = ", "))
  }
  vault <- normalizePath(vault, mustWork = TRUE)
  status <- system2("Rscript", c(shQuote(path), "--vault", shQuote(vault), args))
  invisible(status)
}

qv_coding_summary <- function(vault = ".") {
  qv_run("coding_summary.R", vault)
}

qv_code_frequency <- function(vault = ".") {
  qv_run("code_frequency_table.R", vault)
}

qv_code_by_participant <- function(vault = ".") {
  qv_run("code_by_participant_matrix.R", vault)
}

qv_theme_matrix <- function(vault = ".") {
  qv_run("theme_matrix.R", vault)
}

qv_cooccurrence_network <- function(vault = ".") {
  qv_run("cooccurrence_network.R", vault)
}

qv_results_tables <- function(vault = ".") {
  qv_run("qualitative_results_tables.R", vault)
}
