> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Bulk Omics Figures

Bulk transcriptomics/proteomics visualization: differential expression,
sample quality, enrichment, survival. Data typically: DE result tables
(gene, log2FC, padj), count matrices + metadata, ORA/GSEA result tables,
expression + clinical data.

Read `scripts/biostyle.py` / `scripts/biostyle.R` usage in SKILL.md first.
Every template below assumes `use_style()` (Python) or `theme_biostyle()`
(R) has been applied.

## Catalog

| Question | Figure | Data input | Language | Template id |
|---|---|---|---|---|
| Which genes are DE and how strongly? | Volcano (labeled) | DE table | py / r | `volcano` |
| Global DE magnitude vs abundance | MA plot | DE table | py | `ma_plot` |
| Do samples cluster by condition? | Sample correlation heatmap | normalized matrix | r | `sample_corr` |
| Main variance directions + outliers | PCA with ellipses & loadings | normalized matrix + metadata | py | `pca_samples` |
| Coherent DE blocks across samples | DEG z-score heatmap (annotated) | matrix + DE list | r | `deg_heatmap` |
| Which pathways are enriched? | ORA dot plot | ORA table | py | `enrich_dot` |
| GSEA result at a glance | Running-score + NES bars | GSEA table + detail | py | `gsea_running` |
| Does a gene split survival? | KM curve with risk table | expression + clinical | r | `km_curve` |
| Multi-model / multi-covariate effects | Forest plot | coefficient table | py | `forest` |
| Overlap of several DE sets | UpSet plot | gene set list | py | `upset` |
| Pathway-gene relationships | Chord diagram | pathway-gene membership | r | `chord_go` |
| Expression distributions per group | Ridgeline | long-format expression | py | `ridge_expr` |
| Distribution + raw data + summary at once | Raincloud | long-format values | py / r | `raincloud` |
| Full gene population context | Volcano + marginals | DE table | py | `volcano_marginal` |
| Group separation + spread | PCA + marginal densities | PCs + condition | py | `pca_marginal` |
| Full GSEA evidence | Aligned ES/hit/metric tracks | GSEA detail table | py | `gsea_tracks` |
| Many comparisons as numbers | Effect + CI matrix | effect + CI tables | py | `effect_matrix` |
| Individual trajectories | Paired-observation lines | long-format subjects | py | `paired_trajectory` |
| Mutation landscape | Oncoprint | gene × sample variant table | r | `oncoprint` |
| Pathway activity per sample | Pathway-score heatmap | pathway score matrix | py | `enrich_heatmap` |
| Which module tracks which trait? | Module-trait correlation heatmap | eigengene × trait r + p | py | `module_trait` |
| 3-4+ treatment arms | Volcano grid (per contrast) | per-contrast DE tables | py | `contrast_grid` |

---

### volcano — Volcano plot `id: volcano`

```python
# INPUT : DataFrame de, columns: gene(str), log2FC(float), padj(float)
# OUTPUT: fig1_volcano.png/svg
# DEPENDS: matplotlib, adjustText(optional)
import numpy as np, matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
de = de.copy()
de["nlp"] = -np.log10(de["padj"].clip(lower=1e-300))   # -log10 padj (valid column name)
sig = (de.padj < 0.05) & (de.log2FC.abs() > 1)
up, down = sig & (de.log2FC > 0), sig & (de.log2FC < 0)

fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
ax.scatter(de.loc[~sig, "log2FC"], de.loc[~sig, "nlp"],
           s=6, c="#C7CDD4", lw=0, label=None)
ax.scatter(de.loc[up, "log2FC"], de.loc[up, "nlp"],
           s=10, c="#D55E00", lw=0, label=f"Up ({up.sum()})")
ax.scatter(de.loc[down, "log2FC"], de.loc[down, "nlp"],
           s=10, c="#0072B2", lw=0, label=f"Down ({down.sum()})")
ax.axvline(0, c="#999999", lw=0.6, ls="--")
for thr in (1, -1):
    ax.axvline(thr, c="#999999", lw=0.6, ls=":")
ax.axhline(-np.log10(0.05), c="#999999", lw=0.6, ls=":")

top = de[sig].nlargest(12, "nlp")
try:
    from adjustText import adjust_text
    texts = [ax.text(r.log2FC, r.nlp, r.gene, fontsize=7)
             for r in top[["log2FC", "nlp", "gene"]].itertuples()]
    adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="-", lw=0.4))
except ImportError:
    for i, r in enumerate(top.itertuples()):   # rank-staggered fallback
        ax.annotate(r.gene, (r.log2FC, r.nlp), fontsize=7,
                    xytext=(3, 2 + 9 * i), textcoords="offset points")
ax.set(xlabel="log$_2$ fold change", ylabel="-log$_{10}$ padj")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2,
          handletextpad=0, frameon=False)
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig1_volcano")
```

