"""Discover bridge extensions without duplicating external skills."""
import importlib
import inspect
from importlib.util import find_spec
from functools import lru_cache

EXPORTS = {
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
    "atlas": ("atlas_ext", ["query_gtex", "query_hpa", "search_cellxgene_collections", "query_ena_runs"]),
    "workflow": ("workflow_ext", ["inspect_ssh_route", "prepare_remote_task", "prepare_server_inventory", "inspect_remote_task", "verify_remote_results", "audit_sample_metadata", "audit_result_table", "build_server_download_manifest"]),
    "literature": ("literature_ext", ["query_pubmed", "query_europepmc", "doi_metadata", "fetch_open_access_article", "fetch_supplementary_info_from_doi", "extract_local_document", "discover_publisher_supplements", "download_publisher_supplement"]),
    "omics": ("omics_ext", ["audit_expression_matrix", "audit_h5ad", "local_gene_set_enrichment", "preranked_gsea", "map_orthologs", "annotate_cells_by_markers", "transfer_cell_labels"]),
}


@lru_cache(maxsize=1)
def registry():
    entries = {}
    for category, (module_name, names) in EXPORTS.items():
        module = importlib.import_module(module_name)
        for name in names:
            function = getattr(module, name)
            required, optional = [], []
            for parameter in inspect.signature(function).parameters.values():
                item = {"name": parameter.name, "type": str(parameter.annotation).replace("<class '", "").replace("'>", ""), "description": parameter.name.replace("_", " ")}
                if parameter.default is inspect.Parameter.empty:
                    required.append(item)
                else:
                    item["default"] = parameter.default
                    optional.append(item)
            dependencies = []
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
            entries[(category, name)] = {"function": function, "name": name, "description": inspect.getdoc(function) or "", "required_parameters": required, "optional_parameters": optional, "implementation": f"bridge extension: {module_name}", "dependency_check": {package: find_spec(package) is not None for package in dependencies}}
            entries[(category,name)]['requires_local_edition'] = name in {'run_bulk_rnaseq','aggregate_pseudobulk','run_normalized_expression','run_small_single_cell','molecular_descriptors','run_vina_docking','score_pathway_activity','analyze_ppi_network','convert_molecular_structure'}
            entries[(category,name)]['requires_local_edition'] |= name in {'compare_groups','plan_sample_size','meta_analyze_effects','fit_statistical_model','run_designed_expression','import_expression_data','analyze_cell_composition','score_regulatory_activity','audit_network_stability','audit_batch_embedding','run_donor_differential_state','infer_diffusion_pseudotime','evaluate_binary_prediction','prepare_ligand_meeko'}
    return entries
