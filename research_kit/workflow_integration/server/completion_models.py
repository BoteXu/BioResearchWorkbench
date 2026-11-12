"""Actual author-model inference, selected existing server environments only.

Nothing in this module trains a model or fabricates an observed modality. Imports
inside functions are intentional: local planning must not initialize any engine.
"""
from pathlib import Path
import os
import sys
from runtime import read,sha,write
from completion_common import (model_manifest,model_device,safe_state,text_axis,
    metadata,matrix,save_matrix)

def _identity(meta,kind,out,outputs):
    q=meta.copy();q['data_kind']=kind;q['independent_validation']='not_established'
    path=out/'prediction_identity.tsv';q.to_csv(path,sep='\t',index=False);outputs.append((path,'prediction_identity'))

def _primary(out,outputs,rows):
    import pandas as pd
    path=out/'primary_results.tsv';pd.DataFrame(rows).to_csv(path,sep='\t',index=False);outputs.append((path,'primary_results'))

def _check_rows(x,meta,p):
    if list(x.index.astype(str))!=meta.query_id.tolist():raise ValueError('Literal expression/query row order differs; no positional reassignment')
    if len(meta)>p['maximum_cases']:raise ValueError('Query exceeds the selected server case budget')

def _state(d):
    return d['state_dict'] if 'state_dict' in d else d

def prnet(ids,p,out,kind):
    import numpy as np
    from models.PRnet import PGM
    m=model_manifest(ids,p,'prnet_predict');torch,device=model_device(p)
    features=text_axis(ids['features']);x=matrix(ids,'query_expression',features,p);meta=metadata(ids,len(x));_check_rows(x,meta,p)
    if m['preprocessing'].get('scale')!='log1p_normalized' or m.get('likelihood')!='gaussian':raise ValueError('This route implements the author Gaussian/log-normalized model only; no silent NB substitution')
    import pandas as pd
    cond=pd.read_csv(ids['condition_embeddings'],sep='\t',index_col=0,dtype=str,keep_default_na=False)
    if list(cond.index.astype(str))!=meta.query_id.tolist() or list(cond.columns)!=m.get('condition_feature_order') or not np.isfinite(cond.to_numpy(dtype=float)).all():raise ValueError('Actual checkpoint-compatible drug/dose embeddings and exact query axis required')
    cond=cond.apply(pd.to_numeric,errors='raise')
    allowed={'x_dim','c_dim','n_dim','hidden_layer_sizes','z_dimension','adaptor_layer_sizes','comb_adapt_dim','dr_rate'}
    cfg=p['architecture']
    if set(cfg)!=allowed or cfg['x_dim']!=len(features) or cfg['comb_adapt_dim']!=cond.shape[1] or cfg['n_dim']!=10 or cfg!=m.get('architecture'):raise ValueError('PRnet checkpoint architecture or real condition feature axis differs')
    model=PGM(**cfg).to(device);model.load_state_dict(_state(safe_state(ids['checkpoint'],torch)),strict=True);model.eval()
    means=[];sds=[];predictions=[]
    with torch.inference_mode():
        for i in range(0,len(x),p['batch_size']):
            a=torch.tensor(x.iloc[i:i+p['batch_size']].to_numpy(dtype='float32'),device=device)
            c=torch.tensor(cond.iloc[i:i+p['batch_size']].to_numpy(dtype='float32'),device=device)
            y=model(a,c,torch.randn((len(a),10),device=device))
            if y.shape!=(len(a),2*len(features)):raise ValueError('PRnet decoder channel contract differs from checkpoint')
            mean=y[:,:len(features)];sd=torch.sqrt(torch.nn.functional.softplus(y[:,len(features):]))
            # These clamps and Gaussian draws follow the author test path; means/SD
            # are also returned unchanged so the sampling presentation is auditable.
            pred=torch.distributions.Normal(mean.clamp(1e-3,1e3),sd.clamp(1e-3,1e3)).sample() if p['gaussian_sampling'] else mean
            means.append(mean.cpu().numpy());sds.append(sd.cpu().numpy());predictions.append(pred.cpu().numpy())
    outputs=[]
    for name,a,role in [('prediction.tsv',np.concatenate(predictions),'prediction_matrix'),('mean.tsv',np.concatenate(means),'prediction_mean'),('sd.tsv',np.concatenate(sds),'prediction_sd')]:save_matrix(out,name,a,meta.query_id,features,role,outputs)
    _identity(meta,kind,out,outputs);_primary(out,outputs,[{'queries':len(meta),'features':len(features),'likelihood':'gaussian','output_kind':kind}])
    return outputs,{'queries':len(meta),'features':len(features),'minimum_predictive_sd':float(np.concatenate(sds).min()),'gaussian_sampling':p['gaussian_sampling']}

