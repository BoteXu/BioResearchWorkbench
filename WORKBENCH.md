# Research workbench 2.9

BioResearchWorkbench began with Biomni. These additions supply original bridge and
workflow integration. Upstream scientific packages retain algorithm attribution.
No separate model, API key or data lake is added.

## Private project, workflow and evidence

`workbench.create_research_project` creates an empty private revisioned SQLite
project. Supply question, study design, analysis plan and species/model/assay/
independent unit/contrast/limitations. `prepare_project_revision` previews selected
changes; `apply_project_revision` requires the reviewed hash and explicit dispatch.
Concurrent changes fail closed. No full library or research directory is imported.

Datasets, claims, located source evidence, figures and stages have globally unique
IDs; directed edges have `source,target,relation`. Keep source page/line positions,
versions, support assessments and limitations. A supports edge is a recorded
judgment, not proof. `audit_project_lineage` traces downstream impact of changed
sources and compares supplied private cohort IDs/pseudonymous subject tokens.
Missing lineage stays unknown; distinct accession IDs do not prove independence.

Stages specify `id,kind,placement,depends_on`; kinds are qc/analysis/check/figure/
report and placement is local_review/server. Analysis requires a QC ancestor and
all dependencies must be accepted. Executed stages cannot be edited away: create
a new stage for revised analysis. `execute_workflow_stage` executes one explicitly
dispatched allowlisted local QC/check, preserving a real bridge receipt. It does
not run arbitrary plugins, network queries, shell commands or remote jobs.

`advance_workflow_stage` records prepare/submit/observation/acceptance for server
tasks. Submission needs a real job/process ID. Completion needs successful runner
output hashes bound to the prepared task. Original receipts are copied privately
with hashes. Acceptance requires checks, a pass decision and limitations; read
individual issues even when a tool succeeds. Unknown submissions cannot be
resubmitted: inspect real scheduler/process/log state via the shared terminal.
`build_project_dashboard` renders a private escaped HTML state snapshot with
blockers, recovery actions and supplied software observations, not live monitoring.

`freeze_reproduction_package` copies explicitly selected bounded results, hashes,
the project plan, environment/reference versions and exact command records. It
freezes provenance; actual rerun agreement and scientific validity are separate.

## Backup, restore and adapter SDK

`create_private_backup` uses explicit project/index/config scope and consistent
SQLite snapshots. Backups can contain secrets and are not encrypted: retain them
on protected private storage. `prepare_private_restore` checks archive membership,
paths and hashes; explicit apply checks SQLite integrity and restores into a fresh
staging folder. It never overwrites active indexes or configurations. Migrate
reviewed staged records/settings separately; never publish any runtime artifacts.

`validate_adapter_contract` checks schema 1 contracts with id/version/license/
source, placement, typed input/output declarations, resource limits, fixed argv,
named result parser and unverified/synthetic_pass/real_pass/failed state. Contract
validation does not load code or authorize execution. Executable adapters require
reviewed fixed source, actual receipts and both acceptance/refusal tests.

## Fulltext and scoped Zotero sync

`academic_workspace.index_selected_fulltext` reads up to 25 explicitly selected
bounded PDFs and/or a saved scoped Zotero annotation snapshot. It preserves PDF
page locators, annotation labels/positions and source hashes in a private index.
Low-text pages need OCR/manual review. `search_selected_fulltext` returns literal
phrase matches with nearby text and QC; it does not establish claim support.
Annotation page labels can differ from physical PDF pages.

`scientific_backend.prepare_pdf_ocr` prepares a server OCRmyPDF task returning
searchable PDF, page text and low-text/replacement-character/page-count QC. Existing
OCRmyPDF/Tesseract/pypdf are required. No local heavy install or public PDF upload.
OCR completion is not accuracy validation. Index returned searchable PDFs only
within an explicitly selected scope after QC.

`prepare_zotero_incremental_sync` previews a scoped saved Zotero snapshot against
the separate private research index. Source-version regression blocks apply;
personal tags/notes/reading states/history persist. Missing entries are never
deleted. Hash-bound explicit apply changes the index only, not source Zotero.
This is one-way incremental ingestion, not automatic cloud/bidirectional sync.
Source-library writes retain their separate reviewed/native authorization gates.

## Resumable review and native manuscript collaboration

`create_review_search` records exact approved public Europe PMC queries.
`retrieve_review_search_page` saves one cursor page per explicit dispatch, hit
coverage and response hashes; failure preserves revision/cursor. Resume and bounded
deduplication do not establish exhaustive review coverage or study eligibility.
`record_independent_screening` records actual distinct reviewer decisions with
independence attestation. A second reviewer is never fabricated. Conflict resolution
requires two differing recorded decisions and retains original judgments.
`inspect_review_search` lists pending second reviews and unresolved conflicts.

Windows Word COM adapter reads explicit DOCX native UTF-16 offsets, rendered pages,
fields, revisions and comments. Reviewed hash-bound range edits/comments run on a
fresh copy with tracked revisions. `render_native_word_pdf` is a separate read-only
export, so rendering failure cannot hide an already saved manuscript revision.
Citation fields, existing
revisions and paragraph/cell markers are protected. Mac/Linux/HarmonyOS retain
portable document tools; native Windows COM is not supported there. No Office
installation occurs. Document macros/ActiveX/embedded objects and external
non-hyperlink relationships are refused. Mixed formatting requires visual review.

Generic Word field update excludes Zotero citations. Explicitly authorized
`request_native_citation_refresh` calls only the already-installed trusted Zotero
template macro on a fresh copy, leaving Word open for user review. Invocation
may be asynchronous or display dialogs and is recorded as pending, never complete.
Review/save the copy in Word and inspect it again before final publication.
Unknown native writes are never automatically retried; source documents stay intact.
The adapter does not change Word's personal author preferences. Private document
metadata and comment authors must be reviewed before any sharing/publication.

## Validation

Offline tests cover revision conflicts, QC gates, false/wrong-task completion,
unknown submission refusal, source-impact/overlap checks, escaped dashboards,
scoped backups/restores, incremental sync, located text, cursor recovery, real
reviewer conflicts and unsafe native documents. Dedicated isolated CI executes
actual R methods on synthetic datasets and invalid QC inputs. Native Word has an
explicit optional synthetic runtime check. Real cluster environments, study
inference, OCR accuracy, citation refresh and final rendering need separate receipts.
