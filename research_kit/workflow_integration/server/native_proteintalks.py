"""Native original ProteinTalks ppODE, checkpoint-aligned proteome/drug channels."""
import importlib.util
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    from native_genetics import reference_manifest
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,torch
    source,members=reference_manifest(inputs['source_manifest']);modelmeta,weights=reference_manifest(inputs['model_manifest']);semantics=read(inputs['channel_receipt']);outputs=[]
    sourcefile=members.get(source.get('model_source'))
    if sourcefile is None or sha(sourcefile)!='aba29c4fb4ce95ff7c387b8d889b8c95222eed9951f7d309fb3cc1457acc6063':raise ValueError('Actual ProteinTalks ppODE source differs from the exact author code reviewed')
    checkpoint=weights.get(modelmeta.get('model_file'));configuration=modelmeta.get('model_configuration',{})
    if checkpoint is None or not modelmeta.get('source_url') or not modelmeta.get('license') or modelmeta.get('trusted_source_reviewed') is not True or modelmeta.get('phenotype_definition')!=p['phenotype_definition'] or modelmeta.get('expression_scale')!=p['expression_scale']:raise ValueError('Existing trusted native checkpoint, exact preprocessing scale and binary phenotype label definition required')
    if modelmeta.get('trained_physical_timepoints_hours')!=[0,6,24,48] or modelmeta.get('internal_time_ticks')!=[0,1,2,3]:raise ValueError('This native checkpoint uses fixed equal internal ODE ticks mapped to training observations at 0/6/24/48 hours; no silent physical-time reintegration')
    def table(role):
        if semantics.get('inputs',{}).get(role)!=sha(inputs[role]) or not semantics.get('channel_definitions',{}).get(role):raise ValueError('Exact actual input channel/preprocessing provenance missing: '+role)
        z=pd.read_csv(inputs[role],sep='\t',index_col=0,dtype=str,keep_default_na=False)
        if not z.index.is_unique or not z.columns.is_unique or not np.isfinite(z.to_numpy(float)).all():raise ValueError('Finite actual unique sample/feature channels required')
        return z.astype(float)
    baseline=table('baseline_profiles');pert=table('perturbation_descriptors');fa=table('drug_a_features');fb=table('drug_b_features');meta=pd.read_csv(inputs['case_metadata'],sep='\t',index_col=0,dtype=str,keep_default_na=False)
    if semantics.get('inputs',{}).get('case_metadata')!=sha(inputs['case_metadata']):raise ValueError('Exact case/drug/baseline identity receipt must be bound with the numerical channels')
    if not meta.index.is_unique or not {p['unit_key'],'baseline_sample_id','drug_a_id','drug_b_id'}<=set(meta) or (meta=='').any().any() or len(meta)>p['maximum_cases']:raise ValueError('Bounded exact case/actual baseline/biological-unit/drug identities required')
    if not all(z.index.equals(meta.index) for z in [pert,fa,fb]) or not set(meta.baseline_sample_id)<=set(baseline.index):raise ValueError('Actual case/source baseline axes differ; do not align by row position or infer labels')
    if meta.groupby('baseline_sample_id')[p['unit_key']].nunique().max()!=1:raise ValueError('An actual baseline sample cannot be assigned to different biological units across cases')
    bydrug={}
    for frame,key in [(fa,'drug_a_id'),(fb,'drug_b_id')]:
        for caseid,row in frame.iterrows():
            drug=meta.loc[caseid,key];v=row.to_numpy()
            if drug in bydrug and not np.array_equal(bydrug[drug],v):raise ValueError('Same literal drug has inconsistent fixed molecular descriptor channels')
            bydrug[drug]=v
    proteins=modelmeta.get('protein_order');features=modelmeta.get('drug_feature_order')
    if proteins!=list(baseline.columns) or proteins!=list(pert.columns) or features!=list(fa.columns) or features!=list(fb.columns):raise ValueError('Literal protein and molecular descriptor order must equal the trained checkpoint axes')
    if modelmeta.get('drug_feature_definition_sha256')!=semantics.get('drug_feature_definition_sha256') or modelmeta.get('protein_normalization_contract_sha256')!=semantics.get('protein_normalization_contract_sha256'):raise ValueError('Actual feature definitions/scaling differ from model training, not interchangeable descriptor vectors')
    if any(not isinstance(modelmeta.get(key),str) or len(modelmeta[key])!=64 for key in ['drug_feature_definition_sha256','protein_normalization_contract_sha256']):raise ValueError('Actual feature/scaling definitions must be hash-bound')
    spec=importlib.util.spec_from_file_location('private_exact_proteintalks',sourcefile);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native);torch.manual_seed(p['seed']);device=torch.device('cuda' if p['accelerator']=='gpu' else 'cpu')
    model=native.ppODE(node_feats=configuration['node_feats'],pert_feats=configuration['pert_feats'],hidden_feats=configuration['hidden_feats'],out_feats=1,pro_feats=len(proteins),drug_feature_feats=len(features),dropout=configuration['dropout']);model.set_time_stamp_predict_drug('6_24_48');state=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if p['state_dictionary_key'] is not None:state=state[p['state_dictionary_key']]
    # Author DDP prefix applies only to model parameter names, never gene IDs.
    cleaned={k[7:] if k.startswith('module.') else k:v for k,v in state.items()}
    if len(cleaned)!=len(state):raise ValueError('Ambiguous distributed/native state dictionary keys')
    model.load_state_dict(cleaned,strict=True);model=model.to(device).eval();predictions=[];phenotypes=[]
    for start in range(0,len(meta),p['batch_size']):
        case=meta.iloc[start:start+p['batch_size']];ids=case.index
        arrays=[baseline.loc[case.baseline_sample_id].to_numpy(),pert.loc[ids].to_numpy(),fa.loc[ids].to_numpy(),fb.loc[ids].to_numpy()];tensors=[torch.as_tensor(z,dtype=torch.float32,device=device).unsqueeze(-1) for z in arrays]
        with torch.no_grad():pred,prob,_=model(*tensors,time_stamp_predict_drug='6_24_48')
        pred=pred.detach().cpu().numpy();prob=prob.detach().cpu().numpy()
        if pred.shape!=(len(ids),3,len(proteins),1) or prob.shape!=(len(ids),) or not np.isfinite(pred).all() or not np.isfinite(prob).all() or ((prob<0)|(prob>1)).any():raise ValueError('Native proteome/phenotype output identity/dimension/numerical QC failed')
        predictions.append(pred[...,0]);phenotypes.extend(prob.tolist())
    values=np.concatenate(predictions);np.savez_compressed(out/'proteintalks_predictions.npz',protein_expression=values,case_ids=meta.index.to_numpy(str),protein_ids=np.asarray(proteins,dtype=str),physical_timepoint_labels_hours=np.asarray([6,24,48]),native_internal_ticks=np.asarray([1,2,3]));meta['native_binary_phenotype_probability']=phenotypes;meta['phenotype_definition']=p['phenotype_definition'];meta.to_csv(out/'proteintalks_case_predictions.tsv',sep='\t')
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_cases':len(meta),'n_proteins':len(proteins),'literal_checkpoint_channels_preserved':True,'phenotype_definition':p['phenotype_definition'],'scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Native original ProteinTalks ppODE point prediction with exact protein/drug/preprocessing channels. Original ODE ticks are 0/1/2/3 with trained observation labels 0/6/24/48 hours; not a newly calibrated continuous physical-hour model. Phenotype probability refers to the exact checkpoint binary training label, not a continuous synergy score, measured efficacy or clinical response. No SWAG uncertainty or independent validation claimed.'});write(out/'versions.json',p['software_versions'])
    return [(out/'proteintalks_predictions.npz','proteome_predictions'),(out/'proteintalks_case_predictions.tsv','phenotype_predictions'),(out/'diagnostics.json','diagnostics'),(out/'versions.json','backend_versions')]
