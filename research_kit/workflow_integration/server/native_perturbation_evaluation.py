"""Systema evaluation with exact native centroid metric and explicit Pearson compatibility repair."""
from pathlib import Path
import importlib.util
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    if mode!='systema_evaluate':raise ValueError('Unknown fixed perturbation evaluation route')
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd
    from scipy.stats import pearsonr
    folder=Path(p['evaluation_directory']);source=folder/'centroid_accuracy.py'
    if not folder.is_absolute() or not source.is_file() or sha(source)!='dd82add60a9bcaf12d2705c58659e3393bff222d30dc0db3902dc9b0edc9e987':raise ValueError('Existing exact reviewed author Systema centroid implementation required; no implicit source download or arbitrary module import')
    spec=importlib.util.spec_from_file_location('_reviewed_systema_centroid',source);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    def matrix(role):
        # Read identifiers as literal strings before numeric conversion. Inspect
        # raw header first to prevent pandas duplicate-header name mangling.
        import csv
        with inputs[role].open(encoding='utf-8-sig',newline='') as f:header=next(csv.reader(f,delimiter='\t'))
        if len(header)<4 or len(set(header))!=len(header) or any(not h for h in header[1:]):raise ValueError('Unique literal profile feature columns required')
        raw=pd.read_csv(inputs[role],sep='\t',dtype=str,keep_default_na=False);raw.columns=header;index=raw.iloc[:,0].tolist()
        if any(not v for v in index) or len(set(index))!=len(index):raise ValueError('Unique nonempty literal profile IDs required')
        frame=raw.iloc[:,1:].apply(pd.to_numeric,errors='raise');frame.index=index
        if not np.isfinite(frame.to_numpy()).all():raise ValueError('Actual finite measured/predicted full profiles required; no missing-as-zero')
        return frame
    train=matrix('training_profiles');truth=matrix('true_profiles');prediction=matrix('predicted_profiles')
    if not train.columns.equals(truth.columns) or not train.columns.equals(prediction.columns):raise ValueError('Exact full ordered feature identity required across train, truth and predictions')
    def meta(role,index,predicted=False):
        import csv
        with inputs[role].open(encoding='utf-8-sig',newline='') as f:header=next(csv.reader(f,delimiter='\t'))
        if len(set(header))!=len(header):raise ValueError('Duplicate source metadata columns')
        frame=pd.read_csv(inputs[role],sep='\t',dtype=str,keep_default_na=False);frame.columns=header;frame.index=frame.iloc[:,0].tolist();frame=frame.iloc[:,1:]
        required=[p['unit_key'],p['condition_key']]+(['method'] if predicted else [])
        if not frame.index.is_unique or set(frame.index)!=set(index) or not set(required)<=set(frame) or frame[required].eq('').any().any():raise ValueError('Exact complete source profile metadata required')
        frame=frame.loc[index]
        if frame.duplicated([p['unit_key'],p['condition_key']]+(['method'] if predicted else [])).any():raise ValueError('One prespecified profile per independent unit/condition/method required; aggregate technical repeats upstream')
        return frame
    tm=meta('training_metadata',train.index);ym=meta('truth_metadata',truth.index);pm=meta('prediction_metadata',prediction.index,True)
    if set(train.index)&set(truth.index):raise ValueError('Training and test source profile identities overlap')
    condition=p['condition_key'];unit=p['unit_key'];test_conditions=set(ym[condition])
    if p['holdout_axis']=='unit' and set(tm[unit])&set(ym[unit]):raise ValueError('Heldout independent-unit evaluation leaks training units')
    if p['holdout_axis']=='perturbation' and (set(tm[condition])-{p['control']})&test_conditions:raise ValueError('Claimed unseen perturbation is in training')
    if p['control'] in test_conditions or len(test_conditions)<2:raise ValueError('At least two genuinely heldout perturbation centroids required for rank evaluation')
    expected=set(zip(ym[unit],ym[condition]));methods=list(dict.fromkeys(pm.method))
    for method in methods:
        rows=pm[pm.method==method]
        if set(zip(rows[unit],rows[condition]))!=expected:raise ValueError('Every compared method must cover exactly the same observed unit/condition scenarios; no missing-method cherry picking')
    # Unit-level profiles were prespecified upstream. Conditions are averaged with
    # equal independent-unit weights; no replicate/cell-count weighting invented.
    reference_conditions=tm.loc[tm[condition]!=p['control'],condition].unique()
    if not len(reference_conditions):raise ValueError('Actual perturbed training profiles required for the custom reference')
    train_centroids=train.groupby(tm[condition],sort=False).mean();reference=train_centroids.loc[reference_conditions].mean(0).to_numpy()
    true_centroids=truth.groupby(ym[condition],sort=False).mean();parts=[]
    for method in methods:
        idx=pm.index[pm.method==method];frame=prediction.loc[idx].groupby(pm.loc[idx,condition],sort=False).mean();frame.index=pd.MultiIndex.from_arrays([frame.index,[method]*len(frame)],names=['condition','method']);parts.append(frame)
    predicted_centroids=pd.concat(parts);predicted_centroids.index.names=['condition','method']
    scores=native.calculate_centroid_accuracies(predicted_centroids,true_centroids)
    if set(scores.index)!=test_conditions or set(scores.columns)!=set(methods) or not np.isfinite(scores.to_numpy()).all() or (scores.to_numpy()<0).any() or (scores.to_numpy()>1).any():raise ValueError('Native rank centroid-accuracy dimensions/numerical contract failed')
    panel=read(inputs['evaluation_gene_panel'])
    if not isinstance(panel,dict) or panel.get('selection_scope')!='training_or_external_only' or not panel.get('source_sha256') or not isinstance(panel.get('gene_ids'),list) or len(set(panel['gene_ids']))!=len(panel['gene_ids']) or len(panel['gene_ids'])<3 or not set(panel['gene_ids'])<=set(train.columns):raise ValueError('Explicit independently selected evaluation gene panel and source required; no heldout-outcome feature selection for model choice')
    selection=read(inputs['panel_selection_receipt'])
    if panel['source_sha256'] not in {r.get('sha256') for r in selection.get('inputs',[])} or selection.get('state')!='COMPLETED' or not any(r.get('sha256')==sha(inputs['evaluation_gene_panel']) for r in selection.get('outputs',[])):raise ValueError('Actual panel selection producer receipt does not bind the reviewed source and panel')
    if any(r.get('sha256')==sha(inputs['true_profiles']) for r in selection.get('inputs',[])):raise ValueError('Heldout truth used for the declared training/external evaluation panel')
    indices=train.columns.get_indexer(panel['gene_ids']);correlations=[]
    def correlation(x,y):
        if np.var(x)==0 or np.var(y)==0:return None
        value=float(pearsonr(x,y)[0])
        return value if np.isfinite(value) else None
    for (target,method),row in predicted_centroids.iterrows():
        observed=true_centroids.loc[target].to_numpy()-reference;predicted=row.to_numpy()-reference
        correlations.append({'condition':target,'method':method,'corr_all_allpert':correlation(observed,predicted),'corr_panel_allpert':correlation(observed[indices],predicted[indices]),'panel_genes':len(indices),'scope':'Systema custom perturbed-training reference; explicit panel compatibility repair'})
    outputs=[]
    def emit(frame,name,role,index=True):
        fn=out/(name+'.tsv');frame.to_csv(fn,sep='\t',index=index,na_rep='NA');outputs.append((fn,role))
    emit(scores,'systema_centroid_rank_accuracy','centroid_accuracy');emit(pd.DataFrame(correlations),'systema_pearson_delta','perturbation_metrics',False);emit(true_centroids,'systema_observed_centroids','observed_centroids');emit(predicted_centroids,'systema_predicted_centroids','predicted_centroids');emit(pd.DataFrame({'feature_id':train.columns,'reference':reference}),'systema_training_reference','reference_profile',False)
    diagnostic={'mode':mode,'software_versions':p['software_versions'],'n_methods':len(methods),'n_test_conditions':len(test_conditions),'n_test_units':ym[unit].nunique(),'holdout_axis':p['holdout_axis'],'panel_size':len(indices),'native_centroid_source_sha256':sha(source),'native_centroid_definition':'Fraction of alternative true centroids farther from a prediction than its correct centroid, denominator n_conditions-1, strict greater-than tie rule; not binary nearest-centroid classification','pearson_compatibility_repair':'Reviewed author helper d54be9ecbf4c885ee7752bdc7e1d183b17504cdc048bbb573295bd36f6a1ecce uses an undefined top20_de_idxs global and differs from its README signature. Apply the same explicit Pearson delta formula with an actual source-bound panel; do not mislabel a non-20 panel as PearsonDelta20','aggregation_scope':'One source profile per independent unit/condition; equal-unit then equal-condition training reference. Distinct from a cell-weighted preprocessing choice','undefined_correlations':sum(r['corr_all_allpert'] is None or r['corr_panel_allpert'] is None for r in correlations),'scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Heldout benchmark metrics conditional on the declared source profiles, panel and training reference; not validation of experimental target engagement, causal mechanism or clinical utility'}
    write(out/'native_diagnostics.json',diagnostic);outputs.append((out/'native_diagnostics.json','diagnostics'));write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'));return outputs
