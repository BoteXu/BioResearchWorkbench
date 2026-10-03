# Expanded research workflows

Version 2.7 preserves server/core and optional local editions. A specialist function being listed, imported or executed on a synthetic fixture is not scientific validation. Review the category, actual dependencies, last attempt, source receipts, QC decisions and complete result tables.

## New analysis and review interfaces

| Category/function | Implemented behavior | Required review |
|---|---|---|
| `advanced.run_designed_expression` | Native limma eBayes, limma voom or edgeR QL with continuous covariates, explicit categorical references, interactions and one numeric contrast | Mandatory count/scale, independent-unit, rank/resource and sample QC; repeated rows require another backend |
| `advanced.import_expression_data` | Bounded 10x MTX or explicitly named H5AD count layer to CSV | Unique source IDs, feature modality, dimensions, finite nonnegative integer values and source provenance; never guess raw-count status |
| `advanced.run_donor_differential_state` | Curated cell-type pseudobulk followed by actual donor-level DE; per-type and across-tested-type BH | Low-cell and failed types remain visible; donors define independent units; caller declares the family of selected types |
| `advanced.analyze_cell_composition` | Donor-level counts, denominators and proportions | Descriptive only; no cell-level p-values or differential-abundance model |
| `advanced.score_regulatory_activity` | Signed weighted target-expression scores with measured-target coverage | Descriptive scoring, not decoupler ULM/MLM, statistical significance or causal regulator activation |
| `advanced.summarize_pathway_overlap` | Selected-set Jaccard redundancy and reviewed leading-edge lists | No automatic term deletion or change to multiplicity families |
| `advanced.audit_network_stability` | Threshold/resolution sensitivity, fixed-node ARI and optional degree-preserving unweighted modularity nulls | A query subgraph is selected; sensitivity/nulls are not independent biological replication |
| `advanced.infer_diffusion_pseudotime` | Scanpy diffusion pseudotime with explicit roots and root sensitivity on a reviewed neighbor graph | Pseudotime is not measured time or lineage tracing; unreachable cells remain visible |
| `advanced.audit_batch_embedding` | Batch/biology silhouettes and label-confounding table | Mixing can erase biology; compare before/after and review independent donors |
| `advanced.audit_cell_communication` | Review returned donor-level ligand/receptor scores, coverage and repeated-unit issues | Does not execute a communication package or establish physical/functional signaling |
| `advanced.evaluate_binary_prediction` | Validation ROC AUC/AP/Brier, calibration bins and fixed-threshold counts after a split audit | No validation-set threshold tuning; metric uncertainty/external validation require further work |
| `advanced.audit_colocalization_results` | Returned posterior, assembly, locus coverage, priors, tissue and signal-model checks | Does not run coloc/SuSiE; H4 alone is not causal-gene or mediation evidence |
| `advanced.audit_redocking_coordinates` | Same-frame heavy-atom RMSD for explicit one-to-one atom mappings | Review chemical equivalence, symmetry and mapping coverage; no guessed alignment or universal pass threshold |
| `advanced.audit_md_summary` | Returned time-series ranges, continuity and block stability | Frames/blocks are not independent simulation replicates; stable RMSD does not establish adequate sampling |
| `molecular.prepare_ligand_meeko` | One reviewed explicit-H 3D SDF to PDBQT | Chemical state, tautomer and stereochemistry must be reviewed; no silent protonation generation |
| `reporting.audit_analysis_result` | Complete output hashes, context, expected contrast/units and preanalysis gate | Integrity is not scientific validity; read complete tests and diagnostics |

Reports are static offline HTML with escaped text, file links, plot previews, bounded table previews, limitations and recursive SHA256 output manifests. No external script/resource or automatic report upload is used. CSV/JSON remains editable. Reports and source receipts can contain private data and must remain private.

## Real server task integration

