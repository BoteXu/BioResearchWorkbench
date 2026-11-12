"""Native CINEMA-OT effects and CellCap programs, with explicit scope and unit QC."""
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,anndata as ad
    from scipy import sparse
    np.random.seed(p['seed']);a=ad.read_h5ad(inputs['object']);outputs=[];diag={'mode':mode,'software_versions':p['software_versions'],'scientific_acceptance':'NOT_ESTABLISHED'}
    keys=[p['unit_key'],p['condition_key']]
    if not a.obs_names.is_unique or not a.var_names.is_unique or not set(keys)<=set(a.obs) or a.obs[keys].isna().any().any():raise ValueError('Unique observed cells/genes and actual independent-unit/condition metadata required')
    def values(x):return x.data if sparse.issparse(x) else np.asarray(x)
    def emit(frame,name,role):
        fn=out/(name+'.tsv');frame.to_csv(fn,sep='\t',index=True);outputs.append((fn,role))
    if mode=='cinemaot_effects':
        import pertpy as pt
        x=a.layers[p['expression_layer']]
        if p['expression_scale']!='log1p_normalized' or not np.isfinite(values(x)).all() or (values(x)<0).any():raise ValueError('Actual observed nonnegative log1p expression required; estimated effects are differences on this scale, not log2FC or counts')
        a.X=x.copy();ledger=[];completed=0
        for unit,positions in a.obs.groupby(p['unit_key'],observed=True,sort=False).indices.items():
            for target in p['treatments']:
                idx=positions[a.obs.iloc[positions][p['condition_key']].isin([p['control'],target]).to_numpy()];z=a[idx].copy();control=(z.obs[p['condition_key']]==p['control']).to_numpy();nctrl=int(control.sum());ntreated=int((~control).sum());number=len(ledger)
                row={'pair_index':number,'unit_id':str(unit),'target':target,'n_control':nctrl,'n_treated':ntreated}
                if min(nctrl,ntreated)<p['minimum_cells_per_arm']:ledger.append({**row,'state':'HOLD_INSUFFICIENT_OBSERVED_ARM'});continue
                rep=z.obsm[p['representation_key']]
                if p['preweight_label'] is not None and (p['preweight_label'] not in z.obs or z.obs[p['preweight_label']].isna().any()):raise ValueError('Native label-preweighting requires an actual complete observed annotation')
                if z.n_obs*z.n_vars>p['maximum_dense_expression_entries'] or nctrl*ntreated>p['maximum_coupling_entries']:raise ValueError('Native dense effect/matching computation exceeds the reviewed server task budget')
                if rep.shape[0]!=z.n_obs or rep.shape[1]<p['dimension'] or not np.isfinite(rep).all():raise ValueError('Finite reviewed cell-aligned PCA/latent representation of sufficient dimension required')
                effect=pt.tl.Cinemaot().causaleffect(z,pert_key=p['condition_key'],control=p['control'],return_matching=True,use_rep=p['representation_key'],dim=p['dimension'],thres=p['dependence_threshold'],smoothness=p['smoothness'],eps=p['solver_tolerance'],solver='Sinkhorn',preweight_label=p['preweight_label'],random_state=p['seed'])
                if not effect.obs_names.equals(z.obs_names[~control]) or not effect.var_names.equals(z.var_names):raise ValueError('Native CINEMA-OT treated-cell or gene identity differs')
                coupling=np.asarray(effect.obsm['ot']);mass=coupling.sum(1)
                if coupling.shape!=(ntreated,nctrl) or not np.isfinite(coupling).all() or (coupling<0).any() or (mass<=0).any():raise ValueError('Native counterfactual matching lacks positive, finite, correctly aligned mass')
                dense=z.X.toarray() if sparse.issparse(z.X) else np.asarray(z.X);expected=dense[~control]-(coupling/mass[:,None])@dense[control]
                actual=effect.X.toarray() if sparse.issparse(effect.X) else np.asarray(effect.X)
                error=float(abs(actual-expected).max())
                if not np.isfinite(actual).all() or error>p['effect_reconstruction_tolerance']:raise ValueError('Native effect values do not match their actual treated-minus-weighted-control definition')
                effect.uns['effect_scale']='Observed log1p expression difference, conditional on native OT assumptions; not measured single-cell pairing';effect.uns['matching_control_cell_ids']=list(z.obs_names[control]);fn=out/('cinemaot_effect_'+str(number)+'.h5ad');effect.write_h5ad(fn);outputs.append((fn,'counterfactual_effect_object'))
                emit(effect.obs[[p['unit_key'],p['condition_key']]],'cinemaot_treated_'+str(number),'effect_identity');emit(z.obs.loc[control,keys],'cinemaot_controls_'+str(number),'control_identity')
                emit(pd.DataFrame({'gene_id':z.var_names,'mean_conditional_effect':actual.mean(0)}),'cinemaot_mean_effect_'+str(number),'unit_effect_summary')
                ledger.append({**row,'state':'NATIVE_COMPLETED','maximum_effect_reconstruction_error':error});completed+=1
        write(out/'cinemaot_pair_qc.json',ledger);outputs.append((out/'cinemaot_pair_qc.json','pair_diagnostics'))
        if not completed:raise ValueError('No supported observed unit/condition contrast; retain missing-arm states instead of fabricating responses')
        diag.update(n_completed_pairs=completed,n_hold_pairs=len(ledger)-completed,causal_assumptions=p['causal_assumptions'],interpretation='Native maintained CINEMA-OT unweighted/label-preweighted Sinkhorn branch per actual independent unit and treatment; no experimental pairing, out-of-distribution response validation or gene-level hypothesis tests asserted')
    elif mode=='cellcap_programs':
        import torch,scvi,inspect
        from cellcap.scvi_module import CellCap
        from cellcap.model import CellCapModel
        for component,digest in [(CellCap,'cf8ebdc68190c016afbfe539fdbe5b92ef198b11045b65c4e53218d2b03e670d'),(CellCapModel,'1a1047ee90121fbc274165423d0b9a17009bd99357776445406705029cd7743f')]:
            if sha(inspect.getsourcefile(component))!=digest:raise ValueError('Installed CellCap source differs from the exact reviewed legacy implementation; review the installed version first')
        x=a.layers[p['count_layer']];v=values(x)
        if not np.isfinite(v).all() or (v<0).any() or (v!=np.floor(v)).any() or (np.asarray(x.sum(1)).ravel()==0).any():raise ValueError('Actual nonzero-library integer count layer required')
        if a.obs[p['unit_key']].nunique()<p['minimum_units']:raise ValueError('Insufficient actual independent-unit support')
        targets=p['target_order'];observed=set(a.obs[p['condition_key']])
        if observed!={p['control'],*targets}:raise ValueError('Prespecified target/control universe differs from actual observed single-condition assignments')
        design=np.column_stack([(a.obs[p['condition_key']]==target).to_numpy(float) for target in targets]);a.obsm['reviewed_CellCap_target']=design
        if p['covariate_key'] is None:
            covariate=np.zeros((a.n_obs,1));covariate_names=['structural_no_covariate_term']
        else:
            key=p['covariate_key']
            if key not in a.obs or a.obs[key].isna().any():raise ValueError('Actual complete declared technical covariate required')
            covariate_names=p['covariate_order']
            if set(covariate_names)!=set(a.obs[key]):raise ValueError('Literal observed covariate categories/order differ')
            covariate=np.column_stack([(a.obs[key]==name).to_numpy(float) for name in covariate_names])
        a.obsm['reviewed_CellCap_covariate']=covariate;scvi.settings.seed=p['seed'];torch.manual_seed(p['seed'])
        CellCap.setup_anndata(a,layer=p['count_layer'],target_key='reviewed_CellCap_target',covar_key='reviewed_CellCap_covariate')
        model=CellCap(a,n_hidden=p['n_hidden'],n_latent=p['n_latent'],n_layers=p['n_layers'],dropout_rate=p['dropout_rate'],n_drug=len(targets),n_prog=p['n_programs'],n_covar=covariate.shape[1],n_head=p['n_heads'],lamda=p['adversarial_weight'],ard_kl_weight=p['ard_weight'],rec_weight=p['reconstruction_weight'],kl_weight=p['kl_weight'])
        # Upstream random cell split is used for optimizer monitoring only. It is
        # explicitly not accepted as independent-donor predictive validation.
        model.train(max_epochs=p['max_epochs'],batch_size=p['batch_size'],use_gpu=p['use_gpu'],train_size=p['optimization_train_fraction'],validation_size=1-p['optimization_train_fraction'],lr=p['learning_rate'],early_stopping=p['early_stopping'],save_best=True,check_val_every_n_epoch=1)
        basal=np.asarray(model.get_latent_embedding(a,batch_size=p['batch_size']));usage=np.asarray(model.get_h_attn(a,batch_size=p['batch_size']));relevance=np.asarray(model.get_h());response=np.asarray(model.get_resp_loadings());decoder=np.asarray(model.get_loadings())
        if basal.shape!=(a.n_obs,p['n_latent']) or usage.shape!=(a.n_obs,p['n_programs']) or relevance.shape!=(len(targets),p['n_programs']) or response.shape!=(p['n_programs'],p['n_latent']) or decoder.shape!=(a.n_vars,p['n_latent']) or any(not np.isfinite(z).all() for z in [basal,usage,relevance,response,decoder]):raise ValueError('Native CellCap program, latent, observation or gene dimensions fail numerical/identity QC')
        programs=['program_'+str(i+1) for i in range(p['n_programs'])]
        emit(pd.DataFrame(basal,index=a.obs_names),'cellcap_basal','basal_representation');emit(pd.DataFrame(usage,index=a.obs_names,columns=programs),'cellcap_usage','program_usage');emit(pd.DataFrame(relevance,index=targets,columns=programs),'cellcap_perturbation_relevance','program_relevance');emit(pd.DataFrame(decoder@response.T,index=a.var_names,columns=programs),'cellcap_decoder_projection','program_gene_projection')
        a.obsm['CellCap_basal']=basal;a.obsm['CellCap_program_usage']=usage;fn=out/'cellcap_result.h5ad';a.write_h5ad(fn);outputs.append((fn,'processed_object'));model.save(out/'cellcap_model',overwrite=False)
        for name,frame in model.history.items():emit(pd.DataFrame(frame),'cellcap_training_'+name,'training_history')
        for fn in (out/'cellcap_model').rglob('*'):
            if fn.is_file():outputs.append((fn,'model_checkpoint'))
        diag.update(n_cells=a.n_obs,n_units=a.obs[p['unit_key']].nunique(),target_order=targets,covariate_order=covariate_names,n_programs=p['n_programs'],validation_scope=p['validation_scope'],interpretation='Descriptive native CellCap program fit with random-cell optimizer monitoring only; no independent-unit validation. Decoder projections are model weights, not measured gene effects or causal programs; basal mixing alone does not establish QC')
    else:raise ValueError('Unknown native response program route')
    write(out/'native_diagnostics.json',diag);outputs.append((out/'native_diagnostics.json','diagnostics'));write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'));return outputs