def scdiffusion(ids,p,out,kind):
    import numpy as np
    import pandas as pd
    from guided_diffusion.script_util import create_model_and_diffusion,model_and_diffusion_defaults,create_classifier_and_diffusion,classifier_and_diffusion_defaults
    from VAE.VAE_model import VAE
    m=model_manifest(ids,p,'scdiffusion_generate');torch,device=model_device(p);features=text_axis(ids['features'])
    cfg=p['diffusion_config']
    if set(cfg)!=set(model_and_diffusion_defaults()) or cfg!=m.get('diffusion_config') or cfg['input_dim']!=p['latent_dim'] or cfg['class_cond'] is not False:raise ValueError('Explicit complete frozen unconditional scDiffusion configuration required')
    if p['n_samples']*len(features)>p['maximum_output_entries']:raise ValueError('Generated expression exceeds explicit server budget')
    model,diffusion=create_model_and_diffusion(**cfg);model.load_state_dict(_state(safe_state(ids['checkpoint'],torch)),strict=True);model.to(device).eval()
    ae=VAE(len(features),device=str(device),seed=p['seed'],hidden_dim=p['latent_dim'])
    # Author transfer-loading helpers intentionally delete trained endpoint keys.
    # Frozen inference loads every key strictly, preserving the real gene axis.
    ae_state=safe_state(ids['autoencoder_checkpoint'],torch)
    if set(ae_state)=={'encoder','decoder'}:
        ae.encoder.load_state_dict(_state(ae_state['encoder']),strict=True);ae.decoder.load_state_dict(_state(ae_state['decoder']),strict=True)
    else:ae.load_state_dict(_state(ae_state),strict=True)
    ae.eval();latent=[];expression=[];classifiers=[]
    for g in p['guidance']:
        bound=m.get('guidance_models',{}).get(g['input_id'],{})
        if m.get('artifact_sha256',{}).get(g['input_id'])!=sha(ids[g['input_id']]) or bound.get('config')!=g['config'] or set(g['config'])!=set(classifier_and_diffusion_defaults()) or g['config']['input_dim']!=p['latent_dim']:raise ValueError('Guidance checkpoint/architecture is not bound to this actual model manifest')
        order=bound.get('class_order',[])
        if len(order)!=g['config']['num_class'] or g['target_class']>=len(order) or order[g['target_class']]!=g['class_label']:raise ValueError('Classifier numeric target and literal class order differ')
        for k in ['diffusion_steps','noise_schedule','timestep_respacing','rescale_timesteps']:
            if g['config'][k]!=cfg[k]:raise ValueError('Classifier timestep/noise training schedule differs from the generative backbone')
        classifier,_=create_classifier_and_diffusion(**g['config']);classifier.load_state_dict(_state(safe_state(ids[g['input_id']],torch)),strict=True);classifier.to(device).eval();classifiers.append((classifier,g))
    def cond_fn(x,t,**unused):
        with torch.enable_grad():
            a=x.detach().requires_grad_(True);gradient=torch.zeros_like(a)
            for cl,g in classifiers:
                logits=cl(a,t);selected=torch.nn.functional.log_softmax(logits,dim=-1)[:,g['target_class']]
                gradient=gradient+torch.autograd.grad(selected.sum(),a)[0]*g['scale']
            return gradient
    # Classifier guidance requires autograd for input gradients; inference_mode
    # would incorrectly disable that computation even inside enable_grad.
    with torch.no_grad():
        for i in range(0,p['n_samples'],p['batch_size']):
            n=min(p['batch_size'],p['n_samples']-i);fn=diffusion.p_sample_loop if p['sampling_method']=='ddpm' else diffusion.ddim_sample_loop
            kw={'clip_denoised':p['clip_denoised'],'device':device,'progress':False}
            if p['sampling_method']=='ddpm':kw['start_time']=len(diffusion.betas)
            if classifiers:
                kw['cond_fn']=cond_fn
                if p['sampling_method']=='ddpm':kw['start_guide_steps']=p['guidance_start_step']
            z=fn(model,(n,p['latent_dim']),**kw)
            if p['sampling_method']=='ddpm':z=z[0] # pinned DDPM returns (sample, trajectory); DDIM returns a tensor.
            latent.append(z.cpu().numpy());expression.append(ae(z,return_decoded=True).cpu().numpy())
    names=[f'model_draw_seed{p["seed"]}_{i+1:06d}' for i in range(p['n_samples'])]
    meta=pd.DataFrame({'query_id':names,'unit_id':['not_a_biological_replicate']*len(names),'draw_seed':[p['seed']]*len(names)})
    meta['generated_condition']=' + '.join(g['class_label'] for g in p['guidance']) if classifiers else 'unconditional'
    outputs=[];save_matrix(out,'prediction.tsv',np.concatenate(expression),names,features,'prediction_matrix',outputs)
    save_matrix(out,'latent.tsv',np.concatenate(latent),names,[f'latent_{j+1}' for j in range(p['latent_dim'])],'latent_representation',outputs)
    _identity(meta,kind,out,outputs);_primary(out,outputs,[{'draws':len(names),'features':len(features),'sampling':p['sampling_method'],'condition':meta.generated_condition.iloc[0]}])
    return outputs,{'generated_draws':len(names),'features':len(features),'guidance_classifiers':len(classifiers),'negative_decoded_fraction':float((np.concatenate(expression)<0).mean())}