`server.prepare_scheduler_task` builds a Slurm bundle. Preparation makes no SSH connection and submits no job. Through the user's existing shared terminal, copy it to the verified server and execute `python3 scheduler_agent.py submit .`. The standard-library server adapter invokes `sbatch --parsable`, retains a real job ID, and supports explicit status/cancellation operations. Status reads both squeue and sacct; it does not interpret an empty queue as success. Unrecognized responses/timeouts preserve an unknown-outcome receipt and prevent automatic resubmission. Cancellation preserves logs and outputs.

The portable runner verifies the configured current compute hostname, exact task/input hashes and fresh expected outputs. An allocation to a different node fails this host check; prepare the task only after obtaining the current intended node or use a reviewed scheduler allocation that matches it. No heavy calculation is run on the login node by these preparation tools. Submission/accounting and analysis execution are separate receipts. Result download checks remain in `workflow.verify_remote_results`.

The Slurm subprocess protocol is tested with synthetic responses; a real user's live cluster has not been validated for this release. Cluster routing, modules, account/partition policy and node naming must be checked privately. No automatic recovery, arbitrary remote HTTP API, credentials or generic background SSH service is configured.

## Standard server pipeline adapters

`server.prepare_standard_pipeline` supports:

- `nfcore_rnaseq`: explicitly pinned numeric release, samplesheet, FASTA/GTF, output directory and existing container/runtime profile. Optional resume requires retained compatible work/cache. Read returned MultiQC summaries using `inspect_multiqc_report`; no universal threshold is invented.
- `tximport`: server R helper for a reviewed sample/path manifest and unique transcript-to-gene mapping. It exports the complete tximport object, estimated counts, abundance and effective lengths. Do not round estimated counts and pass them to an arbitrary counts-only workflow; use tximport-aware DE with the appropriate offsets.
- `dream`: server R helper for repeated-measures expression with a restricted model formula, explicit contrast, rank/count/unit checks and existing variancePartition environment. Source parsing is checked; full runtime on the user's server is not yet verified.
- `gromacs_summary`: fixed rms/rmsf/gyrate/energy/hbond preparation with explicit menu/group selections and time options. Review index groups, fitting and periodic-boundary handling. Full trajectories stay on the server.
- `meeko_receptor`: server receptor-preparation command with reviewed input and a fresh output basename. Residues, water, cofactors, metals and protonation remain explicit review decisions.

R helper paths must be reachable from `remote_workdir`; supply a private `script_path` after copying the bundle. The bridge installs none of these server environments and does not assume their packages exist. The helper scripts are provided and syntax-checked; tximport/dream live server execution remains unverified.

## Persistent software and validation states

`software.check_software_health` compares fixed version probes to saved private registrations. `inspect_cytoscape_health` checks only a local CyREST version/layout response. No GUI is installed or started automatically. A missing GUI returns unavailable rather than a successful integration claim.

Open Babel is optional through `requirements-interfaces.txt` or an existing registered installation. One Windows synthetic structure conversion has been executed; its optional binary packaging is not part of the four-platform default local-profile gate. Cytoscape GUI/render/export is not runtime-verified. Maintain those states separately from the passing R, Vina, Meeko and bounded-analysis fixtures.

## Primary references

- [nf-core/rnaseq usage](https://nf-co.re/rnaseq/latest/docs/usage/) and [outputs](https://nf-co.re/rnaseq/latest/docs/output/)
- [Slurm sbatch](https://slurm.schedmd.com/sbatch.html), [squeue](https://slurm.schedmd.com/squeue.html), [sacct](https://slurm.schedmd.com/sacct.html)
- [Dream](https://bioconductor.org/packages/release/bioc/vignettes/variancePartition/inst/doc/dream.html)
- [Scanpy DPT](https://scanpy.readthedocs.io/en/stable/api/generated/scanpy.tl.dpt.html)
- [Meeko preparation](https://meeko.readthedocs.io/en/develop/tutorial1.html)
- [Coloc assumptions](https://chr1swallace.github.io/coloc/articles/a02_data.html) and [prior sensitivity](https://chr1swallace.github.io/coloc/articles/a04_sensitivity.html)
