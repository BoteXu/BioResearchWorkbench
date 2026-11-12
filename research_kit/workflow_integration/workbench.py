"""Private depth extension: plan server science and review real returned diagnostics."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
from acceptance import load,sha,selected,inspect_result

HERE=Path(__file__).resolve().parent

def _bridge_root():
    """Resolve only an explicitly selected private installation, never a shipped path."""
    import os
    candidate=os.environ.get('BIORESEARCH_BRIDGE_ROOT')
    config=HERE/'deployment.local.json'
    if not candidate and config.is_file():candidate=load(config).get('bridge_root')
    if not isinstance(candidate,str) or not candidate.strip():
        raise ValueError('Select an existing private bridge using BIORESEARCH_BRIDGE_ROOT or the ignored deployment.local.json; no machine path is shipped')
    selected_root=Path(candidate)
    if not selected_root.is_absolute():raise ValueError('The explicitly selected private bridge must use an absolute local path')
    selected_root=selected_root.resolve(strict=True)
    if not selected_root.is_dir() or not (selected_root/'bridge.py').is_file():raise ValueError('Selected existing bridge.py is missing; no installation or fallback is attempted')
    return str(selected_root)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def plan(path,out):
    path=Path(path).resolve();project=load(path)
    if project.get('example_only') is True or project.get('template_not_executable') is True:raise ValueError('Disabled examples are not reviewed scientific projects; supply actual inputs, QC and prespecified decisions first')
    profiles=load(HERE/'profiles.json');backend=project['backend']
    if backend not in profiles['backends']:raise ValueError('Choose exact backend')
    profile=profiles['backends'][backend]
    profile={k:(list(v) if isinstance(v,list) else v) for k,v in profile.items()}
    from server.completion_contracts import ROUTES as COMPLETION,QUALITY_METRICS,validate as validate_completion
    if backend in COMPLETION:
        extra=validate_completion(backend,project['parameters'],{r['id']:r for r in project['inputs']})
        profile['required_inputs']=extra['required_inputs'];profile['result_roles']=extra['required_roles']
        if not any(g.get('role')=='diagnostics' and g.get('field') in {'metrics.'+k for k in QUALITY_METRICS[backend]} and g.get('operator') in {'ge','le','eq'} and all(g.get(k) for k in ('definition','unit','threshold_basis')) for g in project.get('acceptance_rules',[])):
            raise ValueError('Prespecify a real numeric native QC/result criterion, not only completion or a source-hash flag')
    if backend in {'diablo_fit','snf_fusion'}:
        from server.native_teaching_contracts import validate as validate_views
        validate_views(backend,project['parameters'])
        profile['required_inputs']+=project['parameters']['view_ids']
    if backend=='xcms_preprocess':
        from server.native_teaching_contracts import validate as validate_raw
        validate_raw(backend,project['parameters'])
        profile['required_inputs']+=project['parameters']['raw_input_ids']
    if backend=='ml' and project['parameters'].get('shap') is not None:
        from server.shap_native import contract as shap_contract
        q=project['parameters'];shap_contract(q['shap'],q['train_units'],q['test_units'],q['features'])
        if not set(q['shap']['models'])<=set(q['models']):raise ValueError('SHAP can explain only actual models in the selected comparison')
        profile['result_roles']+=['shap_values','shap_summary','shap_identity','shap_diagnostics']
    if backend=='omics71':
        from server.analysis71 import contract
        specific=contract(project['parameters'],{r['id']:r for r in project['inputs']})
        if project.get('analysis_id')!=project['parameters']['analysis_id']:raise ValueError('Workflow branch differs from executable branch')
        profile['required_inputs']=specific['required_inputs']
        profile['required_parameters']+=specific['required_parameters']
        profile['result_roles']+=specific['required_roles']+specific.get('required_proof_roles',[])
        if not any(g.get('role')=='analysis_diagnostics' and str(g.get('field','')).startswith('0.metrics.') and all(g.get(k) for k in ('definition','unit','threshold_basis')) for g in project.get('acceptance_rules',[])):
            raise ValueError('Prespecify an actual primary numerical diagnostic criterion, not only variant count or success status')
    if backend=='r_omics':
        method=project['parameters'].get('method')
        if method not in profiles['r_methods']:raise ValueError('Unknown exact R method')
        specific=profiles['r_methods'][method]
        profile['required_inputs']+=specific['inputs'];profile['required_parameters']+=specific['parameters'];profile['result_roles']=specific['roles']
        if method=='MOFA2':profile['required_inputs']+=project['parameters']['view_ids']
    for key in profile['required_parameters']:
        if key not in project['parameters']:raise ValueError('Missing explicit analysis parameter: '+key)
    if backend in {'cnmf_programs','composition_sccoda','cellrank_multiview','perturbation_baselines'}:
        from server.teaching_contracts import validate_backend
        validate_backend(backend,project['parameters'])
    from server.native_teaching_contracts import PACKAGES,validate as validate_native
    if backend in PACKAGES:validate_native(backend,project['parameters'])
    if project.get('public_upload') is not False or project.get('server_execution_authorized') is not False:raise ValueError('Private plan only; dispatch is a separate explicit step')
    ids={r['id'] for r in project['inputs']}
    if len(ids)!=len(project['inputs']) or not set(profile['required_inputs'])<=ids:raise ValueError('Missing or duplicate scientific input roles')
    # Paths are server-relative and hashes belong to actual inputs, not a dummy local summary.
    import re
    for row in project['inputs']:
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,99}',str(row.get('id',''))):raise ValueError('Safe explicit input role ID required')
        name=row['path']
        if not isinstance(name,str) or ':' in name or '\\' in name or name.startswith('/') or any(s in ('','..','.') for s in name.split('/')):raise ValueError('Use server project-relative inputs')
        if not re.fullmatch('[a-f0-9]{64}',row.get('sha256','')):raise ValueError('Exact input checksum required')
    if not project.get('upstream_qc') or not project.get('statistical_plan') or not project.get('acceptance_rules'):
        raise ValueError('Substantive upstream QC, statistical plan and prespecified result criteria required')
    if not isinstance(project['statistical_plan'],dict) or any(not project['statistical_plan'].get(k) for k in ('estimand','independent_unit','missingness','multiplicity','sensitivity')):
        raise ValueError('A status string is not a statistical plan')
    import math
    rules=project['acceptance_rules']
    if not isinstance(rules,list) or any(not isinstance(g,dict) for g in rules):raise ValueError('Explicit structured output acceptance rules required')
    rule_ids=[]
    for gate in rules:
        if any(k not in gate for k in ['id','role','field','operator','bound','definition','unit','threshold_basis']):raise ValueError('Each result criterion needs an ID, actual output role/field, operator, bound, definition, unit and scientific basis')
        if any(not isinstance(gate[k],str) or not gate[k] for k in ['id','role','field','definition','unit','threshold_basis']) or any(not part for part in gate['field'].split('.')):raise ValueError('Invalid or empty output criterion field')
        if gate['role'] not in profile['result_roles'] or gate['operator'] not in {'eq','le','ge'}:raise ValueError('Acceptance rule must inspect a declared required output using a supported comparison')
        if gate['operator']!='eq' and (type(gate['bound']) not in (int,float) or not math.isfinite(gate['bound'])):raise ValueError('Numerical result cutoff must be finite, not boolean or text')
        if gate['operator']=='eq' and (type(gate['bound']) not in (str,int,float,bool) or isinstance(gate['bound'],float) and not math.isfinite(gate['bound'])):raise ValueError('Equality criterion requires a finite explicit scalar')
        if 'source_path' in gate and (not isinstance(gate['source_path'],str) or not gate['source_path'] or ':' in gate['source_path'] or '\\' in gate['source_path'] or gate['source_path'].startswith('/') or any(x in {'','..','.'} for x in gate['source_path'].split('/'))):raise ValueError('Explicit result criterion source must be a safe actual server-output relative path')
        rule_ids.append(gate['id'])
    if len(set(rule_ids))!=len(rule_ids):raise ValueError('Duplicate output acceptance IDs')
    resources=project.get('resource_budget',{})
    if type(resources.get('cpus')) is not int or resources['cpus']<1 or type(resources.get('gpus')) is not int or resources['gpus']<0:
        raise ValueError('Explicit server CPU/GPU resource budget required')
    if backend=='af3' and resources['gpus']<1:raise ValueError('AF3 inference requires an explicitly allocated server GPU')
    if project['parameters'].get('accelerator')=='gpu' and resources['gpus']<1:raise ValueError('Selected native GPU model requires an allocated server GPU')
    if project['parameters'].get('use_gpu') is True and resources['gpus']<1:raise ValueError('Selected legacy native GPU model requires an allocated server GPU')
    parameters=project['parameters']
    for key in ('paired','robust','run_data_pipeline','require_assigned_stereochemistry','weights_access_confirmed'):
        if key in parameters and type(parameters[key]) is not bool:raise ValueError('Explicit boolean parameter required: '+key)
    for key in ('threads','cpu','outer_folds','inner_folds','max_candidates','max_epochs','batch_size','samples_per_seed','num_recycles','stride','qc_pcs','qc_variable_features','minimum_units'):
        if key in parameters and (type(parameters[key]) is not int or parameters[key]<1):raise ValueError('Explicit positive integer budget required: '+key)
    if backend=='xcms_preprocess':
        from server.native_teaching_contracts import validate as validate_raw
        validate_raw(backend,project['parameters'])
        profile['required_inputs']+=project['parameters']['raw_input_ids']
    if backend=='ml' and (not isinstance(parameters.get('models'),dict) or 'baseline' not in parameters['models']):raise ValueError('Model comparison requires an explicit same-split baseline')
    if project.get('source_omics_plan'):
        binding=project['source_omics_plan'];source=selected(path.parent,binding['path'])
        if sha(source)!=binding['sha256']:raise ValueError('Source omics plan bytes changed')
        import sys
        bridge_root=_bridge_root()
        if bridge_root not in sys.path:sys.path.insert(0,bridge_root)
        import omics_workflows_ext
        original=omics_workflows_ext._validate_plan(load(source))
        if not original['plan_contract_consistent']:raise ValueError('Source omics plan is still structurally blocked')
        if project['statistical_plan']['estimand']!=original['design']['estimand'] or project['statistical_plan']['independent_unit']!=original['design']['biological_unit']:
            raise ValueError('Scientific run estimand/unit differs from the source workflow')
        if project.get('analysis_id') and project['analysis_id'] not in {r['id'] for r in original['analysis_routes']}:
            raise ValueError('Scientific extension was not selected in the reviewed source workflow')
    # Structural planning is not scientific approval: actual QC evidence is a mandatory predecessor.
    request={**project,'schema':'private-scientific-request/2','required_roles':profile['result_roles'],
             'server_execution_authorized':False,'submission_state':'not_submitted',
             'source_sha256':{p.name:sha(p) for p in (HERE/'server').glob('*') if p.is_file() and p.suffix in {'.py','.R','.json'}}}
    body=json.dumps(request,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf8')
    request['plan_sha256']=hashlib.sha256(body).hexdigest()
    out=Path(out);out.mkdir(parents=True,exist_ok=False);write(out/'server_request.private.json',request)
    import shutil
    shutil.copytree(HERE/'server',out/'server')
    write(out/'handoff.private.json',{'state':'prepared_not_submitted','command_argv':['python3','server/runtime.py','server_request.private.json','NEW_OUTPUT_DIR'],
      'required_before_dispatch':['current compute host','real upstream QC and statistics review','exact installed backend version','resource allocation','explicit dispatch'],
      'server_execution_authorized':False,'no_automatic_install':True,'unknown_submission_policy':'inspect_existing_receipts_never_retry'})
    return {'state':'prepared_not_submitted','backend':backend,'required_roles':profile['result_roles'],'scientific_backend_validation':'not_run'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=['coverage','plan','accept','crosslink','static-review','sequence-plan','sequence-fetch','af3-input-check','fasta-check','workflow71-plan','teaching-coverage','teaching-plan','figure-plan'])
    parser.add_argument('--request',type=Path);parser.add_argument('--receipt',type=Path);parser.add_argument('--root',type=Path);parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    try:
        if args.operation=='figure-plan':
            from figure_bridge import prepare as prepare_figure
            result=prepare(args.root,load(args.request))
        elif args.operation=='teaching-coverage':
            from teaching_flow import coverage
            result=coverage()
        elif args.operation=='teaching-plan':
            from teaching_flow import plan as teaching_plan
            result=teaching_plan(load(args.request))
        elif args.operation=='coverage':result=load(HERE/'profiles.json')
        elif args.operation=='plan':result=plan(args.request,args.out)
        elif args.operation=='accept':
            request=load(args.request);selection=request.pop('selected_return_files',None)
            if selection is None:raise ValueError('Provide selected_return_files in a separate acceptance request')
            result=inspect_result(selected(args.request.parent,request['scientific_request']),selected(args.request.parent,request['server_receipt']),args.root,HERE/'server',selection)
        elif args.operation=='crosslink':
            from cross_domain import audit
            result=audit(args.root,load(args.request))
        elif args.operation=='workflow71-plan':
            from workflow71 import audit_plan
            result=audit_plan(args.root,load(args.request))
        elif args.operation in {'sequence-plan','sequence-fetch'}:
            from sequence_af3 import sequence_plan
            result=sequence_plan(**load(args.request))
            if args.operation=='sequence-fetch':
                import sys
                existing=_bridge_root()
                if existing not in sys.path:sys.path.insert(0,existing)
                import bridge
                receipt=bridge.query_database(result['existing_bridge_query'],result['parameters'])
                result={'query_plan':result,'receipt':receipt,'state':'retrieved_requires_identity_version_review',
                        'private_sequence_uploaded':False,'new_client_or_mcp_created':False}
        elif args.operation=='af3-input-check':
            from sequence_af3 import audit_af3_input
            result=audit_af3_input(load(args.request),False)
        elif args.operation=='fasta-check':
            from sequence_af3 import audit_fasta
            r=load(args.request);result=audit_fasta(selected(args.root,r['path']),r['kind'],r['expected_ids'])
        else:
            rows=[]
            for path in HERE.rglob('*.py'):
                ast.parse(path.read_text(encoding='utf8'),filename=str(path));rows.append(path.relative_to(HERE).as_posix())
            result={'python_files_parsed':rows,'scientific_engines_executed':False,'R_runtime_validation':'not_run'}
        if args.out and args.operation!='plan':write(args.out,result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('state')=='HOLD' else 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'state':'HOLD','error':str(exc),'public_upload':False},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
