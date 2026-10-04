"""Lightweight task routing and explicit public identifier checks."""
import re
from urllib.parse import quote


def _get_json(url, parameters=None):
    from http_client import get_json
    return get_json(url, parameters)

PATTERNS = {
    'gene_symbol': r'[A-Za-z0-9][A-Za-z0-9_.-]{0,49}',
    'ensembl_gene': r'ENS[A-Z]*G[0-9]+(?:\.[0-9]+)?',
    'uniprot': r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[0-9]+)?',
    'rsid': r'rs[0-9]+', 'pdb': r'[0-9][A-Za-z0-9]{3}',
    'pubchem_cid': r'[1-9][0-9]*', 'chembl': r'CHEMBL[0-9]+',
    'inchikey': r'[A-Z]{14}-[A-Z]{10}-[A-Z]',
}
SPECIES = {'homo_sapiens': 9606, 'mus_musculus': 10090, 'rattus_norvegicus': 10116}
INTENTS = {
    'code_project':[('code_review', 'map_code_project'), ('code_review', 'audit_scientific_code')],
    'code_notebook':[('code_review', 'audit_notebook'), ('code_execution', 'prepare_code_execution')],
    'code_data_contract':[('code_review', 'audit_data_contract'), ('code_review', 'audit_table_join'), ('code_review', 'compare_data_exchange')],
    'code_result_validation':[('code_review', 'audit_numeric_results'), ('code_review', 'compare_scientific_results')],
    'code_qc_binding':[('code_review', 'bind_analysis_qc'), ('code_review', 'check_analysis_qc')],
    'code_revision':[('code_review', 'prepare_code_revision'), ('code_review', 'materialize_code_revision'), ('code_execution', 'prepare_code_execution')],
    'method_reproduction':[('code_review', 'prepare_method_reproduction'), ('code_review', 'audit_plan_implementation')],
    'code_api_migration':[('code_review', 'prepare_api_migration'), ('code_review', 'inspect_dependency_locks'), ('code_review', 'compare_environments')],
    'code_scientific_tests':[('code_review', 'prepare_scientific_test_suite'), ('code_execution', 'prepare_code_execution')],
    'code_configuration_migration':[('code_review', 'prepare_configuration_migration'), ('code_review', 'apply_configuration_migration')],
    'code_release_review':[('code_review', 'audit_dependency_components'), ('code_review', 'audit_release_scope')],
    'code_performance':[('code_execution', 'prepare_code_execution'), ('code_execution', 'summarize_performance'), ('code_execution', 'estimate_compute_resources')],
    'code_parallel':[('code_execution', 'audit_parallel_execution'), ('code_execution', 'prepare_code_task_array')],
    'code_resume':[('code_execution', 'audit_resume_compatibility')],
    'code_workflow':[('code_execution', 'prepare_code_workflow'), ('code_execution', 'preview_code_workflow')],
    'code_adapter':[('code_execution', 'prepare_adapter_development')],
    'medical_guidelines':[('clinical_research', 'audit_medical_guidelines')],
    'medical_drug_reference':[('clinical_research', 'query_drug_reference'), ('clinical_research', 'read_drug_label'), ('clinical_research', 'compare_drug_labels')],
    'clinical_qc':[('clinical_research', 'audit_clinical_dataset'), ('clinical_research', 'audit_clinical_mapping')],
    'clinical_study':[('statistics', 'guide_study_statistics'), ('clinical_research', 'guide_clinical_study'), ('clinical_research', 'prepare_clinical_backend')],
    'clinical_prediction':[('clinical_research', 'audit_clinical_prediction'), ('clinical_research', 'audit_medical_reporting')],
    'clinical_review_effects':[('clinical_research', 'extract_review_effects'), ('clinical_research', 'record_bias_assessment')],
    'pharmacovigilance':[('clinical_research', 'audit_adverse_event_reports')],
    'imaging_qc':[('clinical_research', 'audit_imaging_metadata'), ('code_execution', 'prepare_code_execution')],
    'medical_teaching':[('clinical_research', 'prepare_medical_teaching')],

    'research_project':[('workbench','create_research_project'),('workbench','prepare_project_revision'),('workbench','apply_project_revision'),('workbench','audit_project_lineage')],
    'stage_workflow':[('workbench','inspect_research_project'),('workbench','execute_workflow_stage'),('workbench','advance_workflow_stage'),('workbench','build_project_dashboard')],
    'research_reproduction':[('workbench','freeze_reproduction_package')],
    'private_backup_restore':[('workbench','create_private_backup'),('workbench','prepare_private_restore'),('workbench','apply_private_restore')],
    'adapter_contract':[('workbench','validate_adapter_contract')],
    'fulltext_search':[('academic_workspace','index_selected_fulltext'),('academic_workspace','search_selected_fulltext')],
    'zotero_incremental_sync':[('academic_workspace','prepare_zotero_incremental_sync'),('academic_workspace','apply_zotero_incremental_sync')],
    'review_retrieval':[('academic_workspace','create_review_search'),('academic_workspace','retrieve_review_search_page'),('academic_workspace','inspect_review_search')],
    'independent_screening':[('academic_workspace','record_independent_screening'),('academic_workspace','resolve_screening_conflict')],
    'native_word':[('word_native','inspect_native_word'),('word_native','prepare_native_word_revision'),('word_native','apply_native_word_revision'),('word_native','render_native_word_pdf'),('word_native','request_native_citation_refresh')],
    'scientific_server_backend':[('statistics','guide_study_statistics'),('scientific_backend','inspect_scientific_backends'),('scientific_backend','prepare_scientific_backend')],
    'coloc_susie':[('statistics','guide_study_statistics'),('scientific_backend','prepare_scientific_backend'),('advanced','audit_colocalization_results')],
    'decoupler_activity':[('statistics','guide_study_statistics'),('scientific_backend','prepare_scientific_backend')],
    'multilevel_meta_analysis':[('statistics','guide_study_statistics'),('scientific_backend','prepare_scientific_backend')],
    'server_ocr':[('scientific_backend','prepare_pdf_ocr')],
    'personal_library':[('personal_library','inspect_personal_library'),('personal_library','prepare_personal_library_ingest'),('personal_library','apply_personal_library_ingest'),('personal_library','search_personal_library')],
    'reference_library':[('library','import_reference_library'),('library','audit_reference_duplicates'),('library','export_reference_library'),('review','audit_reference_metadata')],
    'zotero_read':[('zotero','inspect_zotero_connection'),('zotero','read_zotero_library')],
    'zotero_write':[('zotero','prepare_zotero_write'),('zotero','apply_zotero_write')],
    'manuscript_evidence':[('review','inspect_manuscript'),('review','audit_claim_evidence')],
    'paper_review':[('review','audit_paper'),('review','audit_manuscript_format'),('review','audit_terminology_units')],
    'review_audit':[('review','audit_review'),('review','audit_reporting_checklist')],
    'similar_studies':[('review','find_similar_studies'),('review','check_publication_updates')],
    'manuscript_collaboration':[('collaboration','plan_manuscript'),('collaboration','build_evidence_draft'),('collaboration','manage_collaboration_review')],
    'manuscript_revision':[('collaboration','compare_manuscript_versions'),('collaboration','prepare_manuscript_revision')],
    'reviewer_response':[('collaboration','prepare_reviewer_response')],
    'privacy_review':[('privacy','inspect_privacy_policy'),('privacy','audit_outbound_parameters')],
    'statistics_guidance':[('statistics','guide_study_statistics'),('statistics','audit_statistical_dataset')],
    'statistical_comparison':[('statistics','compare_groups'),('statistics','adjust_pvalues')],
    'statistical_model':[('statistics','fit_statistical_model')],
    'sample_size':[('statistics','plan_sample_size')],
    'meta_analysis':[('statistics','meta_analyze_effects')],
    'prediction_validation':[('statistics','audit_prediction_split'),('advanced','evaluate_binary_prediction')],
    'complex_expression':[('advanced','run_designed_expression')],
    'expression_import':[('advanced','import_expression_data')],
    'donor_differential_state':[('advanced','run_donor_differential_state')],
    'cell_composition':[('advanced','analyze_cell_composition')],
    'regulatory_activity':[('advanced','score_regulatory_activity')],
    'pathway_redundancy':[('advanced','summarize_pathway_overlap')],
    'network_render':[('software','cytoscape_import_network'),('software','cytoscape_render_network')],
    'network_stability':[('advanced','audit_network_stability')],
    'trajectory':[('advanced','infer_diffusion_pseudotime')],
    'communication_review':[('advanced','audit_cell_communication')],
    'integration_review':[('advanced','audit_batch_embedding')],
    'redocking_validation':[('advanced','audit_redocking_coordinates')],
    'md_review':[('advanced','audit_md_summary')],
    'colocalization_review':[('advanced','audit_colocalization_results')],
    'server_execution':[('server','prepare_scheduler_task'),('server','inspect_scheduler_receipt')],
    'standard_pipeline':[('server','prepare_standard_pipeline'),('server','inspect_multiqc_report')],
    'analysis_review':[('reporting','audit_analysis_result')],
    'software_health':[('software','check_software_health'),('software','inspect_cytoscape_health')],
    'ligand_preparation':[('molecular','prepare_ligand_meeko')],
    'preanalysis_qc':[('qc','preflight_transcriptomics')],
    'method_comparison':[('qc','compare_analysis_results')],
    'pathway_activity':[('systems','score_pathway_activity')],
    'pathway_enrichment':[('omics','local_gene_set_enrichment'),('omics','preranked_gsea')],
    'ppi':[('systems','query_string_network'),('systems','analyze_ppi_network')],
    'software_interfaces':[('software','software_inventory'),('software','register_local_software')],
    'bulk_rnaseq': [('transcriptomics','inspect_local_compute'),('transcriptomics','run_bulk_rnaseq')],
    'single_cell': [('transcriptomics','inspect_local_compute'),('transcriptomics','run_small_single_cell')],
    'pseudobulk': [('transcriptomics','aggregate_pseudobulk'),('transcriptomics','run_bulk_rnaseq')],
    'normalized_expression': [('transcriptomics','run_normalized_expression')],
    'molecular_properties': [('molecular','molecular_descriptors')],
    'docking': [('molecular','audit_docking_inputs'),('molecular','run_vina_docking')],
    'docking_audit': [('molecular','audit_docking_inputs'),('molecular','summarize_vina_poses')],
    'compute_capacity': [('transcriptomics','inspect_local_compute')],
    'drug_target_audit': [('biomedical','audit_drug_target_records')],
    'cohort_eligibility': [('biomedical','assess_cohort_eligibility')],
    'genetic_alignment': [('biomedical','audit_genetic_alignment')],
    'evidence_matrix': [('biomedical','build_evidence_matrix')],
    'evidence_conflicts': [('biomedical','compare_evidence')],
    'structure_audit': [('biomedical','audit_structure_context')],
    'disease_terms': [('biomedical','map_disease_terms')],
    'cell_annotation_audit': [('biomedical','audit_cell_annotations')],
    'enrichment_audit': [('biomedical','audit_enrichment_results')],
    'study_elements': [('biomedical','extract_study_elements')],
    'literature': [('literature', 'query_pubmed'), ('literature', 'query_europepmc')],
    'identifier': [('research', 'resolve_identifier'), ('research', 'audit_identifier_mapping')],
    'genetics': [('database', 'query_gwas_catalog'), ('database', 'query_clinvar'), ('database', 'query_gnomad')],
    'target': [('database', 'query_opentarget'), ('database', 'query_chembl')],
    'protein': [('database', 'query_uniprot'), ('database', 'query_interpro')],
    'structure': [('database', 'query_pdb_data'), ('database', 'query_alphafold'), ('database', 'query_sifts')],
    'expression_metadata': [('atlas', 'query_gtex'), ('atlas', 'query_hpa'), ('atlas', 'search_cellxgene_collections')],
    'sequencing_metadata': [('atlas', 'query_ena_runs'), ('workflow', 'build_server_download_manifest')],
    'sample_audit': [('workflow', 'audit_sample_metadata')],
    'result_audit': [('workflow', 'audit_result_table'), ('workflow', 'verify_remote_results')],
    'server_task': [('workflow', 'prepare_server_inventory'), ('workflow', 'prepare_remote_task'), ('workflow', 'inspect_remote_task')],
    'small_omics': [('omics', 'audit_expression_matrix'), ('omics', 'audit_h5ad'), ('omics', 'local_gene_set_enrichment')],
}


