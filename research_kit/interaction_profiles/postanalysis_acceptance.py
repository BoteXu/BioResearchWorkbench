"""Bounded post-analysis evidence checks, no local RDKit/xTB/NumPy imports."""
from pathlib import Path
import math
from collections import Counter
from contracts import read,sha,digest,selected,sources,validate
from postanalysis_contracts import lineage_spec
from server.return_binding import receipt_index,proof_issues,preview_issues

MAX=8_000_000
CONSISTENT='RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW'
SNAPSHOTS=('origin_lineage.private.json','origin_request_snapshot.private.json','origin_receipt_snapshot.private.json','origin_generation_contract_snapshot.private.json')

def small(f):
    if not 0<Path(f).stat().st_size<=MAX:raise ValueError('Bounded JSON summary <=8 MB required')
    return read(f)

def _origin(v,content,root,spec,allow_quality_hold=False):
    issues=[];prefix=v+'/'
    req=content[prefix+'origin_request_snapshot.private.json'];rc=content[prefix+'origin_receipt_snapshot.private.json'];line=content[prefix+'origin_lineage.private.json']
    if sha(selected(root,prefix+'origin_request_snapshot.private.json'))!=spec['origin_request_sha256'] or sha(selected(root,prefix+'origin_receipt_snapshot.private.json'))!=spec['origin_receipt_sha256']:issues.append('origin_request_or_receipt_snapshot_changed')
    body={k:x for k,x in req.items() if k!='plan_sha256'};body['server_execution_authorized']=False
    if req.get('method')!='shepherd2_generate' or digest(body)!=req.get('plan_sha256') or req.get('source_sha256')!=sources():issues.append('origin_generation_plan_or_source_changed')
    if rc.get('plan_sha256')!=req.get('plan_sha256') or rc.get('request_sha256')!=spec['origin_request_sha256'] or rc.get('state')!='COMPLETED' or type(rc.get('exit_code')) is not int or rc['exit_code']!=0 or rc.get('public_upload') is not False:issues.append('origin_receipt_not_completed_exact_generation')
    if rc.get('source_sha256')!=req.get('source_sha256') or any(rc.get(k)!=req.get(k if k!='host' else 'expected_host') for k in ('method','run_id','host')):issues.append('origin_run_host_or_source_identity_changed')
    source_inputs={x['id']:x['sha256'] for x in req.get('inputs',[])};actual_inputs=rc.get('inputs',[])
    if {x['id']:x['sha256'] for x in actual_inputs}!=source_inputs or len(actual_inputs)!=len(source_inputs):issues.append('origin_actual_input_denominator_changed')
    if source_inputs.get('context')!=sha(selected(root,'source_context.private.json')):issues.append('postanalysis_context_does_not_match_exact_origin_context')
    output,invalid=receipt_index(rc.get('outputs'));issues.extend('origin_'+x for x in invalid)
    contract=output.get(spec['origin_variant']+'/generation_contract.private.json',{})
    if sha(selected(root,prefix+'origin_generation_contract_snapshot.private.json'))!=contract.get('sha256'):issues.append('origin_generation_contract_snapshot_changed')
    if line.get('lineage_spec')!=spec:issues.append('origin_lineage_spec_changed')
    review=line.get('source_review',{});quality={'prespecified_chemical_valid_fraction_failed','prespecified_constraint_pass_fraction_failed'}
    quality_hold=allow_quality_hold and review.get('state')=='HOLD' and isinstance(review.get('issues'),list) and bool(review['issues']) and all(x in quality or x.startswith('prespecified_actual_QC_gate_failed:') for x in review['issues'])
    if not quality_hold and (review.get('state')!=CONSISTENT or review.get('issues')!=[]):issues.append('origin_complete_source_review_not_accepted')
    if line.get('frame_id')!=content['source_context.private.json'].get('frame_id'):issues.append('origin_coordinate_frame_changed')
    n=req.get('parameters',{}).get('n_samples')
    if type(n) is not int or n<1:raise ValueError('Origin requested sampling denominator invalid')
    return issues,n

