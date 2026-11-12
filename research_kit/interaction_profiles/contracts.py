"""Private interaction-profile planning. No scientific package imports or local calculation."""
from pathlib import Path
import json,hashlib,re,math,shutil
ROOT=Path(__file__).resolve().parent
METHODS={'score_fixed_pose':'fixed_pose_ligand_profile_similarity','align_profiles':'free_ligand_profile_alignment','shepherd2_generate':'native_shepherd2_interaction_conditioned_generation','prepare_reference_profiles':'server_reference_axis_preparation_for_reviewed_constraints'}
POST_METHODS={'paper_native_evaluation':'native_relaxation_and_independent_modality_evaluation','prepare_generated_identities':'computed_parent_groups_preserving_original_docking_state_and_coordinates'}
METHODS.update(POST_METHODS)
def read(f):return json.loads(Path(f).read_text(encoding='utf-8-sig'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def sha(f):
    h=hashlib.sha256()
    with Path(f).open('rb') as stream:
        for b in iter(lambda:stream.read(1048576),b''):h.update(b)
    return h.hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf8')).hexdigest()
def write(f,obj):
    with Path(f).open('x',encoding='utf8',newline='\n') as out:json.dump(obj,out,ensure_ascii=False,indent=2,allow_nan=False);out.write('\n')
def safe_path(v):return isinstance(v,str) and bool(v) and not v.startswith('/') and ':' not in v and '\\' not in v and all(p not in ('','.','..') for p in v.split('/'))
def selected(root,name):
    if not safe_path(name):raise ValueError('Exact project-relative selected file required')
    root=Path(root).resolve();f=(root/name).resolve(strict=True)
    if not f.is_relative_to(root) or not f.is_file():raise ValueError('Selected asset escapes approved project')
    return f
def sources():return {f.relative_to(ROOT).as_posix():sha(f) for f in sorted(ROOT.rglob('*')) if f.is_file() and (f.suffix=='.py' or f.name=='upstream_code.json') and '__pycache__' not in f.parts and 'tests' not in f.parts}
def validate(r):
    key=r['method'];p=r['parameters']
    if key not in METHODS:raise ValueError('Unknown fixed scientific method')
    if r.get('example_only') is True:raise ValueError('Disabled example is not a reviewed scientific project')
    if r.get('public_upload') is not False or r.get('server_execution_authorized') is not False or r.get('automatic_download') is not False:raise ValueError('Private planning only; no automatic download or dispatch')
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,70}',r.get('run_id','')):raise ValueError('Fresh safe run ID required')
    if r.get('node_role')!='compute' or not isinstance(r.get('expected_host'),str) or not r['expected_host']:raise ValueError('Current allocated compute host required')
    budget=r['resource_budget']
    if type(budget.get('cpus')) is not int or budget['cpus']<1 or type(budget.get('gpus')) is not int or budget['gpus']<0:raise ValueError('Actual positive CPU/nonnegative GPU allocation required')
    needed={'structure_manifest','software','context'}|({'checkpoint_manifest'} if key=='shepherd2_generate' else set());ids=[x['id'] for x in r['inputs']]
    if len(ids)!=len(set(ids)) or set(ids)!=needed:raise ValueError('Exact selected input roles required')
    for x in r['inputs']:
        if not safe_path(x['path']) or not re.fullmatch('[a-f0-9]{64}',x.get('sha256','')):raise ValueError('Actual selected input path and hash required')
    if key in POST_METHODS:
        from postanalysis_contracts import validate_parameters
        validate_parameters(r)
        return validate_run_rules(r)
    common={'device','seed','surface_points','probe_radius','esp_lambda','solvent','xtb_timeout','expected_xtb_sha256','expected_xtb_version','expected_versions','max_atoms','charge_sum_tolerance'}
    extra={'alignment_restarts','alignment_steps'} if key=='align_profiles' else {'n_samples','batch_size','denoise_steps','generated_formal_charge','add_atoms','add_pharms','composition_mode','profile_weights','min_valid_fraction','generation_options'} if key=='shepherd2_generate' else set()
    if set(p)!=common|extra:raise ValueError('Missing or unknown parameters; no implicit scientific decisions')
    for k in ('seed','surface_points','xtb_timeout','max_atoms','alignment_restarts','alignment_steps','n_samples','batch_size','denoise_steps'):
        if k in p and (type(p[k]) is not int or p[k]<(0 if k=='seed' else 1)):raise ValueError('Explicit nonnegative seed / positive integer budget required: '+k)
    if p['seed']>2147483646 or p['device'] not in ('cpu','cuda') or p['solvent'] not in ('water','dmso','methanol','chcl3'):raise ValueError('Unsupported explicit device/solvent/seed')
    if not 50<=p['surface_points']<=400:raise ValueError('Evaluation surface count is outside the pinned native ALPHA interpolation domain 50..400')
    for k in ('probe_radius','esp_lambda','charge_sum_tolerance'):
        if type(p[k]) not in (float,int) or not math.isfinite(p[k]) or p[k]<=0:raise ValueError('Positive finite method parameter required: '+k)
    if not re.fullmatch('[a-f0-9]{64}',p['expected_xtb_sha256']) or not isinstance(p['expected_xtb_version'],str) or not p['expected_xtb_version']:raise ValueError('Exact reviewed installed xTB binary/version required')
    required_versions={'numpy','scipy','torch','rdkit','open3d','shepherd-score'}|({'shepherd'} if key=='shepherd2_generate' else set())
    if not isinstance(p['expected_versions'],dict) or set(p['expected_versions'])!=required_versions or any(not isinstance(v,str) or not v for v in p['expected_versions'].values()):raise ValueError('All selected installed dependency versions must be explicit')
    budget=r['resource_budget']
    if type(budget.get('cpus')) is not int or budget['cpus']<1 or type(budget.get('gpus')) is not int or budget['gpus']<0 or p['device']=='cuda' and budget['gpus']<1:raise ValueError('Actual CPU/GPU allocation required')
    needed={'structure_manifest','software','context'}|({'checkpoint_manifest'} if key=='shepherd2_generate' else set());ids=[x['id'] for x in r['inputs']]
    if len(ids)!=len(set(ids)) or set(ids)!=needed:raise ValueError('Exact selected input roles required')
    for x in r['inputs']:
        if not safe_path(x['path']) or not re.fullmatch('[a-f0-9]{64}',x.get('sha256','')):raise ValueError('Actual selected input path and hash required')
    if key=='shepherd2_generate':
        if p['batch_size']>p['n_samples'] or type(p['generated_formal_charge']) is not int or any(type(p[k]) is not int for k in ('add_atoms','add_pharms')):raise ValueError('Generation budget / explicit charge / atom count contract invalid')
        if p['composition_mode'] not in ('single','default','conditional') or not isinstance(p['profile_weights'],list) or not p['profile_weights'] or any(type(v) not in (int,float) or not math.isfinite(v) for v in p['profile_weights']) or not any(v>0 for v in p['profile_weights']):raise ValueError('Explicit native single/profile-composition weights required')
        if p['composition_mode']=='single' and p['profile_weights']!=[1]:raise ValueError('Single-profile conditioning requires the exact native unit weight')
        if type(p['min_valid_fraction']) not in (int,float) or not math.isfinite(p['min_valid_fraction']) or not 0<p['min_valid_fraction']<=1:raise ValueError('Prespecified finite generated-molecule QC fraction required')
    if key=='shepherd2_generate':
        from generation_contracts import validate_options
        validate_options(p)
    return validate_run_rules(r)

def validate_run_rules(r):
    p=r['parameters'];variants=r.get('sensitivity_variants');seen=set()
    if not isinstance(variants,list) or len(variants)<2:raise ValueError('At least two actual seeded runs required; precision/sampling scope stays descriptive')
    for v in variants:
        if set(v)!={'label','seed'} or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,30}',v['label']) or v['label']=='primary' or v['label'] in seen or type(v['seed']) is not int or not 0<=v['seed']<=2147483646 or v['seed']==p['seed']:raise ValueError('Distinct explicit technical seeds required')
        seen.add(v['label'])
    if len({v['seed'] for v in variants})!=len(variants):raise ValueError('Duplicate technical seed')
    if not r.get('acceptance_rules'):raise ValueError('Prespecify actual measured QC fields and thresholds')
    for g in r['acceptance_rules']:
        if not all(g.get(k) for k in ('metric','unit','definition','threshold_basis')) or g.get('operator') not in ('ge','le','eq') or type(g.get('bound')) not in (int,float) or not math.isfinite(g['bound']):raise ValueError('Measured numerical acceptance contract required')
    return r
def prepare(r,out):
    validate(r);r={**r,'schema':'private-interaction-request/2','source_sha256':sources(),'submission_state':'NOT_SUBMITTED'};r['plan_sha256']=digest(r)
    out=Path(out);out.mkdir(parents=True,exist_ok=False);shutil.copytree(ROOT/'server',out/'server')
    for f in list(ROOT.glob('*.py'))+[ROOT/'upstream_code.json']:shutil.copy2(f,out/f.name)
    write(out/'request.private.json',r);write(out/'dispatch.private.json',{'state':'PREPARED_NOT_SUBMITTED','command_argv':['python3','server/runtime.py','request.private.json','FRESH_OUTPUT_DIRECTORY'],'automatic_download':False,'unknown_submission':'inspect_actual_receipts_never_retry','public_upload':False})
    return {'state':'PREPARED_NOT_SUBMITTED','method':r['method'],'scientific_runtime':'NOT_RUN_SERVER_UNAVAILABLE','public_upload':False}
