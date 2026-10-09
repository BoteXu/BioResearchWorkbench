# Privacy and security boundaries

Package 2.13.2 adds bounded private call/memory diagnostics and selected configuration checks. Diagnostics retain opaque IDs, states, timings and memory measurements; no query arguments, result bodies, tokens, personal labels or configuration paths are recorded by the shared layer. Client configuration checks output only counts/issues. Catalog caching remains installation-local and bounded; the separate public identifier cache requires exact public-data approval, is memory-only, and retains its source retrieval time. Private research text and writes are excluded from public query caching. Research summary audits query nothing unless the specifically approved public batch resolver is selected. See [RESEARCH_QUALITY.md](RESEARCH_QUALITY.md).

## Private local tools, no personal public API

The direct bridge needs no separate model provider, model API key or personal remote service. Server installations default to an authenticated owner-local shared HTTP MCP registration; legacy/local profiles retain stdio. The owner starts the shared backend explicitly. Installation does not create an Internet endpoint, connect to SSH, launch a browser gateway, submit server jobs or upload results automatically. Shared execution and private configuration are described in [SHARED_MCP.md](SHARED_MCP.md).

The optional browser gateway defaults to loopback and now refuses non-loopback exposure unless a private policy explicitly allows it; TLS is additionally required outside loopback. No remote gateway is enabled by the installer. Tokens are owner-local files and never embedded in URLs or browser storage. Do not expose a tool host publicly or publish generated client settings.

## Outbound public retrieval

`privacy.inspect_privacy_policy` reports mode/exposure settings without listing private identifiers or paths. `audit_outbound_parameters` checks parameters locally and returns only categories. Public HTTP/database routes reject private absolute paths, address literals, emails, credential formats and privately configured deny terms. Public request sessions disable automatic environment credentials/netrc authentication and automatic environment proxy use. A trusted DNS proxy flag permits synthetic DNS responses but does not authorize sending private parameters.

These rules are defense in depth. They cannot identify every patient name, personal identifier, rare phenotype or sensitive unpublished datum. Codex must still review the query and require the user's specific authorization for sensitive data. Never claim a pattern scan proves anonymity. New analysis functions operate on local files; they do not send expression matrices, clinical tables, structures or reports to a public analysis service.

Private `.local/privacy_config.json` supports `mode` (`public_data_only` or `offline`), `allow_remote_gateway` (default false) and `deny_terms` (private strings). Invalid policy fails closed. The public package contains no configured private values. Offline mode blocks public HTTP/database queries; it does not block owned local CyREST or local file analysis. Remote server dispatch remains manual through the authorized shared terminal.

## Publication exclusions

Never distribute `.env`, credentials, certificates/private keys, private compute/privacy/software settings, generated client snippets, runtime receipts, source snapshots, downloaded data, analysis outputs or logs. Source-only edition ZIPs are built from a reviewed Git tree with complete hash manifests. User paths, host names, addresses, personal emails and identifiers must be checked using a private deny list. Commit author/committer identity is generic. A public repository still reveals its owning account; that association requires explicit consent and cannot be removed by code redaction.

## Execution controls

- Fixed software adapters probe known executable names and fixed version arguments. There is no arbitrary new software runner in the local registry.
- New statistical predictors/contrasts use typed columns and numeric weights; local formula strings are not evaluated. Server dream specifications reject function calls and use restricted model syntax.
- The portable server runner uses argument arrays without shell expansion, verifies current hostname and input hashes, and rejects pre-existing expected outputs.
- Slurm submission preserves unknown outcomes and prevents repeated submission when a receipt or lock exists. Inspect the actual server before any recovery.
- HTML reports escape supplied text, disable active scripts/resources, and remain local. Output review rejects manifest traversal and altered files.
- Synthetic tests use generated fixtures only. They do not publish or require a user's clinical data or server configuration.

Dependency pins, checksums and tests reduce specific risks but do not guarantee absence of vulnerabilities, complete privacy or scientific validity. Keep client/runtime software updated, keep private files under the owner's access controls, and review any future connector's data flow before enabling it.
