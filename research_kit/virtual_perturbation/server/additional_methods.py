"""Fixed CPA/scGPT/MaBoSS analysis calls, available only through the guarded server worker."""
from pathlib import Path
import csv,math,shutil
from contracts import read,write,sha
from methods import assets,training,version,adata_qc,dense,emit
from model_contracts import cpa_dose_string,cpa_setup_contract,scgpt_architecture_contract

def expression_outputs(job,out,predictions,controls,coverage,details,metrics):
    import numpy as np,pandas as pd
    records=[]
    for unit,genes,wt,ko in predictions:
        if wt.shape!=ko.shape or ko.shape[1]!=len(genes) or not np.isfinite(ko).all() or not np.isfinite(wt).all():raise ValueError('Predicted expression/control axes or values fail')
        records.extend((unit,str(g),float(a),float(b),float(b-a)) for g,a,b in zip(genes,wt.mean(axis=0),ko.mean(axis=0)))
    emit(job,out,[pd.DataFrame(records,columns=['unit_id','feature_id','predicted_control','predicted_perturbation','model_delta']),pd.DataFrame(coverage,columns=['unit_id','control_cells','genes']),pd.DataFrame(controls),pd.DataFrame(details)],metrics,interpretation='Checkpoint-conditional expression response, not measured knockout; matched predicted-control subtraction avoids treating reconstruction bias as perturbation effect')

def cpa(job,out):
    import numpy as np,pandas as pd,anndata as ad,cpa as package,torch
    p=job['parameters'];version('cpa-tools',p);A,b=assets(job,['model_directory','registered_reference','control_adata']);e=training(job,b)
    if not job['context'].get('training_expression_contract') or job['context']['training_expression_contract']!=e.get('training_expression_contract'):raise ValueError('CPA transformation/normalization/gene-axis contract differs from training')
    if e.get('training_modality') not in ('CRISPR_KO','CRISPRi') or e.get('checkpoint_task')!='CPA_perturbation_response':raise ValueError('Actual genetic-perturbation-trained CPA checkpoint required')
    if e.get('layer') is not None:raise ValueError('This exact CPA adapter expects the reviewed model registered on X; layer-specific models need an explicit compatible adapter')
    perturb=e['perturbation_key'];dose=e['dosage_key'];control=e['control_group'];target='+'.join(p['ko_genes'])
    if any('+' in g for g in p['ko_genes']) or not set(p['ko_genes'])<=set(e['perturbation_vocabulary']):raise ValueError('Unknown/ambiguous perturbation labels')
    if len(p['ko_genes'])>1 and not e.get('combination_training_conditions'):raise ValueError('Combination prediction requires actual combination training evidence')
    if not e['dose_support'][0]<=p['dose']<=e['dose_support'][1]:raise ValueError('Dose is outside reviewed training support')
    reference=ad.read_h5ad(A['registered_reference']);a=adata_qc(ad.read_h5ad(A['control_adata']),p)
    if not a.var_names.equals(reference.var_names):raise ValueError('CPA gene axis differs from the fitted reference')
    model=package.CPA.load(str(A['model_directory']),adata=reference,use_gpu=p['device']=='cuda')
    if not model.is_trained_:raise ValueError('CPA checkpoint is not fitted')
    setup=cpa_setup_contract(dict(model.adata_manager.registry['setup_args']),e,p['ko_genes'],model.pert_encoder,model.covars_encoder)
    predictions=[];coverage=[];audit=[];detail=[];rng=np.random.default_rng(p['seed'])
    for unit in p['evaluation_units']:
        cells=a[(a.obs.unit_id.astype(str)==unit)&(a.obs[perturb].astype(str)==control)].copy()
        if cells.n_obs<p['min_control_cells']:raise ValueError('CPA donor-matched controls insufficient')
        if cells.n_obs>p['max_control_cells']:cells=cells[rng.choice(cells.n_obs,p['max_control_cells'],replace=False)].copy()
        for name,allowed in e['covariate_support'].items():
            if name not in cells.obs or not set(cells.obs[name].astype(str))<=set(allowed):raise ValueError('CPA categorical context outside reviewed training support')
        counts=np.asarray(dense(cells.X))
        if not np.isfinite(counts).all() or (counts<0).any():raise ValueError('CPA baseline expression invalid')
        def predict(label,value):
            obs=cells.obs.loc[:,[c for c in cells.obs if not c.startswith('_scvi')]].copy();obs[perturb]=label;obs[dose]=cpa_dose_string(value,label.split('+'))
            query=ad.AnnData(X=cells.X.copy(),obs=obs,var=cells.var.copy())
            import copy
            package.CPA.setup_anndata(query,**copy.deepcopy(setup))
            torch.manual_seed(p['seed']);model.predict(adata=query,batch_size=p['batch_size'],n_samples=p['posterior_samples'],return_mean=True)
            z=np.asarray(query.obsm['CPA_pred'])
            if z.shape!=cells.shape:raise ValueError('Unexpected current CPA native prediction shape')
            return z
        wt=predict(control,e['control_dose']);ko=predict(target,p['dose'])
        if np.sqrt(((wt-counts)**2).mean())>p['max_control_reconstruction_rmse']:raise ValueError('CPA control reconstruction fails the prespecified training-scale bound')
        predictions.append((unit,list(a.var_names),wt,ko));coverage.append((unit,cells.n_obs,cells.n_vars));audit.append({'unit_id':unit,'control_label':control,'target_label':target,'dose':p['dose'],'observed_counterfactual_truth_available':False});detail.append({'unit_id':unit,'evaluation_scope':p['evaluation_scope'],'posterior_samples':p['posterior_samples'],'matched_control_reconstruction_RMSE':float(np.sqrt(((wt-counts)**2).mean()))})
    expression_outputs(job,out,predictions,audit,coverage,detail,{'units':len(coverage),'predicted_gene_units':sum(len(r[1]) for r in predictions),'maximum_control_reconstruction_RMSE':max(r['matched_control_reconstruction_RMSE'] for r in detail)})

