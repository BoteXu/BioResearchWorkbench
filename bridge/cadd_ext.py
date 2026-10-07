"""Original bounded CADD planning and result audits. No engine execution or network."""
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from statistics import mean, stdev
from academic_common import artifact, text


def _bounded(value):
    try:
        raw = json.dumps(value, allow_nan=False, ensure_ascii=False).encode('utf8')
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError('Provide finite JSON input') from exc
    if len(raw) > 2_000_000:
        raise ValueError('Summary exceeds local budget; aggregate on the server')
    return hashlib.sha256(raw).hexdigest()


def _rows(value, limit=1000, allow_empty=False):
    _bounded(value)
    if not isinstance(value, list) or not (0 if allow_empty else 1) <= len(value) <= limit or any(not isinstance(x, dict) for x in value):
        raise ValueError('Provide a nonempty bounded list of objects')
    return value


def _num(value, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Finite numeric value required; no booleans or numeric strings')
    if low is not None and value < low or high is not None and value > high:
        raise ValueError('Numeric value outside declared range')
    return value


def _integer(value, low=0, high=10**12):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Bounded integer required')
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Lowercase SHA256 required')
    return value


def _context(context):
    _bounded(context)
    if not isinstance(context, dict):
        raise ValueError('Explicit scientific context required')
    for key in ['species', 'system', 'purpose', 'source_version']:
        text(context.get(key), 1000)
    return context


def _issue(issues, code, scope, severity='block'):
    issues.append({'code': code, 'scope': scope, 'severity': severity})


def _result(kind, inputs, issues, **data):
    _bounded(inputs)
    return artifact('cadd_' + kind, {
        'audit': kind, 'input_sha256': _bounded(inputs), 'issues': issues,
        'qc_gate_pass': not any(x['severity'] == 'block' for x in issues),
        'scientific_validity': 'not_established', 'execution_state': 'summary_audit_only',
        **data,
    })


ROUTES = {
    'small_molecule_docking': {'software': ['Vina', 'UniDock / UniDock-Pro'], 'audits': ['molecular.audit_docking_inputs', 'cadd.audit_docking_campaign'], 'decisions': ['prepared chemical states', 'explicit site and score domain', 'reference and counter-screen controls']},
    'macromolecular_docking': {'software': ['HDOCK', 'HADDOCK'], 'audits': ['biomedical.audit_structure_context', 'cadd.audit_restraint_mapping', 'cadd.audit_docking_campaign'], 'decisions': ['chain and numbering mapping', 'restraint provenance', 'cluster and pose review']},
    'md': {'software': ['GROMACS', 'Amber / AmberTools'], 'audits': ['cadd.audit_simulation_protocol', 'cadd.audit_restart_manifest', 'advanced.audit_md_summary'], 'decisions': ['parameterization and solvent compatibility', 'staged equilibration', 'independent starts and convergence observables']},
    'tremd': {'software': ['GROMACS', 'Amber'], 'audits': ['cadd.audit_simulation_protocol', 'cadd.audit_replica_exchange'], 'decisions': ['temperature ladder', 'exchange pilot', 'state versus walker trajectory demultiplexing']},
    'rest2': {'software': ['GROMACS / PLUMED'], 'audits': ['cadd.audit_simulation_protocol', 'cadd.audit_replica_exchange'], 'decisions': ['selected hot region', 'reviewed Hamiltonian scaling', 'exact backend capability and pilot receipts']},
    'af3_review': {'software': ['existing AF3 outputs', 'optional af-analysis on server'], 'audits': ['cadd.audit_af3_records', 'biomedical.audit_structure_context'], 'decisions': ['exact sample/source binding', 'declared chain order and selected interface', 'geometric review separate from confidence']},
    'endpoint_energy': {'software': ['AmberTools MMPBSA.py', 'existing validated server backend'], 'audits': ['cadd.audit_mmgbsa_summary'], 'decisions': ['frame selection and equilibration removal', 'topology and protocol alignment', 'entropy and autocorrelation limits']},
}


def guide_cadd_workflow(task: str, context: dict) -> dict:
    """Choose a CADD audit route without installing, executing, or uploading anything."""
    _context(context)
    if task not in ROUTES:
        raise ValueError('Select an explicit supported CADD task')
    return _result('workflow', {'task': task, 'context': context}, [], task=task, route=ROUTES[task],
                   compute_placement='server', next_action='Review inputs and QC, then use the existing shared-SSH task workflow',
                   limitations=['A software name is not an installed or validated engine.', 'No target-specific design or simulation is launched.'])


def audit_simulation_protocol(protocol: dict, context: dict) -> dict:
    """Audit declared MD/tREMD/REST2 units, stages and capabilities; no force-field validation."""
    _context(context); _bounded(protocol)
    if not isinstance(protocol, dict) or protocol.get('engine') not in {'gromacs', 'amber'} or protocol.get('mode') not in {'md', 'tremd', 'rest2'}:
        raise ValueError('Declare engine gromacs/amber and mode md/tremd/rest2')
    issues = []
    for key in ['engine_version', 'force_field', 'solvent_model', 'parameterization_source', 'protonation_basis', 'equilibration_acceptance', 'convergence_observables', 'resource_budget']:
        if not isinstance(protocol.get(key), str) or not protocol[key].strip():
            _issue(issues, 'missing_' + key, 'protocol')
    for key in ['system_sha256', 'topology_sha256']:
        _hash(protocol.get(key))
    if protocol.get('duration_unit') != 'ps' or protocol.get('timestep_unit') != 'ps' or protocol.get('temperature_unit') != 'K':
        raise ValueError('Declare duration/timestep in ps and temperature in K')
    _num(protocol.get('temperature_K'), 1, 2000)
    stages = _rows(protocol.get('stages'), 20)
    names = [text(s.get('name'), 60) for s in stages]
    if len(set(names)) != len(names):
        raise ValueError('Stage names must be unique')
    if 'minimization' not in names or 'equilibration' not in names or 'production' not in names:
        _issue(issues, 'missing_required_stage', 'protocol')
    elif not names.index('minimization') < names.index('equilibration') < names.index('production'):
        _issue(issues, 'stage_order', 'protocol')
    times = []
    for stage in stages:
        steps = _integer(stage.get('steps'), 1)
        if stage['name'] == 'minimization':
            times.append({'name': stage['name'], 'steps': steps, 'duration_ps': None})
            continue
        dt = _num(stage.get('dt_ps'), 0.000001, 0.01)
        duration = steps * dt
        declared = _num(stage.get('duration_ps'), 0)
        if not math.isclose(duration, declared, rel_tol=1e-9, abs_tol=1e-8):
            _issue(issues, 'duration_steps_mismatch', stage['name'])
        if dt > 0.002 and protocol.get('large_timestep_validated') is not True:
            _issue(issues, 'large_timestep_requires_validation', stage['name'])
        times.append({'name': stage['name'], 'steps': steps, 'duration_ps': duration, 'dt_ps': dt})
    if _integer(protocol.get('independent_starts'), 1, 100) < 2:
        _issue(issues, 'single_start_limits_reproducibility', 'protocol', 'review')
    mode = protocol['mode']
    if mode in {'tremd', 'rest2'}:
        temperatures = protocol.get('temperatures_K')
        if not isinstance(temperatures, list) or not 2 <= len(temperatures) <= 128:
            raise ValueError('Provide 2..128 explicit temperatures')
        [_num(t, 1, 2000) for t in temperatures]
        if any(a >= b for a, b in zip(temperatures, temperatures[1:])):
            _issue(issues, 'temperature_ladder_not_increasing', 'protocol')
        ranks = _integer(protocol.get('mpi_ranks'), 1, 100000)
        if ranks < len(temperatures) or ranks % len(temperatures):
            _issue(issues, 'insufficient_replica_resources', 'protocol')
        if protocol.get('pilot_receipt_verified') is not True:
            _issue(issues, 'exchange_pilot_required', 'protocol')
        _integer(protocol.get('exchange_interval_steps'), 1)
    if mode == 'rest2':
        if protocol['engine'] != 'gromacs':
            _issue(issues, 'rest2_adapter_route_unsupported', 'protocol')
        for key in ['hot_region_reviewed', 'scaled_topologies_verified', 'hrex_verified', 'plumed_verified', 'capability_receipt_verified']:
            if protocol.get(key) is not True:
                _issue(issues, 'missing_' + key, 'protocol')
        ref = _num(protocol.get('reference_temperature_K'), 1, 2000)
        if not math.isclose(protocol['temperature_K'], ref):
            _issue(issues, 'protocol_reference_temperature_mismatch', 'protocol')
        thermostat = protocol.get('thermostat_temperatures_K')
        scales = protocol.get('scales')
        if not isinstance(thermostat, list) or not isinstance(scales, list) or len(thermostat) != len(temperatures) or len(scales) != len(temperatures):
            raise ValueError('REST2 thermostat and scaling vectors must match the ladder')
        if not math.isclose(temperatures[0], ref):
            _issue(issues, 'reference_temperature_mismatch', 'protocol')
        for i, (temp, scale, bath) in enumerate(zip(temperatures, scales, thermostat)):
            _num(scale, 0.000001, 1); _num(bath, 1, 2000)
            if not math.isclose(scale, ref/temp, rel_tol=1e-6) or not math.isclose(bath, ref, rel_tol=1e-6):
                _issue(issues, 'rest2_scaling_or_thermostat_mismatch', str(i))
    return _result('protocol', {'protocol': protocol, 'context': context}, issues, stages=times,
                   limitations=['This checks declared metadata, not topology physics or actual capabilities.', 'Engine logs, Hamiltonian checks and convergence review remain required on the server.'])


def audit_restart_manifest(segments: list, context: dict) -> dict:
    """Check per-walker segment continuity and exact system/protocol/checkpoint lineage."""
    _context(context); _rows(segments)
    issues = []; groups = defaultdict(list); ids = set()
    bindings = ['system_sha256', 'topology_sha256', 'protocol_sha256']
    for row in segments:
        sid = text(row.get('id'), 100)
        if sid in ids:
            raise ValueError('Unique segment IDs required')
        ids.add(sid); groups[text(row.get('walker'), 100)].append(row)
        for key in bindings + ['output_checkpoint_sha256', 'receipt_sha256']:
            _hash(row.get(key))
        _integer(row.get('start_step')); _integer(row.get('end_step'), 1)
        if row['end_step'] <= row['start_step']:
            _issue(issues, 'invalid_step_interval', sid)
        _num(row.get('dt_ps'), 0.000001, 0.01)
        text(row.get('engine_version'), 100)
        if row.get('state') != 'completed' or type(row.get('exit_code')) is not int or row['exit_code'] != 0 or row.get('receipt_verified') is not True:
            _issue(issues, 'segment_not_verified_complete', sid)
    summaries = []
    for walker, group in groups.items():
        group.sort(key=lambda x: x['start_step'])
        first = group[0]
        if first['start_step'] != 0:
            _issue(issues, 'partial_chain_prefix', walker, 'review')
        for previous, current in zip(group, group[1:]):
            sid = current['id']
            if current['start_step'] != previous['end_step']:
                _issue(issues, 'gap_or_overlap', sid)
            if any(current[k] != previous[k] for k in bindings + ['dt_ps', 'engine_version']):
                _issue(issues, 'restart_compatibility_changed', sid)
            if _hash(current.get('input_checkpoint_sha256')) != previous['output_checkpoint_sha256']:
                _issue(issues, 'checkpoint_lineage_mismatch', sid)
        summaries.append({'walker': walker, 'segments': len(group), 'start_step': first['start_step'], 'end_step': group[-1]['end_step']})
    return _result('restart', {'segments': segments, 'context': context}, issues, walkers=summaries,
                   limitations=['Checkpoint bytes, append-file checksums and velocities must be verified by the engine.', 'Manifests and caller-declared receipt verification are not live scheduler observations.'])


def audit_replica_exchange(ladder: list, exchanges: list, visits: list, context: dict) -> dict:
    """Audit adjacent exchange counters and full walker permutations; no convergence claim."""
    _context(context); _bounded(ladder); _rows(exchanges, 256); _rows(visits, 1000)
    if not isinstance(ladder, list) or not 2 <= len(ladder) <= 128:
        raise ValueError('Explicit 2..128 state ladder required')
    [_num(t, 1, 2000) for t in ladder]
    if any(a >= b for a, b in zip(ladder, ladder[1:])):
        raise ValueError('State ladder must strictly increase')
    n = len(ladder); issues = []; edges = {}; rates = []
    for row in exchanges:
        a = _integer(row.get('state_a'), 0, n-1); b = _integer(row.get('state_b'), 0, n-1)
        if b != a+1 or (a, b) in edges:
            raise ValueError('One aggregated counter for each adjacent pair required')
        attempted = _integer(row.get('attempted')); accepted = _integer(row.get('accepted'), 0, attempted)
        edges[a, b] = accepted
        rate = accepted/attempted if attempted else None
        rates.append({'state_a': a, 'state_b': b, 'attempted': attempted, 'accepted': accepted, 'acceptance': rate})
        if accepted == 0:
            _issue(issues, 'unmixed_or_unobserved_edge', str(a))
    if set(edges) != {(i, i+1) for i in range(n-1)}:
        _issue(issues, 'missing_exchange_pair', 'ladder')
    ordered = sorted(visits, key=lambda x: _integer(x.get('step')))
    if len({x['step'] for x in ordered}) != len(ordered):
        raise ValueError('Unique visit steps required')
    observed = [set() for _ in ladder]; phase = [0 for _ in ladder]; trips = [0 for _ in ladder]
    for row in ordered:
        states = row.get('walker_states')
        if not isinstance(states, list) or len(states) != n or any(type(x) is not int for x in states) or set(states) != set(range(n)):
            raise ValueError('Each visit must be a complete state permutation indexed by walker')
        for walker, state in enumerate(states):
            observed[walker].add(state)
            if phase[walker] == 0 and state == 0: phase[walker] = 1
            elif phase[walker] == 1 and state == n-1: phase[walker] = 2
            elif phase[walker] == 2 and state == 0:
                trips[walker] += 1; phase[walker] = 1
    for i, states in enumerate(observed):
        if len(states) < n: _issue(issues, 'walker_missing_states', str(i), 'review')
        if trips[i] == 0: _issue(issues, 'no_observed_low_high_low_trip', str(i), 'review')
    return _result('exchange', {'ladder': ladder, 'exchanges': exchanges, 'visits': visits, 'context': context}, issues,
                   pair_counters=rates, walkers=[{'walker': i, 'visited_states': sorted(s), 'observed_low_high_low_round_trips': trips[i]} for i, s in enumerate(observed)],
                   limitations=['Visits are sampled observations; missed transitions cannot be reconstructed.', 'Exchange acceptance and round trips do not prove equilibrium, adequate sampling or biological replication.', 'State trajectories and continuous walker trajectories answer different questions.'])


def audit_docking_campaign(expected: list, results: list, score_domain: dict, context: dict) -> dict:
    """Retain failed/missing candidates and rank only one exact declared scoring domain."""
    _context(context); _rows(expected); _rows(results, allow_empty=True); _bounded(score_domain)
    if not isinstance(score_domain, dict) or score_domain.get('direction') not in {'lower', 'higher'}:
        raise ValueError('Explicit scoring domain and direction required')
    for key in ['engine', 'version', 'scoring', 'units', 'search_mode']:
        text(score_domain.get(key), 100)
    for key in ['receptor_sha256', 'preparation_sha256', 'site_sha256']:
        _hash(score_domain.get(key))
    exp = {}; issues = []; found = {}; eligible = []; exclusions = []
    for row in expected:
        sid = text(row.get('id'), 100)
        if sid in exp: raise ValueError('Unique expected state IDs required')
        if row.get('role') not in {'candidate', 'reference', 'negative_control'}:
            raise ValueError('Declare candidate/reference/negative_control roles')
        text(row.get('parent_id'), 100); _hash(row.get('ligand_sha256')); exp[sid] = row
    for row in results:
        sid = text(row.get('id'), 100)
        if sid in found: raise ValueError('Aggregate technical runs explicitly; duplicate result IDs refused')
        found[sid] = row
        if sid not in exp:
            _issue(issues, 'unexpected_result', sid); exclusions.append({'id': sid, 'reason': 'unexpected'}); continue
        reasons = []
        if row.get('state') != 'completed' or type(row.get('exit_code')) is not int or row['exit_code'] != 0: reasons.append('execution_failed_or_unknown')
        if row.get('ligand_sha256') != exp[sid]['ligand_sha256']: reasons.append('ligand_binding_mismatch')
        if row.get('score_domain') != score_domain: reasons.append('incomparable_score_domain')
        if row.get('pose_qc_pass') is not True: reasons.append('pose_qc_required')
        if not isinstance(row.get('pose_sha256'), str) or not re.fullmatch('[a-f0-9]{64}', row['pose_sha256']): reasons.append('pose_binding_required')
        value = row.get('score')
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value): reasons.append('missing_or_invalid_score')
        for reason in reasons: _issue(issues, reason, sid)
        if reasons: exclusions.append({'id': sid, 'reason': reasons})
        else: eligible.append({'id': sid, 'parent_id': exp[sid]['parent_id'], 'role': exp[sid]['role'], 'score': value, 'pose_sha256': row['pose_sha256']})
    for sid in exp.keys()-found.keys():
        _issue(issues, 'missing_result', sid); exclusions.append({'id': sid, 'reason': 'missing'})
    for role in ['reference', 'negative_control']:
        if not any(x['role'] == role for x in exp.values()): _issue(issues, 'missing_' + role, 'campaign', 'review')
    eligible.sort(key=lambda x: ((-x['score'] if score_domain['direction'] == 'higher' else x['score']), x['id']))
    for i, row in enumerate(eligible, 1): row['rank'] = i
    parents = Counter(x['parent_id'] for x in eligible)
    return _result('docking_campaign', {'expected': expected, 'results': results, 'score_domain': score_domain, 'context': context}, issues,
                   expected_count=len(exp), observed_count=len(found), eligible=eligible, excluded=exclusions,
                   repeated_parents=[k for k, v in parents.items() if v > 1],
                   limitations=['Ranking is limited to the exact declared score domain; different methods are not pooled.', 'Pose QC is caller-declared; inspect coordinates and receipts separately.', 'Chemical states and technical seeds are not independent molecules or biological replicates.', 'Control presence does not establish acceptable control performance or binding activity.'])