def squidiff(ids,p,out,kind):
    import numpy as np
    from Squidiff.script_util import create_model_and_diffusion,model_and_diffusion_defaults
    m=model_manifest(ids,p,'squidiff_predict');torch,device=model_device(p);features=text_axis(ids['features']);x=matrix(ids,'query_expression',features,p);meta=metadata(ids,len(x));_check_rows(x,meta,p)
    cfg=p['diffusion_config']
    if set(cfg)!=set(model_and_diffusion_defaults()) or cfg!=m.get('diffusion_config') or cfg['gene_size']!=len(features) or cfg['use_encoder'] is not True or cfg['use_drug_structure'] or cfg['class_cond']:raise ValueError('This branch uses the original semantic encoder and a frozen latent direction, not an unprovided chemical encoder')
    direction=read(ids['latent_direction'])
    if direction.get('scope')!='training_units_only' or not direction.get('training_units') or direction.get('checkpoint_sha256')!=sha(ids['checkpoint']):raise ValueError('Latent direction must be frozen from named training units and this exact checkpoint')
    if set(meta.unit_id)&set(direction['training_units']):raise ValueError('Prediction-unit leakage into direction construction')
    vector=np.asarray(direction['vector'],dtype=float)
    if vector.ndim!=1 or len(vector)!=cfg['output_dim'] or not np.isfinite(vector).all():raise ValueError('Actual native semantic direction dimension required')
    model,diffusion=create_model_and_diffusion(**cfg);model.load_state_dict(_state(safe_state(ids['checkpoint'],torch)),strict=True);model.to(device).eval();pred=[];lat=[]
    with torch.inference_mode():
        for i in range(0,len(x),p['batch_size']):
            a=torch.tensor(x.iloc[i:i+p['batch_size']].to_numpy(dtype='float32'),device=device)
            z=model.encoder(a)+p['direction_scale']*torch.tensor(vector,dtype=a.dtype,device=device)
            y=diffusion.ddim_sample_loop(model,(len(a),len(features)),clip_denoised=p['clip_denoised'],model_kwargs={'z_mod':z},device=device,progress=False)
            pred.append(y.cpu().numpy());lat.append(z.cpu().numpy())
    outputs=[];save_matrix(out,'prediction.tsv',np.concatenate(pred),meta.query_id,features,'prediction_matrix',outputs)
    save_matrix(out,'semantic_latent.tsv',np.concatenate(lat),meta.query_id,[f'latent_{i+1}' for i in range(len(vector))],'latent_representation',outputs)
    _identity(meta,kind,out,outputs);_primary(out,outputs,[{'queries':len(meta),'features':len(features),'direction_scale':p['direction_scale'],'scope':'frozen_training_direction'}])
    return outputs,{'queries':len(meta),'features':len(features),'direction_l2':float(np.linalg.norm(vector)),'training_unit_overlap':0}

