"""Server-side real assay QC, pseudobulk and matched-view analyses using existing environments."""
from runtime import write

def analyze(inputs,p,out,mode):
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp
    if mode=='multiomics_concordance':
        from scipy.stats import spearmanr
        a=pd.read_csv(inputs['view_a'],sep='\t',index_col=0);b=pd.read_csv(inputs['view_b'],sep='\t',index_col=0)
        mapping=pd.read_csv(inputs['feature_map'],sep='\t');pairs=pd.read_csv(inputs['sample_map'],sep='\t')
        if pairs['unit_id'].duplicated().any() or pairs['sample_a'].duplicated().any() or pairs['sample_b'].duplicated().any():
            raise ValueError('Concordance requires one prespecified matched measurement per independent unit')
        if p['matching'] not in {'same_biospecimen','same_unit'}:raise ValueError('No rowwise association for unpaired data')
        if any(s not in a.columns for s in pairs['sample_a']) or any(s not in b.columns for s in pairs['sample_b']):raise ValueError('Sample mapping not present in actual views')
        if mapping[['feature_a','feature_b']].duplicated().any():raise ValueError('Duplicate feature relation')
        rows=[]
        for row in mapping.to_dict('records'):
            if row['feature_a'] not in a.index or row['feature_b'] not in b.index:
                rows.append({**row,'status':'unmapped_feature','rho':None,'pvalue':None,'n_units':0});continue
            x=a.loc[row['feature_a'],pairs['sample_a']].to_numpy(dtype=float);y=b.loc[row['feature_b'],pairs['sample_b']].to_numpy(dtype=float)
            keep=np.isfinite(x)&np.isfinite(y);n=int(keep.sum())
            if n<p['minimum_units'] or len(set(x[keep]))<2 or len(set(y[keep]))<2:
                rows.append({**row,'status':'insufficient_or_constant','rho':None,'pvalue':None,'n_units':n});continue
            r,pv=spearmanr(x[keep],y[keep]);rows.append({**row,'status':'estimated','rho':float(r),'pvalue':float(pv),'n_units':n})
        result=pd.DataFrame(rows)
        from statsmodels.stats.multitest import multipletests
        valid=result['status']=='estimated';result['fdr']=np.nan
        if valid.any():result.loc[valid,'fdr']=multipletests(result.loc[valid,'pvalue'],method='fdr_bh')[1]
        result.to_csv(out/'concordance.tsv',sep='\t',index=False)
        write(out/'diagnostics.json',{'matching':p['matching'],'unit_count':len(pairs),'mapping_rows':len(mapping),'missing_values_imputed':False,
           'adjusted_covariates':False,'interpretation':'Marginal matched-unit association only; no causal/post-translational inference',
           'multiplicity_family':p['multiplicity_family'],'view_scales':p['view_scales']})
        return [(out/'concordance.tsv','cross_modal_association'),(out/'diagnostics.json','diagnostics')]
    import anndata
    adata=anndata.read_h5ad(inputs['object'])
    layer=p['count_layer']
    if layer not in adata.layers:raise ValueError('Explicit raw-count layer required; never infer counts from log data')
    counts=adata.layers[layer]
    values=counts.data if sp.issparse(counts) else np.asarray(counts)
    if not np.isfinite(values).all() or (values<0).any() or (values!=np.floor(values)).any():raise ValueError('Invalid raw count values')
    required=[p[k] for k in ('sample_key','unit_key','condition_key')]
    if adata.obs_names.duplicated().any() or adata.var_names.duplicated().any() or adata.obs[required].isna().any().any():raise ValueError('Object identity invalid')
    if adata.obs.groupby(p['sample_key'],observed=True)[p['unit_key']].nunique().max()!=1:raise ValueError('One technical sample maps to multiple biological units')
    if adata.obs.groupby(p['sample_key'],observed=True)[p['condition_key']].nunique().max()!=1:raise ValueError('One technical sample maps to multiple conditions')
    if mode=='pseudobulk':
        original_unit_conditions=adata.obs[[p['unit_key'],p['condition_key']]].drop_duplicates().copy()
        qc=pd.read_csv(inputs['cell_qc'],sep='\t',index_col=0)
        if qc.index.duplicated().any() or set(qc.index)!=set(adata.obs_names):raise ValueError('Pseudobulk must consume exact selected cell-QC decisions, not an unreviewed object')
        qc=qc.loc[adata.obs_names]
        if not set(qc['keep'].astype(str).str.lower())<={'true','false'}:raise ValueError('Explicit per-cell QC decisions required')
        adata=adata[qc['keep'].astype(str).str.lower().eq('true')].copy();counts=adata.layers[layer]
        keys=[p['unit_key'],p['condition_key'],p['celltype_key']]
        if adata.obs[keys].isna().any().any():raise ValueError('Missing pseudobulk identity')
        if p['technical_library_policy'] not in {'reject_multiple','pool_same_unit_condition'}:raise ValueError('Explicit technical library policy required')
        libraries=adata.obs.groupby([p['unit_key'],p['condition_key']],observed=True)[p['sample_key']].nunique()
        if p['technical_library_policy']=='reject_multiple' and (libraries>1).any():raise ValueError('Multiple libraries per unit/condition need reviewed pooling')
        if len(p['celltype_universe'])!=len(set(p['celltype_universe'])) or set(adata.obs[p['celltype_key']])-set(p['celltype_universe']):raise ValueError('Exact declared cell type universe required')
        rows=[];matrices=[]
        for n,(identity,idx) in enumerate(adata.obs.groupby(keys,observed=True).indices.items()):
            state='eligible' if len(idx)>=p['minimum_cells'] else 'ineligible_low_cell_support'
            rows.append(dict(zip(keys,identity),sample_id='PB'+str(n),n_cells=len(idx),eligibility=state))
            matrices.append(np.asarray(counts[idx].sum(axis=0)).ravel())
        if not rows:raise ValueError('No retained pseudobulk population; do not fabricate all-zero samples')
        pd.DataFrame(np.asarray(matrices).T,index=adata.var_names,columns=[r['sample_id'] for r in rows]).to_csv(out/'pseudobulk_counts.tsv',sep='\t')
        pd.DataFrame(rows).to_csv(out/'pseudobulk_metadata.tsv',sep='\t',index=False)
        observed={(r[p['unit_key']],r[p['condition_key']],r[p['celltype_key']]) for r in rows};missing=[]
        for unit,condition in original_unit_conditions.itertuples(index=False,name=None):
            for celltype in p['celltype_universe']:
                if (unit,condition,celltype) not in observed:missing.append({'unit_id':unit,'condition':condition,'celltype':celltype,'state':'not_observed_no_expression_column_created'})
        pd.DataFrame(missing,columns=['unit_id','condition','celltype','state']).to_csv(out/'missing_populations.tsv',sep='\t',index=False)
        write(out/'diagnostics.json',{'aggregation':'sum raw counts per unit x condition x cell type','all_groups_retained':True,
          'all_groups_retained_scope':'all observed groups; missing populations are ledger-only, never synthetic expression columns','technical_library_policy':p['technical_library_policy'],
          'ineligible_not_zero':True,'differential_analysis':'run count-aware R backend separately per eligible cell type and prespecified contrast'})
        return [(out/'pseudobulk_counts.tsv','pseudobulk_counts'),(out/'pseudobulk_metadata.tsv','pseudobulk_eligibility'),(out/'missing_populations.tsv','missing_populations'),(out/'diagnostics.json','diagnostics')]
    import scanpy as sc
    adata.X=counts.copy()
    if p['mitochondrial_namespace']!='explicit_gene_ids':raise ValueError('Use explicit assay/species mitochondrial IDs; no universal prefix heuristic')
    mito=set(pd.read_csv(inputs['mitochondrial_genes'],sep='\t')['gene_id'].astype(str));adata.var['mitochondrial']=adata.var_names.isin(mito)
    if not mito or not adata.var['mitochondrial'].any():raise ValueError('Mitochondrial identifier mapping has no actual coverage')
    sc.pp.calculate_qc_metrics(adata,layer=layer,qc_vars=['mitochondrial'],percent_top=None,inplace=True)
    qc=adata.obs[[*required,'total_counts','n_genes_by_counts','pct_counts_mitochondrial']].copy()
    from teaching_contracts import qc_thresholds
    gates=qc_thresholds(adata.obs[p['sample_key']].tolist(),p['qc_thresholds'],p.get('qc_thresholds_by_sample'))
    minimum_counts=adata.obs[p['sample_key']].map({k:v['min_counts'] for k,v in gates.items()})
    minimum_genes=adata.obs[p['sample_key']].map({k:v['min_genes'] for k,v in gates.items()})
    maximum_mito=adata.obs[p['sample_key']].map({k:v['max_mito_percent'] for k,v in gates.items()})
    qc['low_counts']=qc.total_counts<minimum_counts;qc['low_genes']=qc.n_genes_by_counts<minimum_genes;qc['high_mito']=qc.pct_counts_mitochondrial>maximum_mito
    qc['keep']=~(qc.low_counts|qc.low_genes|qc.high_mito)
    pd.DataFrame.from_dict(gates,orient='index').rename_axis('sample_id').to_csv(out/'qc_thresholds.tsv',sep='\t')
    doublet='UNASSESSED_UNSUPPORTED_ASSAY'
    if p['assay_contract']=='droplet_umi':doublet='UNASSESSED_NOT_SELECTED'
    if p['assay_contract']=='droplet_umi' and p.get('doublet_method')=='scrublet':
        sc.pp.scrublet(adata,batch_key=p['sample_key'],expected_doublet_rate=p['expected_doublet_rate'],random_state=p['seed'])
        qc['doublet_score']=adata.obs['doublet_score'];qc['predicted_doublet']=adata.obs['predicted_doublet'];qc['keep'] &= ~qc['predicted_doublet']
        doublet='assay_supported_prediction_not_physical_singlet_proof'
    elif p.get('doublet_method') not in {'none','unsupported'}:
        raise ValueError('Do not apply droplet doublet model to unsupported assay')
    qc.to_csv(out/'cell_qc.tsv',sep='\t')
    attrition=qc.groupby([p['sample_key'],p['unit_key'],p['condition_key']],observed=True)['keep'].agg(['size','sum']);attrition.to_csv(out/'attrition.tsv',sep='\t')
    if p.get('celltype_key') and p['celltype_key'] in adata.obs:
        joined=qc.assign(annotated_type=adata.obs[p['celltype_key']]);joined.groupby([p['sample_key'],p['unit_key'],p['condition_key'],'annotated_type'],observed=True)['keep'].agg(['size','sum']).to_csv(out/'annotation_attrition.tsv',sep='\t')
    adata=adata[qc['keep']].copy()
    if adata.n_obs<p['minimum_retained_cells'] or adata.n_vars<3:raise ValueError('Insufficient retained cells/features')
    diagnostics={'doublet_state':doublet,'retained_cells':adata.n_obs,'thresholds':gates,
       'threshold_basis':p['threshold_basis'],'ambient_rna':'not_removed; requires selected assay-compatible server method',
       'cell_identity':'not_established_by_embedding','independent_unit':p['unit_key']}
    if mode=='scvi':
        import scvi
        scvi.settings.seed=p['seed'];model=p['model']
        baseline=adata.copy();sc.pp.normalize_total(baseline,target_sum=p['baseline_target_sum']);sc.pp.log1p(baseline)
        sc.pp.highly_variable_genes(baseline,n_top_genes=min(p['baseline_hvg_count'],baseline.n_vars),batch_key=p['batch_key'])
        baseline_npc=min(p['baseline_n_pcs'],baseline.n_obs-1,int(baseline.var.highly_variable.sum())-1)
        if baseline_npc<2:raise ValueError('Unintegrated baseline cannot support requested comparison')
        sc.pp.pca(baseline,n_comps=baseline_npc,random_state=p['seed']);adata.obsm['X_pca_unintegrated']=baseline.obsm['X_pca'].copy()
        pd.DataFrame(baseline.obsm['X_pca'],index=baseline.obs_names).to_csv(out/'unintegrated_pca.tsv',sep='\t');del baseline
        adata.X=adata.layers[layer].copy()
        if model=='SCVI':
            scvi.model.SCVI.setup_anndata(adata,layer=layer,batch_key=p['batch_key'])
            fit=scvi.model.SCVI(adata,n_latent=p['latent_dimensions'])
        elif model=='TOTALVI':
            protein_key=p['protein_obsm_key']
            if p['assay_contract']!='droplet_umi' or protein_key not in adata.obsm:raise ValueError('TOTALVI requires same-cell raw RNA and ADT counts')
            protein=np.asarray(adata.obsm[protein_key])
            if not np.isfinite(protein).all() or (protein<0).any() or (protein!=np.floor(protein)).any():raise ValueError('ADT is not raw count data')
            scvi.model.TOTALVI.setup_anndata(adata,layer=layer,batch_key=p['batch_key'],protein_expression_obsm_key=protein_key)
            fit=scvi.model.TOTALVI(adata,n_latent=p['latent_dimensions'])
        else:raise ValueError('Select SCVI or TOTALVI; MULTIVI has a different explicit RNA/ATAC object contract')
        fit.train(max_epochs=p['max_epochs'],accelerator=p['accelerator'],devices=1,early_stopping=True)
        adata.obsm['X_integrated']=fit.get_latent_representation()
        if p.get('save_model') is True:fit.save(str(out/'model'),overwrite=False,save_anndata=False)
        diagnostics['model']=model;diagnostics['downstream_differential']='Original-count donor models, never latent embedding p-values'
        diagnostics['validation_limits']='Training history and cell-level held-out reconstruction do not validate donor generalization'
        fit.history['elbo_train'].to_csv(out/'training_history.tsv',sep='\t')
        adata.write_h5ad(out/'processed.h5ad')
        write(out/'diagnostics.json',diagnostics)
        result=[(out/'processed.h5ad','processed_object'),(out/'cell_qc.tsv','cell_qc'),(out/'attrition.tsv','attrition'),(out/'qc_thresholds.tsv','qc_thresholds'),(out/'unintegrated_pca.tsv','unintegrated_baseline'),
                (out/'diagnostics.json','diagnostics'),(out/'training_history.tsv','training_history')]
        if (out/'annotation_attrition.tsv').exists():result.append((out/'annotation_attrition.tsv','annotation_attrition'))
        return result
    sc.pp.filter_genes(adata,min_cells=p['min_cells_per_gene'])
    sc.pp.normalize_total(adata,target_sum=p['target_sum']);sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata,n_top_genes=min(p['hvg_count'],adata.n_vars),batch_key=p.get('batch_key'))
    n_pcs=min(p['n_pcs'],adata.n_obs-1,int(adata.var.highly_variable.sum())-1)
    if n_pcs<2:raise ValueError('PCA has insufficient dimensions')
    sc.pp.pca(adata,n_comps=n_pcs,random_state=p['seed']);sc.pp.neighbors(adata,n_neighbors=min(p['neighbors'],adata.n_obs-1),n_pcs=n_pcs,random_state=p['seed'])
    sc.tl.leiden(adata,resolution=p['resolution'],random_state=p['seed']);sc.tl.umap(adata,random_state=p['seed'])
    sc.tl.rank_genes_groups(adata,'leiden',method='wilcoxon',use_raw=False)
    sc.get.rank_genes_groups_df(adata,group=None).to_csv(out/'descriptive_markers.tsv',sep='\t',index=False)
    adata.write_h5ad(out/'processed.h5ad');write(out/'diagnostics.json',diagnostics)
    result=[(out/'processed.h5ad','processed_object'),(out/'cell_qc.tsv','cell_qc'),(out/'attrition.tsv','attrition'),(out/'qc_thresholds.tsv','qc_thresholds'),
            (out/'descriptive_markers.tsv','descriptive_markers'),(out/'diagnostics.json','diagnostics')]
    if (out/'annotation_attrition.tsv').exists():result.append((out/'annotation_attrition.tsv','annotation_attrition'))
    return result
