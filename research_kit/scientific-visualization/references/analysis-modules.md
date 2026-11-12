> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Analysis Modules — Data In, Figure Set Out

End-to-end pipelines: each module takes a defined input, runs the analysis,
and emits a coordinated figure set (all figures share the style engine and a
consistent palette mapping). Figure code reuses the layer-1 templates in the
domain references — this file defines the pipelines and their contracts.

Module spec format: **Input** → **Steps** → **Outputs** (figure files).
Every module validates its input columns before running and stops with a
clear message listing missing columns.

## Module index

| id | Domain | Input | Outputs |
|---|---|---|---|
| `bulk-de` | Bulk | counts matrix + metadata | QC pair, PCA, volcano, MA, heatmap |
| `enrichment` | Bulk | DE gene list (+ background) | dot plot, bar, cnet, ridge, NES |
| `survival` | Bulk | expression + clinical | KM, forest, time-ROC |
| `immune-infiltration` | Bulk | expression matrix | proportion stack, correlation heatmap, survival link |
| `scrna-qc` | Single-cell | raw AnnData | QC triplet, QC scatter, filtering summary |
| `scrna-cluster` | Single-cell | processed AnnData | UMAP, dot plot, marker heatmap, proportions |
| `scrna-trajectory` | Single-cell | clustered AnnData + root | trajectory, branch heatmap, velocity |
| `cellcomm` | Single-cell | clustered AnnData (LR DB) | bubble plot, chord, circle |
| `vs-triage` | Docking | score table (+ SDF) | funnel, heatmap, 2D interaction grid |
| `docking-validation` | Docking | predicted + experimental | validation scatter, residuals, stats table |
| `md-qc` | MD | time-series exports | RMSD, Rg/SASA, H-bond, convergence panels |
| `fel` | MD | two CVs per frame | FEL contour, 1D PMFs, minimum-path overlay |
| `mmpbsa` | MD | energy decomposition | component stack, residue waterfall |
| `ml-benchmark` | ML | predictions per model | ROC, PR, calibration, confusion 2×2 |
| `ml-interpret` | ML | fitted model + data | SHAP suite, importance comparison |
| `spectra` | QM | excitation/frequency tables | IR/UV-Vis/Raman panel |
| `qm-summary` | QM | optimization + orbitals + charges | convergence, levels, charges composite |

---

## bulk-de — Bulk differential expression set

**Input**: `counts` (genes × samples, raw integer counts), `meta`
(samples × columns incl. `condition` with exactly 2+ levels, optional
covariates), `contrast` (e.g. `"treated_vs_control"`).

**Steps**:
1. Validate: integer counts, no NaN, ≥ 2 replicates per group.
2. DESeq2 (R) or DESeq2 via `pydeseq2` (Python) → DE table.
3. QC: library-size bar + sample Spearman heatmap (`sample_corr`).
4. PCA on VST/rlog values (`pca_samples`).
5. Volcano (`volcano`), MA (`ma_plot`), top-DEG heatmap (`deg_heatmap`).

**Outputs**: `fig_qc_libsize`, `fig_samplecorr`, `fig_pca`, `fig_volcano`,
`fig_ma`, `fig_deg_heatmap` + `de_results.csv`.

```python
# WORKED EXAMPLE (Python path, pydeseq2)
# INPUT : counts.csv (index=gene, columns=samples), meta.csv (index=sample, column condition)
# OUTPUT: de_results.csv + 5 figures
# DEPENDS: pydeseq2, matplotlib, pandas
import pandas as pd, numpy as np
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats
from biostyle import use_style, save_fig, journal_size

use_style("journal")
counts = pd.read_csv("counts.csv", index_col=0).T          # samples x genes
meta = pd.read_csv("meta.csv", index_col=0).loc[counts.index]
assert counts.dtypes.map(np.issubdtype, dtype=object, other=np.integer).all(), \
    "counts must be integers"
assert meta.condition.notna().all(), "condition has missing values"

dds = DeseqDataSet(counts=counts, metadata=meta, design="~condition")
dds.deseq2()
stat = DeseqStats(dds, contrast=["condition", "treated", "control"])
stat.summary()
de = stat.results_df.rename_axis("gene").reset_index()
de.to_csv("de_results.csv", index=False)
# -> then render volcano / MA / heatmap with the bulk-omics templates
```

