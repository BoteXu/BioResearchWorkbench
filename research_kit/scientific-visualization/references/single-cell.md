> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Single-Cell Figures

scRNA-seq visualization: embeddings, QC, marker genes, trajectories,
cell-cell communication. Data typically: AnnData (`.h5ad`) with
`obsm["X_umap"]`, `obs` annotations, `X` expression; or Scanpy objects.

Assumes Scanpy conventions; adapt column names to the user's object.
For R/Seurat users, port with `scRNA.seq` equivalents or export to
DataFrames and use the R templates in `bulk-omics.md` (heatmaps, KM).

## Catalog

| Question | Figure | Data input | Language | Template id |
|---|---|---|---|---|
| What cell types/clusters exist? | UMAP with cluster labels | obsm X_umap + obs cluster | py | `umap_clusters` |
| Where is a gene expressed? | Feature-plot grid | embedding + expression | py | `feature_grid` |
| Which markers define each cluster? | Dot plot (gene × cluster) | mean expr + %expressing | py | `dot_plot` |
| Does expression shift by condition? | Split violin | expr + cluster + condition | py | `split_violin` |
| Is QC filtering sound? | QC triplet + scatter | obs QC metrics | py | `qc_triplet` |
| How do proportions change? | Stacked proportion bars | obs cluster × condition | py | `proportion_stack` |
| What is the differentiation path? | Pseudotime trajectory | embedding + pseudotime | py | `trajectory` |
| Direction of movement? | RNA velocity stream | velocity field | py | `velocity_stream` |
| Who signals to whom? | LR bubble plot | LR communication scores | py | `cellcomm_bubble` |
| Marker blocks across clusters | Annotated marker heatmap | matrix + markers | r | `marker_heatmap` |
| Pathway activity per cell? | Gene-set score feature plot | embedding + score | py | `genescore` |
| How do identities flow? | Alluvial flow diagram | two annotations of same cells | py / r | `alluvial` |
| Identity × marker card page | Marker strips | mean expr + detection matrices | py | `marker_strip` |
| Two programs co- or exclusive? | Butterfly (dual enrichment) | two program scores per cell | py | `butterfly` |
| Where is one identity? | Gray-background highlight | embedding + one identity | py | `dim_highlight` |
| 3D structure of the embedding? | 3D scatter + 2D projections | 3D embedding + clusters | py | `scatter3d_projections` |
| Compare many genes at once? | Stacked violins | long-format expr per gene × cluster | py | `stacked_violin` |
| Smooth expression landscape? | Expression density (Nebulosa) | embedding + expression | py | `expr_density` |
| Genes along pseudotime? | Smoothed trajectory lines | pseudotime + expression | py | `pseudotime_lines` |
| Was barcoding deep enough? | Barcode rank (knee) plot | per-barcode UMI counts | py | `barcode_rank` |
| Consistent across samples? | Faceted embedding small multiples | embedding + sample/condition | py | `dim_facet` |
| Markers per identity? | One-vs-rest volcano grid | per-cluster DE tables | py | `onevsrest_grid` |
| Aneuploidy / large-scale CNV? | inferCNV-style heatmap | smoothed CNV matrix + chrom | py | `cnv_heatmap` |
| Velocity model sensible? | Spliced-unspliced phase portrait | spliced/unspliced counts | py | `velocity_phase` |
| Who signals to whom (global)? | LR chord diagram | aggregated LR weights | r | `cellcomm_chord` |
| Two markers co-expressed? | Two-gene overlay (red/blue mix) | embedding + two expressions | py | `feature_overlay` |
| Per-sample spread of proportions? | Proportion dots (color+shape) | samples × cluster proportions | py | `proportion_dots` |
| Which genes peak when? | Pseudotime-ordered heatmap | pseudotime + gene matrix | py | `pseudotime_heat` |

---

### umap_clusters — UMAP with cluster label boxes `id: umap_clusters`

```python
# INPUT : DataFrame emb (columns: x, y), obs-like Series clusters (categorical)
# OUTPUT: fig_umap.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
pal = cat_palette(clusters.nunique())
for i, c in enumerate(sorted(clusters.unique(), key=str)):
    m = (clusters == c).to_numpy()
    ax.scatter(emb.x[m], emb.y[m], s=1.6, c=pal[i], lw=0, rasterized=True)
    ctr = emb[m].median()
    ax.text(ctr.x, ctr.y, str(c), fontsize=8, fontweight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.22", fc="white", ec=pal[i], lw=0.9, alpha=0.9))
ax.set(xlabel="UMAP 1", ylabel="UMAP 2", xticks=[], yticks=[])
ax.set_aspect("equal")
for s in ax.spines.values(): s.set_visible(True)
save_fig(fig, "fig_umap")
```

### feature_grid — Feature-plot grid `id: feature_grid`

