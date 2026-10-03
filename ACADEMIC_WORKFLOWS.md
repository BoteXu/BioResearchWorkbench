# Academic review and manuscript collaboration

Version 2.8 adds 25 registered functions in `library`, `zotero`, `review` and `collaboration`. Both server/core and opt-in local editions expose these bounded workflows. No second model, cloud writing service, heavy analysis package or personal public endpoint is added. Codex supplies authored reasoning; functions extract, locate, compare, validate and save private artifacts.

## Workflow and evidence boundaries

1. Select a local reference export or one explicit Zotero collection/item set.
2. Inspect the manuscript and source documents. Confirm extraction, including empty PDF pages and Word fields/comments.
3. Review evidence at exact locations with species, model, assay, independent unit, contrast and limitations.
4. Approve public query strings before similar-study or DOI metadata retrieval. Drafts, local facets and library records are not sent.
5. Prepare sections and figure plans from declared results. Keep completed, partial, planned, failed and negative states separate.
6. Assemble supplied reviewed/unresolved prose with reference and evidence IDs. Generate a diff and located revision rather than overwriting the original.
7. Audit reporting, numerical consistency, citation mapping, terminology and supplied official journal requirements.
8. Generate a coauthor comment ledger or reviewer response. Nothing is messaged, shared, synchronized or submitted by the collaboration tools.

Saved outputs contain an editable JSON record, offline escaped HTML report, requested text/document files and a SHA256 file manifest. They can contain unpublished text, names, notes and paths. Keep them private. A receipt or matching excerpt does not establish scientific truth.

## Library exchange

| Function | Contract |
|---|---|
| `library.import_reference_library(path)` | RIS, balanced ordinary BibTeX, CSL-JSON, normalized JSON, EndNote XML or a saved Zotero selection. Retains source fields and reports unsupported entries. No native database access. |
| `library.audit_reference_duplicates(path)` | Equal DOI and equal title/year candidates; missing metadata. No automatic deletion or merging. |
| `library.export_reference_library(path, output_format)` | `ris`, `bibtex` or `csl-json`; retained journal/volume/issue/page fields where available. New author strings remain literal names. |
| `library.index_pdf_folder(folder, max_files)` | One explicit nonrecursive folder, at most 100 PDFs, 10 MB per PDF; first-three-page DOI candidates and file hashes. No OCR/upload. |

Exchange formats are not lossless bidirectional synchronization. EndNote/Paperpile/Mendeley and other software can supply supported exports; no undocumented native API or running database write is claimed. Attachment links, notes, group permissions and citation keys need review. BibTeX macros/TeX accents are not evaluated; export of unresolved macros is refused. Unsupported BibTeX syntax is refused rather than silently skipped. UTF-8 exports are required. Numeric EndNote reference types without names need review; no undocumented numeric type mapping is inferred.

## Review functions

| Function | Checks and boundaries |
|---|---|
| `review.inspect_manuscript` | PDF pages, DOCX paragraph indexes/current text, Word fields/comments, Markdown/text/LaTeX lines. No layout certification, OCR or instruction execution. |
| `review.audit_claim_evidence` | Exact claim location, bibliography IDs, source excerpts and SHA256, complete evidence context and explicitly supplied support/contradiction/insufficiency decisions. No inferred semantic support. |
| `review.audit_paper` | Calls statistics consultation; flags located causal/computational-validation/novelty wording for context review; compares explicitly supplied same-estimand numeric mentions. No image-fraud verdict or automated statistical reanalysis. |
| `review.audit_review` | Systematic/scoping/narrative operational topics, declared search dates/counts, exclusion reasons, screening accounting, inclusion/evidence mapping and supplied cohort/dataset overlap. Not the full official PRISMA checklist or a bias instrument. |
| `review.audit_reporting_checklist` | Any supplied complete, officially sourced/versioned PRISMA, CONSORT, STROBE, ARRIVE or journal profile. Every intended item remains reported/not-reported/unclear/not-applicable/not-assessed with located excerpts and rationale. No overall quality score. |
| `review.audit_manuscript_format` | Citation keys, Zotero embedded instructions/URI mapping, unresolved EndNote fields, numbering candidates, headings, approximate word count and explicit journal rules. Numeric references require their own mapping; native citation-style refresh remains necessary. |
| `review.audit_terminology_units` | Explicit glossary expansions/first-use order and located declared quantity/unit mentions. No guessed expansions, automatic unit conversion or universal SI certification. |
| `review.find_similar_studies` | 1–5 explicitly approved Europe PMC queries, 1–100 results per first page, local lexical/facet comparison and dataset overlap candidates. Stores exact queries, hit counts, cursor and partial-coverage state. No global-first, plagiarism or exhaustive-review verdict. |
| `review.check_publication_updates` | 1–25 public DOIs, Crossref deposited update/retraction relationships. Failures and absent metadata remain uncertain. |
| `review.audit_reference_metadata` | Explicit export subset of 1–25 records; sends DOIs only to Crossref and compares title/year candidates. Author/source fields remain local inputs; official returned metadata remains evidence, not an automatic overwrite. |

