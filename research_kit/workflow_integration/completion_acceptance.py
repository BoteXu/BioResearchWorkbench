"""Bounded proof review for new native routes; never execute an analysis."""
from server.completion_contracts import ROUTES,COMMON_ROLES

def inspect_completion(request,receipt,local,load,rows):
    mode=request['backend'];p=request['parameters'];issues=[]
    for role in COMMON_ROLES:
        if role not in local:issues.append('completion_summary_not_selected:'+role)
    if issues:return issues
    diag=load(local['diagnostics']);proof=load(local['result_channel_proof'])
    if diag.get('mode')!=mode or diag.get('software_versions')!=p['software_versions'] or diag.get('data_kind')!=ROUTES[mode]['kind']:issues.append('native_mode_version_or_kind_changed')
    if not isinstance(diag.get('metrics'),dict) or not diag['metrics']:issues.append('actual_native_numeric_QC_missing')
    if proof.get('schema')!='native-completion-proof/1' or proof.get('mode')!=mode or proof.get('input_semantics')!=ROUTES[mode]['kind']:issues.append('native_full_result_proof_contract_changed')
    output_records=receipt.get('outputs',[]);bound={r['path']:r for r in output_records};covered=set();by_role={}
    for item in proof.get('outputs',[]):
        path=item.get('path');native=bound.get(path)
        if path in covered:issues.append('duplicate_native_proof_path')
        covered.add(path);by_role.setdefault(item.get('role'),[]).append(item)
        if not native or any(native.get(k)!=item.get(k) for k in ['role','sha256','bytes']):issues.append('native_full_file_proof_not_bound:'+str(path));continue
        if item.get('data_kind')!=ROUTES[mode]['kind']:issues.append('native_result_kind_not_preserved:'+path)
        if 'columns' in item:
            if type(item.get('rows')) is not int or item['rows']<0 or not item['columns'] or len(set(item['columns']))!=len(item['columns']):issues.append('invalid_full_table_denominator:'+path)
            preview=item.get('preview',{});pr=bound.get(preview.get('path'))
            if not pr or pr.get('sha256')!=preview.get('sha256') or pr.get('role')!='preview_'+item['role']:issues.append('native_preview_not_bound_to_full_file:'+path)
            pp=local.get('_by_path',{}).get(preview.get('path'))
            full=local.get('_by_path',{}).get(path)
            if pp:
                header,data=rows(pp)
                if header!=preview.get('columns') or len(data)!=preview.get('rows') or preview.get('rows')!=min(item['rows'],40) or header!=item['columns'][:100]:issues.append('native_preview_shape_or_axis_changed:'+path)
            elif not full:issues.append('native_table_needs_full_file_or_bound_preview:'+path)
    for role in ROUTES[mode]['roles']+['primary_results']:
        if role not in by_role:issues.append('actual_native_scientific_channel_missing:'+role)
    if mode=='csi_result_import' and diag.get('metrics',{}).get('fresh_network_calls')!=0:issues.append('CSI_import_must_not_submit_private_spectra')
    if mode in {'prnet_predict','squidiff_predict','stack_incontext','scdiffusion_generate'}:
        identity=by_role.get('prediction_identity',[]);matrix=by_role.get('prediction_matrix',[])
        if len(identity)!=1 or len(matrix)!=1 or identity[0].get('rows')!=matrix[0].get('rows'):issues.append('prediction_identity_matrix_denominator_mismatch')
    if mode=='cellnavi_drivers':
        if len(by_role.get('driver_logits',[]))!=1 or by_role['driver_logits'][0].get('rows')!=diag.get('metrics',{}).get('queries'):issues.append('driver_ranking_query_axis_not_bound')
    return sorted(set(issues))
