"""Discover bridge extensions without duplicating external skills."""
import importlib
import inspect
from functools import lru_cache

EXPORTS = {
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
            entries[(category, name)] = {"function": function, "name": name, "description": inspect.getdoc(function) or "", "required_parameters": required, "optional_parameters": optional, "implementation": f"bridge extension: {module_name}"}
    return entries
