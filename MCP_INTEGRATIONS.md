# Optional MCP integrations (2.11)

BioResearchWorkbench began with Biomni. This release adds optional upstream processes and original restricted adapters. Codex supplies reasoning. Each external component retains its original authorship and license. No additional language-model account or model API key is required for these integrations.

## Components and boundaries

| Component | Use | Default boundary | Acceptance |
|---|---|---|---|
| Serena 1.7.0 | Symbol definitions, references and outlines; optional symbol edits | One selected code project; no shell, project switching, REPL, memories or dashboard | Real Python/Jedi symbol and reference calls |
| Context7 | Version-aware public software documentation | Prefer an existing plugin; only approved public queries | Resolve a library and retrieve relevant documentation separately |
| DuckDB | Inspect selected result tables | Fixed table allowlist, structured bound predicates, read-only database, disabled external I/O, 128 MB and 10 seconds | Query plus foreign-table, write and external-file refusal |
| Qdrant | Retrieve selected private source passages | One collection, find tool only, pinned offline embedding files | Real retrieval plus source-ID/version/hash checks |
| Playwright | Inspect and test browser pages | Isolated browser session; private empty working directory; no existing cookies or unrestricted file access | Actual page navigation, DOM interaction and response checks |
| Docker MCP Gateway | Optional container management for a reviewed tool set | Static single-tool candidate, image digest, no host volumes or secrets, bounded resources | A working owned engine and actual gateway calls are required |
| Slurm monitor | Queue, accounting, resource and selected log observations | Fixed read-only commands for selected job IDs belonging to the current server user | Real scheduler observation required; preparation/parsers are separate |
| Scientific interfaces | Zotero/Cytoscape checks, exports and layout previews | Selected items/network only; reviewed network/version hash before layout dispatch | Connections, actual exports, GUI rendering and writes have separate receipts |

The optional installations are independent environments. Serena and Qdrant currently require incompatible Pydantic versions. Core and local analysis editions keep their existing registrations and dependency boundaries.

## Portable installation

Use Python and uv on Windows, macOS or compatible Linux. Install Node including npm for browser/documentation components. Keep the runtime root and generated profiles in a private directory outside this checkout.

```sh
python install_mcp.py --runtime-root "$MCP_RUNTIME" --components serena duckdb qdrant playwright
```

The installer refuses existing component environments and records installation separately from runtime acceptance. `requirements-mcp-*.txt` pins the tested interfaces and important dependencies. Installed dependency inventories remain private. The core installer does not install these optional environments.

If Context7 is already installed, reuse it. Otherwise its optional process can be installed with `--components context7`; no key is configured by this package. Documentation queries are sent to the Context7 service. Never include private source, drafts, patient information or identifiers in them.

On Windows with an independently provided Node executable, `--node` and `--npm-cli` can select an existing npm CLI. npm uses separate empty configuration files, the official registry and disabled installation scripts.

For Python code, create a Serena project using the separately installed Jedi backend:

```sh
serena project create --language python_jedi "$SELECTED_PROJECT"
```

Use the Serena executable from its optional environment. Preserve existing project settings. Other languages require their own language-server prerequisites and real runtime acceptance. This release does not claim validation of all languages or native HarmonyOS support.

## Scope and client configuration

Create a selected DuckDB file and an explicitly reviewed source index before generating profiles. Generate client fragments privately:

```sh
python configure_mcp.py --runtime-root "$MCP_RUNTIME" --output-dir "$PRIVATE_PROFILES" \
  --project "$SELECTED_PROJECT" --database "$SELECTED_DATABASE" --table-names observations \
  --index-path "$SELECTED_INDEX" --collection selected_sources \
  --node "$NODE_EXECUTABLE" --playwright-cli "$PLAYWRIGHT_CLI" --browser-executable "$BROWSER_EXECUTABLE"
```

`--components` selects a subset. Existing client settings are never overwritten by these helpers. Review and merge only new server sections. Do not duplicate an existing Context7 plugin or rename working biomni registrations. New MCP processes normally become available in a new client session; an old cached process can still expose an older bridge version.

