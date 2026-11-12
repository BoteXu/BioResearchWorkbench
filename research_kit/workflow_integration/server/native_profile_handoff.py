"""Receipt-bound actual gene-profile handoff, preserving scope and biological units."""
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad
    from scipy import sparse
    receipt=read(inputs['producer_receipt']);request=read(inputs['producer_request']);producer=request['backend'];parameters=request['parameters']
    allowed={'scgen_predict':'predicted_expression','scvidr_predict':'predicted_expression','biolord_attributes':'predicted_expression','causcell_counterfactual_fit':'predicted_expression','seurat_to_anndata':'processed_object'}
    if producer not in allowed or receipt.get('state')!='COMPLETED' or receipt.get('exit_code')!=0 or receipt.get('request_sha256')!=sha(inputs['producer_request']) or receipt.get('source_sha256')!=request.get('source_sha256'):raise ValueError('Actual completed native producer/request/source binding required; no guessed interface or historical receipt')
    matches=[row for row in receipt.get('outputs',[]) if row.get('role')==allowed[producer] and row.get('sha256')==sha(inputs['object'])]
    if len(matches)!=1:raise ValueError('Actual selected expression object is not uniquely bound to the expected producer output role')
    predicted=producer!='seurat_to_anndata'
    if p['data_kind']!=('model_decoded_expression' if predicted else 'observed_log_expression') or parameters.get('unit_key') not in {None,p['unit_key']}:raise ValueError('Actual producer expression kind and independent-unit semantics differ')
    a=ad.read_h5ad(inputs['object']);obs=a.obs.copy()
    if not a.obs_names.is_unique or not a.var_names.is_unique or a.n_obs>p['maximum_cells'] or p['unit_key'] not in obs or obs[p['unit_key']].isna().any() or not obs[p['unit_key']].map(lambda x:isinstance(x,str) and bool(x)).all():raise ValueError('Actual unique source cell/gene and literal independent-unit identities required')
    required_scenarios=[]
    if producer in {'scgen_predict','scvidr_predict'}:
        if 'model_target_condition' in obs:raise ValueError('Reserved target field already exists; do not silently overwrite it')
        obs['model_target_condition']=parameters['treatment'];required_scenarios=['model_target_condition']
    elif producer=='biolord_attributes':required_scenarios=parameters['prediction_attributes']
    elif producer=='causcell_counterfactual_fit':required_scenarios=['result_scope']+['model_concept_label::'+key for key in parameters['concepts']]
    if not set(required_scenarios)<=set(p['scenario_columns']):raise ValueError('Handoff would collapse distinct actual model target conditions/concept interventions')
    group=[p['unit_key']]+p['scenario_columns']
    if not set(group)<=set(obs) or obs[group].isna().any().any():raise ValueError('Actual complete source grouping/condition fields required')
    if p['aggregation_scope']=='within_unit_and_celltype' and (p['celltype_key'] not in p['scenario_columns'] or parameters.get('celltype_key') not in {None,p['celltype_key']}):raise ValueError('Preserve the actual producer cell-type strata; no implicit population mixing')
    for key,values in p['selected_scenarios'].items():
        if key not in p['scenario_columns'] or not values or not set(values)<=set(obs[key]):raise ValueError('Only explicit actual scenario values may be selected')
    keep=np.ones(a.n_obs,dtype=bool)
    for key,values in p['selected_scenarios'].items():keep&=obs[key].isin(values).to_numpy()
    selection=obs[group].copy();selection['selected_for_handoff']=keep;selection.to_csv(out/'source_selection.tsv',sep='\t')
    x=a.X;v=x.data if sparse.issparse(x) else np.asarray(x)
    if not np.isfinite(v).all():raise ValueError('Actual expression channel contains nonfinite values; no imputation or zero substitution')
    rows=[];matrices=[];metadata=[];membership=[]
    filtered=obs.loc[keep]
    for key,indices in filtered.groupby(group,sort=False,observed=True,dropna=False).indices.items():
        if not isinstance(key,tuple):key=(key,)
        cells=filtered.index[indices];index=a.obs_names.get_indexer(cells);record='profile_'+str(len(rows)+1);eligible=len(cells)>=p['minimum_cells_per_profile'];row={'profile_id':record,**dict(zip(group,key)),'n_source_cells':len(cells),'state':'ELIGIBLE' if eligible else 'HOLD_INSUFFICIENT_CELLS','data_kind':p['data_kind'],'source_producer':producer};rows.append(row)
        membership.extend({'profile_id':record,'source_cell_id':cell,'used_in_profile':eligible} for cell in cells)
        if eligible:
            matrices.append(np.asarray(x[index].mean(axis=0)).ravel());metadata.append(row)
    if not matrices:raise ValueError('No actual independent-unit profile has prespecified support; absence remains HOLD, never fabricated zero')
    meta=pd.DataFrame(metadata).set_index('profile_id');profiles=pd.DataFrame(np.stack(matrices),index=meta.index,columns=a.var_names);profiles.to_csv(out/'unit_profiles.tsv',sep='\t');meta.to_csv(out/'unit_profile_metadata.tsv',sep='\t');pd.DataFrame(rows).to_csv(out/'profile_eligibility.tsv',sep='\t',index=False);pd.DataFrame(membership).to_csv(out/'profile_membership.tsv',sep='\t',index=False)
    validation_scope={'scgen_predict':parameters.get('holdout_axis'),'scvidr_predict':parameters.get('holdout_scope'),'biolord_attributes':parameters.get('validation_scope'),'causcell_counterfactual_fit':parameters.get('validation_scope'),'seurat_to_anndata':'observed_expression_format_exchange'}[producer]
    write(out/'handoff_lineage.private.json',{'producer_backend':producer,'producer_request_sha256':sha(inputs['producer_request']),'producer_receipt_sha256':sha(inputs['producer_receipt']),'object_sha256':sha(inputs['object']),'validation_scope':validation_scope,'aggregation':'arithmetic mean of the unchanged actual X channel within literal independent unit and all selected scenario fields; no new normalization','aggregation_scope':p['aggregation_scope'],'selected_scenarios':p['selected_scenarios'],'data_kind':p['data_kind'],'feature_axis':list(a.var_names),'unit_key':p['unit_key'],'scenario_columns':p['scenario_columns'],'normalization_not_changed':True,'private_only':True})
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_profiles':len(meta),'n_hold_profiles':sum(row['state']!='ELIGIBLE' for row in rows),'source_receipt_bound':True,'data_kind':p['data_kind'],'producer_validation_scope':validation_scope,'scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Actual receipt-bound independent-unit mean profiles and explicit source-cell memberships for plotting/comparison/Systema input preparation. Model decoded expression stays distinct from observed data; averaging creates no new replicate and cannot upgrade the producer validation scope. Counts, velocity, embeddings, CellOT generic feature space and latent states are not accepted as gene-expression substitutes.'});write(out/'versions.json',p['software_versions'])
    return [(out/'unit_profiles.tsv','unit_expression_profiles'),(out/'unit_profile_metadata.tsv','profile_metadata'),(out/'profile_eligibility.tsv','profile_eligibility'),(out/'profile_membership.tsv','profile_membership'),(out/'source_selection.tsv','source_selection'),(out/'handoff_lineage.private.json','crossflow_lineage'),(out/'diagnostics.json','diagnostics'),(out/'versions.json','backend_versions')]
