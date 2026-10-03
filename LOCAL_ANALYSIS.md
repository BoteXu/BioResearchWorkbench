# Server and local analysis editions

Version 2.6 distributes two source-only ZIP files from the same audited source tree. `edition.json` selects the default installation profile; each archive has its own verified manifest.

| Edition | Default profile | Intended use |
|---|---|---|
| Server | `core` | Retrieval, study/evidence checks, command/task preparation, software inventory preparation and returned-result review. Heavy work runs in your existing server environments. |
| Local | `local` | The same tool layer plus bounded transcriptomics, pathway, network and molecular calculations on your own host. |

The repository checkout defaults to the server edition. Both editions retain MCP stdio and the private browser gateway. HarmonyOS browser devices connect to an owned desktop host; no native HarmonyOS compute runtime is claimed.

## Installation

On macOS/Linux, extract the chosen release ZIP and run `sh ./Install.sh --client portable --skip-registration`. On Windows run `powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -Client portable -SkipRegistration`. The archive chooses its default profile. When installing from the repository, choose `--profile local` or `-Profile local` for local analysis. Use a fresh installation directory. Defaults are `BiomniTools` / `biomni` for the server edition and `BiomniLocalTools` / `biomni-local` for the local edition, allowing both to coexist. Use `--mcp-name` or `-McpName` to choose another private client name.

The local profile installs scientific Python packages, including PyDESeq2, Scanpy, RDKit and GSEApy. It excludes torch and a separate model stack. RDKit is pinned to its compatible Intel macOS release on that platform; actual backend versions are recorded in results. The installer does not install R, Open Babel, server alignment software or a data lake. Reuse existing compatible environments.

For docking add `--install-vina` (POSIX/Python) or `-InstallVina` (PowerShell). This downloads a fixed official Vina 1.2.7 executable with a checked SHA256 into the private installation. An existing Vina can instead be registered through `software.register_local_software`.

