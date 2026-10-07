# 自动生成功能目录

此目录由公开源码生成，不读取运行回执或私人配置。

| 扩展函数 | 类别 | 任务路由 | 包版本 |
|---|---|---|---|
| 237 | 36 | 142 | 2.13.0 |

参数 schema、默认值、枚举和调用模板见 [TOOL_CATALOG.json](TOOL_CATALOG.json)。模板中的占位符需要实际填写，模板不是可执行验收。

## academic_workspace

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `index_selected_fulltext` | Index explicitly selected PDFs and a saved scoped Zotero annotation snapshot with page locators and extraction QC; never upload content or perform implicit OCR. | pdf_files |
| `search_selected_fulltext` | Search a selected private index by literal text and return page/annotation positions, hashes and nearby text. | index_id, query |
| `prepare_zotero_incremental_sync` | Preview incremental metadata ingestion from an explicitly scoped saved Zotero snapshot; preserve notes/tags/history and never delete missing entries. | library_id, snapshot_path, source_namespace, scope |
| `apply_zotero_incremental_sync` | Apply a reviewed conflict-free incremental index plan; never write the source Zotero library. | plan_file, expected_sha256 |
| `create_review_search` | Create a private resumable Europe PMC search ledger for exact approved public queries; no retrieval yet. | public_queries |
| `retrieve_review_search_page` | Retrieve one approved cursor page and atomically persist coverage and source records; failed pages do not advance the cursor. | search_id, query_index, expected_revision |
| `record_independent_screening` | Record one actual reviewer decision with identity and independence attestation; never invent a second reviewer. | search_id, expected_revision, record_id, reviewer_id, decision, reason |
| `resolve_screening_conflict` | Save an explicit adjudication after at least two different reviewers have disagreed; preserve original decisions. | search_id, expected_revision, record_id, resolver_id, decision, rationale |
| `inspect_review_search` | Inspect saved retrieval coverage, outstanding second reviews and conflicts; no public request. | search_id |

## advanced

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `run_designed_expression` | Design-aware limma/voom/edgeR expression analysis with continuous covariates, explicit reference levels, interactions and one numeric contrast. | matrix_path, metadata_path, matrix_kind, unit_key, predictors, contrast_weights, context |
| `import_expression_data` | Convert bounded H5AD raw-count layers or 10x MTX directories to gene-by-cell CSV; preserve IDs and reject guessed count provenance. | input_path, input_format, context |
| `analyze_cell_composition` | Aggregate cell composition at the independent-unit level with explicit denominators; descriptive proportions, not cell-level inference. | metadata_path, unit_key, condition_key, cell_type_key, context |
| `score_regulatory_activity` | Score signed weighted target expression after within-sample gene standardization; retain coverage, no significance or causal activity claim. | expression_path, metadata_path, network_path, context |
| `summarize_pathway_overlap` | Describe selected pathway redundancy and explicit leading-edge genes; no automatic deletion or re-ranking of enrichment tests. | gene_sets_path, selected_terms |
| `audit_network_stability` | Measure PPI threshold/community sensitivity and optional degree-preserving modularity nulls with fixed nodes; synthetic nulls are not biological replication. | edges_path, context, thresholds |
| `audit_redocking_coordinates` | Compute heavy-atom RMSD against an explicit reference using reviewed atom correspondences in the same receptor frame; no silent alignment or symmetry guessing. | reference_path, predicted_path, atom_mapping, same_coordinate_frame |
| `audit_md_summary` | Audit returned MD summary time series and block stability; frames and blocks are not declared independent simulation replicates. | path, time_key, metric_ranges, window, block_width, time_unit |
| `audit_batch_embedding` | Inspect bounded embedding batch/biology silhouettes and batch-label confounding; descriptive integration diagnostics only. | embedding_path, metadata_path, batch_key, biology_key |
| `run_donor_differential_state` | Execute donor-level pseudobulk and differential expression for explicitly curated cell types; retain failed/low-coverage types and a combined test family. | counts_path, metadata_path, unit_key, condition_key, cell_type_key, cell_types, case, control, context |
| `infer_diffusion_pseudotime` | Run exploratory Scanpy diffusion pseudotime on an existing QC-reviewed neighbor graph with explicit root-cell sensitivity. | h5ad_path, root_cells, unit_key, context |
| `audit_cell_communication` | Review returned ligand/receptor communication scores for donor coverage and provenance; expression scores do not establish signaling. | records, conditions |
| `evaluate_binary_prediction` | Evaluate independent validation predictions with discrimination, Brier score, fixed-threshold counts and calibration bins after an explicit split audit. | records, outcome_key, probability_key, unit_key, threshold, split_review |
| `audit_colocalization_results` | Audit returned colocalization evidence for assembly, locus coverage, priors, tissue, signal model and posterior consistency; no gene causality inferred. | records |

