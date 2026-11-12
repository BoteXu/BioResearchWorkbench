# Current result-only API (v2.1 private)

For native workflow receipt/QC consumers and stored-PCA handoffs, read
[workflow results](workflow-results.md). `shap_summary` defaults to a small
rose inset, keeps complete feature shares and uses actual explanation units.
Generic model figures require explicit `evaluation` metadata before labeling a
partition OOF/held-out/external; absent scope stays unspecified.


Add the skill's `scripts` directory to the Python import path in your existing
environment. The render layer requires NumPy, pandas, SciPy and Matplotlib;
seaborn is needed by retained alternatives, Pillow by GIF. It does not install
or train analysis tools. HTML molecular views use the bundled 3Dmol viewer.

```python
from renderers import render_template
fig, metadata = render_template(
    "umap_clusters", existing_results, variant="profile",
    width="double", outdir=output_directory, stem="cell_atlas_v2",
)
```

Static calls return `(figure, metadata)` and write PNG at 300 dpi and editable
SVG by default. Close the figure after use. Existing files are protected unless
`overwrite=True` is explicitly supplied. Output stems preserve the legacy
catalog defaults; choose a fresh version stem for normal work. Exact canvas
widths are `single=89`, `onehalf=120`, `double=183` mm. `aspect` means canvas
height/width; omit it to use the data-aware default. Titles wrap, but long names
and many categories may still require explicit facets or pagination.

```python
from composite import render_composite
path, metadata = render_composite(
    "bulk-de-story", panel_results, outdir=output_directory,
    stem="bulk_story_v2", ncols=2, panel_options=per_panel_options,
)
```

Seven recipes render actual supplied panels. `ncols=1` makes a vertical story;
`panel_ids` explicitly selects alternative available channels. Children are
rendered at their actual column width, not silently shrunk. Composite output
is SVG; use an actual browser to export/inspect PNG, including embedded SVG
references. No empty panel counts as completion.

`composition_layout="auto"` balances columns when child heights differ
substantially. Use `composition_layout="grid"` for an explicit common-row grid,
or `balanced_columns` deliberately. Panel positions in millimetres are returned.
Long vertical stories are scrolling/report layouts; paginate for manuscript pages.

Core shape contracts: matrices accept a DataFrame or a dictionary with
`values`, `rows`, `columns`. ndarrays require matching identities. Sparse
conversion is explicit and bounded; it is not automatically supported by every
template. No positional ID reassignment or silent imputation. Figure-specific
schemas below reflect actual tested channels, not arbitrary-format promises.

Heatmaps preserve unclipped-value average linkage and declared distances.
`cluster_mode="free"` is the default; `condition_blocks` requires aligned
groups and explicit group order. Save returned row/column orders. A display
limit only changes colors. Missing values have their own key. Constant or
missing matrices cannot request undefined clustering distances.

`missing_pattern` preserves the original row-rate summary and adds column rates.
Only NaN/None is missing; a measured zero is observed. `missing_reference=0.30`
(or legacy `drop_thr=0.30`) is an optional configurable fraction, passed to the
line and returned rate table. No default threshold or deletion is invented.

PCA accepts upstream coordinates and explained variance, not raw counts.
Covariance ellipses are dispersion summaries and are omitted if unestimable.
QC squared-Mahalanobis scores and configurable reference lines are passed
through and saved in a side table; plots do not exclude observations.
Effects require complete supplied estimates/interval limits. Frozen densities
are required for distribution forests/raincloud clouds; intervals are never
used to invent densities. Volcano adjusted P=0 is explicitly marked at a
declared display height. Source thresholds remain unchanged.

UMAP atlas/profile/highlight/classic and matched-stage verification options
preserve coordinates and sample identities. Exact duplicate stages collapse
by default with a recorded reason. No embedding is refitted.

SHAP swarms, rose and classic combinations are variants of `shap_summary`, not
extra catalog IDs. See [preserved SHAP designs](shap-preservation.md). The
current interaction example is off-diagonal-only; its omitted diagonal is
not a claim of zero main effects. Declare the matrix kind explicitly.

HTML/GIF IDs return `(None, metadata)` and require `outdir`. `pose-3d-html`
accepts supplied PDB/frames or a genuine cube field; volume and signed
isosurfaces are distinct modes. No fabricated density or 3D stand-in. Browser
validation must exercise filters, camera/style/frame controls offline. GIF
requires aligned real coordinate frames, times and units. Inspect playback
as well as representative frames.

