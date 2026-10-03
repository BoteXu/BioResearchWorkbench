# Biomedical evidence helpers (2.4)

Call these ten helpers through `biomni_run_tool` with `category="biomedical"`. They use the core environment. Large analysis remains on the server. Retrieve source data with the existing database/literature tools; Codex reads and curates the relevant fields before an audit. No separate model or large matrix download is included.

A successful tool receipt means the function ran, even when the audit reports exclusions or errors. Inspect the actual check fields and reasons. File integrity is distinct from scientific validity.

## Input contracts and outputs

All curated records use `source_reference` (DOI, PMID, source URL or an explicit local reference). Optional `receipt_file` checks an existing source-result SHA256; it does not verify the interpretation of that source. Keep private paths and runtime reports private.

Complete executable synthetic inputs: [biomedical_inputs.json](examples/biomedical_inputs.json). Values and marker names are fixtures, not scientific recommendations.

### 1. audit_drug_target_records

Arguments: `records`, `target_id`, `species`. Rows supply activity/molecule/assay/target IDs, target type, species, assay type, confidence score, activity type/value/units/relation, source and conditions when available. Returns originals, normalized values, comparison context and issues. No pooling across assays.

Supported concentration units: M, mM, uM/µM/μM, nM, pM. Mass concentrations are not converted without molecular-weight and chemical-form review. Exact values may produce `negative_log_molar`; censored relations remain inequalities. This calculated field is not a claim that ChEMBL published pChEMBL. A binding candidate requires B assay, single-protein target and confidence 9; source-method review is still required.

### 2. assess_cohort_eligibility

Arguments: `studies`, `criteria`. Criteria require species, tissue, model, assay and contrast; optional platform/matrix type/dose/time are exact-match criteria. Study rows supply study ID, group_unit_counts, biological_unit, sample_metadata_reference, matrix_type and source. Paired/batch/dose/time omissions become warnings; shared cohort_id flags reuse.

Returns exclusion, needs_review or eligible_under_supplied_criteria with reasons. Minimum two biological units per group is an engineering floor, not proof of power. Cell/spot/frame/spectrum/technical-replicate counts do not establish biological independence. Missing metadata is distinct from a documented exclusion.

### 3. audit_genetic_alignment

Arguments: `rows`, `reference_assembly`; optional `max_frequency_difference` defaults to 0.15, a configurable review policy. Each row has variant_id, left and right objects. Each side supplies species, chromosome, positive integer position, assembly, ancestry, effect/other alleles, effect_type (beta or OR), effect, effect_allele_frequency and source. Optional confidence_interval has two values. requires_same_tissue=true also checks tissue.

Returns originals, actions, aligned right values and refusal reasons. Allele swaps negate beta or reciprocate OR, invert intervals and complement frequency. Palindromes, non-SNPs, missing frequencies and incompatible coordinates/builds require review. No liftover, reference-sequence normalization, LD clumping, MR or colocalization is performed.

### 4. build_evidence_matrix

Arguments: `records`, `question`. Records require candidate and evidence_type: human_genetics, expression, perturbation, binding, clinical, structure or other. Include species/model/tissue/assay/biological_unit/contrast and source.

Returns separate evidence classes, context gaps and provenance without a total score. Absent classes mean not supplied, not biological absence. Different databases can repeat the same study; they are not independent replications.

### 5. compare_evidence

Argument: `records`, at most 100. Supply question, endpoint, species/model/tissue/assay/biological_unit/contrast, dose, time, effect_unit, outcome and source. Positive/negative mean curated positive/negative **effect direction under the stated contrast**. Null means no detected effect as reported; inconclusive means unresolved. Negative must not mean unspecified lack of support or a failed experiment.

Returns direction agreement/conflict, null/detection difference, inconclusive or not_comparable, with reasons. Context differences and shared sources block an independent directional comparison. Agreement alone does not establish replication or causality.

### 6. audit_structure_context

