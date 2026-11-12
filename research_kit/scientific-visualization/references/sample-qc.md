> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Sample-level & quantification QC

Figures for sample quality: library size, RLE, sample correlation, PCA
outliers, batch before/after integration, covariate association, missingness,
CV, and normalization shift. Inputs are plain DataFrames (metrics per sample
or feature) derived from colData, assay matrices, or proteomics/ metabolomics
tables. Color sample-level QC by **batch or QC group**, not by biology,
unless the question is confounding.

```python
# shared setup for every template in this file
import sys; sys.path.insert(0, "<skill-dir>/scripts")
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from qcstyle import (use_style, save_fig, journal_size, cat_palette,
                     seq_cmap, div_cmap, beautify, grid_axis, add_colorbar)
use_style("journal")
```

### libsize_bar — Library-size bars with median line `id: libsize_bar`

Total reads/counts per sample, sorted, colored by group, with the median
line. Bars far below the median are the first candidates for filtering.

```python
# INPUT : DataFrame lib, columns: sample, size (total counts), group
# OUTPUT: fig_qc_libsize.png/svg
# DEPENDS: matplotlib, numpy
lib = lib.sort_values("size", ignore_index=True)
groups = sorted(lib["group"].unique(), key=str)
gcol = dict(zip(groups, cat_palette(len(groups))))
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.6))
ax.bar(lib["sample"], lib["size"] / 1e6,
       color=[gcol[g] for g in lib["group"]], width=0.72)
med = float(np.median(lib["size"])) / 1e6
ax.axhline(med, color="#1A1A1A", lw=0.9, ls=(0, (4, 3)))
ax.annotate(f"median {med:.1f}M", xy=(1, med), xycoords=("axes fraction", "data"),
            xytext=(3, 2), textcoords="offset points", fontsize=7, va="bottom")
ax.set(xlabel="", ylabel="Library size (M reads)")
ax.tick_params(axis="x", rotation=60)
handles = [plt.Rectangle((0, 0), 1, 1, color=gcol[g]) for g in groups]
ax.legend(handles, groups, title=None, ncol=min(3, len(groups)))
beautify(ax)
save_fig(fig, "fig_qc_libsize")
```

### rle_plot — Relative log expression `id: rle_plot`

RLE boxes per sample (each gene's log2 deviation from its median across
samples). After good normalization, boxes hug zero with similar spread;
a shifted or squeezed box flags a failed library.

```python
# INPUT : ndarray mat (features x samples, log2 normalized); list samples
# OUTPUT: fig_qc_rle.png/svg
# DEPENDS: matplotlib, numpy
from scipy.sparse import issparse
if issparse(mat):                     # accept csr/dense alike
    mat = np.asarray(mat.todense())
rle = mat - np.median(mat, axis=1, keepdims=True)
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.6))
bp = ax.boxplot(rle, widths=0.6, showfliers=False, patch_artist=True,
                medianprops=dict(color="#1A1A1A", lw=1.2),
                boxprops=dict(facecolor="#B9C4CF", lw=0.8),
                whiskerprops=dict(color="#1A1A1A", lw=0.8),
                capprops=dict(color="#1A1A1A", lw=0.8))
ax.axhline(0, color="#1A1A1A", lw=0.8)
ax.set_xticks(range(1, len(samples) + 1), samples, rotation=60,
              ha="right", fontsize=7)
ax.set(xlabel="", ylabel="Log2 deviation from median")
beautify(ax)
save_fig(fig, "fig_qc_rle")
```

### sample_corr — Sample correlation heatmap with groups `id: sample_corr`

Pairwise Spearman correlation with group color strips on top and left;
replicates of one group should form a bright diagonal block. Off-diagonal
brightness across groups hints at batch or contamination.

```python
# INPUT : ndarray mat (features x samples, log2); list samples; list groups
# OUTPUT: fig_qc_sample_corr.png/svg
# DEPENDS: matplotlib, numpy, pandas
import matplotlib as mpl
from scipy.sparse import issparse
if issparse(mat):                     # accept csr/dense alike
    mat = np.asarray(mat.todense())
rho = pd.DataFrame(mat).corr(method="spearman").to_numpy()
ugroups = list(dict.fromkeys(groups))          # unique, for the palette
gcol = dict(zip(ugroups, cat_palette(len(ugroups))))
fig, ax = plt.subplots(figsize=journal_size("single", 0.85))
im = ax.imshow(rho, cmap="mako", vmin=0.5, vmax=1.0)
ax.set_xticks(range(len(samples)), samples, rotation=90, fontsize=6)
ax.set_yticks(range(len(samples)), samples, fontsize=6)
for i, g in enumerate(groups):   # one strip cell per sample (groups = per-sample labels)
    ax.add_patch(mpl.patches.Rectangle((i - .5, len(samples) - .5), 1, .28,
                 color=gcol[g], clip_on=False, lw=0))
    ax.add_patch(mpl.patches.Rectangle((-0.78, i - .5), .28, 1,
                 color=gcol[g], clip_on=False, lw=0))
add_colorbar(fig, im, ax, label="Spearman rho")
ax.set(xlabel="", ylabel="")
save_fig(fig, "fig_qc_sample_corr")
```