R: source `scripts/biostyle.R`, then `scripts/render_r.R` for
`render_heatmap_r` and `scripts/result_views.R` for `render_result_r`.
Native R alternatives currently include volcano, raincloud, chords, alluvial,
KM, oncoprint and marker/expression/pathway/correlation heatmaps. Other original
R code remains reference material and is not marked runtime-accepted by the
Python render. Existing R packages are reused; no forced Python rewrite.

Compatibility: `sample_corr` remains the main Spearman R identity.
`render_template("sample_corr", data, source="qc-visualization")` resolves to
`qc_sample_corr`. `qcstyle.py` delegates to `biostyle.py`; legacy imports
remain. `assets/compatibility.json` preserves qualified IDs and old field maps.

## Per-template current contracts

### volcano

Volcano plot · bulk

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `biological_unit`, `contrast`, `de`, `pca`, `pca_variance`, `pca_genes`, `correlation`, `expression`, `heatmap`, `densities`, `clustering`, `thresholds`, `limitation`.

Call: `render_template("volcano", data, ...)`. Legacy output: `fig1_volcano.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### ma_plot

MA plot · bulk

Actual result fields: `x`, `y`, `color`, `color_label`, `xlabel`, `ylabel`, `title`, `zero_y`.

Call: `render_template("ma_plot", data, ...)`. Legacy output: `fig_ma.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### sample_corr

Sample correlation heatmap · bulk

Actual result fields: `matrix`, `groups`, `group_order`, `correlation_method`.

Call: `render_template("sample_corr", data, ...)`. Legacy output: `fig_samplecorr.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### pca_samples

PCA with ellipses · bulk

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `biological_unit`, `contrast`, `de`, `pca`, `pca_variance`, `pca_genes`, `correlation`, `expression`, `heatmap`, `densities`, `clustering`, `thresholds`, `limitation`.

Call: `render_template("pca_samples", data, ...)`. Legacy output: `fig_pca.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### deg_heatmap

DEG z-score heatmap · bulk

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `biological_unit`, `contrast`, `de`, `pca`, `pca_variance`, `pca_genes`, `correlation`, `expression`, `heatmap`, `densities`, `clustering`, `thresholds`, `limitation`.

Call: `render_template("deg_heatmap", data, ...)`. Legacy output: `fig_deg_heatmap.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### enrich_dot

ORA dot plot · bulk

Actual result fields: `table`, `ratio_label`, `effect_provenance`.

Call: `render_template("enrich_dot", data, ...)`. Legacy output: `fig_enrich_dot.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### gsea_running

GSEA running score + NES bars · bulk

Actual result fields: `pathways`.

Call: `render_template("gsea_running", data, ...)`. Legacy output: `fig_gsea.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### km_curve

Kaplan-Meier with risk table · bulk

Actual result fields: `table`, `time_unit`.

Call: `render_template("km_curve", data, ...)`. Legacy output: `fig_km.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### forest

Forest plot · bulk

Actual result fields: `source`, `table`, `unit`, `interval_label`, `n_malignant`, `n_benign`, `plan_sha256`.

Call: `render_template("forest", data, ...)`. Legacy output: `fig_forest.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### upset

UpSet plot · bulk

Actual result fields: `sets`.

Call: `render_template("upset", data, ...)`. Legacy output: `fig_upset.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### chord_go

Pathway-gene chord diagram · bulk

Actual result fields: `links`, `weight_label`, `source`, `display_selection`.

Call: `render_template("chord_go", data, ...)`. Legacy output: `fig_chord.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### ridge_expr

Expression ridgeline · bulk

Actual result fields: `table`, `densities`, `genes`, `group_order`, `unit`.

Call: `render_template("ridge_expr", data, ...)`. Legacy output: `fig_ridge.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### raincloud

Raincloud plot · bulk

Actual result fields: `values`, `labels`, `densities`, `unit`.

Call: `render_template("raincloud", data, ...)`. Legacy output: `fig_raincloud.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### volcano_marginal

Volcano + marginal densities · bulk

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `biological_unit`, `contrast`, `de`, `pca`, `pca_variance`, `pca_genes`, `correlation`, `expression`, `heatmap`, `densities`, `clustering`, `thresholds`, `limitation`.

Call: `render_template("volcano_marginal", data, ...)`. Legacy output: `fig_volcano_marg.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### pca_marginal

PCA + marginal densities · bulk

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `biological_unit`, `contrast`, `de`, `pca`, `pca_variance`, `pca_genes`, `correlation`, `expression`, `heatmap`, `densities`, `clustering`, `thresholds`, `limitation`.

