# Biomni Direct Tools

Version 2.7 adds a dedicated statistics consultation module, complex expression designs, expanded analysis/review workflows, real server-side Slurm adapters and stronger privacy gates. See [STATISTICS.md](STATISTICS.md), [RESEARCH_WORKFLOWS.md](RESEARCH_WORKFLOWS.md) and [PRIVACY_SECURITY.md](PRIVACY_SECURITY.md). It retains separately packaged server and local analysis editions. The local edition includes mandatory pre-analysis QC, three count-model backends, normalized-expression tests, small single-cell/pseudobulk workflows, pathway/PPI analysis, molecular descriptors, bounded Vina docking and persistent software interfaces. See [LOCAL_ANALYSIS.md](LOCAL_ANALYSIS.md) and [SOFTWARE_INTERFACES.md](SOFTWARE_INTERFACES.md). Platform access remains documented in [PLATFORMS.md](PLATFORMS.md).

A direct Biomni tool layer for Codex. Codex provides reasoning; the bridge provides explicit database queries, literature retrieval, evidence records, metadata lookups and result checks. No additional model API key or local LLM is required.

## Scope

- Selected public genetics, target, protein, structure, pharmacology and literature queries.
- GTEx expression/eQTL/sQTL, Human Protein Atlas, CELLxGENE collection metadata and ENA run/file metadata.
- Server task and inventory preparation, returned lifecycle receipt inspection, output checksum checks, sample-unit audits and small result-table checks.
- Existing lightweight omics helpers with explicit limitations.

Large calculations and large downloads belong on the recipient's own server. Reuse that server's analysis environment. This is not the full Biomni reasoning agent, E1 environment or data lake.

## Cross-platform installation

For macOS and Linux run `sh ./Install.sh`; for HarmonyOS use the compatible environment or browser route in [PLATFORMS.md](PLATFORMS.md). The same lightweight core profile is used across desktop platforms.

## Install on Windows

Prerequisites: Windows x64 and `uv`. The `codex` command is required only for automatic Codex registration. OpenSSH is required for SSH-specific helpers. Installation downloads Python 3.11 if needed, the pinned official Biomni source and Python dependencies.