Normalized-expression analysis and optional count backends require an installed R with `limma` and `edgeR`. Install only missing packages in the intended R environment using the official [Bioconductor installation instructions](https://bioconductor.org/install/); record the resulting package versions. The bridge never installs R packages during an analysis. Use the software registry to retain the intended Rscript path. Package presence is not runtime proof.

## Required QC before formal analysis

`qc.preflight_transcriptomics` accepts an explicitly declared `raw_counts` or `log2_normalized` matrix. It performs input, alignment, replicate/design, resource and sample checks without fitting differential-expression models. Bulk and normalized-expression workflows repeat the mandatory gate on the exact bytes before fitting, so changing an input invalidates the previous input hash.

Checks and retained outputs include:

- Unique identifiers and rectangular CSV/TSV; no missing/nonfinite numeric values or automatic duplicate collapse.
- Raw integer count checks, declared processing scale and source context. Integer values alone do not prove raw counts.
- Exact sample/metadata sets with explicit alignment; no silent sample intersection.
- Independent biological units, minimum three units per condition, complete pairing and no repeated unit/condition observations.
- Categorical model covariates, full design rank and residual degrees of freedom. Confounded designs block analysis.
- Raw library totals, detected genes, zero fractions and depth relative to the median. Empty or extremely imbalanced libraries block analysis.
- Constant features/samples, Pearson and Spearman sample correlations and exploratory PCA. No sample is automatically removed.
- Input hashes, decision fields, warnings, QC tables and an independent HTML/JSON report.

A failed input/design check returns a failure receipt. A completed QC report can still have `qc_gate_pass=false` and `formal_analysis_allowed=false`. Review the actual decisions. Revise inputs/thresholds with scientific justification before re-running; the bridge offers no flag that simply bypasses a failed gate.

Cell workflows retain all-cell QC before clustering, including detected genes, counts, mitochondrial fraction and explicit filtering decisions. The mitochondrial prefix must match measured identifiers. If more than half the cells fail QC, the workflow blocks clustering for input/threshold review. PPI and docking have their own input QC gates before their calculations.

## Analysis methods and inputs

| Tool | Implemented methods | Required input and limits |
|---|---|---|
| `transcriptomics.run_bulk_rnaseq` | `pydeseq2_wald`, `edgeR_ql`, `limma_voom` | Declared unnormalized integer gene counts; explicit case/control, unit key, optional pairing and categorical covariates. No TPM/FPKM, rounded normalized values, interactions or continuous-covariate inference. |
| `transcriptomics.run_normalized_expression` | R limma `ebayes` or `treat` with an explicit log2 effect threshold | Already processed log2 expression with documented platform normalization. No raw CEL preprocessing, RMA or automatic probe-to-gene mapping. |
| `transcriptomics.aggregate_pseudobulk` | Exact sums by curated cell type and biological unit/condition | Raw cell counts, unit/condition/cell-type metadata and minimum cells. Low-cell groups are retained in the exclusion audit. Aggregation alone is not differential expression. |
| `transcriptomics.run_small_single_cell` | Scanpy QC, total normalization, log1p, HVG, PCA, neighbors, UMAP, Leiden resolution grid; exploratory Wilcoxon or t-test cluster markers | Small gene-by-cell count table with unit metadata. Optional Scrublet requires an explicit library key; removal occurs only if requested. No automatic cell identity or batch integration. |
| Existing `omics` enrichment | Hypergeometric ORA with a tested-gene universe; seeded preranked GSEA | Local species/identifier-matched GMT/JSON and explicit statistics. Differential-expression pipelines run ORA separately for up and down genes. |
| `systems.score_pathway_activity` | Rank-based ssGSEA | Log2 normalized expression, sample metadata, local gene sets, gene-set source/version and namespace. Coverage and rejected sets are retained. No group-level p-value or activation claim is inferred. |
| `systems.analyze_ppi_network` | Components, isolates, degree, weighted degree, sampled betweenness, closeness, Louvain communities | Explicit edge ID/source/target/0..1 confidence table, source/version and physical/functional/unknown type. Self edges and low scores are excluded; duplicate pairs retain maximum confidence. |
| `qc.compare_analysis_results` | Pairwise effect rank correlation, sign agreement and significant-set Jaccard | Complete tables for the same intended contrast. Agreement on the same data is sensitivity analysis, not replication or a pooled effect. |
| `molecular.molecular_descriptors` | RDKit weight, estimated logP, TPSA, hydrogen-bond counts, rotatable bonds and formal charge | Up to 100 explicit SMILES; invalid strings remain visible. These are calculated descriptors, not measured ADMET. |
| `molecular.run_vina_docking` | One ligand, rigid receptor, Vina scoring | Prepared PDBQT, explicit box, context and bounded CPU/search parameters. Syntax/geometry checks do not validate preparation chemistry. |

Default matrix limits are 200 MB per file, 20 million entries, 60,000 features, at most 500 bulk observations or 10,000 cells, and a conservative memory gate. These are guardrails, not guarantees of peak memory or runtime. Oversized work returns a server recommendation. Long local workflows should use `biomni_job_submit` and actual completion receipts; this is not an HPC scheduler.

## Returned outputs and audit trail

Every run uses a fresh output directory. Successful workflows retain all result tables, QC, model design, exact contrast, input/output hashes, backend/package versions, parameter choices and warning records. Bulk retains filtered genes, normalized counts, PCA and volcano output. Single-cell retains raw counts in `processed.h5ad`, QC, cluster assignments, resolution stability and exploratory markers. PPI exports GraphML plus metrics and a clearly marked display subset. Vina retains prepared inputs, parameters, poses and raw backend log.

Missing/undefined tests remain in the complete differential table. Failed/interrupted runs keep their state, logs and partial files; inspect them before retrying. A succeeded receipt and file integrity establish engineering completion, not biological truth, clinical utility, causal mechanism or experimental target binding.

The local edition is an explicit installation choice. The server edition refuses new formal local compute calls while still exposing preparation, retrieval and lightweight review routes. Your existing server pipeline remains under your control; verify the current compute host and reuse its environments before submitting heavy work.

## Method references and verification

Implementation follows the primary [PyDESeq2 workflow](https://pydeseq2.readthedocs.io/en/stable/auto_examples/plot_minimal_pydeseq2_pipeline.html), [Scanpy clustering workflow](https://scanpy.readthedocs.io/en/stable/tutorials/basics/clustering.html), [limma guide](https://bioconductor.org/packages/release/bioc/vignettes/limma/inst/doc/usersguide.pdf), [edgeR package](https://bioconductor.org/packages/edgeR/), [GSEApy tutorial](https://gseapy.readthedocs.io/en/latest/gseapy_example.html), [STRING API](https://string-db.org/help/api/) and [Vina docking guide](https://autodock-vina.readthedocs.io/en/latest/docking_basic.html).

`tests/analysis_check.py` runs real selected backends on fixed synthetic inputs, checking contrast direction/reversal, mandatory QC refusal, exact pseudobulk sums, pathway/network behavior and toy docking execution. Such checks establish listed software behavior; they do not validate docking accuracy, general biomedical reasoning or a real study. Inspect the actual release CI result and its platform-specific jobs before claiming verification. Open Babel and a real Cytoscape GUI require separate installed-software checks; native HarmonyOS and Linux ARM64 remain outside the clean-install matrix.