Call: `render_template("pca_marginal", data, ...)`. Legacy output: `fig_pca_marg.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### gsea_tracks

GSEA aligned multi-track · bulk

Actual result fields: `pathways`.

Call: `render_template("gsea_tracks", data, ...)`. Legacy output: `fig_gsea_tracks.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### effect_matrix

Effect + CI matrix · bulk

Actual result fields: `table`, `unit`.

Call: `render_template("effect_matrix", data, ...)`. Legacy output: `fig_effects.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### paired_trajectory

Paired-observation lines · bulk

Actual result fields: `table`, `stage_order`, `quantity`, `unit_description`.

Call: `render_template("paired_trajectory", data, ...)`. Legacy output: `fig_paired.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### oncoprint

Oncoprint · bulk

Actual result fields: `genes`, `samples`, `events`, `assayed`, `event_types`, `assay_note`.

Call: `render_template("oncoprint", data, ...)`. Legacy output: `fig_oncoprint.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### enrich_heatmap

Pathway-score heatmap (two-way clustered) · bulk

Actual result fields: `heatmap`, `groups`, `group_order`.

Call: `render_template("enrich_heatmap", data, ...)`. Legacy output: `fig_enrich_heatmap.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### module_trait

Module-trait correlation heatmap · bulk

Actual result fields: `matrix`.

Call: `render_template("module_trait", data, ...)`. Legacy output: `fig_module_trait.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### contrast_grid

Volcano grid (per contrast) · bulk

Actual result fields: `contrasts`.

Call: `render_template("contrast_grid", data, ...)`. Legacy output: `fig_contrast_grid.png/svg`. Original reference: [references/bulk-omics.md](bulk-omics.md).

### umap_clusters

UMAP with cluster labels · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("umap_clusters", data, ...)`. Legacy output: `fig_umap.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### feature_grid

Feature-plot grid · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("feature_grid", data, ...)`. Legacy output: `fig_features.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### dot_plot

Gene x cluster dot plot · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("dot_plot", data, ...)`. Legacy output: `fig_dotplot.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### split_violin

Split violin · single-cell

Actual result fields: `table`, `densities`, `genes`, `group_order`, `hue_order`, `hue_label`, `unit`, `gene_as_group`.

Call: `render_template("split_violin", data, ...)`. Legacy output: `fig_split_violin.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### qc_triplet

QC triplet + scatter · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("qc_triplet", data, ...)`. Legacy output: `fig_qc.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### proportion_stack

Proportion stacked bars · single-cell

Actual result fields: `values`, `categories`, `labels`.

Call: `render_template("proportion_stack", data, ...)`. Legacy output: `fig_props.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### trajectory

Pseudotime trajectory · single-cell

Actual result fields: `source`, `sample_ids`, `group_order`, `groups`, `age_days`, `embedding`, `umap`, `velocity_embedding`, `projection`, `pseudotime`, `time_label`, `phase`, `heatmap`, `trend`, `limitations`, `xlabel`, `ylabel`.

Call: `render_template("trajectory", data, ...)`. Legacy output: `fig_traj.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### velocity_stream

RNA velocity stream · single-cell

Actual result fields: `source`, `sample_ids`, `group_order`, `groups`, `age_days`, `embedding`, `umap`, `velocity_embedding`, `projection`, `pseudotime`, `time_label`, `phase`, `heatmap`, `trend`, `limitations`, `xlabel`, `ylabel`.

Call: `render_template("velocity_stream", data, ...)`. Legacy output: `fig_velocity.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### cellcomm_bubble

LR bubble plot · single-cell

Actual result fields: `table`, `score_label`, `display_pairs`, `source`, `display_selection`.

Call: `render_template("cellcomm_bubble", data, ...)`. Legacy output: `fig_cellcomm.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### marker_heatmap

Annotated marker heatmap · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("marker_heatmap", data, ...)`. Legacy output: `fig_markers.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### genescore

Gene-set score feature plot · single-cell

Actual result fields: `embedding`, `scores`, `score_names`, `unit`.

Call: `render_template("genescore", data, ...)`. Legacy output: `fig_genescore.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### alluvial

Alluvial identity flow · single-cell

Actual result fields: `links`, `flow_semantics`.

Call: `render_template("alluvial", data, ...)`. Legacy output: `fig_alluvial.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### marker_strip

Marker strips · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("marker_strip", data, ...)`. Legacy output: `fig_marker_strip.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### butterfly

Dual-enrichment butterfly · single-cell

Actual result fields: `program_scores`, `program_names`, `groups`, `group_order`, `sample_ids`, `unit`, `method`.

