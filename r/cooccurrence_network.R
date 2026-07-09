#!/usr/bin/env Rscript
# Draw the code co-occurrence network as a picture.
#
# Reads the network the Python script built (run that first):
#   python3 _scripts/python/build_code_cooccurrence_network.py
#
# Run from the vault folder:   Rscript _scripts/r/cooccurrence_network.R
# Output: 12_Exports/code_cooccurrence_network.png
#
# How to read it: a line means two codes appear close together in the talk;
# a thicker line means it happens more often. Together is not cause, and
# central is not important. Clusters are questions to take to a memo.

source(file.path(dirname(sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1])), "qv_common.R"))
suppressWarnings(suppressPackageStartupMessages(library(igraph)))

vault <- find_vault()
edges_file <- file.path(vault, "12_Exports", "code_cooccurrence_edges.csv")
nodes_file <- file.path(vault, "12_Exports", "code_cooccurrence_nodes.csv")
if (!file.exists(edges_file) || !file.exists(nodes_file)) {
  die("The network files are not in 12_Exports/ yet.",
      "First run: python3 _scripts/python/build_code_cooccurrence_network.py — then run this again.")
}

edges <- read_csv(edges_file, show_col_types = FALSE)
nodes <- read_csv(nodes_file, show_col_types = FALSE)
if (nrow(edges) == 0) {
  die("The network has no links yet — codes never appeared close to each other.",
      "This is normal early on. Come back after coding more transcripts.")
}

g <- graph_from_data_frame(edges, directed = FALSE,
                           vertices = nodes |> rename(name = code))

set.seed(20)  # same layout every run, so versions are comparable
out_name <- "code_cooccurrence_network.png"

if (requireNamespace("ggraph", quietly = TRUE)) {
  # Nicer drawing when ggraph is installed (recommended).
  suppressWarnings(suppressPackageStartupMessages(library(ggraph)))
  p <- ggraph(g, layout = "fr", weights = E(g)$weight) +
    geom_edge_link(aes(edge_width = weight), colour = "#c9c0e4", alpha = 0.9) +
    geom_node_point(aes(size = n_excerpts), colour = QV_PURPLE) +
    geom_node_text(aes(label = name), colour = QV_INK, size = 3.4,
                   repel = TRUE, family = "sans") +
    scale_edge_width(range = c(0.5, 3), guide = "none") +
    scale_size(range = c(4, 12), guide = "none") +
    labs(
      title = "Code co-occurrence network",
      subtitle = "Line = codes appear close together in the talk; thicker = more often",
      caption = "Together is not cause, and central is not important.\nClusters are questions to take to a memo, not findings."
    ) +
    theme_void(base_size = 12) +
    theme(plot.title = element_text(face = "bold", size = 14, colour = QV_INK),
          plot.subtitle = element_text(colour = QV_LILAC),
          plot.caption = element_text(colour = QV_LILAC, size = 9),
          plot.margin = margin(10, 20, 10, 20))
  save_plot(vault, p, out_name, width = 9, height = 7)
} else {
  lay <- layout_with_fr(g, weights = E(g)$weight)
  out <- file.path(vault, "12_Exports", out_name)
  png(out, width = 1600, height = 1200, res = 150, bg = "white")
  par(mar = c(1, 1, 3, 1))
  plot(
    g, layout = lay,
    vertex.size = 8 + 2.5 * sqrt(V(g)$n_excerpts),
    vertex.color = "#8d7bbf", vertex.frame.color = "#5b4b8a",
    vertex.label = V(g)$name, vertex.label.family = "sans",
    vertex.label.color = "#2b2640", vertex.label.cex = 0.9, vertex.label.dist = 1.4,
    edge.width = 1.5 * E(g)$weight, edge.color = "#c9c0e4"
  )
  title(main = "Code co-occurrence network", col.main = "#2b2640", font.main = 2,
        sub = "Line = codes appear close together in the talk. Together is not cause; central is not important.",
        col.sub = "#8d7bbf", cex.sub = 0.85)
  invisible(dev.off())
  ok(paste0("Wrote 12_Exports/", out_name))
}

audit(vault, "cooccurrence_network.R",
      paste(nrow(nodes), "codes,", nrow(edges), "links"),
      basename(out))

next_steps(
  "Codes that always travel together may be one code, or a candidate category — write a memo either way.",
  "An isolated code is not a problem; it may be your most interesting one.",
  "The .graphml file in 12_Exports opens in Gephi or yEd if you want to explore by hand."
)