Download this repository, open PowerShell in its folder, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1
```

The default destination is a new `BiomniTools` folder under the current user's profile. Use `-InstallDir` to select another new folder. Use `-ValidateOnly` to check repository file hashes. The installer refuses to overwrite an existing directory or an existing `biomni` MCP entry. `-SkipRegistration` permits installing separately before choosing how to register it.

### Profiles and other clients

| Profile | Scope |
|---|---|
| `core` (default) | Retrieval, documents, evidence, tasks and CSV/TSV result checks. No numpy, pandas, scipy, torch or model SDK stack is needed. |
| `local` | Bounded local transcriptomics, pathways, PPI and molecular tools. R backends and external software require their own configured installations. |
| `omics` | Core plus optional matrix/H5AD, enrichment and label-transfer helpers. Large analysis still belongs on the server. |
| `full` | Previous dependency snapshot for additional upstream specialist imports; this is not E1 or proof that every upstream function works. |

Use `-Profile omics` or `-Profile full` only when those optional local helpers are required.

For another client, use `-Client claude-desktop`, `-Client vscode` or `-Client portable`. These choices do not require the Codex CLI. The installer generates configuration snippets in a private `client_configs` folder; merge the appropriate snippet into that client's configuration. Existing client settings are never overwritten. Only the Codex choice performs automatic registration.

The formats follow the documented [local MCP configuration](https://modelcontextprotocol.io/docs/develop/connect-local-servers) and [VS Code MCP configuration](https://code.visualstudio.com/docs/agent-customization/mcp-servers). The server protocol and generated JSON/TOML schemas are tested; individual client GUIs and models need their own connection validation. Provider login/API billing belongs to the chosen client and is separate from this tool layer.

Merge the generated `AGENTS.generated.md` Biomni section into your own Codex instructions, then open a new chat. Check `biomni_status`, inspect `biomni_tool_catalog` and test a public query.

If a trusted local DNS proxy uses synthetic addresses, review the proxy setup before explicitly passing `-TrustDnsProxy`. This option trusts that resolver's domain routing; it does not allow private IP literals or local hostnames. It is off by default.

## Server workflow

Configure your own SSH route and verify the current compute hostname. Credentials and server addresses are not bundled. Heavy jobs should not execute on a login node.

`prepare_remote_task` and `prepare_server_inventory` only create bundles. They do not connect or submit. Use your existing shared terminal or scheduler, then return small result files and execution receipts for review. Expected output paths must be fresh. Inspect current processes/logs before recovering interrupted tasks or stale locks.

`inspect_remote_task` reads a receipt snapshot; it is not live process polling. `biomni_job_submit` starts a local bridge worker, not a remote scheduler job. Submission is not completion.

## Privacy and evidence

This repository contains generic source, fixed dependencies and instructions. It does not distribute installation-specific paths, server configuration, credentials, names, research files or runtime receipts. The pinned official upstream source is fetched separately; its public attribution and license are retained.

Runtime records may contain paths, hostnames, parameters and input hashes. Keep them private. Do not attach logs, generated task bundles or result receipts to public issues without review. Runtime directories and credentials are excluded by `.gitignore`.

Import readiness does not establish runtime readiness. Table formatting, caller-supplied context and file integrity do not establish scientific validity. Keep species, model, assay, independent biological unit, contrast and causal limits explicit. Do not send sensitive data to public endpoints without specific authorization.

Tool catalog descriptions are read without importing a scientific/model stack. Upstream `import_ready: null` means its import was deferred. Pass `check_imports=true` for an explicit import check, and inspect optional dependency checks separately. Observed runtime passes remain distinct from dependency presence.

## Verification

### Research helpers

Use `research.select_tools` through `biomni_run_tool` with one of twelve explicit intents: `literature`, `identifier`, `genetics`, `target`, `protein`, `structure`, `expression_metadata`, `sequencing_metadata`, `sample_audit`, `result_audit`, `server_task`, or `small_omics`. It returns catalog parameters, optional dependency checks and observed runtime state. It only prepares a plan. Set `large_computation=true` to select server preparation; `sensitive_data=true` blocks recommendations that would transmit the data to a public endpoint until specific authorization is obtained. These flags guide planning; they do not replace access controls or user consent.

`research.resolve_identifier` checks a single explicit public gene symbol, Ensembl gene ID, UniProt accession, rsID, PDB entry, PubChem CID or ChEMBL molecule ID. Gene/protein/variant queries require a supported species; rsID queries also require an assembly. Ambiguous candidates and source records are retained. Version mismatches, wrong species and unavailable assemblies are reported. Isoform lookups and genome build conversion are not silently substituted. PDB entry checks do not verify chain identity.

`research.audit_identifier_mapping` accepts a small local list of rows with `source_namespace`, `source_id`, `target_namespace`, `target_id`, `species`, `assembly` and `evidence_reference`. It detects malformed IDs, missing context, duplicate mappings, version suffixes and one-to-many/many-to-one joins. It makes no public queries and does not verify caller-supplied source assertions. Keep ambiguous relationships; do not select the first match merely to make a join work.

If the Ensembl symbol service times out or has a server failure, the resolver can collect UniProt gene cross-references and verify each candidate through Ensembl lookup. This fallback retains the failed attempt and marks candidate coverage incomplete (`partial` for a single candidate). A passing candidate identity check does not establish exhaustive symbol mapping; do not use a partial result as a guaranteed one-to-one join.

Official API contracts: [Ensembl symbol cross-references](https://rest.ensembl.org/documentation/info/xref_external), [Ensembl identifier lookup](https://rest.ensembl.org/documentation/info/lookup), [UniProt API](https://www.uniprot.org/help/api_queries), [RCSB Data API](https://data.rcsb.org/), [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest), and [ChEMBL web services](https://www.ebi.ac.uk/chembl/api/data/docs).

Run `python run_acceptance.py` for fixed offline checks. In an installed core environment, add `--network` to test six public identifier cases and an OLS candidate lookup, saving standard bridge receipts. Optional `--output-file` saves a private report and refuses overwriting. An offline pass explicitly says the network suite was not requested. A pass measures listed engineering checks, not general biomedical reasoning or scientific validity.

`python -m unittest discover -s tests -v` verifies synthetic sample/result audits, client formats, stale outputs and privacy gates. `bridge/smoke_mcp.py` verifies MCP discovery and a tiny result-table fixture; add `--network` for a real public database query.

GitHub Actions runs privacy/history/manifest checks and unit tests, then installs the core profile on clean Windows, Linux, macOS ARM and macOS Intel runners and tests MCP over the network. A separate browser check uses synthetic data at desktop and mobile viewport sizes; this does not certify HarmonyOS hardware. Inspect the actual run result before claiming clean-install success. Other client GUI integrations, optional profiles and a real HPC deployment are not implied by a core CI pass.

Before release, follow [PRIVACY.md](PRIVACY.md). The privacy gate scans current candidates and historical blobs, checks generic commit identities and avoids printing matched values. Names and research context still require manual review.

## Upstream and license

Official Biomni: https://github.com/snap-stanford/Biomni

Pinned upstream revision: `400c1f366b96a35ca253e13c9b06c5076af41d65`.

Apache-2.0; see `LICENSE` and `NOTICE`. This repository provides a direct-tool integration layer and is not an official upstream release.