def select_tools(intent: str, sensitive_data: bool = False, large_computation: bool = False) -> dict:
    """Return an explicit task plan with live catalog/dependency/receipt states; execute nothing."""
    if intent not in INTENTS:
        raise ValueError('Choose an intent: ' + ', '.join(INTENTS))
    if type(sensitive_data) is not bool or type(large_computation) is not bool:
        raise ValueError('Flags must be booleans')
    from bridge import tool_catalog
    from compute_policy import edition
    server_intents={'code_notebook','code_revision','code_scientific_tests','code_performance','code_parallel','code_workflow','clinical_study','imaging_qc','scientific_server_backend','coloc_susie','decoupler_activity','multilevel_meta_analysis','server_ocr'}
    selected = 'server_task' if large_computation and intent not in server_intents else intent
    recommendations = []
    for category, name in INTENTS[selected]:
        entries = tool_catalog(category=category, search=name, limit=100)['tools']
        entry = next((e for e in entries if e['name'] == name), None)
        public = category in {'database', 'atlas', 'literature'} or name in {'resolve_identifier','map_disease_terms','query_string_network','find_similar_studies','check_publication_updates','audit_reference_metadata','retrieve_review_search_page','query_drug_reference','read_drug_label'}
        missing = [p for p, ready in (entry or {}).get('dependency_check', {}).items() if not ready]
        edition_allowed = not (entry or {}).get('requires_local_edition') or edition()=='local'
        recommendations.append({
            'category': category, 'name': name, 'catalog_entry': entry,
            'placement': 'local_preparation_for_server' if selected == 'server_task' or category in {'scientific_backend','code_execution','clinical_research'} and name in {'prepare_scientific_backend','prepare_pdf_ocr','prepare_code_execution','prepare_code_task_array','prepare_clinical_backend'} else 'local',
            'suggested_parameters': {'backend':intent} if name=='prepare_scientific_backend' and intent in {'coloc_susie','decoupler_activity'} else {'backend':'metafor_multilevel'} if name=='prepare_scientific_backend' and intent=='multilevel_meta_analysis' else {},
            'uses_public_endpoint': public,
            'requires_specific_data_authorization': bool(sensitive_data and public),
            'missing_dependencies': missing,
            'eligible_to_attempt': bool(entry and edition_allowed and not missing and not (sensitive_data and public)),
            'compute_edition_allowed': edition_allowed,
            'runtime_success_established': bool(entry and entry.get('runtime_state') == 'passed'),
        })
    return {'requested_intent': intent, 'selected_intent': selected, 'recommendations': recommendations,
            'state': 'plan_only', 'submitted': False,
            'limitations': ['Curated task routing, not model inference or proof of tool suitability.',
                            'No external plugin availability is assumed; consult the actual client tool inventory.',
                            'Dependency presence and previous success do not guarantee this query succeeds.']}


