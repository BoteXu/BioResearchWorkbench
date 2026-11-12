"""Server-only evaluation/identity choices; validation uses the standard library only."""
import math,re
from contracts import safe_path
METHODS={'paper_native_evaluation':'native_relaxation_and_independent_modality_evaluation','prepare_generated_identities':'computed_parent_groups_preserving_original_docking_state_and_coordinates'}
IDENTITY_POLICY_FIELDS=('parent_policy','max_tautomers','max_transforms','tautomer_remove_sp3_stereo','tautomer_remove_bond_stereo','tautomer_reassign_stereo')
ISOTOPE_SCOPE='preserve_isotope_inventory_in_computational_grouping; original_docking_state_and_coordinates_unchanged'

def identity_policy(p):
    """Exact derived policy; the fixed isotope choice needs no additional request parameter."""
    result={k:p[k] for k in IDENTITY_POLICY_FIELDS}
    result.update(schema='computed-parent-policy/2',rdkit_version=p['expected_versions']['rdkit'],
        native_sha256={'rdchem':p['expected_rdchem_sha256'],'standardize':p['expected_standardize_sha256']},
        tautomer_remove_isotopic_hs=False,isotope_policy_scope=ISOTOPE_SCOPE,
        isotope_control_api='CleanupParameters.tautomerRemoveIsotopicHs=False; TautomerEnumerator(CleanupParameters)',
        uncharger={'canonicalOrder':True,'force':False,'protonationOnly':False},
        uncharging_scope='computational_grouping_only; permanent_charges_may_remain; not_physiological_protonation')
    return result
def finite(x,lo=None,hi=None):return type(x) in (int,float) and math.isfinite(x) and (lo is None or x>=lo) and (hi is None or x<=hi)
def validate_parameters(r):
    p=r['parameters'];method=r['method'];common={'seed','expected_versions','max_atoms'}
    if method=='paper_native_evaluation':
        fields=common|{'device','solvent','xtb_timeout_seconds','expected_xtb_sha256','expected_xtb_version','charge_sum_tolerance','condition','priority_policy','minimum_evaluable_fraction','workers','xtb_cores','max_native_npz_bytes'}
        versions={'numpy','pandas','scipy','torch','rdkit','open3d','shepherd-score'}
        if p.get('device')!='cpu' or type(p.get('workers')) is not int or p['workers']!=1:raise ValueError('Auditable native evaluation uses one existing server CPU worker')
        if p.get('condition') not in ('all','surface','esp','pharm') or p.get('priority_policy') not in ('origin_full_profile_mask','none'):raise ValueError('Explicit native evaluation condition and full-profile priority policy required')
        if p['priority_policy']!='none' and p['condition'] not in ('all','pharm'):raise ValueError('HP/LP Tversky requires native pharmacophore evaluation')
        for k in ('xtb_timeout_seconds','xtb_cores','max_native_npz_bytes'):
            if type(p.get(k)) is not int or p[k]<1:raise ValueError('Positive actual evaluation budget required: '+k)
        if p['xtb_cores']>r['resource_budget']['cpus']:raise ValueError('xTB threads exceed approved CPU allocation')
        if not finite(p.get('minimum_evaluable_fraction'),0,1) or not finite(p.get('charge_sum_tolerance'),0) or p['charge_sum_tolerance']==0:raise ValueError('Finite evaluability and charge criteria required')
        if p.get('solvent') not in ('water','dmso','methanol','chcl3'):raise ValueError('Explicit solvent required')
        if not re.fullmatch('[a-f0-9]{64}',p.get('expected_xtb_sha256','')) or not p.get('expected_xtb_version'):raise ValueError('Actual reviewed xTB identity required')
    else:
        fields=common|{'parent_policy','max_tautomers','max_transforms','tautomer_remove_sp3_stereo','tautomer_remove_bond_stereo','tautomer_reassign_stereo','expected_rdchem_sha256','expected_standardize_sha256','minimum_prepared_fraction','grouping_basis'};versions={'rdkit'}
        if p.get('parent_policy') not in ('state_graph','charge_preserving_tautomer','uncharged_tautomer'):raise ValueError('Explicit computational parent-grouping policy required')
        if not isinstance(p.get('grouping_basis'),str) or not p['grouping_basis'].strip():raise ValueError('Grouping rationale required; this does not predict physiological protonation')
        for k in ('max_tautomers','max_transforms'):
            if type(p.get(k)) is not int or not 1<=p[k]<=4294967295:raise ValueError('Positive bounded unsigned-integer tautomer enumeration budget required')
        for k in ('tautomer_remove_sp3_stereo','tautomer_remove_bond_stereo','tautomer_reassign_stereo'):
            if type(p.get(k)) is not bool:raise ValueError('Explicit tautomer stereo settings required')
        if not finite(p.get('minimum_prepared_fraction'),0,1):raise ValueError('Finite preparation fraction required')
        for k in ('expected_rdchem_sha256','expected_standardize_sha256'):
            if not re.fullmatch('[a-f0-9]{64}',p.get(k,'')):raise ValueError('Exact installed RDKit native binary identities required')
    if set(p)!=fields:raise ValueError('Missing or unsupported post-analysis parameters')
    if type(p['seed']) is not int or not 0<=p['seed']<=2147483646 or type(p['max_atoms']) is not int or p['max_atoms']<1:raise ValueError('Exact seed and atom budget required')
    if not isinstance(p['expected_versions'],dict) or set(p['expected_versions'])!=versions or any(not isinstance(v,str) or not v for v in p['expected_versions'].values()):raise ValueError('Exact versions required for all selected dependencies')
    if r['resource_budget']['gpus']!=0:raise ValueError('Post-analysis uses existing server CPU software')
    return r
def lineage_spec(spec,method):
    fields={'schema','origin_request','origin_request_sha256','origin_return_root','origin_receipt_sha256','selected_return_files','origin_variant','reference_id','candidate_ids'}
    if not isinstance(spec,dict) or set(spec)!=fields or spec['schema']!='private-generation-lineage-job/1':raise ValueError('Exact versioned lineage specification required')
    if not all(safe_path(spec[k]) for k in ('origin_request','origin_return_root')):raise ValueError('Origin artifacts must stay in selected server project')
    if any(not re.fullmatch('[a-f0-9]{64}',spec[k]) for k in ('origin_request_sha256','origin_receipt_sha256')):raise ValueError('Exact origin request and receipt hashes required')
    names=spec['selected_return_files']
    if not isinstance(names,list) or not names or len(names)!=len(set(names)) or any(not safe_path(x) for x in names):raise ValueError('Explicit unique bounded origin summary selection required')
    if not isinstance(spec['origin_variant'],str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,30}',spec['origin_variant']):raise ValueError('One actual source generation variant required')
    ids=spec['candidate_ids']
    if method=='paper_native_evaluation':
        if ids!=[] or not isinstance(spec['reference_id'],str) or not spec['reference_id']:raise ValueError('Evaluation covers all requested attempts against one explicit full reference; valid-only filtering is refused')
    elif spec['reference_id'] is not None or not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)) or any(not re.fullmatch('generated_[0-9]+',x) for x in ids):raise ValueError('Select explicit unique eligible candidates for identity preparation')
    return spec
