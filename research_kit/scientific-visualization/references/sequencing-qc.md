> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Read-level sequencing QC

Figures for raw-read quality: per-base quality, base composition, adapter
content, duplication/insert size, mapping summary, gene-body coverage,
saturation, and barcode rank. All templates take **aggregated metric tables**
(one row per cycle / bin / sample) — the kind MultiQC, FastQC summaries, or
Samtools stats emit — never raw FASTQ. Thresholds are parameters, drawn as
dashed ink lines with right-edge labels.

```python
# shared setup for every template in this file
import sys; sys.path.insert(0, "<skill-dir>/scripts")
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from qcstyle import (use_style, save_fig, journal_size, cat_palette,
                     seq_cmap, div_cmap, beautify, grid_axis, add_colorbar)
use_style("journal")
```

### per_base_quality — Per-base quality profile `id: per_base_quality`

FastQC-style per-cycle quality: median line, IQR band, whisker range as a
faint ribbon; Q20/Q30 threshold lines. Read one sample per panel or overlay
a few libraries to spot a bad run.

```python
# INPUT : DataFrame q, columns: cycle(int), q25, median, q75, min, max
#         (Phred scores; one library). Optional Series group to overlay libraries.
# OUTPUT: fig_qc_per_base_quality.png/svg
# DEPENDS: matplotlib, numpy
fig, ax = plt.subplots(figsize=journal_size("single", 0.72))
ax.fill_between(q["cycle"], q["q25"], q["q75"], color="#0072B2", alpha=0.22, lw=0)
ax.plot(q["cycle"], q["median"], color="#0072B2", lw=1.6, label="Median")
ax.plot(q["cycle"], q["q25"], color="#0072B2", lw=0.7, alpha=0.6)
ax.plot(q["cycle"], q["q75"], color="#0072B2", lw=0.7, alpha=0.6)
for thr in (20, 30):
    ax.axhline(thr, color="#1A1A1A", lw=0.8, ls=(0, (4, 3)))
    ax.annotate(f"Q{thr}", xy=(1, thr), xycoords=("axes fraction", "data"),
                xytext=(3, 0), textcoords="offset points", va="center", fontsize=7)
ax.set(xlabel="Cycle (bp)", ylabel="Phred quality",
       ylim=(0, 42), xlim=(0, q["cycle"].max()))
beautify(ax)
save_fig(fig, "fig_qc_per_base_quality")
```

### base_composition — Per-cycle base composition `id: base_composition`

Stacked A/C/G/T fractions per cycle. A sharp wobble in the first ~10 cycles
is normal (random-priming bias); a drift mid-read signals chemistry trouble.

```python
# INPUT : DataFrame comp, columns: cycle(int), A, C, G, T  (fractions summing to 1)
# OUTPUT: fig_qc_base_composition.png/svg
# DEPENDS: matplotlib, numpy
bases = ["A", "C", "G", "T"]
colors = {"A": "#0072B2", "C": "#E69F00", "G": "#009E73", "T": "#CC79A7"}
fig, ax = plt.subplots(figsize=journal_size("single", 0.62))
top = np.zeros(len(comp))
for b in bases:
    ax.fill_between(comp.cycle, top, top + comp[b], color=colors[b],
                    alpha=0.85, lw=0, label=b)
    top = top + comp[b].to_numpy()
ax.set(xlabel="Cycle (bp)", ylabel="Base fraction", ylim=(0, 1),
       xlim=(0, comp.cycle.max()))
ax.legend(ncol=4, loc="lower right", title=None)
beautify(ax)
save_fig(fig, "fig_qc_base_composition")
```

### adapter_content — Adapter enrichment per cycle `id: adapter_content`

Percent of reads carrying adapter sequence, one curve per adapter; log-y
makes early exponential growth readable. Warn line at 5% (FastQC flag).

