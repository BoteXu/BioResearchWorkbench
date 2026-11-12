"""Actual specialist calls, imported only after a private allocated-server guard."""
from pathlib import Path
import sys,os,json,csv,math,random,socket,importlib.metadata,pickle
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import read,write,sha,relative

def offline():
    for k,v in {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_DATASETS_OFFLINE':'1','WANDB_MODE':'disabled','HF_HUB_DISABLE_TELEMETRY':'1'}.items():os.environ[k]=v
    original=socket.socket.connect;original_ex=socket.socket.connect_ex;original_send=socket.socket.sendto
    def connect(s,address):
        if s.family in (socket.AF_INET,socket.AF_INET6):raise RuntimeError('This worker only reads selected server assets; outbound network is disabled')
        return original(s,address)
    def connect_ex(s,address):
        if s.family in (socket.AF_INET,socket.AF_INET6):raise RuntimeError('Outbound network disabled')
        return original_ex(s,address)
    def sendto(s,*args):
        if s.family in (socket.AF_INET,socket.AF_INET6):raise RuntimeError('Outbound datagrams disabled')
        return original_send(s,*args)
    socket.socket.connect=connect;socket.socket.connect_ex=connect_ex;socket.socket.sendto=sendto

def version(distribution,p):
    actual=importlib.metadata.version(distribution)
    if actual!=p['expected_package_version']:raise ValueError('Installed package differs from the reviewed exact version: '+distribution)
    return actual

def assets(job,required):
    I=job['inputs'];bundle=read(I['asset_manifest']);root=Path(job['project_root']);files={}
    if bundle.get('public_upload') is not False or bundle.get('trust_decision')!='REVIEWED_LOCAL_ASSET' or not bundle.get('reviewer') or not bundle.get('origin') or not bundle.get('license_review'):raise ValueError('Reviewed source/license/trust provenance is required before loading model/pickle assets')
    for r in bundle['files']:
        path=relative(root,r['path'])
        if r['path'] in files or sha(path)!=r['sha256']:raise ValueError('Duplicate or changed model asset')
        files[r['path']]=path
    entries={}
    for name,entry in bundle['entries'].items():
        if isinstance(entry,str):
            if entry not in files:raise ValueError('Unlisted file asset')
            entries[name]=files[entry]
        else:
            path=relative(root,entry['directory'],directory=True);members={x.resolve() for x in path.rglob('*') if x.is_file()}
            listed={v.resolve() for v in files.values() if v.is_relative_to(path)}
            if not members or members!=listed:raise ValueError('Every model/dataset/cache file must be hash-listed; partial bundle inventories are refused')
            entries[name]=path
    if not set(required)<=set(entries):raise ValueError('Missing frozen asset role')
    return entries,bundle

def training(job,bundle):
    e=read(job['inputs']['model_training_evidence']);p=job['parameters']
    if e.get('state')!='COMPLETED_REVIEWED' or e.get('asset_manifest_sha256')!=sha(job['inputs']['asset_manifest']) or not e.get('source_receipt_sha256') or not e.get('training_units'):raise ValueError('Actual completed, reviewed, hash-bound model-training evidence required')
    source=read(job['inputs']['model_training_receipt'])
    if sha(job['inputs']['model_training_receipt'])!=e['source_receipt_sha256'] or source.get('state')!='COMPLETED' or source.get('exit_code')!=0:raise ValueError('Training receipt is missing, failed or changed')
    trained={r['sha256'] for r in source.get('outputs',[])}
    declared={r['sha256'] for r in bundle['files'] if r.get('is_model_parameter') is True}
    if not declared or not declared<=trained:raise ValueError('The actual checkpoint is not an output of this training receipt')
    entries=bundle['entries']
    if not isinstance(entries.get('training_unit_ledger'),str):raise ValueError('Actual training unit ledger must be part of the frozen asset bundle')
    ledger=relative(job['project_root'],entries['training_unit_ledger'])
    if sha(ledger) not in trained:raise ValueError('Training units are not an actual output of the training run')
    with ledger.open(encoding='utf-8-sig',newline='') as f:units=list(csv.DictReader(f,delimiter='\t'))
    from training_partitions import inspect_ledger
    job['_training_partition_audit']=inspect_ledger(units,e['training_units'],p['evaluation_units'],p['evaluation_scope'])
    training_units={r['unit_id'] for r in units if r['role']=='TRAINING'}
    if training_units!=set(e['training_units']):raise ValueError('Declared training donors differ from the actual model-training unit ledger')
    if p['evaluation_scope']=='heldout_donor' and set(p['evaluation_units'])&set(e['training_units']):raise ValueError('Evaluation donors were used for training')
    if e.get('species')!=job['context']['species'] or e.get('annotation_version')!=job['context']['annotation_version']:raise ValueError('Model species/annotation differs from selected study')
    return e

def dense(x):return x.toarray() if hasattr(x,'toarray') else x

def adata_qc(a,p):
    import numpy as np
    if not a.obs_names.is_unique or not a.var_names.is_unique or not {'unit_id','cell_type','qc_accepted'}<=set(a.obs):raise ValueError('Unique cell/gene axes and actual donor/cell-type/QC evidence required')
    if not a.obs['qc_accepted'].map(lambda v:v is True or str(v).lower() in ('true','1')).all():raise ValueError('Input contains cells without accepted source-assay QC')
    chosen=a.obs.unit_id.astype(str).isin(p['evaluation_units'])&(a.obs.cell_type.astype(str)==p['cell_type'])
    a=a[chosen].copy()
    if set(a.obs.unit_id.astype(str))!=set(p['evaluation_units']):raise ValueError('Requested evaluation donor/cell-type is missing')
    if min(a.obs.unit_id.astype(str).value_counts())<p['min_cells_per_unit']:raise ValueError('Insufficient donor/cell-type coverage')
    if not set(p['ko_genes'])<=set(a.var_names):raise ValueError('Selected KO gene is not covered by the frozen gene axis')
    if a.n_vars>p.get('max_genes',100000):raise ValueError('Selected frozen gene set exceeds reviewed compute scope')
    return a

def emit(job,out,tables,metrics,**details):
    mapping={}
    if '_training_partition_audit' in job:write(out/'training_partition_audit.private.json',job['_training_partition_audit'])
    if len(tables)!=len(job['required_roles']):raise ValueError('Internal result-role mismatch')
    for role,frame in zip(job['required_roles'],tables):
        name=role+'.tsv';frame.to_csv(out/name,sep='\t',index=False);mapping[role]=name
    write(out/'outputs.private.json',mapping);write(out/'diagnostics.private.json',{'fit_completed':True,'metrics':metrics,'measurement_state':'predicted','biological_KO_or_causal_effect_established':False,**details})

def genki(job,out):
    import anndata as ad,numpy as np,pandas as pd,torch
    from GenKI import GenKI
    from GenKI.utils import get_distance
    p=job['parameters'];version('GenKI',p)
    a=adata_qc(ad.read_h5ad(job['inputs']['adata']),p)
    if 'norm' not in a.layers or job['context']['scale']!='GenKI_reviewed_norm_layer':raise ValueError('Reviewed GenKI normalized layer is required; no implicit re-normalization or gene renaming')
    rows=[];coverage=[];diag=[];nullrows=[]
    for number,unit in enumerate(p['evaluation_units']):
        np.random.seed(p['seed'])
        x=a[a.obs.unit_id.astype(str)==unit].copy()
        raw=np.asarray(dense(x.layers['norm']))
        if not np.isfinite(raw).all() or (raw.var(axis=0)<=0).any():raise ValueError('GenKI input contains nonfinite/constant genes; filter and re-review frozen axes')
        directory=out/('donor_'+str(number));directory.mkdir()
        model=GenKI.from_adata(x,target_gene=p['ko_genes'],preprocess=False,obs_label='cell_type',grn_dir=str(directory/'GRN'),rebuild_grn=True,n_cpus=1,nComp=p['n_components'],cutoff=p['network_percentile'])
        model.fit(epochs=p['epochs'],lr=p['learning_rate'],beta=p['beta'],seed=p['seed'],out_channels=p['latent_dimensions'],log_dir=str(directory/'training'))
        wt=model.trainer if hasattr(model,'trainer') else model._trainer
        wt_data=model.wt_data;ko_data=model.ko_data
        mu,var=wt.get_latent_vars(wt_data);mu_ko,var_ko=wt.get_latent_vars(ko_data)
        dis=np.asarray(get_distance(mu_ko,var_ko,mu,var,by='KL'));null=np.asarray(wt.pmt(ko_data,n=p['resamples'],by='KL'))
        if dis.ndim!=1 or null.shape!=(p['resamples'],len(dis)) or not np.isfinite(dis).all() or not np.isfinite(null).all() or (dis < -1e-7).any():raise ValueError('Invalid GenKI latent-distance/native-bootstrap output')
        identities=list(wt_data.y)
        if len(identities)!=len(dis) or len(set(identities))!=len(dis) or set(identities)!=set(a.var_names):raise ValueError('GenKI changed the frozen gene identity axis')
        threshold=np.quantile(null,.95,axis=1);frequency=(null>=threshold[:,None]).mean(axis=0)
        rows.extend((unit,g,float(d),float(f)) for g,d,f in zip(identities,dis,frequency))
        coverage.append((unit,x.n_obs,x.n_vars))
        epoch,loss,auc,ap=model.metrics;diag.append((unit,int(epoch),float(loss),float(auc),float(ap)))
        for k in range(null.shape[0]):nullrows.append((unit,k,float(null[k].mean()),float(null[k].max())))
        torch.save(wt.model.state_dict(),directory/'model_state.pt')
    emit(job,out,[pd.DataFrame(rows,columns=['unit_id','feature_id','latent_KL','native_bootstrap_top5_frequency']),pd.DataFrame(coverage,columns=['unit_id','cells','genes']),pd.DataFrame(diag,columns=['unit_id','epochs','training_loss','graph_edge_AUC','graph_edge_AP']),pd.DataFrame(nullrows,columns=['unit_id','resample','mean_latent_KL','maximum_latent_KL'])],{'units':len(coverage),'gene_unit_denominator':len(rows)},interpretation='Native pmt resamples cells with replacement and internally resets numpy seed to 0; it is not a label-permutation null. Latent KL/bagging are not logFC, calibrated gene p-values or independent-donor validation; edge AUC is not KO-response accuracy')

def celloracle(job,out):
    import numpy as np,pandas as pd,celloracle as co
    p=job['parameters'];version('celloracle',p);bundle,b=assets(job,['oracle_model']);e=training(job,b)
    oracle=co.load_hdf5(str(bundle['oracle_model']),object_class_name='Oracle');a=oracle.adata
    chosen=adata_qc(a,p);ids=chosen.obs_names;indices=a.obs_names.get_indexer(ids)
    if not p['clip_to_training_range']:raise ValueError('Out-of-support extrapolation is disabled')
    baseline=np.asarray(dense(a.layers['imputed_count']))
    if not np.isfinite(baseline).all():raise ValueError('Invalid CellOracle baseline')
    oracle.simulate_shift(perturb_condition={g:0.0 for g in p['ko_genes']},n_propagation=p['n_propagation'],ignore_warning=False,clip_delta_X=True)
    simulated=np.asarray(dense(a.layers['simulated_count']))
    if simulated.shape!=baseline.shape or not np.isfinite(simulated).all():raise ValueError('Invalid CellOracle prediction')
    delta=simulated[indices]-baseline[indices];records=[];coverage=[]
    for unit in p['evaluation_units']:
        mask=chosen.obs.unit_id.astype(str).to_numpy()==unit
        records.extend((unit,str(g),float(v)) for g,v in zip(a.var_names,delta[mask].mean(axis=0)));coverage.append((unit,int(mask.sum())))
    targets=pd.DataFrame({'feature_id':p['ko_genes'],'modeled_target_mean':simulated[indices][:,a.var_names.get_indexer(p['ko_genes'])].mean(axis=0)})
    emit(job,out,[pd.DataFrame(records,columns=['unit_id','feature_id','model_delta']),pd.DataFrame(coverage,columns=['unit_id','cells']),targets,pd.DataFrame({'training_unit':e['training_units'],'evaluation_scope':p['evaluation_scope']})],{'units':len(coverage),'cells':len(indices),'mean_absolute_model_delta':float(abs(delta).mean())},interpretation='Clipped fitted-GRN expression shift; clipping may prevent exact target=0; neither observed counts nor causal fate')

def geneformer(job,out):
    import numpy as np,pandas as pd,torch
    from datasets import load_from_disk
    from geneformer import InSilicoPerturber
    p=job['parameters'];version('geneformer',p);bundle,b=assets(job,['model_directory','tokenized_dataset','token_dictionary'])
    if job['resource_budget']['gpus']<1 or not torch.cuda.is_available():raise ValueError('Actual allocated GPU required by reviewed Geneformer perturbation path')
    if b.get('model_version')!=p['model_version'] or b.get('token_dictionary_sha256')!=sha(bundle['token_dictionary']):raise ValueError('Geneformer model/tokenizer version lineage differs from reviewed assets')
    ds=load_from_disk(str(bundle['tokenized_dataset']))
    if not {'unit_id','cell_type','input_ids','length','qc_accepted'}<=set(ds.column_names):raise ValueError('Tokenized cells need donor, cell-type, actual source QC and model-specific token axes')
    tokens=pickle.loads(bundle['token_dictionary'].read_bytes())
    if not all(g in tokens for g in p['ko_genes']):raise ValueError('Selected versioned Ensembl genes are absent from reviewed tokenizer')
    wanted={tokens[g] for g in p['ko_genes']};rows=[];coverage=[];native=[]
    for number,unit in enumerate(p['evaluation_units']):
        subset=ds.filter(lambda x:str(x['unit_id'])==unit and str(x['cell_type'])==p['cell_type'])
        if len(subset)<p['min_cells_per_unit'] or not all(str(v).lower() in ('true','1') for v in subset['qc_accepted']):raise ValueError('Geneformer donor/cell-type QC coverage fails')
        valid_tokens=set(tokens.values())
        if any(len(x['input_ids'])!=x['length'] or len(x['input_ids'])!=len(set(x['input_ids'])) or not set(x['input_ids'])<=valid_tokens for x in subset):raise ValueError('Geneformer rank-token length/uniqueness/vocabulary QC fails')
        covered=sum(wanted<=set(x) for x in subset['input_ids']);coverage.append((unit,len(subset),covered))
        if covered<p['min_cells_per_unit']:raise ValueError('Too few cells actually contain all deleted rank tokens')
        subset=subset.filter(lambda x:wanted<=set(x['input_ids']))
        if len(subset)>p['max_cells_per_unit']:subset=subset.shuffle(seed=p['seed']).select(range(p['max_cells_per_unit']))
        folder=out/('donor_'+str(number));folder.mkdir();data=folder/'selected.dataset';subset.save_to_disk(str(data))
        pert=InSilicoPerturber(perturb_type='delete',genes_to_perturb=p['ko_genes'],combos=0,model_type='Pretrained',num_classes=0,emb_mode='cell',model_version=p['model_version'],token_dictionary_file=str(bundle['token_dictionary']),emb_layer=p['embedding_layer'],max_ncells=len(subset),forward_batch_size=p['batch_size'],nproc=1)
        pert.perturb_data(str(bundle['model_directory']),str(data),str(folder),'perturbation')
        values=[];files=list(folder.glob('*.pickle'))
        if not files:raise ValueError('Native Geneformer perturbation files were not generated')
        for file in files:
            obj=pickle.loads(file.read_bytes());found=False
            for k,v in obj.items():
                if isinstance(k,tuple) and len(k)==2 and k[1]=='cell_emb':values.extend(v);found=True
            if not found:raise ValueError('Unexpected Geneformer output; never reinterpret a different score as cosine similarity')
            native.append((unit,file.relative_to(out).as_posix(),sha(file)))
        scores=np.asarray(values,dtype=float)
        if len(scores)!=len(subset) or not np.isfinite(scores).all() or (abs(scores)>1.000001).any():raise ValueError('Geneformer output denominator/similarity bounds fail; inspect version-specific batched output before acceptance')
        rows.append((unit,'+'.join(p['ko_genes']),float(scores.mean()),float((1-scores).mean()),len(scores)))
    emit(job,out,[pd.DataFrame(rows,columns=['unit_id','perturbation_id','mean_cosine_similarity','mean_embedding_distance','cells']),pd.DataFrame(coverage,columns=['unit_id','input_cells','all_target_tokens_covered']),pd.DataFrame(native,columns=['unit_id','native_output','sha256']),pd.DataFrame({'ko_gene':p['ko_genes'],'token':[tokens[g] for g in p['ko_genes']]})],{'units':len(rows),'cells_scored':sum(r[-1] for r in rows)},interpretation='Rank-token deletion changes an embedding; distance has no logFC/direction or experimental KO units')

def dynamo(job,out):
    import anndata as ad,numpy as np,pandas as pd,dynamo as dyn
    p=job['parameters'];version('dynamo-release',p);bundle,b=assets(job,[p['model_entry'],'coordinate_reference']);e=training(job,b)
    a=ad.read_h5ad(bundle[p['model_entry']]);selected=adata_qc(a,p)
    if 'VecFld_pca' not in a.uns or not all(k in a.obsm for k in ('X_pca','X_umap','velocity_pca','velocity_umap')):raise ValueError('Existing fitted PCA vector field, velocities and embeddings are required')
    reference=np.load(bundle['coordinate_reference'],allow_pickle=False)
    if not all(k in reference for k in ('PCs','X_pca','X_umap','genes','cell_ids')) or not np.array_equal(reference['PCs'],a.uns['PCs']) or not np.array_equal(reference['X_pca'],a.obsm['X_pca']) or not np.array_equal(reference['X_umap'],a.obsm['X_umap']) or not np.array_equal(reference['genes'],a.var_names.to_numpy()) or not np.array_equal(reference['cell_ids'],a.obs_names.to_numpy()):raise ValueError('Dynamo sensitivity vector fields use different coordinate/gene/cell axes; their PC components cannot be compared directly')
    dyn.pd.KO(a,KO_genes=p['ko_genes'],vf_key='VecFld',basis='pca',emb_basis='umap',velocity_ko_wt_difference=True,return_vector_field_class=False)
    if 'velocity_pca_KO' not in a.obsm or 'velocity_umap_KO' not in a.obsm:raise ValueError('Unexpected Dynamo KO vector-field schema')
    indices=a.obs_names.get_indexer(selected.obs_names);velocity=np.asarray(a.obsm['velocity_pca_KO'])[indices];original=np.asarray(a.obsm['velocity_pca'])[indices];delta=velocity-original
    if not np.isfinite(delta).all():raise ValueError('Nonfinite perturbation velocity')
    rows=[]
    for unit in p['evaluation_units']:
        mask=selected.obs.unit_id.astype(str).to_numpy()==unit
        rows.extend((unit,'PC'+str(k+1),float(v)) for k,v in enumerate(delta[mask].mean(axis=0)))
    cells=pd.DataFrame({'cell_id':selected.obs_names,'unit_id':selected.obs.unit_id.astype(str).to_numpy(),'velocity_change_norm':np.linalg.norm(delta,axis=1)})
    embed=np.asarray(a.obsm['velocity_umap_KO'])[indices];embedding=pd.DataFrame({'cell_id':selected.obs_names,'delta_velocity_umap_1':embed[:,0],'delta_velocity_umap_2':embed[:,1]})
    a.write_h5ad(out/'native_dynamo_KO.h5ad')
    emit(job,out,[pd.DataFrame(rows,columns=['unit_id','component','mean_velocity_change']),cells,embedding,pd.DataFrame({'training_unit':e['training_units'],'evaluation_scope':p['evaluation_scope']})],{'units':len(p['evaluation_units']),'cells':len(indices),'mean_velocity_change_norm':float(np.linalg.norm(delta,axis=1).mean())},interpretation='Conditional dynamical vector-field change, not steady-state RNA counts or measured fate probability')

def gears(job,out):
    import numpy as np,pandas as pd,torch
    from gears import PertData,GEARS
    import gears.pertdata as pertmodule
    p=job['parameters'];version('cell-gears',p);bundle,b=assets(job,['model_directory','dataset_directory','cache_directory']);e=training(job,b)
    if e.get('training_modality') not in ('CRISPR_KO','CRISPRi') or e.get('cell_type')!=p['cell_type']:raise ValueError('GEARS needs real perturbation training data in the selected cell context')
    if len(p['ko_genes'])>1 and not e.get('combination_training_conditions'):raise ValueError('Single-perturbation training alone is not accepted as validated combination-response prediction')
    def existing_only(url,path,*args,**kwargs):
        if not Path(path).is_file():raise ValueError('Required GEARS GO cache is absent; no automatic download')
    pertmodule.dataverse_download=existing_only
    if not (bundle['dataset_directory']/'data_pyg/cell_graphs.pkl').is_file():raise ValueError('Existing hash-bound GEARS processed graphs required')
    config=pickle.loads((bundle['model_directory']/'config.pkl').read_bytes())
    if any(config.get(k) is None for k in ('G_go','G_go_weight','G_coexpress','G_coexpress_weight')):raise ValueError('Frozen graph tensors must be saved in reviewed GEARS checkpoint; no rebuilding from evaluation data')
    data=PertData(str(bundle['cache_directory']));data.load(data_path=str(bundle['dataset_directory']))
    if not {'unit_id','qc_accepted','cell_type','condition'}<=set(data.adata.obs):raise ValueError('GEARS evaluation context lacks real donor/QC identity')
    a=data.adata.copy()
    if not a.var.gene_name.is_unique:raise ValueError('Ambiguous GEARS model gene-symbol axis')
    a.var_names=a.var.gene_name.astype(str);chosen=adata_qc(a,p)
    data.gene_names=a.var.gene_name;data.node_map={g:i for i,g in enumerate(data.gene_names)};data.dataloader={};data.set2conditions=e['set2conditions'];data.split='custom';data.seed=e['training_seed']
    model=GEARS(data,device=p['device'],weight_bias_track=False);model.load_pretrained(str(bundle['model_directory']))
    rows=[];coverage=[];targets=[];uncertainty=[];rng=np.random.default_rng(p['seed'])
    for unit in p['evaluation_units']:
        controls=chosen[(chosen.obs.unit_id.astype(str)==unit)&(chosen.obs.condition=='ctrl')].copy()
        if controls.n_obs<p['min_control_cells']:raise ValueError('GEARS lacks donor-specific controls')
        if controls.n_obs>p['max_control_cells']:controls=controls[rng.choice(controls.n_obs,p['max_control_cells'],replace=False)].copy()
        model.adata=controls;model.saved_pred={};model.saved_logvar_sum={}
        prediction=model.predict([p['ko_genes']]);unc=None
        if isinstance(prediction,tuple):prediction,unc=prediction
        name='_'.join(p['ko_genes']);values=np.asarray(prediction[name],dtype=float);baseline=np.asarray(dense(controls.X)).mean(axis=0)
        if values.shape!=baseline.shape or values.size!=len(data.gene_names) or not np.isfinite(values).all():raise ValueError('Invalid GEARS expression axis or output')
        rows.extend((unit,str(g),float(v),float(c),float(v-c)) for g,v,c in zip(data.gene_names,values,baseline));coverage.append((unit,controls.n_obs,len(values)))
        targets.extend((unit,g,float(values[list(data.gene_names).index(g)])) for g in p['ko_genes'])
        uncertainty.append((unit,'native_inverse_exp_mean_logvariance' if unc is not None else 'UNASSESSED',float(unc[name]) if unc is not None else 'NA'))
    emit(job,out,[pd.DataFrame(rows,columns=['unit_id','feature_id','predicted_expression','matched_control_mean','model_delta']),pd.DataFrame(coverage,columns=['unit_id','control_cells','genes']),pd.DataFrame(targets,columns=['unit_id','ko_gene','predicted_target_expression']),pd.DataFrame(uncertainty,columns=['unit_id','uncertainty_kind','native_uncertainty_score'])],{'units':len(coverage),'gene_unit_denominator':len(rows)},interpretation='Conditional response prediction on the exact training scale; native uncertainty score is not a confidence interval; CRISPRi is not a full knockout')

def cobra(job,out):
    import numpy as np,pandas as pd,cobra as cb
    from cobra.flux_analysis import single_gene_deletion,moma,room,pfba
    p=job['parameters'];version('cobra',p)
    model=cb.io.read_sbml_model(str(job['inputs']['sbml_model']));medium=read(job['inputs']['medium']);review=read(job['inputs']['model_review'])
    if review.get('model_sha256')!=sha(job['inputs']['sbml_model']) or review.get('mass_balance_review')!='ACCEPT' or review.get('gpr_review')!='ACCEPT' or review.get('objective')!=p['objective_reaction']:raise ValueError('Exact mass-balance/GPR/objective model review required')
    if set(p['evaluation_units'])!={review.get('model_id')}:raise ValueError('A metabolic model is one modeled system, not a collection of independent donors')
    if not set(p['ko_genes']+p['control_genes'])<=set(g.id for g in model.genes):raise ValueError('KO or control genes are absent from the SBML GPR')
    if set(p['ko_genes'])&set(p['control_genes']):raise ValueError('Metabolic controls overlap KO genes')
    for k,v in medium.items():
        if not isinstance(k,str) or type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Invalid explicit exchange medium')
    model.medium=medium;model.objective=p['objective_reaction'];model.objective_direction='max';model.solver=p['solver']
    allowed=set(review.get('allowed_imbalanced_reactions',[]));allowed_unknown=set(review.get('allowed_formula_unknown_metabolites',[]));structure=[]
    missing={m.id for m in model.metabolites if not m.formula or m.charge is None}
    if missing-allowed_unknown:raise ValueError('Metabolite formula/charge missing without explicit reviewed scope')
    for reaction in model.reactions:
        balance=reaction.check_mass_balance();unknown=bool({m.id for m in reaction.metabolites}&missing)
        if (balance or unknown) and not reaction.boundary and reaction.id not in allowed:raise ValueError('Unreviewed internal reaction mass/charge imbalance or unknown composition')
        structure.append((reaction.id,reaction.boundary,bool(balance),unknown,reaction.id in allowed,reaction.gene_reaction_rule))
    pd.DataFrame(structure,columns=['reaction_id','boundary','imbalance_detected','composition_unknown','explicitly_reviewed_exception','gpr']).to_csv(out/'model_structure_qc.tsv',sep='\t',index=False)
    wt=pfba(model)
    if wt.status!='optimal' or not math.isfinite(wt.fluxes[p['objective_reaction']]) or wt.fluxes[p['objective_reaction']]<=p['minimum_WT_objective']:raise ValueError('Model WT objective is infeasible, unbounded or below prespecified support')
    def residual(solution):
        return max(abs(sum(float(solution.fluxes[r.id])*r.metabolites[m] for r in m.reactions)) for m in model.metabolites)
    WT_residual=residual(wt)
    if WT_residual>p['steady_state_tolerance']:raise ValueError('WT stoichiometric steady-state residual fails')
    objective_WT=float(wt.fluxes[p['objective_reaction']]);cases=[('requested_joint',p['ko_genes'])]+[('single_'+str(k),[g]) for k,g in enumerate(p['ko_genes'])]+[('control_'+str(k),[g]) for k,g in enumerate(p['control_genes'])]
    effects=[];flux=[];gprs=[];controls=[];residuals=[('WT',WT_residual)]
    for name,genes in cases:
        with model:
            for g in genes:model.genes.get_by_id(g).knock_out()
            if p['solution_method']=='FBA':solution=model.optimize()
            elif p['solution_method']=='linear_MOMA':solution=moma(model,solution=wt,linear=True)
            elif p['solution_method']=='linear_ROOM':solution=room(model,solution=wt,linear=True,delta=p['room_delta'],epsilon=p['room_epsilon'])
            else:raise ValueError('Unsupported metabolic method')
            # MOMA/ROOM optimize a distance/change objective. Read the biological objective reaction flux explicitly.
            ok=solution.status=='optimal';value=float(solution.fluxes[p['objective_reaction']]) if ok else None
            effects.append((review['model_id'],name,'+'.join(genes),solution.status,value,objective_WT,value/objective_WT if ok else None))
            if ok:
                error=residual(solution);residuals.append((name,error))
                if error>p['steady_state_tolerance']:raise ValueError('KO steady-state residual fails; solver success is insufficient')
                flux.extend((name,r.id,float(solution.fluxes[r.id]),float(wt.fluxes[r.id])) for r in model.reactions)
            for g in genes:
                for reaction in model.genes.get_by_id(g).reactions:gprs.append((name,g,reaction.id,reaction.gene_reaction_rule,reaction.lower_bound,reaction.upper_bound))
            if name.startswith('control_'):controls.append((name,'+'.join(genes),solution.status,value))
    if not all(r[3]=='optimal' for r in effects):raise ValueError('Deletion solution infeasibility is not automatically a biological lethal effect; inspect solver/medium/constraints')
    pd.DataFrame(residuals,columns=['perturbation_id','maximum_stoichiometric_residual']).to_csv(out/'steady_state_residuals.tsv',sep='\t',index=False)
    emit(job,out,[pd.DataFrame(effects,columns=['unit_id','perturbation_id','genes','solver_status','KO_objective_flux','WT_objective_flux','objective_ratio']),pd.DataFrame(flux,columns=['perturbation_id','reaction_id','KO_flux','WT_flux']),pd.DataFrame(gprs,columns=['perturbation_id','gene_id','reaction_id','gpr','lower_bound','upper_bound']).drop_duplicates(),pd.DataFrame(controls,columns=['perturbation_id','genes','solver_status','objective_flux'])],{'model_genes':len(model.genes),'model_reactions':len(model.reactions),'WT_objective_flux':objective_WT,'evaluated_cases':len(cases),'maximum_stoichiometric_residual':max(x[1] for x in residuals)},interpretation='Objective/flux response under explicit medium and GPR assumptions; no measured viability or population inference')

def main():
    import platform
    if sys.platform!='linux' or 'microsoft' in platform.release().lower() or not (os.environ.get('SLURM_JOB_ID') or os.environ.get('SSH_CONNECTION')):raise RuntimeError('Scientific worker cannot run locally')
    job=read(sys.argv[1]);out=Path(sys.argv[2]);offline();random.seed(job['parameters']['seed'])
    # Reviewed GenKI source auto-selects CUDA but later calls Tensor.numpy() without cpu().
    # Select its CPU path before importing torch rather than silently editing the original algorithm.
    if job['method']=='genki':os.environ['CUDA_VISIBLE_DEVICES']=''
    from child_guard import verify
    verify(job)
    import numpy as np
    np.random.seed(job['parameters']['seed'])
    from additional_methods import cpa,scgpt,maboss
    functions={'genki':genki,'celloracle':celloracle,'geneformer':geneformer,'dynamo':dynamo,'gears':gears,'metabolic_gene_deletion':cobra,'cpa':cpa,'scgpt':scgpt,'maboss':maboss}
    functions[job['method']](job,out)
    if 'asset_manifest' in job['inputs']:assets(job,[])

if __name__=='__main__':main()