```python
# INPUT : DataFrame emb (x, y); DataFrame expr (cells x genes) for genes list
# OUTPUT: fig_features.png/svg (grid of panels, shared scale)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap

use_style("journal")
genes = list(expr.columns)[:8]
ncol = 4; nrow = -(-len(genes) // ncol)
fig, axes = plt.subplots(nrow, ncol, figsize=journal_size("double", 0.5 * nrow / ncol * 2))
vmax = np.quantile(expr[genes].to_numpy(), 0.99)   # shared color scale = honest comparison
for ax, g in zip(axes.flat, genes):
    sc = ax.scatter(emb.x, emb.y, c=expr[g], s=1.2, cmap=seq_cmap("mako"),
                    vmin=0, vmax=vmax, lw=0, rasterized=True)
    ax.set(title=g, xticks=[], yticks=[]); ax.set_aspect("equal")
for ax in axes.flat[len(genes):]: ax.axis("off")
cb = fig.colorbar(sc, ax=axes, fraction=0.02, pad=0.01)
cb.set_label("Expression"); cb.outline.set_visible(False)
save_fig(fig, "fig_features")
```

### dot_plot — Gene × cluster dot plot `id: dot_plot`

```python
# INPUT : DataFrame dp, index=genes, columns=clusters, values in [0,1] mean-scaled expression;
#         DataFrame pct, same shape, fraction of cells expressing
# OUTPUT: fig_dotplot.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, div_cmap

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.75))
X, Y = np.meshgrid(range(dp.shape[1]), range(dp.shape[0]))
sc = ax.scatter(X.ravel(), Y.ravel(), s=pct.to_numpy().ravel() * 260,
                c=dp.to_numpy().ravel(), cmap=div_cmap("brand"),
                vmin=-1.5, vmax=1.5, edgecolor="#333333", lw=0.4)
ax.set_xticks(range(dp.shape[1]), dp.columns)
ax.set_yticks(range(dp.shape[0]), dp.index, fontsize=7)
ax.invert_yaxis(); ax.set_aspect("equal")
for s in ax.spines.values(): s.set_visible(False)
ax.set(xlabel="Cluster", ylabel="")
cb = plt.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("Mean expression (z)"); cb.outline.set_visible(False)
save_fig(fig, "fig_dotplot")
```

### split_violin — Split violin by condition `id: split_violin`

```python
# INPUT : DataFrame long, columns: gene(str), cluster(str), condition(str), expr(float)
# OUTPUT: fig_split_violin.png/svg
# DEPENDS: matplotlib, seaborn
import matplotlib.pyplot as plt, seaborn as sns
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.6))
sns.violinplot(long, x="cluster", y="expr", hue="condition", split=True,
               inner="quart", gap=0.1, palette=cat_palette(2), ax=ax, cut=0)
ax.legend(title="", loc="upper right")
ax.set(xlabel="Cluster", ylabel="Expression (log-normalized)")
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_split_violin")
```

### qc_triplet — QC triplet + scatter `id: qc_triplet`

```python
# INPUT : DataFrame qc, columns: n_genes(int), n_counts(int), pct_mt(float)
# OUTPUT: fig_qc.png/svg (4 panels: 3 violins + 1 scatter with threshold lines)
# DEPENDS: matplotlib, seaborn
import matplotlib.pyplot as plt, seaborn as sns
from biostyle import use_style, save_fig, journal_size, beautify, panel_labels, seq_cmap

use_style("journal")
fig, axes = plt.subplots(1, 4, figsize=journal_size("double", 0.32))
for ax, col, lab in zip(axes[:3],
                        ["n_genes", "n_counts", "pct_mt"],
                        ["Genes detected", "UMI counts", "Mitochondrial %"]):
    sns.violinplot(y=qc[col], ax=ax, color="#0072B2", cut=0, inner=None, lw=0.6)
    ax.set(xlabel=lab, xticks=[], ylabel="")
    for thr, side in THRESHOLDS.get(col, []):        # e.g. {"pct_mt": [(10, "max")]}
        ax.axhline(thr, c="#D55E00", lw=1.0, ls="--")
axes[3].scatter(qc.n_counts, qc.n_genes, s=2, c=qc.pct_mt,
                cmap=seq_cmap("rocket_r"), lw=0, rasterized=True)
axes[3].set(xlabel="UMI counts", ylabel="Genes detected")
panel_labels(fig, axes)
save_fig(fig, "fig_qc")
```

### proportion_stack — Cell-proportion stacked bars `id: proportion_stack`

```python
# INPUT : DataFrame obs, columns: condition(str), cluster(str)
# OUTPUT: fig_props.png/svg
# DEPENDS: matplotlib, scipy.stats
import matplotlib.pyplot as plt, pandas as pd
from scipy.stats import chi2_contingency
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
ct = pd.crosstab(obs.condition, obs.cluster, normalize="index")
p = chi2_contingency(pd.crosstab(obs.condition, obs.cluster)).pvalue
fig, ax = plt.subplots(figsize=journal_size("single", 0.75))
bottom = pd.Series(0.0, index=ct.index)
for i, c in enumerate(ct.columns):
    ax.bar(ct.index, ct[c], bottom=bottom, color=cat_palette(len(ct.columns))[i],
           width=0.62, label=c, edgecolor="white", lw=0.4)
    bottom += ct[c]
ax.set(ylabel="Fraction of cells", ylim=(0, 1))
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7)
ax.text(0.99, 0.02, f"χ² p = {p:.1e}", transform=ax.transAxes,
        ha="right", fontsize=7)
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_props")
```

### trajectory — Pseudotime trajectory on embedding `id: trajectory`