def _identifier(namespace, identifier):
    if namespace not in PATTERNS or not isinstance(identifier, str) or not re.fullmatch(PATTERNS[namespace], identifier):
        raise ValueError('Unsupported namespace or invalid identifier')
    return identifier.split('.')[0] if namespace == 'ensembl_gene' else identifier.upper() if namespace == 'pdb' else identifier


def resolve_identifier(namespace: str, identifier: str, species: str = '', assembly: str = '') -> dict:
    """Resolve one public identifier against an official API; retain ambiguity, versions and raw source data."""
    normalized = _identifier(namespace, identifier)
    if namespace == 'inchikey':
        raise ValueError('InChIKey is supported in local mapping audits; resolve compounds by an explicit CID or ChEMBL identifier')
    biological = namespace in {'gene_symbol', 'ensembl_gene', 'uniprot', 'rsid'}
    if biological and species not in SPECIES:
        raise ValueError('Explicit species required: ' + ', '.join(SPECIES))
    if namespace == 'rsid' and not assembly:
        raise ValueError('Variant queries require an explicit assembly')
    if not isinstance(assembly, str) or assembly and not re.fullmatch(r'[A-Za-z0-9_.-]{1,40}', assembly):
        raise ValueError('Invalid assembly')
    candidates, raw, issues = [], [], []
    route, coverage_complete = 'primary_official_api', True
    if namespace in {'gene_symbol', 'ensembl_gene'}:
        if namespace == 'gene_symbol':
            try:
                found = _get_json('https://rest.ensembl.org/xrefs/symbol/' + species + '/' + quote(normalized), {'object_type':'gene','content-type':'application/json'})
            except Exception as exc:
                transient = type(exc).__name__ in {'ReadTimeout','ConnectTimeout','Timeout','TimeoutError','ConnectionError'}
                transient = transient or (type(exc).__name__ == 'HTTPError' and getattr(getattr(exc,'response',None),'status_code',0) >= 500)
                if not transient:
                    raise
                raw.append({'source':'Ensembl symbol cross-reference','failure_type':type(exc).__name__})
                data = _get_json('https://rest.uniprot.org/uniprotkb/search',
                                 {'query':'(gene_exact:' + normalized + ') AND (organism_id:' + str(SPECIES[species]) + ')','format':'json','size':100})
                raw.append(data)
                found = []
                for protein in data.get('results', []):
                    if protein.get('organism',{}).get('taxonId') != SPECIES[species]:
                        continue
                    for ref in protein.get('uniProtKBCrossReferences', []):
                        if ref.get('database') == 'Ensembl':
                            for prop in ref.get('properties', []):
                                if prop.get('key') == 'GeneId':
                                    found.append({'type':'gene','id':prop['value'].split('.')[0]})
                route, coverage_complete = 'uniprot_cross_references_then_ensembl_lookup', False
            if not isinstance(found, list):
                raise ValueError('Unexpected Ensembl symbol response')
            ids = sorted({r['id'] for r in found if r.get('type') == 'gene'})
            raw.append(found)
            if len(ids) > 10:
                raise ValueError('More than ten candidates; narrow the identifier before lookup')
        else:
            ids = [normalized]
        for gene in ids:
            data = _get_json('https://rest.ensembl.org/lookup/id/' + quote(gene), {'content-type':'application/json'})
            raw.append(data)
            if data.get('id') != gene or data.get('object_type') != 'Gene':
                raise ValueError('Ensembl returned an unexpected identity or object type')
            candidates.append({'namespace':'ensembl_gene','identifier':gene,'version':data.get('version'),
                               'gene_symbol':data.get('display_name'),'species':data.get('species'),'assembly':data.get('assembly_name')})
            if namespace == 'ensembl_gene' and '.' in identifier and str(data.get('version')) != identifier.rsplit('.',1)[1]:
                issues.append('requested_identifier_version_mismatch')
    elif namespace == 'uniprot':
        if '-' in normalized:
            raise ValueError('Isoform accessions need isoform-specific sequence review; canonical entry lookup is not substituted')
        data = _get_json('https://rest.uniprot.org/uniprotkb/' + normalized + '.json')
        raw.append(data)
        if data.get('primaryAccession') != normalized:
            issues.append('primary_accession_changed')
        if data.get('organism', {}).get('taxonId') != SPECIES[species]:
            issues.append('species_mismatch')
        if assembly:
            issues.append('assembly_not_verified_for_uniprot_cross_references')
        for ref in data.get('uniProtKBCrossReferences', []):
            if ref.get('database') == 'Ensembl':
                properties = {p['key']:p['value'] for p in ref.get('properties', [])}
                candidates.append({'namespace':'ensembl_gene','identifier':properties.get('GeneId'),
                                   'transcript':ref.get('id'),'protein':properties.get('ProteinId'),
                                   'species':species, 'assembly':None})
        candidates = [c for c in candidates if c['identifier']]
        if not candidates:
            issues.append('no_ensembl_cross_reference')
    elif namespace == 'rsid':
        data = _get_json('https://rest.ensembl.org/variation/' + species + '/' + normalized, {'content-type':'application/json'})
        raw.append(data)
        if data.get('name') != normalized:
            issues.append('primary_variant_identifier_changed')
        mappings = data.get('mappings', [])
        candidates = [{'namespace':'genomic_location','identifier':r.get('location'),'species':species,
                       'assembly':r.get('assembly_name'),'alleles':r.get('allele_string'),'strand':r.get('strand')}
                      for r in mappings if r.get('assembly_name') == assembly]
        if not candidates:
            issues.append('requested_assembly_not_returned')
    elif namespace == 'pdb':
        data = _get_json('https://data.rcsb.org/rest/v1/core/entry/' + normalized)
        raw.append(data)
        if data.get('rcsb_id') != normalized:
            raise ValueError('PDB identifier mismatch')
        candidates = [{'namespace':'pdb','identifier':normalized,'title':data.get('struct',{}).get('title'),
                       'polymer_entity_ids':data.get('rcsb_entry_container_identifiers',{}).get('polymer_entity_ids',[])}]
    elif namespace in {'pubchem_cid','chembl'}:
        if namespace == 'pubchem_cid':
            data = _get_json('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/' + normalized + '/property/InChIKey/JSON')
            rows = data.get('PropertyTable',{}).get('Properties',[])
            if not rows or any(str(r.get('CID')) != normalized for r in rows):
                raise ValueError('PubChem identifier mismatch')
            candidates = [{'namespace':'inchikey','identifier':r.get('InChIKey')} for r in rows]
        else:
            data = _get_json('https://www.ebi.ac.uk/chembl/api/data/molecule/' + normalized + '.json')
            if data.get('molecule_chembl_id') != normalized:
                raise ValueError('ChEMBL identifier mismatch')
            key = (data.get('molecule_structures') or {}).get('standard_inchi_key')
            candidates = [{'namespace':'inchikey','identifier':key}] if key else []
        raw.append(data)
    for candidate in candidates:
        if biological and candidate.get('species') != species:
            issues.append('species_mismatch')
        if assembly and namespace in {'gene_symbol','ensembl_gene'} and candidate.get('assembly') != assembly:
            issues.append('assembly_mismatch')
    unique = {(c['namespace'], c['identifier']) for c in candidates}
    if not unique:
        issues.append('no_mapping_candidates')
    status = 'context_mismatch' if issues else 'ambiguous' if len(unique) > 1 else 'partial' if not coverage_complete else 'resolved'
    return {'input':{'namespace':namespace,'identifier':identifier,'normalized_identifier':normalized,'species':species,'assembly':assembly},
            'status':status,'identity_check_pass':not issues and bool(unique), 'ambiguous':len(unique)>1,
            'resolution_route':route, 'candidate_coverage_complete':coverage_complete,
            'candidate_count':len(unique),'candidates':candidates,'issues':sorted(set(issues)), 'source_data':raw,
            'limitations':['Cross-references are source assertions, not sequence equivalence or orthology proof.',
                           'No genome build conversion is performed. A variant identifier alone is not a uniquely specified allele.',
                           'A PDB entry does not establish chain identity; compound identity does not establish target binding.',
                           'A passing identity check does not make an ambiguous mapping safe for a one-to-one join.']}