def inspect_postanalysis(request_path,root,names):
    r=small(request_path);validate({**r,'server_execution_authorized':False});receipt=small(selected(root,'receipt.private.json'));issues=[]
    body={k:v for k,v in r.items() if k!='plan_sha256'};body['server_execution_authorized']=False
    if digest(body)!=r.get('plan_sha256') or receipt.get('request_sha256')!=sha(request_path) or receipt.get('plan_sha256')!=r.get('plan_sha256'):issues.append('request_or_plan_changed')
    if receipt.get('source_sha256')!=r.get('source_sha256') or r.get('source_sha256')!=sources():issues.append('reviewed_source_expired')
    if receipt.get('state')!='COMPLETED' or type(receipt.get('exit_code')) is not int or receipt['exit_code']!=0:issues.append('scientific_run_not_completed')
    if any(receipt.get(k)!=r.get(k if k!='host' else 'expected_host') for k in ('method','run_id','host')) or receipt.get('public_upload') is not False:issues.append('source_identity_or_privacy_changed')
    expected={x['id']:x['sha256'] for x in r['inputs']};inputs=receipt.get('inputs',[])
    if {x['id']:x['sha256'] for x in inputs}!=expected or len(inputs)!=len(expected):issues.append('actual_input_denominator_changed')
    bound,invalid=receipt_index(receipt.get('outputs'));issues.extend(invalid)
    variants={'primary':r['parameters']['seed'],**{x['label']:x['seed'] for x in r['sensitivity_variants']}}
    native=r['method']=='paper_native_evaluation';role='native_evaluation' if native else 'identity_preparation'
    required={'variant_diagnostics.private.json','full_result_audit.private.json','boundaries.private.json','source_context.private.json','source_structures.private.json','eligible_candidate_outputs.private.json'}|{v+'/'+x for v in variants for x in SNAPSHOTS}|{v+'/'+role+'.preview.private.json' for v in variants}
    if native:
        required|={v+'/'+x for v in variants for x in ('native_global_metrics.private.json','callback_results.private.json','native_records.private.json','reference_binding.private.json','engine_audit.private.json','evaluation_metadata.private.json','software_identity.private.json')}
    else:required|={v+'/'+x for v in variants for x in ('identity_policy.private.json','identity_records.private.json','parent_groups.private.json','postanalysis_boundaries.private.json','origin_eligibility_snapshot.private.json')}
    if not isinstance(names,list) or len(names)!=len(set(names)) or not required<=set(names):raise ValueError('Select every bounded source-lineage, complete row record, preview, engine and policy summary')
    content={};total=0
    for name in names:
        f=selected(root,name);total+=f.stat().st_size
        if name not in bound or sha(f)!=bound[name]['sha256'] or f.stat().st_size!=bound[name]['bytes'] or total>32_000_000:raise ValueError('Unbound/changed/unbounded selected return')
        content[name]=small(f)
    for name,role_in in (('source_context.private.json','context'),('source_structures.private.json','structure_manifest')):
        if sha(selected(root,name))!=expected[role_in]:issues.append('copied_source_context_or_lineage_changed')
    spec=lineage_spec(content['source_structures.private.json'],r['method']);eligible=content['eligible_candidate_outputs.private.json'];eligible_paths=[x.get('path') for x in eligible]
    boundaries=content['boundaries.private.json']
    if boundaries.get('method')!=r['method'] or boundaries.get('scientific_acceptance')!='NOT_ESTABLISHED' or boundaries.get('public_upload') is not False or any(boundaries.get(k) is not True for k in ('postanalysis_of_exact_generation_origin','paper_evaluation_scores_do_not_grant_docking_eligibility','computed_parent_is_not_physiological_state_prediction','technical_rechecks_are_not_independent_molecules')) or boundaries.get('identity_grouping_preserves_original_chemical_state_and_pose') is not (not native):issues.append('postanalysis_scope_or_replication_boundary_changed')
    if len(eligible_paths)!=len(set(eligible_paths)):issues.append('duplicate_candidate_eligibility_record')
    for e in eligible:
        rec=bound.get(e.get('path'),{})
        if e.get('variant') not in variants or not e.get('path','').startswith(e.get('variant','')+'/') or e.get('eligibility')!='REQUIRES_NEW_DOWNSTREAM_QC' or any(e.get(k)!=rec.get(k) for k in ('sha256','bytes')) or not rec:issues.append('candidate_eligibility_not_bound_to_actual_SDF')
    if native and eligible:issues.append('native_optimized_evaluation_cannot_grant_docking_eligibility')
    proof=content['full_result_audit.private.json'];rules={role:{'required':['candidate_id','state'],'empty_valid':False}}
    issues.extend(proof_issues(proof,bound,variants,[role],'full_server_stream_scan_not_independent_scientific_validation',rules))
    diag=content['variant_diagnostics.private.json']
    if not isinstance(diag,list) or len(diag)!=len(variants) or {x.get('variant') for x in diag}!=set(variants):raise ValueError('Complete unique actual variant diagnostics required')
    diag={x['variant']:x for x in diag}
    for v,seed in variants.items():
        pi,n=_origin(v,content,root,spec,allow_quality_hold=native);issues.extend(pi)
        if diag[v].get('seed')!=seed:issues.append('actual_technical_seed_changed')
        if diag[v].get('scientific_acceptance')!='NOT_ESTABLISHED' or diag[v].get('biological_replication_established') is not False:issues.append('postanalysis_diagnostics_scope_changed')
        if native:
            from native_evaluation_reports import inspect_native_variant
            vi,records,metrics=inspect_native_variant(v,content,bound,r['parameters'],spec,n)
            meta=content[v+'/evaluation_metadata.private.json']
            if diag[v].get('pipeline_failure')!=meta.get('pipeline_failure') or diag[v].get('metrics',{}).get('pipeline_completed') is not meta.get('pipeline_completed'):issues.append('native_pipeline_summary_disagrees')
        else:
            # Every candidate-specific identity report must be selected, including failures.
            if any(v+'/'+cid+'.identity.private.json' not in content for cid in spec['candidate_ids']):raise ValueError('All requested identity reports required')
            from identity_reports import inspect_identity_variant
            vi,records,metrics=inspect_identity_variant(v,content,bound,r['parameters'],spec,[x for x in eligible if x['variant']==v])
            boundary=content[v+'/postanalysis_boundaries.private.json']
            if any(boundary.get(k) is not True for k in ('original_graph_and_pose_preserved_for_prepared_records','parent_groups_are_computational','new_downstream_QC_required','seeds_are_technical_rechecks_not_independent_molecules')) or any(boundary.get(k) is not False for k in ('pH_or_pKa_predicted','canonical_tautomer_is_most_stable_asserted','public_upload')) or boundary.get('scientific_acceptance')!='NOT_ESTABLISHED':issues.append('identity_grouping_scope_changed')
        issues.extend(vi)
        for key,value in metrics.items():
            reported=diag[v].get('metrics',{}).get(key)
            if type(reported) not in (int,float) or not math.isfinite(reported) or not math.isclose(reported,value,rel_tol=1e-12,abs_tol=1e-12):issues.append('postanalysis_metrics_disagree_with_complete_records:'+key)
        for gate in r['acceptance_rules']:
            value=metrics.get(gate['metric'])
            if value is None or not {'ge':value>=gate['bound'],'le':value<=gate['bound'],'eq':value==gate['bound']}[gate['operator']]:issues.append('prespecified_actual_QC_gate_failed:'+gate['metric'])
        proofs=[x for x in proof if x.get('variant')==v and x.get('role')==role]
        if len(proofs)!=1:continue
        full=proofs[0];preview=content[v+'/'+role+'.preview.private.json'];issues.extend(preview_issues(preview,full));states={x['candidate_id']:x['state'] for x in records}
        all_values=[{k:str(x.get(k) if x.get(k) is not None else '') for k in full['columns']} for x in records]
        if full.get('row_values_binding_sha256')!=digest(all_values):issues.append('complete_postanalysis_table_values_disagree_with_full_records')
        if full.get('candidate_row_counts')!={x:1 for x in states} or full.get('candidate_states')!=states or full.get('status_counts')!=dict(Counter(states.values())) or full.get('rows')!=len(states):issues.append('complete_postanalysis_denominator_or_state_changed')
        by_id={x['candidate_id']:x for x in records};seen=set()
        for row in preview['preview_rows']:
            cid=row.get('candidate_id')
            if cid in seen or cid not in states or row.get('state')!=states.get(cid):issues.append('postanalysis_preview_identity_or_state_changed')
            seen.add(cid)
            for field in ('parent_id','microstate_id','state_id','source_sdf_sha256','prepared_sdf_sha256','identity_policy_sha256'):
                if field in row and str(row[field] or '')!=str(by_id.get(cid,{}).get(field) or ''):issues.append('postanalysis_preview_chemical_identity_changed')
    return {'state':'HOLD' if issues else CONSISTENT,'issues':sorted(set(issues)),'scientific_acceptance':'NOT_ESTABLISHED','current_server_environment_verified':False,'public_upload':False}