```python
# INPUT : DataFrame emb (x, y); Series pseudotime (float 0-1); Series clusters
# OUTPUT: fig_traj.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
sc = ax.scatter(emb.x, emb.y, c=pseudotime, s=1.6, cmap=seq_cmap("flare"),
                lw=0, rasterized=True)
# smooth backbone: rolling median path through ordered cells
import pandas as pd
o = pd.DataFrame({"x": emb.x, "y": emb.y, "t": pseudotime}).sort_values("t")
roll = o.rolling(200, min_periods=20).median().dropna()
ax.plot(roll.x, roll.y, c="white", lw=2.2, alpha=0.9, zorder=4)
ax.plot(roll.x, roll.y, c="#333333", lw=0.8, zorder=5)
ax.set(xticks=[], yticks=[], xlabel="UMAP 1", ylabel="UMAP 2")
ax.set_aspect("equal")
add_colorbar(fig, sc, ax, label="Pseudotime")
save_fig(fig, "fig_traj")
```

### velocity_stream — RNA velocity stream `id: velocity_stream`

```python
# INPUT : AnnData adata with adata.obsm['X_umap'], adata.obsm['velocity_umap']
# OUTPUT: fig_velocity.png/svg
# DEPENDS: scvelo (pip install scvelo if missing)
import scvelo as scv
from biostyle import use_style, save_fig

use_style("journal")
scv.pl.velocity_embedding_stream(adata, basis="umap", color="clusters",
                                 palette="biostyle",   # falls back to default if absent
                                 title="", show=False, save=False)
fig = plt.gcf()
from biostyle import save_fig
save_fig(fig, "fig_velocity")
```

### cellcomm_bubble — Ligand-receptor bubble plot `id: cellcomm_bubble`

```python
# INPUT : DataFrame lr, columns: source(str), target(str), ligand(str), receptor(str), score(float)
# OUTPUT: fig_cellcomm.png/svg (bubble grid: y=LR pair, x=target, color=source)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
d = lr.nlargest(20, "score").assign(
    pair=lambda x: x.ligand + "–" + x.receptor + "  (" + x.source + ")")
pairs = d.pair.unique(); targets = sorted(d.target.unique())
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.8))
src_list = d.source.unique(); pal = dict(zip(src_list, cat_palette(len(src_list))))
for _, r in d.iterrows():
    ax.scatter(targets.index(r.target), list(pairs).index(r.pair),
               s=r.score / d.score.max() * 300 + 20, c=pal[r.source],
               edgecolor="white", lw=0.5, zorder=3)
ax.set_xticks(range(len(targets)), targets, rotation=45, ha="right", fontsize=7)
ax.set_yticks(range(len(pairs)), pairs, fontsize=6.5)
ax.invert_yaxis()
ax.set(xlabel="Target cell type", ylabel="Ligand–receptor (source)")
handles = [plt.Line2D([], [], marker="o", ls="", color=pal[s], label=s) for s in src_list]
ax.legend(handles=handles, title="Source", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7)
beautify(ax); ax.grid(False)
save_fig(fig, "fig_cellcomm")
```

### marker_heatmap — Annotated marker heatmap `id: marker_heatmap`

```r
# INPUT : mat (genes x cells or aggregated genes x clusters), markers (list per cluster), anno (cluster -> cell type)
# OUTPUT: fig_markers.png/svg
# DEPENDS: ComplexHeatmap, circlize, biostyle.R
library(ComplexHeatmap); library(circlize)
z <- t(scale(t(mat[unlist(markers), , drop = FALSE])))
z[z > 2.5] <- 2.5; z[z < -2.5] <- -2.5
col_fun <- colorRamp2(c(-2, 0, 2), c("#0072B2", "#FAF9F3", "#D55E00"))
row_ha <- rowAnnotation(
  Cluster = rep(names(markers), lengths(markers)),
  col = list(Cluster = setNames(cat_palette(length(markers)), names(markers))))
col_ha <- HeatmapAnnotation(CellType = anno,
                            col = list(CellType = setNames(cat_palette(length(unique(anno))), unique(anno))))
ht <- Heatmap(z, name = "z", col = col_fun,
              right_annotation = row_ha, top_annotation = col_ha,
              cluster_rows = FALSE, cluster_columns = TRUE,
              show_row_names = length(unlist(markers)) <= 60,
              column_split = anno, column_gap = unit(1.5, "mm"))
save_fig_r(ht, "fig_markers", width = 140, height = 120)
```

### genescore — Gene-set score feature plot `id: genescore`

```python
# INPUT : DataFrame emb (x, y); Series score (per-cell gene-set score, e.g. scanpy.tl.score_genes)
# OUTPUT: fig_genescore.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
fig, axes = plt.subplots(1, 2, figsize=journal_size("onehalf", 0.55))
for ax, (lab, vals, cmap) in zip(axes, [
        ("UMAP", score, seq_cmap("mako")),
        ("Distribution", score, None)]):
    if lab == "UMAP":
        sc = ax.scatter(emb.x, emb.y, c=vals, s=1.6, cmap=cmap, lw=0, rasterized=True)
        ax.set(xticks=[], yticks=[], xlabel="UMAP 1", ylabel="UMAP 2")
        ax.set_aspect("equal"); add_colorbar(fig, sc, ax, label="Score")
    else:
        ax.hist(vals, bins=60, color="#0072B2", lw=0)
        ax.set(xlabel="Score", ylabel="Cells")
        beautify(ax)
save_fig(fig, "fig_genescore")
```

### alluvial — Cell-identity flow (alluvial) `id: alluvial`