def audit_identifier_mapping(rows: list, species: str, assembly: str = '') -> dict:
    """Audit caller-supplied mappings locally for malformed IDs, context gaps and conflicting joins; query nothing."""
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000 or species not in SPECIES:
        raise ValueError('Supply 1-10000 mapping rows and an explicit supported species')
    issues, pairs, seen, sources, targets = [], [], set(), {}, {}
    for index, row in enumerate(rows):
        row_issues = []
        if not isinstance(row, dict):
            issues.append({'row':index,'issues':['invalid_row']})
            continue
        try:
            source = (row['source_namespace'], _identifier(row['source_namespace'], row['source_id']))
            target = (row['target_namespace'], _identifier(row['target_namespace'], row['target_id']))
        except (KeyError, ValueError, TypeError):
            issues.append({'row':index,'issues':['invalid_identifier_or_namespace']})
            continue
        pair = (source, target)
        if pair in seen:
            row_issues.append('duplicate_mapping')
        seen.add(pair)
        pairs.append(pair)
        sources.setdefault(source,set()).add(target)
        targets.setdefault(target,set()).add(source)
        if row.get('species') != species:
            row_issues.append('species_missing_or_mismatch')
        if assembly and row.get('assembly') != assembly:
            row_issues.append('assembly_missing_or_mismatch')
        if not row.get('evidence_reference'):
            row_issues.append('missing_evidence_reference')
        for side in ('source','target'):
            if row[side+'_namespace'] == 'ensembl_gene' and '.' in row[side+'_id']:
                row_issues.append('version_suffix_requires_review')
        if row_issues:
            issues.append({'row':index,'issues':row_issues})
    one_to_many = [{'source':list(k),'targets':[list(x) for x in sorted(v)]} for k,v in sources.items() if len(v)>1]
    many_to_one = [{'target':list(k),'sources':[list(x) for x in sorted(v)]} for k,v in targets.items() if len(v)>1]
    return {'rows':len(rows),'parsed_rows':len(pairs),'row_issues':issues,'one_to_many':one_to_many,'many_to_one':many_to_one,
            'safe_one_to_one_join':not issues and not one_to_many and not many_to_one,
            'source_truth_verified':False, 'public_queries_performed':False,
            'limitations':['Evidence references are caller supplied and are not verified by this audit.',
                           'Version suffixes are retained in input but normalized for collision detection; review them before joining.',
                           'Legitimate biological relationships can be many-to-many; preserve them instead of selecting the first match.']}