```python
# INPUT : DataFrame ad, columns: cycle(int), one column per adapter (percent)
# OUTPUT: fig_qc_adapter_content.png/svg
# DEPENDS: matplotlib, numpy
fig, ax = plt.subplots(figsize=journal_size("single", 0.72))
cols = [c for c in ad.columns if c != "cycle"]
for c, col in zip(cols, cat_palette(len(cols))):
    ax.plot(ad.cycle, ad[c], color=col, lw=1.5, label=c)
ax.axhline(5, color="#D55E00", lw=0.9, ls=(0, (4, 3)))
ax.annotate("5% warn", xy=(1, 5), xycoords=("axes fraction", "data"),
            xytext=(3, 0), textcoords="offset points", va="center",
            fontsize=7, color="#D55E00")
ax.set(xlabel="Cycle (bp)", ylabel="Reads with adapter (%)", yscale="log",
       ylim=(1e-3, 100), xlim=(0, ad.cycle.max()))
ax.legend(title=None)
beautify(ax)
save_fig(fig, "fig_qc_adapter_content")
```

### dup_insert — Duplication + insert-size panel `id: dup_insert`

Left: insert-size distribution (one curve per sample, shared axes). Right:
per-sample duplication rate bars with the 20% review line. Read together:
high duplication + short inserts often means over-amplification.

```python
# INPUT : DataFrame ins, columns: size(bp), count, sample
#         DataFrame dup, columns: sample, dup_pct
# OUTPUT: fig_qc_dup_insert.png/svg
# DEPENDS: matplotlib, numpy
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=journal_size("double", 0.62))
samples = sorted(ins["sample"].unique(), key=str)
for s, c in zip(samples, cat_palette(len(samples))):
    d = ins[ins["sample"] == s]
    ax1.plot(d["size"], d["count"] / d["count"].max(), color=c, lw=1.5, label=s)
ax1.set(xlabel="Insert size (bp)", ylabel="Density (peak = 1)")
ax1.legend(title=None)
beautify(ax1)
ax2.bar(dup["sample"], dup["dup_pct"], color="#526272", width=0.68)
ax2.axhline(20, color="#D55E00", lw=0.9, ls=(0, (4, 3)))
ax2.annotate("20% review", xy=(1, 20), xycoords=("axes fraction", "data"),
             xytext=(3, 0), textcoords="offset points", va="center",
             fontsize=7, color="#D55E00")
ax2.set(xlabel="", ylabel="Duplication (%)")
ax2.tick_params(axis="x", rotation=45)
beautify(ax2)
save_fig(fig, "fig_qc_dup_insert")
```

### mapping_summary — Mapping-rate summary bars `id: mapping_summary`

One stacked bar per sample: unique, multi-mapped, unmapped (percent).
Sort by mapped fraction so problem libraries cluster at one end.

```python
# INPUT : DataFrame mp, columns: sample, unique_pct, multi_pct, unmapped_pct
# OUTPUT: fig_qc_mapping_summary.png/svg
# DEPENDS: matplotlib, numpy
mp = mp.sort_values("unique_pct", ignore_index=True)
parts = [("unique_pct", "#0072B2", "Unique"), ("multi_pct", "#56B4E9", "Multi-mapped"),
         ("unmapped_pct", "#D55E00", "Unmapped")]
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.6))
left = np.zeros(len(mp))
for col, c, lab in parts:
    ax.bar(mp["sample"], mp[col], bottom=left, color=c, width=0.72, label=lab)
    left = left + mp[col].to_numpy()
ax.set(xlabel="", ylabel="Reads (%)", ylim=(0, 100))
ax.legend(ncol=3, loc="lower right", bbox_to_anchor=(1.0, 1.02))
ax.tick_params(axis="x", rotation=45)
beautify(ax)
save_fig(fig, "fig_qc_mapping_summary")
```

### gene_body_coverage — Gene-body coverage (5'/3' bias) `id: gene_body_coverage`

Mean coverage across gene bodies in 100 percentile bins, one curve per
sample. A flat line is healthy; a 5' or 3' tilt flags degraded RNA or
capture bias. Overlay up to ~8 samples.

