"""Discover bridge extensions without duplicating external skills."""
import importlib
import inspect
import ast
import os
from pathlib import Path
from importlib.util import find_spec
from functools import lru_cache

EXPORTS = {
    "omics_workflows": ("omics_workflows_ext", ["inspect_omics_workflows", "plan_omics_workflow", "audit_omics_readiness", "audit_omics_result_bundle"]),
    "validation": ("validation_ext", ["inspect_scientific_benchmarks", "audit_benchmark_receipt"]),
    "server_operations": ("server_operations_ext", ["plan_server_budget", "review_unknown_submission", "plan_incremental_return"]),
    "molecular_biology": ("molecular_biology_ext", ["guide_molecular_drylab", "inspect_molecular_resources", "plan_molecular_extension", "query_intact_interactions", "query_complex_record", "query_cell_line", "audit_splicing_results", "audit_regulatory_links", "audit_protein_annotations", "audit_interaction_records", "audit_perturbation_results", "audit_mechanism_graph", "prepare_molecular_pipeline"]),
    "cadd": ("cadd_ext", ["guide_cadd_workflow", "audit_simulation_protocol", "audit_restart_manifest", "audit_replica_exchange", "audit_docking_campaign", "audit_restraint_mapping", "audit_af3_records", "audit_mmgbsa_summary"]),
    "integrations": ("integration_ext", ["inspect_mcp_components", "prepare_slurm_monitor", "inspect_slurm_monitor"]),
    "table_query": ("table_query_ext", ["query_selected_table"]),
    "semantic_index": ("semantic_index_ext", ["prepare_semantic_index", "audit_semantic_results"]),
    "scientific_interfaces": ("interface_ext", ["inspect_scientific_interfaces", "export_zotero_snapshot", "export_cytoscape_snapshot", "prepare_cytoscape_revision", "apply_cytoscape_revision"]),
    "code_review": ("code_review_ext", ["map_code_project", "audit_scientific_code", "audit_notebook", "audit_data_contract", "audit_table_join", "compare_data_exchange", "audit_numeric_results", "compare_scientific_results", "bind_analysis_qc", "check_analysis_qc", "prepare_code_revision", "materialize_code_revision", "prepare_method_reproduction", "audit_plan_implementation", "prepare_api_migration", "inspect_dependency_locks", "compare_environments", "prepare_scientific_test_suite", "prepare_configuration_migration", "apply_configuration_migration", "audit_dependency_components", "audit_release_scope"]),
    "code_execution": ("code_execution_ext", ["prepare_code_execution", "inspect_code_execution", "summarize_performance", "estimate_compute_resources", "audit_parallel_execution", "audit_resume_compatibility", "prepare_code_workflow", "preview_code_workflow", "prepare_code_task_array", "prepare_adapter_development"]),
    "clinical_research": ("clinical_research_ext", ["audit_medical_guidelines", "query_drug_reference", "read_drug_label", "compare_drug_labels", "audit_clinical_dataset", "audit_clinical_mapping", "guide_clinical_study", "audit_clinical_prediction", "audit_medical_reporting", "extract_review_effects", "record_bias_assessment", "audit_adverse_event_reports", "audit_imaging_metadata", "prepare_medical_teaching", "prepare_clinical_backend"]),
    "workbench": ("workbench_ext", ["create_research_project", "inspect_research_project", "prepare_project_revision", "apply_project_revision", "advance_workflow_stage", "execute_workflow_stage", "audit_project_lineage", "build_project_dashboard", "freeze_reproduction_package", "create_private_backup", "prepare_private_restore", "apply_private_restore", "validate_adapter_contract"]),
    "academic_workspace": ("academic_workspace_ext", ["index_selected_fulltext", "search_selected_fulltext", "prepare_zotero_incremental_sync", "apply_zotero_incremental_sync", "create_review_search", "retrieve_review_search_page", "record_independent_screening", "resolve_screening_conflict", "inspect_review_search"]),
    "scientific_backend": ("scientific_backend_ext", ["inspect_scientific_backends", "prepare_scientific_backend", "prepare_pdf_ocr"]),
    "word_native": ("word_native_ext", ["inspect_native_word", "prepare_native_word_revision", "apply_native_word_revision", "render_native_word_pdf", "request_native_citation_refresh"]),
    "personal_library": ("personal_library_ext", ["create_personal_library", "inspect_personal_library", "prepare_personal_library_ingest", "apply_personal_library_ingest", "search_personal_library", "annotate_personal_reference", "export_personal_library"]),
    "library": ("library_ext", ["import_reference_library", "audit_reference_duplicates", "export_reference_library", "index_pdf_folder"]),
    "zotero": ("zotero_ext", ["inspect_zotero_connection", "read_zotero_library", "read_zotero_attachment", "prepare_zotero_write", "apply_zotero_write"]),
    "review": ("review_ext", ["inspect_manuscript", "audit_claim_evidence", "audit_paper", "audit_review", "audit_manuscript_format", "audit_terminology_units", "find_similar_studies", "check_publication_updates", "audit_reporting_checklist", "audit_reference_metadata"]),
    "collaboration": ("collaboration_ext", ["plan_manuscript", "build_evidence_draft", "compare_manuscript_versions", "prepare_manuscript_revision", "manage_collaboration_review", "prepare_reviewer_response"]),
    "privacy": ("privacy_ext", ["inspect_privacy_policy", "audit_outbound_parameters"]),
    "statistics": ("statistics_ext", ["guide_study_statistics", "audit_statistical_dataset", "compare_groups", "adjust_pvalues", "plan_sample_size", "meta_analyze_effects", "audit_prediction_split", "fit_statistical_model"]),
    "advanced": ("advanced_ext", ["run_designed_expression", "import_expression_data", "analyze_cell_composition", "score_regulatory_activity", "summarize_pathway_overlap", "audit_network_stability", "audit_redocking_coordinates", "audit_md_summary", "audit_batch_embedding", "run_donor_differential_state", "infer_diffusion_pseudotime", "audit_cell_communication", "evaluate_binary_prediction", "audit_colocalization_results"]),
    "server": ("server_ext", ["prepare_scheduler_task", "inspect_scheduler_receipt", "prepare_standard_pipeline", "inspect_multiqc_report"]),
    "reporting": ("reporting_ext", ["audit_analysis_result"]),
    "software": ("software_ext", ["register_local_software", "software_inventory", "check_software_health", "inspect_cytoscape_health", "cytoscape_render_network", "convert_molecular_structure", "cytoscape_import_network"]),
    "systems": ("systems_ext", ["score_pathway_activity", "query_string_network", "analyze_ppi_network"]),
    "qc": ("qc_ext", ["preflight_transcriptomics", "compare_analysis_results"]),
    "transcriptomics": ("transcriptomics_ext", ["inspect_local_compute", "run_bulk_rnaseq", "aggregate_pseudobulk", "run_normalized_expression", "run_small_single_cell"]),
    "molecular": ("molecular_ext", ["molecular_descriptors", "prepare_ligand_meeko", "audit_docking_inputs", "summarize_vina_poses", "run_vina_docking"]),
    "biomedical": ("biomedical_ext", ["audit_drug_target_records", "assess_cohort_eligibility", "audit_genetic_alignment", "build_evidence_matrix", "compare_evidence", "audit_structure_context", "map_disease_terms", "audit_cell_annotations", "audit_enrichment_results", "extract_study_elements"]),
    "research": ("research_ext", ["select_tools", "resolve_identifier", "audit_identifier_mapping"]),
    "research_quality": ("research_quality_ext", ["audit_literature_set", "audit_identifier_context", "resolve_public_identifiers", "audit_returned_analysis", "audit_evidence_trace"]),
    "atlas": ("atlas_ext", ["query_gtex", "query_hpa", "search_cellxgene_collections", "query_ena_runs"]),
    "workflow": ("workflow_ext", ["inspect_ssh_route", "prepare_remote_task", "prepare_server_inventory", "inspect_remote_task", "verify_remote_results", "audit_sample_metadata", "audit_result_table", "build_server_download_manifest"]),
    "literature": ("literature_ext", ["query_pubmed", "query_europepmc", "doi_metadata", "fetch_open_access_article", "fetch_supplementary_info_from_doi", "extract_local_document", "discover_publisher_supplements", "download_publisher_supplement"]),
    "omics": ("omics_ext", ["audit_expression_matrix", "audit_h5ad", "local_gene_set_enrichment", "preranked_gsea", "map_orthologs", "annotate_cells_by_markers", "transfer_cell_labels"]),
}


