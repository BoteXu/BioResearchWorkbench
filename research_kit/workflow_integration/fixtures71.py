"""Non-scientific contract fixtures only: no raw data, reference results, fitting or server run."""
import copy
from server.analysis71 import contract,parameter_types
from server.method_contract71 import validate_parameters

def value(name,rule,offset=0):
    if 'enum' in rule:return rule['enum'][offset%len(rule['enum'])]
    kind=rule['type']
    if kind=='integer':return max(rule.get('minimum',1),20 if name in {'bootstraps','permutations','n_perms','simulations','stars_reps','null_permutations','donor_resamples','reference_bootstraps'} else 5)+offset
    if kind=='number':
        low=max(rule.get('minimum',0),rule.get('minimum_exclusive',0)+.001);high=rule.get('maximum',1 if low<1 else low+10);return low+(high-low)*(.25+.2*offset)
    return {'array':lambda:[] if not offset else ['FIXTURE_'+str(offset)],'boolean':lambda:bool(offset%2),'object':lambda:{'FIXTURE_STATE':['C1']},'string':lambda:'FIXTURE_'+str(offset),'contrast':lambda:{'groupTreatment':1.},'bins':lambda:4+offset}[kind]()

def params(key,registry):
    s=registry[key];p={n:value(n,r) for n,r in s['parameter_schema'].items()};p.update(analysis_id=key,implementation=s['implementation'],seed=17)
    if 'control'in p:p['control']='Control'
    if 'treatment'in p:p['treatment']='Treatment'
    if key=='colocalization':
        if p['trait1_type']=='cc':p['case_fraction1']=.3
        if p['trait2_type']=='cc':p['case_fraction2']=.3
    if 'time_group'in p:p['time_group']='none'
    candidates=[]
    for name in s['sensitivity_parameters']:
        for offset in (1,2,3):
            changed=value(name,s['parameter_schema'][name],offset)
            if changed==p[name]:continue
            q={**p,name:changed}
            try:parameter_types(q,s);validate_parameters(q,s)
            except (ValueError,KeyError):continue
            delta={name:changed}
            if delta not in candidates:candidates.append(delta)
    if len(candidates)<2:raise ValueError('Fixture needs two genuinely changed allowed parameter settings: '+key)
    p['sensitivity_variants']=[{'label':'alt1','parameters':candidates[0]},{'label':'alt2','parameters':candidates[1]}]
    return p