def stack(ids,p,out,kind):
    import anndata as ad
    import numpy as np
    from stack.models.core import StateICLModel
    m=model_manifest(ids,p,'stack_incontext');torch,device=model_device(p);features=text_axis(ids['features'])
    base=ad.read_h5ad(ids['context_object']);query=ad.read_h5ad(ids['query_object'])
    for x in (base,query):
        if not x.obs_names.is_unique or not x.var_names.is_unique or list(x.var_names)!=features or 'unit_id' not in x.obs:raise ValueError('Exact complete model genes and literal disjoint context/query identities required; no zero padding of missing genes')
        values=x.X.data if hasattr(x.X,'toarray') else np.asarray(x.X)
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('Actual nonnegative model-compatible observed input required')
    if set(base.obs_names)&set(query.obs_names) or set(base.obs.unit_id)&set(query.obs.unit_id):raise ValueError('Context and target identities/units overlap')
    if query.n_obs>p['maximum_cases'] or query.n_obs*query.n_vars>p['maximum_output_entries']:raise ValueError('In-context query exceeds fixed server budget')
    if m['preprocessing'].get('scale')!='raw_counts' or any(not np.allclose((x.X.data if hasattr(x.X,'toarray') else x.X)%1,0) for x in (base,query)):raise ValueError('This count-output branch requires the actual raw-count checkpoint preprocessing')
    ckpt=safe_state(ids['checkpoint'],torch)
    cfg=ckpt.get('hyper_parameters',{}).get('model_config')
    if not isinstance(cfg,dict) or cfg!=m.get('architecture'):raise ValueError('Exact original StateICL checkpoint architecture required; whole-model pickle is not accepted')
    model=StateICLModel(**cfg);state=ckpt['state_dict'];fixed={k[6:] if k.startswith('model.') else k:v for k,v in state.items()}
    if len(fixed)!=len(state):raise ValueError('Colliding native checkpoint prefixes')
    model.load_state_dict(fixed,strict=True);model.to(device).eval()
    with torch.inference_mode():
        y=model.get_incontext_prediction(base,query,str(ids['features']),mask_rate=p['mask_rate'],prompt_ratio=p['prompt_ratio'],context_ratio=p['context_ratio'],mode='predict',batch_size=p['batch_size'],num_workers=0,random_seed=p['seed'],show_progress=False)
    # At this pinned revision the API returns one aligned CSR prediction matrix,
    # not the four arrays returned by get_prediction or an inferred uncertainty.
    outputs=[];save_matrix(out,'prediction.tsv',y,list(query.obs_names),features,'prediction_matrix',outputs)
    meta=query.obs.copy();meta.insert(0,'query_id',list(query.obs_names));_identity(meta,kind,out,outputs)
    _primary(out,outputs,[{'queries':query.n_obs,'features':query.n_vars,'context_cells':base.n_obs,'scope':'context_conditioned_count_prediction'}])
    return outputs,{'queries':query.n_obs,'context_cells':base.n_obs,'unit_overlap':0,'features':len(features)}

