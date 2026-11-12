"""Method-scoped validation shared by planning, server runs and bounded review. Stdlib only."""
import math,re

PROBABILITIES={'fdr','coverage','auc_threshold','expr_prop','lambda_min_ratio','p1','p2','p12','prv_cut','calibration_alpha','max_internal_priming','dispersion_floor','prop','min_abs_corr','transition_weight','donor_subsample_fraction','alpha_fdr'}
POSITIVE={'alpha','pseudocount','radius','distance_scale','protein_adjustment_weight','sample_size','n1','n2','f_threshold','min_coverage','min_variant_depth','footprint_min_width','footprint_max_width'}
RESAMPLES={'bootstraps','permutations','n_perms','simulations','stars_reps','null_permutations','donor_resamples','reference_bootstraps'}

def validate_parameters(p,spec):
    if type(p.get('seed')) is not int or not 0<=p['seed']<2**31:raise ValueError('Integer seed must also be admissible in the shared R/Python implementation')
    if p.get('contrast_method') in ('unpaired_welch','paired_t') and p.get('covariates'):raise ValueError('The selected Welch/paired model cannot silently ignore covariates')
    if p.get('control') is not None and p.get('control')==p.get('treatment'):raise ValueError('Contrast groups must differ')
    for k in PROBABILITIES&set(p):
        if type(p[k]) not in (int,float) or not math.isfinite(p[k]) or not 0<p[k]<1:raise ValueError('Probability must be finite in (0,1): '+k)
    for k in POSITIVE&set(p):
        if type(p[k]) not in (int,float) or not math.isfinite(p[k]) or p[k]<=0:raise ValueError('Positive finite method parameter required: '+k)
    for k in RESAMPLES&set(p):
        if type(p[k]) is not int or p[k]<20:raise ValueError('At least 20 explicit diagnostic resamples required; production precision remains prespecified: '+k)
    if 'min_set_size' in p and 'max_set_size' in p and p['min_set_size']>p['max_set_size']:raise ValueError('Gene-set minimum exceeds maximum')
    if 'purity' in p and not 0<p['purity']<=1:raise ValueError('Invalid purity')
    if 'footprint_min_width' in p and p['footprint_min_width']>p['footprint_max_width']:raise ValueError('Invalid footprint width range')
    if p.get('action') not in (None,2,3):raise ValueError('MR must infer/drop palindromes conservatively; action=1 is not enabled')
    if 'lambda' in p and not 0<=p['lambda']<=1:raise ValueError('Spatial neighbor weight outside [0,1]')
    for k in ('case_fraction1','case_fraction2'):
        if k in p and (type(p[k]) not in (float,int) or not 0<p[k]<1):raise ValueError('Case fraction must be in (0,1)')
    if p['analysis_id']=='colocalization':
        if p['p12']>min(p['p1'],p['p2']):raise ValueError('Shared-signal prior cannot exceed either trait-association prior')
        for n in (1,2):
            if p['trait'+str(n)+'_type']=='quant' and (type(p.get('sdY'+str(n))) not in (int,float) or p['sdY'+str(n)]<=0):raise ValueError('Quantitative coloc requires actual positive phenotype SD')
            if p['trait'+str(n)+'_type']=='cc' and 'case_fraction'+str(n) not in p:raise ValueError('Case-control coloc requires the actual case fraction')
    for k in ('n_modules','resolution'):
        if p['analysis_id']=='spatial_domains' and k in p and (type(p[k]) is not int or p[k]<2):raise ValueError('Spatial domain resolution is an integer >=2, not Leiden resolution')
    for k in ('holdout_units','training_units','test_units','covariates','calibration_covariates','reference_exclude_donors','celltype_universe'):
        if k in p and (not isinstance(p[k],list) or len(p[k])!=len(set(p[k])) or any(not isinstance(v,str) or not v for v in p[k])):raise ValueError('Unique explicit string list required: '+k)

def strict_bool(value):
    if type(value) is int and value in (0,1):return bool(value)
    if value is True or value in ('True','TRUE','true','1'):return True
    if value is False or value in ('False','FALSE','false','0'):return False
    raise ValueError('Missing or invalid boolean; truthy text is not evidence')

def numeric(value):
    if isinstance(value,bool):raise ValueError('Boolean is not a numerical observation')
    x=float(value)
    if not math.isfinite(x):raise ValueError('Nonfinite numerical observation')
    return x

def validate_rows(columns,rows,rule):
    """Return explicit issues for one selected small result; fitting is never done here."""
    issues=[];key=rule.get('keys',[]);seen=set()
    if not set(rule.get('required',[]))<=set(columns):issues.append('required_columns_missing')
    for row in rows:
        if key and set(key)<=set(columns):
            values=tuple(row[c] for c in key)
            if any(v in ('','NA','NaN','nan','None') for v in values):issues.append('missing_result_key')
            if values in seen:issues.append('duplicate_result_key')
            seen.add(values)
        for name,value in row.items():
            if value in ('','NA','NaN','nan','None'):
                if name in rule.get('nonmissing',[]):issues.append('unexplained_missing_required_value:'+name)
                continue
            low=name.lower()
            if name in rule.get('probability_columns',[]):
                try:
                    if not 0<=numeric(value)<=1:issues.append('probability_out_of_range:'+name)
                except (ValueError,TypeError):issues.append('invalid_probability:'+name)
            if low in {'p','p.value','pvalue','pval','p_value','q','padj','adj.p.val','adj_pvalue','fdr','spatialfdr','spatial_fdr','stage_q','combinedpval','adjustedpval','joint_family_q','posterior_inclusion_probability','cellular_prevalence','cluster_assignment_prob','frame0_fraction','gap_fraction'}:
                try:
                    if not 0<=numeric(value)<=1:issues.append('probability_out_of_range:'+name)
                except (ValueError,TypeError):issues.append('invalid_probability:'+name)
            if low in {'se','standard_error','bse','ccf_sd','cellular_prevalence_std','conditional_se'}:
                try:
                    if numeric(value)<0:issues.append('negative_uncertainty:'+name)
                except (ValueError,TypeError):issues.append('invalid_uncertainty:'+name)
        for lo,hi in (('ci_lower','ci_upper'),('CI.L','CI.R'),('bootstrap_lower','bootstrap_upper')):
            if lo in row and hi in row and row[lo] not in ('','NA') and row[hi] not in ('','NA') and numeric(row[lo])>numeric(row[hi]):issues.append('interval_reversed')
    if not rows and not rule.get('allow_empty',False):issues.append('empty_test_family_or_unassessed_denominator')
    return sorted(set(issues))