How cell identities flow between two (or more) annotations — e.g. before
vs after integration, or across time points.

```python
# INPUT : DataFrame obs, columns: from(str), to(str)  (two annotations of the same cells)
# OUTPUT: fig_alluvial.png/svg
# DEPENDS: matplotlib, pandas
import matplotlib.pyplot as plt, pandas as pd, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
ct = pd.crosstab(obs["from"], obs["to"], normalize="index")   # row fractions
fig, ax = plt.subplots(figsize=journal_size("single", 0.85))
left, right = ct.index.tolist(), ct.columns.tolist()
ly = np.concatenate([[0], np.cumsum(ct.sum(axis=1).to_numpy())])
ry = np.concatenate([[0], np.cumsum(ct.sum(axis=0).to_numpy())])
for i, f in enumerate(left):
    y0 = ct.loc[f].cumsum().shift(fill_value=0)
    for j, t in enumerate(right):
        w = ct.loc[f, t]
        if w <= 0: continue
        ax.fill_betweenx([ly[i] + y0[t], ly[i] + y0[t] + w], 0, 1,
                         color=cat_palette(len(left))[i], alpha=0.45, lw=0)
for i, f in enumerate(left):
    ax.text(-0.03, ly[i] + ct.loc[f].sum() / 2, f, ha="right", va="center", fontsize=7)
for j, t in enumerate(right):
    ax.text(1.03, ry[j] + ct[t].sum() / 2, t, ha="left", va="center", fontsize=7)
ax.set(xticks=[], yticks=[], xlim=(-0.35, 1.35))
for s in ax.spines.values(): s.set_visible(False)
save_fig(fig, "fig_alluvial")
```

R alternative: `ggalluvial::geom_flow` + `geom_stratum` on a Seurat
metadata data frame (see SCpubr `do_AlluvialPlot` for the pattern).

### marker_strip — Per-identity marker strips `id: marker_strip`

One row per identity, one column per marker: dot color = mean expression,
dot size = detection — a compact "identity card" page for many identities
and 2-8 markers, sharing one color scale.

```python
# INPUT : DataFrame mean_e (index=identity, columns=marker), DataFrame pct (same shape, 0-1)
# OUTPUT: fig_marker_strip.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.6))
X, Y = np.meshgrid(range(mean_e.shape[1]), range(mean_e.shape[0]))
vmax = np.quantile(mean_e.to_numpy(), 0.99)
sc = ax.scatter(X.ravel(), Y.ravel(), s=pct.to_numpy().ravel() * 300 + 12,
                c=mean_e.to_numpy().ravel(), cmap=seq_cmap("mako"),
                vmin=0, vmax=vmax, edgecolor="white", lw=0.5)
ax.set_xticks(range(mean_e.shape[1]), mean_e.columns, fontsize=8)
ax.set_yticks(range(mean_e.shape[0]), mean_e.index, fontsize=7)
ax.invert_yaxis(); ax.set_aspect("equal")
for s in ax.spines.values(): s.set_visible(False)
ax.set(xlabel="Marker", ylabel="Identity")
add_colorbar(fig, sc, ax, label="Mean expression")
save_fig(fig, "fig_marker_strip")
```

### butterfly — Dual-enrichment butterfly `id: butterfly`

Neftel/Tirosh-style: two gene-program scores on opposing axes — cells high
in program A drift left, program B right; the y axis is a second score.
Reveals co- vs mutually-exclusive state structure.

```python
# INPUT : DataFrame sc, columns: score_A(float), score_B(float), cluster(str)
# OUTPUT: fig_butterfly.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
clusters = sorted(sc.cluster.unique())
for i, c in enumerate(clusters):
    m = sc.cluster == c
    ax.scatter(sc.score_A[m] - sc.score_B[m], sc.score_A[m] + sc.score_B[m],
               s=2.5, c=cat_palette(len(clusters))[i], lw=0, rasterized=True, label=c)
ax.axvline(0, c="#999999", lw=0.8, ls="--")
ax.set(xlabel="A – B (program dominance)", ylabel="A + B (total program activity)")
ax.legend(title="Cluster", fontsize=7, loc="best")
beautify(ax)
save_fig(fig, "fig_butterfly")
```

### dim_highlight — Highlight one identity on embedding `id: dim_highlight`

dittoSeq/scCustomize-style highlight plot: every cell in uniform light gray,
the selected identity on top in full color. Use when the question is "where
is X?" — one panel per identity beats a 20-color legend. Reuse the identity's
project color (`identity_colors`) so it matches every other figure. Add
shape/letter overlays when color must survive grayscale printing.

```python
# INPUT : DataFrame emb (x, y); Series clusters; str focus (identity to highlight)
# OUTPUT: fig_highlight.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
ax.scatter(emb.x, emb.y, s=1.6, c="#E0E0E0", lw=0, rasterized=True)   # context
m = (clusters == focus).to_numpy()
hl = cat_palette(clusters.nunique())[sorted(clusters.unique(), key=str).index(focus)]
ax.scatter(emb.x[m], emb.y[m], s=2.6, c=hl, lw=0, rasterized=True)
ctr = emb[m].median()
ax.annotate(focus, (ctr.x, ctr.y), fontsize=9, fontweight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=hl, lw=1.0))
ax.set(xlabel="UMAP 1", ylabel="UMAP 2", xticks=[], yticks=[])
ax.set_aspect("equal")
for s in ax.spines.values(): s.set_visible(True)
save_fig(fig, "fig_highlight")
```