def cellnavi(ids,p,out,kind,repo):
    import numpy as np
    import pandas as pd
    import anndata as ad
    from scipy import sparse
    import shutil
    m=model_manifest(ids,p,'cellnavi_drivers');torch,device=model_device(p);query=ad.read_h5ad(ids['query_object'])
    vocab=text_axis(ids['gene_vocabulary']);classes=text_axis(ids['class_order'])
    adjacency=pd.read_csv(ids['adjacency'],index_col=0);distance=pd.read_csv(ids['distance_graph'],index_col=0)
    genes=list(distance.columns)
    if not genes or list(distance.index)!=genes or list(adjacency.columns)!=genes or list(adjacency.index)!=genes or not set(genes)<=set(vocab) or not set(genes)<=set(query.var_names):raise ValueError('Native graph axes, vocabulary and actual observed genes differ; no fallback token assignment')
    for graph in (adjacency,distance):
        if not np.isfinite(graph.to_numpy()).all():raise ValueError('Nonfinite native graph')
    if (adjacency.to_numpy()<0).any() or (distance.to_numpy()<-1).any() or (distance.to_numpy()>9).any() or not np.allclose(distance.to_numpy()%1,0):raise ValueError('Native degree/attention graph domain differs')
    if not query.obs_names.is_unique or not query.var_names.is_unique or query.n_obs>p['maximum_cases'] or query.n_obs*len(classes)>p['maximum_output_entries']:raise ValueError('Exact bounded query scope required')
    if 'perturbation' not in query.obs or 'unit_id' not in query.obs or m.get('class_order_sha256')!=sha(ids['class_order']) or m.get('trained_class_count')!=len(classes) or not 1<=len(classes)<=2058:raise ValueError('Actual training class order, unit and observed perturbation metadata required')
    values=query.X.data if sparse.issparse(query.X) else query.X
    if not np.isfinite(values).all() or (values<0).any() or not np.allclose(values%1,0):raise ValueError('CellNavi original dataset path requires observed integer counts')
    if not set(query.obs.perturbation.astype(str))<=set(classes)|{'control'}:raise ValueError('Unknown observed class cannot be silently assigned a class index')
    # Author ValidationDataset reads a relative config. Stage selected data and
    # configuration in this fresh output, never write into the owned source repo.
    stage=out/'cellnavi_stage';stage.mkdir();work=stage/'tutorials';work.mkdir();data=stage/'data';data.mkdir()
    if 'control' in query.obs.perturbation.astype(str).values:raise ValueError('Select perturbed query cells explicitly; author validation excludes controls, never drop them silently')
    query=query.copy();query.obs['perturbation']=pd.Categorical(query.obs.perturbation,categories=classes)
    query.X=sparse.csr_matrix(query.X);query.write_h5ad(data/'query.h5ad')
    for role,name in [('gene_vocabulary','gene_name.txt'),('adjacency','adjacency.csv'),('distance_graph','distance.csv')]:shutil.copyfile(ids[role],data/name)
    write(stage/'config.json',{'dataset_dir':str(data),'test_data':'query.h5ad','adj_graph':'adjacency.csv','dist_graph':'distance.csv'})
    from cellnavi.model.finetune_model import FinetuneModel
    from cellnavi.data_provider.dataset import ValidationDataset
    previous=Path.cwd();os.chdir(work)
    try:ds=ValidationDataset()
    finally:os.chdir(previous)
    if list(ds._cell_name)!=list(query.obs_names):raise ValueError('Author loader changed query identities')
    model=FinetuneModel();model.load_state_dict(_state(safe_state(ids['checkpoint'],torch)),strict=True);model.to(device).eval();logits=[]
    with torch.inference_mode():
        for i in range(len(ds)):
            item={k:v.to(device) for k,v in ds[i].items()}
            # Original validation items already contain the single-query batch
            # dimension. Forward losses/accuracy are not validation evidence.
            z=model(item)['pred']
            if z.shape!=(1,2058):raise ValueError('Native CellNavi head dimensions changed')
            logits.append(z[0,:len(classes)].cpu().numpy())
    a=np.stack(logits);outputs=[];save_matrix(out,'driver_logits.tsv',a,list(query.obs_names),classes,'driver_logits',outputs)
    ranking=[]
    for i,name in enumerate(query.obs_names):
        for rank,j in enumerate(np.argsort(-a[i],kind='stable')[:min(p['top_k'],len(classes))]):ranking.append({'query_id':name,'unit_id':query.obs.unit_id.iloc[i],'driver':classes[j],'rank':rank+1,'logit':a[i,j],'meaning':'uncalibrated_model_driver_rank'})
    path=out/'driver_ranking.tsv';pd.DataFrame(ranking).to_csv(path,sep='\t',index=False);outputs.append((path,'driver_ranking'))
    meta=query.obs.copy();meta.insert(0,'query_id',list(query.obs_names));_identity(meta,kind,out,outputs)
    _primary(out,outputs,[{'queries':len(query),'trained_classes':len(classes),'native_head_slots':2058,'unmapped_head_slots_excluded_from_ranking':2058-len(classes)}])
    return outputs,{'queries':len(query),'trained_classes':len(classes),'literal_vocabulary_coverage':1.0}