Code access defaults to retrieval. `--allow-code-edits` adds symbol edits only for the selected project. Source comments and instructions remain untrusted. Review changes and preserve an exact source revision before applying edits. No memory write tools are enabled.

The default DuckDB process is the original `duckdb_mcp.py` restricted adapter. The installed upstream MotherDuck MCP remains attributed and optional. Its 1.0.8 ephemeral connections do not reapply initialization SQL, so relying on that mode to enforce disabled external access is insufficient. Arbitrary SQL and connection-switching tools are not exposed by the default adapter.

The Playwright process starts in the private profile folder. Its isolated session does not inherit browser storage. Origin lists are not complete security boundaries; review navigation, downloads, file selection and external writes for each task.

## Offline semantic retrieval

Provision only the fixed public embedding files with the Qdrant environment:

```sh
python provision_mcp_model.py --cache-dir "$EMBEDDING_CACHE"
```

`mcp_embedding_model.json` records the exact source revision and all five file hashes. Query-time adapters verify these files and use offline loading. The compact English model is a retrieval aid; biomedical accuracy, Chinese retrieval quality and source support still need substantive evaluation.

`semantic_index.prepare_semantic_index` requires an explicit source scope, source ID, text, version and location. It creates a hash-bound plan only. Execute the fixed `semantic_index_runner.py` with the reviewed hash in the owned environment. A fresh index and exclusive execution receipt prevent silent duplicate ingestion. Unknown outcomes are investigated before another attempt. `audit_semantic_results` checks returned metadata against the selected source snapshot.

The bounded helper accepts at most 200 selected records and 2 MB of text. Large embedding/index jobs and analysis remain on the server. There is no automatic whole-library import, public vector service or private-text model upload. Zotero remains the source library.

## Slurm and scientific software

`integrations.prepare_slurm_monitor` generates a request and the actual standard-library probe. Copy and dispatch it through the existing shared SSH session on the verified submission host. The probe checks host identity and current job ownership, uses fixed squeue/sacct arguments, bounds output and reads only explicitly selected relative log paths. `inspect_slurm_monitor` checks request hash, timestamp, host and job scope. Empty queues, UNKNOWN records and partial probes cannot establish completion.

`scientific_interfaces.inspect_scientific_interfaces` checks handshakes without enumerating a library. `export_zotero_snapshot` requires specifically authorized item keys and preserves original fields/versions. It performs no library write or cloud request. `export_cytoscape_snapshot` exports one selected network and version. A layout plan binds the exact network/version; `apply_cytoscape_revision` requires its reviewed hash and blocks repeated unknown dispatches. Exports and API receipts do not prove visual or scientific validity.

## Optional container gateway

`prepare_docker_gateway.py` prepares a private static candidate with the reviewed `mcp/fetch` image digest. It does not enable a server, expose a port, mount host files, forward secrets or launch containers. Catalog management depends on the installed gateway's profile feature mode; validate the exact version's flags before activation.

A working owned Docker engine is required. Run the candidate's command with `--dry-run`, then verify actual MCP calls before registration. Keep signature checks enabled; do not use enable-all-servers or automatic dynamic enrollment. For a cluster that prohibits Docker, preserve the ordinary direct process adapters and use its approved container environment. Do not install a root daemon on a login node.

## Acceptance and privacy

`probe_mcp.py` initializes MCP, lists actual tools and executes only the supplied acceptance calls. Each detailed response and stderr file stays in the explicitly selected private output folder. Only server name, state and tool count are printed. A connection without successful substantive calls is marked connected_unprobed.

Run core regression tests separately from `tests/mcp_runtime_check.py` in the optional DuckDB environment. CI also checks real upstream process calls on supported platforms. These checks establish engineering behavior; they do not measure biomedical reasoning quality or validate a live private cluster/library.

Public releases contain source, generic examples, dependency references and attribution. They exclude user directories, addresses, host routes, client fragments, private indexes, software registries, model caches, browser storage, drafts, tokens and runtime receipts. Keep exact public query approval and biological-unit/statistical QC requirements from the existing operating guides.
