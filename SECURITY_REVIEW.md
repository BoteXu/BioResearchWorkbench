# Security review for 2.10

CodeQL completion is separate from alert triage and from scientific validation.
The initial Python analysis reported thirteen alerts, reviewed as follows.

| Location / rule | Reviewed boundary and action |
|---|---|
| `review_ext.py`, numeric citation regex / `py/redos` | Confirmed ambiguous nested repetition. Replaced with separated numeric tokens; a malformed 10,000-digit citation is a regression fixture. |
| `bridge.py`, result writes / `py/path-injection` | Public tool entrypoints select exact registered category/name pairs before executing. Added an independent bounded identifier whitelist inside the receipt writer to protect future callers. |
| `web_gateway.py`, returned result reads / `py/path-injection` | The API builds its receipt through registered bridge calls; client-supplied receipts are not accepted. Added resolved-parent confinement to the bridge results directory and refusal of result symlinks. A forged outside result is a refusal fixture. |
| `bridge.py`, `_input_files` / `py/path-injection` | Intended reads of explicitly selected owner files to record metadata and hashes in private receipts. No implicit disk/library discovery. This privileged local API is not a multi-user filesystem sandbox; token holders must be trusted as the tool-host owner. |
| `evidence.py`, `atomic_json` / `py/path-injection` | Internal writer, not an exposed tool. Callers construct destinations from fixed runtime folders and generated identifiers, or already validated private search/job identifiers. The writer remains a generic internal API; new call sites require destination review. |

The remaining intentional owner-file operations are documented for manual review,
not hidden with inline scanner suppressions. Alert status alone is not evidence
of an exploitable trust-boundary crossing or of complete safety. Later changes
and new call sites require renewed review.

## Deployment boundary

Default privacy policy disables remote gateway exposure. Optional browser access
is a privileged owner interface, with authentication, origin checks, bounded
request bodies and TLS required outside loopback. It is not a service for
untrusted users. Reviewed server scripts inherit their account's privileges;
fixed adapters do not supply OS or network isolation. Use an existing approved
isolated account/container for untrusted source.

Private configurations, registries, drafts, libraries, input files, execution
receipts and logs are excluded from source archives. Publication checks include
selected source content, release manifests, complete Git history and archive
contents. Pattern checks cannot prove complete anonymity; the public repository
account remains visible.