## atlas

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `query_gtex` | Query a bounded GTEx expression/eQTL/sQTL page; retain release, tissue and pagination. | endpoint, parameters |
| `query_hpa` | Retrieve public Human Protein Atlas gene JSON without downloading image or bulk archives. | ensembl_gene_id |
| `search_cellxgene_collections` | Search public CELLxGENE collection metadata locally; does not download count matrices. | search |
| `query_ena_runs` | Retrieve ENA run metadata, file URLs, sizes and MD5 for server-side acquisition. | accession |

## biomedical

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `audit_drug_target_records` | Normalize small activity tables, retaining assay class, censored values, target confidence and duplicates. | records, target_id, species |
| `assess_cohort_eligibility` | Apply explicit study criteria, separating exclusions from missing metadata and cohort overlap. | studies, criteria |
| `audit_genetic_alignment` | Align paired small genetic summaries by explicit alleles; reject palindromes, build/ancestry/tissue gaps and unknown directions. | rows, reference_assembly |
| `build_evidence_matrix` | Group source-linked evidence by candidate and evidence class, retaining context and missing evidence without a total score. | records, question |
| `compare_evidence` | Compare source assertions only after matching question, endpoint, context, dose, time and units; retain nulls separately. | records |
| `audit_structure_context` | Check chain-specific canonical residue mappings, missing residues, isoforms and mutations for a stated protein. | records, protein_id, species |
| `map_disease_terms` | Review explicit ontology relations locally, or retrieve bounded public OLS candidates without asserting equivalence. | terms |
| `audit_cell_annotations` | Review returned marker summaries and donor counts without loading a cell matrix or replacing annotation. | clusters, marker_rules |
| `audit_enrichment_results` | Audit server enrichment summaries for background, ID loss, set versions, repeated terms and driver concentration. | results, background_genes, mapping_summary |
| `extract_study_elements` | Extract located candidate passages for study design; leave values unfilled for Codex source review. | path |

## cadd

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `guide_cadd_workflow` | Choose a CADD audit route without installing, executing, or uploading anything. | task, context |
| `audit_simulation_protocol` | Audit declared MD/tREMD/REST2 units, stages and capabilities; no force-field validation. | protocol, context |
| `audit_restart_manifest` | Check per-walker segment continuity and exact system/protocol/checkpoint lineage. | segments, context |
| `audit_replica_exchange` | Audit adjacent exchange counters and full walker permutations; no convergence claim. | ladder, exchanges, visits, context |
| `audit_docking_campaign` | Retain failed/missing candidates and rank only one exact declared scoring domain. | expected, results, score_domain, context |
| `audit_restraint_mapping` | Check explicit source-to-structure residue keys and evidence, without generating AIRs. | mapping, restraints, context |
| `audit_af3_records` | Audit explicit AF3 sample bindings and declared chain-order summary matrices. | records, selected_pair, context |
| `audit_mmgbsa_summary` | Summarize independent run estimates within an exact endpoint-energy protocol. | runs, context |

## clinical_research

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `audit_medical_guidelines` | Locate recommendations in selected documents and audit versions, region/population applicability and supersession declarations. | sources, recommendations, target_population, review_date |
| `query_drug_reference` | Retrieve an explicitly approved public drug name from fixed RxNorm/DailyMed endpoints; never send patient context. | public_query |
| `read_drug_label` | Retrieve one approved public DailyMed label and its history with XML safety checks and located sections. | set_id |
| `compare_drug_labels` | Compare located extracted label sections and retain version hashes; do not infer safety from changed text. | before_path, after_path |
| `audit_clinical_dataset` | Audit clinical IDs, repeated visits, units, measurement limits, event timing and censoring without excluding records. | table_path, specification |
| `audit_clinical_mapping` | Audit explicitly supplied terminology/table mappings, ambiguity and unresolved concepts; do not claim complete ETL compatibility. | mapping, vocabulary_version |
| `guide_clinical_study` | Produce design-specific clinical research checks after the statistical estimand/unit consultation; fit nothing. | design |
| `audit_clinical_prediction` | Evaluate held-out binary probabilities: Brier, tie-aware AUC, calibration bins, threshold net benefit and subgroup coverage. | predictions_path, specification |
| `audit_medical_reporting` | Audit versioned medical reporting items using actual located source excerpts and reviewer judgments; no bundled proprietary checklist. | document_path, checklist, assessments |
| `extract_review_effects` | Validate actual independently extracted study effects against located source text and detect repeated study/cohort/outcome rows. | sources, extractions |
| `record_bias_assessment` | Record versioned outcome-specific bias/evidence-certainty judgments with source locators and actual reviewers. | tool, assessments |
| `audit_adverse_event_reports` | Deduplicate declared case/version reports and calculate descriptive drug-event reporting odds with explicit continuity correction. | table_path, specification |
| `audit_imaging_metadata` | Audit supplied private imaging metadata for patient/series allocation, acquisition differences and label-review provenance; no image inference. | records, specification |
| `prepare_medical_teaching` | Create a private source-located teaching document from explicitly reviewed claims and approved synthetic/deidentified case material. | title, sources, claims |
| `prepare_clinical_backend` | Prepare fixed existing-R clinical models with mandatory unit/design/QC gates; no local fitting or server submission. | backend, configuration, remote_workdir, expected_host, output_directory, context, inputs |