R twin (ggplot2 + ggrepel):

```r
# INPUT : de, columns: gene(chr), log2FC(num), padj(num)
# OUTPUT: fig1_volcano.png/svg
# DEPENDS: ggplot2, ggrepel, biostyle.R
library(ggplot2); library(ggrepel)
de$neglog10padj <- -log10(pmax(de$padj, 1e-300))
de$sig <- with(de, padj < 0.05 & abs(log2FC) > 1)
de$direction <- with(de, ifelse(!sig, "NS", ifelse(log2FC > 0, "Up", "Down")))
p <- ggplot(de, aes(log2FC, neglog10padj, colour = direction)) +
  geom_point(size = 1.1, alpha = 0.9) +
  geom_vline(xintercept = c(-1, 0, 1), linetype = c(3, 2, 3), colour = "grey55", linewidth = 0.3) +
  geom_hline(yintercept = -log10(0.05), linetype = 3, colour = "grey55", linewidth = 0.3) +
  geom_text_repel(data = subset(de, sig), aes(label = gene),
                  size = 2.4, max.overlaps = 14, seed = 1,
                  box.padding = 0.25, segment.colour = "grey40") +
  scale_colour_manual(values = c(Up = "#D55E00", Down = "#0072B2", NS = "#C7CDD4")) +
  labs(x = expression(log[2]~"fold change"), y = expression(-log[10]~"padj"),
       colour = NULL) +
  theme_biostyle()
save_fig_r(p, "fig1_volcano")
```

### ma_plot — MA plot `id: ma_plot`

```python
# INPUT : DataFrame de, columns: baseMean(float), log2FC(float), padj(float)
# OUTPUT: fig_ma.png/svg
# DEPENDS: matplotlib
import numpy as np, matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
x = np.log10(de.baseMean.clip(lower=1e-3))
sig = de.padj < 0.05
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
ax.scatter(x[~sig], de.log2FC[~sig], s=6, c="#C7CDD4", lw=0)
ax.scatter(x[sig], de.log2FC[sig], s=9, c="#0072B2", lw=0)
ax.axhline(0, c="#D55E00", lw=0.9)
# loess-like running mean of log2FC
order = np.argsort(x); k = max(30, len(x)//50)
roll = np.convolve(de.log2FC.to_numpy()[order], np.ones(k)/k, mode="same")
ax.plot(x.to_numpy()[order], roll, c="#E69F00", lw=1.4, label="running mean")
ax.set(xlabel="log$_{10}$ mean abundance", ylabel="log$_2$ fold change")
ax.legend(loc="best"); beautify(ax)
save_fig(fig, "fig_ma")
```

### sample_corr — Sample correlation heatmap `id: sample_corr`

```r
# INPUT : mat (genes x samples, normalized), meta (samples x condition)
# OUTPUT: fig_samplecorr.png/svg
# DEPENDS: ComplexHeatmap, circlize, biostyle.R
library(ComplexHeatmap); library(circlize)
cc <- colorRamp2(c(0.8, 0.9, 1.0), c("#0279EE", "#FAF9F3", "#FF9400"))
cor_mat <- cor(mat, method = "spearman")
ha_top <- HeatmapAnnotation(
  Condition = meta$condition,
  col = list(Condition = setNames(cat_palette(length(unique(meta$condition))),
                                       unique(meta$condition))),
  annotation_name_side = "left"
)
ht <- Heatmap(cor_mat, name = "Spearman r", col = cc,
              top_annotation = ha_top,
              column_title = "Sample-to-sample correlation",
              row_names_side = "left")
# NOTE (ComplexHeatmap 2.22): with a top_annotation present, do NOT also set
# heatmap_legend_param legend_direction="horizontal" or column_names_rot —
# the layout engine then misplaces all column names (overlapping pile-up).
# Keep the defaults and verify the rendered labels.
save_fig_r(ht, "fig_samplecorr", width = 120, height = 110)
```

### pca_samples — PCA with confidence ellipses `id: pca_samples`