def audit_restraint_mapping(mapping: list, restraints: list, context: dict) -> dict:
    """Check explicit source-to-structure residue keys and evidence, without generating AIRs."""
    _context(context); _rows(mapping); _rows(restraints)
    allowed = {}; issues = []; targets = set()
    for row in mapping:
        for key in ['source_chain', 'source_residue', 'structure_chain', 'structure_residue', 'numbering_scheme', 'source_version']:
            text(row.get(key), 200)
        key = (row['source_chain'], row['source_residue'])
        target = (row['structure_chain'], row['structure_residue'])
        if key in allowed or target in targets: raise ValueError('One-to-one explicit residue mapping required')
        allowed[key] = row; targets.add(target)
    ids = set()
    for row in restraints:
        sid = text(row.get('id'), 100)
        if sid in ids: raise ValueError('Unique restraint IDs required')
        ids.add(sid); text(row.get('evidence'), 1000)
        if row.get('kind') not in {'distance', 'active', 'passive'}: raise ValueError('Explicit restraint kind required')
        endpoints = row.get('endpoints')
        expected_n = 2 if row['kind'] == 'distance' else 1
        if not isinstance(endpoints, list) or len(endpoints) != expected_n: raise ValueError('Wrong endpoint count')
        seen = []
        for endpoint in endpoints:
            if not isinstance(endpoint, dict): raise ValueError('Explicit residue endpoint required')
            key = (text(endpoint.get('source_chain'), 200), text(endpoint.get('source_residue'), 200))
            seen.append(key)
            record = allowed.get(key)
            if record is None: _issue(issues, 'unmapped_endpoint', sid)
            elif record.get('present') is not True: _issue(issues, 'missing_structure_residue', sid)
            elif record.get('source_version') != context['source_version']: _issue(issues, 'mapping_source_version_mismatch', sid)
        if len(seen) == 2 and seen[0] == seen[1]: _issue(issues, 'self_distance_restraint', sid)
        if row['kind'] == 'distance':
            if row.get('unit') != 'angstrom': raise ValueError('Explicit distance unit angstrom required')
            lower = _num(row.get('lower'), 0); upper = _num(row.get('upper'), 0)
            if lower >= upper: _issue(issues, 'invalid_distance_bounds', sid)
    return _result('restraints', {'mapping': mapping, 'restraints': restraints, 'context': context}, issues,
                   mapping_count=len(mapping), restraint_count=len(restraints),
                   limitations=['Insertion codes and numbering schemes must be preserved in explicit residue keys.', 'Experimental evidence, accessibility, atom names and AIR semantics require expert review.', 'No restraints are inferred from a prediction or automatically written to a docking engine.'])