Call: `render_template("butterfly", data, ...)`. Legacy output: `fig_butterfly.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### dim_highlight

Gray-background highlight · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("dim_highlight", data, ...)`. Legacy output: `fig_highlight.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### scatter3d_projections

3D scatter + 2D projections · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("scatter3d_projections", data, ...)`. Legacy output: `fig_3d_projections.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### stacked_violin

Stacked violins · single-cell

Actual result fields: `table`, `densities`, `genes`, `group_order`, `unit`.

Call: `render_template("stacked_violin", data, ...)`. Legacy output: `fig_stacked_violin.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### expr_density

Expression density (Nebulosa) · single-cell

Actual result fields: `embedding`, `density_grids`, `unit`, `method`, `sample_ids`.

Call: `render_template("expr_density", data, ...)`. Legacy output: `fig_expr_density.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### pseudotime_lines

Smoothed trajectory lines · single-cell

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("pseudotime_lines", data, ...)`. Legacy output: `fig_pseudotime_lines.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### barcode_rank

Barcode rank (knee) plot · single-cell

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("barcode_rank", data, ...)`. Legacy output: `fig_barcode_rank.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### dim_facet

Faceted embedding small multiples · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("dim_facet", data, ...)`. Legacy output: `fig_dim_facet.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### onevsrest_grid

One-vs-rest volcano grid · single-cell

Actual result fields: `contrasts`, `source`, `cluster_mapping`, `source_table_sha256`.

Call: `render_template("onevsrest_grid", data, ...)`. Legacy output: `fig_onevsrest.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### cnv_heatmap

inferCNV-style heatmap · single-cell

Actual result fields: `matrix`.

Call: `render_template("cnv_heatmap", data, ...)`. Legacy output: `fig_cnv.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### velocity_phase

Spliced-unspliced phase portrait · single-cell

Actual result fields: `gene`, `table`.

Call: `render_template("velocity_phase", data, ...)`. Legacy output: `fig_velocity_phase.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### cellcomm_chord

LR chord diagram · single-cell

Actual result fields: `links`, `weight_label`, `display_nodes`, `source`, `interaction`, `title`.

Call: `render_template("cellcomm_chord", data, ...)`. Legacy output: `fig_cellcomm_chord.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### feature_overlay

Two-gene overlay (red/blue mix) · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("feature_overlay", data, ...)`. Legacy output: `fig_feature_overlay.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### proportion_dots

Proportion dots (color+shape) · single-cell

Actual result fields: `source`, `sample_ids`, `groups`, `group_order`, `representation`, `embedding`, `pca`, `markers`, `expression`, `dot_mean`, `dot_fraction`, `qc`, `cluster_counts`, `densities`, `limitation`.

Call: `render_template("proportion_dots", data, ...)`. Legacy output: `fig_proportion_dots.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### pseudotime_heat

Pseudotime-ordered heatmap · single-cell

Actual result fields: `heatmap`, `display_columns`.

Call: `render_template("pseudotime_heat", data, ...)`. Legacy output: `fig_pseudotime_heat.png/svg`. Original reference: [references/single-cell.md](single-cell.md).

### affinity_bar

Affinity bars · docking

Actual result fields: `table`, `unit`, `title`.

Call: `render_template("affinity_bar", data, ...)`. Legacy output: `fig_affinity.png/svg`. Original reference: [references/docking.md](docking.md).

### score_violin

Score violin · docking

Actual result fields: `values`, `labels`, `unit`.

Call: `render_template("score_violin", data, ...)`. Legacy output: `fig_score_violin.png/svg`. Original reference: [references/docking.md](docking.md).

### interaction_2d

2D interaction diagram · docking

Actual result fields: `source`, `target`, `score_kind`, `unit`, `lower_is_better`, `pose_ids`, `scores`, `pose_coordinates_A`, `heavy_atom_identity`, `pairwise_rmsd_A`, `components`, `component_names`, `contact_residues`, `closest_distances_A`, `contact_definition`, `contact_fraction`, `molecule_2d`, `renderer_notes`, `bonds`, `elements`, `atom_serials`.

Call: `render_template("interaction_2d", data, ...)`. Legacy output: `fig_interaction_2d.png`. Original reference: [references/docking.md](docking.md).

### pose_grid_3d

3D pose grid · docking

Actual result fields: `source`, `target`, `score_kind`, `unit`, `lower_is_better`, `pose_ids`, `scores`, `pose_coordinates_A`, `heavy_atom_identity`, `pairwise_rmsd_A`, `components`, `component_names`, `contact_residues`, `closest_distances_A`, `contact_definition`, `contact_fraction`, `molecule_2d`, `renderer_notes`, `bonds`, `elements`, `atom_serials`.