## code_execution

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `prepare_code_execution` | Prepare checksum-bound code/Notebook/profile/DICOM tasks for explicit server dispatch; no local source execution. | mode, configuration, remote_workdir, expected_host, output_directory, context, inputs |
| `inspect_code_execution` | Inspect a returned code-adapter receipt snapshot and its declared source/configuration identity. | execution_path, expected_configuration_sha256 |
| `summarize_performance` | Summarize the fixed adapter JSON profile; refuse arbitrary pickle-based profiler files. | profile_path |
| `estimate_compute_resources` | Estimate resources from actual declared pilots with explicit scaling assumptions and observed range; never claim an exact runtime. | pilots, target_units |
| `audit_parallel_execution` | Check nested thread allocation, deterministic seed assignment and shared output conflicts before parallel dispatch. | configuration, tasks |
| `audit_resume_compatibility` | Compare input/code/parameter/environment identities and observed scheduler state before any reviewed recovery. | previous, current, scheduler_observation, checkpoints |
| `prepare_code_workflow` | Generate executable Snakemake/Nextflow orchestration with explicit dependencies, resources and pre-analysis QC receipts; no dispatch. | stages |
| `preview_code_workflow` | Perform a no-execution workflow dependency/resource preview and identify missing external inputs. | workflow_path, available_inputs |
| `prepare_code_task_array` | Prepare a fixed Slurm array of reviewed checksum-bound task files with per-task receipts and concurrency limits; never submit. | tasks, maximum_concurrent, resources |
| `prepare_adapter_development` | Generate a typed fixed-adapter development scaffold, contract tests and private escaped documentation; no registration or exposure. | contract |

## code_review

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `map_code_project` | Map only selected Python ASTs and located non-Python declarations without importing source. | root_path, files |
| `audit_scientific_code` | Locate risky source constructs and scientific pitfalls; no imports, execution or semantic guarantees. | root_path, files |
| `audit_notebook` | Locate execution disorder, stale/error outputs, magic commands and Python name-use candidates without running cells. | notebook_path |
| `audit_data_contract` | Check explicit columns, types, units metadata, missingness, keys, categories and ranges before analysis. | table_path, contract |
| `audit_table_join` | Compute join cardinality, null keys, unmatched counts and row expansion before joining; do not emit private identifiers. | left_path, right_path, keys |
| `compare_data_exchange` | Compare serialized cross-language values by explicit unique keys, types and declared numeric tolerance. | before_path, after_path, keys, columns |
| `audit_numeric_results` | Check finite values, explicit bounds, uncertainty ordering and declared probability sums without fitting models. | table_path, rules |
| `compare_scientific_results` | Compare prespecified result metrics by keys with absolute/relative tolerances and contrast metadata. | before_path, after_path, keys, metrics |
| `bind_analysis_qc` | Bind an actual passing QC result and reviewed assessment to exact input/design/reference versions. | inputs, design, references, qc_receipt_path, assessment |
| `check_analysis_qc` | Invalidate acceptance when an input, scientific design or reference changes; no automatic recalculation. | binding_file, expected_sha256, inputs, design, references |
| `prepare_code_revision` | Produce a source-hash-bound patch for explicit full-file replacements and validation commands; no execution or overwrite. | root_path, replacements, rationale, validation_commands |
| `materialize_code_revision` | Save reviewed source replacements in a fresh staging directory, with original hashes and patch; never overwrite the active project. | plan_file, expected_sha256, destination_directory |
| `prepare_method_reproduction` | Validate located method-to-code mappings and produce a gap ledger; do not invent unspecified paper parameters. | method, mappings, baseline |
| `audit_plan_implementation` | Compare declared endpoints, estimand, units, contrasts, filtering and missingness with located actual implementation observations. | plan, observations |
| `prepare_api_migration` | Create a version-specific migration ledger from supplied official documentation and located source uses. | installed_versions, changes |
| `inspect_dependency_locks` | Read scoped uv, renv, requirements and environment records without sourcing profiles, restoring or installing packages. | root_path, files |
| `compare_environments` | Compare supplied actual environment snapshots and expose missing runtime/platform/library dimensions. | before, after |
| `prepare_scientific_test_suite` | Generate executable unittest cases for reviewed fixed Python module/functions and explicit expected values or refusal cases. | cases, source_manifest |
| `prepare_configuration_migration` | Preview explicit JSON key renames/additions with source hash, validation and reversible original snapshot. | configuration_path, operations, target_schema |
| `apply_configuration_migration` | Write a reviewed migration to a fresh destination only; preserve original and refuse changed source/plan. | plan_file, expected_sha256, destination |
| `audit_dependency_components` | Audit supplied package provenance, licenses, pins and vulnerability-review dates; no online lookup or install. | components |
| `audit_release_scope` | Scan explicit text sources/notebook outputs for sensitive patterns without echoing matching private values. | root_path, files |

