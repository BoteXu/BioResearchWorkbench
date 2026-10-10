"""Original offline omics contracts and bounded summary checks; never launch scientific engines."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re


def _digest(value):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf8')
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError('Finite bounded JSON is required') from exc
    if len(raw) > 400_000:
        raise ValueError('Select metadata and small server summaries, at most 400 KB')
    return hashlib.sha256(raw).hexdigest()


def _text(value, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Nonempty bounded text required')
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Exact lowercase SHA256 required')
    return value


def _rows(value, maximum=1000, nonempty=True):
    _digest(value)
    if not isinstance(value, list) or len(value) > maximum or nonempty and not value or any(not isinstance(v, dict) for v in value):
        raise ValueError('Provide a bounded list of objects')
    ids = [_text(v.get('id'), 100) for v in value]
    if len(set(ids)) != len(ids):
        raise ValueError('Object IDs must be unique')
    return value


def _catalog():
    local = Path(__file__).with_name('omics_workflows.json')
    path = local if local.is_file() else Path(__file__).resolve().parents[1] / 'omics_workflows.json'
    raw = path.read_bytes()
    if len(raw) > 300_000:
        raise ValueError('Workflow catalog exceeds static bound')
    value = json.loads(raw)
    if value.get('schema') != 1:
        raise ValueError('Unsupported catalog schema')
    ids = [w['id'] for w in value['workflows']]
    if len(ids) != len(set(ids)):
        raise ValueError('Workflow catalog contains duplicate IDs')
    for w in value['workflows']:
        if any(e not in value['extensions'] for e in w['extensions']) or any(r not in value['references'] for r in w['reference_ids']):
            raise ValueError('Unresolved workflow reference')
    return value, hashlib.sha256(raw).hexdigest()


def _selected(workflow):
    catalog, digest = _catalog()
    matches = [w for w in catalog['workflows'] if w['id'] == workflow]
    if not matches:
        raise ValueError('Choose an exact workflow ID from inspect_omics_workflows')
    return catalog, digest, deepcopy(matches[0])


def _issue(issues, code, scope, severity='block'):
    issues.append({'code': code, 'scope': scope, 'severity': severity})


def _finish(kind, inputs, issues, **extra):
    return {'audit': kind, 'input_sha256': _digest(inputs), 'issues': issues,
            'summary_consistent': not any(i['severity'] == 'block' for i in issues),
            'execution_state': 'offline_summary_review_only', 'analysis_started': False,
            'analysis_authorized': False, 'automatic_submission': False, 'automatic_retry': False,
            'scientific_validity_established': False, 'caller_assertions_independently_verified': False,
            'public_queries_performed': False, **extra}


def inspect_omics_workflows(workflow: str = '', family: str = '', detail: bool = False, limit: int = 40) -> dict:
    """Discover 28 original standard/extension workflow contracts, QC, result roles and server-only candidates offline."""
    if type(detail) is not bool or type(limit) is not int or not 1 <= limit <= 40:
        raise ValueError('detail must be boolean and limit an integer from 1 to 40')
    catalog, digest = _catalog()
    if workflow and workflow not in {w['id'] for w in catalog['workflows']}:
        raise ValueError('Unknown workflow ID')
    if family and family not in {w['family'] for w in catalog['workflows']}:
        raise ValueError('Unknown family')
    selected = [w for w in catalog['workflows'] if (not workflow or w['id'] == workflow) and (not family or w['family'] == family)]
    keys = ('id', 'family', 'title', 'input_description', 'input_kinds', 'extensions', 'backend_status')
    result = deepcopy(selected[:limit]) if detail else [{k: w[k] for k in keys} for w in selected[:limit]]
    refs = {key: catalog['references'][key] for w in selected[:limit] for key in w['reference_ids']}
    return {'catalog_version': catalog['catalog_version'], 'catalog_sha256': digest,
            'total_workflows': len(catalog['workflows']), 'matched': len(selected), 'returned': len(result),
            'families': sorted({w['family'] for w in catalog['workflows']}), 'workflows': result,
            'extensions': deepcopy(catalog['extensions']) if detail else list(catalog['extensions']),
            'references': refs, 'execution_state': 'catalog_only', 'new_executors': False,
            'public_queries_performed': False, 'local_scientific_execution': False}


def plan_omics_workflow(workflow: str, context: dict, design: dict, input_manifest: list, extensions: list = None) -> dict:
    """Prepare an exact version-bound server workflow with modality QC and explicitly selected conditional extensions; never submit."""
    _digest([context, design, input_manifest, extensions])
    catalog, catalog_hash, profile = _selected(workflow)
    if not isinstance(context, dict) or not isinstance(design, dict):
        raise ValueError('Explicit context and design objects required')
    for key in profile['required_context_fields']:
        _text(context.get(key))
    for key in ('estimand', 'biological_unit', 'contrast', 'missingness_plan'):
        _text(design.get(key))
    if design.get('unit_type') not in {'donor', 'animal', 'independent_culture', 'biological_sample', 'pedigree', 'study'}:
        raise ValueError('Declare biological units; cells, spots, reads and technical repeats are not independent by default')
    if design.get('inference_mode') not in {'inferential', 'descriptive'}:
        raise ValueError('Choose inferential or descriptive')
    if type(design.get('batch_confounded')) is not bool or type(design.get('repeated_measures')) is not bool:
        raise ValueError('Explicit batch confounding and repeated-measure flags required')
    if not isinstance(design.get('covariates'), list) or len(design['covariates']) > 30:
        raise ValueError('Declare the bounded covariate list, including an explicit empty list')
    for c in design['covariates']:
        _text(c, 100)
    units = _rows(design.get('units'), 1000)
    for row in units:
        _text(row.get('group'), 100)
    inputs = _rows(input_manifest, 100)
    for row in inputs:
        _text(row.get('kind'), 100); _hash(row.get('sha256')); _text(row.get('source_location'))
    requested = [] if extensions is None else extensions
    if not isinstance(requested, list) or len(requested) > 12 or any(not isinstance(v, str) for v in requested) or len(set(requested)) != len(requested):
        raise ValueError('Select at most 12 distinct extension IDs')
    if any(v not in profile['extensions'] for v in requested):
        raise ValueError('Selected extension is incompatible with this workflow')
    capabilities = design.get('capabilities', {})
    if not isinstance(capabilities, dict) or len(capabilities) > 100:
        raise ValueError('Provide bounded evidence-backed capabilities')
    issues = []
    if any(row['kind'] not in profile['input_kinds'] for row in inputs):
        _issue(issues, 'incompatible_input_scale_or_kind', 'input_manifest')
    if design['inference_mode'] == 'inferential' and design['batch_confounded']:
        _issue(issues, 'batch_and_target_completely_confounded', 'design')
    counts = Counter(row['group'] for row in units)
    # This is a minimum structural guard, never a power/sample-size acceptance criterion.
    if design['inference_mode'] == 'inferential' and min(counts.values()) < 2:
        _issue(issues, 'insufficient_declared_independent_replication', 'design')
    if design['repeated_measures'] and not design.get('dependence_structure'):
        _issue(issues, 'missing_repeated_measure_structure', 'design')
    if design.get('inference_mode') == 'descriptive' and requested:
        _issue(issues, 'descriptive_extension_requires_inferential_plan', 'design')
    extension_routes = []
    for name in requested:
        route = deepcopy(catalog['extensions'][name]); missing = []
        for prerequisite in route['prerequisites']:
            row = capabilities.get(prerequisite)
            if not isinstance(row, dict) or row.get('available') is not True or not isinstance(row.get('source_location'), str) or not row['source_location'].strip() or len(row['source_location']) > 500 or not re.fullmatch('[a-f0-9]{64}', str(row.get('source_sha256', ''))):
                missing.append(prerequisite)
                _issue(issues, 'missing_extension_prerequisite', name + ':' + prerequisite)
        route['missing_prerequisites'] = missing
        route['state'] = 'blocked' if missing else 'requires_host_review_and_server_acceptance'
        extension_routes.append(route)
    required_qc = deepcopy(catalog['common_qc'] + profile['qc_gates'])
    required_qc += [{'id': 'extension__' + name, 'description': 'Selected extension assumptions, prerequisites and diagnostics'} for name in requested]
    roles = list(dict.fromkeys(catalog['common_result_roles'] + profile['result_roles'] + [role for r in extension_routes for role in r['result_roles']]))
    if design['inference_mode'] == 'descriptive':
        roles = [r for r in roles if r not in {'differential', 'differential_regions', 'association', 'multiple_testing'}]
        roles.append('descriptive_results')
    binding = {'catalog_sha256': catalog_hash, 'context_sha256': _digest(context), 'design_sha256': _digest(design), 'inputs_sha256': _digest(inputs)}
    body = {'schema': 1, 'catalog_version': catalog['catalog_version'], 'workflow': workflow,
            'context': context, 'design': design, 'input_manifest': inputs, 'requested_extensions': requested,
            'binding': binding, 'profile': profile, 'required_qc': required_qc, 'result_roles': roles,
            'extension_routes': extension_routes, 'issues': issues,
            'required_consultation': 'statistics.guide_study_statistics before inferential analysis',
            'server_routes': ['server_operations.plan_server_budget', 'code_execution.prepare_code_execution',
                              'workflow.prepare_remote_task', 'workflow.inspect_remote_task', 'workflow.verify_remote_results'],
            'execution_state': 'plan_only', 'analysis_started': False, 'automatic_submission': False,
            'local_scientific_execution': False, 'scientific_validity_established': False,
            'public_queries_performed': False}
    return {**deepcopy(body), 'plan_sha256': _digest(body),
            'plan_contract_consistent': not any(i['severity'] == 'block' for i in issues)}


def _validate_plan(plan):
    _digest(plan)
    if not isinstance(plan, dict) or plan.get('schema') != 1:
        raise ValueError('Provide the complete generated plan')
    rebuilt = plan_omics_workflow(plan.get('workflow'), plan.get('context'), plan.get('design'), plan.get('input_manifest'), plan.get('requested_extensions'))
    if plan != rebuilt:
        raise ValueError('Plan changed or catalog is stale; prepare and review a new plan')
    return rebuilt


def _source(row):
    return (isinstance(row.get('source_location'), str) and bool(row['source_location'].strip())
            and len(row['source_location']) <= 500 and bool(re.fullmatch('[a-f0-9]{64}', str(row.get('source_sha256', ''))))
            and row.get('reviewed_by_host') is True)


def _binding(row, plan):
    return row.get('plan_sha256') == plan['plan_sha256'] and all(row.get(k) == v for k, v in plan['binding'].items())


def _measurements(rows, scope, issues):
    if rows is None:
        return
    _rows(rows, 50, nonempty=False)
    for row in rows:
        for k in ('definition', 'unit', 'threshold_basis', 'observation_scope'):
            _text(row.get(k))
        value = row.get('value'); bound = row.get('bound'); op = row.get('operator')
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError('QC observed value must be finite numeric, never boolean or a numeric string')
        if op not in {'ge', 'le', 'between'}:
            raise ValueError('QC predicate must be ge, le or between')
        bounds = bound if op == 'between' else [bound]
        if not isinstance(bounds, list) or len(bounds) != (2 if op == 'between' else 1) or any(type(b) not in (int, float) or not math.isfinite(b) for b in bounds):
            raise ValueError('Finite QC threshold bounds required')
        if op == 'between' and bounds[0] > bounds[1]:
            raise ValueError('QC interval is reversed')
        passed = value >= bounds[0] if op == 'ge' else value <= bounds[0] if op == 'le' else bounds[0] <= value <= bounds[1]
        if not passed:
            _issue(issues, 'observed_qc_outside_declared_threshold', scope + ':' + row['id'])


def audit_omics_readiness(plan: dict, checks: list, statistical_receipt: dict = None, backend_receipt: dict = None) -> dict:
    """Audit plan-bound modality QC, explicit threshold units, statistical consultation and existing server acceptance declarations offline."""
    current = _validate_plan(plan); _rows(checks, 100, nonempty=False)
    _digest([statistical_receipt, backend_receipt])
    issues = deepcopy(current['issues']); required = {v['id'] for v in current['required_qc']}
    supplied = {row['id']: row for row in checks}
    for key in sorted(required - set(supplied)):
        _issue(issues, 'missing_required_qc', key)
    for key, row in supplied.items():
        if key not in required:
            _issue(issues, 'unexpected_qc_scope', key)
        if not _binding(row, current):
            _issue(issues, 'qc_binding_mismatch', key)
        if row.get('status') not in {'passed', 'failed', 'unknown'}:
            raise ValueError('Required QC status must be passed, failed or unknown; no silent not-applicable bypass')
        if row['status'] != 'passed':
            _issue(issues, 'qc_failed_or_unknown', key)
        if not _source(row):
            _issue(issues, 'qc_source_unreviewed_or_unlocated', key)
        _measurements(row.get('measurements'), key, issues)
    if current['design']['inference_mode'] == 'inferential':
        row = statistical_receipt or {}
        if not isinstance(row, dict):
            raise ValueError('Statistical receipt must be an object')
        if not _binding(row, current) or not _source(row) or row.get('status') != 'reviewed':
            _issue(issues, 'missing_bound_statistical_consultation', 'statistics')
        if row.get('estimand') != current['design']['estimand'] or row.get('biological_unit') != current['design']['biological_unit']:
            _issue(issues, 'statistical_estimand_or_unit_mismatch', 'statistics')
    backend = backend_receipt or {}
    if not isinstance(backend, dict):
        raise ValueError('Backend receipt must be an object')
    if not _binding(backend, current) or not _source(backend) or backend.get('status') != 'runtime_verified' or backend.get('route') != 'existing_server':
        _issue(issues, 'existing_server_backend_unverified', 'backend')
    versions = backend.get('method_versions')
    if not isinstance(versions, dict) or not versions or len(versions) > 100 or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() or v.strip().lower() in {'latest', 'dev', 'main', 'master', 'unknown'} for k, v in versions.items()):
        _issue(issues, 'missing_exact_method_versions', 'backend')
    return _finish('omics_readiness', [plan, checks, statistical_receipt, backend_receipt], issues,
                   plan_sha256=current['plan_sha256'], required_qc_count=len(required),
                   next_action='host_review_then_explicit_server_dispatch' if not any(i['severity'] == 'block' for i in issues) else 'resolve_qc_and_design_blockers',
                   limits=['Only supplied summaries are inspected. Source review and runtime declarations need independent real receipts.',
                           'Two units per declared group is a structural minimum, not statistical power acceptance.',
                           'QC numeric thresholds are task-defined with explicit units, definitions and scope; no universal cutoff is supplied.'])


def audit_omics_result_bundle(plan: dict, result_manifest: list, execution_receipt: dict, checks: list, statistical_receipt: dict = None, backend_receipt: dict = None) -> dict:
    """Audit required standard/extension output roles, exact provenance and declared server completion; read no raw data and retry nothing."""
    current = _validate_plan(plan); _rows(result_manifest, 200, nonempty=False)
    readiness = audit_omics_readiness(current, checks, statistical_receipt, backend_receipt)
    _digest(execution_receipt)
    if not isinstance(execution_receipt, dict):
        raise ValueError('Execution receipt object required')
    issues = deepcopy(readiness['issues']); roles = set(); required = set(current['result_roles'])
    for row in result_manifest:
        _text(row.get('role'), 100); _hash(row.get('sha256')); _text(row.get('source_location'))
        if type(row.get('bytes')) is not int or row['bytes'] <= 0:
            _issue(issues, 'empty_or_invalid_result_size', row['id'])
        if row['role'] in roles:
            _issue(issues, 'duplicate_result_role', row['role'])
        roles.add(row['role'])
        if row['role'] not in required:
            _issue(issues, 'extra_result_requires_review', row['role'], 'review')
        if not _binding(row, current):
            _issue(issues, 'result_provenance_mismatch', row['id'])
    for role in sorted(required - roles):
        _issue(issues, 'missing_required_result', role)
    if not _binding(execution_receipt, current) or not _source(execution_receipt):
        _issue(issues, 'execution_receipt_unbound_or_unreviewed', 'execution')
    if execution_receipt.get('state') != 'COMPLETED' or type(execution_receipt.get('exit_code')) is not int or execution_receipt['exit_code'] != 0:
        _issue(issues, 'server_completion_not_established', 'execution')
    if not execution_receipt.get('scheduler_receipt_id') or not execution_receipt.get('runner_receipt_id'):
        _issue(issues, 'missing_scheduler_or_runner_receipt', 'execution')
    return _finish('omics_result_bundle', [plan, result_manifest, execution_receipt, checks, statistical_receipt, backend_receipt], issues,
                   plan_sha256=current['plan_sha256'], required_roles=sorted(required),
                   missing_roles=sorted(required - roles), returned_roles=sorted(roles),
                   local_file_hashes_verified=False, actual_server_process_observed=False,
                   next_action='independently_verify_selected_files_and_interpret' if not any(i['severity'] == 'block' for i in issues) else 'inspect_original_receipts_and_resolve_missing_results',
                   limits=['Manifest hashes and server status are caller declarations; independently inspect actual receipts and selected returned files.',
                           'An intact bundle and consistent summaries do not establish scientific validity.'])