### scatter3d_projections — 3D embedding with companion 2D projections `id: scatter3d_projections`

Workbench D01 pattern: 3D scatters hide structure behind occlusion, so always
pair the 3D view with the three orthogonal 2D projections. Use orthographic
projection (`set_proj_type("ortho")`) — perspective distorts relative
distances — and light pane colors so points read through. Rename axis labels
to the real space (PC1-3, UMAP 1-3, force components...).

```python
# INPUT : DataFrame emb3 (columns: x, y, z); Series clusters (categorical)
# OUTPUT: fig_3d_projections.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, cat_palette

use_style("journal")
pal = cat_palette(clusters.nunique())
levels = sorted(clusters.unique(), key=str)
fig = plt.figure(figsize=(7.0, 6.4))
gs = fig.add_gridspec(2, 3, height_ratios=[1.15, 1])
ax3 = fig.add_subplot(gs[0, :], projection="3d")
ax3.set_proj_type("ortho")
for i, c in enumerate(levels):
    m = (clusters == c).to_numpy()
    ax3.scatter(emb3.x[m], emb3.y[m], emb3.z[m], s=2.0, c=pal[i], lw=0,
                rasterized=True)
ax3.view_init(elev=18, azim=-60)
ax3.set_box_aspect((1, 1, 1))
ax3.set(xlabel="Dim 1", ylabel="Dim 2", zlabel="Dim 3")
for axis in (ax3.xaxis, ax3.yaxis, ax3.zaxis):     # light panes, faint grid
    axis.pane.set_facecolor("#F6F8FA"); axis.pane.set_edgecolor("#DCE4E8")
    axis._axinfo["grid"].update(color="#DDE5E9", linewidth=0.55)
for slot, (yc, xc) in enumerate([("y", "x"), ("z", "x"), ("z", "y")]):
    ax = fig.add_subplot(gs[1, slot])
    for i, c in enumerate(levels):
        m = (clusters == c).to_numpy()
        ax.scatter(emb3[xc][m], emb3[yc][m], s=1.6, c=pal[i], lw=0,
                   rasterized=True)
    ax.set(xlabel=f"Dim {xc[-1]}", ylabel=f"Dim {yc[-1]}", xticks=[], yticks=[])
    ax.set_aspect("equal")
fig.subplots_adjust(wspace=0.22, hspace=0.12)
save_fig(fig, "fig_3d_projections")
```

### stacked_violin — Multi-gene stacked violins `id: stacked_violin`

scCustomize `Stacked_VlnPlot` pattern: one violin row per gene, clusters on
the shared x axis. Reads gene-by-gene top to bottom; keep rows to ≤8 genes
or the figure becomes a wall. White median bars keep rows comparable.

```python
# INPUT : DataFrame expr_long (columns: gene, cluster, value); list gene_order
# OUTPUT: fig_stacked_violin.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
clusters = sorted(expr_long.cluster.unique(), key=str)
pal = cat_palette(len(clusters))
fig, axes = plt.subplots(len(gene_order), 1, sharex=True,
                         figsize=journal_size("single", 0.38 * len(gene_order)))
for ax, g in zip(np.atleast_1d(axes), gene_order):
    sub = expr_long[expr_long.gene == g]
    data = [sub.value[sub.cluster == c].to_numpy() for c in clusters]
    vp = ax.violinplot(data, widths=0.85, showextrema=False)
    for body, ci in zip(vp["bodies"], pal):
        body.set_facecolor(ci); body.set_alpha(0.85); body.set_linewidth(0)
    q = [np.median(d) for d in data]
    ax.hlines(q, np.arange(1, len(clusters) + 1) - 0.16,
              np.arange(1, len(clusters) + 1) + 0.16,
              color="white", lw=1.2, zorder=3)
    ax.set_ylabel(g, rotation=0, ha="right", va="center", fontsize=8)
    ax.set_yticks([])
    beautify(ax)
ax_last = np.atleast_1d(axes)[-1]
ax_last.set_xticks(np.arange(1, len(clusters) + 1), clusters, fontsize=8)
save_fig(fig, "fig_stacked_violin")
```

### expr_density — Expression density on embedding (Nebulosa-style) `id: expr_density`

Nebulosa's core idea: kernel-density-smooth the embedding weighted by
expression, so sparse dropout-y markers read as a continuous landscape
instead of peppered dots. For a joint two-gene density use
`weights=(e1 + e2) / 2`. Density is relative — no colorbar units.

```python
# INPUT : DataFrame emb (x, y); Series expr (expression of one gene per cell)
# OUTPUT: fig_expr_density.png/svg
# DEPENDS: matplotlib, numpy, scipy
import matplotlib.pyplot as plt, numpy as np
from scipy.stats import gaussian_kde
from biostyle import use_style, save_fig, journal_size, seq_cmap

use_style("journal")
xy = np.column_stack([emb.x, emb.y])
kde = gaussian_kde(xy.T, weights=expr.to_numpy())
xg = np.linspace(emb.x.min(), emb.x.max(), 120)
yg = np.linspace(emb.y.min(), emb.y.max(), 120)
XX, YY = np.meshgrid(xg, yg)
Z = kde(np.column_stack([XX.ravel(), YY.ravel()]).T).reshape(XX.shape)
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
ax.contourf(XX, YY, Z, levels=40, cmap=seq_cmap("mako"))
ax.set(xlabel="UMAP 1", ylabel="UMAP 2", xticks=[], yticks=[])
ax.set_aspect("equal")
for s in ax.spines.values(): s.set_visible(True)
save_fig(fig, "fig_expr_density")
```

