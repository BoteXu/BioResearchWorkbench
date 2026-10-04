# 科研代码开发与审查 / Scientific code workflows (2.10)

Codex provides reasoning, implementation and review. This workbench supplies
bounded source/data checks, version facts, executable test/workflow artifacts and
actual execution receipts. It adds no separate model account, API key or public
personal endpoint. Selected source instructions are untrusted data.

## Scope and execution

Select a project root and an explicit list of relative files. Review refuses
traversal, source links, credential files, more than 200 files, files over 2 MB,
and total source over 12 MB. Table checks accept at most 20,000 rows / 12 MB.
Export larger summaries on the server. No automatic project/library/disk scan.
Every report is private and source hashed. Static findings are review candidates,
not proofs that an error exists or that unflagged code is safe.

The default edition runs only review/preparation. `code_execution` creates server
bundles, not local code workers or scheduler jobs. Explicitly dispatch using an
owned current compute host and the existing shared terminal. Reuse installed
environments; generated files never install packages. The runner is **not an OS
sandbox**: reviewed code inherits its server account privileges. Use an existing
approved isolated account/container for untrusted source. It does not enforce
network isolation or an account-wide resource limit.

## Capability coverage

| Requested increment | Callable implementation | Actual boundary |
|---|---|---|
| Project code map | `code_review.map_code_project` | Python AST imports/definitions/calls; other languages are located lexical candidates |
| Official API/version checks | `prepare_api_migration` | Supplied installed versions + official documentation ledger; Codex verifies sources |
| Paper method reproduction | `prepare_method_reproduction` | Located method/code/parameter mappings, assumption and missing-detail ledger |
| Refactor / debug / repair | `prepare_code_revision`, `materialize_code_revision` | Exact before/after hashes + unified patch, fresh staged files; validation runs separately |
| Notebook state | `audit_notebook`, `code_execution.prepare_code_execution` | Static order/name/output checks; actual clean server kernel execution |
| Data contracts | `audit_data_contract` | Columns, finite types, keys, ranges, categories, units metadata, ordering |
| SQL/table joins | `audit_table_join` | Cardinality/unmatched/expansion checks from selected tables; no arbitrary SQL execution |
| Python/R exchange | `compare_data_exchange` | Keyed values and declared numeric tolerance; textual categories stay distinct |
| Risk-focused tests | `prepare_scientific_test_suite` | Executable equals/numeric/refusal/permutation tests from reviewed assertions |
| Numerical stability | `audit_numeric_results` | Finite/range/CI/probability checks; backend convergence still needs its actual receipt |
| Result properties | Generated permutation/refusal tests | Only scientifically justified caller-supplied properties |
| Scientific result changes | `compare_scientific_results`, `audit_plan_implementation` | Effect/uncertainty/sample metrics + located analysis-plan deviation review |
| Profiling | `prepare_code_execution(mode='python_profile')`, `summarize_performance` | Actual cProfile to bounded JSON; child/native/GPU/memory coverage is incomplete |
| Resource estimation | `estimate_compute_resources` | At least two declared actual pilot measurements; scaling/range/extrapolation explicit |
| Large-data optimization | Versioned code revision + resource pilots | Codex designs chunking/sparsity/cache changes and validates outputs on server |
| Parallel safety | `audit_parallel_execution` | CPU allocation, output collisions, seeds; distinct seeds are not proven independent streams |
| Analysis-to-workflow | `prepare_code_workflow` | Actual Snakemake / Nextflow files with explicit argv/DAG/resources |
| Workflow preview | `preview_code_workflow` | Graph/QC ancestry, output conflict, missing input and resource declarations; no process launch |
| Scheduler arrays | `prepare_code_task_array` | Fixed Slurm array and per-task checksum locks; submission/state require real scheduler receipts |
| Resume/cache checks | `audit_resume_compatibility` | Exact identity/checkpoint comparison and supplied scheduler state; no automatic relaunch |
| Interfaces/panels | `prepare_adapter_development` + existing MCP/CLI/browser client | Typed development client/schema/private escaped review page; no automatic new service |
| Scientific adapter SDK | `prepare_adapter_development` | Fixed invocation/input/output/resource contracts; new backends need reviewed implementation |
| Dependencies/upgrades | `inspect_dependency_locks`, `compare_environments`, configuration migration tools | uv/renv/requirements inspection, differences, fresh-copy reversible JSON migration |
| Release review | `audit_dependency_components`, `audit_release_scope`, repository `audit_release.py` | Provenance/license/vulnerability ledger, selected text checks, separate full-history release scan |

