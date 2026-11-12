> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Figure Assembly Mechanics

Layout mechanics for multi-panel figures: GridSpec/Mosaic layouts (Python),
patchwork/cowplot (R), panel tags, shared colorbars, legend extraction, and
export settings. Recipes for *which* panels go together live in
`composite-figures.md`.

## Python — GridSpec and subplots_mosaic

```python
# INPUT : panel-drawing functions
# OUTPUT: assembled figure
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, panel_labels

use_style("journal")
# Mosaic layout: readable ASCII art of the grid
fig, axes = plt.subplots_mosaic(
    [["umap", "umap", "dot"],
     ["umap", "umap", "dot"],
     ["prop", "qc",   "qc"]],
    figsize=journal_size("double", 0.6),
    gridspec_kw={"wspace": 0.25, "hspace": 0.35})
draw_umap(axes["umap"]); draw_dot(axes["dot"])
draw_prop(axes["prop"]); draw_qc(axes["qc"])
panel_labels(fig, [axes["umap"], axes["dot"], axes["prop"], axes["qc"]])
save_fig(fig, "fig_mosaic")
```

- `gridspec_kw` spacing: `wspace`/`hspace` 0.25–0.4 for composites; tighten
  only after checking label collisions.
- For a panel spanning rows/columns, prefer `subplots_mosaic` over raw
  `GridSpec` — the ASCII layout documents itself.
- `constrained_layout=True` is an alternative to manual spacing; do not mix
  it with `tight_bbox` savefig of colorbars added via `fig.colorbar(ax=...)`
  (it handles them correctly, manual `plt.tight_layout()` does not).

## Shared colorbar across panels

```python
# INPUT : two imshow/contourf panels with the same quantity
# OUTPUT: one shared colorbar on the right
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size

use_style("journal")
fig, axes = plt.subplots(1, 2, figsize=journal_size("onehalf", 0.55))
im1 = axes[0].imshow(A, vmin=0, vmax=1, cmap="mako")
im2 = axes[1].imshow(B, vmin=0, vmax=1, cmap="mako")
cb = fig.colorbar(im1, ax=axes, fraction=0.03, pad=0.02)
cb.set_label("Shared quantity (units)"); cb.outline.set_visible(False)
save_fig(fig, "fig_shared_cbar")
```

## Extract one legend for the whole figure

```python
# INPUT : panels sharing categorical colors
# OUTPUT: single legend at figure level
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size

use_style("journal")
fig, axes = plt.subplots(1, 2, figsize=journal_size("onehalf", 0.5))
h, l = axes[0].get_legend_handles_labels()          # from the first panel
axes[1].legend(h, l, loc="upper right", ncol=1)     # draw once
save_fig(fig, "fig_one_legend")
```

## R — patchwork assembly

```r
# INPUT : ggplot objects p_a, p_b, p_c
# OUTPUT: assembled figure with tags
# DEPENDS: patchwork, biostyle.R
library(patchwork)
combo <- (p_a | p_b) / p_c +
  plot_layout(heights = c(1, 1.3)) +
  panel_tags() +
  plot_annotation(theme = theme_biostyle())
save_fig_r(combo, "fig_patchwork", width = col_mm("double"), height = 120)
```

- `p1 + p2` side by side; `p1 / p2` stacked; `|` and `/` mix with parentheses.
- `plot_layout(guides = "collect")` merges identical legends — use it when
  panels share a categorical scale.
- ComplexHeatmap objects combine with patchwork via `wrap_elements(ht)`.

## R — cowplot alignment

```r
# INPUT : ggplot objects with different panel sizes
# OUTPUT: pixel-aligned composite
# DEPENDS: cowplot, biostyle.R
library(cowplot)
combo <- plot_grid(p_a, p_b, labels = c("a", "b"), ncol = 2,
                   align = "h", axis = "lb", label_size = 11,
                   label_fontface = "bold")
save_fig_r(combo, "fig_cowplot", width = col_mm("double"), height = 70)
```

## Export settings that matter

- SVG text editable: Python `svg.fonttype = "none"` (set by `use_style`);
  R `svglite` (used by `save_fig_r`).
- PNG 300 dpi at journal width: `save_fig`/`save_fig_r` defaults.
- PDF for submission: `fig.savefig("fig.pdf")` with `pdf.fonttype = 42`
  (set by `use_style`) so fonts embed as text, not paths.
- Rasterize huge point clouds inside vector figures: `ax.scatter(...,
  rasterized=True)` keeps SVG small while text stays vector.
- Version filenames (`fig1_v1`, `fig1_v2`) — never overwrite a figure the
  user may be comparing.

## Panel-tag conventions

- Bold lowercase a, b, c (Nature style) or A, B, C (Cell style) — pick one
  per deliverable and stay consistent.
- Position: top-left, outside the axes (`x=-0.14, y=1.06` in axes fraction,
  as in `panel_labels`).
- R: patchwork `tag_levels` via `panel_tags()`; cowplot `labels=` argument.
