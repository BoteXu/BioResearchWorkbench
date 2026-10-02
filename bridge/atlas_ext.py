"""Small public metadata queries; expression matrices stay on the server."""
import json
import re
from http_client import get_json, request


def query_gtex(endpoint: str, parameters: dict) -> dict:
    """Query a bounded GTEx expression/eQTL/sQTL page; retain release, tissue and pagination."""
    allowed = {'reference/geneSearch', 'reference/gene', 'expression/medianGeneExpression', 'association/singleTissueEqtl', 'association/singleTissueSqtl', 'association/singleTissueEqtlByLocation'}
    if endpoint not in allowed:
        raise ValueError('Unsupported GTEx endpoint')
    p = dict(parameters)
    if not 1 <= int(p.get('itemsPerPage', 100)) <= 1000 or not 0 <= int(p.get('page', 0)) <= 1000000:
        raise ValueError('Invalid pagination; maximum 1000 rows per call')
    p.setdefault('itemsPerPage', 100)
    if endpoint.startswith(('association/', 'expression/')):
        if not p.get('datasetId') or not p.get('tissueSiteDetailId'):
            raise ValueError('Explicit datasetId and tissueSiteDetailId required')
        if not any(p.get(k) for k in ('gencodeId', 'variantId', 'start')):
            raise ValueError('Target a gene, variant, or bounded region')
    if endpoint.endswith('ByLocation'):
        if not all(k in p for k in ('chromosome', 'start', 'end')) or not 0 < int(p['end']) - int(p['start']) <= 2000000:
            raise ValueError('Specify a region of at most 2 Mb')
    data = get_json('https://gtexportal.org/api/v2/' + endpoint, p)
    return {'source': 'GTEx', 'query': p, 'data': data, 'complete_dataset': False, 'limitations': ['Single bounded API page; check pagination before treating it as complete.', 'Normal tissue expression and QTL associations do not establish disease mechanisms or causality.']}


def query_hpa(ensembl_gene_id: str) -> dict:
    """Retrieve public Human Protein Atlas gene JSON without downloading image or bulk archives."""
    if not re.fullmatch(r'ENSG\d{11}', ensembl_gene_id):
        raise ValueError('An unversioned human Ensembl gene ID is required')
    data = get_json('https://www.proteinatlas.org/' + ensembl_gene_id + '.json')
    return {'source': 'Human Protein Atlas', 'gene': ensembl_gene_id, 'data': data, 'limitations': ['RNA expression and antibody-based protein measurements are distinct assays.', 'Review tissue, cell type, antibody reliability and release before interpretation.']}


def search_cellxgene_collections(search: str, limit: int = 20) -> dict:
    """Search public CELLxGENE collection metadata locally; does not download count matrices."""
    if not search.strip() or not 1 <= limit <= 100:
        raise ValueError('Provide a search term and limit 1..100')
    collections = get_json('https://api.cellxgene.cziscience.com/curation/v1/collections')
    if not isinstance(collections, list):
        raise ValueError('Unexpected CELLxGENE collection response')
    matches = [c for c in collections if search.casefold() in json.dumps(c, ensure_ascii=False).casefold()]
    return {'source': 'CELLxGENE Discover', 'search': search, 'total_matches': len(matches), 'collections': matches[:limit], 'limitations': ['Metadata discovery only; cell counts are not independent donor counts.', 'Check dataset schema, species, assay and donor metadata on the server before analysis.']}


def query_ena_runs(accession: str, limit: int = 100) -> dict:
    """Retrieve ENA run metadata, file URLs, sizes and MD5 for server-side acquisition."""
    if not re.fullmatch(r'(?:[SED]R[PRSX]\d+|PRJ[EDN][AB]\d+|SAM[END][AG]?\d+)', accession) or not 1 <= limit <= 1000:
        raise ValueError('Provide a public ENA/SRA study, sample, experiment or run accession; limit 1..1000')
    fields = 'run_accession,study_accession,sample_accession,scientific_name,tax_id,library_strategy,library_layout,read_count,fastq_ftp,fastq_md5,fastq_bytes'
    raw, _ = request('https://www.ebi.ac.uk/ena/portal/api/filereport', params={'accession': accession, 'result': 'read_run', 'fields': fields, 'format': 'json', 'limit': limit})
    data = json.loads(raw)
    return {'source': 'ENA', 'accession': accession, 'runs': data, 'limit': limit, 'possibly_truncated': len(data) >= limit, 'limitations': ['Run and sample accessions do not by themselves identify independent biological replicates.', 'FASTQ downloads should execute on the server; verify every file size and source MD5.']}
