"""Native SHAP on the fitted, fold-contained pipeline; no re-fitting or unsafe pickle loading."""
import math

def contract(config,train_units,test_units,features):
    if not isinstance(config,dict) or config.get('algorithm')!='permutation' or config.get('output') not in {'response','probability','decision_function'}:raise ValueError('Explicit supported native SHAP algorithm and model output required')
    if not isinstance(config.get('models'),list) or not config['models'] or len(set(config['models']))!=len(config['models']) or any(not isinstance(k,str) or not k for k in config['models']):raise ValueError('Explicit unique fitted model IDs to explain required')
    for key in ['background_units','explain_units']:
        if not isinstance(config.get(key),list) or not config[key] or len(set(config[key]))!=len(config[key]):raise ValueError('Unique prespecified exact SHAP background/explanation units required')
    if not set(config['background_units'])<=set(train_units) or not set(config['explain_units'])<=set(test_units):raise ValueError('SHAP background must be training-only and explained units must be locked test units')
    if set(config['background_units'])&set(config['explain_units']):raise ValueError('SHAP background/test leakage')
    for key in ['maximum_background_units','maximum_explain_units','max_evals']:
        if type(config.get(key)) is not int or config[key]<1:raise ValueError('Positive bounded SHAP budget required')
    if len(config['background_units'])>config['maximum_background_units'] or len(config['explain_units'])>config['maximum_explain_units'] or config['max_evals']<2*len(features)+1:raise ValueError('SHAP budget does not support selected units/features')
    if not isinstance(config.get('software_version'),str) or not config['software_version']:raise ValueError('Pin installed server SHAP version')
    if type(config.get('additivity_tolerance')) not in (int,float) or not math.isfinite(config['additivity_tolerance']) or config['additivity_tolerance']<=0:raise ValueError('Finite positive output-scale additivity criterion required')
    return True

def display_metadata(config):
    """Output provenance only; no scientific engine is initialized."""
    output=config['output']
    unit='probability' if output=='probability' else 'model decision score' if output=='decision_function' else config.get('response_unit','model response units (unspecified)')
    if not isinstance(unit,str) or not unit.strip():raise ValueError('Response unit must be explicit nonempty text')
    return {'output':output,'output_name':str(config.get('class_label',config.get('response_name','model response'))),
            'link':'identity','contribution_unit':unit,
            'original_feature_values_scale':'original supplied feature units; preprocessing stays inside fitted predictor'}


def explain(predict,features_frame,unit_ids,config,features,seed,out,name):
    from runtime import write
    import importlib.metadata
    if importlib.metadata.version('shap')!=config['software_version']:raise ValueError('Installed SHAP differs from reviewed version')
    import numpy as np,pandas as pd,shap
    lookup={str(v):i for i,v in enumerate(unit_ids)}
    background=features_frame.iloc[[lookup[v] for v in config['background_units']]].copy();query=features_frame.iloc[[lookup[v] for v in config['explain_units']]].copy()
    # Predictor receives original features. Every imputer, scaler and selector is
    # the already fitted training-fold pipeline, never learned again for SHAP.
    def fn(x):return np.asarray(predict(pd.DataFrame(x,columns=features)),dtype=float).reshape(-1)
    masker=shap.maskers.Independent(background.to_numpy(),max_samples=len(background))
    explainer=shap.PermutationExplainer(fn,masker,feature_names=features,seed=seed)
    result=explainer(query.to_numpy(),max_evals=config['max_evals'],batch_size='auto',silent=True)
    values=np.asarray(result.values);base=np.asarray(result.base_values).reshape(-1);pred=fn(query.to_numpy())
    if values.shape!=query.shape or base.shape!=(len(query),) or not np.isfinite(values).all() or not np.isfinite(base).all() or not np.isfinite(pred).all():raise ValueError('Native SHAP numerical/feature/observation dimensions failed')
    error=np.abs(base+values.sum(1)-pred)
    np.savez_compressed(out/(name+'_shap.npz'),values=values,base_values=base,model_output=pred,original_feature_values=query.to_numpy(float),feature_names=np.asarray(features,dtype=str),unit_ids=np.asarray(config['explain_units'],dtype=str))
    summary=pd.DataFrame({'feature_id':features,'mean_abs_shap':abs(values).mean(0),'mean_shap':values.mean(0)})
    summary.to_csv(out/(name+'_shap_summary.tsv'),sep='\t',index=False)
    identity=pd.DataFrame({'unit_id':config['explain_units'],'base_value':base,'model_output':pred,'sum_shap':values.sum(1),'absolute_additivity_error':error});identity.to_csv(out/(name+'_shap_identity.tsv'),sep='\t',index=False)
    diagnostic={'model':name,'algorithm':'native_shap_PermutationExplainer',**display_metadata(config),'scientific_runtime':'completed native explanation in producer only; downstream receipts still required','software_version':config['software_version'],'background_units':config['background_units'],'explained_units':config['explain_units'],'max_evals':config['max_evals'],'maximum_additivity_error':float(error.max()),'additivity_tolerance':config['additivity_tolerance'],'additivity_pass':bool((error<=config['additivity_tolerance']).all()),'feature_axis':features,'interpretation':'Approximate marginal feature attribution relative to the declared training background and model output; not causal mechanism or proof of feature independence. Identity link retains the declared prediction scale; decision_function is not automatically log-odds.'}
    write(out/(name+'_shap_diagnostics.json'),diagnostic)
    if not diagnostic['additivity_pass']:raise ValueError('SHAP additivity failed on declared model-output scale; preserve outputs and inspect, do not relabel scale')
    return [(out/(name+'_shap.npz'),'shap_values'),(out/(name+'_shap_summary.tsv'),'shap_summary'),(out/(name+'_shap_identity.tsv'),'shap_identity'),(out/(name+'_shap_diagnostics.json'),'shap_diagnostics')]