## Scientific acceptance and QC version binding

`bind_analysis_qc` requires a concrete passing QC result, source receipt and a
reviewed assessment. It hashes explicitly selected inputs together with design
and reference versions. `check_analysis_qc` blocks current acceptance when any
dimension changes. A pass applies only to that binding; checksums do not establish
scientific truth. Private binding files are never published.

Generated workflow QC stages must declare `qc_gate_output` among their outputs
and actually write JSON containing `gate_pass: true`. Analysis needs a QC
ancestor. Stage runners preserve source/configuration/external-input hashes,
verify dependency output hashes and reject stale/fresh-output collisions. A
durable exclusive dispatch lock prevents automatic retries after unknown runs.
Inspect live processes, scheduler state, logs and partial files before recovery.
All code/scripts/reference files affecting the result must be declared inputs;
an undeclared dependency cannot be tracked or validated by the runner.

Nextflow tasks use the owned shared project workspace, because fixed stage argv
may use shared server data. Generated generic tasks disable engine caching;
recovery requires the separate identity/checkpoint review and a new reviewed
execution plan. Native Nextflow/Snakemake resume behavior of existing specialist
pipelines retains its own acceptance checks. Independent stages must have
disjoint outputs. Resources are declared per-stage budgets, not measured usage.

## Fixed server modes

`prepare_code_execution` accepts `python_syntax`, `r_syntax`, `python_run`,
`python_tests`, `python_profile`, `notebook`, `dicom_metadata`. Bind every selected
source/data file with SHA256 and choose a fresh output path. Running source
requires `reviewed_code: true`; syntax modes parse without importing/evaluating
the selected source. R parsing uses the existing `Rscript --vanilla`.

Notebook mode uses existing nbformat/nbclient and a selected installed kernel.
It clears saved outputs/counts, executes from a fresh kernel, stops at the first
error and retains partial executed notebook/failure receipts. Original selected
sources are checked for changes. Execution may read other files or run child
processes according to reviewed code; those must be scoped and isolated by the
owned server environment. Cell timeout does not promise cleanup of arbitrary
detached child processes.

Profiling deserializes only the profiler output produced by that exact run;
local review accepts JSON, never arbitrary profiler pickle files. Compare speed
separately using repeated controlled benchmarks. DICOM mode reads metadata only
and keeps pseudonymous outputs private; it does not validate pixel content.

## Development and acceptance

An adapter scaffold is clearly `scaffold_requires_implementation_and_runtime_acceptance`.
Its typed client validates parameters; it does not invent an executable backend,
register third-party code, expose an endpoint or authorize writes. Codex implements
the selected fixed bridge route, validates fixtures and documents runtime scope.
Patch plans and configuration migrations preserve originals and materialize
fresh copies only. Existing project configuration is not silently replaced.

The standard offline suite tests semantic success/refusal cases. Dedicated Linux
CI executes real synthetic Notebook, R parser, DICOM metadata and generated
Snakemake/Nextflow workflows. Public Python CodeQL scanning is separate from
scientific result acceptance. A passing CI fixture does not verify a user's
cluster, private code, real dataset or clinical conclusion.

## Upstream references

- [uv](https://docs.astral.sh/uv/) and [renv](https://rstudio.github.io/renv/articles/renv.html): environment management.
- [Python profiling](https://docs.python.org/3/library/profile.html): cProfile and benchmark limits.
- [Jupyter nbclient](https://nbclient.readthedocs.io/en/latest/client.html): clean kernel execution and partial failure output.
- [Snakemake](https://snakemake.readthedocs.io/en/stable/) and [Nextflow](https://docs.seqera.io/nextflow/): existing workflow engines.
- [GitHub code scanning](https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning): public repository security checks.

Upstream tools retain their authorship and licenses. This project authors the
contracts, fixed adapters, review records, private routing and acceptance checks.
