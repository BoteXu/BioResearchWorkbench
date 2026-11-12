"""Allocated-server only: compare model expression deltas with independent measured perturbations."""
def evaluate(predicted,measured,manifest):
    import sys,platform,os
    if sys.platform!='linux' or 'microsoft' in platform.release().lower() or not (os.environ.get('SLURM_JOB_ID') or os.environ.get('SSH_CONNECTION')):raise RuntimeError('Scientific benchmark execution belongs on the existing server')
    import numpy as np,pandas as pd
    from scipy.stats import pearsonr
    if manifest['prediction_kind']!='expression_delta' or manifest['truth_kind']!='measured_perturbation_delta':raise ValueError('Embedding/vector-field/network distances cannot be benchmarked as measured RNA fold changes')
    for key in ('species','annotation_version','expression_scale','control_definition','perturbation_type'):
        if manifest['predicted_context'][key]!=manifest['measured_context'][key]:raise ValueError('Benchmark contexts are not comparable: '+key)
    if set(manifest['training_units'])&set(manifest['evaluation_units']):raise ValueError('Benchmark donors overlap training')
    key=['unit_id','perturbation_id','feature_id'];required=key+['delta']
    if any(not set(required)<=set(x) or x.duplicated(key).any() for x in (predicted,measured)):raise ValueError('Benchmark axes are ambiguous')
    if set(measured.unit_id)!=set(manifest['evaluation_units']):raise ValueError('Measured benchmark does not cover the declared evaluation units')
    x=predicted.merge(measured,on=key,how='outer',suffixes=('_predicted','_measured'),indicator=True,validate='one_to_one')
    if (x._merge!='both').any():raise ValueError('Full prespecified benchmark denominator differs; missing measurements cannot be treated as zero')
    if not np.isfinite(x[['delta_predicted','delta_measured']].to_numpy()).all():raise ValueError('Benchmark has nonfinite deltas')
    rows=[]
    for (unit,pert),g in x.groupby(['unit_id','perturbation_id'],sort=False):
        a=g.delta_predicted.to_numpy();b=g.delta_measured.to_numpy();mse=float(np.mean((a-b)**2));zero=float(np.mean(b*b))
        r=float(pearsonr(a,b).statistic) if len(a)>2 and np.ptp(a)>0 and np.ptp(b)>0 else None
        delta_margin=manifest['direction_minimum_abs_measured_delta'];mask=abs(b)>=delta_margin
        rows.append({'unit_id':unit,'perturbation_id':pert,'features':len(g),'delta_MSE':mse,'no_change_baseline_MSE':zero,'MSE_improvement_over_no_change':zero-mse,'delta_Pearson_descriptive':r,'direction_eligible_features':int(mask.sum()),'direction_accuracy':float(np.mean(np.sign(a[mask])==np.sign(b[mask]))) if mask.any() else None,'scope':'within-unit gene-wise descriptive metrics; not independent gene replicates'})
    return rows
