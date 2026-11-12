"""Bounded review of measured constraint reports; no local molecule reconstruction."""
import math
from generation_contracts import branch_ids, selection_mask
from contracts import digest

SUCCESS = 'CHEMICAL_QC_PASSED_REQUIRES_DOCKING'


def generation_names(request, variants):
    if request['method'] != 'shepherd2_generate': return set()
    return {'source_checkpoint_manifest.private.json'} | {
        v + '/' + name for v in variants for name in ['generation_contract.private.json'] +
        ['generated_' + str(i) + '.constraints.private.json' for i in range(request['parameters']['n_samples'])]}


def point_report_issues(report, required, limits, source_types):
    issues = []
    if type(report.get('required')) is not int or type(report.get('matched')) is not int or report.get('required') != len(required) or report.get('matched') != len(required) or report.get('passed') is not True:
        return ['required_pharmacophore_recovery_failed']
    rows = report.get('points', [])
    if not isinstance(rows, list) or len(rows) != len(required) or any(type(r.get('source_point_index')) is not int for r in rows) or {r.get('source_point_index') for r in rows} != set(required):
        return ['pharmacophore_point_denominator_changed']
    matched = []
    for row in rows:
        index = row.get('source_point_index')
        actual = row.get('matched_actual_point_index')
        dist, cosine = row.get('distance_angstrom'), row.get('direction_cosine')
        if (row.get('passed') is not True or type(actual) is not int or actual < 0
                or type(dist) not in (int, float) or not math.isfinite(dist)
                or not 0 <= dist <= limits['max_priority_distance_angstrom']):
            issues.append('actual_point_distance_or_identity_failed')
        if type(row.get('source_type')) is not int or row.get('source_type') != source_types[index]: issues.append('actual_point_type_changed')
        if source_types[index] in (0, 1, 2, 4):
            if type(cosine) not in (int, float) or not math.isfinite(cosine) or not limits['min_direction_cosine'] <= cosine <= 1.000001:
                issues.append('actual_directional_pharmacophore_failed')
        matched.append(actual)
    if len(matched) != len(set(matched)): issues.append('actual_pharmacophore_reused_for_multiple_required_points')
    return issues


def constraint_outcome_issues(request, contract, report):
    """Verify reported failed and incomplete assessments as well as successful ones."""
    g=request['parameters']['generation_options'];weights=request['parameters']['profile_weights'];issues=[]
    expected={x['reference_id']:x for i,x in enumerate(g['reference_conditions']) if g['task']!='unconditional' and weights[i]>0}
    results=report.get('reference_results',[])
    if not isinstance(results,list) or any(not isinstance(x,dict) for x in results):return ['candidate_constraint_outcomes_malformed']
    identities=[x.get('reference_id') for x in results]
    if any(x not in expected for x in identities) or len(identities)!=len(set(identities)):issues.append('candidate_reference_constraint_coverage_changed')
    complete_axis=len(results)==len(expected) and set(identities)==set(expected)
    if report.get('hard_constraints_assessed') is True and not complete_axis:issues.append('assessed_constraint_reference_axis_incomplete')
    snapshots={x['reference_id']:x for x in contract['reference_snapshots']}
    for row in results:
        ref=row.get('reference_id')
        if ref not in expected:continue
        scaffold=row.get('scaffold',{})
        flags=[scaffold.get('passed')]
        if type(row.get('assessment_complete')) is not bool or type(scaffold.get('assessment_complete')) is not bool or row.get('assessment_complete') is not scaffold.get('assessment_complete'):issues.append('constraint_assessment_completeness_disagrees')
        required=[j for j,bit in enumerate(snapshots[ref]['resolved_priority_mask_on_full_reference_axis']) if bit]
        source_types=[x['type'] for x in snapshots[ref]['pharmacophore_axis']]
        for key in ('raw_generated_pharmacophore_head','reextracted_actual_molecular_pharmacophores'):
            points=row.get(key,{})
            values=points.get('points',[]);matched=points.get('matched');passed=points.get('passed');flags.append(passed)
            if (type(points.get('required')) is not int or points['required']!=len(required) or type(matched) is not int or not 0<=matched<=len(required) or type(passed) is not bool or passed!=(matched==len(required)) or not isinstance(values,list) or any(not isinstance(x,dict) for x in values)):
                issues.append('constraint_point_outcome_counts_disagree');continue
            if len(values)!=len(required) or any(type(x.get('source_point_index')) is not int for x in values) or {x.get('source_point_index') for x in values}!=set(required):issues.append('constraint_point_outcome_axis_changed');continue
            if any(type(x.get('passed')) is not bool for x in values) or sum(x.get('passed') is True for x in values)!=matched:issues.append('constraint_point_outcome_counts_disagree')
            for point in values:
                index=point['source_point_index']
                if type(point.get('source_type')) is not int or point.get('source_type')!=source_types[index]:issues.append('constraint_point_outcome_type_changed')
        if any(type(x) is not bool for x in flags) or type(row.get('passed')) is not bool or row.get('passed') is not all(x is True for x in flags):issues.append('reference_constraint_outcome_disagrees')
    if complete_axis and (results or report.get('hard_constraints_assessed') is True):
        assessed=all(x.get('assessment_complete') is True for x in results)
        passed=all(x.get('passed') is True for x in results)
        if report.get('hard_constraints_assessed') is not assessed or report.get('constraints_passed') is not passed:issues.append('candidate_constraint_outcome_disagrees')
    if report.get('state')=='HOLD_SEARCH_INCOMPLETE' and (report.get('hard_constraints_assessed') is not False or not complete_axis or not any(x.get('assessment_complete') is False for x in results)):issues.append('search_incomplete_state_has_no_incomplete_assessment')
    return issues