Call: `render_template("pose_grid_3d", data, ...)`. Legacy output: `fig_poses.png`. Original reference: [references/docking.md](docking.md).

### score_heatmap

Conformation x ligand heatmap · docking

Actual result fields: `matrix`.

Call: `render_template("score_heatmap", data, ...)`. Legacy output: `fig_score_heatmap.png/svg`. Original reference: [references/docking.md](docking.md).

### validation_scatter

Validation scatter · docking

Actual result fields: `x`, `y`, `xlabel`, `ylabel`, `title`, `point_labels`.

Call: `render_template("validation_scatter", data, ...)`. Legacy output: `fig_validation.png/svg`. Original reference: [references/docking.md](docking.md).

### contact_freq

Contact-frequency heatmap · docking

Actual result fields: `table`, `unit`, `title`.

Call: `render_template("contact_freq", data, ...)`. Legacy output: `fig_contacts.png/svg`. Original reference: [references/docking.md](docking.md).

### res_contrib

Per-residue waterfall · docking

Actual result fields: `table`, `unit`, `title`, `error_label`.

Call: `render_template("res_contrib", data, ...)`. Legacy output: `fig_res_contrib.png/svg`. Original reference: [references/docking.md](docking.md).

### pose_rmsd_cluster

Pose RMSD clustering · docking

Actual result fields: `matrix`.

Call: `render_template("pose_rmsd_cluster", data, ...)`. Legacy output: `fig_pose_cluster.png/svg`. Original reference: [references/docking.md](docking.md).

### vs_funnel

VS funnel · docking

Actual result fields: `stages`, `counts`.

Call: `render_template("vs_funnel", data, ...)`. Legacy output: `fig_funnel.png/svg`. Original reference: [references/docking.md](docking.md).

### ligand_efficiency

Ligand-efficiency plot · docking

Actual result fields: `x`, `y`, `xlabel`, `ylabel`, `title`, `point_labels`.

Call: `render_template("ligand_efficiency", data, ...)`. Legacy output: `fig_le.png/svg`. Original reference: [references/docking.md](docking.md).

### consensus_rank

Consensus rank heatmap · docking

Actual result fields: `matrix`.

Call: `render_template("consensus_rank", data, ...)`. Legacy output: `fig_consensus.png/svg`. Original reference: [references/docking.md](docking.md).

### rmsd_overlay

RMSD overlay · md

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("rmsd_overlay", data, ...)`. Legacy output: `fig_rmsd.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### rmsf

RMSF with SSE bands · md

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("rmsf", data, ...)`. Legacy output: `fig_rmsf.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### rg_sasa

Rg + SASA panels · md

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("rg_sasa", data, ...)`. Legacy output: `fig_rg_sasa.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### hbond

H-bond panels · md

Actual result fields: `curves`, `xlabel`, `ylabel`.

Call: `render_template("hbond", data, ...)`. Legacy output: `fig_hbond.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### dist_ridge

Distance series + ridgeline · md

Actual result fields: `values`, `densities`, `labels`, `unit`, `title`.

Call: `render_template("dist_ridge", data, ...)`. Legacy output: `fig_dist.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### fel_2d

2D free-energy landscape · md

Actual result fields: `x`, `y`, `z`, `unit`, `xlabel`, `ylabel`, `title`, `sample_coordinates`, `limitation`.

Call: `render_template("fel_2d", data, ...)`. Legacy output: `fig_fel.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### pmf_1d

1D PMF curves · md

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`, `source_raw_profile`, `correction`, `license`.

Call: `render_template("pmf_1d", data, ...)`. Legacy output: `fig_pmf.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### traj_pca

Trajectory PCA · md

Actual result fields: `pca`, `pca_variance`, `groups`, `group_order`.

Call: `render_template("traj_pca", data, ...)`. Legacy output: `fig_trajpca.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### contact_map

Contact-frequency matrix · md

Actual result fields: `matrix`.

Call: `render_template("contact_map", data, ...)`. Legacy output: `fig_contacts_md.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### dccm

DCCM matrix · md

Actual result fields: `matrix`.

Call: `render_template("dccm", data, ...)`. Legacy output: `fig_dccm.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### ramachandran

Ramachandran density · md

Actual result fields: `x`, `y`, `xlabel`, `ylabel`, `title`.