def morphdiff(ids,p,out,kind,mode):
    import numpy as np
    import pandas as pd
    from omegaconf import OmegaConf
    from ldm.util import instantiate_from_config
    from ldm.models.diffusion.ddim import DDIMSampler
    m=model_manifest(ids,p,mode);torch,device=model_device(p);meta=metadata(ids)
    if len(meta)>p['maximum_cases']:raise ValueError('Generated image query exceeds explicit server budget')
    cfg=OmegaConf.load(ids['model_config'])
    if m.get('config_sha256')!=sha(ids['model_config']) or m.get('latent_downsample_factor')!=4 or len(m.get('image_channels',[]))!=5:raise ValueError('Reviewed five-channel MorphDiff config and factor-four geometry required')
    # The config is hash-bound reviewed model code, never an arbitrary target supplied by an external document.
    if OmegaConf.to_container(cfg.model,resolve=True)!=m.get('model_config'):raise ValueError('Model config differs from independently reviewed constructor tree')
    model=instantiate_from_config(cfg.model);model.load_state_dict(_state(safe_state(ids['checkpoint'],torch)),strict=True);model.to(device).eval();sampler=DDIMSampler(model)
    genes=np.load(ids['gene_condition'],allow_pickle=False)
    if genes.shape[0]!=len(meta) or list(genes.shape[1:])!=m.get('gene_condition_shape') or not np.isfinite(genes).all():raise ValueError('Actual fixed native gene-conditioning representation required')
    count=len(meta)*5*p['image_height']*p['image_width']
    if count>p['maximum_output_entries']:raise ValueError('Generated image tensor exceeds the declared server budget')
    source=None
    if mode=='morphdiff_image2image':
        source=np.load(ids['source_images'],allow_pickle=False)
        if source.shape!=(len(meta),5,p['image_height'],p['image_width']) or not np.isfinite(source).all() or source.min()<-1 or source.max()>1:raise ValueError('Real source image tensor must use the checkpoint five-channel [-1,1] scale')
    images=[]
    with torch.inference_mode(),model.ema_scope():
        for i in range(0,len(meta),p['batch_size']):
            n=min(p['batch_size'],len(meta)-i);g=torch.as_tensor(genes[i:i+n],dtype=torch.float32,device=device);c=model.get_learned_conditioning(g)
            uc=model.get_learned_conditioning(n*['']) if p['guidance_scale']!=1 else None
            if source is None:
                z,_=sampler.sample(S=p['steps'],conditioning=c,batch_size=n,shape=[4,p['image_height']//4,p['image_width']//4],verbose=False,unconditional_guidance_scale=p['guidance_scale'],unconditional_conditioning=uc,eta=p['eta'])
            else:
                init=torch.as_tensor(source[i:i+n],dtype=torch.float32,device=device);z0=model.get_first_stage_encoding(model.encode_first_stage(init))
                sampler.make_schedule(ddim_num_steps=p['steps'],ddim_eta=p['eta'],verbose=False)
                # strength=1 would index one past the DDIM schedule in the author API.
                t=min(int(p['strength']*p['steps']),p['steps']-1)
                z=z0 if t==0 else sampler.decode(sampler.stochastic_encode(z0,torch.full((n,),t,device=device,dtype=torch.long)),c,t,unconditional_guidance_scale=p['guidance_scale'],unconditional_conditioning=uc)
            a=((model.decode_first_stage(z)+1)/2).clamp(0,1).cpu().numpy()
            if a.shape!=(n,5,p['image_height'],p['image_width']):raise ValueError('Native decoded morphology channel/geometry mismatch')
            images.append(a)
    a=np.concatenate(images);outputs=[];path=out/'generated_images.npy';np.save(path,a,allow_pickle=False);outputs.append((path,'predicted_images'))
    rows=[]
    for i,name in enumerate(meta.query_id):
        for j,ch in enumerate(m['image_channels']):rows.append({'query_id':name,'channel':ch,'mean_intensity':float(a[i,j].mean()),'sd_intensity':float(a[i,j].std()),'fraction_clipped':float(((a[i,j]<=0)|(a[i,j]>=1)).mean())})
    path=out/'channel_summary.tsv';pd.DataFrame(rows).to_csv(path,sep='\t',index=False);outputs.append((path,'channel_summary'))
    _identity(meta,kind,out,outputs);_primary(out,outputs,[{'queries':len(meta),'channels':5,'height':p['image_height'],'width':p['image_width'],'images_are':'model_generated'}])
    return outputs,{'queries':len(meta),'channels':5,'fraction_at_display_bounds':float(((a<=0)|(a>=1)).mean())}
