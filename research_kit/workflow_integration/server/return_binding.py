"""Strict receipt/proof identity contracts. Stdlib only; scientific results are not recalculated."""
import math,re

def safe_path(name):
    return isinstance(name,str) and bool(name) and ':' not in name and '\\' not in name and not name.startswith('/') and all(s not in ('','.','..') for s in name.split('/'))

def receipt_index(records,require_role=False):
    issues=[];bound={}
    if not isinstance(records,list):return {},['output_manifest_not_a_list']
    for row in records:
        if not isinstance(row,dict) or not safe_path(row.get('path')):issues.append('invalid_output_path');continue
        if row['path'] in bound:issues.append('duplicate_output_receipt')
        if not re.fullmatch('[a-f0-9]{64}',str(row.get('sha256',''))) or type(row.get('bytes')) is not int or row['bytes']<1:issues.append('invalid_output_identity')
        if require_role and (not isinstance(row.get('role'),str) or not row['role']):issues.append('output_role_missing')
        bound[row['path']]=row
    return bound,issues

def proof_issues(proof,bound,variants,roles,scope,rules=None,preview_kind='json'):
    issues=[];wanted={(v,r) for v in variants for r in roles};seen=[]
    if not isinstance(proof,list):return ['full_result_proof_not_a_list']
    for row in proof:
        if not isinstance(row,dict):issues.append('malformed_full_result_proof');continue
        identity=(row.get('variant'),row.get('role'));seen.append(identity)
        if identity not in wanted:issues.append('unexpected_full_result_identity');continue
        canonical=identity[0]+'/'+identity[1]+'.tsv';record=bound.get(canonical)
        if row.get('path')!=canonical or record is None:issues.append('full_result_path_not_canonical_or_registered')
        if not re.fullmatch('[a-f0-9]{64}',str(row.get('sha256',''))) or type(row.get('bytes')) is not int or row['bytes']<1 or record is None or any(row.get(k)!=record.get(k) for k in ('sha256','bytes')):issues.append('full_result_proof_changed')
        columns=row.get('columns');n=row.get('rows')
        if type(n) is not int or n<0 or not isinstance(columns,list) or not columns or any(not isinstance(c,str) or not c for c in columns) or len(columns)!=len(set(columns)):issues.append('malformed_full_result_denominator');continue
        if row.get('scope')!=scope:issues.append('unknown_full_result_check_scope')
        rule=(rules or {}).get(identity[1],{})
        if not set(rule.get('required',[]))<=set(columns) or n==0 and not rule.get('empty_valid',rule.get('allow_empty',False)):issues.append('result_schema_or_denominator_failed')
        preview=identity[0]+'/'+identity[1]+('.preview.private.json' if preview_kind=='json' else '.preview.tsv')
        if preview not in bound:issues.append('preview_not_registered_in_completion_receipt')
        if preview_kind=='tsv' and (row.get('preview_path')!=preview or bound.get(preview,{}).get('sha256')!=row.get('preview_sha256') or row.get('preview_rows')!=min(40,n)):issues.append('preview_proof_identity_changed')
    if len(seen)!=len(wanted) or set(seen)!=wanted:issues.append('missing_or_duplicate_full_result_denominators')
    return sorted(set(issues))

def preview_issues(preview,proof):
    if not isinstance(preview,dict):return ['malformed_preview']
    rows=preview.get('preview_rows');n=proof.get('rows');issues=[]
    if not isinstance(rows,list) or type(n) is not int or len(rows)!=min(40,n):issues.append('preview_row_count_mismatch')
    if preview.get('is_full_result') is not (type(n) is int and n<=40):issues.append('preview_completeness_flag_changed')
    if preview.get('full_result_sha256')!=proof.get('sha256') or preview.get('full_rows')!=n:issues.append('preview_not_bound_to_full_result')
    return issues

def finite(value):
    if isinstance(value,bool):raise ValueError('Boolean is not a numerical result')
    n=float(value)
    if not math.isfinite(n):raise ValueError('Nonfinite result')
    return n

def algebra_issues(values,rule):
    issues=[]
    for item in rule.get('algebra',[]):
        needed=[item[k] for k in ('left','right','result')]
        if any(values.get(k) in (None,'','NA','NaN') for k in needed):
            if not rule.get('allow_missing',False):issues.append('algebra_missing_value')
            continue
        try:
            a,b,c=[finite(values[k]) for k in needed];expected=b-a if item['operation']=='right_minus_left' else b/a if item['operation']=='right_over_left' and a!=0 else None
            if expected is not None and not math.isclose(c,expected,abs_tol=1e-7,rel_tol=1e-6):issues.append('inconsistent_reported_difference_or_ratio')
        except (TypeError,ValueError,OverflowError):issues.append('invalid_algebra_value')
    return issues

def comparison_scope(changed,spec):
    keys=set(changed)
    if keys=={'seed'}:return 'random_seed_reproducibility_only'
    if keys<=set(spec.get('precision_only_parameters',[]))|{'seed'}:return 'numerical_precision_and_randomness_only'
    if 'max_time' in keys:return 'finite_horizon_exploration_changes_time_estimand'
    if 'update_type' in keys:return 'explicit_logical_update_assumption_sensitivity'
    return 'explicit_model_or_sampling_sensitivity'