Call: `render_template("ramachandran", data, ...)`. Legacy output: `fig_rama.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### mmpbsa_stack

MM-PBSA components · md

Actual result fields: `source`, `source_sha256`, `extraction`, `unit`, `system`, `n_frames`, `temperature_K`, `rows`, `scope`, `title`.

Call: `render_template("mmpbsa_stack", data, ...)`. Legacy output: `fig_mmpbsa.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### mmpbsa_residue

Per-residue dG waterfall · md

Actual result fields: `matrix`, `title`.

Call: `render_template("mmpbsa_residue", data, ...)`. Legacy output: `fig_mmpbsa_res.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### convergence

Block-average convergence · md

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("convergence", data, ...)`. Legacy output: `fig_convergence.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### ifp_barcode

IFP barcode (residue x frame) · md

Actual result fields: `matrix`, `time_ns`, `definition`.

Call: `render_template("ifp_barcode", data, ...)`. Legacy output: `fig_ifp.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### rmsd_2d

Pairwise 2D-RMSD matrix · md

Actual result fields: `matrix`.

Call: `render_template("rmsd_2d", data, ...)`. Legacy output: `fig_rmsd_2d.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### state_occupancy

State-occupancy stacked area · md

Actual result fields: `values`, `categories`, `labels`, `state_definition`.

Call: `render_template("state_occupancy", data, ...)`. Legacy output: `fig_state_occ.png/svg`. Original reference: [references/molecular-dynamics.md](molecular-dynamics.md).

### roc_multi

Multi-model ROC · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`.

Call: `render_template("roc_multi", data, ...)`. Legacy output: `fig_roc.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### pr_curve

PR curve · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`.

Call: `render_template("pr_curve", data, ...)`. Legacy output: `fig_pr.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### confusion

Confusion matrix · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("confusion", data, ...)`. Legacy output: `fig_confusion.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### calibration

Calibration curve · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`.

Call: `render_template("calibration", data, ...)`. Legacy output: `fig_calibration.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### gain_lift

Gain/lift chart · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("gain_lift", data, ...)`. Legacy output: `fig_gain_lift.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### feat_importance

Feature importance · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("feat_importance", data, ...)`. Legacy output: `fig_importance.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### shap_summary

SHAP beeswarm + bar · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`.

Call: `render_template("shap_summary", data, ...)`. Legacy output: `fig_shap.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### shap_dependence

SHAP dependence · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("shap_dependence", data, ...)`. Legacy output: `fig_shap_dep.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### shap_interaction

SHAP interaction heatmap · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("shap_interaction", data, ...)`. Legacy output: `fig_shap_int.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### learning_curve

Learning curve · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("learning_curve", data, ...)`. Legacy output: `fig_learning.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### grid_heatmap

Grid-search heatmap · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("grid_heatmap", data, ...)`. Legacy output: `fig_grid.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### reg_scatter

Predicted vs true · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("reg_scatter", data, ...)`. Legacy output: `fig_reg.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### reg_diagnostics

Residual 2x2 panel · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("reg_diagnostics", data, ...)`. Legacy output: `fig_diagnostics.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### decision_boundary

Decision boundary · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("decision_boundary", data, ...)`. Legacy output: `fig_boundary.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### silhouette

Silhouette plot · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("silhouette", data, ...)`. Legacy output: `fig_silhouette.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### k_selection

Elbow + silhouette · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("k_selection", data, ...)`. Legacy output: `fig_k_selection.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### cv_box

CV score boxplots · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("cv_box", data, ...)`. Legacy output: `fig_cv_box.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### feat_corr

Feature correlation heatmap · ml

Actual result fields: `matrix`.

Call: `render_template("feat_corr", data, ...)`. Legacy output: `fig_featcorr.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### training_dashboard

Training-curve dashboard · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("training_dashboard", data, ...)`. Legacy output: `fig_training.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### radar

Radar (normalized) · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("radar", data, ...)`. Legacy output: `fig_radar.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### parallel_coords

Parallel coordinates · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("parallel_coords", data, ...)`. Legacy output: `fig_parallel.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### pdp_ice

PDP + ICE curves · ml

Actual result fields: `source`, `positive_class`, `features`, `X`, `y`, `method_plan_sha256`, `models`, `limitation`, `explanation`, `learning`, `grid`, `clusters`, `regression`, `pdp`, `additional`.

Call: `render_template("pdp_ice", data, ...)`. Legacy output: `fig_pdp_ice.png/svg`. Original reference: [references/machine-learning.md](machine-learning.md).

### ir_spectrum

IR spectrum · qm