```python
# INPUT : DataFrame mat (samples x genes, normalized), meta with 'condition'
# OUTPUT: fig_pca.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from scipy.stats import chi2
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify, panel_labels

use_style("journal")
pcs = PCA(n_components=2, svd_solver="full").fit_transform(mat)
evr = PCA(n_components=2, svd_solver="full").fit(mat).explained_variance_ratio_ * 100
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
for i, cond in enumerate(sorted(meta.condition.unique())):
    m = (meta.condition == cond).to_numpy()
    ax.scatter(pcs[m, 0], pcs[m, 1], s=34, c=cat_palette(len(meta.condition.unique()))[i],
               label=cond, edgecolor="white", linewidth=0.5, zorder=3)
    pts = pcs[m]
    ctr, cov = pts.mean(0), np.cov(pts.T)
    # 95% chi-square ellipse
    evals, evecs = np.linalg.eigh(cov)
    ang = np.degrees(np.arctan2(evecs[1, 1], evecs[0, 1]))
    w, h = 2 * np.sqrt(chi2.ppf(0.95, 2) * evals)
    ell = plt.matplotlib.patches.Ellipse(ctr, w, h, angle=ang, fill=False,
                                         lw=1.0, alpha=0.8)
    ax.add_patch(ell)
ax.set(xlabel=f"PC1 ({evr[0]:.1f}%)", ylabel=f"PC2 ({evr[1]:.1f}%)")
ax.legend(title="Condition", loc="best"); beautify(ax)
save_fig(fig, "fig_pca")
```

### deg_heatmap — DEG z-score heatmap with annotations `id: deg_heatmap`

```r
# INPUT : mat (genes x samples), genes (DE gene vector), meta (condition)
# OUTPUT: fig_deg_heatmap.png/svg
# DEPENDS: ComplexHeatmap, circlize, biostyle.R
library(ComplexHeatmap); library(circlize)
z <- t(scale(t(mat[intersect(genes, rownames(mat)), ])))
z[z >  2.5] <-  2.5; z[z < -2.5] <- -2.5   # clip outliers for contrast
col_fun <- colorRamp2(c(-2.5, 0, 2.5), c("#0072B2", "#FAF9F3", "#D55E00"))
ha <- HeatmapAnnotation(
  Condition = meta$condition,
  col = list(Condition = setNames(cat_palette(length(unique(meta$condition))),
                                  unique(meta$condition))))
ht <- Heatmap(z, name = "z-score", col = col_fun,
              top_annotation = ha,
              cluster_columns = TRUE, clustering_method_columns = "ward.D2",
              show_row_names = FALSE,      # enable only for short gene lists
              row_dend_width = unit(6, "mm"),
              heatmap_height = unit(110, "mm"))
save_fig_r(ht, "fig_deg_heatmap", width = 120, height = 120)
```

### enrich_dot — ORA dot plot `id: enrich_dot`

```python
# INPUT : DataFrame ora, columns: term(str), GeneRatio("k/n" str), padj(float), Count(int)
# OUTPUT: fig_enrich_dot.png/svg
# DEPENDS: matplotlib
import numpy as np, matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap, beautify

use_style("journal")
d = ora.nsmallest(12, "padj").sort_values("padj")          # top terms, ordered
d["rich"] = [int(k) / int(n) for k, n in d.GeneRatio.str.split("/")]
d["-log10p"] = -np.log10(d.padj)
fig, ax = plt.subplots(figsize=journal_size("single", 0.85))
sc = ax.scatter(d.rich, range(len(d)), s=d.Count * 4 + 20,
                c=d["-log10p"], cmap=seq_cmap("mako"), edgecolor="white", lw=0.5)
ax.set_yticks(range(len(d)), [t if len(t) <= 46 else t[:44] + "…" for t in d.term],
              fontsize=7)
ax.invert_yaxis()
ax.set(xlabel="Gene ratio (k/n)")
cb = plt.colorbar(sc, ax=ax, fraction=0.035, pad=0.02)
cb.set_label("-log$_{10}$ padj"); cb.outline.set_visible(False)
beautify(ax); ax.grid(False)
save_fig(fig, "fig_enrich_dot")
```

### gsea_running — GSEA running score + NES bars `id: gsea_running`

```python
# INPUT : DataFrame nes (columns: pathway, NES, padj);
#         dict detail {pathway: DataFrame(hit(bool), RUNES(float))} from GSEA detail
# OUTPUT: fig_gsea.png/svg (2 panels)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify, panel_labels

use_style("journal")
fig, axes = plt.subplots(1, 2, figsize=journal_size("double", 0.42),
                         gridspec_kw={"width_ratios": [1.4, 1]})
ax = axes[0]
d = detail[pathway_of_interest]
x = np.arange(len(d))
ax.plot(x, d.RUNES, c="#0072B2", lw=1.6)
hits = np.where(d.hit)[0]
ax.vlines(hits, 0, d.RUNES[hits], color="#D55E00", lw=0.8, alpha=0.7)
ax.set(xlabel="Genes in ranked list", ylabel="Running enrichment score",
       title=pathway_of_interest)
beautify(ax)

ax = axes[1]
top = nes.nsmallest(10, "padj").sort_values("NES")
colors = [cat_palette(2)[0] if v < 0 else cat_palette(2)[1] for v in top.NES]
ax.barh(range(len(top)), top.NES, color=colors, height=0.7)
ax.set_yticks(range(len(top)), top.pathway, fontsize=7)
ax.axvline(0, c="black", lw=0.8)
ax.set(xlabel="Normalized enrichment score")
beautify(ax); grid_axis(ax, "x", on=False)
panel_labels(fig, axes)
save_fig(fig, "fig_gsea")
```

