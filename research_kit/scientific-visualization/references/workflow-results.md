# Native workflow results and figure selection

This private update connects the teaching-workflow source review to result-only
figures. `assets/workflow_channels.json` maps all 49 v3.3 routes to existing
figure families, exact output roles and interpretation boundaries. These are
49 semantic mappings, not 49 newly executed engines or automatic object decoders.
The original 140 figure IDs, 22 modules and seven composite recipes remain.

## Choose the ingestion path

- A selected frozen TSV from another workflow: use the existing Biomni
  `research_quality.prepare_figure_handoff`, then
  `handoff_views.handoff_plan`. `render_handoff_pca` consumes actual stored PC
  coordinates, labels and supplied explained variance without fitting PCA.
- A completed private native run: use `native_figures.plan_native_figures`.
  It verifies request/receipt/current-source bindings, returned QC and every
  explicitly selected output file. A changed source expires old acceptance.
  `selection` maps each role to a list of exact receipt paths, preserving
  repeated roles. More than one file requires an explicit selected path.
- A model/H5AD/RDS object: prepare a bounded frozen display export using the
  existing server environment. Do not execute or unpickle a model, fit an
  embedding, aggregate cells into new biological replicates or install a local
  analysis stack merely to make a panel.

```python
from native_figures import plan_native_figures, render_native_shap

plan = plan_native_figures(
    request_path=selected_request,
    receipt_path=selected_completed_receipt,
    output_root=selected_return_directory,
    acceptance_path=selected_return_check,
    selection={
        "shap_values": ["model_shap.npz"],
        "shap_summary": ["model_shap_summary.tsv"],
        "shap_identity": ["model_shap_identity.tsv"],
        "shap_diagnostics": ["model_shap_diagnostics.json"],
    },
    expected_source_sha256=reviewed_current_server_source_hashes,
)
fig, metadata = render_native_shap(
    plan, model=actual_model_name, width="double",
    outdir=private_figure_directory, stem="model_contributions_reviewed",
)
```

The selected names must be actual producer receipt paths, never invented example
outputs. The SHAP loader reads four real result files and checks dimensions,
feature/unit identities, complete magnitude summaries, background/test membership,
the explained output and actual output-scale additivity. It imports no SHAP
engine and executes no predictor. Identity-link probability values stay in
probability units; a decision function is not automatically log-odds. Regression
must declare its actual response unit. An unspecified response scale is held.

Default: sample swarms with a small calibrated rose inset in reserved space.
Keep `variant="swarm"`, `variant="rose"`, `variant="beeswarm_rose"` and
`variant="reference_classic", layout="compact"` available. The last option
retains the earlier rose/ring companion. Feature colors from mixed raw units
use an explicitly labeled within-feature range (Low–High), with constant
features at the midpoint. This is color mapping only; no standardization or
change to SHAP values is performed. Genuine prestandardized color channels can
declare their limits and units instead.

## Callable result views

| Actual channel | Entry / presentation | Required distinction |
|---|---|---|
| Native SHAP NPZ + summary + identity + diagnostics | `render_native_shap` | Output scale, link, background, unit IDs, complete feature denominator |
| Bounded numeric TSV with literal axes | `render_native_matrix(plan, role, path=...)` | Source order by default; no silent normalization, imputation or reclustering |
| BATCHIE combination table | `render_batchie_intervals(plan, row_ids=...)` | Mean with Q05–Q95 **90% posterior credible interval of conditional mean**, not a 95% CI or biological replicate |
| ProteinTalks exact prediction NPZ | `render_proteintalks_checkpoints(plan, feature_ids=..., ncols=...)` | Three **discrete** native checkpoints, trained labels 6/24/48 h; no invented continuous physical-hour curve |
| Frozen source hierarchy | `render_template(..., data={..., "row_linkage": ..., "row_linkage_ids": ..., "column_linkage": ..., "column_linkage_ids": ...})` | Exact unchanged matrix axis identities must accompany each supplied linkage; preserve hierarchy method and distance, never substitute Euclidean TOM clustering |
| Stored PCA FigureHandoff | `render_handoff_pca(handoff_path, width=...)` | Stored coordinates, all samples, actual variance fractions, original units |

Matrix roles accepted directly include estimated proportions/abundance,
reference signatures, transport coupling, modality attention, program decoder
projection, fused similarity, module eigengenes, PROGENy activity, explicit
unit profiles and latent matrices. Unknown object formats fail clearly.
Named heatmaps are limited to 80 rows per readable page; select/paginate larger
exports explicitly. Attention and decoder weight matrices keep their model
labels. They cannot be relabeled as observed biological contributions.

## Preserve interpretation across workflows

- **DestVI / cell2location:** actual normalized `get_proportions()` output is
  distinct from unnormalized estimated cell abundance. Do not silently turn
  Q05 abundance into percentages, exact counts or mean abundance. Gamma stays
  a latent state. Keep section/spot identities and the real biological unit.
- **CausCell:** native `Original` is a model reference reconstruction. Keep
  it separate from observed input and generated counterfactuals. Preserve
  concept labels, assumed DAG, source-cell identities and actual validation
  scope. Computational pairing is not an experimental pair.
- **CINEMA-OT / CellOT / scGen / scVIDR / biolord:** retain the actual feature
  scale and scenario. A log1p difference is not log2FC; a generic author
  feature space is not automatically a gene matrix. Never promote optimizer
  cell splits or controls seen in training to held-out donor validation.
- **WGCNA / hdWGCNA / multi-omics:** use real power/TOM/module/ME/membership
  exports and supplied trees. DIABLO loadings, SNF similarity and CellCap
  projections are different result quantities. A pretty cluster does not
  establish biological independence or external model validation.
- **Systema / general ML:** centroid rank fraction is not binary nearest-class
  accuracy. Curves use the actual positive label, class order, partition,
  threshold and validation scope. Unspecified validation stays unspecified;
  no automatic malignant label or five-fold OOF assertion.
- **PRESCIENT / ProteinTalks / BATCHIE:** simulation replicates are not donors;
  learned potential is not thermodynamic free energy; phenotype probability
  is not a continuous synergy score; posterior mean uncertainty is not a
  new-observation predictive interval.
- **DiffDock / DiffSBDD / RFdiffusion / MACE / genetics:** pose confidence is
  not affinity; generated geometry is not demonstrated function; molecular
  single-point energy/force is not ESP or binding free energy; annotation,
  SMR and HEIDI must preserve their allele/LD/assumption boundaries.

## Acceptance

Every exact final export starts `RENDERED_UNREVIEWED`. Inspect 1–2 images per
batch at their actual target size, fix and re-render affected files. Record
numeric identity, rendering, visual inspection and any browser interaction
separately. Do not infer a complete 140-template visual re-review from these
targeted source/adapter changes. Keep examples and receipts outside the skill.

The teaching v3.3 engines were not run or remotely probed in this update.
`NOT_RUN_THIS_UPGRADE` / `NOT_PROBED_THIS_UPGRADE` describes this upgrade,
not the current availability of the server. Missing native runtime evidence
must not be replaced by a synthetic success receipt or an attractive example.

Primary semantic references: [SHAP output/link units](https://shap.readthedocs.io/en/latest/generated/shap.Explainer.html),
[original scvi-tools DestVI output](https://docs.scvi-tools.org/en/stable/api/reference/scvi.model.DestVI.html),
[cell2location author tutorial](https://cell2location.readthedocs.io/en/latest/notebooks/cell2location_tutorial.html).
Use the pinned producer version; newer DestVI implementations may live in
scVIVA-Tools and are not silently substituted for a pinned old checkpoint.