def audit_af3_records(records: list, selected_pair: list, context: dict) -> dict:
    """Audit explicit AF3 sample bindings and declared chain-order summary matrices."""
    _context(context); _rows(records, 200)
    if not isinstance(selected_pair, list) or len(selected_pair) != 2 or any(not isinstance(x, str) for x in selected_pair) or len(set(selected_pair)) != 2:
        raise ValueError('Select two distinct chain IDs')
    [text(x, 30) for x in selected_pair]
    issues = []; samples = set(); ids = set(); audited = []; targets = {}
    for row in records:
        sid = text(row.get('id'), 100)
        if sid in ids: raise ValueError('Unique record IDs required')
        ids.add(sid)
        key = (text(row.get('target_id'), 100), _integer(row.get('seed')), _integer(row.get('sample')))
        if key in samples: raise ValueError('Duplicate target/seed/sample refused')
        samples.add(key)
        for name in ['structure_sha256', 'summary_sha256', 'input_sha256']:
            _hash(row.get(name))
        previous = targets.setdefault(row['target_id'], row['input_sha256'])
        if previous != row['input_sha256']: _issue(issues, 'target_input_revision_mismatch', sid)
        if row.get('binding_verified') is not True: _issue(issues, 'sample_file_binding_required', sid)
        chains = row.get('chain_ids')
        if not isinstance(chains, list) or not 2 <= len(chains) <= 128 or any(not isinstance(x, str) or not x for x in chains) or len(set(chains)) != len(chains):
            raise ValueError('Explicit ordered unique chain IDs required')
        if not set(selected_pair) <= set(chains):
            _issue(issues, 'selected_interface_absent', sid); continue
        summary = row.get('summary')
        if not isinstance(summary, dict): raise ValueError('Explicit summary object required')
        if 'chain_ids' in summary and summary['chain_ids'] != chains: _issue(issues, 'summary_chain_order_mismatch', sid)
        for name in ['iptm', 'ptm']:
            _num(summary.get(name), 0, 1)
        _num(summary.get('ranking_score'), -100, 1.5)
        if type(summary.get('has_clash')) is not bool: raise ValueError('Explicit clash boolean required')
        if summary['has_clash']: _issue(issues, 'predicted_clash', sid)
        pair_values = {}
        n = len(chains); a, b = [chains.index(c) for c in selected_pair]
        for field, maximum in [('chain_pair_iptm', 1), ('chain_pair_pae_min', None)]:
            matrix = summary.get(field)
            if matrix is None:
                _issue(issues, 'missing_' + field, sid); continue
            if not isinstance(matrix, list) or len(matrix) != n or any(not isinstance(x, list) or len(x) != n for x in matrix):
                raise ValueError('Chain-pair arrays must match explicit chain order')
            for values in matrix:
                for v in values: _num(v, 0, maximum)
            pair_values[field] = {'forward': matrix[a][b], 'reverse': matrix[b][a]}
        audited.append({'id': sid, 'target_id': row['target_id'], 'seed': row['seed'], 'sample': row['sample'], 'selected_pair': selected_pair,
                        'iptm': summary['iptm'], 'ptm': summary['ptm'], 'ranking_score': summary['ranking_score'], **pair_values})
    return _result('af3', {'records': records, 'selected_pair': selected_pair, 'context': context}, issues, records=audited,
                   limitations=['Summary source hashes and binding_verified declarations require independent source audit.', 'No automatic first-file, model-zero or all-protein assumptions; no archive extraction.', 'PAE uses tokens, pLDDT may use atoms; this auditor does not recompute advanced metrics.', 'No global cross-target ranking or arbitrary good/bad confidence cutoff is applied.', 'Confidence is not affinity, specificity, experimental binding or design success.'])


