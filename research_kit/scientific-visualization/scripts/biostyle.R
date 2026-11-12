# biostyle.R \u2014 publication-grade ggplot2 style engine (R twin of biostyle.py)
#
# Source this file, then:
#
#   source("biostyle.R")
#   p <- ggplot(df, aes(x, y, colour = grp)) + geom_line(linewidth = 0.8) +
#        scale_colour_biostyle() + theme_biostyle() + labs(x = "...", y = "...")
#   save_fig_r(p, "fig1_line", width = 89, height = 70)
#
# Design rules baked in
# ---------------------
# - Colorblind-safe palettes (Okabe-Ito / Phylo brand); never rainbow/jet.
# - Clean spines, outward ticks, subtle grid, Liberation Sans.
# - SVG text stays editable (svglite); PNG at 300 dpi.
# - Journal column widths: single 89 mm, 1.5-column 120 mm, double 183 mm.
#
# Theme variants: journal (default) | poster | dark | minimal
#   theme_biostyle("poster") etc.

suppressPackageStartupMessages({
  library(ggplot2)
})

# ---------------------------------------------------------------- palettes --

PHYLO     <- c("#0279EE", "#FF9400", "#75A025", "#FD9BED", "#E9ED4C", "#7A00E6")
OKABE_ITO <- c("#0072B2", "#E69F00", "#009E73", "#D55E00",
               "#CC79A7", "#56B4E9", "#F0E442", "#999999")
PALETTE   <- OKABE_ITO[1:7]
.biostyle_palette_path <- file.path(dirname(normalizePath(sys.frame(1)$ofile)), '../assets/palettes.json')
biostyle_palettes <- function() jsonlite::read_json(.biostyle_palette_path, simplifyVector=TRUE)

#' Categorical palette of n colors ("okabe" default or "phylo")
cat_palette <- function(n, style = 'okabe') {
  style <- style[1]
  palettes <- biostyle_palettes()
  base <- if(style=='okabe') OKABE_ITO else if(style=='phylo') PHYLO else palettes[[style]]
  if(is.null(base))stop('Unknown palette; use names(biostyle_palettes())')
  if(length(n)!=1L || !is.finite(n) || n<0 || n!=as.integer(n))stop('Nonnegative integer colour count required')
  if(n>length(base))stop('Palette capacity exceeded; use explicit colours, shapes or facets instead of repeated identities')
  base[seq_len(n)]
}

#' Discrete colour/fill scales on biostyle palettes
scale_colour_biostyle <- function(style = c("okabe", "phylo"), ...) {
  style <- style[1]
  ggplot2::discrete_scale("colour", paste0("biostyle_", style),
                          palette = function(n) cat_palette(n, style), ...)
}
scale_fill_biostyle <- function(style = c("okabe", "phylo"), ...) {
  style <- style[1]
  ggplot2::discrete_scale("fill", paste0("biostyle_", style),
                          palette = function(n) cat_palette(n, style), ...)
}

#' Balanced brand diverging gradient (blue <-> paper <-> orange), CVD-safe
scale_fill_div_biostyle <- function(name = "brand", ...) {
  pal <- c("#0279EE", "#7FB6F2", "#FAF9F3", "#FFC466", "#FF9400")
  ggplot2::scale_fill_gradient2(low = pal[1], mid = pal[3], high = pal[5],
                                midpoint = 0, ...)
}
scale_colour_div_biostyle <- function(name = "brand", ...) {
  pal <- c("#0279EE", "#7FB6F2", "#FAF9F3", "#FFC466", "#FF9400")
  ggplot2::scale_colour_gradient2(low = pal[1], mid = pal[3], high = pal[5],
                                  midpoint = 0, ...)
}

# ------------------------------------------------------------------ themes --

#' biostyle ggplot theme
#'
#' variant: "journal" (default), "poster", "dark", "minimal".
#' base_size is derived from the variant; override for fine control.
theme_biostyle <- function(variant = c("journal", "poster", "dark", "minimal"),
                           base_size = NULL) {
  variant <- match.arg(variant)
  if (is.null(base_size)) {
    base_size <- switch(variant, journal = 8, poster = 13, dark = 10, minimal = 10)
  }
  dark <- variant == "dark"
  ink  <- if (dark) "#FAF9F3" else "#1A1A1A"
  bg   <- if (dark) "#1E1E24" else "white"
  grid <- if (dark) "#4A4A55" else "#D8DEE4"

  out <- ggplot2::theme_bw(base_size = base_size, base_family = "Liberation Sans") +
    ggplot2::theme(
      text              = ggplot2::element_text(family = "Liberation Sans", colour = ink),
      line              = ggplot2::element_line(linewidth = 0.5, colour = ink),
      rect              = ggplot2::element_rect(fill = bg, colour = NA),
      panel.background  = ggplot2::element_rect(fill = bg, colour = NA),
      plot.background   = ggplot2::element_rect(fill = bg, colour = NA),
      panel.border      = ggplot2::element_blank(),
      panel.grid        = ggplot2::element_line(colour = grid, linewidth = 0.4),
      panel.grid.major.x = ggplot2::element_blank(),
      panel.grid.minor  = ggplot2::element_blank(),
      axis.line         = ggplot2::element_line(colour = ink, linewidth = 0.5),
      axis.ticks        = ggplot2::element_line(colour = ink, linewidth = 0.5),
      axis.ticks.length = ggplot2::unit(2.2, "pt"),
      axis.text         = ggplot2::element_text(colour = ink, size = base_size - 1),
      axis.title        = ggplot2::element_text(colour = ink, size = base_size),
      plot.title        = ggplot2::element_text(face = "bold", size = base_size + 1),
      legend.background = ggplot2::element_blank(),
      legend.key        = ggplot2::element_blank(),
      legend.title      = ggplot2::element_text(size = base_size - 1),
      legend.text       = ggplot2::element_text(size = base_size - 1),
      strip.background  = ggplot2::element_rect(fill = if (dark) "#2A2A33" else "#EFF2F5",
                                                colour = NA),
      strip.text        = ggplot2::element_text(face = "bold", colour = ink)
    )
  if (variant == "minimal") {
    out <- out + ggplot2::theme(panel.grid = ggplot2::element_blank(),
                                axis.line  = ggplot2::element_blank())
  }
  out
}

