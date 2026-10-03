"""Pre-analysis QC reports with explicit blocking decisions and immutable input hashes."""
import hashlib
import json
from pathlib import Path
from transcriptomics_ext import _frames,_design,_capacity,_folder,_finish,_context,_workflow


def qc_frames(matrix,meta,input_paths,matrix_kind,context,design_info=None):
    import numpy as np
    import pandas as pd
    folder = _folder('preanalysis_qc')
    data = matrix.to_numpy(dtype=float)
    issues,warnings = [],[]
    constant = matrix.var(axis=1)==0
    sample_constant = matrix.var(axis=0)==0
    metrics = pd.DataFrame(index=matrix.columns)
    metrics['minimum'] = matrix.min()
    metrics['maximum'] = matrix.max()
    metrics['median'] = matrix.median()
    metrics['constant_values'] = sample_constant
    if sample_constant.any(): issues.append('constant_sample_expression')
    if int((~constant).sum())<20: issues.append('fewer_than_twenty_varying_features')
    if matrix_kind=='raw_counts':
        metrics['library_counts'] = matrix.sum()
        metrics['detected_genes'] = (matrix>0).sum()
        metrics['zero_fraction'] = (matrix==0).mean()
        if (metrics.library_counts<=0).any(): issues.append('empty_library')
        if (metrics.detected_genes<20).any(): issues.append('very_low_expression_coverage')
        median = float(metrics.library_counts.median())
        metrics['depth_vs_median'] = metrics.library_counts/max(median,1.)
        if ((metrics.depth_vs_median<0.1)|(metrics.depth_vs_median>10)).any(): issues.append('extreme_library_depth_requires_review_or_revised_input')
        exploratory = np.log2(matrix.div(matrix.sum().replace(0,np.nan),axis=1)*1000000+1)
        pca_scale = 'log2 CPM plus one; exploratory only'
    else:
        exploratory = matrix
        pca_scale = 'caller-declared log2 normalized expression'
        if data.min()>=0 and np.equal(data,np.floor(data)).all(): warnings.append('integer_only_values_in_declared_log_expression_review_provenance')
    matrix.corr(method='pearson').to_csv(folder/'sample_pearson.csv')
    matrix.corr(method='spearman').to_csv(folder/'sample_spearman.csv')
    metrics.to_csv(folder/'sample_qc.csv')
    if np.isfinite(exploratory.to_numpy()).all() and matrix.shape[1]>=3 and (~constant).sum()>=2:
        from sklearn.decomposition import PCA
        selected = exploratory.loc[exploratory.var(axis=1).nlargest(min(2000,len(matrix))).index]
        model = PCA(n_components=2,svd_solver='full')
        scores = model.fit_transform(selected.T)
        pd.DataFrame(scores,index=matrix.columns,columns=['PC1','PC2']).to_csv(folder/'preanalysis_pca.csv')
    source = [{'role':role,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()} for role,path in input_paths.items()]
    return _finish(folder,{'workflow':'preanalysis_qc','qc_gate_pass':not issues,'formal_analysis_allowed':not issues,'issues':issues,'warnings':warnings,'matrix_kind':matrix_kind,'features':matrix.shape[0],'observations':matrix.shape[1],'constant_features':int(constant.sum()),'pca_scale':pca_scale,'design':design_info,'input_hashes':source,'context':context,'limitations':['QC success does not verify source provenance or scientific truth.','PCA and correlation are exploratory; no sample is automatically removed.','Species, processing scale and unit labels need source-method review.','Extremely imbalanced depth requires reviewed input or a justified separate workflow; this tool does not bypass the block.']})


@_workflow
def preflight_transcriptomics(matrix_path: str, metadata_path: str, matrix_kind: str, condition_key: str, unit_key: str, case: str, control: str, context: dict, paired: bool = False, covariates: list = None, min_units: int = 3) -> dict:
    """Run input, resource, replicate/design and sample QC before any formal differential-expression fit."""
    _context(context)
    if matrix_kind not in {'raw_counts','log2_normalized'}: raise ValueError('Choose raw_counts or log2_normalized; do not infer scale from values')
    matrix,meta = _frames(matrix_path,metadata_path,matrix_kind=='raw_counts')
    _capacity(matrix,'bulk' if matrix_kind=='raw_counts' else 'normalized')
    d,formula,x,units = _design(meta,condition_key,unit_key,case,control,paired,covariates or [],min_units)
    result = qc_frames(matrix,meta,{'matrix':matrix_path,'metadata':metadata_path},matrix_kind,context,{'formula':formula,'biological_units':units,'case':case,'control':control})
    x.to_csv(Path(result['output_directory'])/'design_matrix.csv')
    return result


def require_qc(matrix,meta,paths,matrix_kind,context,formula,units):
    report = qc_frames(matrix,meta,paths,matrix_kind,context,{'formula':formula,'biological_units':units})
    if not report['qc_gate_pass']:
        raise ValueError('Pre-analysis QC blocked formal analysis; inspect the preserved QC report: '+report['report_file'])
    return {'report_file':report['report_file'],'summary_file':str(Path(report['output_directory'])/'summary.json'),'input_hashes':report['input_hashes'],'qc_gate_pass':True}


def compare_analysis_results(result_paths: list, context: dict) -> dict:
    """Pairwise effect/rank/sign agreement for explicitly comparable complete result tables; no meta-analysis."""
    _context(context)
    if not isinstance(result_paths,list) or not 2<=len(result_paths)<=8: raise ValueError('Provide two to eight complete result tables with the same intended contrast')
    import pandas as pd
    import numpy as np
    from transcriptomics_ext import _read
    frames = []
    for path in result_paths:
        h,r = _read(path)
        frame = pd.DataFrame([v[1:] for v in r],index=[v[0] for v in r],columns=h[1:])
        if not {'log2FoldChange','padj'}<=set(frame.columns): raise ValueError('Result tables need log2FoldChange and padj columns')
        for column in ('log2FoldChange','padj'): frame[column] = pd.to_numeric(frame[column],errors='coerce')
        frames.append(frame)
    rows = []
    for i,left in enumerate(frames):
        for j in range(i+1,len(frames)):
            right = frames[j]
            shared = left.index.intersection(right.index)
            values = pd.concat([left.loc[shared,'log2FoldChange'],right.loc[shared,'log2FoldChange']],axis=1).replace([np.inf,-np.inf],np.nan).dropna()
            a = set(left.index[left.padj<0.05]); b = set(right.index[right.padj<0.05])
            corr = float(values.iloc[:,0].corr(values.iloc[:,1],method='spearman')) if len(values)>2 else float('nan')
            rows.append({'left':i,'right':j,'shared_features':len(shared),'finite_effect_pairs':len(values),'effect_spearman':corr if np.isfinite(corr) else None,'sign_agreement':float((np.sign(values.iloc[:,0])==np.sign(values.iloc[:,1])).mean()) if len(values) else None,'significant_set_jaccard':len(a&b)/len(a|b) if a|b else None})
    return {'success':True,'comparisons':rows,'context':context,'input_hashes':[hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in result_paths],'limitations':['Caller must establish matching species, gene namespace, samples and contrast direction.','Agreement across methods on the same data is sensitivity analysis, not independent replication.','No pooled effect, causal attribution or automatic best-method selection is performed.']}