### km_curve — Kaplan-Meier with risk table `id: km_curve`

```r
# INPUT : clin (columns: time(num), event(0/1), group(factor, e.g. High/Low expression))
# OUTPUT: fig_km.png/svg
# DEPENDS: survminer, survival, biostyle.R
library(survminer); library(survival)
fit  <- survfit(Surv(time, event) ~ group, data = clin)
pval <- surv_pvalue(fit, data = clin)$pval
p <- ggsurvplot(fit, data = clin,
  pval = paste0("log-rank p = ", signif(pval, 2)),
  pval.size = 3.2, pval.coord = c(0.65 * max(clin$time), 0.15),
  risk.table = TRUE, risk.table.height = 0.25,
  palette = cat_palette(2), linetype = 1,
  legend.labs = levels(clin$group), legend.title = "",
  xlab = "Time (months)", ylab = "Survival probability",
  surv.median.line = "hv",
  ggtheme = theme_biostyle(), tables.theme = theme_biostyle())
png_sw <- save_fig_r(p, "fig_km", width = 120, height = 110)
```

### forest — Forest plot `id: forest`

```python
# INPUT : DataFrame cox, columns: term(str), HR(float), lo(float), hi(float), p(float)
# OUTPUT: fig_forest.png/svg
# DEPENDS: matplotlib
import numpy as np, matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
d = cox.sort_values("HR")
y = np.arange(len(d))
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
ax.hlines(y, d.lo, d.hi, color="#0072B2", lw=1.6)
ax.scatter(d.HR, y, s=28, c="#0072B2", zorder=3, edgecolor="white", lw=0.5)
ax.axvline(1, c="#999999", lw=0.8, ls="--")
ax.set_xscale("log")
ax.set_xticks([0.5, 1, 2, 5, 10], ["0.5", "1", "2", "5", "10"])
ax.set_yticks(y, [t if len(t) <= 34 else t[:32] + "…" for t in d.term], fontsize=7)
ax.invert_yaxis()
ax.set(xlabel="Hazard ratio (log scale, 95% CI)")
beautify(ax); ax.grid(False)
save_fig(fig, "fig_forest")
```

### upset — UpSet plot for set overlaps `id: upset`

Matrix-layout intersection view (Lex et al. 2014) — Venn diagrams do not
scale past 3-4 sets. Uses the zero-dependency `biostyle.upset_plot`
(the `upsetplot` package breaks on pandas >= 3 copy-on-write; UpSetR is
the R alternative). Cite doi:10.1109/TVCG.2014.2346248 in publication.

```python
# INPUT : dict sets {set_name: iterable of members (genes)}
# OUTPUT: fig_upset.png/svg
# DEPENDS: matplotlib (biostyle.upset_plot)
from biostyle import use_style, save_fig, upset_plot

use_style("journal")
fig, ax = upset_plot(sets, max_shown=20)
save_fig(fig, "fig_upset")
```

### chord_go — Pathway-gene chord diagram `id: chord_go`

```r
# INPUT : df (columns: pathway(chr), gene(chr)) — membership of top genes in top pathways
# OUTPUT: fig_chord.png/svg
# DEPENDS: circlize, biostyle.R
library(circlize)
mat <- table(df$pathway, df$gene)
grid.col <- setNames(cat_palette(ncol(mat)), colnames(mat))
circos.clear()
par(mar = c(1, 1, 1, 1))
chordDiagram(mat, grid.col = grid.col,
             transparency = 0.55, annotationTrack = "grid",
             preAllocateTracks = list(track.height = 0.04))
draw_chord <- function() {          # function, not recordPlot(): replaying a
  circos.clear()                    # recorded plot across device types yields
  par(mar = c(1, 1, 1, 1))          # silently empty files
  chordDiagram(mat, grid.col = grid.col, transparency = 0.55,
               annotationTrack = "grid",
               preAllocateTracks = list(track.height = 0.04))
  circos.trackPlotRegion(track.index = 1, panel.fun = function(x, y) {
    sector.name <- get.cell.meta.data("sector.index")
    circos.text(CELL_META$xcenter, CELL_META$ycenter + 0.3, sector.name,
                facing = "clockwise", niceFacing = TRUE, cex = 0.6)
  }, bg.border = NA)
}
draw_chord()                        # preview on the current device
save_fig_r(draw_chord, "fig_chord", width = 120, height = 120)
```

