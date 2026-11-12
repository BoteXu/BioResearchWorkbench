"""Native BATCHIE sparse-combination posterior, masked outcomes stay unknown."""
import inspect
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd,arviz as az
    from batchie.data import Screen,ExperimentSpace
    from batchie.core import ThetaHolder
    from batchie.models.sparse_combo import SparseDrugCombo
    from batchie.sampling import sample
    if sha(inspect.getsourcefile(SparseDrugCombo))!='23e583ec1b025257b09dc390caea074d5975e71503c0cc517d48410ce11b0716' or sha(inspect.getsourcefile(Screen))!='758e72bbf0882d941317014e8f994a465b57a8f819b278fef427ce574fdf727c':raise ValueError('Native BATCHIE model/data source differs from exact primary review')
    d=pd.read_csv(inputs['screen_table'],dtype=str,keep_default_na=False);keys=['row_id','sample_id','plate_id','drug1','dose1','drug2','dose2','observed','viability',p['unit_key']]
    if not set(keys)<=set(d) or not len(d) or len(d)>p['maximum_experiments'] or d.row_id.duplicated().any() or (d[[k for k in keys if k!='viability']]=='').any().any():raise ValueError('Bounded actual complete row/sample/plate/drug/dose/biological-unit identities required')
    mask=d.observed.map({'true':True,'false':False})
    if mask.isna().any() or not mask.any() or mask.all():raise ValueError('Actual explicit observed/unobserved flags and both measured/candidate rows required')
    values=pd.to_numeric(d.viability,errors='coerce').to_numpy();mask=mask.to_numpy(bool)
    if not np.isfinite(values[mask]).all() or ((values[mask]<0)|(values[mask]>1)).any() or np.isfinite(values[~mask]).any():raise ValueError('Observed viability is an actual 0-1 fraction; candidate outcomes must remain missing, never hidden ground truth or inferred zero')
    doses=d[['dose1','dose2']].to_numpy(float)
    if not np.isfinite(doses).all() or (doses<0).any():raise ValueError('Finite actual nonnegative doses in one explicit unit required')
    if d.groupby('sample_id')[p['unit_key']].nunique().max()!=1 or d.groupby(p['unit_key']).sample_id.nunique().max()!=1:raise ValueError('Native sample axis must bind one-to-one to actual independent experimental units in this route')
    if d.loc[mask,p['unit_key']].nunique()<p['minimum_units']:raise ValueError('Insufficient observed independent-unit support')
    # One native model supports one/two treatments. Native control slots remain
    # explicit; unobserved zero below is a masked serialization placeholder only.
    names=d[['drug1','drug2']].to_numpy(str);serialized=np.where(mask,values,0.)
    screen=Screen(treatment_names=names,treatment_doses=doses,sample_names=d.sample_id.to_numpy(str),plate_names=d.plate_id.to_numpy(str),observations=serialized,observation_mask=mask,control_treatment_name=p['control_treatment_name'])
    observed=screen.subset_observed();space=ExperimentSpace.from_screen(screen)
    if space.n_unique_samples!=d.sample_id.nunique() or observed.size!=int(mask.sum()):raise ValueError('Native observation mask/sample identity differs')
    if not np.array_equal(screen.sample_names,d.sample_id.to_numpy(str)) or not np.array_equal(screen.plate_names,d.plate_id.to_numpy(str)) or not np.array_equal(screen.treatment_names,names) or not np.array_equal(screen.treatment_doses,doses) or not np.array_equal(screen.observation_mask,mask):raise ValueError('Native screen changed/reordered actual experiment identities or measurement flags')
    outputs=[];chains=[];alpha=[];precision=[];seedseq=np.random.SeedSequence(p['seed']).spawn(p['n_chains'])
    if p['n_chains']*p['posterior_draws']*screen.size>p['maximum_prediction_entries']:raise ValueError('Native posterior prediction exceeds the explicit reviewed server task budget')
    for chain_index in range(p['n_chains']):
        # The preserved legacy implementation uses global np.random instead of
        # the wrapper RNG. Explicit independent global streams are therefore
        # bound in addition to the author's sampling wrapper stream.
        global_seed=int(seedseq[chain_index].generate_state(1)[0]);np.random.seed(global_seed)
        model=SparseDrugCombo(experiment_space=space,n_embedding_dimensions=p['n_latent'],predict_interactions=False);model.add_observations(observed);holder=ThetaHolder(n_thetas=p['posterior_draws']);sample(model,holder,seed=p['seed'],n_chains=p['n_chains'],chain_index=chain_index,n_burnin=p['burnin'],thin=p['thin'],progress_bar=False)
        if len(holder.thetas)!=p['posterior_draws']:raise ValueError('Actual native posterior draw count differs')
        prediction=np.stack([theta.predict_viability(screen) for theta in holder.thetas]);chains.append(prediction);alpha.append([theta.alpha for theta in holder.thetas]);precision.append([theta.precision for theta in holder.thetas]);fn=out/('batchie_chain_'+str(chain_index)+'.h5');holder.save_h5(str(fn));outputs.append((fn,'posterior_checkpoint'))
    draws=np.stack(chains)
    if draws.shape!=(p['n_chains'],p['posterior_draws'],screen.size) or not np.isfinite(draws).all() or ((draws<0)|(draws>1)).any():raise ValueError('Native posterior viability dimensions/finite/probability QC failed')
    inference=az.from_dict(posterior={'viability_mean':draws,'alpha':np.asarray(alpha),'precision':np.asarray(precision)});rhat=az.rhat(inference,method='rank');ess=az.ess(inference,method='bulk');rvalues=np.concatenate([v.to_numpy().ravel() for v in rhat.data_vars.values()]);evalues=np.concatenate([v.to_numpy().ravel() for v in ess.data_vars.values()]);assessed=np.isfinite(rvalues).all() and np.isfinite(evalues).all();passed=bool(assessed and max(rvalues)<=p['maximum_rhat'] and min(evalues)>=p['minimum_ess'])
    table=d.copy();table['posterior_mean_viability']=draws.mean((0,1));table['posterior_q05_viability']=np.quantile(draws,.05,axis=(0,1));table['posterior_q95_viability']=np.quantile(draws,.95,axis=(0,1));table['posterior_sd_of_mean_viability']=draws.std((0,1),ddof=1);table.to_csv(out/'batchie_predictions.tsv',sep='\t',index=False)
    np.savez_compressed(out/'batchie_posterior_predictions.npz',viability=draws,row_ids=d.row_id.to_numpy(str));outputs.extend([(out/'batchie_predictions.tsv','combination_predictions'),(out/'batchie_posterior_predictions.npz','posterior_predictions')]);inference.to_netcdf(out/'batchie_posterior.nc');outputs.append((out/'batchie_posterior.nc','posterior_diagnostics_object'))
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_observed':int(mask.sum()),'n_unobserved':int((~mask).sum()),'n_units':d[p['unit_key']].nunique(),'mcmc_qc_assessed':bool(assessed),'mcmc_qc_pass':passed,'maximum_rhat':float(max(rvalues)) if assessed else None,'minimum_bulk_ess':float(min(evalues)) if assessed else None,'unobserved_outcomes_remain_unknown':True,'dose_unit':p['dose_unit'],'scientific_acceptance':'NOT_ESTABLISHED','compatibility_note':'Explicit distinct global NumPy seeds accompany native wrapper seeds because preserved legacy steps use global RNG. Native observations/model logits are clipped to 0.01-0.99; observed measurements are retained unchanged.','interpretation':'Native BATCHIE SparseDrugCombo viability posterior only. Credible intervals describe the model conditional mean, not a new biological replicate or observational prediction interval. MCMC diagnostics of predicted means/alpha/precision are required but not full posterior convergence or independent validation. No DBAL plate ranking, wet-lab dispatch, drug synergy or clinical efficacy asserted.'});outputs.append((out/'diagnostics.json','diagnostics'));write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