```python
# INPUT : DataFrame gb, columns: bin(int 0-100), cov (mean normalized coverage), sample
# OUTPUT: fig_qc_gene_body_coverage.png/svg
# DEPENDS: matplotlib, numpy
fig, ax = plt.subplots(figsize=journal_size("single", 0.72))
samples = sorted(gb["sample"].unique(), key=str)
for s, c in zip(samples, cat_palette(len(samples))):
    d = gb[gb["sample"] == s]
    ax.plot(d["bin"], d["cov"], color=c, lw=1.5, label=s)
ax.axhline(1, color="#1A1A1A", lw=0.7, ls=(0, (4, 3)))
ax.annotate("5'", xy=(0.01, 1.04), xycoords="axes fraction", fontsize=8)
ax.annotate("3'", xy=(0.97, 1.04), xycoords="axes fraction", fontsize=8)
ax.set(xlabel="Position in gene body (percentile)",
       ylabel="Relative coverage", xlim=(0, 100))
ax.legend(title=None, ncol=2)
beautify(ax)
save_fig(fig, "fig_qc_gene_body_coverage")
```

### saturation_curve — Sequencing-depth saturation `id: saturation_curve`

Median metric (genes detected, reads per cell, or bases) against downsampled
depth, one curve per group, with the chosen sequencing depth marked. A curve
still climbing at the working depth means more depth still buys information.

```python
# INPUT : DataFrame sat, columns: depth, metric, group (aggregated, e.g. median)
#         float working_depth (drawn as a vertical marker)
# OUTPUT: fig_qc_saturation.png/svg
# DEPENDS: matplotlib, numpy
fig, ax = plt.subplots(figsize=journal_size("single", 0.72))
groups = sorted(sat["group"].unique(), key=str)
for g, c in zip(groups, cat_palette(len(groups))):
    d = sat[sat["group"] == g].sort_values("depth")
    ax.plot(d["depth"], d["metric"], color=c, lw=1.6, label=g)
ax.axvline(working_depth, color="#1A1A1A", lw=0.9, ls=(0, (4, 3)))
ax.annotate("working depth", xy=(working_depth, 0.02),
            xycoords=("data", "axes fraction"), xytext=(3, 0),
            textcoords="offset points", rotation=90, va="bottom", fontsize=7)
ax.set(xlabel="Sequencing depth (reads)", ylabel="Median genes detected")
ax.legend(title=None)
beautify(ax)
save_fig(fig, "fig_qc_saturation")
```

### knee_rank — Barcode rank (knee) plot `id: knee_rank`

Log-log barcode rank vs UMI count with the knee and inflection marked and
called cells shaded — the standard 10x library-complexity figure.

```python
# INPUT : DataFrame bc, columns: rank(int), count (all barcodes, sorted)
#         int knee_rank, cell_rank (from knee/inflection detection)
# OUTPUT: fig_qc_knee_rank.png/svg
# DEPENDS: matplotlib, numpy
fig, ax = plt.subplots(figsize=journal_size("single", 0.72))
ax.plot(bc["rank"], bc["count"], color="#0072B2", lw=1.6)
ax.fill_between(bc["rank"], 1e-1, bc["count"], where=(bc["rank"] <= cell_rank),
                color="#0072B2", alpha=0.15, lw=0)
for r, lab in ((knee_rank, "knee"), (cell_rank, "inflection")):
    ax.axvline(r, color="#D55E00", lw=0.9, ls=(0, (4, 3)))
    ax.annotate(lab, xy=(r, 0.95), xycoords=("data", "axes fraction"),
                 xytext=(3, 0), textcoords="offset points", fontsize=7,
                 color="#D55E00", rotation=90, va="top")
ax.set(xlabel="Barcode rank", ylabel="UMI count", xscale="log", yscale="log")
beautify(ax)
save_fig(fig, "fig_qc_knee_rank")
```
