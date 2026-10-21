"""Original bounded literature, identity, returned-result and evidence audits; no analysis engines."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from shared_support import BoundedCache

PUBLIC_CACHE = BoundedCache(max_items=32, max_bytes=2*1024**2, ttl=300)
ANALYSES = {
    'bulk': ['input_qc', 'design', 'normalization', 'differential', 'diagnostics'],
    'single_cell': ['cell_qc', 'doublet_review', 'annotation', 'donor_design', 'differential', 'diagnostics'],
    'spatial': ['spot_qc', 'spatial_coordinates', 'annotation', 'donor_design', 'spatial_model', 'diagnostics'],
    'pathway': ['identifier_mapping', 'gene_universe', 'enrichment', 'multiple_testing', 'redundancy_review'],
    'ppi': ['identifier_mapping', 'network_edges', 'edge_evidence', 'network_controls', 'stability'],
    'docking': ['input_qc', 'protocol', 'controls', 'poses', 'pose_review', 'score_domain'],
}


def _bounded(value):
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > 2*1024**2:
        raise ValueError('Narrow the selected summaries to 2 MiB')


def _rows(value, maximum=500):
    _bounded(value)
    if not isinstance(value, list) or not 1 <= len(value) <= maximum or any(not isinstance(v, dict) for v in value):
        raise ValueError('Provide a bounded nonempty list of record objects')
    ids = [row.get('id') for row in value]
    if any(not isinstance(v, str) or not v for v in ids) or len(set(ids)) != len(ids):
        raise ValueError('Record IDs must be nonempty and unique')
    return value


def _issue(issues, code, record='context', severity='block'):
    issues.append({'code': code, 'record': record, 'severity': severity})


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _finish(kind, value, issues, **extra):
    return {'audit': kind, 'input_sha256': _digest(value), 'issues': issues,
            'summary_consistent': not any(v['severity']=='block' for v in issues),
            'scientific_validity_established': False, 'caller_assertions_independently_verified': False,
            'public_queries_performed': False, **extra}


def _doi(value):
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', str(value or '').strip().lower())
    if value and not re.fullmatch(r'10\.\d{4,9}/\S+', value): raise ValueError('Invalid declared DOI')
    return value


def audit_literature_set(records: list, searches: list, relations: list = None) -> dict:
    """Audit exact-ID duplicates, declared publication relations/updates and search coverage; query nothing."""
    _rows(records); _rows(searches, 50); _bounded(relations or [])
    if not isinstance(relations or [], list) or len(relations or [])>500:
        raise ValueError('Publication relations must be a bounded list')
    issues = []; keys = {}; groups = []; updates = []; titles = {}; relations_out = []
    search_ids = {r['id'] for r in searches}
    for search in searches:
        for key in ['source', 'exact_query', 'retrieved_at_utc', 'returned_count', 'coverage_state']:
            if search.get(key) is None or search.get(key)=='': _issue(issues, 'missing_search_'+key, search['id'])
        if 'reported_total' not in search:
            _issue(issues, 'missing_search_reported_total', search['id'])
        elif search['reported_total'] is None:
            _issue(issues, 'search_total_unknown', search['id'], 'review')
            if search.get('coverage_state')=='all_reported_records':
                _issue(issues, 'unknown_total_cannot_establish_complete_search', search['id'])
        if search.get('coverage_state') not in {'bounded_page', 'all_reported_records', 'interrupted'}:
            _issue(issues, 'unknown_search_coverage', search['id'])
        for key in ['reported_total', 'returned_count']:
            if key=='reported_total' and 'reported_total' in search and search[key] is None: continue
            if type(search.get(key)) is not int or search[key]<0: _issue(issues, 'invalid_'+key, search['id'])
        if type(search.get('reported_total')) is int and type(search.get('returned_count')) is int:
            if search['returned_count']>search['reported_total']: _issue(issues, 'search_count_inconsistent', search['id'])
            if search.get('coverage_state')=='all_reported_records' and search['returned_count']!=search['reported_total']:
                _issue(issues, 'incomplete_search_declared_complete', search['id'])
    parent = {r['id']:r['id'] for r in records}
    def root(k):
        while parent[k]!=k: k=parent[k]
        return k
    for row in records:
        rid = row['id']; ids = []
        try: doi = _doi(row.get('doi'))
        except ValueError: doi = ''; _issue(issues, 'invalid_doi', rid)
        if doi: ids.append(('doi', doi))
        if row.get('pmid'):
            if not re.fullmatch(r'\d+', str(row['pmid'])): _issue(issues, 'invalid_pmid', rid)
            else: ids.append(('pmid', str(row['pmid'])))
        if not ids: _issue(issues, 'no_strong_publication_identifier', rid, 'review')
        for key in ids:
            if key in keys: parent[root(rid)] = root(keys[key])
            else: keys[key] = rid
        title = re.sub(r'\W+', '', str(row.get('title', '')).casefold())
        if title: titles.setdefault(title, []).append(rid)
        if row.get('search_id') not in search_ids: _issue(issues, 'missing_search_lineage', rid)
        if row.get('publication_type') not in {'preprint', 'article', 'review', 'correction', 'retraction_notice', 'other'}:
            _issue(issues, 'publication_type_requires_review', rid, 'review')
        if row.get('retracted') is True:
            _issue(issues, 'declared_retraction_review_required', rid); updates.append({'id':rid, 'state':'declared_retracted'})
        if row.get('corrected') is True: updates.append({'id':rid, 'state':'declared_corrected_review_required'})
        if not row.get('update_source'): _issue(issues, 'publication_update_check_not_documented', rid, 'review')
    buckets = {}
    for row in records: buckets.setdefault(root(row['id']), []).append(row)
    for rows in buckets.values():
        if len(rows)>1:
            groups.append([r['id'] for r in rows])
            pmids = {str(r['pmid']) for r in rows if r.get('pmid')}
            dois = set()
            for item in rows:
                try: normalized_doi = _doi(item.get('doi'))
                except ValueError: continue
                if normalized_doi: dois.add(normalized_doi)
            if len(pmids)>1 or len(dois)>1: _issue(issues, 'conflicting_strong_identifiers', rows[0]['id'])
    for link in relations or []:
        if not isinstance(link, dict): raise ValueError('Publication relation must be an object')
        if link.get('from') not in parent or link.get('to') not in parent or link.get('from')==link.get('to'):
            _issue(issues, 'invalid_publication_relation')
        if link.get('type') not in {'is_preprint_of', 'corrects', 'retracts', 'is_version_of'}:
            _issue(issues, 'unknown_publication_relation')
        if not link.get('source_reference') or not link.get('source_locator'):
            _issue(issues, 'unlocated_publication_relation')
        relations_out.append({**link, 'independently_verified':False})
    represented = {r.get('search_id') for r in records}
    for search in searches:
        selected = sum(r.get('search_id')==search['id'] for r in records)
        if type(search.get('returned_count')) is int and selected>search['returned_count']:
            _issue(issues, 'selected_records_exceed_reported_return', search['id'])
    return _finish('literature_set', [records, searches, relations], issues,
        exact_identifier_duplicate_groups=groups, publication_relations=relations_out, publication_updates=updates,
        title_only_review_candidates=[v for v in titles.values() if len(v)>1 and len({root(k) for k in v})>1],
        searches_without_selected_records=sorted(search_ids-represented), deduplication_applied=False,
        limitations=['Title similarity does not establish the same study.', 'Relations, correction and retraction flags require the located primary source.',
                     'A bounded page or missing update record cannot establish exhaustive search or absence of retraction.'])


def audit_search_snapshot(provider: str, records: list, search: dict, relations: list = None) -> dict:
    """Audit selected SciSpace or generic publication metadata offline; retain provider types, identifiers and unknown coverage."""
    _bounded([records, search, relations])
    if provider not in {'scispace', 'generic'} or not isinstance(records, list) or not 1<=len(records)<=500:
        raise ValueError('Select scispace or generic and one to 500 metadata records')
    if not isinstance(search, dict) or not isinstance(search.get('id'), str):
        raise ValueError('A search object with an explicit ID and coverage is required')
    if search.get('source')!=provider or search.get('returned_count')!=len(records):
        raise ValueError('Snapshot source and returned count must match the selected records')
    # Only metadata are retained. Abstracts, prompts and generated summaries are not evidence.
    normalized = []; issues = []
    labels = {'journal article':'article','article':'article','review':'review',
              'preprint':'preprint','correction':'correction','retraction notice':'retraction_notice','other':'other'}
    for raw in records:
        if not isinstance(raw, dict): raise ValueError('Publication metadata must be objects')
        rid = raw.get('unique_id') if provider=='scispace' else raw.get('id')
        if not isinstance(rid, str) or not rid.strip() or len(rid)>200:
            raise ValueError('Every record needs a stable provider ID')
        try: doi = _doi(raw.get('doi'))
        except ValueError: doi = ''; _issue(issues, 'invalid_provider_doi', rid)
        declared = str(raw.get('publication_type') or '').strip()
        kind = labels.get(declared.casefold(), 'other')
        if declared.casefold() not in labels: _issue(issues, 'provider_publication_type_requires_review', rid, 'review')
        hint = ('preprint' if doi.startswith(('10.48550/arxiv.', '10.1101/', '10.21203/'))
                else 'repository_record' if doi.startswith(('10.5281/zenodo.', '10.17863/', '10.25740/')) else None)
        if hint and kind!=hint:
            _issue(issues, 'identifier_type_hint_conflicts_with_provider_label', rid, 'review')
        date = raw.get('date', raw.get('publication_date'))
        if date:
            try: datetime.fromisoformat(str(date).replace('Z','+00:00'))
            except ValueError: _issue(issues, 'provider_date_requires_review', rid, 'review')
        row = {'id':rid, 'title':str(raw.get('title') or '').strip(), 'doi':doi,
               'publication_type':kind, 'provider_publication_type':declared,
               'identifier_type_hint':hint, 'provider_date':date,
               'date_semantics':'Provider date; online, issue and repository dates are not interchangeable.',
               'search_id':search['id'], 'primary_metadata_verified':False,
               'update_source':raw.get('update_source')}
        for key in ['pmid','retracted','corrected']:
            if key in raw: row[key]=raw[key]
        normalized.append(row)
    result = audit_literature_set(normalized, [search], relations)
    all_issues = issues+result['issues']
    return {**result, 'audit':'search_snapshot', 'provider':provider, 'records':normalized,
            'input_sha256':_digest([provider, records, search, relations]),
            'issues':all_issues, 'summary_consistent':not any(v['severity']=='block' for v in all_issues),
            'primary_metadata_verified':False, 'generated_text_is_primary_evidence':False,
            'search_exhaustiveness_established':False,
            'limitations':result['limitations']+[
                'DOI-prefix hints are review flags, not publisher verification or an automatic publication-type correction.',
                'Provider-generated summaries and missing limitation text cannot establish that a method has no limitations.']}


def prepare_figure_handoff(input_path: str, figure_spec: dict, context: dict, qc: dict, execution: dict, sources: list, output_dir: str = '') -> dict:
    """Bind one selected frozen TSV, QC, execution evidence and provenance to a portable figure handoff; execute no analysis."""
    from figure_handoff_contract import prepare_handoff
    return prepare_handoff(input_path, figure_spec, context, qc, execution, sources, output_dir)


def audit_identifier_context(records: list, expected_context: dict) -> dict:
    """Audit species, build, annotation release, transcript/isoform specificity and mapping ambiguity offline."""
    _rows(records); _bounded(expected_context); issues = []; mappings = {}
    if not isinstance(expected_context, dict) or not expected_context.get('species') or not expected_context.get('annotation_version'):
        raise ValueError('Expected species and annotation_version are required')
    namespaces = {'gene', 'transcript', 'protein', 'protein_isoform', 'variant', 'compound', 'structure_chain'}
    for row in records:
        rid = row['id']; namespace = row.get('namespace')
        if namespace not in namespaces: _issue(issues, 'unknown_identifier_namespace', rid)
        for key in ['species', 'annotation_version']:
            if row.get(key)!=expected_context[key]: _issue(issues, key+'_missing_or_mismatch', rid)
        if namespace in {'gene', 'transcript', 'variant'}:
            if not expected_context.get('assembly') or row.get('assembly')!=expected_context.get('assembly'):
                _issue(issues, 'assembly_missing_or_mismatch', rid)
        for key in ['source_id', 'target_id', 'source_reference', 'source_version']:
            if not row.get(key): _issue(issues, 'missing_'+key, rid)
        if row.get('candidate_coverage_complete') is not True: _issue(issues, 'candidate_coverage_incomplete', rid, 'review')
        if namespace == 'transcript' and not row.get('transcript_version'): _issue(issues, 'transcript_version_missing', rid)
        if namespace == 'protein_isoform' and (not row.get('isoform_id') or row.get('canonical_substituted') is not False):
            _issue(issues, 'isoform_identity_not_established', rid)
        mappings.setdefault((namespace, row.get('source_id')), set()).add(row.get('target_id'))
    ambiguous = [{'namespace':k[0], 'source_id':k[1], 'targets':sorted(str(v) for v in values)} for k,values in mappings.items() if len(values)>1]
    for row in ambiguous: _issue(issues, 'one_to_many_mapping_requires_policy', row['source_id'])
    return _finish('identifier_context', [records, expected_context], issues, ambiguous_mappings=ambiguous,
                   safe_one_to_one_join=not issues and not ambiguous,
                   limitations=['No sequence comparison, liftover, orthology inference or automatic first-candidate selection is performed.'])


def resolve_public_identifiers(namespace: str, identifiers: list, species: str = '', assembly: str = '', approved_public_data: bool = False, use_cache: bool = True) -> dict:
    """Resolve at most ten explicitly approved public IDs sequentially; preserve official raw data and partial failures."""
    if approved_public_data is not True: raise ValueError('Specific approval of these exact public identifiers is required')
    if type(use_cache) is not bool or not isinstance(identifiers, list) or not 1<=len(identifiers)<=10 or any(not isinstance(v,str) for v in identifiers):
        raise ValueError('Use one to ten public identifier strings')
    from research_ext import resolve_identifier, _identifier
    for identifier in identifiers: _identifier(namespace, identifier)
    rows = []
    for identifier in dict.fromkeys(identifiers):
        key = _digest([namespace, identifier, species, assembly])
        cached = PUBLIC_CACHE.get(key) if use_cache else None
        if cached is not None:
            rows.append({'identifier':identifier, 'cache_hit':True, **cached}); continue
        try:
            value = {'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                     'resolution':resolve_identifier(namespace, identifier, species, assembly)}
            if use_cache: PUBLIC_CACHE.put(key, value)
            rows.append({'identifier':identifier, 'cache_hit':False, **value})
        except Exception as error:
            rows.append({'identifier':identifier, 'cache_hit':False, 'error_type':type(error).__name__, 'state':'failed_requires_review'})
    return {'records':rows, 'requested_count':len(identifiers), 'unique_count':len(rows),
            'batch_complete':all('resolution' in v for v in rows),
            'public_resolution_attempted':any(not v['cache_hit'] for v in rows),
            'public_queries_performed':True if any(not v['cache_hit'] and 'resolution' in v for v in rows) else None if any(not v['cache_hit'] for v in rows) else False,
            'cache':PUBLIC_CACHE.summary(), 'source_truth_verified':False,
            'limitations':['Cache is bounded, memory-only, five minutes, and restricted to explicitly approved public IDs.',
                           'A cache hit reuses dated source data; it is not a fresh source fetch. Failed entries are never cached.',
                           'Partial fallback remains partial; retained cross-references do not prove sequence or isoform equivalence.']}


def audit_returned_analysis(analysis: str, artifacts: list, context: dict, qc: dict, completion: dict) -> dict:
    """Audit selected server-returned summaries, required result roles, exact QC bindings and method boundaries; execute nothing."""
    if analysis not in ANALYSES: raise ValueError('Choose a documented analysis: '+', '.join(ANALYSES))
    _rows(artifacts, 100); _bounded([context, qc, completion]); issues = []; checked = []; roles = set()
    for key in ['species', 'model', 'biological_unit', 'contrast', 'method', 'method_version', 'reference_version', 'design_sha256']:
        if not context.get(key): _issue(issues, 'missing_'+key)
    context_hash = _digest(context)
    if qc.get('state')!='passed' or qc.get('context_sha256')!=context_hash:
        _issue(issues, 'qc_not_passed_for_exact_context')
    if completion.get('state')!='completed' or type(completion.get('exit_code')) is not int or completion['exit_code']!=0:
        _issue(issues, 'server_completion_not_established')
    if completion.get('context_sha256')!=context_hash or not completion.get('receipt_reference'):
        _issue(issues, 'server_receipt_lineage_missing_or_mismatch')
    budget = 0
    for row in artifacts:
        rid = row['id']; roles.add(row.get('role')); result = {'id':rid, 'role':row.get('role'), 'bytes_checked':False}
        if not row.get('source_reference') or not row.get('locator'):
            _issue(issues, 'result_source_or_locator_missing', rid)
        if row.get('context_sha256')!=context_hash: _issue(issues, 'result_context_mismatch', rid)
        if not re.fullmatch(r'[a-f0-9]{64}', str(row.get('sha256', ''))): _issue(issues, 'invalid_result_hash', rid)
        if row.get('path'):
            path = Path(row['path'])
            if path.is_symlink() or not path.is_file(): _issue(issues, 'selected_result_missing_or_linked', rid)
            elif path.stat().st_size>20*1024**2 or budget+path.stat().st_size>100*1024**2:
                _issue(issues, 'selected_result_exceeds_bounded_check_budget', rid)
            else:
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    while block := stream.read(65536): digest.update(block); budget += len(block)
                result['bytes_checked'] = True
                result['hash_matches'] = digest.hexdigest()==row.get('sha256')
                if not result['hash_matches']: _issue(issues, 'result_hash_mismatch', rid)
        else: _issue(issues, 'selected_result_bytes_not_checked', rid, 'review')
        checked.append(result)
    missing = sorted(set(ANALYSES[analysis])-roles)
    for role in missing: _issue(issues, 'missing_result_role:'+role)
    if analysis in {'single_cell','spatial'}:
        if context.get('biological_unit') in {'cell','spot'}: _issue(issues, 'technical_unit_used_as_independent_replicate')
        if type(context.get('independent_units')) is not int or context['independent_units']<2:
            _issue(issues, 'independent_unit_count_requires_review')
    if analysis=='pathway':
        if not context.get('gene_universe_version') or not context.get('ranking_or_selection_rule'):
            _issue(issues, 'enrichment_universe_or_selection_missing')
    if analysis=='ppi' and context.get('interaction_claim')=='physical_binding' and context.get('edge_evidence')!='direct_physical':
        _issue(issues, 'functional_network_not_physical_binding_proof')
    if analysis=='docking':
        if context.get('score_units') not in {'kcal/mol', 'engine_specific'}: _issue(issues, 'docking_score_units_missing')
        if context.get('claims_experimental_activity') is True: _issue(issues, 'docking_not_experimental_activity')
    return _finish('returned_analysis', [analysis, artifacts, context, qc, completion], issues,
                   analysis=analysis, context_sha256=context_hash, required_roles=ANALYSES[analysis],
                   missing_roles=missing, checked_artifacts=checked, bytes_read=budget, server_submission_performed=False,
                   limitations=['Receipt/QC context bindings check internal consistency; declared receipts still need independent server verification.',
                                'Selected file checks do not inspect omitted matrices, validate statistical assumptions or establish scientific truth.'])


def audit_evidence_trace(claims: list, sources: list, context: dict) -> dict:
    """Audit located claim-to-source edges, versions, context conflicts and declared evidence ceilings offline."""
    _rows(claims); _rows(sources); _bounded(context); issues = []; edges = []; lookup = {s['id']:s for s in sources}
    for source in sources:
        for key in ['reference', 'version', 'locator', 'excerpt']:
            if not source.get(key): _issue(issues, 'missing_source_'+key, source['id'])
        if not re.fullmatch(r'[a-f0-9]{64}', str(source.get('sha256',''))): _issue(issues, 'invalid_source_hash', source['id'])
    for claim in claims:
        rid = claim['id']; before = len(issues)
        if not claim.get('text') or claim.get('reviewed_negation_and_context') is not True:
            _issue(issues, 'claim_context_not_reviewed', rid)
        links = claim.get('source_ids')
        if not isinstance(links,list) or not links:
            _issue(issues, 'claim_has_no_source_edges', rid); links = []
        for sid in links:
            source = lookup.get(sid)
            if source is None: _issue(issues, 'missing_claim_source', rid); continue
            for key in ['species','model','assay','biological_unit','contrast']:
                expected = claim.get(key, context.get(key))
                if not expected or source.get(key)!=expected: _issue(issues, 'source_'+key+'_missing_or_mismatch', rid)
            if claim.get('claim_type')=='causal' and source.get('evidence_type') in {'association','coexpression','motif','docking','database_prediction'}:
                _issue(issues, 'declared_evidence_below_causal_claim', rid)
            if source.get('retracted') is True: _issue(issues, 'retracted_source_requires_review', rid)
            edges.append({'claim_id':rid, 'source_id':sid, 'source_sha256':source.get('sha256'),
                          'source_locator':source.get('locator'), 'direct_support_established':False})
        if claim.get('support_label') not in {'direct', 'indirect', 'conflicting', 'insufficient', 'unreviewed'}:
            _issue(issues, 'unknown_support_label', rid)
        if claim.get('support_label')=='direct' and len(issues)>before: _issue(issues, 'direct_support_label_requires_revision', rid)
    return _finish('evidence_trace', [claims, sources, context], issues, edges=edges,
                   limitations=['Located excerpts and caller-declared support labels require human/model semantic review.',
                                'Hashes establish byte identity only; neither a citation nor this audit establishes direct support.'])