# ------------------------------------------------------------------ output --

#' Journal column width in mm
col_mm <- function(width = c("single", "onehalf", "double")) {
  width <- match.arg(width)
  switch(width, single = 89, onehalf = 120, double = 183)
}

#' Save a plot as PNG (300 dpi) + SVG (editable text via svglite)
#'
#' Accepts ggplot objects, patchwork/cowplot composites, ComplexHeatmap
#' objects, survminer ggsurvplot objects, and recorded plots.
#' width/height in mm (default: single column x 0.75 aspect).
#' Returns the written paths invisibly.
save_fig_r <- function(plot, name, outdir = NULL,
                       width = col_mm("single"), height = 0.75 * width,
                       formats = c("png", "svg"), dpi = 300) {
  stopifnot(requireNamespace("svglite", quietly = TRUE))
  outdir <- outdir %||% Sys.getenv("BIOMNI_RESULTS", "figures")
  dir.create(outdir, showWarnings = FALSE, recursive = TRUE)
  is_gg <- inherits(plot, c("ggplot", "patchwork", "grob", "gtable"))
  if (is.function(plot)) {
    # base-graphics drawer (circlize, oncoPrint helpers): re-run per device.
    # recordPlot() replay across device types silently yields empty files.
    draw_in <- function() plot()
  } else {
    draw_in <- function() {                     # device-agnostic printing
      if (inherits(plot, "Heatmap")) ComplexHeatmap::draw(plot)
      else print(plot)                          # ggsurvplot, recorded plots, ...
    }
  }
  written <- character(0)
  for (ext in formats) {
    path <- file.path(outdir, sprintf("%s.%s", name, ext))
    if (is_gg) {
      ggplot2::ggsave(path, plot, width = width, height = height,
                      units = "mm", dpi = dpi)
    } else if (ext == "png") {
      grDevices::png(path, width = width, height = height,
                     units = "mm", res = dpi)
      draw_in(); grDevices::dev.off()
    } else {
      svglite::svglite(path, width = width / 25.4, height = height / 25.4)
      draw_in(); grDevices::dev.off()
    }
    written <- c(written, path)
  }
  invisible(written)
}

`%||%` <- function(a, b) if (is.null(a)) b else a

# ------------------------------------------------------------- annotations --

#' Bold panel tags (a, b, c, ...) via patchwork's tag system
#'
#' Usage: (p1 | p2) / p3 + panel_tags()
#' case: "lower" (a, b, c) or "upper" (A, B, C).
panel_tags <- function(case = c("lower", "upper")) {
  case <- match.arg(case)
  if (!requireNamespace("patchwork", quietly = TRUE)) {
    stop("panel_tags() requires the patchwork package")
  }
  patchwork::plot_annotation(tag_levels = if (case == "lower") "a" else "A")
}

#' Significance stars from p-values ("ns", "*", "**", "***", "****")
sig_stars <- function(p) {
  dplyr::case_when(
    p < 1e-4 ~ "****", p < 1e-3 ~ "***", p < 1e-2 ~ "**",
    p < 0.05 ~ "*", TRUE ~ "ns"
  )
}

#' Add significance brackets to a ggplot (ggpubr bridge)
#'
#' p: plot; data-driven alternative to ggpubr::geom_signif for precomputed
#' p-values. positions: named vector category -> x; pairs: list of 2-element
#' category vectors; pvals: matching p-values; y_start/step in data units;
#' h: bracket stub height (auto-estimated from the y range when omitted).
add_sig_brackets <- function(p, positions, pairs, pvals, y_start, step, h = NULL) {
  if (!requireNamespace("ggpubr", quietly = TRUE)) {
    stop("add_sig_brackets() requires the ggpubr package")
  }
  if (is.null(h)) {
    yr <- tryCatch(ggplot2::layer_scales(p)$y$range$range,
                   error = function(e) c(0, 1))
    if (is.null(yr)) yr <- c(0, 1)
    h <- 0.02 * diff(yr)
  }
  df <- data.frame(
    group1 = vapply(pairs, function(x) x[1], ""),
    group2 = vapply(pairs, function(x) x[2], ""),
    p.adj  = pvals
  )
  df$map <- sig_stars(df$p.adj)
  if (length(pairs) != length(pvals)) stop('pairs/pvals lengths differ')
  if (any(!is.na(pvals) & (pvals < 0 | pvals > 1))) stop('p outside [0,1]')
  df$y.position <- y_start + (seq_len(nrow(df)) - 1) * step
  ggpubr::stat_pvalue_manual(df, label='map', y.position='y.position',
    xmin='group1', xmax='group2', tip.length=0.01, size=3, bracket.size=0.4)
}