Actual result fields: `spectra`, `xlabel`, `ylabel`, `reverse_x`.

Call: `render_template("ir_spectrum", data, ...)`. Legacy output: `fig_ir.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### uvvis

UV-Vis spectrum · qm

Actual result fields: `spectra`, `xlabel`, `ylabel`.

Call: `render_template("uvvis", data, ...)`. Legacy output: `fig_uvvis.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### emission_stokes

Absorption/emission mirror · qm

Actual result fields: `spectra`, `xlabel`, `ylabel`, `title`.

Call: `render_template("emission_stokes", data, ...)`. Legacy output: `fig_stokes.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### ecd

ECD spectrum · qm

Actual result fields: `spectra`, `xlabel`, `ylabel`.

Call: `render_template("ecd", data, ...)`. Legacy output: `fig_ecd.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### dos

DOS/PDOS areas · qm

Actual result fields: `spectra`, `xlabel`, `ylabel`.

Call: `render_template("dos", data, ...)`. Legacy output: `fig_dos.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### orbitals

Orbital level diagram · qm

Actual result fields: `systems`.

Call: `render_template("orbitals", data, ...)`. Legacy output: `fig_orbitals.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### irc

IRC/reaction profile · qm

Actual result fields: `curves`, `xlabel`, `ylabel`.

Call: `render_template("irc", data, ...)`. Legacy output: `fig_irc.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### scan_curve

PES scan curve · qm

Actual result fields: `curves`, `xlabel`, `ylabel`.

Call: `render_template("scan_curve", data, ...)`. Legacy output: `fig_scan.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### opt_convergence

Optimization convergence · qm

Actual result fields: `curves`, `xlabel`, `ylabel`.

Call: `render_template("opt_convergence", data, ...)`. Legacy output: `fig_opt.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### charges

Charge bar chart · qm

Actual result fields: `table`, `unit`, `title`.

Call: `render_template("charges", data, ...)`. Legacy output: `fig_charges.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### charge_diff

Charge difference · qm

Actual result fields: `table`, `unit`, `title`.

Call: `render_template("charge_diff", data, ...)`. Legacy output: `fig_chargediff.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### wiberg

Wiberg bond-order matrix · qm

Actual result fields: `matrix`, `title`.

Call: `render_template("wiberg", data, ...)`. Legacy output: `fig_wiberg.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### charge_2d

2D structure + charges · qm

Actual result fields: `molecule_2d`, `charges`, `title`.

Call: `render_template("charge_2d", data, ...)`. Legacy output: `fig_charge2d.png`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### gap_compare

HOMO-LUMO gap dumbbell · qm

Actual result fields: `systems`.

Call: `render_template("gap_compare", data, ...)`. Legacy output: `fig_gap.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### boltzmann

Conformer populations · qm

Actual result fields: `table`, `unit`, `title`.

Call: `render_template("boltzmann", data, ...)`. Legacy output: `fig_boltzmann.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### nci_rdg

NCI/RDG scatter · qm

Actual result fields: `x`, `y`, `color`, `color_label`, `xlabel`, `ylabel`, `title`, `source_total_grid_points`, `display_grid_points`.

Call: `render_template("nci_rdg", data, ...)`. Legacy output: `fig_nci.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### nmr_spectrum

NMR spectrum · qm

Actual result fields: `spectra`, `xlabel`, `ylabel`, `reverse_x`.

Call: `render_template("nmr_spectrum", data, ...)`. Legacy output: `fig_nmr.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### pes_2d

2D PES contour · qm

Actual result fields: `x`, `y`, `color`, `xlabel`, `ylabel`, `color_label`, `title`, `sample_path`.

Call: `render_template("pes_2d", data, ...)`. Legacy output: `fig_pes_2d.png/svg`. Original reference: [references/quantum-chemistry.md](quantum-chemistry.md).

### umap-dashboard

Interactive UMAP dashboard (plotly HTML) · interactive

Actual result fields: `embedding`, `groups`, `sample_ids`.

Call: `render_template("umap-dashboard", data, ...)`. Legacy output: `dashboard.html`. Original reference: [references/interactive-linked.md](interactive-linked.md).

### condition-toggle

Condition-toggle dashboard · interactive

Actual result fields: `embedding`, `groups`, `sample_ids`.

Call: `render_template("condition-toggle", data, ...)`. Legacy output: `toggle.html`. Original reference: [references/interactive-linked.md](interactive-linked.md).

### pose-3d-html

Interactive 3D pose viewer · interactive

Actual result fields: `pdb OR frames OR cube`.

