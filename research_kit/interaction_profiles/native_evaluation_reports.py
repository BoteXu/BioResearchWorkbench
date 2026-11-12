"""Review complete native callback/engine metadata, never recalculate molecular scores."""
import math
from pathlib import Path
from contracts import digest,read

TIMEOUT='each_xtb_subprocess_not_whole_molecule_or_batch'
SUCCESS='NATIVE_EVALUATED_REQUIRES_SCIENTIFIC_REVIEW'
SCORE_FIELDS={'surface':['sims_surf_target_relax_optimal'],'esp':['sims_esp_target_relax_optimal'],'pharm':['sims_pharm_target_relax_optimal'],'all':['sims_surf_target_relax_optimal','sims_esp_target_relax_optimal','sims_pharm_target_relax_optimal']}

def finite(x):return type(x) in (int,float) and math.isfinite(x)

def inspect_native_variant(v,content,bound,p,spec,n):
    prefix=v+'/';issues=[];records=content[prefix+'native_records.private.json'];callbacks=content[prefix+'callback_results.private.json'];audit=content[prefix+'engine_audit.private.json'];meta=content[prefix+'evaluation_metadata.private.json'];glob=content[prefix+'native_global_metrics.private.json'];line=content[prefix+'origin_lineage.private.json'];reference=content[prefix+'reference_binding.private.json'];contract=content[prefix+'origin_generation_contract_snapshot.private.json'];rc=content[prefix+'origin_receipt_snapshot.private.json'];origin=content[prefix+'origin_request_snapshot.private.json'];software=content[prefix+'software_identity.private.json']
    wanted=['generated_'+str(i) for i in range(n)]
    if any(not isinstance(rows,list) or [x.get('candidate_id') for x in rows]!=wanted for rows in (records,callbacks)):raise ValueError('Complete native records/callbacks required in original requested order')
    outputs={x['path']:x for x in rc['outputs']};snapshots=[x for x in contract['reference_snapshots'] if x['reference_id']==spec['reference_id']]
    if len(snapshots)!=1:raise ValueError('Exact full reference snapshot required')
    snapshot=snapshots[0];mask=snapshot['resolved_priority_mask_on_full_reference_axis']
    axis=snapshot.get('pharmacophore_axis',[])
    if not isinstance(mask,list) or len(mask)!=len(axis) or any(type(x) is not int or x not in (0,1) for x in mask):raise ValueError('Strict full-reference priority mask required')
    if p['priority_policy']=='none':priority=None;priority_scope='NOT_REQUESTED'
    elif not any(mask):priority=None;priority_scope='NO_PRIORITY_SUBSET_IN_ORIGIN_MASK'
    elif all(mask):priority=None;priority_scope='NO_NONPRIORITY_COMPLEMENT_IN_ORIGIN_MASK'
    else:priority=[i for i,x in enumerate(mask) if x];priority_scope='FULL_PHARM_ALIGNMENT_THEN_REFERENCE_TVERSKY_FOR_BOTH_SUBSETS'
    scores=list(SCORE_FIELDS[p['condition']])
    if priority is not None:scores+=['sims_pharm_priority_target_relax_optimal','sims_pharm_nonpriority_target_relax_optimal']
    if line.get('eligible_only_filter_used') is not False or line.get('candidate_ids')!=wanted or line.get('expected_attempts')!=n or line.get('reference_id')!=spec['reference_id'] or line.get('priority_indices_full_reference_axis')!=priority or line.get('priority_scope')!=priority_scope:issues.append('native_full_campaign_or_priority_lineage_changed')
    if meta.get('required_score_fields')!=scores or meta.get('condition')!=p['condition'] or meta.get('priority_scope')!=priority_scope or meta.get('expected_attempts')!=n or meta.get('reference_binding_sha256')!=bound.get(prefix+'reference_binding.private.json',{}).get('sha256'):issues.append('native_evaluation_method_or_reference_changed')
    for obj in (audit,meta,glob):
        if obj.get('energy_unit')!='hartree' or obj.get('timeout_scope')!=TIMEOUT or obj.get('scientific_acceptance')!='NOT_ESTABLISHED':issues.append('native_energy_timeout_or_acceptance_scope_changed')
    if meta.get('method_cli_explicit') is not False or audit.get('method_cli_explicit') is not False or meta.get('docking_eligibility_established') is not False or meta.get('fixed_pose_constraints_reassessed') is not False or meta.get('independently_aligned_modalities') is not True or glob.get('one_joint_docking_pose_established') is not False or software.get('generation_weights_loaded') is not False:issues.append('native_evaluation_misrepresented_as_one_docking_pose_or_explicit_GFN')
    if meta.get('timeout_seconds')!=p['xtb_timeout_seconds'] or meta.get('surface_points')!=400 or meta.get('probe_radius_angstrom')!=1.2 or meta.get('pharm_multi_vector') is not False:issues.append('native_evaluation_configuration_changed')
    if reference.get('reference_id')!=spec['reference_id'] or any(reference.get(k)!=snapshot.get(k) for k in ('source_sdf_sha256','atom_axis_sha256','pharmacophore_axis_sha256')) or reference.get('partial_charges_from_exact_origin_profile') is not True or reference.get('coordinates_unit')!='angstrom':issues.append('full_reference_profile_identity_changed')
    if reference.get('source_profile_sha256')!=outputs.get(spec['origin_variant']+'/profile_'+spec['reference_id']+'.npz',{}).get('sha256') or reference.get('source_axes_sha256')!=outputs.get(spec['origin_variant']+'/'+spec['reference_id']+'.axes.private.json',{}).get('sha256'):issues.append('reference_profile_or_axis_not_generation_receipt_bound')
    xtb=audit.get('xtb_identity',{})
    if audit.get('single_worker') is not True or xtb.get('sha256')!=p['expected_xtb_sha256'] or xtb.get('reviewed_version_text')!=p['expected_xtb_version'] or xtb.get('version_matches') is not True or type(xtb.get('version_exit_code')) is not int or xtb['version_exit_code']!=0 or software.get('versions')!=p['expected_versions'] or software.get('xtb_identity')!=xtb:issues.append('actual_native_evaluation_software_changed')
    pins=read(Path(__file__).with_name('upstream_code.json'))['shepherd-score'];identities=software.get('python_sources',[])
    if len(identities)!=1 or identities[0].get('package')!='shepherd-score' or identities[0].get('upstream_commit')!=pins['commit'] or identities[0].get('fingerprint')!=digest(pins['python_blobs']):issues.append('native_evaluation_author_source_changed')
    calls=audit.get('calls')
    if not isinstance(calls,list) or [x.get('call_index') for x in calls]!=list(range(len(calls))):raise ValueError('Complete unique ordered engine-call records required')
    calls_by={cid:[] for cid in wanted}
    for call in calls:
        cid=call.get('candidate_id')
        if cid not in calls_by:issues.append('engine_call_unknown_candidate');continue
        calls_by[cid].append(call)
        if call.get('timeout_seconds')!=p['xtb_timeout_seconds'] or call.get('timeout_scope')!=TIMEOUT or call.get('energy_unit')!='hartree' or call.get('energy_scope')!='isolated_conformer_not_binding_energy' or call.get('xtb_sha256')!=p['expected_xtb_sha256'] or call.get('method_cli_explicit') is not False:issues.append('engine_call_identity_or_energy_scope_changed')
        argv=call.get('native_argv',[])
        expected_argv=['xtb','input_mol.xyz','--opt' if call.get('stage')=='relaxation' else '--scc','--alpb',p['solvent'],'--parallel',str(p['xtb_cores']),'--chrg',str(call.get('requested_formal_charge'))]
        if type(call.get('requested_formal_charge')) is not int or argv!=expected_argv or call.get('executed_argv')!=[xtb.get('executable')]+expected_argv[1:] or call.get('operation')!=('check_call' if call.get('stage')=='relaxation' else 'check_output'):issues.append('native_engine_program_operation_or_solvent_changed')
        try:
            charge=int(argv[argv.index('--chrg')+1]);threads=int(argv[argv.index('--parallel')+1])
            if charge!=call.get('requested_formal_charge') or threads!=p['xtb_cores'] or '--gfn' in argv or call.get('stage')!=('relaxation' if '--opt' in argv else 'single_point'):issues.append('engine_native_command_or_charge_changed')
        except (ValueError,IndexError,TypeError):issues.append('engine_native_command_or_charge_changed')
        if call.get('evidence_complete') is True and (type(call.get('returncode')) is not int or call['returncode']!=0 or call.get('exception_type') is not None or call.get('timed_out') is not False or call.get('binary_unchanged_after_call') is not True or call.get('normal_termination_observed') is not True or not finite(call.get('energy_hartree')) or call.get('evidence_issues') or not finite(call.get('partial_charge_sum')) or abs(call['partial_charge_sum']-call['requested_formal_charge'])>p['charge_sum_tolerance']):issues.append('engine_success_without_complete_evidence')
        if call.get('evidence_complete') is True:
            artifacts=call.get('artifacts',{});needed={'input_mol.xyz','charges','engine.log'}|({'xtbopt.xyz'} if call.get('stage')=='relaxation' else set())
            if not needed<=set(artifacts) or any(not isinstance(artifacts.get(k),dict) or type(artifacts[k].get('bytes')) is not int or artifacts[k]['bytes']<1 for k in needed):issues.append('engine_success_without_required_artifacts')
            if type(call.get('atoms')) is not int or not 0<call['atoms']<=p['max_atoms'] or type(call.get('partial_charge_count')) is not int or call['partial_charge_count']!=call.get('atoms') or call.get('partial_charge_unit')!='elementary_charge':issues.append('engine_success_with_incomplete_atom_or_charge_axis')
            if call.get('stage')=='relaxation' and call.get('optimized_coordinate_axis_valid') is not True:issues.append('engine_relaxation_without_valid_optimized_coordinate_axis')
        for artifact in call.get('artifacts',{}).values():
            if artifact is None:continue
            rec=bound.get(prefix+'xtb_audit/'+artifact.get('path',''),{})
            if not rec or any(rec.get(k)!=artifact.get(k) for k in ('sha256','bytes')):issues.append('engine_artifact_not_bound_to_completion_receipt')
    ninputs=0;ncallback=0;valid=0;post=0;graph=0;nengine=0;ncomplete=0;map_native={}
    for record,cb in zip(records,callbacks):
        cid=record['candidate_id'];i=record.get('native_i');result=cb.get('native_result');own=calls_by[cid]
        if record.get('strain_energy_unit')!='hartree' or record.get('rmsd_unit')!='angstrom' or record.get('eligible_for_docking') is not False:issues.append('native_candidate_units_or_docking_scope_changed')
        if any(cb.get(k)!=record.get(k) for k in ('candidate_id','state','native_i','error','raw_sha256','source_report_sha256','origin_generation_state')):issues.append('native_callback_record_binding_changed')
        rawpath=spec['origin_variant']+'/'+cid+'.raw.npz';reportpath=spec['origin_variant']+'/'+cid+'.constraints.private.json'
        if record.get('source_report_sha256')!=outputs.get(reportpath,{}).get('sha256') or record.get('raw_sha256')!=outputs.get(rawpath,{}).get('sha256'):issues.append('native_input_not_bound_to_generation_outputs')
        if i is not None:
            if type(i) is not int or i!=ninputs:issues.append('native_input_index_denominator_changed')
            map_native[str(i)]=cid;ninputs+=1
            if not record.get('raw_sha256'):issues.append('native_evaluation_without_raw_input')
        elif record.get('state') not in ('INPUT_UNAVAILABLE','INPUT_INVALID') or not record.get('error'):issues.append('missing_native_input_not_explicitly_unavailable')
        elif (record['state']=='INPUT_UNAVAILABLE') is (record.get('raw_sha256') is not None):issues.append('unavailable_and_invalid_native_inputs_confused')
        if cb.get('engine_call_indices')!=[x['call_index'] for x in own] or any(x.get('native_i')!=i for x in own):issues.append('engine_candidate_callback_mapping_changed')
        complete_engine=len(own)==2 and {x['stage'] for x in own}=={'single_point','relaxation'} and all(x.get('evidence_complete') is True for x in own)
        if record.get('engine_evidence_complete') is not complete_engine or record.get('engine_calls')!=len(own):issues.append('engine_evidence_denominator_changed')
        charge_matches=all(x.get('requested_formal_charge')==origin['parameters']['generated_formal_charge'] for x in own) if own else None
        if record.get('native_reconstruction_charge_matches_origin_declared') is not charge_matches:issues.append('native_reconstructed_charge_review_changed')
        scoring=all(finite(record.get(key)) for key in scores)
        if record.get('native_scoring_complete') is not scoring:issues.append('native_requested_score_missingness_changed')
        if isinstance(result,dict):
            ncallback+=1
            if result.get('error')!=record.get('error'):issues.append('native_callback_error_changed')
            for flag,artifact_key in (('is_valid','molblock'),('is_valid_post_opt','molblock_post_opt')):
                artifact=cb.get('native_artifacts',{}).get(artifact_key)
                if result.get(flag) is True and (not isinstance(artifact,dict) or not artifact.get('path') or type(artifact.get('bytes')) is not int or artifact['bytes']<1):issues.append('native_valid_structure_missing_bound_molblock')
            if i is None or type(result.get('i')) is not int or result['i']!=i:issues.append('native_callback_index_changed')
            for key in ('is_valid','is_valid_post_opt','is_graph_consistent'):
                if type(result.get(key)) is not bool or record.get('native_'+key) is not result[key]:issues.append('native_validity_flag_changed')
            for field,value in record.items():
                if field.startswith('sims_'):
                    expected=result.get('sim'+field[4:])
                    if value!=expected:issues.append('native_score_changed_between_callback_and_ledger')
                    if value is not None and (not finite(value) or not -1e-6<=value<=1.000001):issues.append('invalid_native_dimensionless_similarity')
            expected_state='NATIVE_EVALUATION_FAILED_OR_PARTIAL' if not result['is_valid'] or not result['is_valid_post_opt'] else 'NATIVE_EVALUATION_AUDIT_HOLD' if not result['is_graph_consistent'] or not complete_engine or not charge_matches or not scoring else SUCCESS
            if record['state']!=expected_state:issues.append('native_outcome_promoted_despite_failure_or_incomplete_evidence')
            for field in ('strain_energy','rmsd','smiles','smiles_post_opt'):
                if record.get(field)!=result.get(field):issues.append('native_property_changed_between_callback_and_ledger')
        elif result is not None or i is not None and record.get('state')!='NATIVE_CALLBACK_MISSING':issues.append('missing_native_callback_not_explicitly_unavailable')
        for artifact in cb.get('native_artifacts',{}).values():
            if artifact is None:continue
            rec=bound.get(prefix+artifact.get('path',''),{})
            if not rec or any(rec.get(k)!=artifact.get(k) for k in ('sha256','bytes')):issues.append('native_molecular_artifact_not_completion_bound')
        valid+=record.get('native_is_valid') is True;post+=record.get('native_is_valid_post_opt') is True;graph+=record.get('native_is_graph_consistent') is True;nengine+=complete_engine;ncomplete+=record['state']==SUCCESS
    if line.get('native_i_to_candidate_id')!=map_native:issues.append('native_to_original_requested_identity_changed')
    if meta.get('native_input_count')!=ninputs or meta.get('native_callback_count')!=ncallback or glob.get('native_denominator')!=ninputs or glob.get('all_requested_denominator')!=n:issues.append('native_or_requested_global_denominator_changed')
    if meta.get('pipeline_invoked') is not (ninputs>0):issues.append('native_pipeline_invocation_state_changed')
    if ninputs>0 and (meta.get('pipeline_completed') is not True or meta.get('pipeline_failure') is not None or meta.get('native_dataframe_is_full_export') is not True or glob.get('native_dataframe_complete') is not True or meta.get('native_pandas_rows')!=ninputs):issues.append('native_pipeline_or_export_incomplete')
    if ninputs==0 and (meta.get('pipeline_completed') is not False or meta.get('native_dataframe_is_full_export') is not False or glob.get('native_dataframe_complete') is not False):issues.append('native_pipeline_completed_without_inputs')
    frame=meta.get('native_dataframe_artifact',{})
    if frame.get('path')!='native_dataframe.private.json' or frame.get('sha256')!=bound.get(prefix+'native_dataframe.private.json',{}).get('sha256'):issues.append('native_dataframe_not_completion_bound')
    if any(x.get('pipeline_failure')!=meta.get('pipeline_failure') for x in records):issues.append('native_pipeline_failure_record_disagrees')
    if ninputs/n<p['minimum_evaluable_fraction']:issues.append('prespecified_input_evaluable_fraction_failed')
    if audit.get('capture_errors'):issues.append('engine_audit_capture_incomplete')
    metrics={'requested_attempts':n,'input_evaluable_count':ninputs,'input_evaluable_fraction':ninputs/n,'native_callback_count':ncallback,'native_valid_count':valid,'native_post_opt_valid_count':post,'native_graph_consistent_count':graph,'engine_evidence_complete_count':nengine,'native_evaluation_audit_complete_count':ncomplete,'native_evaluation_audit_complete_fraction':ncomplete/n,'native_valid_fraction_all_requested':valid/n,'native_post_opt_valid_fraction_all_requested':post/n,'native_graph_consistent_fraction_all_requested':graph/n}
    return issues,records,metrics
