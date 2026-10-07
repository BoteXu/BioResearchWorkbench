"""Original molecular dry-lab routing and bounded evidence audits; no analysis engines."""
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
from academic_common import artifact, text


def _digest(value):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf8')
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError('Finite JSON input required') from exc
    if len(raw) > 2_000_000:
        raise ValueError('Provide a bounded server summary, not a complete analysis dataset')
    return hashlib.sha256(raw).hexdigest()


def _context(value, genomic=False):
    _digest(value)
    if not isinstance(value, dict):
        raise ValueError('Explicit scientific context required')
    for key in ['species', 'model', 'biological_unit', 'contrast', 'source_version']:
        text(value.get(key), 500)
    if genomic:
        text(value.get('assembly'), 100)
    return value


def _rows(rows):
    _digest(rows)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000 or any(not isinstance(r, dict) for r in rows):
        raise ValueError('Provide 1 to 2000 summary records')
    ids = [text(r.get('id'), 200) for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Record IDs must be unique')
    return rows


def _number(value, low=None, high=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite numeric value required; booleans and numeric strings are refused')
    if low is not None and value < low or high is not None and value > high:
        raise ValueError('Numeric value outside the declared range')
    return value


def _issue(issues, code, scope, severity='block'):
    issues.append({'code': code, 'scope': scope, 'severity': severity})


def _common(row, context, issues, genomic=False):
    rid = row['id']
    for key in ['species', 'model', 'source_version'] + (['assembly'] if genomic else []):
        if not context.get(key) or row.get(key) != context.get(key):
            _issue(issues, key + '_mismatch_or_missing', rid)
    for key in ['source_location', 'assay']:
        if not isinstance(row.get(key), str) or not row[key].strip():
            _issue(issues, 'missing_' + key, rid)
    if not re.fullmatch('[a-f0-9]{64}', str(row.get('source_sha256', ''))):
        _issue(issues, 'missing_source_binding', rid)
    if row.get('source_reviewed') is not True:
        _issue(issues, 'unreviewed_source', rid)
    units = row.get('independent_units')
    if not isinstance(units, list) or not units or any(not isinstance(u, str) or not u.strip() for u in units):
        _issue(issues, 'missing_independent_units', rid)
    elif len(set(units)) != len(units):
        _issue(issues, 'duplicated_independent_units', rid)
    if row.get('biological_unit') != context['biological_unit']:
        _issue(issues, 'biological_unit_mismatch', rid)
    if row.get('contrast') != context['contrast']:
        _issue(issues, 'contrast_mismatch', rid)


def _finish(kind, inputs, issues, records=None, **extra):
    return artifact('molecular_' + kind, {
        'audit': kind, 'input_sha256': _digest(inputs), 'issues': issues,
        'qc_gate_pass': not any(i['severity'] == 'block' for i in issues),
        'records': records or [], 'scientific_validity': 'not_established',
        'execution_state': 'summary_audit_only',
        'limitations': ['Source review and QC declarations are supplied by the caller and need independent inspection.',
                        'Hashes identify exact inputs; they do not establish an assertion as true.',
                        'These tools inspect summaries; they do not execute or validate the underlying scientific engine.'],
        **extra,
    })


ROUTES = {
    'gene_annotation': {'sources': ['Ensembl', 'UniProt', 'InterPro'], 'analysis': ['research.resolve_identifier', 'research.audit_identifier_mapping'], 'qc': ['species and assembly', 'gene/transcript/protein namespace', 'annotation release and one-to-many mapping']},
    'expression': {'sources': ['GEO', 'ENA', 'GTEx', 'HPA'], 'analysis': ['qc.preflight_transcriptomics', 'statistics.guide_study_statistics', 'transcriptomics.run_bulk_rnaseq'], 'qc': ['count versus transformed matrix', 'sample order and donor independence', 'design, batch, contrast and resource budget']},
    'single_cell': {'sources': ['CELLxGENE', 'GEO'], 'analysis': ['omics.audit_h5ad', 'transcriptomics.aggregate_pseudobulk', 'advanced.run_donor_differential_state'], 'qc': ['donor-level replication', 'ambient RNA/doublets and cell-type labels', 'expression layer and integration effects']},
    'splicing': {'sources': ['Ensembl', 'GENCODE'], 'analysis': ['molecular_biology.audit_splicing_results', 'code_execution.prepare_code_execution'], 'methods': ['rMATS', 'LeafCutter', 'DEXSeq', 'DRIMSeq', 'IsoformSwitchAnalyzeR'], 'qc': ['event versus transcript estimand', 'junction coverage, mappability and strandedness', 'annotation/assembly, delta-PSI and tested universe']},
    'long_read_rna': {'sources': ['ENA', 'GENCODE'], 'analysis': ['molecular_biology.audit_splicing_results', 'code_execution.prepare_code_execution'], 'methods': ['IsoQuant', 'FLAIR', 'SQANTI3'], 'qc': ['full-length evidence and read support', 'internal priming and chimeras', 'novel structure versus abundance inference']},
    'chromatin': {'sources': ['ENCODE', 'JASPAR'], 'analysis': ['molecular_biology.audit_regulatory_links', 'code_execution.prepare_code_execution'], 'methods': ['nf-core/atacseq', 'nf-core/chipseq', 'DiffBind'], 'qc': ['fragment/TSS enrichment and assay-specific controls', 'peak reproducibility and common peak universe', 'assembly and peak-to-gene ambiguity']},
    'rna_binding': {'sources': ['ENCODE', 'RNAcentral'], 'analysis': ['molecular_biology.audit_regulatory_links', 'molecular_biology.audit_splicing_results'], 'methods': ['CLIPper', 'PureCLIP'], 'qc': ['input/background and replicate support', 'binding sites versus RNA-processing consequences', 'transcript and genomic coordinate mapping']},
    'translation': {'sources': ['GEO', 'PRIDE'], 'analysis': ['molecular_biology.audit_regulatory_links', 'code_execution.prepare_code_execution'], 'methods': ['RiboTaper', 'RiboCode', 'DESeq2 interaction model'], 'qc': ['periodicity and P-site assignment', 'paired RNA abundance', 'translation efficiency interaction estimand']},
    'epigenetics': {'sources': ['ENCODE', 'GEO'], 'analysis': ['molecular_biology.audit_regulatory_links', 'code_execution.prepare_code_execution'], 'methods': ['nf-core/methylseq', 'DSS'], 'qc': ['conversion/coverage and reference', 'cell mixture and batch', 'region testing and association boundaries']},
    'regulatory_network': {'sources': ['JASPAR', 'ENCODE', 'Reactome'], 'analysis': ['advanced.score_regulatory_activity', 'advanced.audit_network_stability', 'molecular_biology.audit_regulatory_links'], 'methods': ['decoupleR', 'Arboreto', 'SCENIC'], 'qc': ['regulon species and evidence', 'resampling, confounding and donor units', 'motif/coexpression versus causal regulation']},
    'protein_function': {'sources': ['UniProt', 'InterPro', 'QuickGO', 'HPA'], 'analysis': ['molecular_biology.audit_protein_annotations', 'biomedical.audit_structure_context'], 'qc': ['isoform/sequence and residue mapping', 'experimental versus predicted annotation', 'NOT qualifiers and PTM localization']},
    'proteomics': {'sources': ['PRIDE', 'ProteomeXchange'], 'analysis': ['molecular_biology.audit_protein_annotations', 'code_execution.prepare_code_execution'], 'methods': ['DIA-NN', 'MSstats', 'DEP'], 'qc': ['peptide/protein/site FDR', 'shared peptide and missingness model', 'PTM abundance versus protein abundance']},
    'interaction': {'sources': ['IntAct', 'Complex Portal', 'STRING'], 'analysis': ['molecular_biology.query_intact_interactions', 'molecular_biology.audit_interaction_records', 'systems.analyze_ppi_network'], 'qc': ['physical versus functional edge', 'complex expansion and assay context', 'source publications and isoform/fragment mapping']},
    'perturbation': {'sources': ['Cellosaurus', 'GEO'], 'analysis': ['molecular_biology.audit_perturbation_results', 'statistics.guide_study_statistics'], 'methods': ['MAGeCK', 'drug-response models'], 'qc': ['biological replication and matched controls', 'target specificity and confounding', 'multiple testing and context-specific effects']},
    'structure_cadd': {'sources': ['PDB', 'AlphaFold', 'ChEMBL', 'BindingDB'], 'analysis': ['cadd.guide_cadd_workflow', 'biomedical.audit_structure_context', 'molecular.audit_docking_inputs'], 'qc': ['chain/isoform/protonation mapping', 'positive controls and score comparability', 'independent starts and real engine receipts']},
    'mechanism': {'sources': ['PubMed', 'Europe PMC', 'Reactome'], 'analysis': ['molecular_biology.audit_mechanism_graph', 'biomedical.build_evidence_matrix', 'review.audit_claim_evidence'], 'qc': ['edge-specific evidence and direction', 'species/model/time context', 'negative findings, conflicts and alternative explanations']},
}

PIPELINES = {
    'atacseq': {'revision':'2.1.2','commit':'1a1dbe52ffbd82256c941a032b0e22abbd925b8a','annotation':True},
    'chipseq': {'revision':'2.1.0','commit':'76e2382b6d443db4dc2396e6831d1243256d80b0','annotation':True},
    'methylseq': {'revision':'4.2.0','commit':'5aa56467a85a5e2d6795ea72dfa5a5f0c9babc23','annotation':False},
}


def prepare_molecular_pipeline(pipeline: str, parameters: dict, qc_binding_file: str, qc_binding_sha256: str,
                               qc_inputs: list, design: dict, references: dict, remote_workdir: str,
                               expected_host: str, expected_outputs: list, context: dict, inputs: list) -> dict:
    """Prepare fixed commit-pinned nf-core ATAC/ChIP/methylation tasks after exact input/design/reference QC checks; submit nothing."""
    _context(context, True)
    if pipeline not in PIPELINES or not isinstance(parameters,dict):raise ValueError('Choose a fixed reviewed molecular pipeline')
    spec=PIPELINES[pipeline];required={'input','fasta','outdir','profile'} | ({'gtf'} if spec['annotation'] else set())
    if set(parameters)!=required or parameters['profile'] not in {'singularity','apptainer','docker','conda'}:
        raise ValueError('Provide only the fixed pipeline parameters and an existing supported server runtime')
    from workflow_ext import prepare_remote_task, _relative
    for key in required-{'profile'}:_relative(parameters[key])
    if not parameters['input'].endswith('.csv'):raise ValueError('Reviewed CSV samplesheet required')
    if not isinstance(inputs,list) or not inputs or not {parameters[k] for k in required-{'outdir','profile'}} <= {r.get('path') for r in inputs if isinstance(r,dict)}:
        raise ValueError('Samplesheet and references require checksummed server input bindings')
    if not isinstance(design,dict) or design.get('remote_inputs')!=inputs or design.get('pipeline_commit')!=spec['commit'] or design.get('statistical_consultation_recorded') is not True:
        raise ValueError('QC design must bind this pipeline commit, remote input manifest and statistical consultation')
    if not isinstance(references,dict) or references.get('assembly')!=context['assembly'] or references.get('source_version')!=context['source_version']:
        raise ValueError('QC reference context mismatch')
    from code_review_ext import check_analysis_qc
    qc=check_analysis_qc(qc_binding_file,qc_binding_sha256,qc_inputs,design,references)
    if qc.get('qc_current') is not True:raise ValueError('Input/design/reference QC has expired')
    argv=['nextflow','run','nf-core/'+pipeline,'-r',spec['commit'],'-profile',parameters['profile'],'--igenomes_ignore','true']
    for key in ['input','fasta','gtf','outdir']:
        if key in parameters:argv+=['--'+key,parameters[key]]
    bundle=prepare_remote_task(argv,remote_workdir,expected_host,expected_outputs,context,inputs)
    return {**bundle,'pipeline':'nf-core/'+pipeline,'reviewed_revision':spec['revision'],'pipeline_commit':spec['commit'],
            'qc_binding_sha256':qc_binding_sha256,'qc_current':True,'submitted':False,'argv':argv,
            'runtime_acceptance':'requires_real_server_receipt',
            'limitations':bundle['limitations']+['Pipeline schema and source are pinned; actual server engine, references and containers need runtime acceptance.',
            'No package installation, reference download, SSH connection or scheduler submission occurs here.',
            'Input readiness QC precedes dispatch; read/fragment/peak/conversion QC remains required before downstream inference.',
            'A preparation-time QC binding does not validate the subsequent scientific analysis.']}


def guide_molecular_drylab(task: str, context: dict) -> dict:
    """Plan a molecular dry-lab task with assay-specific QC and actual tool states; start no analysis."""
    _context(context)
    if task not in ROUTES:
        raise ValueError('Choose a task from the molecular dry-lab route catalog')
    from bridge import tool_catalog
    routes = []
    for route in ROUTES[task]['analysis']:
        category, name = route.split('.', 1)
        entries = tool_catalog(category=category, search=name, limit=100)['tools']
        entry = next((e for e in entries if e['name'] == name), None)
        routes.append({'tool': route, 'available_in_catalog': entry is not None,
                       'runtime_state': (entry or {}).get('runtime_state', 'unknown'),
                       'last_attempt_success': (entry or {}).get('last_attempt_success'),
                       'dependency_check': (entry or {}).get('dependency_check', {}),
                       'requires_local_edition': (entry or {}).get('requires_local_edition', False)})
    return artifact('molecular_plan', {'task': task, 'context': context, **ROUTES[task], 'tools': routes,
                    'state': 'plan_only', 'submitted': False, 'compute_placement': 'server',
                    'stages': ['question and estimand', 'input/reference/unit QC', 'method and environment review',
                               'explicit server dispatch', 'real receipts and result QC', 'evidence and interpretation'],
                    'method_runtime_state': 'not_verified_here',
                    'limitations': ['Method names are candidate routes, not installed or executable backends.',
                                    'Reuse the existing server environment and verify version, parameters and resource budget.',
                                    'QC and statistical consultation must precede formal inference.',
                                    'Public retrieval requires specifically approved public identifiers; private material stays local.']})


def inspect_molecular_resources() -> dict:
    """Inspect pinned external skill/MCP candidates, reused clients and implemented molecular resources."""
    path = Path(__file__).with_name('molecular_resources.json')
    if not path.exists():
        path = path.parent.parent / path.name
    return {'success': True, **json.loads(path.read_text(encoding='utf8')), 'runtime_state': 'not_probed',
            'limitations': ['Source review is scoped and static; it is not a complete security audit or runtime acceptance.',
                            'Repository-level licenses may differ from individual skill and database licenses.',
                            'External candidates are not automatically installed, registered or connected.']}


def plan_molecular_extension(resource_id: str, public_identifiers: list, scope: str = 'public_retrieval') -> dict:
    """Prepare a scoped external-resource review plan; disclose no identifiers and execute no installation or query."""
    data = inspect_molecular_resources()
    resource = next((r for r in data['candidates'] if r['id'] == resource_id), None)
    if resource is None or scope != 'public_retrieval':
        raise ValueError('Select a known resource with an explicit public-retrieval scope')
    if not isinstance(public_identifiers, list) or not 1 <= len(public_identifiers) <= 20:
        raise ValueError('Provide 1 to 20 reviewed public identifiers')
    for identifier in public_identifiers:
        text(identifier, 200)
    from privacy_ext import audit_outbound_parameters
    review = audit_outbound_parameters({'identifiers': public_identifiers})
    return artifact('molecular_extension_plan', {'resource_id': resource_id, 'source_commit': resource['commit'],
                    'scope': scope, 'query_sha256': _digest(public_identifiers),
                    'outbound_gate_pass': review['outbound_gate_pass'], 'issues': review['issues'],
                    'state': 'review_plan_only', 'installed': False, 'connected': False,
                    'required_reviews': ['selected tool schemas and code', 'pinned package/dependency integrity',
                                         'source-data terms', 'private credential isolation', 'bounded runtime acceptance'],
                    'limitations': ['This plan is not a usable MCP connection or authorization to transmit private material.',
                                    'Apply the existing skill-security workflow before installing a selected external payload.',
                                    'Reuse an existing working database function when the candidate only duplicates it.']})


def _authorized(approved_public_data):
    if approved_public_data is not True:
        raise ValueError('Explicit authorization for these public identifiers is required')


def query_intact_interactions(uniprot_id: str, taxon_id: int, approved_public_data: bool = False, page: int = 0, page_size: int = 10) -> dict:
    """Retrieve one bounded IntAct page for an approved public protein; preserve experimental context and partial coverage."""
    _authorized(approved_public_data)
    if not re.fullmatch(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[0-9]+)?', uniprot_id):
        raise ValueError('Provide a UniProt accession, not a free-text query')
    if type(taxon_id) is not int or not 1 <= taxon_id <= 10**9 or type(page) is not int or not 0 <= page <= 10000 or type(page_size) is not int or not 1 <= page_size <= 50:
        raise ValueError('Provide bounded taxonomy and pagination values')
    from http_client import get_json
    # Use the observed accession search grammar, then retain explicit per-row species context.
    # Unsupported field aliases can return HTTP 200 with zero hits and must not masquerade as absence.
    query = uniprot_id
    data = get_json('https://www.ebi.ac.uk/intact/ws/interaction/findInteractions/' + quote(query, safe=''), {'page': page, 'pageSize': page_size})
    if not isinstance(data, dict) or not isinstance(data.get('content'), list) or len(data['content']) > page_size:
        raise ValueError('Unexpected or unbounded IntAct response')
    if data.get('number') != page or data.get('size') != page_size or type(data.get('totalElements')) is not int or data['totalElements'] < 0:
        raise ValueError('IntAct pagination contract changed; do not infer complete coverage')
    fields = ['ac', 'idA', 'idB', 'uniqueIdA', 'uniqueIdB', 'taxIdA', 'taxIdB', 'detectionMethod', 'type', 'interactionType',
              'detectionMethodMIIdentifier', 'publicationPubmedIdentifier', 'publicationIdentifiers', 'publicationAnnotations', 'expansionMethod', 'negative', 'mutationA', 'mutationB', 'intactMiscore', 'hostOrganismTaxId']
    selected = [row for row in data['content'] if taxon_id in {row.get('taxIdA'), row.get('taxIdB')}]
    unresolved_species = sum(type(row.get('taxIdA')) is not int or type(row.get('taxIdB')) is not int for row in data['content'])
    records = [{key: row.get(key) for key in fields} for row in selected]
    coverage = page == 0 and len(data['content']) == data['totalElements'] and not unresolved_species
    return {'success': True, 'source': 'IntAct', 'source_version': 'not_reported', 'query': {'uniprot_id': uniprot_id, 'taxon_id': taxon_id},
            'records': records, 'raw_result': data, 'page': page, 'page_size': page_size, 'total_records_before_species_filter': data['totalElements'],
            'species_filter': 'local_page_filter_at_least_one_participant', 'unresolved_species_rows': unresolved_species,
            'returned_before_species_filter': len(data['content']), 'returned_after_species_filter': len(records),
            'candidate_coverage_complete': coverage, 'next_page': page + 1 if data.get('last') is False else None,
            'scientific_validity': 'not_established',
            'limitations': ['Review returned participant species: a species query can include cross-species interactions.',
                            'Accession searches can include isoforms, processed fragments and mutations; inspect uniqueIdA/B.',
                            'A recorded interaction can be association or complex expansion, not direct binding or regulatory direction.',
                            'Database curation and publication sources need independent review; no bulk pagination is performed.']}


def query_complex_record(complex_id: str, approved_public_data: bool = False) -> dict:
    """Retrieve one approved public Complex Portal accession; check identity and preserve stoichiometry/source context."""
    _authorized(approved_public_data)
    if not re.fullmatch(r'CPX-[1-9][0-9]{0,9}', complex_id):
        raise ValueError('Provide a Complex Portal accession')
    from http_client import get_json
    data = get_json('https://www.ebi.ac.uk/intact/complex-ws/complex/' + complex_id)
    if not isinstance(data, dict) or data.get('complexAc') != complex_id or not isinstance(data.get('participants'), list):
        raise ValueError('Complex Portal identity/schema mismatch')
    return {'success': True, 'source': 'Complex Portal', 'source_version': data.get('version', 'not_reported'),
            'complex_id': complex_id, 'identity_check_pass': True, 'result': data,
            'limitations': ['Complex membership is not every pair directly binding.',
                            'Inspect species, participant isoforms/fragments, stoichiometry and experimental versus inferred evidence.']}


def query_cell_line(accession: str, approved_public_data: bool = False) -> dict:
    """Read bounded Cellosaurus identity/species/caution metadata for one approved public cell line; no donor or private table upload."""
    _authorized(approved_public_data)
    if not re.fullmatch(r'CVCL_[A-Z0-9]{4}', accession):
        raise ValueError('Provide a Cellosaurus accession')
    from http_client import get_json
    data = get_json('https://api.cellosaurus.org/cell-line/' + accession, {'format': 'json', 'fields': 'ac,id,ox,caution,problematic,dt'})
    entries = data.get('Cellosaurus', {}).get('cell-line-list', []) if isinstance(data, dict) else []
    if len(entries) != 1 or not any(a.get('type') == 'primary' and a.get('value') == accession for a in entries[0].get('accession-list', [])):
        raise ValueError('Cellosaurus primary accession mismatch; review merged/secondary identifiers separately')
    return {'success': True, 'source': 'Cellosaurus', 'accession': accession, 'identity_check_pass': True,
            'entry_version': entries[0].get('entry-version'), 'last_updated': entries[0].get('last-updated'), 'result': entries[0],
            'limitations': ['A reference entry is not authentication of the actual experimental cell stock.',
                            'Missing caution metadata is not proof that contamination or misidentification is absent.']}


def audit_splicing_results(records: list, context: dict) -> dict:
    """Audit returned event/isoform results, separating abundance, junction/structure evidence, design and protein extrapolation."""
    _context(context, True); _rows(records); issues = []; decisions = []
    for row in records:
        rid = row['id']; before = len(issues); _common(row, context, issues, True)
        level = row.get('analysis_level')
        if level not in {'exon_event', 'transcript_usage', 'transcript_abundance', 'transcript_structure'}:
            _issue(issues, 'unknown_analysis_level', rid)
        for key in ['gene_id', 'feature_id', 'annotation_version', 'method_version', 'library_type']:
            if not isinstance(row.get(key), str) or not row[key].strip(): _issue(issues, 'missing_' + key, rid)
        for key in ['mapping_qc_pass', 'coverage_qc_pass', 'design_qc_pass']:
            if row.get(key) is not True: _issue(issues, 'missing_or_failed_' + key, rid)
        evidence = row.get('evidence_type')
        if evidence not in {'gene_expression', 'junction_counts', 'transcript_estimate', 'full_length_structure'}:
            _issue(issues, 'unknown_evidence_type', rid)
        if level in {'exon_event', 'transcript_usage', 'transcript_structure'} and evidence == 'gene_expression':
            _issue(issues, 'gene_expression_not_isoform_evidence', rid)
        if level == 'transcript_structure' and evidence != 'full_length_structure':
            _issue(issues, 'insufficient_transcript_structure_evidence', rid)
        if level != 'transcript_structure':
            effect = row.get('effect'); units = row.get('effect_unit')
            if units not in {'delta_psi_fraction', 'delta_usage_fraction', 'log2_fold_change'}:
                _issue(issues, 'unknown_effect_unit', rid)
            elif effect is None: _issue(issues, 'missing_effect', rid)
            else: _number(effect, -1 if units.endswith('_fraction') else None, 1 if units.endswith('_fraction') else None)
            if level == 'exon_event' and units != 'delta_psi_fraction': _issue(issues, 'event_estimand_mismatch', rid)
            if level == 'transcript_usage' and units != 'delta_usage_fraction': _issue(issues, 'usage_estimand_mismatch', rid)
            if level == 'transcript_abundance' and units != 'log2_fold_change': _issue(issues, 'abundance_estimand_mismatch', rid)
            if row.get('adjusted_pvalue') is None: _issue(issues, 'missing_adjusted_pvalue', rid)
            else: _number(row['adjusted_pvalue'], 0, 1)
            if row.get('tested_universe_recorded') is not True: _issue(issues, 'missing_tested_universe', rid)
        if row.get('claims_protein_change') is True and row.get('protein_evidence_reviewed') is not True:
            _issue(issues, 'rna_result_not_protein_validation', rid)
        decisions.append({'id': rid, 'analysis_level': level, 'evidence_type': evidence, 'summary_consistent': len(issues) == before,
                          'protein_change_established': False})
    return _finish('splicing', {'records': records, 'context': context}, issues, decisions)


def _regulatory(row, issues):
    rid = row['id']; mode = row.get('evidence_type'); claim = row.get('claim')
    ceilings = {'motif': 'sequence_candidate', 'accessibility': 'accessible_region', 'coexpression': 'association',
                'chip_binding': 'binding_context', 'clip_binding': 'binding_context', 'chromatin_contact': 'spatial_proximity',
                'perturbation': 'context_specific_effect', 'methylation_association': 'association', 'ribosome_occupancy': 'occupancy'}
    if mode not in ceilings: _issue(issues, 'unknown_regulatory_evidence', rid)
    allowed = {'candidate', 'association', 'binding', 'regulation', 'translation_efficiency'}
    if claim not in allowed: _issue(issues, 'unknown_regulatory_claim', rid)
    if claim == 'binding' and mode not in {'chip_binding', 'clip_binding'}: _issue(issues, 'prediction_not_measured_binding', rid)
    if claim == 'regulation' and (mode != 'perturbation' or row.get('target_specificity_reviewed') is not True or row.get('matched_controls_reviewed') is not True):
        _issue(issues, 'regulation_requires_specific_perturbation_and_controls', rid)
    if claim == 'translation_efficiency' and (mode != 'ribosome_occupancy' or row.get('paired_rna_reviewed') is not True or row.get('interaction_model_reviewed') is not True):
        _issue(issues, 'occupancy_not_translation_efficiency', rid)
    for key in ['regulator_id', 'target_id', 'feature_mapping_reviewed', 'background_qc_pass', 'replicate_qc_pass']:
        if key.endswith(('_reviewed', '_pass')):
            if row.get(key) is not True: _issue(issues, 'missing_or_failed_' + key, rid)
        elif not row.get(key): _issue(issues, 'missing_' + key, rid)
    if row.get('direction') not in {'positive', 'negative', 'unsigned'}: _issue(issues, 'missing_regulatory_direction', rid)
    if row.get('direction') != 'unsigned' and mode != 'perturbation': _issue(issues, 'binding_or_prediction_not_regulatory_sign', rid)
    return ceilings.get(mode, 'unknown')


def audit_regulatory_links(records: list, context: dict) -> dict:
    """Audit returned chromatin/RNA-binding/translation links; motif, proximity and occupancy retain their evidence boundaries."""
    _context(context, True); _rows(records); issues = []; decisions = []
    for row in records:
        before = len(issues); _common(row, context, issues, True); ceiling = _regulatory(row, issues)
        decisions.append({'id': row['id'], 'evidence_ceiling': ceiling, 'summary_consistent': len(issues) == before})
    return _finish('regulatory', {'records': records, 'context': context}, issues, decisions)


def audit_protein_annotations(records: list, context: dict) -> dict:
    """Check returned domain/GO/PTM annotations for isoform and residue binding, NOT qualifiers and experimental boundaries."""
    _context(context); _rows(records); issues = []; decisions = []
    for row in records:
        rid = row['id']; before = len(issues); _common(row, context, issues)
        kind = row.get('annotation_type')
        if kind not in {'domain', 'go', 'ptm', 'localization', 'function'}: _issue(issues, 'unknown_protein_annotation', rid)
        for key in ['protein_id', 'isoform_id', 'annotation_id', 'annotation_version']:
            if not row.get(key): _issue(issues, 'missing_' + key, rid)
        if not re.fullmatch('[a-f0-9]{64}', str(row.get('sequence_sha256', ''))): _issue(issues, 'missing_sequence_binding', rid)
        if row.get('residue_mapping_reviewed') is not True: _issue(issues, 'unreviewed_residue_mapping', rid)
        source = row.get('evidence_type')
        if source not in {'experimental', 'computational', 'homology', 'curated_inference'}: _issue(issues, 'unknown_annotation_evidence', rid)
        if row.get('claims_experimental_validation') is True and source != 'experimental': _issue(issues, 'annotation_not_experimental_validation', rid)
        qualifiers = row.get('qualifiers', [])
        if not isinstance(qualifiers, list) or any(not isinstance(q, str) for q in qualifiers): raise ValueError('Annotation qualifiers must be strings')
        if any(q.upper() == 'NOT' for q in qualifiers) and row.get('positive_claim') is True: _issue(issues, 'negated_annotation_not_positive_support', rid)
        if kind == 'go':
            code = row.get('evidence_code')
            if not code: _issue(issues, 'missing_go_evidence_code', rid)
            if code in {'IEA', 'ISS', 'ISO', 'ISA', 'ISM', 'IBA', 'IBD', 'IKR', 'IRD', 'RCA', 'IC', 'TAS', 'NAS', 'ND'} and row.get('claims_experimental_validation') is True:
                _issue(issues, 'go_code_not_direct_experimental_validation', rid)
        if kind in {'domain', 'ptm'}:
            if any(row.get(k) is None for k in ['start', 'end', 'protein_length']): _issue(issues, 'missing_residue_coordinates', rid)
            else:
                if any(type(row[k]) is not int for k in ['start', 'end', 'protein_length']): raise ValueError('Integer residue coordinates required')
                if not 1 <= row['start'] <= row['end'] <= row['protein_length']: _issue(issues, 'residue_outside_sequence', rid)
        if kind == 'ptm':
            if row.get('site_probability') is None or row.get('declared_min_site_probability') is None: _issue(issues, 'missing_ptm_localization_criterion', rid)
            elif _number(row['site_probability'], 0, 1) < _number(row['declared_min_site_probability'], 0, 1): _issue(issues, 'ambiguous_ptm_site', rid)
            if row.get('claims_functional_effect') is True and row.get('functional_effect_reviewed') is not True: _issue(issues, 'ptm_detection_not_functional_effect', rid)
        decisions.append({'id': rid, 'evidence_type': source, 'summary_consistent': len(issues) == before})
    return _finish('protein_annotations', {'records': records, 'context': context}, issues, decisions)


def _interaction(row, issues):
    rid = row['id']; mode = row.get('evidence_type'); claim = row.get('claim')
    modes = {'coexpression', 'prediction', 'functional_association', 'physical_association', 'direct_binding', 'complex_membership'}
    if mode not in modes: _issue(issues, 'unknown_interaction_evidence', rid)
    if claim not in {'candidate', 'functional_association', 'physical_association', 'direct_binding'}: _issue(issues, 'unknown_interaction_claim', rid)
    if claim == 'direct_binding' and (mode != 'direct_binding' or row.get('pairwise_assay_reviewed') is not True or row.get('expansion') != 'none'):
        _issue(issues, 'association_or_complex_not_direct_binding', rid)
    if claim == 'physical_association' and mode not in {'physical_association', 'direct_binding'}:
        _issue(issues, 'functional_or_predicted_not_physical', rid)
    if claim == 'functional_association' and mode not in {'functional_association', 'coexpression'}:
        _issue(issues, 'physical_or_predicted_not_functional_effect', rid)
    if row.get('negative') is not False: _issue(issues, 'negative_or_unknown_not_positive_support', rid)
    if row.get('direction') != 'unsigned': _issue(issues, 'interaction_not_regulatory_direction', rid)
    for key in ['participant_a', 'participant_b']:
        if not row.get(key): _issue(issues, 'missing_' + key, rid)
    if row.get('participant_mapping_reviewed') is not True: _issue(issues, 'unreviewed_participant_mapping', rid)
    if row.get('assay_controls_reviewed') is not True: _issue(issues, 'unreviewed_assay_controls', rid)
    return mode if mode in modes else 'unknown'


def audit_interaction_records(records: list, context: dict) -> dict:
    """Audit physical/functional/complex/predicted interaction summaries without converting them into binding or regulation."""
    _context(context); _rows(records); issues = []; decisions = []
    for row in records:
        before = len(issues); _common(row, context, issues); ceiling = _interaction(row, issues)
        decisions.append({'id': row['id'], 'evidence_ceiling': ceiling, 'summary_consistent': len(issues) == before})
    return _finish('interaction', {'records': records, 'context': context}, issues, decisions)


def _perturbation(row, issues):
    rid = row['id']
    for key in ['target_id', 'endpoint', 'method_version']:
        if not row.get(key): _issue(issues, 'missing_' + key, rid)
    for key in ['design_qc_pass', 'matched_controls_reviewed', 'target_specificity_reviewed', 'confounding_reviewed', 'tested_universe_recorded']:
        if row.get(key) is not True: _issue(issues, 'missing_or_failed_' + key, rid)
    for key in ['effect', 'ci_low', 'ci_high', 'adjusted_pvalue']:
        if row.get(key) is None: _issue(issues, 'missing_' + key, rid)
        else: _number(row[key], 0 if key == 'adjusted_pvalue' else None, 1 if key == 'adjusted_pvalue' else None)
    if all(row.get(k) is not None for k in ['effect', 'ci_low', 'ci_high']) and not row['ci_low'] <= row['effect'] <= row['ci_high']:
        _issue(issues, 'inconsistent_effect_interval', rid)
    if not row.get('effect_unit') or not row.get('ci_method'): _issue(issues, 'missing_uncertainty_scale_or_method', rid)
    if row.get('direction') not in {'positive', 'negative', 'null'}: _issue(issues, 'unknown_perturbation_direction', rid)
    if row.get('effect') is not None:
        actual = 'positive' if row['effect'] > 0 else 'negative' if row['effect'] < 0 else 'null'
        if row.get('direction') != actual: _issue(issues, 'effect_direction_mismatch', rid)
    units = row.get('independent_units', [])
    if isinstance(units, list) and len(set(str(u) for u in units)) < 2: _issue(issues, 'insufficient_independent_units_for_inference', rid)
    if row.get('claims_general_causality') is True: _issue(issues, 'context_specific_effect_not_general_causality', rid)
    if row.get('claims_rescue') is True and row.get('rescue_specificity_reviewed') is not True: _issue(issues, 'unreviewed_rescue_specificity', rid)


def audit_perturbation_results(records: list, context: dict) -> dict:
    """Review returned molecular-screen/perturbation effects for independent units, specificity, controls and uncertainty; design no reagents."""
    _context(context); _rows(records); issues = []; decisions = []
    for row in records:
        before = len(issues); _common(row, context, issues); _perturbation(row, issues)
        decisions.append({'id': row['id'], 'evidence_ceiling': 'context_specific_effect', 'summary_consistent': len(issues) == before})
    return _finish('perturbation', {'records': records, 'context': context}, issues, decisions)


def audit_mechanism_graph(nodes: list, edges: list, evidence_records: list, context: dict) -> dict:
    """Audit a declared molecular mechanism graph against located, typed evidence, context and conflicting signs; prove no causal mechanism."""
    _context(context); _rows(nodes); _rows(edges); _rows(evidence_records)
    node_ids = {n['id'] for n in nodes}; sources = {r['id']: r for r in evidence_records}; issues = []; decisions = []; signs = defaultdict(set)
    for node in nodes:
        if not node.get('identifier') or node.get('species') != context['species'] or node.get('mapping_reviewed') is not True:
            _issue(issues, 'unresolved_node_identity', node['id'])
    for edge in edges:
        rid = edge['id']; before = len(issues); kind = edge.get('claim'); direction = edge.get('direction')
        if edge.get('source') not in node_ids or edge.get('target') not in node_ids: _issue(issues, 'unknown_graph_node', rid)
        if kind not in {'candidate', 'association', 'binding', 'regulation', 'context_specific_effect'}: _issue(issues, 'unknown_mechanism_claim', rid)
        if direction not in {'positive', 'negative', 'unsigned', 'null'}: _issue(issues, 'unknown_edge_direction', rid)
        if direction in {'positive', 'negative'}: signs[(edge.get('source'), edge.get('target'), kind)].add(direction)
        ids = edge.get('evidence_ids')
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
            _issue(issues, 'missing_or_duplicate_edge_evidence', rid); ids = []
        supported = False
        for eid in ids:
            row = sources.get(eid)
            if row is None: _issue(issues, 'unknown_evidence_id', rid); continue
            local = []; _common(row, context, local, row.get('kind') == 'regulatory')
            mode = row.get('kind')
            if mode == 'interaction':
                ceiling = _interaction(row, local)
                fits = kind in {'candidate', 'association'} or kind == 'binding' and ceiling == 'direct_binding'
                if direction != 'unsigned': fits = False
                participants = {row.get('participant_a'), row.get('participant_b')}
                mapped = {next((n.get('identifier') for n in nodes if n['id'] == edge.get(k)), None) for k in ['source', 'target']}
                if participants != mapped: _issue(local, 'edge_participant_mismatch', rid)
            elif mode == 'regulatory':
                ceiling = _regulatory(row, local)
                fits = kind == 'candidate' or kind == 'association' and row.get('claim') == 'association' or kind == 'binding' and row.get('claim') == 'binding' or kind == 'regulation' and row.get('claim') == 'regulation'
                if row.get('regulator_id') != next((n.get('identifier') for n in nodes if n['id'] == edge.get('source')), None) or row.get('target_id') != next((n.get('identifier') for n in nodes if n['id'] == edge.get('target')), None):
                    _issue(local, 'edge_regulatory_target_mismatch', rid)
                if direction != row.get('direction'): fits = False
            elif mode == 'perturbation':
                _perturbation(row, local); ceiling = 'context_specific_effect'
                fits = kind in {'candidate', 'context_specific_effect'} and direction == row.get('direction')
                if row.get('target_id') != next((n.get('identifier') for n in nodes if n['id'] == edge.get('source')), None) or row.get('endpoint') != next((n.get('identifier') for n in nodes if n['id'] == edge.get('target')), None):
                    _issue(local, 'edge_perturbation_endpoint_mismatch', rid)
            else:
                _issue(local, 'unknown_evidence_kind', eid); fits = False; ceiling = 'unknown'
            issues.extend(local)
            if not local and fits: supported = True
        if not supported: _issue(issues, 'no_consistent_evidence_for_claim', rid)
        if edge.get('claims_transitive_causality') is True: _issue(issues, 'edge_chain_not_transitive_causality', rid)
        decisions.append({'id': rid, 'declared_claim': kind, 'summary_consistent': len(issues) == before,
                          'scientific_support_established': False})
    for key, values in signs.items():
        if len(values) > 1: _issue(issues, 'conflicting_edge_directions', list(key))
    used = set()
    for edge in edges:
        ids = edge.get('evidence_ids')
        if isinstance(ids, list): used.update(eid for eid in ids if isinstance(eid, str))
    return _finish('mechanism', {'nodes': nodes, 'edges': edges, 'evidence_records': evidence_records, 'context': context}, issues, decisions,
                   graph={'nodes': nodes, 'edges': edges}, unused_evidence_ids=sorted(set(sources) - used))
