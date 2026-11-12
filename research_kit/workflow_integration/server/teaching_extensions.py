"""Actual optional scientific backends, invoked only behind runtime.guard on server."""
from pathlib import Path
from runtime import write

def analyze(inputs,p,out,mode):
    from teaching_contracts import validate_backend
    validate_backend(mode,p,verify_versions=True)
    import numpy as np,pandas as pd
    np.random.seed(p['seed'])
    from scipy import sparse
    outputs=[]
    def emit(frame,name,role,index=True):
        path=out/(name+'.tsv');frame.to_csv(path,sep='\t',index=index);outputs.append((path,role))
    def dense(x):return x.toarray() if sparse.issparse(x) else np.asarray(x)
    def object_input():
        import anndata as ad
        a=ad.read_h5ad(inputs['object'])
        if not a.obs_names.is_unique or not a.var_names.is_unique:raise ValueError('Unique literal cell and gene identities required')
        if p['unit_key'] not in a.obs or a.obs[p['unit_key']].isna().any():raise ValueError('Actual biological unit for every cell required')
        return a
    def counts_input():
        a=object_input();x=a.layers[p['count_layer']];v=x.data if sparse.issparse(x) else np.asarray(x)
        if not np.isfinite(v).all() or (v<0).any() or (v!=np.floor(v)).any():raise ValueError('Nonnegative actual raw counts required')
        a.X=x.copy();return a
    diagnostics={'mode':mode,'scientific_validity':'not_established','runtime_scope':'Actual selected server run, not general backend validation'}
    if mode=='cnmf_programs':
        from cnmf import cNMF
        a=counts_input();ks=p['components'];K=p['selected_k']
        if not isinstance(ks,list) or len(ks)<2 or len(set(ks))!=len(ks) or any(type(k) is not int or not 2<=k<min(a.shape) for k in ks) or K not in ks:raise ValueError('Prespecified admissible K grid and selected K required')
        if type(p['n_iter']) is not int or p['n_iter']<2 or not 0<p['density_threshold']<=2 or not 0<p['local_neighborhood_size']<1:raise ValueError('Invalid cNMF replicate/density parameters')
        if (np.asarray(a.X.sum(axis=1)).ravel()==0).any():raise ValueError('Zero count cells must be resolved upstream')
        fn=out/'cnmf_input_counts.h5ad';a.write_h5ad(fn)
        fit=cNMF(output_dir=str(out/'cnmf'),name='programs')
        fit.prepare(counts_fn=str(fn),components=ks,n_iter=p['n_iter'],seed=p['seed'],num_highvar_genes=p['hvg_count'],max_NMF_iter=p['max_nmf_iterations'])
        fit.factorize(worker_i=0,total_workers=1);fit.combine();fit.k_selection_plot(close_fig=True)
        fit.consensus(k=K,density_threshold=p['density_threshold'],local_neighborhood_size=p['local_neighborhood_size'],show_clustering=False,close_clustergram_fig=True)
        usage,loadings,tpm,genes=fit.load_results(K=K,density_threshold=p['density_threshold'],n_top_genes=p['top_genes'])
        if set(usage.index)!=set(a.obs_names) or not np.isfinite(usage.to_numpy()).all():raise ValueError('cNMF output cell identity/finite-value contract failed')
        emit(usage.loc[a.obs_names],'program_usage','program_usage');emit(loadings,'program_loadings','program_loadings');emit(tpm,'program_internal_scaled_spectra','program_spectra');emit(genes,'program_top_genes','program_top_genes')
        emit(usage.join(a.obs[[p['unit_key']]]).groupby(p['unit_key'],observed=True).mean(),'donor_program_usage','donor_program_table')
        stats=Path(fit.paths['k_selection_stats'])
        if not stats.is_file():raise ValueError('Actual stability/error statistics not generated')
        outputs.append((stats,'k_stability'));diagnostics.update(selected_k=K,K_grid=ks,n_initializations=p['n_iter'],inference='Cell usage descriptive; donor means are descriptive and not independent-condition tests',scale='cNMF internal per-cell scaled spectra; not gene-length-corrected measured TPM')
    elif mode=='composition_sccoda':
        import anndata as ad,pertpy as pt,arviz as az
        table=pd.read_csv(inputs['count_table'],sep='\t',index_col=0);meta=pd.read_csv(inputs['metadata'],sep='\t',index_col=0)
        if not table.index.is_unique or not table.columns.is_unique or not meta.index.is_unique or set(table.index)!=set(meta.index):raise ValueError('Exact sample-by-celltype count table and metadata required')
        meta=meta.loc[table.index];values=table.to_numpy(float)
        if not np.isfinite(values).all() or (values<0).any() or (values!=np.floor(values)).any() or (values.sum(axis=1)==0).any():raise ValueError('Actual nonnegative captured cell counts required')
        if meta[[p['unit_key'],*p['covariates']]].isna().any().any() or meta[p['unit_key']].duplicated().any():raise ValueError('This scCODA adapter supports complete covariates and independent units only, not unmodelled repeated samples')
        condition=p['condition_key'];levels=p['condition_levels']
        if condition not in p['covariates'] or len(levels)!=len(set(levels)) or set(meta[condition])!=set(levels):raise ValueError('Exact condition levels in explicit reference-first order required')
        meta[condition]=pd.Categorical(meta[condition],categories=levels)
        import patsy
        design=patsy.dmatrix(p['formula'],meta,return_type='dataframe')
        if len(design)!=len(meta) or np.linalg.matrix_rank(design.to_numpy())!=design.shape[1] or design.shape[0]<=design.shape[1]:raise ValueError('Composition design is confounded, has missing rows or no residual support')
        if p['reference_cell_type'] not in table or not p['reference_basis']:raise ValueError('Explicit actual reference cell type and stability basis required')
        if type(p['chains']) is not int or p['chains']<2:raise ValueError('Independent MCMC chains required')
        chains=[];effects=[];credible=[];model=pt.tl.Sccoda()
        for c in range(p['chains']):
            a=ad.AnnData(X=values.copy(),obs=meta.copy(),var=pd.DataFrame(index=table.columns))
            a=model.prepare(a,formula=p['formula'],reference_cell_type=p['reference_cell_type'])
            model.run_nuts(a,num_warmup=p['warmup'],num_samples=p['posterior_samples'],rng_key=p['seed']+c)
            model.set_fdr(a,p['est_fdr'])
            eff=model.get_effect_df(a).copy();eff['chain']=c;effects.append(eff)
            dec=model.credible_effects(a,est_fdr=p['est_fdr']).rename('credible').to_frame();dec['chain']=c;credible.append(dec)
            tree=model.make_arviz(a,rng_key=p['seed']+c,num_prior_samples=100,use_posterior_predictive=False)
            posterior=getattr(tree,'posterior',None)
            if posterior is None:posterior=tree['posterior']
            if hasattr(posterior,'ds'):posterior=posterior.ds
            if not hasattr(posterior,'data_vars'):raise ValueError('Installed pertpy posterior API differs; do not replace diagnostics with success status')
            arrays={}
            for name,value in posterior.data_vars.items():
                if not {'chain','draw'}<=set(value.dims):continue
                arrays[name]=np.asarray(value.transpose('chain','draw',*[d for d in value.dims if d not in {'chain','draw'}]))
            if not arrays:raise ValueError('No actual chain/draw posterior arrays returned')
            chains.append(arrays)
        if any(set(x)!=set(chains[0]) for x in chains):raise ValueError('Posterior parameter axes differ across chains')
        posterior={k:np.concatenate([x[k] for x in chains],axis=0) for k in chains[0]};idata=az.from_dict(posterior=posterior);summary=az.summary(idata,var_names=p['diagnostic_var_names'])
        emit(summary,'composition_mcmc','composition_diagnostics');emit(pd.concat(effects),'composition_effects','composition_effects');emit(pd.concat(credible),'composition_credible_by_chain','composition_credible');emit(table,'observed_cell_counts','observed_counts')
        diagnostics.update(reference=p['reference_cell_type'],reference_basis=p['reference_basis'],condition_levels_reference_first=levels,design_columns=list(design.columns),chains=p['chains'],effect_decisions='Official per-chain scCODA decisions retained at the declared FDR; cross-chain agreement reviewed separately',max_rhat=float(summary.r_hat.max()),min_ess_bulk=float(summary.ess_bulk.min()),interpretation='Relative composition of captured cells, not absolute tissue counts')
        diagnostics['mcmc_qc_pass']=bool(np.isfinite(summary[['r_hat','ess_bulk']].to_numpy()).all() and summary.r_hat.max()<=p['maximum_rhat'] and summary.ess_bulk.min()>=p['minimum_ess'])
    elif mode=='cellrank_multiview':
        import cellrank as cr
        from teaching_contracts import validate_kernels
        a=object_input();spec=validate_kernels(p['kernels']);units=a.obs[p['unit_key']].to_numpy();kernel=None
        if not p['direction_evidence'] or p['cluster_key'] not in a.obs:raise ValueError('Root/direction evidence and actual annotation required')
        for row in spec:
            kind=row['kind']
            if kind=='velocity':
                if 'velocity' not in a.layers or not {'spliced','unspliced'}<=set(a.layers):raise ValueError('Actual velocity and processing layers required')
                item=cr.kernels.VelocityKernel(a).compute_transition_matrix()
            elif kind=='pseudotime':
                if row['time_key'] not in a.obs or not np.isfinite(a.obs[row['time_key']].to_numpy(float)).all():raise ValueError('Actual finite reviewed pseudotime required')
                item=cr.kernels.PseudotimeKernel(a,time_key=row['time_key'],backward=row['backward']).compute_transition_matrix(threshold_scheme='hard',frac_to_keep=row['frac_to_keep'],n_jobs=1)
            elif kind=='connectivity':item=cr.kernels.ConnectivityKernel(a).compute_transition_matrix()
            else:
                if not row['source_evidence'] or row['matrix_key'] not in a.obsp:raise ValueError('Precomputed transition needs exact upstream method evidence and cell-aligned matrix')
                matrix=a.obsp[row['matrix_key']];v=matrix.data if sparse.issparse(matrix) else np.asarray(matrix)
                if not np.isfinite(v).all() or (v<0).any() or not np.allclose(np.asarray(matrix.sum(axis=1)).ravel(),1):raise ValueError('Precomputed transition must be a finite nonnegative row-stochastic matrix')
                item=cr.kernels.PrecomputedKernel(matrix,adata=a)
            coo=sparse.coo_matrix(item.transition_matrix)
            if np.any(coo.data[units[coo.row]!=units[coo.col]]>0):raise ValueError('Selected within-unit fate route has cross-unit transitions; review upstream graph rather than silently pruning it')
            kernel=row['weight']*item if kernel is None else kernel+row['weight']*item
        terminals=p['terminal_states'];all_terminal=[v for cells in terminals.values() for v in cells]
        if len(terminals)<2 or len(all_terminal)!=len(set(all_terminal)) or not set(all_terminal)<=set(a.obs_names):raise ValueError('Disjoint actual terminal-cell sets required')
        for unit in set(units):
            ids=set(a.obs_names[units==unit])
            if any(not ids&set(v) for v in terminals.values()):raise ValueError('Each disconnected unit must cover each compared terminal state')
        fit=cr.estimators.GPCCA(kernel);fit.set_terminal_states(terminals,cluster_key=p['cluster_key']);fit.compute_fate_probabilities(use_petsc=False)
        values=np.asarray(fit.fate_probabilities)
        if not np.isfinite(values).all() or (values<0).any() or not np.allclose(values.sum(axis=1),1,atol=1e-6):raise ValueError('Fate probabilities fail numerical QC')
        emit(pd.DataFrame(values,index=a.obs_names,columns=fit.fate_probabilities.names),'fate_probabilities','fate_probabilities');emit(a.obs[[p['unit_key'],p['cluster_key']]],'fate_identity','fate_identity')
        sparse.save_npz(out/'transitions.npz',sparse.csr_matrix(kernel.transition_matrix));outputs.append((out/'transitions.npz','transition_matrix'))
        diagnostics.update(kernels=spec,graph_scope='within biological unit',maximum_rowsum_error=float(np.max(abs(values.sum(axis=1)-1))),interpretation='Model conditional fate probabilities, not experimental descendants')
    elif mode=='perturbation_baselines':
        x=pd.read_csv(inputs['training_expression'],sep='\t',index_col=0);meta=pd.read_csv(inputs['training_metadata'],sep='\t',index_col=0);test=pd.read_csv(inputs['test_metadata'],sep='\t',index_col=0)
        if not x.columns.is_unique or not x.index.is_unique or not meta.index.is_unique or not test.index.is_unique or set(x.columns)!=set(meta.index) or set(meta.index)&set(test.index):raise ValueError('Exact, unique disjoint training/test scenario identities required')
        meta=meta.loc[x.columns];key=p['condition_key'];context=p['context_key'];unit=p['unit_key']
        if not np.isfinite(x.to_numpy(float)).all():raise ValueError('Actual finite training expression profiles required')
        for m in [meta,test]:
            if m[[key,context,unit]].isna().any().any():raise ValueError('Missing scenario/unit/condition map')
        if p['holdout_axis']=='unit' and set(meta[unit])&set(test[unit]):raise ValueError('Claimed heldout donors overlap training')
        if p['holdout_axis']=='perturbation' and (set(meta[key])-{p['control']}) & set(test[key]):raise ValueError('Claimed unseen perturbation occurs in training')
        if p['holdout_axis'] not in {'unit','perturbation'}:raise ValueError('This adapter implements unit or perturbation holdout only')
        predictions=[]
        for name,row in test.iterrows():
            local=meta[meta[context]==row[context]];ctrl=local[local[key]==p['control']];pert=local[local[key]!=p['control']]
            if ctrl.empty or pert.empty:raise ValueError('Baseline context lacks actual training controls or perturbations')
            # Average within unit/condition before pooling, so cell/sample count does not manufacture donor replication.
            ctr=x.T.loc[ctrl.index].groupby([ctrl[unit],ctrl[key]],observed=True).mean().groupby(level=0).mean().mean(axis=0)
            per=x.T.loc[pert.index].groupby([pert[unit],pert[key]],observed=True).mean().groupby(level=0).mean().mean(axis=0)
            predictions.extend({'scenario_id':name,'baseline':label,'gene_id':gene,'prediction':float(value)} for label,profile in [('no_change_control',ctr),('training_perturbed_mean',per)] for gene,value in profile.items())
        emit(pd.DataFrame(predictions),'baseline_predictions','baseline_predictions',False);emit(test,'test_scenarios','baseline_identity')
        diagnostics.update(holdout_axis=p['holdout_axis'],training_only=True,scale=p['expression_scale'],interpretation='Two explicit descriptive prediction baselines; no test outcomes or test DEG selection used',evaluation='Use separately frozen true outcomes, full gene axis, perturbation-specific delta and functional endpoints')
    else:raise ValueError('Unknown selected teaching backend')
    diagnostics['software_versions']=p['software_versions']
    write(out/'diagnostics.json',diagnostics);outputs.append((out/'diagnostics.json','diagnostics'))
    write(out/'backend_versions.json',p['software_versions']);outputs.append((out/'backend_versions.json','backend_versions'));return outputs