### pseudotime_lines — Genes along pseudotime `id: pseudotime_lines`

Smoothed expression trajectories along pseudotime: quantile-bin the cells,
plot bin means ± SEM. Robust alternative to raw scatter for showing
induction/repression waves; fits (splines, tradeSeq/GAMs) can replace the
binned means for publication.

```python
# INPUT : DataFrame pt with column pseudotime + one column per gene
# OUTPUT: fig_pseudotime_lines.png/svg
# DEPENDS: matplotlib, numpy, pandas
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
genes = ["CDK1", "LYZ", "GATA1"]                 # columns of pt to plot
pal = cat_palette(len(genes))
sub = pt.sort_values("pseudotime")
bins = pd.qcut(sub.pseudotime, 40, duplicates="drop")
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
for i, g in enumerate(genes):
    m = sub.groupby(bins, observed=True)[g].agg(["mean", "sem"])
    x = np.array([iv.mid for iv in m.index])
    ax.plot(x, m["mean"], c=pal[i], lw=1.6, label=g)
    ax.fill_between(x, m["mean"] - m["sem"], m["mean"] + m["sem"],
                    color=pal[i], alpha=0.18, lw=0)
ax.set(xlabel="Pseudotime", ylabel="Smoothed expression (mean ± SEM)")
ax.legend(fontsize=7, frameon=False, loc="best")
beautify(ax)
save_fig(fig, "fig_pseudotime_lines")
```

### barcode_rank — Barcode rank (knee) plot `id: barcode_rank`

Log-log rank vs total-UMI curve with the knee and the cell-calling cutoff
marked. The QC figure that justifies how many barcodes became cells; supply
`knee_rank` / `cell_rank` from the caller (dropletUtils, crtools, ...).

```python
# INPUT : array-like counts (total UMI per barcode, BEFORE cell calling);
#         int knee_rank, cell_rank (from knee/inflection detection)
# OUTPUT: fig_barcode_rank.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
counts = np.sort(np.asarray(counts, dtype=float))[::-1]
rank = np.arange(1, len(counts) + 1)
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
ax.plot(rank, counts, c="#0072B2", lw=1.4)
ax.set(xscale="log", yscale="log",
       xlabel="Barcode rank", ylabel="Total UMI count")
ax.axvline(knee_rank, c="#E69F00", lw=1.1, ls="--")
ax.axvline(cell_rank, c="#009E73", lw=1.1, ls="--")
ymax = counts.max()
ax.text(knee_rank * 1.15, ymax / 8, "knee", color="#B36900",
        fontsize=8, rotation=90)
ax.text(cell_rank * 1.15, ymax / 8, "cell cutoff", color="#00694E",
        fontsize=8, rotation=90)
beautify(ax)
save_fig(fig, "fig_barcode_rank")
```

### dim_facet — Faceted embedding small multiples `id: dim_facet`

One embedding panel per sample/condition/batch with shared limits and one
shared cluster palette — the honest way to check batch effects and
replicate consistency (a merged panel hides exactly this). Keep the same
axis limits on every panel; never re-embed per panel.

```python
# INPUT : DataFrame emb (x, y); Series groups (sample/condition/batch);
#         Series clusters
# OUTPUT: fig_dim_facet.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette

use_style("journal")
levels = sorted(groups.unique(), key=str)
clusters = sorted(clusters.unique(), key=str)
pal = dict(zip(clusters, cat_palette(len(clusters))))
ncol = min(4, len(levels)); nrow = -(-len(levels) // ncol)
fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                         figsize=journal_size("double", 0.5 * nrow))
xlim = (emb.x.min(), emb.x.max()); ylim = (emb.y.min(), emb.y.max())
for ax, lev in zip(axes.ravel(), levels):
    m = (groups == lev).to_numpy()
    for c in clusters:
        sel = m & (clusters == c).to_numpy()
        if sel.any():
            ax.scatter(emb.x[sel], emb.y[sel], s=1.2, c=pal[c], lw=0,
                       rasterized=True)
    ax.set(title=str(lev), xticks=[], yticks=[], xlim=xlim, ylim=ylim)
    ax.set_aspect("equal")
for ax in axes.ravel()[len(levels):]:
    ax.remove()
save_fig(fig, "fig_dim_facet")
```

### onevsrest_grid — One-vs-rest volcano grid `id: onevsrest_grid`

Per-identity volcano small multiples for cluster-marker DE. Same thresholds
and axis ranges across panels so identities are comparable; label only the
top hits or labels collide.

