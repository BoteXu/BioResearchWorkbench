# Publication privacy

Only generic source and documentation belong in this repository. Runtime records and generated client settings contain local paths, hostnames or research parameters and must remain private.

Before committing or publishing:

1. Review staged source and documentation manually for identifying names, study details, paths, addresses and credentials.
2. Run `python audit_release.py --history`. Optionally provide `--deny-file` pointing to a private list of additional identifying terms; do not publish that list.
3. Refresh hashes with `python update_manifest.py`, then run `python audit_release.py --history --manifest`.
4. Use the generic commit name `Project Contributors` and reserved example address `contributors@example.invalid` for both author and committer. Do not copy another workspace's history.
5. Build release archives from the audited Git tree, not from an entire working directory.

CI rejects matching address/path/key/email patterns, tracked runtime files, manifest differences and non-generic commit identities. It scans current candidates and historical blob contents without printing matched private values.

Automated scanning cannot identify every personal name or private research context. Manual review remains necessary. Public repository ownership associates the repository with its hosting account; this is outside source-code anonymization.

Never attach runtime logs, generated configurations, task bundles or result receipts to public issues without a separate review.
