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
    selected = 'server_task' if large_computation else intent
    recommendations = []
    for category, name in INTENTS[selected]:
        entries = tool_catalog(category=category, search=name, limit=100)['tools']
        entry = next((e for e in entries if e['name'] == name), None)
        public = category in {'database', 'atlas', 'literature'} or name == 'resolve_identifier'
        missing = [p for p, ready in (entry or {}).get('dependency_check', {}).items() if not ready]
        recommendations.append({
            'category': category, 'name': name, 'catalog_entry': entry,
            'placement': 'local_preparation_for_server' if selected == 'server_task' else 'local',
            'uses_public_endpoint': public,
            'requires_specific_data_authorization': bool(sensitive_data and public),
            'missing_dependencies': missing,
            'eligible_to_attempt': bool(entry and not missing and not (sensitive_data and public)),
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
    if namespace in {'gene_symbol', 'ensembl_gene'}:
        if namespace == 'gene_symbol':
            found = _get_json('https://rest.ensembl.org/xrefs/symbol/' + species + '/' + quote(normalized), {'object_type':'gene','content-type':'application/json'})
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
    status = 'context_mismatch' if issues else 'ambiguous' if len(unique) > 1 else 'resolved'
    return {'input':{'namespace':namespace,'identifier':identifier,'normalized_identifier':normalized,'species':species,'assembly':assembly},
            'status':status,'identity_check_pass':not issues and bool(unique), 'ambiguous':len(unique)>1,
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