```python
# INPUT : DataFrame de (columns: cluster, gene, lfc, nlp)  # nlp = -log10(padj)
# OUTPUT: fig_onevsrest.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size

use_style("journal")
clusters = sorted(de.cluster.unique(), key=str)
ncol = min(4, len(clusters)); nrow = -(-len(clusters) // ncol)
fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                         figsize=journal_size("double", 0.5 * nrow))
for ax, c in zip(axes.ravel(), clusters):
    sub = de[de.cluster == c]
    up = (sub.lfc > 1) & (sub.nlp > 2)
    dn = (sub.lfc < -1) & (sub.nlp > 2)
    ns = ~(up | dn)
    ax.scatter(sub.lfc[ns], sub.nlp[ns], s=1.5, c="#C7C7C7", lw=0,
               rasterized=True)
    ax.scatter(sub.lfc[dn], sub.nlp[dn], s=2.5, c="#0072B2", lw=0,
               rasterized=True)
    ax.scatter(sub.lfc[up], sub.nlp[up], s=2.5, c="#D55E00", lw=0,
               rasterized=True)
    ax.axhline(2, c="#999999", lw=0.7, ls="--")
    ax.axvline(0, c="#999999", lw=0.7)
    for _, r in sub.nlargest(2, "nlp").iterrows():
        ax.annotate(r.gene, (r.lfc, r.nlp), fontsize=6, ha="center",
                    va="bottom")
    ax.set(title=f"{c} vs rest", xlabel="log2 FC", ylabel="-log10 padj")
for ax in axes.ravel()[len(clusters):]:
    ax.remove()
save_fig(fig, "fig_onevsrest")
```

### cnv_heatmap — inferCNV-style CNV heatmap `id: cnv_heatmap`

Cells (rows, ordered by cluster) × genes (columns, genomic order) smoothed
log2 copy ratios on a diverging scale centered at 0, with white chromosome
boundaries. The standard view for malignant-cell aneuploidy; supply the
reference-normalized matrix from inferCNV/copyKAT/HoneyBADGER.

```python
# INPUT : DataFrame cnv (cells x genes, smoothed log2 ratio; genes in genomic
#         order); Series cell_cluster (per cell, row order); Series chrom
#         (gene -> chromosome, same order as cnv columns)
# OUTPUT: fig_cnv.png/svg
# DEPENDS: matplotlib, numpy, pandas
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from biostyle import use_style, save_fig, journal_size, div_cmap, add_colorbar

use_style("journal")
M = cnv.to_numpy()
M = M[np.argsort(cell_cluster.to_numpy(), kind="stable")]
bounds = np.cumsum(chrom.value_counts(sort=False).to_numpy())[:-1]
fig, ax = plt.subplots(figsize=journal_size("double", 0.5))
im = ax.imshow(M, aspect="auto", cmap=div_cmap("brand"), vmin=-1, vmax=1,
               interpolation="nearest", rasterized=True)
ax.set_xticks([]); ax.set_yticks([])
for b in bounds:
    ax.axvline(b - 0.5, c="white", lw=0.7)
ax.set(xlabel="Genes (chromosomal order)", ylabel="Cells (ordered by cluster)")
add_colorbar(fig, im, ax, label="log2 copy ratio")
save_fig(fig, "fig_cnv")
```

### velocity_phase — Spliced-unspliced phase portrait `id: velocity_phase`

One gene's phase portrait: unspliced vs spliced counts with the recovered
steady-state line (slope = degradation rate γ). Cells above the line are
inducing, below repressing — the QC view behind RNA velocity. Draw for a
panel of driver genes, one small figure each.

```python
# INPUT : DataFrame ph (columns: spliced, unspliced) for ONE gene
# OUTPUT: fig_velocity_phase.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
ax.scatter(ph.spliced, ph.unspliced, s=8, c="#0072B2", alpha=0.45, lw=0,
           rasterized=True)
gamma, u0 = np.polyfit(ph.spliced, ph.unspliced, 1)   # steady-state ratio
s = np.linspace(0, ph.spliced.max() * 1.02, 50)
ax.plot(s, gamma * s + u0, c="#E69F00", lw=1.4,
        label=rf"steady state ($\gamma$ = {gamma:.2f})")
ax.set(xlabel="Spliced", ylabel="Unspliced")
ax.legend(fontsize=7, frameon=False, loc="best")
beautify(ax)
save_fig(fig, "fig_velocity_phase")
```

### cellcomm_chord — Ligand-receptor chord diagram `id: cellcomm_chord`

circlize chord diagram of aggregated ligand-receptor signaling
(source cell type → target cell type, weighted by mean LR score). The
global complement to the `cellcomm_bubble` matrix; keep ≤12 sectors or
labels tangle. Base graphics — pass the drawing code as a function to
`save_fig_r` (it re-runs per device; a `recordPlot()` replay across device
types writes silently empty files).

```r
# INPUT : DataFrame lr (columns: source, target, weight)  # aggregated LR scores
# OUTPUT: fig_cellcomm_chord.png/svg
# DEPENDS: circlize
source("scripts/biostyle.R")
library(circlize)

lev <- unique(c(lr$source, lr$target))
grid.col <- setNames(cat_palette(length(lev)), lev)
draw_chord <- function() {          # function, not recordPlot(): replaying a
  circos.clear()                    # recorded plot across device types yields
  chordDiagram(as.data.frame(lr[, c("source", "target", "weight")]),  # empty files
               grid.col = grid.col, transparency = 0.35,
               annotationTrack = "grid",
               preAllocateTracks = list(track.height = 0.08))
  circos.track(sectors = lev, ylim = c(0, 1), track.height = 0.04,
               bg.border = NA,
               panel.fun = function(x, y) {
                 circos.text(CELL_META$xcenter, CELL_META$ycenter,
                             CELL_META$sector.index, cex = 0.7,
                             facing = "clockwise", niceFacing = TRUE)
               })
}
draw_chord()                        # preview on the current device
save_fig_r(draw_chord, "fig_cellcomm_chord", width = 120, height = 120)
```