### ridge_expr — Expression ridgeline per group `id: ridge_expr`

```python
# INPUT : DataFrame long, columns: group(str/categorical), expr(float)  (one gene or one score)
# OUTPUT: fig_ridge.png/svg
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, ridge, cat_palette

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
order = long.groupby("group").expr.median().sort_values().index.tolist()
ridge(long, "expr", "group", order=order,
      palette=cat_palette(len(order)), ax=ax, overlap=0.85)
ax.set(xlabel="Expression (log$_2$ TPM)")
save_fig(fig, "fig_ridge")
```

### raincloud — Raincloud plot (cloud + rain + box) `id: raincloud`

Full distribution, every raw observation, and robust summary in one panel —
prefer it over plain boxplots whenever raw data can be shown.

```python
# INPUT : DataFrame long, columns: group(str), value(float)
# OUTPUT: fig_raincloud.png/svg
# DEPENDS: matplotlib, scipy (biostyle.raincloud)
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, raincloud, cat_palette

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.55))
order = long.groupby("group").value.median().sort_values().index.tolist()
raincloud(long, "value", "group", order=order,
          palette=cat_palette(len(order)), ax=ax)
ax.set(xlabel="Group", ylabel="Value (unit)")
save_fig(fig, "fig_raincloud")
```

R twin (ggdist pattern — half-eye + box + dots):

```r
# INPUT : df with columns group(fct), value(num)
# OUTPUT: fig_raincloud.png/svg
# DEPENDS: ggdist, ggplot2, biostyle.R
library(ggplot2); library(ggdist)
p <- ggplot(df, aes(group, value, fill = group)) +
  ggdist::stat_halfeye(adjust = .5, width = .3, .width = 0,
                       justification = -.3, point_colour = NA) +
  geom_boxplot(width = .1, outlier.shape = NA) +
  ggdist::stat_dots(side = "left", dotsize = .3, justification = 1.1,
                    binwidth = .1) +
  scale_fill_biostyle() +
  labs(x = "Group", y = "Value (unit)") +
  theme_biostyle() + theme(legend.position = "none")
save_fig_r(p, "fig_raincloud")
```

### volcano_marginal — Volcano with marginal distributions `id: volcano_marginal`

Adds stacked edge histograms (log2FC below, -log10p right) so the reader
sees the full gene population, not only significant points.

```python
# INPUT : DataFrame de, columns: gene(str), log2FC(float), padj(float)
# OUTPUT: fig_volcano_marginal.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
import matplotlib.gridspec as gs
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
de = de.assign(nlp=-np.log10(de.padj.clip(lower=1e-300)))
sig = (de.padj < 0.05) & (de.log2FC.abs() > 1)
fig = plt.figure(figsize=journal_size("single", 1.15))
gspec = gs.GridSpec(2, 2, width_ratios=[4, 1], height_ratios=[1, 4],
                    hspace=0.05, wspace=0.05)
ax = fig.add_subplot(gspec[1, 0]); axx = fig.add_subplot(gspec[0, 0], sharex=ax)
axy = fig.add_subplot(gspec[1, 1], sharey=ax)
ax.scatter(de.loc[~sig, "log2FC"], de.loc[~sig, "nlp"], s=6, c="#C7CDD4", lw=0)
ax.scatter(de.loc[sig, "log2FC"], de.loc[sig, "nlp"], s=10,
           c=np.where(de.loc[sig, "log2FC"] > 0, "#D55E00", "#0072B2"), lw=0)
ax.axvline(0, c="#999999", lw=0.6, ls="--")
ax.axhline(-np.log10(0.05), c="#999999", lw=0.6, ls=":")
ax.set(xlabel="log$_2$ fold change", ylabel="-log$_{10}$ padj")
axx.hist(de.log2FC, bins=60, color="#9FB8CE", lw=0)
axx.axis("off")
axy.hist(de.nlp, bins=60, orientation="horizontal", color="#9FB8CE", lw=0)
axy.axis("off")
beautify(ax)
save_fig(fig, "fig_volcano_marginal")
```

### pca_marginal — PCA with marginal densities `id: pca_marginal`