### pca_outlier — PCA with outlier flagging `id: pca_outlier`

PC1/PC2 scatter colored by QC group with a 95% confidence ellipse per group
and outliers labeled by sample id. Use the *residual* PCA (regress out known
covariates) when hunting outliers, the raw PCA when hunting batch.

```python
# INPUT : DataFrame pcs, columns: PC1, PC2, sample, group
# OUTPUT: fig_qc_pca_outlier.png/svg
# DEPENDS: matplotlib, numpy
from matplotlib.patches import Ellipse
fig, ax = plt.subplots(figsize=journal_size("single", 0.85))
groups = sorted(pcs["group"].unique(), key=str)
for g, c in zip(groups, cat_palette(len(groups))):
    d = pcs[pcs["group"] == g]
    ax.scatter(d["PC1"], d["PC2"], s=26, color=c, lw=0, label=g, zorder=3)
    xy = d[["PC1", "PC2"]].to_numpy()
    ctr, cov = xy.mean(0), np.cov(xy.T)
    ev, evec = np.linalg.eigh(cov)
    ang = np.degrees(np.arctan2(evec[1, 1], evec[0, 1]))
    w, h = 2 * 2.45 * np.sqrt(ev)          # ~95% chi2 ellipse
    ax.add_patch(Ellipse(ctr, w, h, angle=ang, fill=False,
                         color=c, lw=1.0, alpha=0.8))
    d2 = (xy - ctr) @ np.linalg.solve(cov, (xy - ctr).T)
    for k in np.where(d2.diagonal() > 5.99)[0]:   # Mahalanobis outliers
        ax.annotate(d["sample"].iloc[k], xy[k], xytext=(4, 4),
                    textcoords="offset points", fontsize=6.5, color="#D55E00")
ax.set(xlabel="PC1", ylabel="PC2")
ax.legend(title=None)
beautify(ax)
save_fig(fig, "fig_qc_pca_outlier")
```

### batch_umap — Integration before/after `id: batch_umap`

Two UMAP panels with identical limits: cells colored by batch before and
after integration. Batch mixing (not separation) after integration is the
pass signal; biology coloring belongs in a separate figure.

```python
# INPUT : DataFrame emb, columns: x, y, batch, stage ("before"/"after")
# OUTPUT: fig_qc_batch_umap.png/svg
# DEPENDS: matplotlib, numpy
batches = sorted(emb["batch"].unique(), key=str)
bcol = dict(zip(batches, cat_palette(len(batches))))
fig, axes = plt.subplots(1, 2, figsize=journal_size("double", 0.55),
                         sharex=True, sharey=True)
for ax, stage in zip(axes, ["before", "after"]):
    d = emb[emb["stage"] == stage]
    for b in batches:
        dd = d[d["batch"] == b]
        ax.scatter(dd["x"], dd["y"], s=3, color=bcol[b], lw=0, label=b)
    ax.set(title=stage.capitalize(), xlabel="UMAP 1", ylabel="UMAP 2")
    beautify(ax)
handles = [plt.Line2D([], [], marker="o", ls="", color=bcol[b], ms=5)
           for b in batches]
axes[1].legend(handles, batches, title=None, loc="upper right")
save_fig(fig, "fig_qc_batch_umap")
```

### confounder_assoc — Covariate–PC association heatmap `id: confounder_assoc`

-log10(p) of covariate-vs-PC tests (linear/anova) for the first ~6 PCs.
Covariates that light up early PCs explain major variance — confounders if
they are not the biology of interest.

```python
# INPUT : DataFrame assoc, columns: covariate, PC, nlp (-log10 p)
# OUTPUT: fig_qc_confounder.png/svg
# DEPENDS: matplotlib, numpy, pandas
M = assoc.pivot(index="covariate", columns="PC", values="nlp")
M = M.reindex(columns=sorted(M.columns, key=str))
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
im = ax.imshow(M.to_numpy(), cmap="rocket", aspect="auto",
               vmin=0, vmax=np.nanmax(M.to_numpy()))
ax.set_xticks(range(M.shape[1]), M.columns)
ax.set_yticks(range(M.shape[0]), M.index, fontsize=7)
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        v = M.iloc[i, j]
        if np.isfinite(v):
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6,
                    color="white" if v > 0.6 * np.nanmax(M.to_numpy()) else "#1A1A1A")
add_colorbar(fig, im, ax, label="-log10(p)")
ax.set(xlabel="", ylabel="")
save_fig(fig, "fig_qc_confounder")
```