def scgpt(job,out):
    import numpy as np,pandas as pd,anndata as ad,torch
    from scgpt.model import TransformerGenerator
    from scgpt.tokenizer.gene_tokenizer import GeneVocab
    p=job['parameters'];version('scgpt',p);A,b=assets(job,['model_config','vocabulary','model_state','control_adata']);e=training(job,b)
    if e.get('cell_type')!=p['cell_type'] or not job['context'].get('training_expression_contract') or job['context']['training_expression_contract']!=e.get('training_expression_contract'):raise ValueError('scGPT cell context or transformation/normalization/gene-axis contract differs from training')
    if e.get('checkpoint_task')!='scGPT_perturbation_finetuned' or e.get('training_modality') not in ('CRISPR_KO','CRISPRi'):raise ValueError('Generic scGPT pretraining weights are not a perturbation-finetuned checkpoint')
    if len(p['ko_genes'])>1 and not e.get('combination_training_conditions'):raise ValueError('Combination inference lacks combination training evidence')
    a=adata_qc(ad.read_h5ad(A['control_adata']),p);cfg=read(A['model_config']);vocab=GeneVocab.from_file(A['vocabulary'])
    allowed={'d_model','nhead','d_hid','nlayers','nlayers_cls','n_cls','dropout','pad_token','pad_value','pert_pad_id','do_mvc','domain_spec_batchnorm','cell_emb_style','mvc_decoder_style','ecs_threshold','explicit_zero_prob','use_fast_transformer','fast_transformer_backend','pre_norm'}
    if set(cfg)-allowed or not {'d_model','nhead','d_hid','nlayers','nlayers_cls','n_cls','pad_token','pad_value','pert_pad_id','explicit_zero_prob'}<=set(cfg):raise ValueError('Frozen exact TransformerGenerator architecture required; no inferred dimensions or partial weight loading')
    scgpt_architecture_contract(cfg)
    if any(g not in vocab for g in a.var_names) or a.n_vars>p['max_sequence_genes']:raise ValueError('Missing model-vocabulary genes or sequence exceeds reviewed training scope; do not silently truncate or fill unmapped genes with pad')
    model=TransformerGenerator(ntoken=len(vocab),vocab=vocab,**cfg)
    state=torch.load(A['model_state'],map_location='cpu',weights_only=True);model.load_state_dict(state,strict=True);model.to(p['device']);model.eval()
    ids=torch.tensor([vocab[g] for g in a.var_names],dtype=torch.long,device=p['device']);target_indices=a.var_names.get_indexer(p['ko_genes']);predictions=[];coverage=[];audit=[];detail=[];rng=np.random.default_rng(p['seed'])
    for unit in p['evaluation_units']:
        cells=a[(a.obs.unit_id.astype(str)==unit)&(a.obs[e['condition_key']].astype(str)==e['control_group'])].copy()
        if cells.n_obs<p['min_control_cells']:raise ValueError('scGPT donor-matched control coverage fails')
        if cells.n_obs>p['max_control_cells']:cells=cells[rng.choice(cells.n_obs,p['max_control_cells'],replace=False)].copy()
        x=np.asarray(dense(cells.X),dtype=np.float32)
        if not np.isfinite(x).all() or (x<0).any():raise ValueError('scGPT training-scale control expression invalid')
        def predict(perturbed):
            output=[]
            with torch.no_grad():
                for start in range(0,len(x),p['batch_size']):
                    values=torch.tensor(x[start:start+p['batch_size']],device=p['device']);flags=torch.zeros_like(values,dtype=torch.long)
                    if perturbed:flags[:,target_indices]=1
                    tokens=ids.repeat(len(values),1);mask=torch.zeros_like(values,dtype=torch.bool)
                    z=model(tokens,values,flags,src_key_padding_mask=mask,CLS=False,CCE=False,MVC=False,ECS=False,do_sample=False)['mlm_output']
                    output.append(z.detach().cpu().numpy())
            return np.concatenate(output)
        wt=predict(False);ko=predict(True)
        if np.sqrt(((wt-x)**2).mean())>p['max_control_reconstruction_rmse']:raise ValueError('scGPT control reconstruction fails the prespecified training-scale bound')
        predictions.append((unit,list(a.var_names),wt,ko));coverage.append((unit,cells.n_obs,cells.n_vars));audit.append({'unit_id':unit,'perturbation_flags':','.join(p['ko_genes']),'all_frozen_genes_retained':True});detail.append({'unit_id':unit,'evaluation_scope':p['evaluation_scope'],'control_reconstruction_RMSE':float(np.sqrt(((wt-x)**2).mean()))})
    expression_outputs(job,out,predictions,audit,coverage,detail,{'units':len(coverage),'predicted_gene_units':sum(len(r[1]) for r in predictions),'maximum_control_reconstruction_RMSE':max(r['control_reconstruction_RMSE'] for r in detail)})

