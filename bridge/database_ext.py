"""Explicit database adapters and corrections for the pinned Biomni release."""
import json
import re
from urllib.parse import quote, urlsplit
from http_client import get_json, graphql

# function, allowed parameters, required parameter, permitted HTTPS host
SPECS = {
    "reactome": ("query_reactome", {"endpoint", "verbose"}, "endpoint", "reactome.org"),
    "clinvar": ("query_clinvar", {"search_term", "max_results"}, "search_term", None),
    "gwas_catalog": ("query_gwas_catalog", {"endpoint", "params", "max_results"}, "endpoint", "www.ebi.ac.uk"),
    "gnomad": ("query_gnomad", {"gene_symbol", "reference_genome", "query", "variables"}, None, None),
    "opentargets": ("query_opentarget", {"query", "variables", "verbose"}, "query", None),
    "interpro": ("query_interpro", {"endpoint", "max_results"}, "endpoint", "www.ebi.ac.uk"),
    "pdb": ("query_pdb", {"query", "max_results"}, "query", None),
    "pdb_data": ("query_pdb_data", {"endpoint"}, "endpoint", "data.rcsb.org"),
    "sifts": ("query_sifts", {"pdb_id"}, "pdb_id", None),
    "chembl": ("query_chembl", {"endpoint", "chembl_id", "smiles", "molecule_name", "max_results", "verbose"}, None, "www.ebi.ac.uk"),
    "pubchem": ("query_pubchem", {"endpoint", "max_results", "verbose"}, "endpoint", "pubchem.ncbi.nlm.nih.gov"),
    "string": ("query_stringdb", {"endpoint", "verbose"}, "endpoint", "version-12-0.string-db.org"),
    "pride": ("query_pride", {"endpoint", "max_results"}, "endpoint", "www.ebi.ac.uk"),
}


def validate(name, parameters):
    _, allowed, required, host = SPECS[name]
    extras = set(parameters) - allowed
    if extras:
        raise ValueError(f"Unsupported parameters for {name}: {sorted(extras)}")
    if required and not parameters.get(required):
        raise ValueError(f"{name} requires {required}")
    if name == "gnomad" and not (parameters.get("gene_symbol") or parameters.get("query")):
        raise ValueError("gnomad requires gene_symbol or a read-only GraphQL query")
    if name == "chembl" and not any(parameters.get(key) for key in ("endpoint", "chembl_id", "smiles", "molecule_name")):
        raise ValueError("chembl requires endpoint or a molecule identifier")
    if "max_results" in parameters and (type(parameters["max_results"]) is not int or not 1 <= parameters["max_results"] <= 100):
        raise ValueError("max_results must be an integer from 1 to 100")
    endpoint = parameters.get("endpoint")
    if endpoint is not None:
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must be a nonempty string")
        url = urlsplit(endpoint)
        if url.scheme or url.netloc:
            if url.scheme != "https" or url.hostname != host or url.username or url.password:
                raise ValueError(f"{name} requires official HTTPS host {host}")
        if endpoint.lstrip().startswith(("//", "\\")):
            raise ValueError("Invalid endpoint")
    if "query" in parameters and isinstance(parameters["query"], str) and re.search(r"\bmutation\b", parameters["query"], re.I):
        raise ValueError("Only read-only GraphQL queries are supported")


def adapted_query(name, p):
    """Return None for unchanged upstream functions; otherwise use a corrected adapter."""
    if name == "reactome":
        endpoint = p["endpoint"]
        if endpoint.startswith("https://"):
            url = endpoint
        else:
            url = "https://reactome.org/ContentService/" + endpoint.lstrip("/")
        if not any(url.startswith(base) for base in ("https://reactome.org/ContentService/", "https://reactome.org/AnalysisService/")):
            raise ValueError("Use the Reactome ContentService or AnalysisService")
        result = get_json(url)
        identifier = re.search(r"/data/query/(R-[A-Z]{3}-\d+)(?:$|\?)", url)
        if identifier and (not isinstance(result, dict) or result.get("stId") != identifier[1]):
            return {"success": False, "error": "Reactome stable identifier mismatch", "result": result}
        return {"success": True, "query_info": {"endpoint": url}, "result": result}
    if name == "gwas_catalog":
        base = "https://www.ebi.ac.uk/gwas/rest/api/v2"
        endpoint = p["endpoint"]
        if endpoint.startswith("https://"):
            if not endpoint.startswith(base + "/"):
                raise ValueError("GWAS Catalog queries must use API v2")
            url = endpoint
        else:
            url = base + "/" + endpoint.lstrip("/")
        params = {"size": p.get("max_results", 10), **p.get("params", {})}
        return {"success": True, "api_version": "v2", "result": get_json(url, params)}
    if name == "gnomad":
        reference = p.get("reference_genome", "GRCh38")
        if reference not in {"GRCh37", "GRCh38"}:
            raise ValueError("reference_genome must be GRCh37 or GRCh38")
        query = p.get("query")
        variables = p.get("variables", {})
        if not query:
            symbol = p["gene_symbol"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", symbol):
                raise ValueError("Invalid gene symbol")
            query = '''query($symbol:String!, $reference:ReferenceGenomeId!){
                gene(gene_symbol:$symbol, reference_genome:$reference){
                    gene_id symbol canonical_transcript_id
                    gnomad_constraint { obs_lof exp_lof oe_lof oe_lof_upper }
                }
            }'''
            variables = {"symbol": symbol, "reference": reference}
        result = graphql("https://gnomad.broadinstitute.org/api", query, variables)
        result["reference_genome"] = reference
        result["scope"] = "Constraint annotation; variant frequencies require an explicit dataset in a custom query."
        return result
    if name == "opentargets":
        return graphql("https://api.platform.opentargets.org/api/v4/graphql", p["query"], p.get("variables"))
    if name == "pdb_data":
        base = "https://data.rcsb.org/rest/v1/core"
        endpoint = p["endpoint"]
        url = endpoint if endpoint.startswith("https://") else base + "/" + endpoint.lstrip("/")
        if not url.startswith(base + "/"):
            raise ValueError("Use the RCSB core API")
        return {"success": True, "result": get_json(url)}
    if name == "sifts":
        identifier = p["pdb_id"]
        if not re.fullmatch(r"[A-Za-z0-9]{4}", identifier):
            raise ValueError("pdb_id must contain four letters/digits")
        return {"success": True, "result": get_json("https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/" + identifier.lower()), "scope": "Residue/chain mapping; inspect discontinuities and isoforms before interpreting positions."}
    if name == "clinvar":
        from literature_ext import ncbi_search
        return ncbi_search("clinvar", p["search_term"], p.get("max_results", 5))
    return None