## collaboration

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `plan_manuscript` | Prepare a section/figure/evidence plan from explicit completed/planned results and statistical consultation; invent no results. | study, results |
| `build_evidence_draft` | Assemble supplied authored paragraphs into Markdown/LaTeX plus a citation map; require evidence IDs or explicit unresolved marking. | title, sections, references_path, evidence_ids |
| `compare_manuscript_versions` | Compare located current text and complete Word citation instructions between two explicit files; do not merge or decide scientific correctness. | before_path, after_path |
| `prepare_manuscript_revision` | Produce a fresh Markdown/LaTeX/text revision or conservative Word tracked revision; protect all citation instructions and refuse complex/protected paragraphs. | manuscript_path, edits, expected_source_sha256 |
| `manage_collaboration_review` | Prepare a located comment/action ledger with dependencies and source hashes; never send messages or change author attribution. | manuscript_path, comments |
| `prepare_reviewer_response` | Generate an editable point-by-point response with exact revised locations and explicit completed/planned/declined states. | manuscript_path, responses |

## integrations

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_mcp_components` | Describe pinned optional processes and distinguish configuration from runtime acceptance. |  |
| `prepare_slurm_monitor` | Prepare actual read-only squeue/sacct and bounded-log probes; no SSH or scheduler submission occurs here. | job_ids, submission_host |
| `inspect_slurm_monitor` | Audit a returned live observation receipt, including request binding, age, unknown states and resource fields. | request_path, receipt_path |

## library

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `import_reference_library` | Normalize an explicit exported library and retain source fields; do not merge or access a native database. | path |
| `audit_reference_duplicates` | Flag equal DOI, equal title/year and missing metadata; never delete or automatically merge records. | path |
| `export_reference_library` | Export normalized records to CSL-JSON, RIS or BibTeX with explicit field-loss warnings and source provenance. | path, output_format |
| `index_pdf_folder` | Hash and extract DOI candidates from one explicit nonrecursive local PDF folder; no upload or automatic DOI assignment. | folder |

## literature

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `query_pubmed` | Search PubMed, preserving the submitted query. max_retries is compatibility-only. | query |
| `query_europepmc` | Search Europe PMC core metadata; return cursor and the exact query. | query |
| `doi_metadata` | Retrieve Crossref DOI metadata, including corrections/updates where deposited. | doi |
| `fetch_open_access_article` | Retrieve Europe PMC OA JATS XML and optionally the supplementary ZIP. | pmcid |
| `fetch_supplementary_info_from_doi` | Resolve DOI through Europe PMC, then retrieve available OA supplements. | doi |
| `extract_local_document` | Extract text from local PDF, DOCX, XML/JATS or UTF-8 text without uploading it. | path |
| `discover_publisher_supplements` | Discover public publisher links; report blocked pages and never infer absent files. | doi |
| `download_publisher_supplement` | Download a URL explicitly listed in an intact prior discovery receipt. | discovery_receipt, url |

## molecular

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `molecular_descriptors` | RDKit descriptors for at most 100 explicit SMILES; no property is an experimental ADMET measurement. | smiles |
| `prepare_ligand_meeko` | Prepare one reviewed explicit-hydrogen 3D SDF with Meeko; retain provenance, refuse guessed protonation or multiple molecules. | sdf_path, context |
| `audit_docking_inputs` | Validate prepared PDBQT and explicit bounded search geometry; preparation chemistry remains unverified. | receptor_path, ligand_path, center, box_size, context |
| `summarize_vina_poses` | Read all Vina result remarks, retaining affinities and reference-pose RMSD bounds. | poses_path |
| `run_vina_docking` | Run one prepared ligand against a rigid receptor using installed Vina; preserve failed and partial files. | receptor_path, ligand_path, center, box_size, context |

## molecular_biology

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `guide_molecular_drylab` | Plan a molecular dry-lab task with assay-specific QC and actual tool states; start no analysis. | task, context |
| `inspect_molecular_resources` | Inspect pinned external skill/MCP candidates, reused clients and implemented molecular resources. |  |
| `plan_molecular_extension` | Prepare a scoped external-resource review plan; disclose no identifiers and execute no installation or query. | resource_id, public_identifiers |
| `query_intact_interactions` | Retrieve one bounded IntAct page for an approved public protein; preserve experimental context and partial coverage. | uniprot_id, taxon_id |
| `query_complex_record` | Retrieve one approved public Complex Portal accession; check identity and preserve stoichiometry/source context. | complex_id |
| `query_cell_line` | Read bounded Cellosaurus identity/species/caution metadata for one approved public cell line; no donor or private table upload. | accession |
| `audit_splicing_results` | Audit returned event/isoform results, separating abundance, junction/structure evidence, design and protein extrapolation. | records, context |
| `audit_regulatory_links` | Audit returned chromatin/RNA-binding/translation links; motif, proximity and occupancy retain their evidence boundaries. | records, context |
| `audit_protein_annotations` | Check returned domain/GO/PTM annotations for isoform and residue binding, NOT qualifiers and experimental boundaries. | records, context |
| `audit_interaction_records` | Audit physical/functional/complex/predicted interaction summaries without converting them into binding or regulation. | records, context |
| `audit_perturbation_results` | Review returned molecular-screen/perturbation effects for independent units, specificity, controls and uncertainty; design no reagents. | records, context |
| `audit_mechanism_graph` | Audit a declared molecular mechanism graph against located, typed evidence, context and conflicting signs; prove no causal mechanism. | nodes, edges, evidence_records, context |
| `prepare_molecular_pipeline` | Prepare fixed commit-pinned nf-core ATAC/ChIP/methylation tasks after exact input/design/reference QC checks; submit nothing. | pipeline, parameters, qc_binding_file, qc_binding_sha256, qc_inputs, design, references, remote_workdir, expected_host, expected_outputs, context, inputs |

## omics

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `audit_expression_matrix` | Audit numeric CSV/TSV, identifiers and sample metadata without inferring its scale. | path, matrix_kind |
| `audit_h5ad` | Inspect H5AD identifiers, metadata and matrix blocks without treating cells as replicates. | path, matrix_kind |
| `local_gene_set_enrichment` | Hypergeometric ORA with explicit tested-gene universe and BH across all eligible sets. | genes, background, gene_sets_path |
| `preranked_gsea` | Seeded GSEA using a two-column gene/ranking-statistic CSV/TSV and local GMT/JSON. | ranks_path, gene_sets_path |
| `map_orthologs` | Map explicit Ensembl IDs via homology, retaining absent and nonmatching mappings. | gene_ids, source_species, target_species |
| `annotate_cells_by_markers` | Score explicit marker sets locally and retain ambiguous cells as Unknown. | path, markers_path, matrix_kind |
| `transfer_cell_labels` | Reference-fitted PCA/kNN transfer on shared genes with an explicit Unknown class. | reference_path, query_path, label_key, matrix_kind |

## personal_library

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `create_personal_library` | Create a fresh private SQLite research index with an opaque ID; do not read/import Zotero or configure cloud synchronization. | title, purpose |
| `inspect_personal_library` | Read explicit/default private index metadata and reading-state counts without returning paper content or notes. |  |
| `prepare_personal_library_ingest` | Preview a bounded reference snapshot with source-scoped IDs, updates and duplicate-DOI candidates; apply nothing. | library_id, references_path, source_namespace |
| `apply_personal_library_ingest` | Atomically apply an unchanged reviewed private ingest plan with revision/conflict checks and history; never modify Zotero. | plan_file, expected_sha256 |
| `search_personal_library` | Search one explicit private index by literal phrase/tags/reading state with bounded pagination; no online semantic service. | library_id |
| `annotate_personal_reference` | Update explicit private reading state/tags/note with conflict checks and retained before history; no Zotero/cloud write. | library_id, record_id, expected_fingerprint, expected_revision, reading_state, tags, note |
| `export_personal_library` | Export an explicit bounded private selection to RIS/BibTeX/CSL-JSON, retaining partial coverage; no public upload. | library_id, output_format |

## privacy

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_privacy_policy` | Report privacy mode and exposure boundaries without disclosing private identifiers or file paths. |  |
| `audit_outbound_parameters` | Flag private paths, literal addresses, emails, credential formats and privately configured identifiers without echoing their values. | parameters |

