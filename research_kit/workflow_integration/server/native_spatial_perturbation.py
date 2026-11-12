"""Native spatial and perturbation calls, exclusively behind the server guard."""
from runtime import write,read

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad
    from scipy import sparse
    np.random.seed(p['seed']);outputs=[];diag={'mode':mode,'software_versions':p['software_versions'],'scientific_acceptance':'NOT_ESTABLISHED'}
    def emit(frame,name,role):
        fn=out/(name+'.tsv');frame.to_csv(fn,sep='\t',index=True);outputs.append((fn,role))
    def vals(x):return x.data if sparse.issparse(x) else np.asarray(x)
    def obj(role,layer=None):
        a=ad.read_h5ad(inputs[role])
        if not a.obs_names.is_unique or not a.var_names.is_unique or min(a.shape)<2:raise ValueError('Unique exact observed cell/spot and gene axes required')
        if p['unit_key'] not in a.obs or a.obs[p['unit_key']].isna().any():raise ValueError('Complete real independent-unit mapping required')
        if layer is not None:
            if layer not in a.layers:raise ValueError('Declared count layer absent')
            x=a.layers[layer];v=vals(x)
            if not np.isfinite(v).all() or (v<0).any() or (v!=np.floor(v)).any() or (np.asarray(x.sum(1)).ravel()==0).any():raise ValueError('Actual nonzero-library nonnegative integer counts required')
        return a
    def record_model(model,name):
        model.save(out/name,overwrite=False)
        for fn in (out/name).rglob('*'):
            if fn.is_file():outputs.append((fn,'model_checkpoint'))
        for k,frame in model.history.items():emit(pd.DataFrame(frame),name+'_history_'+k,'training_history')
    if mode=='mixscape_classify':
        import pertpy as pt
        a=obj('object');keys=[p['unit_key'],p['celltype_key'],p['replicate_key'],p['target_key']]
        if any(k not in a.obs for k in keys) or a.obs[keys].isna().any().any():raise ValueError('Reviewed perturbation targets, units, cell types and technical replicate metadata required')
        x=a.layers[p['expression_layer']];v=vals(x)
        if not np.isfinite(v).all() or (v<0).any() or p['expression_scale']!='log1p_normalized':raise ValueError('Mixscape marker fold changes require observed log1p-normalized expression, not scaled residuals')
        a.X=x.copy();groupkeys=list(dict.fromkeys([p['unit_key'],p['celltype_key'],p['replicate_key']]))
        codes,levels=pd.factorize(pd.MultiIndex.from_frame(a.obs[groupkeys]),sort=False)
        a.obs['_reviewed_mixscape_stratum']=['stratum_'+str(i) for i in codes]
        for group,sub in a.obs.groupby('_reviewed_mixscape_stratum',observed=True):
            n_control=int((sub[p['target_key']]==p['control']).sum())
            if n_control<p['n_neighbors'] or n_control<3:raise ValueError('Each unit/celltype/replicate stratum needs enough actual non-targeting controls; no cross-unit borrowing')
        model=pt.tl.Mixscape();model.perturbation_signature(a,pert_key=p['target_key'],control=p['control'],split_by='_reviewed_mixscape_stratum',ref_selection_mode='nn',n_neighbors=p['n_neighbors'],use_rep=p['representation_key'],n_dims=p['n_dims'],copy=False)
        model.mixscape(a,pert_key=p['target_key'],control=p['control'],layer='X_pert',de_layer=p['expression_layer'],split_by='_reviewed_mixscape_stratum',min_de_genes=p['min_de_genes'],logfc_threshold=p['logfc_threshold'],test_method=p['test_method'],iter_num=p['max_iterations'],scale=p['scale_signature'],pval_cutoff=p['pvalue_cutoff'],perturbation_type=p['perturbation_type'],random_state=p['seed'],copy=False)
        prob='mixscape_class_p_'+p['perturbation_type'].lower();required=['mixscape_class','mixscape_class_global',prob]
        if not set(required)<=set(a.obs):raise ValueError('Installed native Mixscape output schema differs')
        numeric=pd.to_numeric(a.obs[prob],errors='raise');known=numeric.notna()
        if ((numeric[known]<0)|(numeric[known]>1)).any():raise ValueError('Invalid returned perturbation probability')
        emit(a.obs[keys+required+['_reviewed_mixscape_stratum']],'mixscape_classification','perturbation_classification')
        emit(a.obs.groupby(groupkeys+['mixscape_class_global'],observed=True,dropna=False).size().rename('n_cells').to_frame(),'mixscape_composition','classification_by_unit')
        fn=out/'mixscape_result.h5ad';a.write_h5ad(fn);outputs.append((fn,'processed_object'));diag.update(n_cells=a.n_obs,unassessed_probability_cells=int((~known).sum()),n_strata=len(levels),cells_automatically_removed=0,interpretation='Native perturbation-response classification; NP/unknown retained, not proof that editing or target engagement failed; no automatic selection for DE')
    elif mode=='cellot_predict':
        import torch,importlib.metadata
        from cellot.models.cellot import load_networks
        from cellot.networks.icnns import ICNN
        import inspect
        expected_sources={load_networks:'15235c303567291e775ad32eeb2e9c3260ef4adc9014b40d256e56b0355660f2',ICNN:'380b0ae3d3a687e40e8c08e709e7a85b11bcfa7a9626cefbdc3eb8bae3ac3a35'}
        for component,digest in expected_sources.items():
            if __import__('runtime').sha(inspect.getsourcefile(component))!=digest:raise ValueError('Installed CellOT author source differs from the exact reviewed native implementation; review that version before dispatch')
        a=obj('query_controls');config=read(inputs['model_config']);lineage=read(inputs['checkpoint_lineage'])
        if set(a.obs[p['condition_key']])!={p['control']} or p['representation']!='author_model_feature_space':raise ValueError('Actual control cells in the author checkpoint feature space required')
        features=lineage.get('ordered_features');training_units=lineage.get('training_units');training_cells=lineage.get('training_cell_ids')
        if features!=list(a.var_names) or not isinstance(training_units,list) or not training_units or not isinstance(training_cells,list) or not training_cells:raise ValueError('Actual checkpoint ordered feature, training unit and cell identity provenance required')
        if set(training_cells)&set(a.obs_names) or (p['holdout_axis']=='unit' and set(training_units)&set(a.obs[p['unit_key']])):raise ValueError('CellOT prediction holdout leaks training observations')
        if lineage.get('checkpoint_sha256')!=__import__('runtime').sha(inputs['checkpoint']) or lineage.get('target_condition')!=p['treatment'] or lineage.get('representation')!=p['representation']:raise ValueError('Checkpoint is not bound to this exact task and representation')
        if not isinstance(config,dict) or set(config)!={'model'} or config['model'].get('name')!='cellot':raise ValueError('Exact architecture-only CellOT JSON required; no arbitrary config includes or data paths')
        allowed={'name','hidden_units','activation','softplus_W_kernels','softplus_beta','std','fnorm_penalty','kernel_init_fxn','f','g'}
        if set(config['model'])-allowed or any(set(config['model'].get(k,{}))-allowed for k in ['f','g']):raise ValueError('Unreviewed CellOT architecture parameters')
        for cfg in [config['model'],config['model'].get('f',{}),config['model'].get('g',{})]:
            if 'kernel_init_fxn' in cfg and cfg['kernel_init_fxn'].get('name') not in {'normal','uniform'}:raise ValueError('Only reviewed built-in initialization functions permitted')
        v=vals(a.X)
        if not np.isfinite(v).all():raise ValueError('Finite actual author-model features required')
        f,g=load_networks(config,input_dim=a.n_vars)
        # Never use the upstream unrestricted pickle loader for an imported checkpoint.
        state=torch.load(inputs['checkpoint'],map_location='cpu',weights_only=True)
        if not {'f_state','g_state'}<=set(state):raise ValueError('Native CellOT state dictionary keys absent')
        f.load_state_dict(state['f_state'],strict=True);g.load_state_dict(state['g_state'],strict=True);g.eval();blocks=[]
        for first in range(0,a.n_obs,p['batch_size']):
            x=a.X[first:first+p['batch_size']];x=x.toarray() if sparse.issparse(x) else np.asarray(x)
            tensor=torch.as_tensor(x,dtype=torch.float32).requires_grad_(True)
            blocks.append(g.transport(tensor).detach().cpu().numpy())
        prediction=np.concatenate(blocks)
        if prediction.shape!=a.shape or not np.isfinite(prediction).all():raise ValueError('Native transport prediction dimension/finite-value QC failed')
        result=ad.AnnData(prediction,obs=a.obs.copy(),var=a.var.copy());result.uns['prediction_scale']='CellOT checkpoint feature space; not observed counts';fn=out/'cellot_prediction.h5ad';result.write_h5ad(fn);outputs.append((fn,'predicted_expression'))
        emit(a.obs[[p['unit_key'],p['condition_key']]],'cellot_query_identity','prediction_identity');emit(pd.DataFrame({'feature_id':a.var_names,'mean_predicted':prediction.mean(0),'mean_control':np.asarray(a.X.mean(0)).ravel()}),'cellot_feature_summary','prediction_summary')
        diag.update(n_query_cells=a.n_obs,n_features=a.n_vars,holdout_axis=p['holdout_axis'],checkpoint_sha256=lineage['checkpoint_sha256'],interpretation='Native ICNN gradient transport from reviewed existing CellOT checkpoint. This route does not train CellOT or claim experimental single-cell pairing/causal response')
    elif mode in {'destvi_deconvolution','cell2location_reference','cell2location_map'}:
        import scvi,torch
        scvi.settings.seed=p['seed'];torch.manual_seed(p['seed'])
        if mode=='cell2location_reference':
            import cell2location as c2l
            a=obj('reference',p['count_layer']);key=p['celltype_key']
            if key not in a.obs or p['batch_key'] not in a.obs or a.obs[[key,p['batch_key']]].isna().any().any():raise ValueError('Actual reference labels and technical batch annotation required')
            c2l.models.RegressionModel.setup_anndata(a,layer=p['count_layer'],batch_key=p['batch_key'],labels_key=key)
            model=c2l.models.RegressionModel(a);model.train(max_epochs=p['max_epochs'],batch_size=p['batch_size'],train_size=1,lr=p['learning_rate'],accelerator=p['accelerator'],devices=1)
            a=model.export_posterior(a,use_quantiles=True,add_to_varm=['q05','q50','q95'],sample_kwargs={'batch_size':p['batch_size'],'accelerator':p['accelerator']})
            factors=list(a.uns['mod']['factor_names'])
            for q in ['q05','q50','q95']:
                raw=a.varm[q+'_per_cluster_mu_fg']
                frame=pd.DataFrame(raw,index=a.var_names)
                expected=[q+'_per_cluster_mu_fg_'+str(x) for x in factors]
                # Use the native labelled columns; never assign cell types by position.
                if list(frame.columns)!=expected:raise ValueError('Native reference signature column identity differs from reviewed schema')
                frame.columns=factors
                if not np.isfinite(frame.to_numpy()).all() or (frame.to_numpy()<0).any():raise ValueError('Invalid native reference signatures')
                emit(frame,'reference_signature_'+q,'reference_signatures' if q=='q50' else 'reference_signature_uncertainty')
            record_model(model,'reference_model');fn=out/'reference_result.h5ad';a.write_h5ad(fn);outputs.append((fn,'processed_object'));diag.update(n_reference_cells=a.n_obs,n_celltypes=len(factors),reference_summary='Posterior median q50, not posterior mean',interpretation='Reference-conditional NB signatures. Transfer requires exact genes/species and independent spatial QC')
        else:
            spatial=obj('object',p['count_layer']);coords=spatial.obsm[p['spatial_key']]
            if coords.shape[0]!=spatial.n_obs or coords.shape[1]<2 or not np.isfinite(coords).all() or not p['coordinate_unit']:raise ValueError('Actual spatial coordinate identity and declared units required')
            if p['batch_key'] not in spatial.obs or spatial.obs[p['batch_key']].isna().any():raise ValueError('Actual spatial section/batch identities required')
            if mode=='destvi_deconvolution':
                ref=obj('reference',p['reference_count_layer'])
                if not ref.var_names.equals(spatial.var_names) or p['celltype_key'] not in ref.obs or ref.obs[p['celltype_key']].isna().any():raise ValueError('Exact ordered common genes and real reference celltype labels required; resolve mappings upstream')
                scvi.model.CondSCVI.setup_anndata(ref,layer=p['reference_count_layer'],labels_key=p['celltype_key'])
                reference_model=scvi.model.CondSCVI(ref,n_latent=p['n_latent'],weight_obs=p['weight_reference_observations']);reference_model.train(max_epochs=p['reference_max_epochs'],batch_size=p['batch_size'],accelerator=p['accelerator'],devices=1)
                scvi.model.DestVI.setup_anndata(spatial,layer=p['count_layer'],batch_key=p['batch_key'])
                model=scvi.model.DestVI.from_rna_model(spatial,reference_model,vamp_prior_p=p['vamp_prior_p']);model.train(max_epochs=p['max_epochs'],batch_size=p['batch_size'],accelerator=p['accelerator'],devices=1)
                proportions=model.get_proportions();arr=proportions.to_numpy(float)
                if not proportions.index.equals(spatial.obs_names) or not np.isfinite(arr).all() or (arr<0).any() or not np.allclose(arr.sum(1),1,atol=1e-6):raise ValueError('Native DestVI fractions fail numerical/identity QC')
                emit(proportions,'destvi_proportions','celltype_proportions');gamma=model.get_gamma(return_numpy=False)
                for i,(ct,frame) in enumerate(gamma.items()):
                    if not frame.index.equals(spatial.obs_names) or not np.isfinite(frame.to_numpy()).all():raise ValueError('Celltype-specific spatial state identity failed')
                    emit(frame,'destvi_gamma_'+str(i),'celltype_latent_state')
                write(out/'destvi_state_map.json',{str(i):str(ct) for i,ct in enumerate(gamma)});outputs.append((out/'destvi_state_map.json','celltype_state_identity'));record_model(reference_model,'reference_model')
                diag.update(maximum_probability_rowsum_error=float(abs(arr.sum(1)-1).max()),n_celltypes=proportions.shape[1],interpretation='Reference-conditional fractions and latent states, not experimentally resolved single cells or absolute counts')
            else:
                import cell2location as c2l
                signatures=pd.read_csv(inputs['reference_signatures'],sep='\t',index_col=0)
                if not signatures.index.equals(spatial.var_names) or not signatures.columns.is_unique or not np.isfinite(signatures.to_numpy(float)).all() or (signatures.to_numpy()<0).any():raise ValueError('Actual source-bound, gene-aligned nonnegative reference signature matrix required')
                c2l.models.Cell2location.setup_anndata(spatial,layer=p['count_layer'],batch_key=p['batch_key'])
                model=c2l.models.Cell2location(spatial,cell_state_df=signatures,N_cells_per_location=p['cells_per_location'],detection_alpha=p['detection_alpha']);model.train(max_epochs=p['max_epochs'],batch_size=p['batch_size'],train_size=1,lr=p['learning_rate'],accelerator=p['accelerator'],devices=1)
                spatial=model.export_posterior(spatial,use_quantiles=True,add_to_obsm=['q05','q50','q95'],sample_kwargs={'batch_size':p['batch_size'],'accelerator':p['accelerator']})
                arrays=[]
                for q in ['q05','q50','q95']:
                    name=q+'_cell_abundance_w_sf'
                    if name not in spatial.obsm:raise ValueError('Native posterior did not return a labelled abundance matrix; inspect alternate obs export instead of guessing')
                    frame=spatial.obsm[name]
                    if not isinstance(frame,pd.DataFrame) or not frame.index.equals(spatial.obs_names) or not np.isfinite(frame.to_numpy()).all() or (frame.to_numpy()<0).any():raise ValueError('Invalid native posterior abundance axes/values')
                    emit(frame,'cell2location_abundance_'+q,'celltype_abundance' if q=='q50' else 'abundance_uncertainty');arrays.append(frame.to_numpy())
                if (arrays[0]>arrays[1]).any() or (arrays[1]>arrays[2]).any():raise ValueError('Native posterior abundance quantiles are not ordered')
                diag.update(n_celltypes=signatures.shape[1],cells_per_location_prior=p['cells_per_location'],prior_basis=p['prior_basis'],interpretation='Model-dependent posterior cell abundance, not histologically measured absolute counts; median and uncertainty retained')
            emit(spatial.obs[[p['unit_key'],p['batch_key']]],'spatial_identity','spatial_identity');record_model(model,'spatial_model');fn=out/'spatial_result.h5ad';spatial.write_h5ad(fn);outputs.append((fn,'processed_object'));diag['n_spots']=spatial.n_obs
    else:raise ValueError('Unknown fixed native spatial/perturbation mode')
    write(out/'native_diagnostics.json',diag);outputs.append((out/'native_diagnostics.json','diagnostics'));write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'));return outputs
