"""Real local-to-server native scoring and CellPhoneDB calls; offline resources only."""
from runtime import read,write

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad
    from scipy import sparse
    np.random.seed(p['seed']);a=ad.read_h5ad(inputs['object']);outputs=[];diag={'mode':mode,'software_versions':p['software_versions'],'scientific_acceptance':'NOT_ESTABLISHED'}
    if not a.obs_names.is_unique or not a.var_names.is_unique or p['unit_key'] not in a.obs or a.obs[p['unit_key']].isna().any():raise ValueError('Actual unique cells/features and complete independent-unit annotation required')
    x=a.layers[p['expression_layer']];v=x.data if sparse.issparse(x) else np.asarray(x)
    if p['expression_scale']!='log1p_normalized' or not np.isfinite(v).all() or (v<0).any():raise ValueError('Actual observed finite nonnegative log1p expression required; no scaled/imputed counts substitute')
    def emit(frame,name,role,index=True):
        fn=out/(name+'.tsv');frame.to_csv(fn,sep='\t',index=index);outputs.append((fn,role))
    if mode=='drug2cell_score':
        import drug2cell as d2c
        targets=read(inputs['targets']);eligible={};coverage=[]
        if not isinstance(targets,dict) or not targets:raise ValueError('Source-bound actual drug/target sets required; no implicit online/bundled database substitution')
        for drug,genes in targets.items():
            if not isinstance(drug,str) or not drug or not isinstance(genes,list) or not genes or any(not isinstance(g,str) or not g for g in genes) or len(set(genes))!=len(genes):raise ValueError('Unique literal drug and gene identities required')
            present=[g for g in genes if g in a.var_names];ok=len(present)>=p['minimum_targets']
            coverage.append({'drug_id':drug,'requested_targets':len(genes),'observed_targets':len(present),'status':'ELIGIBLE' if ok else 'INSUFFICIENT_FEATURE_COVERAGE','present_genes':','.join(present),'missing_genes':','.join(g for g in genes if g not in a.var_names)})
            if ok:eligible[drug]=genes
        emit(pd.DataFrame(coverage),'drug_target_coverage','target_coverage',False)
        if not eligible:raise ValueError('No requested target set satisfies prespecified measured-feature coverage; do not fabricate zero scores')
        d2c.score(a,targets=eligible,nested=False,method=p['method'],layer=p['expression_layer'],use_raw=False,n_bins=p['n_bins'],ctrl_size=p['ctrl_size'])
        result=a.uns['drug2cell']
        result_values=result.X.data if sparse.issparse(result.X) else np.asarray(result.X)
        if not result.obs_names.equals(a.obs_names) or set(result.var_names)!=set(eligible) or not np.isfinite(result_values).all():raise ValueError('Native drug2cell score identity/numerical contract failed')
        # Save the returned scored object separately: nested AnnData in .uns is not
        # a portable h5ad schema in every AnnData release.
        fn=out/'drug2cell_scores.h5ad';result.write_h5ad(fn);outputs.append((fn,'scored_object'));emit(result.to_df(),'drug2cell_scores','drug_scores')
        by_unit=result.to_df().join(a.obs[[p['unit_key']]]).groupby(p['unit_key'],observed=True).mean();emit(by_unit,'drug2cell_unit_means','unit_activity')
        diag.update(n_cells=a.n_obs,n_requested_drugs=len(targets),n_scored_drugs=result.n_vars,method=p['method'],interpretation='Expression-based target-set score, not measured drug potency, binding, inhibition or clinical response; unit means descriptive only')
    elif mode=='cellphonedb_per_unit':
        from cellphonedb.src.core.methods import cpdb_statistical_analysis_method as cpdb
        keys=[p['unit_key'],p['condition_key'],p['celltype_key']]
        if not set(keys)<=set(a.obs) or a.obs[keys].isna().any().any() or any('|' in str(v) for v in a.obs[p['celltype_key']].unique()):raise ValueError('Complete actual unit, condition and delimiter-safe celltype labels required')
        if p['species']!='Homo sapiens':raise ValueError('This native CPDB route uses a human database; explicit reviewed ortholog mapping must precede a separate nonhuman route')
        a.X=x.copy();ledger=[];complete=0
        for i,((unit,condition),positions) in enumerate(a.obs.groupby([p['unit_key'],p['condition_key']],observed=True,sort=False).indices.items()):
            b=a[positions].copy();numbers=b.obs[p['celltype_key']].value_counts();eligible=numbers[numbers>=p['minimum_cells_per_type']].index
            row={'stratum_index':i,'unit_id':str(unit),'condition':str(condition),'n_cells':b.n_obs,'n_eligible_types':len(eligible)}
            if len(eligible)<2:ledger.append({**row,'status':'HOLD_INSUFFICIENT_CELLTYPE_SUPPORT'});continue
            b=b[b.obs[p['celltype_key']].isin(eligible)].copy();b.raw=None;folder=out/('unit_'+str(i));folder.mkdir()
            meta=pd.DataFrame({'Cell':b.obs_names,'cell_type':b.obs[p['celltype_key']].to_numpy()});metafile=folder/'meta.tsv';meta.to_csv(metafile,sep='\t',index=False)
            countsfile=folder/'observed_log_expression.h5ad';b.write_h5ad(countsfile)
            result=cpdb.call(cpdb_file_path=str(inputs['database']),meta_file_path=str(metafile),counts_file_path=str(countsfile),counts_data=p['gene_identifier_type'],output_path=str(folder/'native'),iterations=p['iterations'],threshold=p['minimum_expression_fraction'],threads=p['threads'],debug_seed=p['seed'],result_precision=p['result_precision'],pvalue=p['pvalue_cutoff'],subsampling=False,debug=False,output_suffix='reviewed',score_interactions=False)
            for key,role in [('means','lr_means'),('pvalues','lr_pvalues'),('significant_means','lr_significant_means')]:
                if key not in result or not isinstance(result[key],pd.DataFrame):raise ValueError('Native CPDB output schema differs from reviewed return')
                frame=result[key];numeric=[c for c in frame.columns if '|' in str(c)]
                if not numeric or frame.empty:raise ValueError('No native celltype-pair interaction results; inspect database gene coverage')
                if key=='pvalues':
                    vals=frame[numeric].to_numpy(float)
                    if not np.isfinite(vals).all() or (vals<0).any() or (vals>1).any():raise ValueError('Invalid native CellPhoneDB permutation probabilities')
                emit(frame,'cellphonedb_unit_'+str(i)+'_'+key,role,False)
            for key in ['deconvoluted','deconvoluted_percents','means_deconvoluted','cell_types']:
                if key in result and isinstance(result[key],pd.DataFrame):emit(result[key],'cellphonedb_unit_'+str(i)+'_'+key,'lr_native_support',False)
            outputs.extend([(metafile,'stratum_metadata'),(countsfile,'stratum_object')]);complete+=1;ledger.append({**row,'status':'NATIVE_COMPLETED_NOT_SCIENTIFICALLY_VALIDATED'})
        emit(pd.DataFrame(ledger),'cellphonedb_strata','stratum_eligibility',False)
        if not complete:raise ValueError('No unit has adequate observed celltype support; retain eligibility ledger, do not substitute pooled-cell significance')
        diag.update(n_completed_strata=complete,n_hold_strata=len(ledger)-complete,iterations=p['iterations'],interpretation='CellPhoneDB cell-label permutation evidence computed separately within actual unit/condition. Not donor-level condition inference or proof of physical interaction; use independent-unit LR contrasts separately')
    else:raise ValueError('Unrecognized fixed native gene activity route')
    write(out/'native_diagnostics.json',diag);outputs.append((out/'native_diagnostics.json','diagnostics'));write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'));return outputs
