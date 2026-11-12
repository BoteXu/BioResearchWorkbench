"""Bounded fictional metadata and file-operation tests; never launch scientific engines."""
from pathlib import Path
from copy import deepcopy
import importlib.util,json,hashlib,subprocess,sys,tempfile,ast
R=Path(__file__).parent
sys.dont_write_bytecode=True
T=R/'toolkit' if (R/'toolkit').is_dir() else R/'revision/toolkit/molecular_workflow_v3'
tests=[]
def load(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def check(name,v):tests.append({'case':name,'passed':bool(v)});assert v,name
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audit=load('revised_audit',T/'quality/audit_project.py')
plan=load('plan_incremental',T/'incremental/plan_incremental.py');sys.modules['plan_incremental']=plan
rank=load('ranking',T/'incremental/compare_rankings.py')
def fill(x):
    if x is None:return 'DEMO'
    if isinstance(x,str) and '__FILL' in x:return 'DEMO'
    if isinstance(x,dict):return {k:fill(v) for k,v in x.items()}
    if isinstance(x,list):return [fill(v) for v in x]
    return x
with tempfile.TemporaryDirectory(prefix='private_contract_',dir=R/'qa') as tmp:
    w=Path(tmp);(w/'input.txt').write_text('Fictional fixture; no molecular coordinates.\n',encoding='utf8');(w/'evidence.txt').write_text('Metadata test evidence only. Not a scientific review.\n',encoding='utf8')
    p=fill(json.loads((T/'project/project.example.json').read_text(encoding='utf8')));p['main_engine']='amber'
    p['inputs']=[{'role':'fixture','path':'input.txt','sha256':sha(w/'input.txt')}]
    for g in p['scientific_reviews']:g['status']='passed';g['evidence']=[{'path':'evidence.txt','sha256':sha(w/'evidence.txt'),'bytes':(w/'evidence.txt').stat().st_size}]
    run=lambda x:audit.audit(x,w,True,True)
    a=run(p);check('complete_declared_metadata_passes_only_metadata_scope',a['metadata_ready'] and a['execution_allowed'] is False and a['scientific_validity']=='not_established')
    b=deepcopy(p);b['scientific_reviews'][0]['evidence']=[];check('empty_review_evidence_refused',not run(b)['metadata_ready'])
    b=deepcopy(p);b['scientific_reviews'][0]['evidence']='evidence.txt';check('unbound_legacy_evidence_refused',not run(b)['metadata_ready'])
    b=deepcopy(p);b['scientific_reviews'][0]['evidence'][0]['sha256']='0'*64;check('changed_review_evidence_refused',not run(b)['metadata_ready'])
    b=deepcopy(p);b['scientific_reviews'][0]['evidence'][0]['path']='../outside.txt';check('evidence_outside_selected_root_refused',not run(b)['metadata_ready'])
    b=deepcopy(p);b['schema_version']='2.0';check('legacy_ready_requires_explicit_migration',not run(b)['metadata_ready'])
    b=deepcopy(p);b['software']['engine_version']={};check('empty_software_identity_refused',not run(b)['metadata_ready'])
    b=deepcopy(p);b['scientific_reviews'][0]['status']='pending';check('pending_review_not_ready',not run(b)['metadata_ready'])
    b=deepcopy(p);b['inputs'][0]['sha256']='0'*64;check('changed_input_hash_refused',not run(b)['metadata_ready'])
    b=deepcopy(p);b['runs'].append(deepcopy(b['runs'][0]));check('duplicate_run_refused',not run(b)['metadata_ready'])
    (w/'project.json').write_text(json.dumps(p),encoding='utf8');(w/'report.json').write_text('KEEP',encoding='utf8')
    proc=subprocess.run([sys.executable,str(T/'quality/audit_project.py'),str(w/'project.json'),'--root',str(w),'--output',str(w/'report.json')],capture_output=True,text=True)
    check('project_report_does_not_overwrite',proc.returncode==2 and (w/'report.json').read_text()=='KEEP')
    proc=subprocess.run([sys.executable,str(T/'environment/environment_audit.py'),'--output',str(w/'report.json')],capture_output=True,text=True)
    check('environment_existing_report_rejected_before_probes',proc.returncode==2 and (w/'report.json').read_text()=='KEEP')
    wf={'schema_version':1,'project_id':'FIXTURE','tasks':[{'id':'A','kind':'metadata_fixture','entity_id':'E','inputs':{'text':{'path':'input.txt'}},'outputs':{'result':'result.txt'},'parameters':{},'software':{'version':{'nested':None}},'code':{'adapter':'input.txt'},'depends_on':[]}]}
    f=w/'workflow.json';f.write_text(json.dumps(wf),encoding='utf8');cfg,tasks,deps,order=plan.load_workflow(f,w)
    state=plan.load_state(None,'FIXTURE');r=plan.assess(cfg,tasks,deps,order,state,w,None)
    check('nested_unknown_software_identity_blocks_reuse_plan',r['tasks'][0]['status']=='blocked')
    wf['tasks'][0]['software']={'version':'fixture-1'};f.write_text(json.dumps(wf),encoding='utf8');cfg,tasks,deps,order=plan.load_workflow(f,w)
    (w/'result.txt').write_text('Existing fixture result; do not overwrite.\n',encoding='utf8');r=plan.assess(cfg,tasks,deps,order,state,w,None)
    check('existing_outputs_visible_without_dispatch_permission',r['tasks'][0]['existing_output_paths']==['result.txt'] and r['execution_authorized'] is False)
    entry=r['tasks'][0]
    review={'execution':{'log_path':'evidence.txt','run_id':'fixture_run','exit_code':0,'started_at':'2020-01-01T00:00:00Z','ended_at':'2020-01-01T00:01:00Z'},'checks':[{'name':'metadata_only','status':'passed','evidence':['evidence.txt']}]}
    (w/'draft.json').write_text(json.dumps(review),encoding='utf8');bound=plan.bind_review(tasks['A'],entry,'draft.json',w)
    check('binding_is_pending_not_scientific_acceptance',bound['status']=='pending' and bound['checks'][0]['status']=='pending')
    bound.update(status='accepted',reviewer='fixture_review_role',reviewed_at='2020-01-01T00:02:00Z');bound['checks'][0]['status']='passed';(w/'review.json').write_text(json.dumps(bound),encoding='utf8')
    rec=plan.record_review(tasks['A'],entry,'review.json',w);state['records']['A']=rec
    check('unchanged_exact_metadata_snapshots_reuse',plan.assess(cfg,tasks,deps,order,state,w,None)['tasks'][0]['status']=='reuse')
    (w/'evidence.txt').write_text('changed',encoding='utf8')
    check('changed_evidence_invalidates_reuse',plan.assess(cfg,tasks,deps,order,state,w,None)['tasks'][0]['status']=='run')
    bad=deepcopy(wf);bad['tasks'][0]['depends_on']=['A'];f.write_text(json.dumps(bad),encoding='utf8')
    try:plan.load_workflow(f,w);refused=False
    except plan.Invalid:refused=True
    check('dependency_cycle_refused',refused)
    bad=deepcopy(wf);bad['tasks'][0]['inputs']['text']['path']='../outside.txt';f.write_text(json.dumps(bad),encoding='utf8')
    try:plan.load_workflow(f,w);refused=False
    except plan.Invalid:refused=True
    check('project_path_escape_refused',refused)
    for engine in ['amber','gromacs']:
        out=w/engine;argv=[sys.executable,str(T/'md/make_md_inputs.py'),'--engine',engine,'--out',str(out),'--replicate','1','--base-seed','42','--production-segments','2']
        if engine=='amber':argv+=['--amber-mask',':1-5 & !@H=']
        proc=subprocess.run(argv,capture_output=True,text=True)
        check(engine+'_input_render_only',proc.returncode==0 and json.loads(proc.stdout)['simulation_run'] is False)
        m=json.loads((out/'STAGE_MANIFEST.json').read_text());check(engine+'_template_and_render_hashes_bound',all(sha(out/x['name'])==x['sha256'] for x in m['files']) and len(m['source_template_sha256'])==10)
        before=sha(out/'STAGE_MANIFEST.json');proc=subprocess.run(argv,capture_output=True,text=True)
        check(engine+'_existing_input_directory_preserved',proc.returncode!=0 and sha(out/'STAGE_MANIFEST.json')==before)
    proc=subprocess.run([sys.executable,str(T/'md/make_md_inputs.py'),'--engine','amber','--out',str(w/'no_mask'),'--replicate','1','--base-seed','42'],capture_output=True,text=True)
    check('amber_missing_mask_rejected_before_writing',proc.returncode!=0 and not (w/'no_mask').exists())
    snap={'schema_version':1,'snapshot_id':'old','comparison_key':'fixture','score_model':'arbitrary-model','score_name':'arbitrary-test-score','unit':'arbitrary','direction':'higher','rows':[{'parent_id':k,'status':'scored','value':v} for k,v in [('A',1),('B',2),('C',2)]]}
    (w/'old.json').write_text(json.dumps(snap));new=deepcopy(snap);new['snapshot_id']='new';new['rows'].append({'parent_id':'D','status':'scored','value':4});(w/'new.json').write_text(json.dumps(new));rr=rank.compare(w/'old.json',w/'new.json',1)
    check('common_member_ranking_not_library_insertion_artifact',rr['spearman_on_common_members']==1 and rr['old_top_count']==2)
    new['score_model']='changed-model';(w/'new.json').write_text(json.dumps(new))
    try:rank.compare(w/'old.json',w/'new.json',1);refused=False
    except plan.Invalid:refused=True
    check('mixed_score_models_refused_by_default',refused)
    rr=rank.compare(w/'old.json',w/'new.json',1,True);check('explicit_cross_model_rank_only_has_no_score_delta',all(x['score_delta_new_minus_old'] is None for x in rr['records']))
report={'state':'METADATA_AND_FILE_CONTRACT_TESTS_PASS','count':len(tests),'passed':sum(x['passed'] for x in tests),'tests':tests,'scientific_engines_executed':False,'molecular_data_analyzed':False,'server_backend_validated':False,'scope':'Fictional text metadata and input-template rendering only; imports reviewed statically before tests.'}
(R/'qa/regression_tests.private.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='tests'}))
