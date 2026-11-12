"""Pure source contracts only. No model import, fit or numerical inference."""
import copy,math

def cpa_dose_string(value,targets):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0 or not isinstance(targets,list) or not targets:raise ValueError('Finite nonnegative dose and explicit targets required')
    if any(not isinstance(g,str) or not g or '+' in g for g in targets) or len(set(targets))!=len(targets):raise ValueError('Ambiguous CPA perturbation labels')
    return '+'.join([str(float(value))]*len(targets))

def cpa_setup_contract(saved,evidence,targets,pert_encoder,covar_encoder):
    if not isinstance(saved,dict):raise ValueError('Actual persisted CPA registry setup arguments required')
    setup=copy.deepcopy(saved)
    for key in ('perturbation_key','dosage_key','control_group'):
        if not setup.get(key) or setup[key]!=evidence.get(key):raise ValueError('CPA persisted registry differs from reviewed training evidence: '+key)
    if setup.get('layer') is not None or any(setup.get(k) is not None for k in ('deg_uns_key','deg_uns_cat_key','smiles_key')):raise ValueError('This X-only genetic CPA adapter does not reconstruct DEG-mask or chemical-SMILES registry fields')
    if type(setup.get('max_comb_len')) is not int or len(targets)>setup['max_comb_len']:raise ValueError('Perturbation combination exceeds checkpoint architecture')
    control=setup['control_group'];vocabulary=set(pert_encoder)-{'<PAD>',control}
    if vocabulary!=set(evidence.get('perturbation_vocabulary',[])) or not set(targets)<=vocabulary:raise ValueError('Checkpoint perturbation encoder differs from declared training vocabulary')
    if set(covar_encoder)!=set(evidence.get('covariate_support',{})):raise ValueError('Every actual CPA categorical/batch covariate needs a reviewed support domain')
    for name,allowed in evidence['covariate_support'].items():
        if not allowed or not set(map(str,allowed))<=set(map(str,covar_encoder[name])):raise ValueError('Declared CPA covariate support exceeds checkpoint encoder')
    # Upstream setup can append batch_key to the caller list; keep each query independent.
    batch=setup.get('batch_key');setup['categorical_covariate_keys']=[k for k in dict.fromkeys(setup.get('categorical_covariate_keys') or []) if k!=batch]
    if set(setup['categorical_covariate_keys']+([batch] if batch else []))!=set(covar_encoder):raise ValueError('Persisted categorical axes and model encoders disagree')
    return setup

def scgpt_architecture_contract(config):
    if config.get('explicit_zero_prob') is not False:raise ValueError('Explicit-zero sampling models need a separately reviewed Monte Carlo adapter')
    if config.get('pert_pad_id')!=2:raise ValueError('Perturbation flag 0/1 and padding flag 2 must be distinct')
    if type(config.get('d_model')) is not int or type(config.get('nhead')) is not int or config['nhead']<1 or config['d_model']%config['nhead']:raise ValueError('scGPT embedding/head dimensions are incompatible')