```python
# INPUT : DataFrame pcs (columns: PC1, PC2), Series condition
# OUTPUT: fig_pca_marginal.png/svg
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt
import matplotlib.gridspec as gs
from scipy.stats import gaussian_kde
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig = plt.figure(figsize=journal_size("single", 1.1))
gspec = gs.GridSpec(2, 2, width_ratios=[3, 1], height_ratios=[1, 3],
                    hspace=0.05, wspace=0.05)
ax = fig.add_subplot(gspec[1, 0]); axx = fig.add_subplot(gspec[0, 0], sharex=ax)
axy = fig.add_subplot(gspec[1, 1], sharey=ax)
conds = sorted(condition.unique())
for i, c in enumerate(conds):
    m = (condition == c).to_numpy()
    col = cat_palette(len(conds))[i]
    ax.scatter(pcs.PC1[m], pcs.PC2[m], s=26, c=col, label=c,
               edgecolor="white", lw=0.5)
    for v, target, orient in [(pcs.PC1[m], axx, "v"), (pcs.PC2[m], axy, "h")]:
        kde = gaussian_kde(v)
        grid = np.linspace(v.min() - 1, v.max() + 1, 120)
        dens = kde(grid)
        if orient == "v":
            target.fill_between(grid, dens, color=col, alpha=0.6, lw=0)
        else:
            target.fill_betweenx(grid, dens, color=col, alpha=0.6, lw=0)
ax.set(xlabel="PC1 (34.2%)", ylabel="PC2 (21.7%)")
ax.legend(fontsize=7)
axx.axis("off"); axy.axis("off")
beautify(ax)
save_fig(fig, "fig_pca_marginal")
```

### gsea_tracks — GSEA aligned multi-track `id: gsea_tracks`

One pathway per row-block: ES curve, hit positions, and ranking metric
aligned on a shared x (ranked list) — the full-evidence alternative to a
single running-score line.

```python
# INPUT : DataFrame d, columns: rank(int), metric(float), hit(bool), RUNES(float)
#         (one pathway's GSEA detail, sorted by rank)
# OUTPUT: fig_gsea_tracks.png/svg (3 aligned tracks)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gs
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
fig = plt.figure(figsize=journal_size("onehalf", 0.8))
gspec = gs.GridSpec(3, 1, height_ratios=[2.2, 1, 1.6], hspace=0.08)
ax_es = fig.add_subplot(gspec[0]); ax_hit = fig.add_subplot(gspec[1], sharex=ax_es)
ax_m = fig.add_subplot(gspec[2], sharex=ax_es)
x = d.rank
ax_es.plot(x, d.RUNES, c="#0072B2", lw=1.6)
ax_es.set(ylabel="Running ES")
ax_hit.vlines(x[d.hit], 0, 1, c="#D55E00", lw=0.6)
ax_hit.set(ylabel="Hits", yticks=[])
ax_m.scatter(x, d.metric, s=1.5, c="#9FB8CE", lw=0)
ax_m.set(ylabel="Rank metric", xlabel="Rank in ordered list")
for a in (ax_es, ax_hit, ax_m): beautify(a)
save_fig(fig, "fig_gsea_tracks")
```

### effect_matrix — Effect + uncertainty matrix `id: effect_matrix`

Compact table-figure: one row per feature/gene, one column per comparison;
color = effect size, text = effect with CI. Good when many comparisons must
be read as numbers.

```python
# INPUT : DataFrame eff (index=feature, columns=comparison, values=effect);
#         DataFrame lo, hi (same shape, CI bounds)
# OUTPUT: fig_effect_matrix.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, div_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.9))
im = ax.imshow(eff.to_numpy(), cmap=div_cmap("brand"),
               vmin=-np.abs(eff.to_numpy()).max(), vmax=np.abs(eff.to_numpy()).max(),
               aspect="auto")
ax.set_xticks(range(eff.shape[1]), eff.columns, rotation=45, ha="right", fontsize=7)
ax.set_yticks(range(eff.shape[0]), eff.index, fontsize=6.5)
for i in range(eff.shape[0]):
    for j in range(eff.shape[1]):
        ax.text(j, i, f"{eff.iloc[i, j]:.2f}\n[{lo.iloc[i, j]:.2f}, {hi.iloc[i, j]:.2f}]",
                ha="center", va="center", fontsize=5.5,
                color="white" if abs(eff.iloc[i, j]) > 0.6 * np.abs(eff.to_numpy()).max()
                else "#1A1A1A")
for s in ax.spines.values(): s.set_visible(False)
add_colorbar(fig, im, ax, label="Effect (unit)")
save_fig(fig, "fig_effect_matrix")
```

### paired_trajectory — Paired-observation trajectories `id: paired_trajectory`

Longitudinal/paired design: one line per subject across time points,
colored by response group — shows individual trajectories instead of
group means only.

