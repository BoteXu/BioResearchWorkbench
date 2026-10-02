# Biomni Direct Tools

A direct Biomni tool layer for Codex. Codex provides reasoning; the bridge provides explicit database queries, literature retrieval, evidence records, metadata lookups and result checks. No additional model API key or local LLM is required.

## Scope

- Selected public genetics, target, protein, structure, pharmacology and literature queries.
- GTEx expression/eQTL/sQTL, Human Protein Atlas, CELLxGENE collection metadata and ENA run/file metadata.
- Server task and inventory preparation, returned lifecycle receipt inspection, output checksum checks, sample-unit audits and small result-table checks.
- Existing lightweight omics helpers with explicit limitations.

Large calculations and large downloads belong on the recipient's own server. Reuse that server's analysis environment. This is not the full Biomni reasoning agent, E1 environment or data lake.

## Install on Windows

Prerequisites: Windows x64, `uv`, OpenSSH, and an available `codex` command for automatic MCP registration. Installation downloads Python 3.11 if needed, the pinned official Biomni source and fixed Python dependencies.

Download this repository, open PowerShell in its folder, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1
```

The default destination is a new `BiomniTools` folder under the current user's profile. Use `-InstallDir` to select another new folder. Use `-ValidateOnly` to check repository file hashes. The installer refuses to overwrite an existing directory or an existing `biomni` MCP entry. `-SkipRegistration` permits installing separately before choosing how to register it.

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

## Verification

The source and bridge have been checked in a relocated environment. `bridge/smoke_mcp.py` verifies tool discovery, a public database query and a tiny specialist fixture. An installation on a new machine still needs its own smoke test. No claim of a complete independent-machine or HPC deployment is made.

## Upstream and license

Official Biomni: https://github.com/snap-stanford/Biomni

Pinned upstream revision: `400c1f366b96a35ca253e13c9b06c5076af41d65`.

Apache-2.0; see `LICENSE` and `NOTICE`. This repository provides a direct-tool integration layer and is not an official upstream release.
