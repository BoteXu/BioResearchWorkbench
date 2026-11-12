"""Native CausCell with stable concept coding and preserved identity/unknowns."""
import os,inspect
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    if not os.environ.get('CUDA_VISIBLE_DEVICES'):raise ValueError('Reuse an explicit existing GPU allocation; original CausCell must not choose its hard-coded default GPU 3')
    import numpy as np,pandas as pd,anndata as ad,torch
    from scipy import sparse
    from causcell import CausCell
    if sha(inspect.getsourcefile(CausCell))!='594e665efea56ce30e58ab11b1a5601e380c86f075b5460274323f34288c7e9f':raise ValueError('Installed original CausCell differs from the exact reviewed primary source')
    original=ad.read_h5ad(inputs['object']);a=original.copy();concepts=p['concepts'];coding=read(inputs['concept_mapping']);outputs=[]
    keys=[p['unit_key']]+concepts
    if not a.obs_names.is_unique or not a.var_names.is_unique or not set(keys)<=set(a.obs) or a.obs[keys].isna().any().any() or a.n_vars!=p['profile_size']:raise ValueError('Literal complete actual cell/gene/unit/concept identities and exact selected model feature count required; no native feature truncation')
    x=a.layers[p['expression_layer']];x=x.toarray() if sparse.issparse(x) else np.asarray(x)
    if p['expression_scale']!='log_normalized_expression' or not np.isfinite(x).all() or (x<0).any() or a.n_obs*a.n_vars>p['maximum_dense_expression_entries']:raise ValueError('Actual bounded nonnegative log expression required')
    a.X=x.copy();counts=[]
    # The original helper encodes labels independently in each dataset and drops
    # cell/gene IDs. Use an explicit shared codebook without that helper; leave
    # expression values and the literal observed axes unchanged.
    for concept in concepts:
        labels=coding.get(concept)
        if not isinstance(labels,list) or len(labels)<2 or len(set(labels))!=len(labels) or set(labels)!=set(a.obs[concept]):raise ValueError('Exact complete observed concept vocabulary/order required')
        a.obs[concept]=a.obs[concept].map({v:i for i,v in enumerate(labels)}).astype(int);counts.append(len(labels))
    targets=[];selected=np.ones(a.n_obs,dtype=bool)
    for row in p['interventions']:
        concept=row['concept'];values=coding[concept];reference=values.index(row['reference']);target=values.index(row['target']);selected&=a.obs[concept].to_numpy()==reference
        targets.append({'target_factor':concept,'ref_factor_value':reference,'tgt_factor_value':target})
    if selected.sum()<p['minimum_source_cells']:raise ValueError('Actual source concept combination lacks support')
    if a.obs[p['unit_key']].nunique()<p['minimum_units']:raise ValueError('Actual independent-unit support below the reviewed descriptive-fit requirement')
    prepared=out/'causcell_encoded.h5ad';a.write_h5ad(prepared);outputs.append((prepared,'encoded_object'));write(out/'concept_mapping.json',coding);outputs.append((out/'concept_mapping.json','concept_mapping'))
    model=CausCell(device='cuda',save_and_sample_every=p['checkpoint_every']);model.train(training_data_pwd=str(prepared),model_save_pwd=str(out/'model'),concept_list=concepts,concept_counts=counts,concept_cdag=p['causal_dag'],loss_type='l2',training_num_steps=p['training_steps'],training_batch_size=p['batch_size'],training_lr=p['learning_rate'],max_profile_size=a.n_vars,timesteps=p['diffusion_steps'],seed=p['seed'],train_log=True)
    model.model.eval()
    # Compatibility repair of the native generation boundary: the original
    # floor(n/batch)+1 loop issues an empty final batch for exact multiples and
    # discards gene identifiers. Keep its actual sampler and supplied latent
    # tensor; use nonempty bounded slices and the bound decoder feature axis.
    def generate(model,concept_embs,save_pwd,factor_list,factor_counts,factor_cdag,factor_df,name,batch_size):
        tensor=np.asarray(concept_embs);pieces=[]
        if tensor.ndim!=3 or tensor.shape[1]!=len(factor_df):raise ValueError('Actual concept/cell latent identity dimensions differ')
        with torch.no_grad():
            for start in range(0,tensor.shape[1],batch_size):
                z=torch.as_tensor(tensor[:,start:start+batch_size,:].transpose(1,0,2),device='cuda');pieces.append(model.sample_with_factor(concept_embs=z,batch_size=z.shape[0]).detach().cpu().numpy())
        matrix=np.concatenate(pieces)
        if matrix.shape!=(len(factor_df),a.n_vars) or not np.isfinite(matrix).all():raise ValueError('Native CausCell generated expression is nonfinite or feature/cell dimensions differ')
        result=ad.AnnData(X=matrix,obs=factor_df.copy(),var=a.var.copy());result.write_h5ad(out/(name+'.h5ad'));return result
    function=model.counterfactual_generation.__func__;prior=function.__globals__['generation_based_concept_embs'];function.__globals__['generation_based_concept_embs']=generate
    try:result=model.counterfactual_generation(data_pwd=str(prepared),save_pwd=str(out),concept_list=concepts,concept_counts=counts,concept_cdag=p['causal_dag'],multi_target_list=targets,file_name='causcell_counterfactuals',batch_size=p['batch_size'])
    finally:function.__globals__['generation_based_concept_embs']=prior
    n=int(selected.sum())
    if result.n_obs!=2*n or not result.var_names.equals(a.var_names) or not list(result.obs_names)==list(a.obs_names[selected])*2:raise ValueError('Native counterfactual source-cell/gene axes differ')
    result.obs['source_cell_id']=result.obs_names.astype(str);result.obs['native_Type']=result.obs['Type'];result.obs['result_scope']=['model_counterfactual']*n+['model_reference_reconstruction']*n
    # Duplicate source cell IDs across model conditions are expected, but each
    # explicit (source, result scope) key must be unique.
    if result.obs[['source_cell_id','result_scope']].duplicated().any():raise ValueError('Native generation duplicated a source/result identity')
    result.write_h5ad(out/'causcell_native_raw.h5ad');outputs.append((out/'causcell_native_raw.h5ad','native_raw_prediction'))
    result.obs['native_observation_id']=result.obs_names.astype(str);result.obs_names=pd.Index(['model_record_'+str(i) for i in range(result.n_obs)])
    for concept in concepts:
        result.obs['model_concept_label::'+concept]=result.obs[concept].astype(str).map({str(i):value for i,value in enumerate(coding[concept])})
        if result.obs['model_concept_label::'+concept].isna().any():raise ValueError('Native generated concept code has no exact codebook value')
    result.write_h5ad(out/'causcell_counterfactuals.h5ad');outputs.append((out/'causcell_counterfactuals.h5ad','predicted_expression'));result.obs.to_csv(out/'prediction_identity.tsv',sep='\t');outputs.append((out/'prediction_identity.tsv','prediction_identity'));original.obs.loc[a.obs_names[selected],keys].to_csv(out/'actual_source_identity.tsv',sep='\t');outputs.append((out/'actual_source_identity.tsv','observed_source_identity'))
    for fn in (out/'model').rglob('*'):
        if fn.is_file():outputs.append((fn,'model_checkpoint' if fn.suffix=='.pt' else 'native_training_artifact'))
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_actual_source_cells':n,'n_model_generated_profiles':result.n_obs,'feature_axes_preserved':True,'concept_mapping_stable':True,'scientific_acceptance':'NOT_ESTABLISHED','compatibility_repairs':['Explicit stable concept codebook preserving observed axes, bypassing lossy per-dataset helper','Nonempty generation batches and explicit trained decoder feature axis'],'interpretation':'Native original CausCell descriptive fit and within-observed-vocabulary concept intervention under a user-reviewed assumed DAG. DAG is assumed, not discovered/proven causal. Both native Generated and Original halves are model outputs; Original is a reconstruction, not measured truth. No heldout-donor predictive validation or experimental pairing asserted.'});outputs.append((out/'diagnostics.json','diagnostics'));write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