### missing_pattern — Missingness matrix + rates `id: missing_pattern`

Left: boolean matrix of missing values (features x samples), missing = dark.
Right: per-feature missing-rate bars with the removal-threshold line.
Proteomics/metabolomics staple; also use for clinical covariate tables.

```python
# INPUT : DataFrame obs (features x samples, values or NaN)
#         float drop_thr (per-feature missing fraction threshold)
# OUTPUT: fig_qc_missing.png/svg
# DEPENDS: matplotlib, numpy
miss = obs.isna().to_numpy()
rate = miss.mean(axis=1)
order = np.argsort(-rate)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=journal_size("double", 0.8),
                               gridspec_kw=dict(width_ratios=[4, 1], wspace=0.04),
                               sharey=True)
ax1.imshow(miss[order], cmap="mako", aspect="auto", interpolation="nearest")
ax1.set_xticks(range(obs.shape[1]), obs.columns, rotation=90, fontsize=6)
ax1.set_yticks([])
ax1.set(xlabel="", ylabel="Features (sorted by missing rate)")
ax2.barh(range(len(rate)), rate[order] * 100, color="#526272", height=0.8)
ax2.axvline(drop_thr * 100, color="#D55E00", lw=0.9, ls=(0, (4, 3)))
ax2.annotate(f"{drop_thr:.0%}", xy=(drop_thr * 100, 0.02),
             xycoords=("data", "axes fraction"), xytext=(3, 0),
             textcoords="offset points", fontsize=7, color="#D55E00", va="bottom")
ax2.set(xlabel="Missing (%)")
beautify(ax2)
save_fig(fig, "fig_qc_missing")
```

### cv_density — CV distribution before/after filtering `id: cv_density`

Coefficient-of-variation density per group, before and after QC filtering,
shared x-axis. Filtering should shift mass left (tighter technical noise)
without erasing real biological spread between groups.

```python
# INPUT : DataFrame cv, columns: value (CV %), stage ("raw"/"filtered"), group
# OUTPUT: fig_qc_cv_density.png/svg
# DEPENDS: matplotlib, numpy
stages = ["raw", "filtered"]
styles = {"raw": dict(ls=(0, (4, 3)), alpha=0.9), "filtered": dict(ls="-", alpha=1.0)}
groups = sorted(cv["group"].unique(), key=str)
fig, ax = plt.subplots(figsize=journal_size("single", 0.72))
from scipy.stats import gaussian_kde
xs = np.linspace(0, cv["value"].quantile(0.98), 200)
for gi, (g, c) in enumerate(zip(groups, cat_palette(len(groups)))):
    for st in stages:
        d = cv[(cv["group"] == g) & (cv["stage"] == st)]["value"].to_numpy()
        dens = gaussian_kde(d)(xs)
        ax.plot(xs, dens, color=c, lw=1.5 if st == "filtered" else 1.1,
                **styles[st], label=f"{g} ({st})" if st == "filtered" else None)
        ax.fill_between(xs, dens, color=c, alpha=0.08, lw=0)
ax.set(xlabel="Coefficient of variation (%)", ylabel="Density", xlim=(0, xs[-1]))
ax.legend(title=None)
beautify(ax)
save_fig(fig, "fig_qc_cv_density")
```

### norm_density — Normalization shift `id: norm_density`

Offset-stacked intensity/log-count distributions before and after
normalization (ridges, one row per sample). After normalization every row's
peak should sit at the same x; residual spread means scale-invariant
differences remain.

```python
# INPUT : DataFrame dens, columns: x (log2 intensity bin), density, sample, stage
# OUTPUT: fig_qc_norm_density.png/svg
# DEPENDS: matplotlib, numpy
samples = sorted(dens["sample"].unique(), key=str)
stages = ["before", "after"]
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.9))
cmap = plt.get_cmap("mako")
for k, s in enumerate(samples):
    for si, st in enumerate(stages):
        d = dens[(dens["sample"] == s) & (dens["stage"] == st)]
        d = d.sort_values("x")
        y = d["density"] / d["density"].max()
        off = k * 1.1 + si * 0.45
        ax.fill_between(d["x"], off, off + y, color=cmap(k / max(1, len(samples) - 1)),
                        alpha=0.75, lw=0)
        ax.plot(d["x"], off + y, color="#1A1A1A", lw=0.4, alpha=0.5)
ax.set_yticks([k * 1.1 + 0.45 for k in range(len(samples))], samples, fontsize=7)
ax.set(xlabel="Log2 intensity", ylabel="")
ax.spines[["left"]].set_visible(False)
ax.tick_params(axis="y", length=0)
save_fig(fig, "fig_qc_norm_density")
```