R path: DESeq2 `DESeqDataSetFromMatrix` + `results()`; identical figure set
via the R templates (`sample_corr`, `deg_heatmap`).

## enrichment — ORA + GSEA set

**Input**: ranked or thresholded gene list; optional background universe;
GO/KEGG/MSigDB gene sets (offline `gseapy` Enrichr libraries or local GMT).

**Steps**: ORA (`gseapy.enrichr`) and/or GSEA (`gseapy.prerank`) →
dot plot (`enrich_dot`), NES bars + running score (`gsea_running`),
gene-concept network (cnetplot-style via `gseapy`/networkx), enrichment
mountain ridge over clusters.

**Outputs**: `fig_enrich_dot`, `fig_gsea`, `fig_cnet`, `fig_ridge_enrich`.

Guardrails: state the gene-set database and version; report both ORA and
GSEA when both are run; never pool terms with different ontologies in one
panel without labeling.

## survival — Expression–survival set

**Input**: `expr` (gene × sample), `clin` (sample × {time, event,
covariates}).

**Steps**: choose gene(s); split by median or validated cutoff (report
which); KM with risk table (`km_curve`); univariate + multivariate Cox →
forest (`forest`); time-dependent AUC at 1/3/5 y if `scikit-survival`
available.

**Outputs**: `fig_km`, `fig_forest`, optional `fig_time_roc` +
`survival_stats.csv`.

Guardrails: report cutoff derivation; state censoring; HR with 95% CI.

## immune-infiltration — Infiltration set

**Input**: normalized expression matrix; cell-type signature matrix
(e.g. LM22) or ssGSEA gene sets.

**Steps**: CIBERSORT-like deconvolution (`cibersortx` external) or ssGSEA
(`gseapy.ssgsea`) → proportions stacked bars (`proportion_stack` adapted),
cell-type correlation heatmap, proportions vs survival/condition link.

**Outputs**: `fig_infiltration_stack`, `fig_infiltration_corr`,
`fig_infiltration_surv`.

## scrna-qc — scRNA QC set

**Input**: raw AnnData (`.h5ad`) or Cell Ranger `filtered_feature_bc_matrix`.

**Steps**: compute QC metrics (`sc.pp.calculate_qc_metrics`) → QC triplet
(`qc_triplet`); apply thresholds (report them); before/after UMAP or
count-density comparison.

**Outputs**: `fig_qc`, `fig_qc_after`, `qc_thresholds.json`.

## scrna-cluster — scRNA clustering set

**Input**: processed AnnData (normalized, HVG-selected, integrated if
multi-sample).

**Steps**: PCA → neighbors → Leiden → UMAP → markers
(`rank_genes_groups`) → UMAP (`umap_clusters`), dot plot (`dot_plot`),
marker heatmap (`marker_heatmap`), proportions (`proportion_stack`).

**Outputs**: `fig_umap`, `fig_dotplot`, `fig_markers`, `fig_props` +
`markers.csv`.

Guardrails: state resolution, integration method, and marker test.

## scrna-trajectory — Trajectory set

**Input**: clustered AnnData + root cell type; optional spliced/unliced
layers for velocity.

**Steps**: pseudotime (diffusion pseudotime or palantir) → trajectory plot
(`trajectory`); branch expression heatmap (top branch-dependent genes);
velocity stream if spliced/unliced present (`velocity_stream`).

**Outputs**: `fig_traj`, `fig_branch_heatmap`, optional `fig_velocity`.

## cellcomm — Cell-cell communication set

**Input**: clustered AnnData; LR database (CellChat/CellPhoneDB/NicheNet
resources).

