# Private personal research library

Version 2.8 adds a persistent `personal_library` index beside the source literature manager. Zotero remains the master reference/attachment library; this index holds explicitly selected metadata, research tags, reading status and private notes. It never reads a native Zotero database, modifies source references, uploads content or exposes a public API. Large downloads and analyses still belong on the server.

## Functions

| Function | Behavior |
|---|---|
| `create_personal_library(title, purpose, set_as_default=false)` | Fresh private SQLite index and opaque ID. Optional default pointer is created exclusively; an existing default is not overwritten. |
| `inspect_personal_library(library_id='')` | Explicit/default index title, purpose, revision and reading-state counts; no paper/note retrieval. |
| `prepare_personal_library_ingest(library_id, references_path, source_namespace, tags)` | Preview a supported export or saved Zotero selection. Shows inserts/updates, duplicate-DOI candidates, source fingerprint and expected index revision. |
| `apply_personal_library_ingest(plan_file, expected_sha256, dispatch=false)` | Explicit hash-bound dispatch; atomic SQLite transaction, revision/record conflict checks, before history and fresh receipt. No source-library change. |
| `search_personal_library(library_id, query, tags, reading_state, limit, start)` | Offline literal phrase, tags and reading-state filtering, pagination and completeness. Searches only the selected index. |
| `annotate_personal_reference(library_id, record_id, expected_fingerprint, expected_revision, reading_state, tags, note)` | Explicit private annotation update with history and conflict checks. |
| `export_personal_library(library_id, output_format, query, tags, limit)` | Bounded selected RIS/BibTeX/CSL-JSON export; reports partial selection coverage. No sharing/upload. |

## Workflow

Create an index, then read one explicit Zotero collection/item set or export a selected reference subset. Feed its saved JSON/export into an ingest preview using a stable source namespace such as `zotero:user` or `endnote:project`. Review the preview/hash and dispatch explicitly. Different namespaces remain distinct even when DOI/title matches. Do not count duplicate-source papers or shared cohorts as independent biological evidence.

Search by a topic phrase/tag; update the selected item's reading state (`unread`, `reading`, `reviewed`, `excluded`) and private note with its current fingerprint/revision. Add located evidence via the academic review workflow. Export a selected subset for manuscript citations. A reading label is a personal workflow state, not a validity or eligibility certification.

Records are identified by source namespace plus source item ID. Updates only touch matching source-scoped IDs and preserve private notes/status. New tags are merged during reviewed ingestion. Source records omitted from a partial page are never deleted. A same DOI in another namespace is retained as a duplicate candidate, not automatically merged.

## Boundaries and recovery

An index supports at most 10000 metadata records; each ingest accepts at most 5000 and search/export pages at most 100. Split larger research collections or prepare a server index. This is metadata/note management, not bulk full-text download, vector embedding, automatic recommendation or background synchronization. Full-text PDF inventory and evidence extraction remain separate bounded functions.

Indices, default pointers, history, import plans, source records and reading notes stay under private runtime data/outputs excluded from public packages. The original exported file, source PDFs and Zotero records are preserved. Review plan and database revisions before retrying an interrupted operation; do not infer failure from a missing output receipt. SQLite commits are atomic, but a filesystem failure after commit can prevent writing the final report. Reusing a stale ingest plan is refused.

Source exchange can lose software-specific fields; inspect ACADEMIC_WORKFLOWS.md. Local notes and tags are not automatically propagated into Zotero or exported bibliography fields. Zotero writeback is a separate reviewed, sync-aware action described in ZOTERO_LOCAL.md. No private library is sent to a public search service.

Synthetic tests cover preview-before-dispatch, ingest/revision conflicts, source namespaces, literal wildcard search, annotation/history, source-preserving exports and default-pointer protection. Scientific interpretation and real selected-collection import remain separate user-scoped workflows.