```python
# INPUT : DataFrame long, columns: subject(str), time(num), value(float), group(str)
# OUTPUT: fig_paired.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.75))
groups = sorted(long.group.unique())
pal = dict(zip(groups, cat_palette(len(groups))))
for (subj, g), d in long.groupby(["subject", "group"]):
    d = d.sort_values("time")
    ax.plot(d.time, d.value, c=pal[g], lw=0.8, alpha=0.55)
mean_traj = long.groupby(["group", "time"]).value.mean().reset_index()
for g in groups:
    m = mean_traj[mean_traj.group == g]
    ax.plot(m.time, m.value, c=pal[g], lw=2.6, label=f"{g} (mean)")
ax.set(xlabel="Time (unit)", ylabel="Value (unit)")
ax.legend(fontsize=7); beautify(ax)
save_fig(fig, "fig_paired")
```

### oncoprint — Mutation landscape `id: oncoprint`

ComplexHeatmap oncoPrint: genes × samples, variant types stacked per cell,
samples ordered by mutation burden, mutation-rate bar on top. The standard
cancer-cohort figure; keep to ≤30 genes (top altered).

```r
# INPUT : DataFrame mut (columns: gene, sample, variant)  # e.g. "Missense",
#         "Truncating", "Amplification"; one row per (gene, sample, variant)
# OUTPUT: fig_oncoprint.png/svg
# DEPENDS: ComplexHeatmap
source("scripts/biostyle.R")
library(ComplexHeatmap)

genes   <- names(sort(table(mut$gene), decreasing = TRUE))[1:min(30, length(unique(mut$gene)))]
samples <- names(sort(table(mut$sample), decreasing = TRUE))
mat <- matrix("", nrow = length(genes), ncol = length(samples),
              dimnames = list(genes, samples))
i <- match(mut$gene, genes); j <- match(mut$sample, samples)
ok <- !is.na(i) & !is.na(j)
mat[cbind(i[ok], j[ok])] <- mut$variant[ok]

col <- c(Missense = "#0072B2", Truncating = "#D55E00",
         Amplification = "#E69F00", Deletion = "#009E73")
alter_fun <- list(
  Missense      = function(x, y, w, h) grid::grid.rect(x, y, w * .9, h * .9,
                    gp = grid::gpar(fill = col[["Missense"]], col = NA)),
  Truncating    = function(x, y, w, h) grid::grid.rect(x, y, w * .9, h * .33,
                    gp = grid::gpar(fill = col[["Truncating"]], col = NA)),
  Amplification = function(x, y, w, h) grid::grid.rect(x, y, w * .9, h * .9,
                    gp = grid::gpar(fill = col[["Amplification"]], col = NA)),
  Deletion      = function(x, y, w, h) grid::grid.rect(x, y, w * .33, h * .9,
                    gp = grid::gpar(fill = col[["Deletion"]], col = NA)))
p <- oncoPrint(mat, get_type = function(x) x, alter_fun = alter_fun, col = col,
               top_annotation = HeatmapAnnotation(
                 Burden = anno_barplot(colSums(mat != ""), gp = grid::gpar(fill = "#526272"),
                                       height = unit(1.2, "cm"))),
               column_title = NULL, row_names_side = "left",
               column_names_rot = 0, pct_side = "right")
save_fig_r(p, "fig_oncoprint", width = 183, height = 110)
```

### enrich_heatmap — Pathway-score heatmap (two-way clustered) `id: enrich_heatmap`

GSVA/ssGSEA/AUCell pathway scores per sample with **two-way clustering**:
pathways (rows) cluster by activity pattern, samples (columns) cluster by
pathway profile — works for 2 conditions or 3-4+ treatment arms alike.
The bulk companion of `enrich_dot`: continuous activity instead of ORA
counts. Clip scores (±3 z) for contrast.

```python
# INPUT : DataFrame scores (pathways x samples, z-scored); Series condition
# OUTPUT: fig_enrich_heatmap.png/svg
# DEPENDS: matplotlib, seaborn, scipy
import matplotlib.pyplot as plt, numpy as np, seaborn as sns
from scipy.cluster.hierarchy import linkage, leaves_list
from biostyle import use_style, save_fig, journal_size, div_cmap

use_style("journal")
row_order = leaves_list(linkage(scores.to_numpy(), method="average"))
col_order = leaves_list(linkage(scores.to_numpy().T, method="average"))
S = scores.iloc[row_order, col_order].clip(-3, 3)
fig, ax = plt.subplots(figsize=journal_size("double", 0.7))
sns.heatmap(S, cmap=div_cmap("brand"), center=0, ax=ax, rasterized=True,
            cbar_kws=dict(label="Pathway score (z)"),
            xticklabels=True, yticklabels=True)
ax.tick_params(labelsize=6)
ax.set(xlabel="", ylabel="")
save_fig(fig, "fig_enrich_heatmap")
```