Use `inspect_manuscript` to obtain locations and hashes before claim/revision tools. Excerpt matching normalizes whitespace/case; it does not evaluate negation or surrounding context. Numeric comparisons require comparable endpoints/units. Rules can flag a negated or quoted claim and must be interpreted by Codex/humans.

### Versioned journal/checklist profiles

`journal_rules` requires `journal`, official `source_url`, `checked_on` (ISO date), `version`, and optional `max_words`, `required_sections`, `required_statements`, `exact_patterns` (literal strings, never arbitrary executable regular expressions). Word counting is approximate and includes text the journal might exclude. Without a profile only generic checks run.

`checklist_profile` requires `name`, `version`, official `source_url`, `checked_on`, and complete intended `items=[{"id":"item1","requirement":"Reviewed requirement"}]`. The user/Codex verifies the current official source and applicability before supplying the profile. The tool preserves every supplied item and the assessment rationale. Do not equate reporting completeness with low bias or valid inference.

`citation_mapping` maps document/numbered item IDs to known exported bibliography IDs. Zotero field URIs can map directly when their item key matches a selected reference. Ambiguous/unmapped citations remain findings; no title-only guess resolves them automatically.

## Manuscript collaboration

| Function | Behavior |
|---|---|
| `collaboration.plan_manuscript` | Study/statistics consultation, section/figure plan, result states and verified-local/declared-unchecked source hash distinction. Planned/failed results are excluded from completed Results. |
| `collaboration.build_evidence_draft` | Assemble supplied paragraph text into editable Markdown and a LaTeX section fragment plus a reference/evidence map. Reviewed prose requires evidence IDs; unresolved prose is visibly marked. No generated claims or fabricated references. |
| `collaboration.compare_manuscript_versions` | Located text diff, added/removed citation candidates and complete Word field instruction comparison. No automatic merge. |
| `collaboration.prepare_manuscript_revision` | Fresh output tied to a reviewed source hash and complete old paragraph/line. Citation-key changes are refused. Conservative Word tracked changes preserve original package parts. |
| `collaboration.manage_collaboration_review` | Located comments, caller-declared owners/status/reasons, dependency cycle checks and blocked resolution checks. Private sidecar ledger, not a live multiuser editor or Word comment insertion. |
| `collaboration.prepare_reviewer_response` | Editable point-by-point response, actual revised locations and optional result source hashes. Completed/planned/declined/clarification states remain explicit. No message or journal submission. |

Word revisions only support simple uniformly formatted text paragraphs. Field-bearing paragraphs, multi-paragraph field ranges, existing tracked revisions, hyperlinks, bookmarks, non-text runs and mixed formatting are refused. The adapter preserves Zotero/EndNote field content in other paragraphs and all other ZIP parts, adds generic-author tracked insertions/deletions, and keeps the original file. Complex edits require native Word. Word/Zotero refresh, acceptance of revisions and rendered visual inspection must occur before submission; package/text tests are not live Word integration validation.

LaTeX output is a project section fragment, not a compiled standalone document. No model API key or writing service is invoked by any function. Processing by the current conversational model is distinct from offline file operations; never describe material sent to a model as staying wholly on the device.

## Validation states

Synthetic tests cover format round trips, exact excerpt/hash failures, metadata/query boundaries, screening overlap, unit/glossary checks, unassessed checklist items, revision conflicts, Word field protection (including split/spanning instructions), comment dependency cycles, explicit result states and local Zotero protocols. A responding local Zotero API establishes connection only. Private collection/attachment reads and live writes need explicit scope and reviewed dispatch; Word GUI integration and actual coauthor workflows remain separate validations.

## Primary references

- [Zotero local API](https://www.zotero.org/support/dev/web_api/v3/local_api)
- [Zotero Word integration](https://www.zotero.org/support/word_processor_integration)
- [PRISMA 2020 checklist](https://www.prisma-statement.org/prisma-2020-checklist)
- [EQUATOR reporting guideline library](https://www.equator-network.org/library/)
- [Crossref Retraction Watch metadata](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)
- [Paperpile export documentation](https://paperpile.com/h/export-library-data/)