def candidate_report_issues(request, contract, report, record, bound, variant):
    issues = []
    p = request['parameters']; g = p['generation_options']; limits = g['constraint_qc']
    name = record['candidate_id']
    if (report.get('candidate_id') != name or report.get('generation_options_sha256') != digest(g)
            or report.get('generation_contract_sha256') != record.get('generation_contract_sha256')
            or report.get('experimental_binding_established') is not False):
        issues.append('candidate_constraint_identity_or_scope_changed')
    chemical=report.get('chemical_valid');constraints=report.get('constraints_passed');eligible=report.get('eligible')
    if any(type(x) is not bool for x in (chemical,constraints,eligible,report.get('hard_constraints_assessed'))):issues.append('candidate_QC_stage_flags_missing_or_invalid')
    if report.get('actual_structure_QC') is not chemical:issues.append('candidate_chemical_QC_alias_disagrees')
    if report.get('hard_constraints_assessed') is True and chemical is not True:issues.append('hard_constraints_assessed_without_valid_chemistry')
    if constraints is True and (chemical is not True or report.get('hard_constraints_assessed') is not True):issues.append('constraint_pass_without_actual_complete_assessment')
    if eligible is True and (chemical is not True or constraints is not True):issues.append('eligibility_without_chemical_and_constraint_pass')
    passed = record.get('state') == SUCCESS
    if eligible is not passed or report.get('state') != record.get('state'):
        issues.append('candidate_constraint_status_disagrees')
    if not passed:
        if not report.get('failure_reason'): issues.append('failed_generation_reason_missing')
    elif report.get('failure_reason'):issues.append('eligible_generation_has_failure_reason')
    restore=request['parameters']['generation_options']['condition_frame']
    expected_restore=restore if isinstance(restore,list) else [0.,0.,0.]
    actual_restore=report.get('native_output_to_source_translation_angstrom')
    if not isinstance(actual_restore,list) or len(actual_restore)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or not math.isclose(x,y,rel_tol=0.,abs_tol=1e-12) for x,y in zip(actual_restore or [],expected_restore)):issues.append('native_output_source_frame_restore_changed')
    score_rows=report.get('profile_fidelity_scores',[])
    references=[r['reference_id'] for r in g['reference_conditions']]
    if not isinstance(score_rows,list) or any(not isinstance(x,dict) for x in score_rows):return issues+['candidate_profile_fidelity_report_malformed']
    scores={x.get('reference_id'):x for x in score_rows}
    if len(scores)!=len(score_rows) or set(scores)!=set(references):issues.append('candidate_profile_fidelity_reference_changed')
    for ref,row in scores.items():
        if ref not in references:continue
        weight=p['profile_weights'][references.index(ref)];direction='positive' if weight>0 else 'negative' if weight<0 else 'zero'
        if type(row.get('guidance_weight')) not in (int,float) or not math.isfinite(row['guidance_weight']) or row['guidance_weight']!=weight or row.get('guidance_direction')!=direction:issues.append('candidate_profile_fidelity_guidance_changed')
        if row.get('scope')!='raw_GFN2_xTB_ligand_profile_similarity_not_binding_energy_or_selectivity':issues.append('candidate_profile_fidelity_scope_changed')
        state=row.get('scoring_state')
        if state not in ('NOT_ASSESSED','SCORED','FAILED'):issues.append('candidate_profile_fidelity_scoring_state_invalid')
        if state=='FAILED' and not row.get('error'):issues.append('failed_profile_fidelity_reason_missing')
        if state!='SCORED' and any(row.get(field) is not None for field in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity')):issues.append('unassessed_or_failed_profile_fidelity_contains_accepted_values')
        if state=='SCORED':
            if chemical is not True:issues.append('unverified_chemistry_has_actual_profile_score')
            for field in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity'):
                value=row.get(field)
                if field=='pharmacophore_similarity' and value is None:continue
                if type(value) not in (int,float) or not math.isfinite(value) or not -1e-6<=value<=1.000001:issues.append('candidate_profile_fidelity_value_invalid')
    if eligible is True and (set(scores)!=set(references) or any(x.get('scoring_state')!='SCORED' for x in score_rows)):issues.append('eligible_candidate_profile_fidelity_incomplete')
    if chemical is not True:return issues
    if report.get('actual_structure_QC') is not True or report.get('saved_SDF_readback_verified') is not True:
        issues.append('accepted_generation_lacks_actual_structure_QC')
    sdf = report.get('actual_sdf', {})
    if sdf.get('path') != name + '.sdf':issues.append('accepted_generation_SDF_path_not_canonical')
    if sdf.get('state_id')!=request['run_id']+'__'+variant+'__'+name or sdf.get('parent_id')!='UNASSESSED_GENERATED_PARENT':issues.append('saved_SDF_state_or_parent_identity_changed')
    if not isinstance(sdf.get('microstate_id'),str) or not sdf['microstate_id']:issues.append('saved_SDF_chemical_identity_missing')
    actual = bound.get(variant + '/' + str(sdf.get('path', '')), {})
    if not actual or any(sdf.get(k) != actual.get(k) for k in ('sha256', 'bytes')):
        issues.append('constraint_report_not_bound_to_actual_SDF')
    issues+=constraint_outcome_issues(request,contract,report)
    if constraints is not True:return issues
    snapshots = {r['reference_id']: r for r in contract['reference_snapshots']}
    expected = {r['reference_id']: r for i, r in enumerate(g['reference_conditions'])
                if g['task'] != 'unconditional' and p['profile_weights'][i] > 0}
    results = report.get('reference_results', [])
    if len(results) != len(expected) or {r.get('reference_id') for r in results} != set(expected):
        return issues + ['candidate_reference_constraint_coverage_changed']
    for row in results:
        selection = expected[row['reference_id']]; snapshot = snapshots[row['reference_id']]
        scaffold = row.get('scaffold', {})
        if row.get('passed') is not True or scaffold.get('passed') is not True or type(scaffold.get('required')) is not int or scaffold.get('required') != len(selection['scaffold_atom_indices']):
            issues.append('accepted_scaffold_constraint_failed')
        if selection['scaffold_mode'] != 'none':
            if scaffold.get('chemical_subgraph_retained') is not True or scaffold.get('source_atom_indices') != selection['scaffold_atom_indices']:
                issues.append('scaffold_chemical_subgraph_or_mapping_changed')
            actual_inds = scaffold.get('actual_atom_indices', [])
            if len(actual_inds) != len(selection['scaffold_atom_indices']) or any(type(x) is not int or x < 0 for x in actual_inds) or len(set(actual_inds)) != len(actual_inds):
                issues.append('scaffold_atom_mapping_not_one_to_one')
            if selection['scaffold_mode'] == 'fixed':
                value = scaffold.get('max_displacement_angstrom')
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= limits['max_scaffold_displacement_angstrom'] or scaffold.get('fixed_position_required') is not True:
                    issues.append('fixed_scaffold_position_not_retained')
            elif scaffold.get('fixed_position_required') is not False:
                issues.append('released_or_inpainted_scaffold_misrepresented_as_fixed')
        required = [j for j, bit in enumerate(snapshot['resolved_priority_mask_on_full_reference_axis']) if bit]
        types = [x['type'] for x in snapshot['pharmacophore_axis']]
        for key in ('raw_generated_pharmacophore_head', 'reextracted_actual_molecular_pharmacophores'):
            issues += [key + ':' + issue for issue in point_report_issues(row.get(key, {}), required, limits, types)]
    return issues


def inspect_generation(request, content, proof, bound, eligibility, variants, diagnostics):
    if request['method'] != 'shepherd2_generate': return []
    p = request['parameters']; g = p['generation_options']; issues = []
    source_refs = [r for r in content['source_structures.private.json']['molecules'] if r['role'] == 'reference']
    if [r['id'] for r in source_refs] != [r['reference_id'] for r in g['reference_conditions']]:
        return ['source_reference_condition_order_changed']
    if any(source.get('sdf',{}).get('sha256')!=wanted['source_sdf_sha256'] for source,wanted in zip(source_refs,g['reference_conditions'])):issues.append('selected_reference_SDF_differs_from_source_manifest')
    # The caller already binds the copied asset-manifest bytes to the request hash.
    assets = content['source_checkpoint_manifest.private.json']
    seeds = {'primary': p['seed'], **{v['label']: v['seed'] for v in request['sensitivity_variants']}}
    for variant in variants:
        contract = content[variant + '/generation_contract.private.json']
        expected_contract_sha = bound[variant + '/generation_contract.private.json']['sha256']
        if (contract.get('plan_sha256') != request['plan_sha256'] or contract.get('generation_options_sha256') != digest(g)
                or contract.get('branch_ids') != branch_ids(p) or contract.get('seed') != seeds[variant]
                or contract.get('checkpoint_sha256') != assets.get('sha256')
                or contract.get('condition_frame') != g['condition_frame']
                or contract.get('profile_weights') != p['profile_weights']
                or contract.get('composition_mode') != p['composition_mode']):
            issues.append('actual_generation_contract_changed')
        if (contract.get('native_surface_points') != 75 or contract.get('native_probe_radius_angstrom') != .6
                or contract.get('threshold_basis') != g['constraint_qc']['threshold_basis']
                or contract.get('scientific_acceptance') != 'NOT_ESTABLISHED' or contract.get('public_upload') is not False):
            issues.append('native_generation_scale_or_acceptance_scope_changed')
        snapshots = contract.get('reference_snapshots', [])
        if len(snapshots) != len(g['reference_conditions']):
            issues.append('reference_axis_snapshot_coverage_changed'); continue
        for actual, wanted in zip(snapshots, g['reference_conditions']):
            if (actual.get('reference_id') != wanted['reference_id'] or actual.get('source_sdf_sha256') != wanted['source_sdf_sha256']
                    or actual.get('atom_axis_sha256') != wanted['atom_axis_sha256']
                    or digest(actual.get('atom_axis')) != wanted['atom_axis_sha256']
                    or actual.get('pharmacophore_axis_sha256') != wanted['pharmacophore_axis_sha256']
                    or digest(actual.get('pharmacophore_axis')) != wanted['pharmacophore_axis_sha256']
                    or len(actual.get('atom_axis', [])) != wanted['expected_atom_count']
                    or len(actual.get('pharmacophore_axis', [])) != wanted['expected_pharmacophore_count']
                    or actual.get('scaffold_mode') != wanted['scaffold_mode'] or actual.get('pharm_mode') != wanted['pharm_mode']):
                issues.append('actual_reference_atom_or_pharmacophore_axis_changed')
            mask = actual.get('resolved_priority_mask_on_full_reference_axis', [])
            direct = selection_mask(wanted['pharm_selection'], wanted['expected_atom_count'], wanted['expected_pharmacophore_count'])
            if wanted['pharm_mode'] == 'inpaint': direct = [0] * wanted['expected_pharmacophore_count']
            if wanted['pharm_mode'] == 'pharm-full': direct = [1] * wanted['expected_pharmacophore_count']
            if len(mask) != wanted['expected_pharmacophore_count'] or any(type(v) is not int or v not in (0, 1) for v in mask) or direct is not None and mask != direct:
                issues.append('actual_priority_mask_changed')
            if wanted['pharm_mode'] in ('pharm-priority', 'pharm-priority-only') and not any(mask):
                issues.append('actual_priority_mask_empty')
        from generation_contracts import effective_conditioning,expected_alignment_steps,completed_steps
        resolved_masks=[x['resolved_priority_mask_on_full_reference_axis'] for x in snapshots]
        effective=effective_conditioning(p,resolved_masks);alignment_steps=expected_alignment_steps(p,effective)
        if digest(contract.get('effective_conditioning'))!=digest(effective) or contract.get('expected_alignment_steps')!=alignment_steps:issues.append('actual_native_conditioning_or_alignment_schedule_changed')
        if type(contract.get('native_early_stop_steps')) is not int or contract.get('native_early_stop_steps')!=completed_steps(g['sampler']['early_stop_edm'],p['denoise_steps']):issues.append('native_early_stop_semantics_changed')
        counts = contract.get('resolved_sample_counts', [])
        if len(counts) != p['n_samples'] or [r.get('candidate_id') for r in counts] != ['generated_' + str(i) for i in range(p['n_samples'])]:
            issues.append('resolved_generation_count_denominator_changed')
        for i, count in enumerate(counts):
            for axis, key, offset in [('atoms', 'N_x1', 'add_atoms'), ('pharms', 'N_x4', 'add_pharms')]:
                value = count.get(key); mode = g['sizes']['mode']; base = g['reference_conditions'][0]['expected_atom_count' if axis == 'atoms' else 'expected_pharmacophore_count']
                if type(value) is not int or not 1 <= value <= p['max_atoms']:
                    issues.append('actual_generation_count_invalid'); continue
                if mode == 'offset' and value != base + p[offset] or mode == 'absolute' and value != g['sizes'][axis] or mode == 'per_sample' and (i >= len(g['sizes'][axis]) or value != g['sizes'][axis][i]):
                    issues.append('actual_generation_count_changed')
                if mode == 'offset_range' and not base + g['sizes'][axis][0] <= value <= base + g['sizes'][axis][1]:
                    issues.append('actual_generation_count_outside_range')
        audit = next((r for r in proof if r['variant'] == variant and r['role'] == 'constraint_results'), None)
        denominator = next(r for r in proof if r['variant'] == variant and r['role'] == 'candidate_denominator')
        if audit is None or audit.get('rows') != p['n_samples'] or audit.get('candidate_row_counts') != denominator.get('candidate_row_counts') or audit.get('status_counts') != denominator.get('status_counts'):
            issues.append('constraint_result_denominator_or_states_changed')
        report_successes = set();chemical_count=0;constraint_count=0
        for i in range(p['n_samples']):
            name = 'generated_' + str(i)
            report = content[variant + '/' + name + '.constraints.private.json']
            record = {'candidate_id': name, 'state': denominator.get('candidate_states',{}).get(name), 'generation_contract_sha256': expected_contract_sha}
            if report.get('chemical_valid') is True:chemical_count+=1
            if report.get('chemical_valid') is True and report.get('constraints_passed') is True:constraint_count+=1
            if report.get('eligible') is True: report_successes.add(name)
            issues += candidate_report_issues(request, contract, report, record, bound, variant)
        if denominator.get('status_counts',{}).get(SUCCESS,0) != len(report_successes):issues.append('complete_constraint_reports_disagree_with_generation_status_denominator')
        score_audit = next(r for r in proof if r['variant']==variant and r['role']=='profile_scores')
        if score_audit.get('rows') != len(report_successes)*len(source_refs) or score_audit.get('candidate_row_counts') != {name:len(source_refs) for name in report_successes}:
            issues.append('accepted_generation_reference_score_coverage_changed')
        eligible = [r for r in eligibility if r['variant'] == variant]
        if {r['candidate_id'] for r in eligible} != report_successes or len(eligible) != len(report_successes):
            issues.append('eligible_candidates_disagree_with_complete_constraint_reports')
        for row in eligible:
            expected_path = variant + '/' + row['candidate_id'] + '.constraints.private.json'
            saved=content[expected_path].get('actual_sdf',{})
            if (row.get('constraints_passed') is not True or row.get('constraint_report_path') != expected_path
                    or row.get('constraint_report_sha256') != bound.get(expected_path, {}).get('sha256')
                    or row.get('generation_contract_sha256') != expected_contract_sha
                    or row.get('generation_options_sha256') != digest(g)
                    or row.get('state_id') != request['run_id']+'__'+variant+'__'+row['candidate_id']
                    or row.get('path') != variant+'/'+row['candidate_id']+'.sdf'
                    or any(row.get(k)!=saved.get(k) for k in ('sha256','bytes','state_id','parent_id','microstate_id'))):
                issues.append('eligible_candidate_constraint_receipt_binding_changed')
        success = len(report_successes)
        actual = next(x for x in diagnostics if x['variant'] == variant)
        metrics=actual.get('metrics',{});requested=p['n_samples']
        # These helpers only inspect scalar reports and use the standard library.
        # Preserve failed/unassessed observations in the full requested denominator.
        from server.generation import summarize_profile_fidelity
        reports=[content[variant+'/generated_'+str(i)+'.constraints.private.json'] for i in range(requested)]
        try:
            expected_fidelity=summarize_profile_fidelity(source_refs,p['profile_weights'],reports,requested)
            if digest(actual.get('profile_fidelity_summary'))!=digest(expected_fidelity):issues.append('profile_fidelity_summary_disagrees_with_complete_reports')
        except (KeyError,TypeError,ValueError,OverflowError):issues.append('profile_fidelity_summary_unverifiable')
        if any(type(metrics.get(k)) is not int or metrics[k]!=value for k,value in [('chemical_valid_count',chemical_count),('constraint_pass_count',constraint_count),('eligible_count',success)]):issues.append('chemical_constraint_eligible_counts_disagree')
        if any(type(metrics.get(k)) not in (int,float) or not math.isfinite(metrics[k]) or not math.isclose(metrics[k],value/requested,rel_tol=0.,abs_tol=1e-12) for k,value in [('chemical_valid_fraction',chemical_count),('constraint_pass_fraction',constraint_count),('eligible_fraction',success)]):issues.append('chemical_constraint_eligible_fractions_disagree')
        if metrics.get('chemical_qc_passed')!=chemical_count or type(metrics.get('chemical_qc_passed')) is not int or type(metrics.get('valid_fraction')) not in (int,float) or not math.isclose(metrics['valid_fraction'],success/requested,rel_tol=0.,abs_tol=1e-12):issues.append('legacy_generation_metric_scope_disagrees')
        chemical_met=chemical_count/requested>=p['min_valid_fraction']
        if actual.get('minimum_valid_fraction_met') is not chemical_met:issues.append('generation_chemical_gate_summary_disagrees')
        if not chemical_met:issues.append('prespecified_chemical_valid_fraction_failed')
        if (actual.get('branch_ids') != branch_ids(p) or actual.get('generation_options_sha256') != digest(g)
                or actual.get('generation_contract_sha256') != expected_contract_sha
                or digest(actual.get('effective_conditioning'))!=digest(effective)
                or actual.get('expected_alignment_steps')!=alignment_steps):
            issues.append('generation_branch_binding_changed')
        constraint_met=constraint_count/requested>=g['constraint_qc']['min_constraint_pass_fraction']
        if actual.get('minimum_constraint_fraction_met') is not constraint_met:issues.append('generation_constraint_gate_summary_disagrees')
        if not constraint_met:issues.append('prespecified_constraint_pass_fraction_failed')
    return issues