def maboss(job,out):
    import numpy as np,pandas as pd,maboss as package
    p=job['parameters'];version('maboss',p);exe=shutil.which('MaBoSS')
    if exe is None or sha(exe)!=p['expected_binary_sha256']:raise ValueError('Existing exact reviewed MaBoSS binary required')
    review=read(job['inputs']['logical_review'])
    if review.get('bnd_sha256')!=sha(job['inputs']['bnd']) or review.get('cfg_sha256')!=sha(job['inputs']['cfg']) or review.get('logic_review')!='ACCEPT' or review.get('rate_review')!='ACCEPT' or p['evaluation_units']!=[review['model_id']]:raise ValueError('Exact logical/rate/model review required')
    initial=pd.read_csv(job['inputs']['initial_probabilities'],sep='\t',dtype={'node':str})
    if initial.node.duplicated().any() or not np.isfinite(initial.p_on).all() or not initial.p_on.between(0,1).all():raise ValueError('Explicit independent Bernoulli initial probabilities invalid')
    base=package.load(job['inputs']['bnd'],job['inputs']['cfg'])
    nodes=set(base.network)
    if set(initial.node)!=nodes or not set(p['ko_genes'])<=nodes or not set(p['output_nodes'])<=nodes:raise ValueError('Logical node, KO or complete initial-state axes mismatch')
    for row in initial.itertuples():base.network.set_istate(row.node,[1-float(row.p_on),float(row.p_on)])
    package.set_output(base,p['output_nodes']);base.update_parameters(max_time=p['max_time'],time_tick=p['time_tick'],sample_count=p['trajectories'],seed_pseudorandom=p['seed'],thread_count=job['resource_budget']['cpus'],use_physrandgen=0)
    ko=package.copy_and_mutate(base,p['ko_genes'],'OFF')
    for gene in p['ko_genes']:ko.network.set_istate(gene,[1.,0.])
    results={};states=[];errors=[]
    for label,sim in [('WT',base),('KO',ko)]:
        folder=out/label;folder.mkdir();result=sim.run(command=exe,workdir=str(folder),overwrite=False,prefix='simulation')
        if getattr(result,'_err',None)!=0:raise ValueError('MaBoSS did not return native exit code zero; partial outputs are not completion')
        z=result.get_nodes_probtraj(nodes=p['output_nodes'],prob_cutoff=None);allstates=result.get_states_probtraj(prob_cutoff=None)
        if not z.index.is_unique or not z.index.is_monotonic_increasing or set(z.columns)!=set(p['output_nodes']) or not np.isfinite(z.to_numpy()).all() or ((z<0)|(z>1)).any().any():raise ValueError('MaBoSS native node/time probability schema invalid')
        if not allstates.index.equals(z.index) or not np.isfinite(allstates.to_numpy()).all() or ((allstates<0)|(allstates>1)).any().any() or np.max(abs(allstates.sum(axis=1)-1))>p['probability_tolerance']:raise ValueError('Full state-probability mass/axes fail; do not use a cutoff-filtered distribution')
        if z.index[-1]<p['max_time']-p['time_tick']*1.1:raise ValueError('MaBoSS did not reach requested simulation horizon')
        if label=='KO' and float(abs(z[p['ko_genes']]).to_numpy().max())>p['probability_tolerance']:raise ValueError('MaBoSS OFF mutation did not keep target-node probability at zero')
        results[label]=z;allstates.to_csv(folder/'full_state_probabilities.tsv',sep='\t',index=True);err=result.get_nodes_probtraj_error()
        if not err.index.equals(z.index) or not set(p['output_nodes'])<=set(err.columns) or not np.isfinite(err[p['output_nodes']].to_numpy()).all() or (err[p['output_nodes']]<0).any().any():raise ValueError('MaBoSS native Monte Carlo error axes/values fail')
        err.to_csv(folder/'native_MC_errors.tsv',sep='\t',index=True)
        for t,row in z.iterrows():states.extend((label,float(t),str(n),float(v)) for n,v in row.items())
        errors.append((label,len(z),float(abs(z.iloc[-1]-z.iloc[-2]).max()) if len(z)>1 else 0,float(err[p['output_nodes']].to_numpy().max())))
    wt,ko=results['WT'],results['KO']
    if not wt.index.equals(ko.index):raise ValueError('WT/KO simulated time axes differ')
    main=pd.DataFrame({'unit_id':review['model_id'],'feature_id':p['output_nodes'],'WT_probability':wt.iloc[-1].reindex(p['output_nodes']).to_numpy(),'KO_probability':ko.iloc[-1].reindex(p['output_nodes']).to_numpy()});main['probability_delta']=main.KO_probability-main.WT_probability
    emit(job,out,[main,pd.DataFrame(states,columns=['scenario','time','node','probability']),initial,pd.DataFrame(errors,columns=['scenario','time_points','terminal_last_step_change','maximum_native_MC_error'])],{'modeled_nodes':len(nodes),'trajectories_per_scenario':p['trajectories'],'requested_horizon':p['max_time'],'terminal_last_step_change':max(r[2] for r in errors),'maximum_native_MC_error':max(r[3] for r in errors)},interpretation='Finite-horizon logical-state probabilities under declared rates and independent Bernoulli initial distribution; not proven stationary probabilities, measured expression or biological replication; MC error is simulation precision')