### feature_overlay — Two-gene overlay (red/blue mix) `id: feature_overlay`

Two markers on one embedding with additive channel mixing: gene 1 → red,
gene 2 → blue, co-expression → magenta. Reads co-expression structure that
side-by-side feature grids hide. Red/blue (not red/green) keeps it
colorblind-safe; state the channel assignment in the caption.

```python
# INPUT : DataFrame emb (x, y); Series e1, e2 (two gene expressions per cell)
# OUTPUT: fig_feature_overlay.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size

use_style("journal")
rgb = np.zeros((len(emb), 3))
rgb[:, 0] = np.clip(e1.to_numpy() / (np.percentile(e1, 99) + 1e-9), 0, 1)
rgb[:, 2] = np.clip(e2.to_numpy() / (np.percentile(e2, 99) + 1e-9), 0, 1)
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
ax.scatter(emb.x, emb.y, s=2.2, c=rgb, lw=0, rasterized=True)
ax.set(xlabel="UMAP 1", ylabel="UMAP 2", xticks=[], yticks=[])
ax.set_aspect("equal")
for s_ in ax.spines.values(): s_.set_visible(True)
save_fig(fig, "fig_feature_overlay")
```

### proportion_dots — Per-sample proportion dots `id: proportion_dots`

Per-sample cluster proportions as dots (color = cluster, shape = condition)
over group means — the honest version of stacked proportion bars, showing
donor-level spread instead of hiding n. Color + shape keeps it readable in
grayscale (dittoSeq principle).

```python
# INPUT : DataFrame prop (samples x clusters, proportions); Series condition
# OUTPUT: fig_proportion_dots.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
clusters = list(prop.columns)
pal = cat_palette(len(clusters))
conds = sorted(condition.unique(), key=str)
markers = ["o", "s", "^", "D"]
x = np.arange(len(clusters))
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
for k, cd in enumerate(conds):
    m = (condition == cd).to_numpy()
    for i, c in enumerate(clusters):
        y = prop.loc[m, c].to_numpy()
        jit = np.random.default_rng(k).uniform(-0.15, 0.15, len(y))
        ax.scatter(x[i] + jit, y, s=16, c=pal[i], marker=markers[k % 4],
                   alpha=0.8, lw=0, label=cd if i == 0 else None)
        mu = y.mean()
        ax.hlines(mu, x[i] - 0.22, x[i] + 0.22, color=pal[i],
                  ls="--" if k else "-", lw=1.4)
ax.set_xticks(x, clusters, fontsize=8)
ax.set(ylabel="Proportion")
ax.legend(title="Condition", fontsize=7, title_fontsize=7, frameon=False)
beautify(ax)
save_fig(fig, "fig_proportion_dots")
```

### pseudotime_heat — Pseudotime-ordered gene heatmap `id: pseudotime_heat`

Genes (rows, ordered by time of peak expression) × pseudotime (columns,
binned and smoothed), z-scored per gene. The compact companion of
`pseudotime_lines` for 30-100 genes; shows waves of induction/repression.

```python
# INPUT : DataFrame pt (column pseudotime + gene columns)
# OUTPUT: fig_pseudotime_heat.png/svg
# DEPENDS: matplotlib, numpy, pandas
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
genes = [c for c in pt.columns if c != "pseudotime"][:60]
bins = pd.qcut(pt.pseudotime, 50, duplicates="drop")
sm = pt.groupby(bins, observed=True)[genes].mean()
x = np.array([iv.mid for iv in sm.index])
order = np.argsort([np.argmax(sm[g].to_numpy()) for g in genes])
Z = sm.to_numpy()[:, order].T
Z = (Z - Z.mean(1, keepdims=True)) / (Z.std(1, keepdims=True) + 1e-9)
fig, ax = plt.subplots(figsize=journal_size("single", 1.1))
im = ax.imshow(Z, aspect="auto", cmap=seq_cmap("mako"), interpolation="nearest",
               extent=[x.min(), x.max(), len(genes) - 0.5, -0.5], rasterized=True)
ax.set(ylabel="Genes (ordered by peak time)", xlabel="Pseudotime", yticks=[])
add_colorbar(fig, im, ax, label="z (smoothed)")
save_fig(fig, "fig_pseudotime_heat")
```

---

## Beauty checklist (single-cell)

- Embeddings: equal aspect, no ticks, rasterized point layers (`rasterized=True`)
  so SVG stays small; label clusters with boxed text at median positions.
- Shared color scale across feature-grid panels; state vmax choice (99th
  percentile) in the caption.
- Dot plots: size = % expressing, color = mean expression; never encode two
  things in color.
- Proportions: order clusters consistently with the UMAP legend; add the
  chi-square/Fisher test result.
- Rasterize big scatters, keep text vector — file size and print quality.

## Common pitfalls

- Comparing UMAP distances or cluster areas across separately computed
  embeddings — always recompute on the integrated object.
- Violin `cut=None` default in seaborn extends beyond data range; use `cut=0`.
- Dot-plot color scale centered on data mid instead of a fixed z range —
  fix vmin/vmax for cross-figure comparability.
- Velocity arrows without stating the preprocessing (spliced/unliced, kNN).