## qc

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `preflight_transcriptomics` | Run input, resource, replicate/design and sample QC before any formal differential-expression fit. | matrix_path, metadata_path, matrix_kind, condition_key, unit_key, case, control, context |
| `compare_analysis_results` | Pairwise effect/rank/sign agreement for explicitly comparable complete result tables; no meta-analysis. | result_paths, context |

## reporting

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `audit_analysis_result` | Check a returned analysis summary, output hashes, context, QC gate and expected contrast; do not infer biological truth. | summary_path, expected_contrast |

## research

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `select_tools` | Return an explicit task plan with live catalog/dependency/receipt states; execute nothing. | intent |
| `resolve_identifier` | Resolve one public identifier against an official API; retain ambiguity, versions and raw source data. | namespace, identifier |
| `audit_identifier_mapping` | Audit caller-supplied mappings locally for malformed IDs, context gaps and conflicting joins; query nothing. | rows, species |

## review

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_manuscript` | Extract bounded located text and Word field/comment inventory privately; no OCR, upload or scientific assessment. | path |
| `audit_claim_evidence` | Verify claim locations, reference IDs and exact located source excerpts; support judgments must be explicitly supplied by a reviewer. | manuscript_path, claims, references_path |
| `audit_paper` | Combine statistical design consultation, explicit numeric consistency and located candidate reporting issues; never certify scientific quality. | manuscript_path, study |
| `audit_review` | Audit supplied review reporting, search logs, screening accounting and cohort overlap with original operational checks, not an official checklist certification. | manuscript_path, review_type, checklist, search_log, screening_records, evidence_records |
| `audit_manuscript_format` | Check located citations, headings, figure/table mentions and explicit versioned journal rules; no automatic formatting or live guideline assumption. | manuscript_path, references_path |
| `audit_terminology_units` | Check explicit abbreviation definitions, first-use order and declared quantity/unit mentions; do not invent expansions or convert units. | manuscript_path, glossary, quantity_rules |
| `find_similar_studies` | Search explicitly approved public queries in Europe PMC and rerank returned metadata with transparent lexical/facet overlap; never transmit a draft. | public_queries, comparison |
| `check_publication_updates` | Query Crossref deposited update/retraction relationships for explicit public DOIs; absence of records is not proof of publication integrity. | dois |
| `audit_reporting_checklist` | Apply a supplied versioned PRISMA/CONSORT/STROBE/ARRIVE or journal checklist with located reviewer assessments, preserving unassessed items. | manuscript_path, checklist_profile, assessments |
| `audit_reference_metadata` | Compare at most 25 explicitly selected DOI records to Crossref metadata; send DOIs only, never a private library or authors list. | references_path |

## scientific_backend

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_scientific_backends` | List fixed server adapters and their runtime boundaries without installing packages or probing a server. |  |
| `prepare_scientific_backend` | Validate a fixed scientific configuration and prepare a checksum-bound server task with mandatory runtime QC; do not submit. | backend, configuration, remote_workdir, expected_host, output_directory, context, inputs |
| `prepare_pdf_ocr` | Prepare a fixed server OCR batch adapter with searchable PDF, page-located extraction and low-text QC; no upload or local OCR installation. | pdf_input, remote_workdir, expected_host, output_directory, context, inputs |