**Steps**: LR permutation scoring → significant pairs table → bubble plot
(`cellcomm_bubble`), chord diagram (`chord_go` adapted to cell types),
circle plot.

**Outputs**: `fig_cellcomm`, `fig_comm_chord`, `comm_pairs.csv`.

Guardrails: state the LR database version and permutation count; these are
inferences, not measured interactions.

## vs-triage — Virtual-screening triage

**Input**: docking score table (ligand × protocol stages); optional SDF of
top hits.

**Steps**: funnel (`vs_funnel`); score heatmap across conformations
(`score_heatmap`); 2D interaction diagrams for top N (`interaction_2d`);
ligand-efficiency check (`ligand_efficiency`).

**Outputs**: `fig_funnel`, `fig_score_heatmap`, `fig_interaction_2d`,
`fig_le`, `top_hits.csv`.

## docking-validation — Rescoring validation

**Input**: predicted scores + experimental affinities for a benchmark set.

**Steps**: correlation scatter (`validation_scatter`); residual analysis;
per-subset (scaffold) breakdown.

**Outputs**: `fig_validation`, `fig_val_residuals`, `validation_stats.csv`.

## md-qc — Trajectory QC set

**Input**: time-series exports (RMSD, Rg, SASA, H-bonds) from GROMACS
(`gmx rms/rmsf/gyrama/sasa/hbond`) or cpptraj.

**Steps**: convergence check (`convergence`); RMSD overlay (`rmsd_overlay`);
Rg/SASA panels (`rg_sasa`); H-bond stability (`hbond`).

**Outputs**: `fig_convergence`, `fig_rmsd`, `fig_rg_sasa`, `fig_hbond`.

## fel — Free-energy landscape

**Input**: per-frame CV table (e.g. RMSD + Rg from the same trajectory).

**Steps**: 2D FEL (`fel_2d`); 1D PMFs per CV (`pmf_1d`); optional minimum
free-energy path overlay.

**Outputs**: `fig_fel`, `fig_pmf`, `fel_params.json` (T, bins, frames).

## mmpbsa — Binding-energy decomposition

**Input**: MM-PBSA decomposition table (per-term, per-residue).

**Steps**: component stack (`mmpbsa_stack`); residue waterfall
(`mmpbsa_residue`); state entropy treatment.

**Outputs**: `fig_mmpbsa`, `fig_mmpbsa_res`, `mmpbsa_summary.csv`.

## ml-benchmark — Model benchmark 2×2

**Input**: per-model prediction table (y_true, y_prob, y_pred, model).

**Steps**: ROC (`roc_multi`), PR (`pr_curve`), calibration (`calibration`),
confusion (`confusion`) — assembled as the 2×2 benchmark composite
(`composite-figures.md` recipe `ml-benchmark`).

**Outputs**: `fig_ml_benchmark` (composite) + `benchmark_stats.csv`.

## ml-interpret — Model interpretation suite

**Input**: fitted tree/linear model + X (DataFrame).

**Steps**: SHAP values → beeswarm + bar (`shap_summary`); dependence for
top features (`shap_dependence`); interactions if affordable
(`shap_interaction`); permutation vs impurity importance (`feat_importance`).

**Outputs**: `fig_shap`, `fig_shap_dep`, `fig_importance`.

## spectra — Spectroscopy panel

**Input**: frequency/intensity tables (IR), excitation tables (UV-Vis/ECD).

**Steps**: broaden and overlay calculated vs experimental (`ir_spectrum`,
`uvvis`, `ecd`); assemble as one multi-panel figure.

**Outputs**: `fig_spectra_panel` + `spectra_params.json`.

## qm-summary — QM study summary

**Input**: optimization history, orbital energies, charges.

**Steps**: convergence panel (`opt_convergence`); orbital level diagram
(`orbitals`); charge bars (`charges`); gap comparison (`gap_compare`).

**Outputs**: `fig_opt`, `fig_orbitals`, `fig_charges`, `fig_gap`.
