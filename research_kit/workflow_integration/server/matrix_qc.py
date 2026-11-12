"""Pre-inference scientific QC on the server; never alter the formal analysis matrix."""
from runtime import write,sha

def analyze(inputs,p,out,mode):
    import numpy as np
    import pandas as pd
    from sklearn.decomposition import PCA
    expression=pd.read_csv(inputs['matrix'],sep='\t',index_col=0);meta=pd.read_csv(inputs['metadata'],sep='\t')
    sample=p['sample_key'];unit=p['unit_key'];condition=p['condition_key'];issues=[]
    if expression.index.duplicated().any() or expression.columns.duplicated().any() or meta[sample].duplicated().any():raise ValueError('Duplicate sample/feature identity')
    if set(expression.columns)!=set(meta[sample]) or meta[[sample,unit,condition]].isna().any().any():raise ValueError('Actual matrix/metadata identity mismatch')
    meta=meta.set_index(sample).loc[expression.columns];x=expression.apply(pd.to_numeric,errors='raise')
    if np.isinf(x.to_numpy()).any():raise ValueError('Infinite assay values')
    if p['scale']=='raw_counts':
        if x.isna().any().any() or (x.to_numpy()<0).any() or (x.to_numpy()!=np.floor(x.to_numpy())).any():raise ValueError('Raw count semantics fail')
        size=x.sum(axis=0);detected=(x>0).sum(axis=0);zero=(size==0)
        qc_matrix=np.log1p(x.div(size.replace(0,np.nan),axis=1)*1e6)
    elif p['scale']=='log2_normalized':
        size=None;detected=x.notna().sum(axis=0);zero=detected==0
        if x.isna().any().any():
            if p.get('missing_for_qc')!='feature_median_qc_only':raise ValueError('Declare PCA-only missingness policy; formal matrix remains unfilled')
            qc_matrix=x.T.fillna(x.median(axis=1)).T
        else:qc_matrix=x.copy()
    else:raise ValueError('Explicit supported assay scale required')
    samples=pd.DataFrame({'sample_id':x.columns,'unit_id':meta[unit].astype(str),'condition':meta[condition].astype(str),
       'observed_features':detected,'missing_fraction':x.isna().mean(axis=0)})
    if size is not None:samples['library_size']=size
    thresholds=p['thresholds']
    samples['numerical_qc_pass']=(samples.observed_features>=thresholds['minimum_observed_features'])&(samples.missing_fraction<=thresholds['maximum_missing_fraction'])&~zero
    if size is not None:samples['numerical_qc_pass'] &= samples.library_size>=thresholds['minimum_library_size']
    samples.to_csv(out/'sample_qc.tsv',sep='\t',index=False)
    if not samples.numerical_qc_pass.all():issues.append('sample_measurement_threshold_failed')
    if meta.groupby([unit,condition],observed=True).size().max()>1:issues.append('technical_repeats_require_reviewed_aggregation')
    groups=meta[condition].astype(str);units=meta[unit].astype(str)
    if p['case'] not in set(groups) or p['control'] not in set(groups):raise ValueError('Requested contrast not present')
    if p['paired']:
        if set(units[groups==p['case']])!=set(units[groups==p['control']]):issues.append('incomplete_biological_pairing')
    elif units.duplicated().any():issues.append('unmodelled_repeated_unit')
    independent=meta.groupby(condition,observed=True)[unit].nunique().to_dict()
    if min(independent.get(p['case'],0),independent.get(p['control'],0))<p['minimum_units']:issues.append('insufficient_independent_support')
    design=pd.DataFrame({'Intercept':np.ones(len(meta))},index=meta.index)
    for name in [condition]+p['covariates']+([unit] if p['paired'] else []):
        if meta[name].isna().any():raise ValueError('Missing design covariate')
        if name in p['covariates'] and p['covariate_types'][name]=='numeric':design[name]=pd.to_numeric(meta[name],errors='raise')
        else:design=design.join(pd.get_dummies(meta[name],prefix=name,drop_first=True,dtype=float))
    rank=int(np.linalg.matrix_rank(design.to_numpy()))
    if rank!=design.shape[1] or design.shape[0]<=design.shape[1]:issues.append('rank_deficient_or_no_residual_df')
    design.to_csv(out/'design_matrix.tsv',sep='\t')
    if qc_matrix.isna().any().any() or not np.isfinite(qc_matrix.to_numpy()).all():issues.append('qc_transform_unavailable')
    else:
        variable=qc_matrix.var(axis=1).sort_values(ascending=False);genes=variable[variable>0].head(p['qc_variable_features']).index
        if len(genes)<2 or x.shape[1]<3:issues.append('qc_pca_insufficient_dimension')
        else:
            pca=PCA(n_components=min(p['qc_pcs'],len(genes),x.shape[1]-1));scores=pca.fit_transform(qc_matrix.loc[genes].T)
            pd.DataFrame(scores,index=x.columns,columns=['PC'+str(i+1) for i in range(scores.shape[1])]).to_csv(out/'pca_scores.tsv',sep='\t')
            qc_matrix.loc[genes].corr(method='spearman').to_csv(out/'sample_correlation.tsv',sep='\t')
    write(out/'matrix_qc.json',{'schema':'actual-matrix-qc/2','matrix_sha256':sha(inputs['matrix']),'metadata_sha256':sha(inputs['metadata']),
      'numerical_qc_pass':not issues,'issues':issues,'design_rank':rank,'design_columns':design.shape[1],
      'independent_units_by_group':independent,'sample_count':x.shape[1],'feature_count':x.shape[0],
      'formal_matrix_modified':False,'qc_transform':'log1p CPM for counts or declared intensity; QC only',
      'threshold_basis':p['threshold_basis'],'host_outlier_batch_review_required':True,'scientific_validity':'not_established'})
    outputs=[(out/'matrix_qc.json','matrix_qc'),(out/'sample_qc.tsv','sample_qc'),(out/'design_matrix.tsv','design_matrix')]
    for name,role in [('pca_scores.tsv','pca_scores'),('sample_correlation.tsv','correlation')]:
        if (out/name).is_file():outputs.append((out/name,role))
    return outputs