## scientific_interfaces

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_scientific_interfaces` | Check local Zotero handshake and Cytoscape version/layouts; never list library contents or import a network. |  |
| `export_zotero_snapshot` | Export an explicitly authorized item set with original Zotero fields/versions and provenance; never write or cloud-sync. | library, item_keys |
| `export_cytoscape_snapshot` | Read one selected running Cytoscape network with version metadata and source hash; no layout or library mutation. | network_id |
| `prepare_cytoscape_revision` | Preview a single layout operation tied to the exact selected network and running version; do not invoke it. | network_id, layout |
| `apply_cytoscape_revision` | Dispatch one explicitly reviewed local layout plan; block changed networks/versions and repeated unknown outcomes. | plan_path, reviewed_sha256 |

## semantic_index

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `prepare_semantic_index` | Build a reviewed, source-hashed bounded index plan; large embedding workloads belong on the server. | records, collection, index_path |
| `audit_semantic_results` | Verify returned semantic-hit source IDs, versions and text hashes against an explicit source snapshot. | results, source_records |

## server

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `prepare_scheduler_task` | Build a Slurm adapter that really submits/polls/cancels when explicitly dispatched on the verified server; preparation itself connects nowhere. | argv, remote_workdir, expected_compute_host, submission_host, expected_outputs, context, partition |
| `inspect_scheduler_receipt` | Review a returned scheduler snapshot with exact task identity and separate scheduler/analysis completion states. | task_file, scheduler_receipt_path |
| `prepare_standard_pipeline` | Prepare pinned nf-core RNA-seq, tximport, dream, molecular preparation or GROMACS analysis tasks using existing server environments; submit nothing. | pipeline, parameters, remote_workdir, expected_host, expected_outputs, context |
| `inspect_multiqc_report` | Inspect a returned MultiQC JSON summary, retain module values and missing fields; no universal QC pass inferred. | path |

## server_operations

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `plan_server_budget` | Extend observed resource pilots with declared CPU/memory-hour budgets and optional user-supplied prices; not a queue or price lookup. | pilots, target_units, cpus |
| `review_unknown_submission` | Review explicit scheduler/runner observations for an ambiguous submission; automatic resubmission is always disabled. | request_sha256, observations |
| `plan_incremental_return` | Plan changed bounded result files from explicit checksum snapshots, retaining missing/oversized/unstable results; transfer nothing. | previous_manifest, current_manifest |

## software

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `register_local_software` | Persist a private executable path for a known adapter; probe only its fixed version command. | name, executable |
| `software_inventory` | Report registered or discovered adapters without launching analyses, containers or services. |  |
| `check_software_health` | Re-probe configured fixed adapters and compare saved versions without launching analyses or overwriting registration. | names |
| `inspect_cytoscape_health` | Read local running Cytoscape CyREST version and available layouts; record connection failure without claiming GUI validation. |  |
| `cytoscape_render_network` | Apply an explicit local Cytoscape layout/style and export a bounded PNG; never follow redirects, start a GUI or publish the image. | network_id, layout |
| `convert_molecular_structure` | Convert one bounded structure through configured Open Babel with explicit pH/3D flags; chemistry needs review. | input_path, output_format, context |
| `cytoscape_import_network` | Import an explicit local GraphML into a running local Cytoscape through CyREST; do not start the GUI. | graphml_path |

## statistics

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `guide_study_statistics` | Produce a design-aware statistical consultation: estimand, units, candidate methods, assumptions and reporting; fit nothing. | study |
| `audit_statistical_dataset` | Audit a local table for missingness, independent units, duplicate records and group overlap without imputing or excluding. | path, unit_key, outcome_keys |
| `compare_groups` | Estimate a prespecified mean difference with a Welch or paired t interval and test; reject pseudoreplicated or missing inputs. | case_values, control_values, case_units, control_units |
| `adjust_pvalues` | Adjust a declared complete family using BH, BY, Holm or Bonferroni; never invent a missing test family. | pvalues, family |
| `plan_sample_size` | Prospective two-sided t-test sample-size sensitivity scenarios using noncentral t; paired effects use SD of differences. | effect_sizes |
| `meta_analyze_effects` | Pool compatible independent study estimates with fixed or DerSimonian-Laird weights, heterogeneity and leave-one-out sensitivity. | studies, effect_scale, contrast |
| `audit_prediction_split` | Check independent-unit overlap and preprocessing/tuning leakage before interpreting prediction performance. | training_units, validation_units, preprocessing_fit_units |
| `fit_statistical_model` | Fit bounded OLS HC3, binary logistic, Poisson or random-intercept linear models using explicit numeric/categorical predictors and QC. | path, outcome, predictors, context |

## systems

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `score_pathway_activity` | Sample-level ssGSEA for declared log2 normalized expression with local versioned gene sets; descriptive scores only. | expression_path, metadata_path, gene_sets_path, context, matrix_kind |
| `query_string_network` | Retrieve a bounded public STRING network only after explicit authorization; predicted physical edges remain predictions. | identifiers, species_taxid |
| `analyze_ppi_network` | QC an explicit confidence-weighted undirected PPI edge table, then compute bounded centrality and Louvain communities. | edges_path, context, network_type, identifier_namespace |

## table_query

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `query_selected_table` | Read selected columns with bound scalar predicates from one local DuckDB table; deny external I/O and arbitrary SQL. | database_path, table_name, columns |

## transcriptomics

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_local_compute` | Estimate local matrix footprint and route large work to server preparation; execute nothing. | genes, observations |
| `run_bulk_rnaseq` | PyDESeq2 on declared raw integer gene counts with biological-unit and design checks; no network. | counts_path, metadata_path, condition_key, unit_key, case, control, context |
| `aggregate_pseudobulk` | Sum raw cell counts within one cell type and biological unit/condition; retain excluded groups. | counts_path, metadata_path, unit_key, condition_key, cell_type_key, cell_type, context |
| `run_normalized_expression` | Native R limma empirical-Bayes analysis for declared log2 normalized expression; no silent scale conversion. | expression_path, metadata_path, condition_key, unit_key, case, control, context, matrix_kind |
| `run_small_single_cell` | Bounded Scanpy QC, log normalization, HVG, PCA, neighbors, UMAP and Leiden; clustering is exploratory. | counts_path, metadata_path, unit_key, context, mitochondrial_prefix |

