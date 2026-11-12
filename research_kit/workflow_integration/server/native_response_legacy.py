"""Native biolord attribute model and original legacy scVIDR response holdout."""
from pathlib import Path
import sys,random,inspect
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad,torch,scvi
    from scipy import sparse
    random.seed(p['seed']);np.random.seed(p['seed']);torch.manual_seed(p['seed']);scvi.settings.seed=p['seed'];a=ad.read_h5ad(inputs['object']);outputs=[]
    keys=[p['unit_key'],p['celltype_key'],p['condition_key']]
    if not a.obs_names.is_unique or not a.var_names.is_unique or not set(keys)<=set(a.obs) or a.obs[keys].isna().any().any():raise ValueError('Literal unique cell/gene identities and actual complete independent-unit/type/condition metadata required')
    x=a.layers[p['expression_layer']];values=x.data if sparse.issparse(x) else np.asarray(x)
    if p['expression_scale']!='log_normalized_expression' or not np.isfinite(values).all() or (values<0).any():raise ValueError('Actual observed nonnegative log-normalized expression required; no z-scored/count substitution')
    a.X=x.copy()
    if 'source_cell_id' in a.obs:raise ValueError('Reserved exact source-identity field already exists; resolve explicitly')
    a.obs['source_cell_id']=a.obs_names.astype(str)
    def emit(frame,name,role):
        fn=out/(name+'.tsv');frame.to_csv(fn,sep='\t',index=True,na_rep='NA');outputs.append((fn,role))
    diag={'mode':mode,'software_versions':p['software_versions'],'scientific_acceptance':'NOT_ESTABLISHED'}
    if mode=='biolord_attributes':
        import biolord
        if sha(inspect.getsourcefile(biolord.Biolord))!='7bf54d8483563edd3d4e1cf3a972514d005db93dbd06b0b71dc45d5f95e085ac':raise ValueError('Native biolord implementation differs from exact source review')
        categorical=p['categorical_attributes'];ordered=p['ordered_attributes'];attributes=categorical+ordered
        if not set(attributes)<=set(a.obs) or a.obs[attributes].isna().any().any():raise ValueError('Actual complete observed categorical/continuous attributes required')
        for key in ordered:
            if not np.isfinite(a.obs[key].to_numpy(float)).all() or a.obs[key].nunique()<2:raise ValueError('Ordered attributes must be observed finite nonconstant quantities')
        for key in categorical:
            if a.obs[key].nunique()<2:raise ValueError('Categorical attributes need actual observed variation')
        biolord.Biolord.setup_anndata(a,ordered_attributes_keys=ordered,categorical_attributes_keys=categorical,layer=p['expression_layer'])
        parameters=dict(p['module_parameters']);parameters.update(gene_likelihood='normal',seed=p['seed'])
        model=biolord.Biolord(a,n_latent=p['n_latent'],module_params=parameters,train_classifiers=False)
        model.train(max_epochs=p['max_epochs'],accelerator=p['accelerator'],device='auto',batch_size=p['batch_size'],train_size=p['optimization_train_fraction'],validation_size=1-p['optimization_train_fraction'],early_stopping=p['early_stopping'],plan_kwargs=p['training_plan'])
        indices=np.asarray(model.train_indices,dtype=int)
        if indices.ndim!=1 or not len(indices) or len(set(indices))!=len(indices) or (indices<0).any() or (indices>=a.n_obs).any():raise ValueError('Actual native optimizer training indices unavailable; do not guess a split')
        model.module.eval();unknown,full=model.get_latent_representation_adata(a,indices=indices,batch_size=p['batch_size'])
        for obj,name in [(unknown,'biolord_unknown_attributes'),(full,'biolord_full_attributes')]:
            if not obj.obs_names.equals(a.obs_names[indices]) or not np.isfinite(obj.X).all():raise ValueError('Native fitted-cell latent identity/numerical QC failed')
            emit(pd.DataFrame(obj.X,index=obj.obs_names),name,'attribute_representation')
        a.obs['optimizer_training_cell']=a.obs_names.isin(a.obs_names[indices]);emit(a.obs[keys+['source_cell_id','optimizer_training_cell']],'biolord_identity','split_identity')
        controls=a[indices][a[indices].obs[p['condition_key']]==p['control']].copy()
        if not controls.n_obs:raise ValueError('Actual optimizer-trained observed control cells required for attribute counterfactuals')
        added=[k for k in ['source_cell_id',p['unit_key'],p['celltype_key']] if k not in p['prediction_attributes']]
        predicted=model.compute_prediction_adata(a,adata_source=controls,target_attributes=p['prediction_attributes'],add_attributes=added)
        if not predicted.var_names.equals(a.var_names) or 'source_cell_id' not in predicted.obs or not set(predicted.obs.source_cell_id)<=set(controls.obs_names) or not np.isfinite(predicted.X).all():raise ValueError('Native counterfactual feature or explicit source-cell identity/numerical QC failed')
        if predicted.obs[['source_cell_id']+p['prediction_attributes']].duplicated().any():raise ValueError('Native counterfactual identity combinations duplicate')
        fn=out/'biolord_counterfactuals.h5ad';predicted.write_h5ad(fn);outputs.append((fn,'predicted_expression'));emit(predicted.obs,'biolord_prediction_identity','prediction_identity');model.save(str(out/'native_model'),overwrite=False,save_anndata=True)
        diag.update(n_fitted_cells=len(indices),n_predictions=predicted.n_obs,validation_scope='descriptive_attribute_fit_optimizer_cell_split_only',interpretation='Native biolord normal-likelihood attribute model and supported counterfactual combinations on actual optimizer-trained control cells. Source IDs propagated as explicit metadata, never recovered by stripping native suffixes. Random-cell monitoring and fitted-cell counterfactuals are not independent-donor generalization or causal identification; held-out unknown embeddings are not interpreted.')
    else:
        from native_genetics import reference_manifest
        source,members=reference_manifest(inputs['source_manifest']);root=(inputs['source_manifest'].parent/source['module_directory']).resolve()
        if not root.is_relative_to(inputs['source_manifest'].parent.resolve()) or (root/'vidr.py').resolve() not in {q.resolve() for q in members.values()} or sha(root/'vidr.py')!='831466dadc261117bbdbc75858bd67de671569781e7b4e8f165e438a9a1087c3':raise ValueError('Exact reviewed existing original scVIDR source directory required')
        if not {q.resolve() for q in root.glob('*.py')}<={q.resolve() for q in members.values()}:raise ValueError('Every original local scVIDR module must be bound')
        sys.path.insert(0,str(root));from vidr import VIDR
        from scvi.data import setup_anndata
        if set(a.obs[p['condition_key']])!={p['control'],p['treatment']}:raise ValueError('Original discrete scVIDR route needs exactly two declared observed conditions')
        held=(a.obs[p['celltype_key']]==p['target_celltype'])&(a.obs[p['condition_key']]==p['treatment'])
        if not held.any():raise ValueError('Actual heldout celltype-response observations required for a verifiable response-holdout benchmark')
        truth=a[held].copy();train=a[~held].copy();query=train[(train.obs[p['celltype_key']]==p['target_celltype'])&(train.obs[p['condition_key']]==p['control'])]
        support=pd.crosstab(train.obs[p['celltype_key']],train.obs[p['condition_key']]);others=support.drop(index=p['target_celltype'],errors='ignore')
        if not query.n_obs or others.shape[0]<2 or (others[[p['control'],p['treatment']]]<p['minimum_cells_per_arm']).any().any():raise ValueError('Actual balanced-arm support in at least two other cell types and query controls required')
        train=setup_anndata(train,copy=True,batch_key=p['condition_key'],labels_key=p['celltype_key'])
        model=VIDR(train,hidden_dim=p['n_hidden'],latent_dim=p['n_latent'],n_hidden_layers=p['n_layers'],dropout_rate=p['dropout_rate'],kl_weight=p['kl_weight'],linear_decoder=False,continuous=False,nca_loss=False,dose_loss=False)
        model.train(max_epochs=p['max_epochs'],batch_size=p['batch_size'],use_gpu=p['use_gpu'],train_size=p['optimization_train_fraction'],validation_size=1-p['optimization_train_fraction'],early_stopping=p['early_stopping'])
        result=model.predict(ctrl_key=p['control'],treat_key=p['treatment'],cell_type_to_predict=p['target_celltype'],regression=p['regression'],continuous=False,low_dose=False)
        predicted,delta=result[:2]
        if not predicted.var_names.equals(a.var_names) or 'source_cell_id' not in predicted.obs or not set(predicted.obs.source_cell_id)<=set(query.obs_names) or not np.isfinite(predicted.X).all() or not np.isfinite(delta).all():raise ValueError('Native scVIDR prediction gene/source identity or latent-shift QC failed')
        fn=out/'scvidr_predictions.h5ad';predicted.write_h5ad(fn);outputs.append((fn,'predicted_expression'));fn=out/'scvidr_heldout_truth.h5ad';truth.write_h5ad(fn);outputs.append((fn,'heldout_expression'));emit(predicted.obs,'scvidr_prediction_identity','prediction_identity');emit(pd.DataFrame({'latent_dimension':np.arange(len(delta)),'delta':delta}),'scvidr_shift','latent_shift_table')
        ledger=query.obs[keys+['source_cell_id']].copy();ledger['native_prediction_count']=ledger.source_cell_id.map(predicted.obs.source_cell_id.value_counts()).fillna(0).astype(int);emit(ledger,'scvidr_sampling_ledger','prediction_attrition');emit(truth.obs[keys+['source_cell_id']],'scvidr_heldout_identity','heldout_identity');model.save(str(out/'native_model'),overwrite=False)
        if p['regression']:
            reg=result[2];emit(pd.DataFrame(reg.coef_),'scvidr_regression_coefficients','latent_regression')
        diag.update(n_predictions=predicted.n_obs,n_query_controls=query.n_obs,n_heldout_truth=truth.n_obs,holdout_scope='celltype_treated_response_only_controls_in_training',interpretation='Actual original legacy discrete scVIDR, optional native centroid-delta regression. Query controls are in VAE training; held out is their cell-type treated response, not donors. Native balancing can subsample or duplicate cells; explicit source identity/count ledger retained. Decoded log expression is not measured counts or experimentally paired response.')
    for fn in (out/'native_model').rglob('*'):
        if fn.is_file():outputs.append((fn,'model_checkpoint'))
    for name,frame in model.history.items():emit(pd.DataFrame(frame),'training_'+name,'training_history')
    write(out/'diagnostics.json',diag);outputs.append((out/'diagnostics.json','diagnostics'));write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