def audit_mmgbsa_summary(runs: list, context: dict) -> dict:
    """Summarize independent run estimates within an exact endpoint-energy protocol."""
    _context(context); _rows(runs, 100)
    issues = []; seen = set(); ids = set(); trajectories = set(); groups = defaultdict(list); excluded = []
    for row in runs:
        sid = text(row.get('id'), 100); ligand = text(row.get('ligand_id'), 100)
        if sid in ids: raise ValueError('Unique energy run IDs required')
        ids.add(sid)
        start = text(row.get('independent_start'), 100)
        if (ligand, start) in seen: raise ValueError('Repeated independent-start labels are not separate runs')
        seen.add((ligand, start))
        if row.get('method') not in {'MMGBSA', 'MMPBSA'} or row.get('units') not in {'kcal/mol', 'kJ/mol'}:
            raise ValueError('Declare endpoint method and energy units')
        protocol = _hash(row.get('protocol_sha256')); _hash(row.get('trajectory_sha256')); _hash(row.get('topology_sha256'))
        before = len(issues)
        trajectory_key = (ligand, row['trajectory_sha256'])
        if trajectory_key in trajectories: _issue(issues, 'reused_trajectory_not_independent', sid)
        trajectories.add(trajectory_key)
        value = _num(row.get('estimate')); frames = _integer(row.get('frames'), 1)
        ess = _num(row.get('effective_samples'), 1, frames)
        for name in ['solvent_parameters', 'entropy_method', 'frame_selection', 'receptor_ligand_mapping']:
            text(row.get(name), 1000)
        if row.get('equilibration_removed') is not True: _issue(issues, 'equilibration_not_removed', sid)
        if row.get('receipt_verified') is not True: _issue(issues, 'energy_receipt_required', sid)
        if row.get('state') != 'completed' or type(row.get('exit_code')) is not int or row['exit_code'] != 0:
            _issue(issues, 'energy_run_not_complete', sid)
        if ess == frames and frames > 1: _issue(issues, 'full_frame_independence_needs_review', sid, 'review')
        signature = (ligand, row['method'], row['units'], protocol, row['topology_sha256'], row['solvent_parameters'], row['entropy_method'], row['frame_selection'], row['receptor_ligand_mapping'])
        if any(x['severity'] == 'block' for x in issues[before:]): excluded.append(sid)
        else: groups[signature].append(value)
    summaries = []
    for key, values in groups.items():
        ligand, method, units, protocol, topology, *_ = key
        if len(values) < 2: _issue(issues, 'single_start_uncertainty_unavailable', ligand, 'review')
        summaries.append({'ligand_id': ligand, 'method': method, 'units': units, 'protocol_sha256': protocol, 'topology_sha256': topology,
                          'independent_starts': len(values), 'mean_run_estimate': mean(values),
                          'sd_between_runs': stdev(values) if len(values) > 1 else None})
    by_ligand = Counter(k[0] for k in groups)
    for ligand, n in by_ligand.items():
        if n > 1: _issue(issues, 'incomparable_protocols_kept_separate', ligand, 'review')
    return _result('endpoint_energy', {'runs': runs, 'context': context}, issues, summaries=summaries, excluded=excluded,
                   limitations=['SD across independent simulation starts is descriptive, not a biological confidence interval.', 'No frame-based t-test, experimental Kd conversion or automatic pooling across protocols.', 'Entropy omission, solvation approximations and autocorrelation limit interpretation.'])
