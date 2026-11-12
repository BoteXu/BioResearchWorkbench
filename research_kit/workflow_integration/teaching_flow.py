"""Private end-to-end decision graph, not an automatic analysis or dispatcher."""
from pathlib import Path
import json,hashlib,re
HERE=Path(__file__).resolve().parent
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
def plan(request):
    policy=json.loads((HERE/'teaching_policy.json').read_text(encoding='utf8'));catalog={s['id']:s for s in policy['stages']}
    if request.get('public_upload') is not False:raise ValueError('Private workflow request required')
    chosen=request.get('stages')
    if chosen=='all':chosen=list(catalog)
    if not isinstance(chosen,list) or not chosen or len(chosen)!=len(set(chosen)) or set(chosen)-set(catalog):raise ValueError('Select unique declared workflow stages')
    channels=request.get('channels',{});checks=request.get('checks',{})
    if not isinstance(channels,dict) or not isinstance(checks,dict):raise ValueError('Explicit named channels and checks required')
    ordered=[];active=set()
    def visit(k):
        if k in active:raise ValueError('Cyclic stage dependencies')
        if k in ordered:return
        active.add(k)
        for parent in catalog[k]['requires']:visit(parent)
        active.remove(k);ordered.append(k)
    for k in chosen:visit(k)
    result=[]
    for k in ordered:
        s=catalog[k];missing=[c for c in s['required_channels'] if not isinstance(channels.get(c),dict) or not re.fullmatch('[a-f0-9]{64}',str(channels[c].get('source_sha256',''))) or not channels[c].get('source_locator')]
        qc=[]
        for i,text in enumerate(s['qc'],1):
            key=k+'__'+str(i);e=checks.get(key,{})
            # A plain PASS string or copied slide statement is not a QC receipt.
            state=e.get('state','UNASSESSED') if isinstance(e,dict) else 'INVALID'
            if state not in {'PASS','WARN','HOLD','NA','UNASSESSED'}:state='INVALID'
            if state in {'PASS','WARN'} and (not all(e.get(v) for v in ['source_sha256','evidence_locator','reviewer','scope']) or not re.fullmatch('[a-f0-9]{64}',str(e.get('source_sha256','')))):state='UNBOUND_DECLARATION'
            if state=='NA' and not e.get('reason'):state='UNEXPLAINED_NA'
            qc.append({'id':key,'question':text,'state':state,'evidence':e})
        result.append({**s,'selected_explicitly':k in chosen,'missing_channels':missing,'checks':qc,'stage_state':'HOLD' if missing or any(x['state'] not in {'PASS','WARN'} for x in qc) else 'READY_FOR_SEPARATE_METHOD_REVIEW','no_automatic_execution':True})
    return {'schema':'teaching-informed-workflow/1','policy_sha256':digest(policy),'request_sha256':digest(request),'source_deck_sha256':policy['source_deck_sha256'],'source_script_sha256':policy['source_script_sha256'],'stages':result,'state':'HOLD' if any(s['stage_state']=='HOLD' for s in result) else 'PREPARED_REQUIRES_SCIENTIFIC_AND_SERVER_ACCEPTANCE','scientific_validity':'NOT_ESTABLISHED','server_dispatch':False,'server_execution_authorized':False,'local_analysis':False,'public_upload':False}

def coverage():
    p=json.loads((HERE/'teaching_policy.json').read_text(encoding='utf8'));return {'version':p['version'],'stages':p['stages'],'source_deck_sha256':p['source_deck_sha256'],'source_script_sha256':p['source_script_sha256'],'scientific_backend_status':'NOT_RUN_THIS_UPGRADE','live_server_status':'NOT_PROBED_THIS_UPGRADE'}
