"""Native PRESCIENT steps with exact selected starting identities and time scale."""
import inspect,re
from types import SimpleNamespace
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    from native_genetics import reference_manifest
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad,torch
    from prescient.train.model import AutoGenerator
    if sha(inspect.getsourcefile(AutoGenerator))!='ec37d1b3bacfce6c2deb58b07bf5d4f6fb80e2e3e101452f7e15301761e39b20':raise ValueError('Installed PRESCIENT model differs from the exact reviewed native source')
    manifest,members=reference_manifest(inputs['model_manifest']);config=read(inputs['model_config']);identity=read(inputs['representation_receipt']);a=ad.read_h5ad(inputs['object'])
    if manifest.get('model_config_sha256')!=sha(inputs['model_config']) or manifest.get('trusted_source_reviewed') is not True or not manifest.get('source_url') or not manifest.get('license'):raise ValueError('Existing exact trusted native model/config and provenance required')
    checkpoint=members.get(manifest.get('model_file'))
    if checkpoint is None or identity.get('output_sha256')!=sha(inputs['object']) or not re.fullmatch('[a-f0-9]{64}',str(manifest.get('representation_contract_sha256',''))) or identity.get('representation_contract_sha256')!=manifest.get('representation_contract_sha256') or not identity.get('preprocessing_method'):raise ValueError('Actual input representation must match the checkpoint training coordinate/scaling contract')
    if not a.obs_names.is_unique or not a.var_names.is_unique or p['unit_key'] not in a.obs or a.obs[p['unit_key']].isna().any():raise ValueError('Exact actual source cells/features/biological units required')
    ids=p['initial_cells'];positions=a.obs_names.get_indexer(ids)
    if (positions<0).any() or len(positions)!=len(set(ids)):raise ValueError('Literal unique observed initial cells required')
    rep=np.asarray(a.obsm[p['representation_key']])
    if rep.ndim!=2 or rep.shape!=(a.n_obs,config['x_dim']) or not np.isfinite(rep).all() or config['activation'] not in {'relu','softplus','none'}:raise ValueError('Actual finite checkpoint-aligned coordinates and supported native potential architecture required; no UMAP metric substitution')
    if p['dt']!=config['train_dt'] or p['noise_sd']!=config['train_sd'] or p['model_time_unit']!=manifest.get('model_time_unit'):raise ValueError('Declared simulation step/noise/time units differ from the trained model; no silent recalibration')
    if p['n_simulations']*len(ids)*(p['n_steps']+1)*config['x_dim']>p['maximum_trajectory_entries']:raise ValueError('Native trajectory exceeds explicit reviewed server output budget')
    device=torch.device('cuda' if p['accelerator']=='gpu' else 'cpu');torch.manual_seed(p['seed']);np.random.seed(p['seed']);model=AutoGenerator(SimpleNamespace(**config)).to(device);state=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if p['state_dictionary_key'] is not None:state=state[p['state_dictionary_key']]
    if not isinstance(state,dict) or not state or any(not isinstance(k,str) or not torch.is_tensor(v) for k,v in state.items()):raise ValueError('Actual compatible safe tensor state dictionary required, never an arbitrary pickled model/config')
    model.load_state_dict(state,strict=True);model.eval();all_sims=[]
    for index in range(p['n_simulations']):
        x=torch.as_tensor(rep[positions],dtype=torch.float32,device=device);trajectory=[x.detach().cpu().numpy().copy()]
        for step in range(p['n_steps']):
            noise=torch.randn(x.shape,device=device)*p['noise_sd'];x=model._step(x,dt=p['dt'],z=noise).detach()
            if not torch.isfinite(x).all():raise ValueError('Native trajectory diverged/nonfinite; preserve partial logs, do not extrapolate a trajectory')
            trajectory.append(x.cpu().numpy().copy())
        all_sims.append(np.stack(trajectory))
    values=np.stack(all_sims);times=np.arange(p['n_steps']+1)*p['dt'];np.savez_compressed(out/'prescient_trajectories.npz',coordinates=values,model_time=times,source_cell_ids=np.asarray(ids,dtype=str));a.obs.loc[ids,[p['unit_key']]].to_csv(out/'prescient_initial_identity.tsv',sep='\t');pd.DataFrame({'step':np.arange(len(times)),'model_time':times,'model_time_unit':p['model_time_unit']}).to_csv(out/'prescient_time_axis.tsv',sep='\t',index=False)
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_simulations':p['n_simulations'],'n_steps':p['n_steps'],'n_initial_cells':len(ids),'initial_identity_preserved':True,'time_calibration_preserved':True,'scientific_acceptance':'NOT_ESTABLISHED','method_scope':'Native AutoGenerator._step and native training noise/dt, with explicitly chosen initial cells instead of opaque random initial sampling. No change to native drift sign or refitting.','interpretation':'Conditional stochastic model trajectories in the checkpoint training representation/time scale. Replicas are computational draws from the same source cells, not biological replicates or measured cell lineage. Native learned potential is not thermodynamic free energy; no gene intervention, growth reweighting, fate proof or new-donor validation asserted.'});write(out/'versions.json',p['software_versions'])
    return [(out/'prescient_trajectories.npz','model_trajectories'),(out/'prescient_initial_identity.tsv','trajectory_identity'),(out/'prescient_time_axis.tsv','trajectory_time'),(out/'diagnostics.json','diagnostics'),(out/'versions.json','backend_versions')]