def enabled_categories():
    value = os.environ.get('BIOMNI_MODULES', '').strip()
    known = set(EXPORTS) | {'database', 'upstream'}
    if not value: return known
    selected = {x.strip() for x in value.split(',') if x.strip()}
    if not selected or selected - known: raise ValueError('Unknown or empty BIOMNI_MODULES selection')
    return selected


def registry():
    return _registry(tuple(sorted(enabled_categories())))


def _lazy_function(module_name, name):
    def call(**parameters):
        return getattr(importlib.import_module(module_name), name)(**parameters)
    return call


@lru_cache(maxsize=16)
def _registry(selected):
    entries = {}
    for category, (module_name, names) in EXPORTS.items():
        if category not in selected: continue
        try:
            tree = ast.parse(Path(__file__).with_name(module_name + '.py').read_text(encoding='utf8'))
        except (OSError, SyntaxError) as exc:
            for name in names:
                entries[(category,name)] = {'function':_lazy_function(module_name,name),'name':name,'description':'Module source is unavailable; repair the selected installation.',
                    'required_parameters':[],'optional_parameters':[],'dependency_check':{},'implementation':'bridge extension: '+module_name,
                    'module_load':'unavailable','discovery_error':type(exc).__name__,'requires_local_edition':False}
            continue
        definitions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name in names:
            node = definitions[name]
            function = _lazy_function(module_name, name)
            required, optional = [], []
            defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults)
            for parameter, default in zip(node.args.args, defaults):
                item = {"name": parameter.arg, "type": ast.unparse(parameter.annotation) if parameter.annotation else 'Any', "description": parameter.arg.replace("_", " ")}
                if default is None:
                    required.append(item)
                else:
                    item["default"] = ast.literal_eval(default)
                    optional.append(item)
            dependencies = []
            if category == 'molecular_biology' and name.startswith('query_'): dependencies = ['requests']
            if category=='table_query': dependencies=['duckdb']
            if category=='scientific_interfaces': dependencies=['requests']
            if category=='academic_workspace' and name=='index_selected_fulltext': dependencies=['pypdf']
            if category=='academic_workspace' and name=='retrieve_review_search_page': dependencies=['requests']
            if category=='zotero': dependencies=['requests']
            if category=='library' and name=='index_pdf_folder': dependencies=['pypdf']
            if category=='review': dependencies=['requests'] if name in {'find_similar_studies','check_publication_updates','audit_reference_metadata'} else ['pypdf']
            if category=='statistics':
                dependencies = ['numpy','scipy'] if name=='compare_groups' else ['scipy'] if name in {'plan_sample_size','meta_analyze_effects'} else ['numpy','pandas','statsmodels'] if name=='fit_statistical_model' else []
            if category=='advanced':
                dependencies = [] if name in {'summarize_pathway_overlap','audit_redocking_coordinates','audit_md_summary','audit_cell_communication','audit_colocalization_results'} else ['numpy','pandas']
                dependencies += {'import_expression_data':['anndata','scipy'], 'infer_diffusion_pseudotime':['scanpy','anndata','scipy'], 'evaluate_binary_prediction':['sklearn'], 'audit_batch_embedding':['sklearn'], 'audit_network_stability':['networkx','sklearn']}.get(name,[])
            if category=='software' and name in {'inspect_cytoscape_health','cytoscape_render_network'}: dependencies=['requests']
            if category=='systems':
                dependencies = ['numpy','pandas','gseapy'] if name=='score_pathway_activity' else ['networkx','matplotlib'] if name=='analyze_ppi_network' else ['requests']
            if category=='software' and name=='cytoscape_import_network': dependencies = ['networkx','requests']
            if category=='qc':
                dependencies = ['numpy','pandas','scipy','sklearn','psutil']
            if category=='transcriptomics':
                dependencies = ['psutil'] if name=='inspect_local_compute' else ['numpy','pandas']
                dependencies += {'run_bulk_rnaseq':['pydeseq2','matplotlib','sklearn'], 'run_normalized_expression':['matplotlib','sklearn'], 'run_small_single_cell':['scanpy','igraph','leidenalg','matplotlib']}.get(name,[])
            if category=='molecular' and name=='molecular_descriptors':
                dependencies = ['rdkit']
            if category=='molecular' and name=='prepare_ligand_meeko': dependencies=['rdkit','meeko','gemmi']
            if category == 'omics' and name != 'map_orthologs':
                dependencies = ['numpy', 'pandas', 'scipy']
                dependencies += {'audit_h5ad':['anndata'], 'preranked_gsea':['gseapy'], 'transfer_cell_labels':['sklearn']}.get(name, [])
            entries[(category, name)] = {"function": function, "name": name, "description": ast.get_docstring(node) or "", "required_parameters": required, "optional_parameters": optional, "implementation": f"bridge extension: {module_name}", "dependency_check": {package: find_spec(package) is not None for package in dependencies}, 'module_load': 'deferred_until_call'}
            entries[(category,name)]['requires_local_edition'] = name in {'run_bulk_rnaseq','aggregate_pseudobulk','run_normalized_expression','run_small_single_cell','molecular_descriptors','run_vina_docking','score_pathway_activity','analyze_ppi_network','convert_molecular_structure'}
            entries[(category,name)]['requires_local_edition'] |= name in {'compare_groups','plan_sample_size','meta_analyze_effects','fit_statistical_model','run_designed_expression','import_expression_data','analyze_cell_composition','score_regulatory_activity','audit_network_stability','audit_batch_embedding','run_donor_differential_state','infer_diffusion_pseudotime','evaluate_binary_prediction','prepare_ligand_meeko'}
    return entries
