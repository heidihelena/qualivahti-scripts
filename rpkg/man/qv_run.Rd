\name{qv_run}
\alias{qv_run}
\alias{qv_scripts_path}
\alias{qv_coding_summary}
\alias{qv_code_frequency}
\alias{qv_code_by_participant}
\alias{qv_theme_matrix}
\alias{qv_cooccurrence_network}
\alias{qv_results_tables}
\title{Run the QualiVahti analysis scripts against a vault folder}
\description{
Executes the QualiVahti analysis scripts (shipped in the package under
\code{inst/scripts/}) against a QualiVahti Local vault folder. The scripts
read the human-reviewed coding files (\code{04_Coding/reviewed_*.csv}),
count only rows a reviewer marked \code{accepted} or \code{edited}, write
tables and charts to \code{12_Exports/}, and append every run to the
vault's audit trail. All processing is local.
}
\usage{
qv_run(script, vault = ".", args = character())
qv_scripts_path()
qv_coding_summary(vault = ".")
qv_code_frequency(vault = ".")
qv_code_by_participant(vault = ".")
qv_theme_matrix(vault = ".")
qv_cooccurrence_network(vault = ".")
qv_results_tables(vault = ".")
}
\arguments{
  \item{script}{File name of a script in \code{qv_scripts_path()},
    e.g. \code{"coding_summary.R"}.}
  \item{vault}{Path to the vault folder (the folder that contains
    \code{04_Coding/}, \code{07_Themes/}, \code{12_Exports/}, ...).}
  \item{args}{Additional command-line arguments passed to the script.}
}
\value{
The script's exit status, invisibly. Outputs are written into the vault's
\code{12_Exports/} folder; each script prints what it wrote and what to do
next.
}
\details{
The convenience wrappers run, in order of a typical study:
\code{qv_coding_summary} (review progress), \code{qv_code_frequency}
(frequency table + chart), \code{qv_code_by_participant} (heat map),
\code{qv_cooccurrence_network} (network drawing; run the Python network
builder first), \code{qv_theme_matrix} (themes across participants, read
from the theme notes' \code{codes:} lists), and \code{qv_results_tables}
(descriptive tables with honest captions). Charts state on the image that
frequency is not importance.
}
\examples{
\dontrun{
qv_coding_summary("~/MyStudyVault")
qv_code_frequency("~/MyStudyVault")
}
}
