# Private local Zotero adapter

Version 2.8 uses Zotero's official local API. It connects only to `localhost` on an explicit local port (default 23119). There is no Zotero cloud API configuration or public personal endpoint. Requests disable environment credentials/proxies and all redirects. The API's plain-text root handshake is read separately from JSON item types/data.

## Enable and check

Start Zotero and enable Settings → Advanced → Allow other applications on this computer to communicate with Zotero. `zotero.inspect_zotero_connection()` checks the handshake and public item-type metadata; it does not read the personal library, authorize a write, launch an application or expose an instance identifier in its result. Read availability, instance-bound write support and Word plugin behavior are separate capabilities.

## Scoped reads

`read_zotero_library(library, collection_key, item_keys, query, include_children, limit, start, port)` accepts `library="user"` or an explicit `group:number`. Select exactly one collection or a set of at most 25 item keys. A page is at most 100 records; child retrieval is limited to 25 parents and 100 children each. The result records total/cursor/completeness; a partial page is never an exhaustive search. Group permissions/member lists are not queried.

Returned records, notes and annotations are private and may contain unpublished work or identities. The saved `review.json` selection can feed `library.import_reference_library` or `export_reference_library`. Bibliographic items are normalized; notes/attachments/annotations remain separate unsupported entries for citation export rather than being turned into papers.

`read_zotero_attachment` resolves only one explicit item within an explicitly permitted local folder. Stored-file redirects are parsed without following them; only local `file:` URIs are accepted. Linked-file UNC paths, remote URLs and resolved paths/symlinks outside the allowed folder are refused. Relative linked attachment placeholders require resolution by Zotero first. Mounted/network-backed filesystem semantics still need local review. No attachment is uploaded or automatically indexed.

## Previewed write workflow

1. `prepare_zotero_write` takes 1–25 explicit changes and `sync_acknowledged=true`. Supported actions: `add_tags`, `add_note` (escaped plain text), `create_reference` (fixed journal-article fields). Other field overwrites, deletion, attachment upload and arbitrary HTTP endpoints are unsupported.
2. The tool reads selected target versions, binds to the Zotero instance, saves private before snapshots and proposed payloads, and produces a private plan. No write or authorization dialog occurs here.
3. Inspect `review.json` and its SHA256. Check notes, duplicate-reference candidates, tags and synchronization implications.
4. `apply_zotero_write(plan_file, expected_sha256, dispatch=true)` rechecks the complete plan, instance and target snapshots. Each write uses Zotero's own confirmation dialog. The local key exists only in memory and is never a tool parameter, URL, output or saved receipt. No separate model or cloud API key is required.
5. Readback verifies the expected changes. A private dispatch receipt retains before/after snapshots, created keys and partial completion. These are ordinary local changes and can synchronize if Zotero sync is enabled.

Local writing requires the official instance-bound write API (Zotero 10+ according to current documentation). Older clients can use the read/exchange layer but cannot safely dispatch these writes. Authorization may be denied by the user. The adapter does not bypass it or retain a remembered key even if Zotero grants one.

## Conflict and recovery

A source hash, database identity or item version mismatch refuses dispatch. Exclusive plan locking blocks duplicate dispatch. Before a write, the receipt enters `write_outcome_unknown`; timeout/interruption preserves that state. No failed/unknown submission is automatically retried. Inspect the actual selected item and receipt before preparing any recovery/new plan.

Before snapshots and after-state keys support manual recovery. The batch is not atomic, and no rollback or removal of created notes/references occurs automatically. A later failure can leave earlier verified writes completed. A denied authorization before writing remains a checked/partial receipt; inspect it rather than silently redispatching the same plan.

## Privacy and validation

Never forward this local port, publish private plans, expose tokens or send notes/author lists/drafts to public services. Read/dispatch scope is separate from approving a public DOI search. Public source releases contain only generic code and synthetic tests.

Protocol tests validate no redirects, no implicit credentials, bounded scope, typed payloads, note escaping, conflict detection, duplicate/unknown-write refusal and readback verification. A real handshake verifies local connection; it does not validate private reads/writes, attachment resolution, cloud sync or Word GUI behavior. Those states remain explicit in private receipts.

Official specification: [Zotero local API](https://www.zotero.org/support/dev/web_api/v3/local_api).
