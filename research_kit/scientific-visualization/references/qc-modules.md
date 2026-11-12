> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# QC workflow sets & dashboard

End-to-end QC figure sets: which templates to run in which order, the
four-panel dashboard composite, and the threshold-report convention that
pairs every figure set with machine-readable pass/fail counts.

## QC workflow sets

| Module | Stage | Inputs | Outputs |
|---|---|---|---|
| `seq-qc` | Read level | per-cycle metrics, mapping stats | per_base_quality, base_composition, adapter_content, dup_insert, mapping_summary |
| `lib-qc` | Library complexity | barcode ranks, saturation table | knee_rank, saturation_curve |
| `sample-qc` | Sample level | log2 matrix + colData | libsize_bar, rle_plot, sample_corr, pca_outlier |
| `batch-qc` | Batch / confounding | embeddings + covariate tests | batch_umap, confounder_assoc |
| `quant-qc` | Quantification | assay matrix (proteomics/metabolomics) | missing_pattern, cv_density, norm_density |

Order a full report as: read level → library → sample → batch → quantification.
Each module ends with a `qc_thresholds.json` sidecar (below).

## Threshold report convention

Every QC figure set ships a sidecar next to the figures:

```json
{
  "rules": [
    {"metric": "q30_pct", "op": ">=", "value": 80, "n_failed": 1, "samples_failed": ["S17"]},
    {"metric": "dup_pct", "op": "<=", "value": 20, "n_failed": 2, "samples_failed": ["S03", "S17"]},
    {"metric": "missing_pct", "op": "<=", "value": 30, "n_failed": 0, "samples_failed": []}
  ],
  "n_samples": 24, "n_passed_all": 21
}
```

Rules are the same values drawn on the figures — keep them in one place and
pass them to both.

```python
# shared setup for every template in this file
import sys; sys.path.insert(0, "<skill-dir>/scripts")
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from qcstyle import (use_style, save_fig, journal_size, cat_palette,
                     seq_cmap, div_cmap, beautify, grid_axis, add_colorbar)
use_style("journal")
```

## qc_dashboard — Four-panel QC summary `id: qc_dashboard`

One-glance cohort QC: library size, RLE, PCA with ellipse, sample
correlation. Use as the "Figure QC-1" of a report; keep per-figure versions
for the sections that zoom in.

```python
# INPUT : DataFrame lib (sample, size, group); ndarray mat (features x samples, log2)
#         list samples; list groups
# OUTPUT: fig_qc_dashboard.png/svg
# DEPENDS: matplotlib, numpy, pandas
from matplotlib.patches import Ellipse
fig, axes = plt.subplots(2, 2, figsize=journal_size("double", 1.0))
(ax_lib, ax_pca), (ax_rle, ax_cor) = axes

# (a) library size, colored by group
lib = lib.sort_values("size", ignore_index=True)
gcol = dict(zip(sorted(set(lib["group"]), key=str), cat_palette(lib["group"].nunique())))
ax_lib.bar(lib["sample"], lib["size"] / 1e6,
           color=[gcol[g] for g in lib["group"]], width=0.7)
med = float(np.median(lib["size"])) / 1e6
ax_lib.axhline(med, color="#1A1A1A", lw=0.8, ls=(0, (4, 3)))
ax_lib.set(xlabel="", ylabel="Library size (M reads)")
ax_lib.tick_params(axis="x", rotation=60, labelsize=5)
beautify(ax_lib)

# (b) PCA with 95% ellipse
from sklearn.decomposition import PCA
xy = PCA(n_components=2).fit_transform(mat.T)
pcs = pd.DataFrame(xy, columns=["PC1", "PC2"])
pcs["group"] = groups
for g, c in gcol.items():
    d = pcs[pcs["group"] == g]
    ax_pca.scatter(d["PC1"], d["PC2"], s=18, color=c, lw=0, label=g)
    p = d[["PC1", "PC2"]].to_numpy()
    ctr, cov = p.mean(0), np.cov(p.T)
    ev, evec = np.linalg.eigh(cov)
    ang = np.degrees(np.arctan2(evec[1, 1], evec[0, 1]))
    ax_pca.add_patch(Ellipse(ctr, 2 * 2.45 * np.sqrt(ev[1]),
                             2 * 2.45 * np.sqrt(ev[0]), angle=ang,
                             fill=False, color=c, lw=0.9, alpha=0.8))
ax_pca.set(xlabel="PC1", ylabel="PC2")
ax_pca.legend(title=None, fontsize=6)
beautify(ax_pca)

# (c) RLE
rle = mat - np.median(mat, axis=1, keepdims=True)
ax_rle.boxplot(rle, widths=0.6, showfliers=False, patch_artist=True,
               medianprops=dict(color="#1A1A1A", lw=1.0),
               boxprops=dict(facecolor="#B9C4CF", lw=0.6),
               whiskerprops=dict(color="#1A1A1A", lw=0.6),
               capprops=dict(color="#1A1A1A", lw=0.6))
ax_rle.axhline(0, color="#1A1A1A", lw=0.7)
ax_rle.set_xticks(range(1, len(samples) + 1), samples, rotation=60,
                  ha="right", fontsize=5)
ax_rle.set(xlabel="", ylabel="Log2 deviation from median")
beautify(ax_rle)

# (d) sample correlation
rho = pd.DataFrame(mat).corr(method="spearman").to_numpy()
im = ax_cor.imshow(rho, cmap="mako", vmin=0.5, vmax=1.0)
ax_cor.set_xticks(range(len(samples)), samples, rotation=90, fontsize=5)
ax_cor.set_yticks(range(len(samples)), samples, fontsize=5)
add_colorbar(fig, im, ax_cor, label="Spearman rho")

for lab, ax in zip("abcd", [ax_lib, ax_pca, ax_rle, ax_cor]):
    ax.set_title(lab, loc="left", fontweight="bold", fontsize=9)
save_fig(fig, "fig_qc_dashboard")
```