Arguments: `records`, `protein_id`, `species`; optional `required_regions`. Chain rows supply structure/chain/protein IDs, species, method, mapping_reference, reference_length, mapped_intervals, missing_residues, mutations, isoform and ligands. Intervals are inclusive one-based **canonical residue coordinates**, not unconverted PDB author numbering.

Returns unique mapped-residue coverage and required-region gaps; overlaps are not double counted. Empty mutation/ligand/missing-residue lists assert checked annotation; omitted fields mean unknown. Noncanonical isoforms and mutations require review. Chain mappings are caller supplied. Coverage is not structural quality or binding validation.

### 7. map_disease_terms

Argument: `terms`, at most 20. Optional local mappings have term, target_id, relation (exact/broad/narrow/related/unknown), ontology_version and source. This route makes no public queries. Exact remains a caller assertion requiring review; automatic merges are disabled.

Without mappings, retrieve at most ten OLS candidates per term, using ontology mondo/efo/hp. Search similarity does not establish equivalence. sensitive_data=true blocks public lookup; use local mappings or obtain specific authorization before sending sensitive terms.

### 8. audit_cell_annotations

Arguments: `clusters`, `marker_rules`; optional min_donors defaults to 2. Clusters supply cluster ID, label, marker list, donor_count, species/tissue/model, doublet_flag and source. Each label rule supplies positive markers, optional negative markers/min_positive, context and its own source.

Returns supporting/conflicting markers, donor/context gaps and review flags. Defaults and user rules are screening policies, not validated annotation standards. Presence-only markers cannot replace expression distributions, donor-level validation or doublet detection. Proposed labels are not overwritten.

### 9. audit_enrichment_results

Arguments: `results`, `background_genes`, `mapping_summary` (input_count, mapped_count). Results supply term_id, database_version, contrast, method, direction, q_value, driver_genes, background_reference and source. GSEA also supplies NES. Optional nonnegative driver_contributions must be documented server summaries; absence means concentration was not evaluated.

Returns background/mapping-loss checks, duplicates, NES-direction mismatch, reported driver concentration and similar driver sets. Defaults max_driver_fraction=0.5 and max_mapping_loss=0.2 are configurable policies, not biological cutoffs. Driver similarity does not prove ontology redundancy. No enrichment is recomputed. Pairwise overlaps use at most the first 100 terms and report truncation.

### 10. extract_study_elements

Argument: local PDF/TXT/Markdown `path`; optional max_excerpts_per_field=5. Files must be under 10 MB and PDFs at most 300 pages. Other formats can use the existing document helper first.

Returns source hash and located passages for samples, randomization, blinding, dose, time, endpoints, statistical unit and statistics. Each passage has a page/line and character offset. Values remain unfilled until Codex reads the original context. “Not randomized” must never become randomized=yes. No rule match means not located, not unreported. PDF offsets refer to extracted page text.

## Calling example

```json
{"category":"biomedical","name":"map_disease_terms","parameters":{"terms":["synthetic disease"],"sensitive_data":true,"mappings":[{"term":"synthetic disease","target_id":"MONDO:0000001","relation":"related","ontology_version":"synthetic_version","source_reference":"synthetic fixture"}]}}
```

Ten new research.select_tools intents mirror the helpers: drug_target_audit, cohort_eligibility, genetic_alignment, evidence_matrix, evidence_conflicts, structure_audit, disease_terms, cell_annotation_audit, enrichment_audit and study_elements. Together with previous intents, 22 plans reuse the actual catalog. Plans conservatively mark ontology search as public; supplied local mappings do not query a public endpoint.

## Verification and primary contracts

run_acceptance.py includes positive and refusal cases for all ten functions. --network also checks six public identities and OLS candidates. MCP discovery verifies ten entries and a local mapping call. These checks do not validate general reasoning, clinical decisions or user-curated assertions.

- [ChEMBL assay/activity definitions](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions)
- [GWAS Catalog harmonization](https://www.ebi.ac.uk/gwas/docs/methods/summary-statistics/)
- [Mondo mapping semantics](https://mondo.monarchinitiative.org/)
- [RCSB Data API](https://data.rcsb.org/)
- [OLS service](https://www.ebi.ac.uk/ols4/help)