### contrast_grid — Multi-condition volcano grid `id: contrast_grid`

One volcano panel per contrast for 3-4+ treatment arms (each arm vs
control, or all pairwise). Shared axis limits and thresholds across panels
make effect sizes comparable; label only each contrast's top genes.

```python
# INPUT : DataFrame de, columns: contrast(str), gene, lfc, nlp  # nlp = -log10 padj
# OUTPUT: fig_contrast_grid.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size

use_style("journal")
contrasts = sorted(de.contrast.unique(), key=str)
ncol = min(3, len(contrasts)); nrow = -(-len(contrasts) // ncol)
fig, axes = plt.subplots(nrow, ncol, squeeze=False, sharex=True, sharey=True,
                         figsize=journal_size("double", 0.45 * nrow))
for ax, ct in zip(axes.ravel(), contrasts):
    sub = de[de.contrast == ct]
    sig = (sub.nlp > 2) & (sub.lfc.abs() > 1)
    ax.scatter(sub.lfc[~sig], sub.nlp[~sig], s=1.5, c="#C7C7C7", lw=0,
               rasterized=True)
    ax.scatter(sub.lfc[sig & (sub.lfc > 0)], sub.nlp[sig & (sub.lfc > 0)],
               s=2.5, c="#D55E00", lw=0, rasterized=True)
    ax.scatter(sub.lfc[sig & (sub.lfc < 0)], sub.nlp[sig & (sub.lfc < 0)],
               s=2.5, c="#0072B2", lw=0, rasterized=True)
    ax.axhline(2, c="#999999", lw=0.7, ls="--")
    ax.axvline(0, c="#999999", lw=0.7)
    for i, (_, r) in enumerate(sub.nlargest(2, "nlp").iterrows()):
        ax.annotate(r.gene, (r.lfc, r.nlp), fontsize=6, ha="center",
                    va="bottom", xytext=(0, 2 + 7 * i),
                    textcoords="offset points")   # stack colliding labels
    ax.set(title=str(ct), xlabel="log2 FC", ylabel="-log10 padj")
for ax in axes.ravel()[len(contrasts):]:
    ax.remove()
save_fig(fig, "fig_contrast_grid")
```

### module_trait — Module-trait correlation heatmap `id: module_trait`

WGCNA-style eigengene × trait Pearson correlations with significance stars.
The bridge from co-expression modules to phenotypes; color = r, text = r
and stars (state the test and n in the caption).

```python
# INPUT : DataFrame cor (modules x traits, Pearson r); DataFrame p (same shape)
# OUTPUT: fig_module_trait.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, div_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
im = ax.imshow(cor.to_numpy(), cmap=div_cmap("brand"), vmin=-1, vmax=1)
ax.set_xticks(range(cor.shape[1]), cor.columns, rotation=30, ha="right",
              fontsize=8)
ax.set_yticks(range(cor.shape[0]), cor.index, fontsize=8)
for i in range(cor.shape[0]):
    for j in range(cor.shape[1]):
        pv = p.iloc[i, j]
        stars = "***" if pv < 1e-3 else "**" if pv < 1e-2 else \
            "*" if pv < 0.05 else ""
        r = cor.iloc[i, j]
        ax.text(j, i, f"{r:.2f} {stars}".strip(), ha="center", va="center",
                fontsize=6.5, color="white" if abs(r) > 0.55 else "#222222")
add_colorbar(fig, im, ax, label="Pearson r")
save_fig(fig, "fig_module_trait")
```

---

## Beauty checklist (bulk)

- Order categories by effect size or hierarchy, never alphabetically by accident.
- Heatmaps: clip z-scores (±2.5) for contrast; annotate conditions as color
  bars, not as row-name prefixes.
- Volcano: label ≤ 12 genes; use adjustText/ggrepel; color only significant
  points, keep the rest light gray.
- Dot plots: encode two quantities (size = count/ratio, color = significance);
  state both encodings in the caption.
- KM: add risk table and median survival line; state censoring in caption.

## Common pitfalls

- Truncating the y-axis of volcano plots at a low -log10(p) ceiling and
  stacking points at the ceiling — clip honestly or use a broken axis.
- Coloring all points by significance with saturated colors: background must
  recede (light gray) so significant genes pop.
- PCA on raw counts instead of normalized/variance-stabilized values.
- Comparing NES across GSEA runs without a common ranking universe.