## validation

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_scientific_benchmarks` | List small licensed public benchmark contracts; installation and runtime acceptance are not inferred. |  |
| `audit_benchmark_receipt` | Check a selected returned benchmark receipt and report three acceptance layers; never collapse a reference match into general scientific validity. | receipt_path, expected_receipt_sha256, benchmark_id |

## word_native

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_native_word` | Read Word native UTF-16 ranges, comments, fields and page positions for one explicit document; no edits or citation refresh. | manuscript_path |
| `prepare_native_word_revision` | Preview range-based tracked edits and native comments against an explicit source hash; field-intersecting changes are forbidden. | manuscript_path, expected_source_sha256 |
| `apply_native_word_revision` | Execute one reviewed native Word plan on a fresh copy; preserve source and create real comments/tracked edits. PDF rendering is a separate read-only task. | plan_file, expected_sha256 |
| `render_native_word_pdf` | Render one explicit unchanged DOCX through installed Word to a fresh private PDF; report completion only after actual native export. | manuscript_path, expected_source_sha256 |
| `request_native_citation_refresh` | Invoke only the installed trusted ZoteroRefresh macro on a fresh document copy; keep an unknown/pending state until explicit native review, never retry. | manuscript_path, expected_source_sha256 |

## workbench

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `create_research_project` | Create an empty private project with explicit design, scientific context and analysis plan. | title, question, design, context, analysis_plan |
| `inspect_research_project` | Read one explicitly selected private project, including real state and pending gates. | project_id |
| `prepare_project_revision` | Preview a replacement of selected project fields; protect recorded execution states and history. | project_id, expected_revision, changes |
| `apply_project_revision` | Commit an unchanged reviewed private project revision with a transaction and conflict check. | plan_file, expected_sha256 |
| `advance_workflow_stage` | Advance one stage using an immutable saved receipt; fail closed on unknown submissions and unmet QC gates. | project_id, stage_id, expected_revision, event, receipt_path |
| `execute_workflow_stage` | Run one reviewed allowlisted local QC/check stage, persist its real bridge receipt and stop before manual acceptance; server stages require separate explicit dispatch. | project_id, stage_id, expected_revision |
| `audit_project_lineage` | Locate overlapping cohort/subject tokens and downstream claims affected by changed sources; never infer independence from different accession IDs. | project_id |
| `build_project_dashboard` | Render a private static task board with blocked stages, receipt snapshots and unverified software states. | project_id |
| `freeze_reproduction_package` | Freeze explicitly selected bounded result files, parameters, environment and commands in a private reproducibility bundle. | project_id, files, environment, commands |
| `create_private_backup` | Create an explicit scoped private archive using transaction-consistent SQLite backup; never discover or scan whole libraries. |  |
| `prepare_private_restore` | Preview restoring a checked backup to a fresh private staging folder; never overwrite active indexes/configuration. | backup_path, destination |
| `apply_private_restore` | Restore an unchanged reviewed archive into a fresh folder; check SQLite integrity and roll back only newly owned files on error. | plan_file, expected_sha256 |
| `validate_adapter_contract` | Validate a versioned adapter SDK contract without importing or executing third-party code. | contract |