Call: `render_template("pose-3d-html", data, ...)`. Legacy output: `pose.html`. Original reference: [references/interactive-linked.md](interactive-linked.md).

### trajectory-gif

Trajectory animation (GIF + offline HTML) · interactive

Actual result fields: `coordinates`, `times`, `unit`, `time_unit`.

Call: `render_template("trajectory-gif", data, ...)`. Legacy output: `traj.gif/html`. Original reference: [references/interactive-linked.md](interactive-linked.md).

### per_base_quality

Per-base quality profile · qc

Actual result fields: `stages`, `xlabel`, `ylabel`, `reference_lines`.

Call: `render_template("per_base_quality", data, ...)`. Legacy output: `fig_qc_per_base_quality.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### base_composition

Per-cycle base composition · qc

Actual result fields: `stages`, `xlabel`, `ylabel`.

Call: `render_template("base_composition", data, ...)`. Legacy output: `fig_qc_base_composition.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### adapter_content

Adapter enrichment per cycle · qc

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("adapter_content", data, ...)`. Legacy output: `fig_qc_adapter_content.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### dup_insert

Duplication + insert-size panel · qc

Actual result fields: `source`, `per_base_quality`, `base_composition`, `adapter_content`, `gene_body_coverage`, `saturation_curve`, `cv_density`, `rle`, `fastp_source`, `fastp`, `thresholds`, `limitations`.

Call: `render_template("dup_insert", data, ...)`. Legacy output: `fig_qc_dup_insert.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### mapping_summary

Mapping-rate summary bars · qc

Actual result fields: `values`, `labels`, `categories`.

Call: `render_template("mapping_summary", data, ...)`. Legacy output: `fig_qc_mapping_summary.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### gene_body_coverage

Gene-body coverage (5'/3' bias) · qc

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("gene_body_coverage", data, ...)`. Legacy output: `fig_qc_gene_body_coverage.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### saturation_curve

Sequencing-depth saturation · qc

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("saturation_curve", data, ...)`. Legacy output: `fig_qc_saturation.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### knee_rank

Barcode rank (knee) plot · qc

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("knee_rank", data, ...)`. Legacy output: `fig_qc_knee_rank.png/svg`. Original reference: [references/sequencing-qc.md](sequencing-qc.md).

### libsize_bar

Library-size bars with median line · qc

Actual result fields: `table`, `unit`, `title`.

Call: `render_template("libsize_bar", data, ...)`. Legacy output: `fig_qc_libsize.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### rle_plot

Relative log expression · qc

Actual result fields: `source`, `per_base_quality`, `base_composition`, `adapter_content`, `gene_body_coverage`, `saturation_curve`, `cv_density`, `rle`, `fastp_source`, `fastp`, `thresholds`, `limitations`.

Call: `render_template("rle_plot", data, ...)`. Legacy output: `fig_qc_rle.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### qc_sample_corr

Sample correlation heatmap with groups · qc

Actual result fields: `matrix`, `groups`, `group_order`.

Call: `render_template("qc_sample_corr", data, ...)`. Legacy output: `fig_qc_sample_corr.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### pca_outlier

PCA with outlier flagging · qc

Actual result fields: `pca`, `groups`, `group_order`, `sample_ids`, `pca_variance`, `outlier_scores`, `outlier_rule`.

Call: `render_template("pca_outlier", data, ...)`. Legacy output: `fig_qc_pca_outlier.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### batch_umap

Integration before/after · qc

Actual result fields: `stages`, `group_order`, `identity_test_only`.

Call: `render_template("batch_umap", data, ...)`. Legacy output: `fig_qc_batch_umap.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### confounder_assoc

Covariate–PC association heatmap · qc

Actual result fields: `matrix`, `pairwise_n`.

Call: `render_template("confounder_assoc", data, ...)`. Legacy output: `fig_qc_confounder.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### missing_pattern

Missingness matrix + rates · qc

Actual result fields: `matrix`.

Call: `render_template("missing_pattern", data, ...)`. Legacy output: `fig_qc_missing.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### cv_density

CV distribution before/after filtering · qc

Actual result fields: `curves`, `xlabel`, `ylabel`, `title`.

Call: `render_template("cv_density", data, ...)`. Legacy output: `fig_qc_cv_density.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

### norm_density

Normalization shift · qc

Actual result fields: `stages`, `xlabel`, `ylabel`.

Call: `render_template("norm_density", data, ...)`. Legacy output: `fig_qc_norm_density.png/svg`. Original reference: [references/sample-qc.md](sample-qc.md).

