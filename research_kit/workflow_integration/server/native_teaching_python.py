"""Additional real native scientific calls; entered exclusively through server guard.

No dependency installation, public upload, implicit download, or automatic dispatch.
"""
from runtime import write

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate,check_split
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad
    from scipy import sparse
    np.random.seed(p['seed']);outputs=[]
    diag={'mode':mode,'scientific_acceptance':'NOT_ESTABLISHED','software_versions':p['software_versions']}
    def emit(frame,name,role):
        fn=out/(name+'.tsv');frame.to_csv(fn,sep='\t',index=True);outputs.append((fn,role))
    def values(x):return x.data if sparse.issparse(x) else np.asarray(x)
    def validate_object(a):
        if not a.obs_names.is_unique or not a.var_names.is_unique or min(a.shape)<2:raise ValueError('Unique literal cell/feature axes and sufficient actual observations required')
        if p['unit_key'] not in a.obs or a.obs[p['unit_key']].isna().any():raise ValueError('Complete actual biological-unit mapping required')
        return a
    if mode=='palantir_trajectory':
        import palantir
        a=validate_object(ad.read_h5ad(inputs['object']));rep=a.obsm[p['representation_key']]
        if rep.shape[0]!=a.n_obs or rep.shape[1]<2 or not np.isfinite(rep).all():raise ValueError('Finite cell-aligned metric representation required')
        terminals=p['terminal_cells'];root=p['root_cell']
        if root not in a.obs_names or not set(terminals.values())<=set(a.obs_names) or root in terminals.values():raise ValueError('Actual distinct root and terminal cells required')
        if not 2<=p['knn']<a.n_obs or not 2<=p['num_waypoints']<=a.n_obs or not 2<=p['n_components']<a.n_obs:raise ValueError('Trajectory graph/diffusion/waypoint budgets exceed available cells')
        dm=palantir.utils.run_diffusion_maps(pd.DataFrame(rep,index=a.obs_names),n_components=p['n_components'],knn=p['knn'],alpha=p['alpha'],seed=p['seed'])
        ms=palantir.utils.determine_multiscale_space(dm,n_eigs=p['n_eigs'])
        if not ms.index.equals(a.obs_names):raise ValueError('Diffusion cell-axis changed')
        # Pass exact cell IDs as a list: published prose and dict orientation differ
        # across releases. No alias normalization or automatic root replacement.
        fit=palantir.core.run_palantir(ms,root,terminal_states=list(terminals.values()),knn=p['knn'],num_waypoints=p['num_waypoints'],n_jobs=1,scale_components=p['scale_components'],use_early_cell_as_start=True,max_iterations=p['max_iterations'],seed=p['seed'])
        prob=fit.branch_probs
        if set(prob.index)!=set(a.obs_names) or set(prob.columns)!=set(terminals.values()):raise ValueError('Native trajectory return identity differs; no positional reassignment')
        prob=prob.loc[a.obs_names,list(terminals.values())];arr=prob.to_numpy(float)
        if not np.isfinite(arr).all() or (arr<0).any() or not np.allclose(arr.sum(1),1,atol=1e-6):raise ValueError('Fate probabilities fail numerical QC')
        pseudotime=fit.pseudotime.reindex(a.obs_names);entropy=fit.entropy.reindex(a.obs_names)
        if not np.isfinite(pseudotime).all() or not np.isfinite(entropy).all():raise ValueError('Unreachable or nonfinite trajectory cells; review partitions/root, do not replace with zero')
        prob.columns=list(terminals);emit(prob,'palantir_fate','fate_probabilities');emit(pd.DataFrame({'pseudotime':pseudotime,'entropy':entropy}).join(a.obs[[p['unit_key']]]),'palantir_order','pseudotime');emit(ms,'diffusion_multiscale','diffusion_space')
        a.obs['palantir_pseudotime']=pseudotime;a.obs['palantir_entropy']=entropy;a.obsm['palantir_fate']=prob.to_numpy();a.uns['palantir_terminal_names']=list(terminals);fn=out/'palantir_result.h5ad';a.write_h5ad(fn);outputs.append((fn,'processed_object'))
        diag.update(root=root,terminal_cells=terminals,direction_evidence=p['direction_evidence'],maximum_probability_rowsum_error=float(abs(arr.sum(1)-1).max()),interpretation='Model-conditional pseudotime and fate, not elapsed time or measured ancestry; donor-aware downstream tests remain separate')
    elif mode=='scgen_predict':
        import scgen,scvi,torch
        scvi.settings.seed=p['seed'];torch.manual_seed(p['seed'])
        train=validate_object(ad.read_h5ad(inputs['training_object']));query=validate_object(ad.read_h5ad(inputs['query_controls']))
        if not train.var_names.equals(query.var_names):raise ValueError('Exact ordered feature identity required; no inferred gene alignment')
        for a in [train,query]:
            if not np.isfinite(values(a.X)).all() or (values(a.X)<0).any():raise ValueError('Actual finite nonnegative log-normalized expression required, no scaled or count substitution')
        def rows(a):
            x=a.obs[[p['unit_key'],p['celltype_key'],p['condition_key']]].copy();x.insert(0,'cell_id',a.obs_names);return x.to_dict('records')
        check_split(rows(train),rows(query),p['unit_key'],p['celltype_key'],p['condition_key'],p['control'],p['treatment'],p['holdout_axis'])
        scgen.SCGEN.setup_anndata(train,batch_key=p['condition_key'],labels_key=p['celltype_key'])
        model=scgen.SCGEN(train,n_hidden=p['n_hidden'],n_latent=p['n_latent'],n_layers=p['n_layers'],dropout_rate=p['dropout_rate'])
        model.train(max_epochs=p['max_epochs'],batch_size=p['batch_size'],early_stopping=p['early_stopping'],accelerator=p['accelerator'],devices=1)
        # Restrict the arithmetic shift to reviewed source cell types with both arms.
        types=p['shift_celltypes']
        if not isinstance(types,list) or not types or len(types)!=len(set(types)):raise ValueError('Prespecified unique source cell types for the scGen shift required')
        for ct in types:
            if set(train.obs.loc[train.obs[p['celltype_key']]==ct,p['condition_key']])!={p['control'],p['treatment']}:raise ValueError('Each shift source cell type needs actual control and treatment observations')
        result=model.predict(ctrl_key=p['control'],stim_key=p['treatment'],adata_to_predict=query,restrict_arithmetic_to={p['celltype_key']:types})
        if not isinstance(result,tuple) or len(result)!=2:raise ValueError('Installed scGen prediction API differs from reviewed native tuple return')
        prediction,delta=result
        if not prediction.obs_names.equals(query.obs_names) or not prediction.var_names.equals(query.var_names) or not np.isfinite(values(prediction.X)).all():raise ValueError('Prediction identity or finite-value contract failed')
        prediction.uns['prediction_scale']='scGen decoded log-normalized expression; not observed counts';prediction.uns['target_condition']=p['treatment'];fn=out/'scgen_prediction.h5ad';prediction.write_h5ad(fn);outputs.append((fn,'predicted_expression'))
        np.save(out/'scgen_latent_shift.npy',np.asarray(delta));outputs.append((out/'scgen_latent_shift.npy','latent_shift'));model.save(out/'scgen_model',overwrite=False)
        emit(query.obs[[p['unit_key'],p['condition_key'],p['celltype_key']]],'query_identity','prediction_identity')
        emit(pd.DataFrame(np.asarray(delta).reshape(1,-1)),'latent_shift','latent_shift_table')
        for name,frame in model.history.items():emit(pd.DataFrame(frame),'training_'+name,'training_history')
        for fn in (out/'scgen_model').rglob('*'):
            if fn.is_file():outputs.append((fn,'model_checkpoint'))
        diag.update(n_training_cells=train.n_obs,n_query_cells=query.n_obs,holdout_axis=p['holdout_axis'],shift_celltypes=types,interpretation='Counterfactual model output; evaluate against independently heldout observed responses and the same-split no-change/mean baselines; not causal validation')
    elif mode in {'multivi_integrate','totalvi_integrate'}:
        import mudata as md,scvi,torch
        scvi.settings.seed=p['seed'];torch.manual_seed(p['seed']);m=md.read_h5mu(inputs['object'])
        if not m.obs_names.is_unique or p['unit_key'] not in m.obs or p['batch_key'] not in m.obs or m.obs[[p['unit_key'],p['batch_key']]].isna().any().any():raise ValueError('Global exact MuData identities, donor and technical batch mapping required')
        before={}
        for role,key in p['modalities'].items():
            if key not in m.mod:raise ValueError('Declared measured modality absent')
            a=m.mod[key]
            if not a.obs_names.equals(m.obs_names) or not a.var_names.is_unique:raise ValueError('This paired route requires complete identical ordered observations in each modality')
            x=a.layers[p['layers'][role]];v=values(x)
            if not np.isfinite(v).all() or (v<0).any() or (v!=np.floor(v)).any() or (np.asarray(x.sum(1)).ravel()==0).any():raise ValueError('Each paired observation requires actual nonzero integer counts for every modality')
            before[key]=x.copy()
        cls=scvi.model.MULTIVI if mode=='multivi_integrate' else scvi.model.TOTALVI
        kwargs={k:p['layers'][k] for k in p['modalities']};mapping={**p['modalities'],'batch_key':None}
        cls.setup_mudata(m,**kwargs,batch_key=p['batch_key'],modalities=mapping)
        model=cls(m,n_latent=p['n_latent']);model.train(max_epochs=p['max_epochs'],batch_size=p['batch_size'],accelerator=p['accelerator'],devices=1)
        latent=model.get_latent_representation()
        if latent.shape!=(m.n_obs,p['n_latent']) or not np.isfinite(latent).all():raise ValueError('Finite cell-aligned latent representation contract failed')
        emit(pd.DataFrame(latent,index=m.obs_names),'joint_latent','integrated_representation');emit(m.obs[[p['unit_key'],p['batch_key']]],'modality_identity','cell_metadata')
        for role,key in p['modalities'].items():
            current=m.mod[key].layers[p['layers'][role]]
            if sparse.issparse(current):unchanged=(current!=before[key]).nnz==0
            else:unchanged=np.array_equal(current,before[key])
            if not unchanged:raise ValueError('Native backend modified an observed count layer')
        m.obsm[mode+'_latent']=latent;fn=out/'multimodal_result.h5mu';m.write_h5mu(fn);outputs.append((fn,'processed_object'));model.save(out/'model',overwrite=False)
        for name,frame in model.history.items():emit(pd.DataFrame(frame),'training_'+name,'training_history')
        for fn in (out/'model').rglob('*'):
            if fn.is_file():outputs.append((fn,'model_checkpoint'))
        diag.update(observation_scope=p['observation_scope'],n_observations=m.n_obs,modality_sizes={k:m.mod[k].n_vars for k in before},observed_counts_unchanged=True,interpretation='Joint latent representation; mixing, biological preservation and heldout generalization need separate result acceptance; no decoded values used as raw counts')
    else:raise ValueError('Unsupported additional native Python route')
    write(out/'native_diagnostics.json',diag);outputs.append((out/'native_diagnostics.json','diagnostics'));write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'))
    return outputs