## workflow

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_ssh_route` | Read effective local SSH configuration without connecting or collecting credentials. |  |
| `prepare_remote_task` | Prepare a portable server task bundle, with exact argv, hostname gate and output checksums; no submission. | argv, remote_workdir, expected_host, expected_outputs, context |
| `prepare_server_inventory` | Prepare a read-only server software inventory task; does not connect, submit or install. | remote_workdir, expected_host |
| `inspect_remote_task` | Read a returned remote lifecycle receipt and check task identity; does not poll a server. | task_file, remote_receipt_path |
| `verify_remote_results` | Check a downloaded remote receipt and expected output bytes/SHA256 against the exact task. | task_file, remote_receipt_path, downloaded_root |
| `audit_sample_metadata` | Check sample IDs and independent-unit counts; detect repeated units and incomplete pairing. | path, sample_key, unit_key, condition_key, case, control |
| `audit_result_table` | Validate small server result tables for differential/MR/coloc/meta/image analysis; no local fitting. | path, analysis, columns, context |
| `build_server_download_manifest` | Convert saved ENA runs into a server download manifest; no local FASTQ download. | ena_result_path |

## zotero

| 函数 | 功能 | 必需参数 |
|---|---|---|
| `inspect_zotero_connection` | Check a local Zotero API without scanning a library or requesting write authorization. |  |
| `read_zotero_library` | Read one explicit collection or item set, including optional bounded notes/annotations; never scan an unspecified whole library. | library |
| `read_zotero_attachment` | Resolve a local Zotero attachment to an explicitly permitted folder; refuse network/remote file URLs and symlink escape. | library, attachment_key, allowed_folder |
| `prepare_zotero_write` | Preview additive tags, plain-text notes or new references with private before snapshots; no authorization dialog or write. | library, changes |
| `apply_zotero_write` | Explicitly dispatch an unchanged preview through Zotero's own authorization dialog; block conflicts and never retry an unknown write. | plan_file, expected_sha256 |

