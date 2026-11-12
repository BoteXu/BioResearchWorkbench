"""Bounded returned-result semantics. Does not fit any scientific model."""
from pathlib import Path
import math

def inspect_branch(request,receipt,local,spec):
    from acceptance import load,rows,number
    from server.return_binding import receipt_index,proof_issues
    issues=[];p=request['parameters'];key=p['analysis_id']
    if p.get('implementation')!=spec['implementation']:issues.append('wrong_actual_implementation')
    for role in spec['required_roles']:
        if role not in local:continue
        cols,data=rows(local[role])
        if role==spec['required_roles'][0] and not any(set(c)<=set(cols) for c in spec['primary_columns_any']):issues.append('primary_result_semantics_missing:'+role)
        if not data and role==spec['required_roles'][0] and not spec.get('primary_result_rule',{}).get('allow_empty'):issues.append('empty_primary_test_family_requires_review')
        from server.method_contract71 import validate_rows
        issues.extend(role+':'+v for v in validate_rows(cols,data,spec.get('primary_result_rule',{}) if role==spec['required_roles'][0] else {'allow_empty':True}))
        for row in data:
            for name,value in row.items():
                if value in ('','NA','NaN'):continue
                lower=name.lower()
                if lower in {'p','pvalue','p_value','p.value','q','qvalue','fdr','adj.p.val','posterior_inclusion_probability','frame0_fraction','gap_fraction','cellular_prevalence','cluster_assignment_prob','structural_zero_probability'}:
                    if not 0<=number(value)<=1:issues.append('invalid_probability:'+role+':'+name)
                if lower in {'se','standard_error','cellular_prevalence_std','ccf_sd','residual_sd'} and number(value)<0:issues.append('negative_uncertainty:'+role)
                if lower in {'pvalue','p.value','pval','padj','fdr','adj_pvalue'} and not 0<=number(value)<=1:issues.append('invalid_test_probability:'+role)
            for left,right in (('ci_lower','ci_upper'),('bootstrap_lower','bootstrap_upper')):
                if left in row and right in row and row[left] not in ('','NA') and row[right] not in ('','NA'):
                    if number(row[left])>number(row[right]):issues.append('reversed_interval:'+role)
            if all(k in row and row[k] not in ('','NA') for k in ('ci_lower','ci_upper','effect')) and not number(row['ci_lower'])<=number(row['effect'])<=number(row['ci_upper']):issues.append('estimate_outside_interval:'+role)
    if 'implementation_record' in local:
        record=load(local['implementation_record'])
        if record.get('analysis_id')!=key or record.get('implementation')!=p.get('implementation') or record.get('public_upload') is not False:issues.append('method_identity_mismatch')
        if record.get('source_sha256')!=receipt.get('source_sha256'):issues.append('method_source_mismatch')
    expected={'primary'}|{v['label'] for v in p['sensitivity_variants']}
    if 'full_result_audit' in local:
        proof=load(local['full_result_audit']);bound,record_issues=receipt_index(receipt['outputs']);issues.extend(record_issues);issues.extend(proof_issues(proof,bound,expected,spec['required_roles'],'FULL_SERVER_FILE_SCAN_NOT_INDEPENDENT_SCIENTIFIC_VALIDATION',{r:(spec['primary_result_rule'] if r==spec['required_roles'][0] else {'allow_empty':True}) for r in spec['required_roles']},preview_kind='tsv'));wanted={(v,r) for v in expected for r in spec['required_roles']}
        if {(r['variant'],r['role']) for r in proof}!=wanted or len(proof)!=len(wanted):issues.append('full_server_audit_denominator_incomplete')
        for r in proof:
            record=bound.get(r['path'],{})
            if r.get('sha256')!=record.get('sha256') or r.get('bytes')!=record.get('bytes') or r.get('scope')!='FULL_SERVER_FILE_SCAN_NOT_INDEPENDENT_SCIENTIFIC_VALIDATION':issues.append('full_server_audit_not_bound_to_actual_result')
            preview=local.get('_by_path',{}).get(r['preview_path'])
            if preview is not None:
                from acceptance import sha
                if sha(preview)!=r['preview_sha256']:issues.append('preview_not_bound_to_full_server_scan')
    else:issues.append('full_result_audit_missing')
    if 'actual_sensitivity_comparison' in local:
        comparison=load(local['actual_sensitivity_comparison'])
        if len(comparison)!=len(expected)-1 or {r['variant'] for r in comparison}!=expected-{'primary'}:issues.append('actual_result_comparison_incomplete')
        if any(r.get('scientific_robustness_established') is not False for r in comparison):issues.append('numerical_rerun_comparison_overclaimed')
    else:issues.append('actual_result_comparison_missing')
    if 'analysis_diagnostics' in local:
        diagnostics=load(local['analysis_diagnostics'])
        if {r.get('variant') for r in diagnostics}!=expected or len(diagnostics)!=len(expected):issues.append('missing_actual_variant_diagnostics')
        for r in diagnostics:
            if r.get('fit_completed') is not True or not r.get('metrics'):issues.append('diagnostics_not_measured')
            for value in r.get('metrics',{}).values():
                try:number(value)
                except (TypeError,ValueError):issues.append('non_numeric_actual_diagnostic')
            metric=r.get('metrics',{})
            for warning in r.get('warnings',[]):
                if any(word in str(warning).lower() for word in ('did not converge','failed','rank deficient','singular','nan','not positive')):issues.append('actual_engine_warning_requires_review')
            if 'converged' in metric and metric['converged']!=1:issues.append('scientific_fit_not_converged')
            if 'maximum_rowsum_error' in metric and metric['maximum_rowsum_error']>.001:issues.append('fate_probability_not_normalized')
    if 'analysis_sensitivity' in local:
        entries=load(local['analysis_sensitivity']);seen={(r.get('variant'),r.get('role')) for r in entries}
        wanted={(v,role) for v in expected for role in spec['required_roles']}
        if seen!=wanted or len(entries)!=len(wanted):issues.append('missing_actual_sensitivity_denominators')
        for r in entries:
            if type(r.get('rows')) is not int or r['rows']<0 or not r.get('columns'):issues.append('malformed_sensitivity_result')
        # Required alternate output hashes must also exist in the same completion receipt.
        actual_paths={r['path'] for r in receipt['outputs']}
        for v in expected:
            for role in spec['required_roles']:
                if v+'/'+role+'.tsv' not in actual_paths:issues.append('variant_data_not_returned:'+v+':'+role)
    if 'analysis_qc' in local:
        q=load(local['analysis_qc']);c=q.get('context',{});pre=q.get('executed_preflight',{})
        if pre.get('state')!='EXECUTED_PREFLIGHT' or not pre.get('observations'):issues.append('executable_preflight_absent')
        if c.get('independent_unit')!=request['statistical_plan']['independent_unit'] or c.get('estimand')!=request['statistical_plan']['estimand']:issues.append('unit_estimand_handoff_changed')
        declared={r['id']:r['sha256'] for r in request['inputs']}
        for evidence in q.get('upstream_evidence',[]):
            if evidence.get('input_id') not in declared or evidence.get('sha256')!=declared[evidence['input_id']]:issues.append('upstream_qc_input_changed')
    return sorted(set(issues))
