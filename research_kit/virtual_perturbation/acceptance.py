"""Bounded local return inspection. Never imports or runs a scientific engine."""
from pathlib import Path
from contracts import read,sha,digest,relative,source_hashes,catalog
from server.return_binding import receipt_index,proof_issues,preview_issues,algebra_issues,comparison_scope

MAX=8_000_000
def small(path):
    if not 0<Path(path).stat().st_size<=MAX:raise ValueError('Select a nonempty bounded returned summary <=8 MB')
    return read(path)

def inspect(request_path,return_root,selected):
    request=small(request_path);root=Path(return_root);receipt=small(relative(root,'receipt.private.json'));issues=[]
    body={k:v for k,v in request.items() if k!='plan_sha256'};body['server_execution_authorized']=False
    if digest(body)!=request.get('plan_sha256'):issues.append('reviewed_plan_hash_invalid')
    if receipt.get('method')!=request.get('method') or receipt.get('run_id')!=request.get('run_id'):issues.append('method_or_run_identity_changed')
    if receipt.get('state')!='COMPLETED' or receipt.get('exit_code')!=0:issues.append('actual_run_not_completed')
    if receipt.get('request_sha256')!=sha(request_path) or receipt.get('plan_sha256')!=request.get('plan_sha256'):issues.append('request_or_plan_changed')
    if receipt.get('source_sha256')!=request.get('source_sha256') or request.get('source_sha256')!=source_hashes():issues.append('reviewed_source_expired')
    expected={r['id']:r['sha256'] for r in request['inputs']};actual={r['id']:r['sha256'] for r in receipt.get('inputs',[])}
    if expected!=actual or len(actual)!=len(receipt.get('inputs',[])):issues.append('scientific_inputs_changed_or_duplicated')
    if receipt.get('host')!=request.get('expected_host') or request.get('node_role')!='compute':issues.append('compute_host_mismatch')
    if len(selected)!=len(set(selected)):issues.append('duplicate_selected_return')
    records=receipt.get('outputs',[]);bound,record_issues=receipt_index(records);issues.extend(record_issues)
    if len(bound)!=len(records):issues.append('duplicate_output_receipt')
    if receipt.get('measurement_state')!='predicted' or receipt.get('public_upload') is not False:issues.append('prediction_or_privacy_boundary_changed')
    spec=catalog()['methods'][request['method']];variants={'primary'}|{v['label'] for v in request['sensitivity_variants']}
    required={'full_result_audit.private.json','sensitivity_comparison.private.json','claim_boundaries.private.json','backend_identity.private.json'}|{v+'/diagnostics.private.json' for v in variants}|{'primary/'+role+'.preview.private.json' for role in spec['roles']}
    if not required<=set(selected):raise ValueError('Return the bounded full-denominator proof, real sensitivity comparison and claim boundaries')
    contents={};total=0
    for name in selected:
        p=relative(root,name);total+=p.stat().st_size
        if total>32_000_000 or name not in bound or sha(p)!=bound[name]['sha256'] or p.stat().st_size!=bound[name]['bytes']:raise ValueError('Selected return is unbound, changed or exceeds bounded local scope')
        contents[name]=small(p)
    if contents['backend_identity.private.json'].get('code_sha256')!=request['parameters']['expected_backend_code_sha256']:issues.append('specialist_code_changed')
    import math
    for variant in variants:
        d=contents[variant+'/diagnostics.private.json']
        if d.get('fit_completed') is not True or not d.get('metrics') or any(type(x) not in (float,int) or not math.isfinite(x) for x in d['metrics'].values()):issues.append('actual_numerical_fit_diagnostics_missing')
    for gate in request['acceptance_rules']:
        d=contents.get(gate['variant']+'/diagnostics.private.json',{}).get('metrics',{});v=d.get(gate['metric']);b=gate['bound']
        if type(v) not in (int,float) or not {'ge':v>=b,'le':v<=b,'eq':v==b}[gate['operator']]:issues.append('prespecified_measured_gate_failed:'+gate['metric'])
    proof=contents['full_result_audit.private.json'];issues.extend(proof_issues(proof,bound,variants,spec['roles'],'full_server_stream_scan_not_independent_scientific_validation',spec['output_rules']));wanted={(v,role) for v in variants for role in spec['roles']};seen={(x['variant'],x['role']) for x in proof}
    if seen!=wanted or len(proof)!=len(wanted):issues.append('missing_full_result_denominators')
    for row in proof:
        if row.get('role')==spec['roles'][0]:
            units=row.get('unit_row_counts',{})
            if set(units)!=set(request['parameters']['evaluation_units']) or any(type(n) is not int or n<1 for n in units.values()) or sum(units.values())!=row.get('rows'):issues.append('primary_unit_denominator_incomplete')
        b=bound.get(row['path'],{})
        if row.get('sha256')!=b.get('sha256') or row.get('bytes')!=b.get('bytes') or type(row.get('rows')) is not int or row['rows']<0:issues.append('full_result_proof_changed')
        if row.get('scope')!='full_server_stream_scan_not_independent_scientific_validation':issues.append('unknown_full_result_check_scope')
        role=row['role'];rule=spec['output_rules'].get(role,{})
        if not set(rule.get('required',[]))<=set(row['columns']) or row['rows']==0 and not rule.get('empty_valid',False):issues.append('result_schema_or_denominator_failed')
        preview_name=row['variant']+'/'+role+'.preview.private.json'
        if preview_name in contents:
            p=contents[preview_name];issues.extend(preview_issues(p,row))
            if p.get('full_result_sha256')!=row['sha256'] or p.get('full_rows')!=row['rows'] or len(p.get('preview_rows',[]))>40:issues.append('preview_not_bound_to_full_result')
            keys=set()
            for values in p.get('preview_rows',[]):
                if not set(rule['required'])<=set(values):issues.append('preview_schema_incomplete');continue
                issues.extend(algebra_issues(values,rule))
                identity=tuple(values[k] for k in rule.get('keys',[]))
                if identity in keys or not all(identity):issues.append('preview_duplicate_or_missing_identity')
                keys.add(identity)
                for column in rule.get('numeric',[]):
                    raw=values[column]
                    if raw in ('','NA','NaN') and rule.get('allow_missing',False):continue
                    try:
                        number=float(raw)
                        if not math.isfinite(number) or column in rule.get('probabilities',[]) and not 0<=number<=1:raise ValueError()
                    except (ValueError,TypeError):issues.append('preview_invalid_numerical_value')
    comparison=contents['sensitivity_comparison.private.json']
    if {r.get('variant') for r in comparison}!=variants-{'primary'}:issues.append('sensitivity_results_missing')
    identities=[(r.get('variant'),r.get('unit_id')) for r in comparison];expected_pairs={(v,u) for v in variants-{'primary'} for u in request['parameters']['evaluation_units']}
    if len(identities)!=len(expected_pairs) or set(identities)!=expected_pairs:issues.append('sensitivity_unit_denominators_missing_or_duplicate')
    for r in comparison:
        variant=next((v for v in request['sensitivity_variants'] if v['label']==r.get('variant')),None)
        if variant is None or r.get('comparison_scope')!=comparison_scope(variant['parameters'],spec) or r.get('scientific_robustness_established') is not False:issues.append('sensitivity_scope_overclaimed')
        for name in ('shared_features','primary_features','alternate_features','primary_missing_in_alternate','alternate_new_features','top_k'):
            if type(r.get(name)) is not int or r[name]<0:issues.append('invalid_comparison_denominator')
        if all(type(r.get(k)) is int for k in ('shared_features','primary_features','alternate_features','primary_missing_in_alternate','alternate_new_features')) and (r['shared_features']+r['primary_missing_in_alternate']!=r['primary_features'] or r['shared_features']+r['alternate_new_features']!=r['alternate_features']):issues.append('inconsistent_comparison_coverage')
        if r.get('biological_replication_established') is not False or r.get('comparison_score')!=spec['comparison_score'] or r.get('shared_features',0)<1:issues.append('invalid_sensitivity_interpretation')
    boundary=contents['claim_boundaries.private.json']
    if boundary.get('measurement_state')!='predicted' or any(boundary.get(k) is not False for k in ('real_KO_observed','causal_effect_established','survival_benefit_established')):issues.append('prediction_promoted_to_causal_or_observed_evidence')
    return {'state':'HOLD' if issues else 'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW','issues':sorted(set(issues)),'method':request['method'],'source_review_current':request.get('source_sha256')==source_hashes(),'current_server_environment_verified':False,'live_server_observed':False,'scientific_acceptance':'NOT_ESTABLISHED','full_results_check':'hash-bound full-server scan, bounded preview inspected only if selected; full scientific results not recomputed locally','public_upload':False}
