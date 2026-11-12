"""Pure parameter/metadata contracts; no data fitting and no network."""
import math,re
def qc_thresholds(samples,defaults,overrides=None):
    overrides=overrides or {};unique=set(samples)
    if set(overrides)-unique:raise ValueError('Unknown exact sample in QC threshold override')
    result={}
    for sample in unique:
        row={**defaults,**overrides.get(sample,{})}
        if set(row)!={'min_counts','min_genes','max_mito_percent'}:raise ValueError('Unknown or missing QC threshold')
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in row.values()):raise ValueError('Finite nonnegative QC thresholds required')
        if row['max_mito_percent']>100:raise ValueError('Mitochondrial threshold must use percent, not an unlabelled fraction')
        result[sample]=row
    return result
def validate_kernels(rows):
    if not isinstance(rows,list) or not rows:raise ValueError('Explicit kernels required')
    if len({r['kind'] for r in rows})!=len(rows):raise ValueError('Duplicate kernel kinds')
    for r in rows:
        if r['kind'] not in {'velocity','pseudotime','connectivity','precomputed'}:raise ValueError('Unsupported kernel; no substitute for a missing assay')
        if type(r.get('weight')) not in (int,float) or not math.isfinite(r['weight']) or not 0<r['weight']<=1:raise ValueError('Positive finite kernel weights required')
    if not math.isclose(sum(r['weight'] for r in rows),1,abs_tol=1e-10):raise ValueError('Kernel weights must sum to one')
    if {r['kind'] for r in rows}=={'connectivity'}:raise ValueError('Undirected similarity alone does not provide a fate direction')
    return rows
def unit_map(rows,sample_key,unit_key,condition_key):
    mapping={}
    for row in rows:
        values=[row.get(k) for k in [sample_key,unit_key,condition_key]]
        if any(not isinstance(v,str) or not v for v in values):raise ValueError('Literal nonempty sample/unit/condition strings required')
        sample,unit,condition=values
        if sample in mapping and mapping[sample]!=(unit,condition):raise ValueError('Technical sample maps to multiple units or conditions')
        mapping[sample]=(unit,condition)
    return mapping

def validate_backend(mode,p,verify_versions=False):
    packages={'cnmf_programs':['cnmf','anndata'],'composition_sccoda':['pertpy','arviz','anndata'],'cellrank_multiview':['cellrank','anndata'],'perturbation_baselines':['numpy','pandas']}[mode]
    versions=p.get('software_versions',{})
    if not isinstance(versions,dict) or any(not isinstance(versions.get(k),str) or not versions[k] for k in packages):raise ValueError('Pin exact versions from the actual existing server environment')
    for key in ['seed','n_iter','hvg_count','max_nmf_iterations','top_genes','chains','warmup','posterior_samples','minimum_ess']:
        if key in p and (type(p[key]) is not int or p[key]<(0 if key=='seed' else 1)):raise ValueError('Invalid integer parameter: '+key)
    for key in ['maximum_rhat','density_threshold','local_neighborhood_size','est_fdr']:
        if key in p and (type(p[key]) not in (int,float) or not math.isfinite(p[key]) or p[key]<=0):raise ValueError('Invalid finite parameter: '+key)
    if mode=='cellrank_multiview':
        validate_kernels(p['kernels'])
        for r in p['kernels']:
            if r['kind']=='pseudotime' and (type(r.get('backward')) is not bool or not isinstance(r.get('time_key'),str) or type(r.get('frac_to_keep')) not in (int,float) or not math.isfinite(r['frac_to_keep']) or not 0<=r['frac_to_keep']<=1):raise ValueError('Explicit pseudotime direction and retained-edge fraction required')
    if mode=='composition_sccoda':
        if not 0<p['est_fdr']<1 or p['chains']<2 or not p['diagnostic_var_names'] or not p['covariates']:raise ValueError('Explicit multi-chain scCODA FDR, covariates and convergence parameter set required')
        if any(not isinstance(k,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',k) for k in p['covariates']) or len(p['covariates'])!=len(set(p['covariates'])) or p['formula']!=' + '.join(p['covariates']):raise ValueError('This scCODA adapter supports an explicit additive covariate formula only; no arbitrary evaluated expressions')
    if verify_versions:
        import importlib.metadata
        for package in packages:
            if importlib.metadata.version(package)!=versions[package]:raise ValueError('Installed server package version differs: '+package)
