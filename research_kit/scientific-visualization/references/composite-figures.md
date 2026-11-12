> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Composite Story Figures

Multi-panel "story figures" that combine layer-1 templates into one
deliverable. Each recipe lists panels, layout, and the assembly code
pattern. Assembly mechanics (GridSpec, patchwork, shared colorbars, panel
tags) are in `figure-assembly.md`.

## Universal rules

- One palette mapping for the whole figure: same condition/cluster/system =
  same color in every panel. Build a `dict` of colors first and pass it to
  every panel.
- Shared color scales for comparable quantitative panels (state the range).
- Panel tags a, b, c... (bold, top-left, outside the axes).
- One caption-level message per figure; the panel order tells the story
  left-to-right, top-to-bottom.
- Export at the target width (double column 183 mm for 2×2 composites).

## Recipes

### scRNA Figure-1 `id: scrna-fig1`

Panels: **a** UMAP clusters (`umap_clusters`) · **b** marker dot plot
(`dot_plot`) · **c** proportion stacked bars (`proportion_stack`) ·
**d** QC violin strip (`qc_triplet`, single panel).

```python
# INPUT : AnnData adata (processed, clustered, marker test done)
# OUTPUT: fig1_scrna.png/svg (2x2 composite, double column)
# DEPENDS: matplotlib, scanpy
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, panel_labels

use_style("journal")
fig, axes = plt.subplots(2, 2, figsize=journal_size("double", 0.55),
                         gridspec_kw={"height_ratios": [1.3, 1]})
# a: UMAP (render with the umap_clusters template onto axes[0,0])
# b: dot plot (render with the dot_plot template onto axes[0,1])
# c: proportions (render with the proportion_stack template onto axes[1,0])
# d: one QC violin (render with the qc_triplet logic onto axes[1,1])
panel_labels(fig, axes)
save_fig(fig, "fig1_scrna")
```

### Bulk DE story `id: bulk-de-story`

Panels: **a** PCA (`pca_samples`) · **b** sample correlation heatmap
(`sample_corr`) · **c** volcano (`volcano`) · **d** DEG heatmap
(`deg_heatmap`). Layout: 2×2, double column; heatmaps get their own
colorbars, PCA and volcano share the condition palette.

### MD summary `id: md-summary`

Panels: **a** RMSD overlay (`rmsd_overlay`) · **b** RMSF (`rmsf`) ·
**c** DCCM (`dccm`) · **d** FEL (`fel_2d`). Layout: 2×2, double column.
State simulation length and equilibration exclusion in the caption.

### ML benchmark 2×2 `id: ml-benchmark`

Panels: **a** ROC (`roc_multi`) · **b** PR (`pr_curve`) · **c** calibration
(`calibration`) · **d** confusion matrix of the best model (`confusion`).
Layout: 2×2, double column. Same model colors in a–c.

### Docking triage `id: docking-triage`

Panels: **a** funnel (`vs_funnel`) · **b** score heatmap (`score_heatmap`)
· **c–f** 3D pose grid of the top hit (`pose_grid_3d`). Layout: left column
a+b stacked, right 2×2 pose grid; double column.

### QM photochemistry `id: qm-photo`

Panels: **a** absorption/emission mirror (`emission_stokes`) · **b** orbital
levels (`orbitals`) · **c** IRC profile (`irc`). Layout: 1×3, double column;
energy axes aligned where comparable.

---

## Assembly pattern (Python)

```python
# INPUT : pre-rendered panel functions (from layer-1 templates)
# OUTPUT: composite figure
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, panel_labels

use_style("journal")
fig, axes = plt.subplots(2, 2, figsize=journal_size("double", 0.55),
                         gridspec_kw={"width_ratios": [1, 1],
                                      "height_ratios": [1.2, 1],
                                      "wspace": 0.28, "hspace": 0.34})
panel_a(axes[0, 0])   # each panel function draws into a provided ax
panel_b(axes[0, 1])
panel_c(axes[1, 0])
panel_d(axes[1, 1])
panel_labels(fig, axes)
save_fig(fig, "fig_composite")
```

Refactor layer-1 templates into `panel_x(ax)` functions when composing —
the templates are written to accept an `ax` where practical.

## Assembly pattern (R)

```r
# INPUT : ggplot objects p_a, p_b, p_c, p_d
# OUTPUT: composite figure
# DEPENDS: patchwork, biostyle.R
library(patchwork)
combo <- (p_a | p_b) / (p_c | p_d) +
  panel_tags() +
  plot_layout(widths = c(1, 1), heights = c(1.2, 1))
save_fig_r(combo, "fig_composite", width = col_mm("double"), height = 110)
```
