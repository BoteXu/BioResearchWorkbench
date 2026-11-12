"""Exact-source native SpatialGlue, one matched measured section at a time."""
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad,torch,inspect,random
    from SpatialGlue.SpatialGlue_pyG import Train_SpatialGlue
    from SpatialGlue.preprocess import construct_neighbor_graph
    for fn,digest in [(Train_SpatialGlue,'ecfffa9d6698a11a982149a354445a2746b20903e6294ba4146d1ef156cbc472'),(construct_neighbor_graph,'f75ebdcda7c7989970fa5100b9a8ddef425048e2de52c47a77fb50f94a9422b7')]:
        if sha(inspect.getsourcefile(fn))!=digest:raise ValueError('Actual installed SpatialGlue code differs from exact reviewed native source')
    a=ad.read_h5ad(inputs['modality1']);b=ad.read_h5ad(inputs['modality2']);receipt=read(inputs['feature_preprocessing_receipt']);metadata=[p['unit_key'],p['section_key']]
    if not a.obs_names.is_unique or not b.obs_names.is_unique or not a.var_names.is_unique or not b.var_names.is_unique or not a.obs_names.equals(b.obs_names) or a.n_obs<max(p['spatial_neighbors']+1,21) or a.n_obs**2>p['maximum_dense_graph_entries']:raise ValueError('Matched measured spot axes and reviewed native dense-graph budget/support required')
    for key in metadata:
        if key not in a.obs or key not in b.obs or not a.obs[key].equals(b.obs[key]) or a.obs[key].isna().any() or a.obs[key].nunique()!=1:raise ValueError('Fit one actual section/independent unit with the same measured metadata; no cross-section edges')
    for role,obj in [('modality1',a),('modality2',b)]:
        if receipt.get('outputs',{}).get(role)!=sha(inputs[role]) or not receipt.get('method') or not receipt.get('input_channels',{}).get(role):raise ValueError('Actual preprocessing/feature-channel provenance must bind each exact native input object')
        feat=obj.obsm.get('feat');coords=obj.obsm.get('spatial')
        if feat is None or feat.ndim!=2 or feat.shape[0]!=obj.n_obs or not np.isfinite(feat).all() or coords is None or coords.shape!=(obj.n_obs,2) or not np.isfinite(coords).all():raise ValueError('Actual reviewed preprocessed feature representation and finite spatial coordinates required')
    if not np.array_equal(a.obsm['spatial'],b.obsm['spatial']):raise ValueError('Paired modalities must use exactly the same measured coordinate frame; use registration upstream, never overwrite coordinates')
    random.seed(p['seed']);np.random.seed(p['seed']);torch.manual_seed(p['seed']);device=torch.device('cuda' if p['accelerator']=='gpu' else 'cpu')
    data=construct_neighbor_graph(a,b,datatype=p['datatype'],n_neighbors=p['spatial_neighbors']);trainer=Train_SpatialGlue(data,datatype=p['datatype'],device=device,random_seed=p['seed'],learning_rate=p['learning_rate'],weight_decay=p['weight_decay'],epochs=p['max_epochs'],dim_output=p['n_latent'],weight_factors=p['weight_factors'])
    if trainer.epochs!=p['max_epochs'] or list(trainer.weight_factors)!=p['weight_factors']:raise ValueError('Native datatype overrides requested epochs/weights; task must declare the actual native settings')
    result=trainer.train();outputs=[]
    for key,value in result.items():
        arr=np.asarray(value)
        if arr.shape[0]!=a.n_obs or arr.ndim!=2 or not np.isfinite(arr).all():raise ValueError('Native embedding/attention shape, spot identity or finite-value QC failed')
        if key.startswith('alpha') and ((arr<0).any() or not np.allclose(arr.sum(1),1,atol=p['attention_sum_tolerance'])):raise ValueError('Native attention weights do not form the expected per-spot simplex')
        a.obsm[key]=arr;fn=out/(key+'.tsv');pd.DataFrame(arr,index=a.obs_names).to_csv(fn,sep='\t');outputs.append((fn,'integrated_representation' if key=='SpatialGlue' else 'modality_attention' if key.startswith('alpha') else 'modality_representation'))
    if result['SpatialGlue'].shape[1]!=p['n_latent']:raise ValueError('Native combined latent dimension differs')
    fn=out/'spatialglue_result.h5ad';a.write_h5ad(fn);outputs.append((fn,'processed_object'));fn=out/'spatialglue_state.pt';torch.save(trainer.model.state_dict(),fn);outputs.append((fn,'model_checkpoint'))
    losses={key:float(getattr(trainer,key).detach().cpu()) for key in ['loss_recon_omics1','loss_recon_omics2','loss_corr_omics1','loss_corr_omics2']}
    if not all(np.isfinite(x) for x in losses.values()):raise ValueError('Native terminal training losses are nonfinite')
    a.obs[metadata].to_csv(out/'spot_identity.tsv',sep='\t');outputs.append((out/'spot_identity.tsv','spatial_identity'));write(out/'terminal_losses.json',losses);outputs.append((out/'terminal_losses.json','training_diagnostics'))
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_spots':a.n_obs,'actual_epochs':trainer.epochs,'actual_weight_factors':trainer.weight_factors,'matched_identity_and_coordinates':True,'scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Native two-modality one-section SpatialGlue graph embedding/attention. Preprocessing is externally reviewed and unchanged; attention is a model weight, not measured biological modality contribution. Terminal losses are not a complete training history or generalization validation; no automatic domain/cell-type labels.'});outputs.append((out/'diagnostics.json','diagnostics'));write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
