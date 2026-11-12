"""Prepare only selected candidate identities for existing docking/QC routes. Never dispatch."""
import re
from contracts import digest,read,sha,sources,selected
from server.return_binding import receipt_index
def prepare_link(request,receipt,selection,context_path=None,eligibility_path=None,return_review=None,*,generation_review=None):
    if request.get('method')=='paper_native_evaluation':raise ValueError('Relaxed independent-modality evaluation has no docking-eligible output; select original qualified generation/identity source')
    if receipt.get('state')!='COMPLETED' or type(receipt.get('exit_code')) is not int or receipt['exit_code']!=0 or receipt.get('plan_sha256')!=request.get('plan_sha256') or receipt.get('source_sha256')!=request.get('source_sha256'):raise ValueError('Actual completed exact source request required')
    body={k:v for k,v in request.items() if k!='plan_sha256'};body['server_execution_authorized']=False
    if request.get('source_sha256')!=sources() or digest(body)!=request.get('plan_sha256'):raise ValueError('Source adapter/plan changed; old handoff acceptance expired')
    if selection.get('public_upload') is not False or selection.get('experimental_validation') is not False or selection.get('target_workflow') not in ('molecular_qc','pose_qc','vina_docking'):raise ValueError('Only private existing downstream QC/docking workflows allowed')
    if selection.get('review_sha256')!=digest({k:v for k,v in selection.items() if k!='review_sha256'}):raise ValueError('Exact reviewed selected-candidate handoff required')
    needed=('protonation_basis','chemical_state_review','source_frame_id','limitations')
    if not selection.get('scientific_context') or any(not selection['scientific_context'].get(k) for k in needed):raise ValueError('New state/coordinate/protonation review required')
    if selection['target_workflow'] in ('pose_qc','vina_docking') and any(not re.fullmatch('[a-f0-9]{64}',str(selection['scientific_context'].get(k,''))) for k in ('receptor_sha256','site_sha256')):raise ValueError('Actual receptor and site SHA256 identities required for downstream docking/pose QC')
    bound,issues=receipt_index(receipt.get('outputs',[]))
    if issues:raise ValueError('Source output receipt is malformed')
    inputs={r['id']:r for r in request['inputs']}
    if context_path is None or sha(context_path)!=inputs.get('context',{}).get('sha256'):raise ValueError('Exact source scientific context required')
    context=read(context_path)
    if selection['scientific_context']['source_frame_id']!=context['frame_id']:raise ValueError('Source coordinate frame changed during handoff')
    if selection['target_workflow']=='pose_qc' and (context.get('frame_kind')!='docking_complex' or any(context.get(k)!=selection['scientific_context'].get(k) for k in ('receptor_sha256','site_sha256'))):raise ValueError('Pose QC requires an actual same-receptor/site complex frame; prepare and review alignment first')
    if eligibility_path is None or sha(eligibility_path)!=bound.get('eligible_candidate_outputs.private.json',{}).get('sha256'):raise ValueError('Actual source candidate QC-eligibility record required')
    eligibility=read(eligibility_path);eligible={r['path']:r for r in eligibility}
    if len(eligible)!=len(eligibility):raise ValueError('Duplicate source eligibility identities')
    rows=selection.get('candidates',[]);paths=[r.get('path') for r in rows]
    if not paths or len(paths)!=len(set(paths)):raise ValueError('Select explicit unique source SDF records')
    from pathlib import Path
    from acceptance import inspect
    if return_review is not None and generation_review is not None:raise ValueError('Use a single explicit return-review binding')
    review=return_review if return_review is not None else generation_review
    if not isinstance(review,dict) or set(review)!={'request_path','returned_root','selected_return_files'}:raise ValueError('Every candidate route requires a fresh complete bounded return review before handoff')
    request_path=Path(review['request_path']);returned_root=Path(review['returned_root'])
    if read(request_path)!=request or read(returned_root/'receipt.private.json')!=receipt:raise ValueError('Fresh return review refers to another request/receipt')
    if receipt.get('request_sha256')!=sha(request_path) or receipt.get('method')!=request.get('method') or receipt.get('run_id')!=request.get('run_id') or receipt.get('host')!=request.get('expected_host') or receipt.get('public_upload') is not False:raise ValueError('Fresh return request, run, host or privacy identity differs')
    expected_inputs={x['id']:x['sha256'] for x in request['inputs']};actual_inputs={x['id']:x['sha256'] for x in receipt.get('inputs',[])}
    if expected_inputs!=actual_inputs or len(actual_inputs)!=len(receipt.get('inputs',[])):raise ValueError('Fresh return input identity denominator differs')
    acceptance=inspect(request_path,returned_root,review['selected_return_files'])
    if acceptance['state']!='RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW':raise ValueError('Complete source return review is on HOLD')
    constraints_verified=request['method'] in ('shepherd2_generate','prepare_generated_identities')
    for row in rows:
        record=bound.get(row['path'])
        if not row['path'].endswith('.sdf') or record is None or record['sha256']!=row.get('sha256') or record['bytes']!=row.get('bytes') or row['path'] not in eligible or any(eligible[row['path']].get(k)!=row.get(k) for k in ('sha256','bytes','candidate_id','parent_id','microstate_id')):raise ValueError('Candidate does not match actual source SDF identity, chemical state or QC eligibility')
        sdf=selected(returned_root,row['path'])
        if sdf.stat().st_size!=row['bytes'] or sha(sdf)!=row['sha256']:raise ValueError('Selected source SDF changed after the returned receipt; handoff refused')
        if row['parent_id']=='UNASSESSED_GENERATED_PARENT' and selection['target_workflow']!='molecular_qc':raise ValueError('Generated graph requires actual parent/state standardization in molecular_qc before docking')
        if request['method']=='shepherd2_generate' and eligible[row['path']].get('constraints_passed') is not True:raise ValueError('Candidate lacks successful actual-chemistry/point constraint QC')
        if request['method']=='prepare_generated_identities':
            if selection['target_workflow']!='molecular_qc':raise ValueError('Computed identity grouping first requires new existing molecular QC, not direct docking dispatch')
            if eligible[row['path']].get('constraints_preserved_by_exact_graph_atom_order_and_coordinate_invariance') is not True:raise ValueError('Original state/pose constraint invariance is unverified')
    target_inputs=[]
    if request['method']=='shepherd2_generate':
        for row in rows:
            e=eligible[row['path']]
            target_inputs.append({'input_role':'ligands','source_path':row['path'],'sha256':row['sha256'],'bytes':row['bytes'],'state_id':e['state_id'],'id_property':'BRW_STATE_ID','parent_property':'BRW_PARENT_ID','require_assigned_stereochemistry':True,'constraint_report_path':e['constraint_report_path'],'constraint_report_sha256':e['constraint_report_sha256'],'generation_contract_sha256':e['generation_contract_sha256'],'target_preparation_state':'EXACT_INPUT_BINDING_REQUIRES_NEW_CORE_PROJECT_AND_QC'})
    elif request['method']=='prepare_generated_identities':
        for row in rows:
            e=eligible[row['path']]
            target_inputs.append({'input_role':'ligands','source_path':row['path'],'sha256':row['sha256'],'bytes':row['bytes'],'state_id':e['state_id'],'id_property':'BRW_STATE_ID','parent_property':'BRW_PARENT_ID','require_assigned_stereochemistry':True,'identity_report_path':e['identity_report_path'],'identity_report_sha256':e['identity_report_sha256'],'identity_policy_sha256':e['identity_policy_sha256'],'source_constraint_report_path':e['source_constraint_report_path'],'source_constraint_report_sha256':e['source_constraint_report_sha256'],'computed_group_is_physiological_state':False,'target_preparation_state':'EXACT_INPUT_BINDING_REQUIRES_NEW_CORE_PROJECT_AND_QC'})
    return {'state':'PREPARED_NOT_DISPATCHED','source_plan_sha256':request['plan_sha256'],'selected_candidates':rows,'existing_core_input_bindings':target_inputs,'target_workflow':selection['target_workflow'],'scientific_context':selection['scientific_context'],'new_input_QC_required':True,'new_pose_validation_required':True,'complete_source_return_reviewed':True,'generation_constraint_return_reviewed':constraints_verified,'required_downstream_checks':['parent_microstate_standardization_review_not_automatically_done_by_core_molecular_QC','preserve_source_atom_and_point_mappings','recheck_scaffold_and_priority_constraints_after_preparation','pose_clashes_strain_and_docking_controls'],'experimental_validation':False,'automatic_submission':False,'public_upload':False}
