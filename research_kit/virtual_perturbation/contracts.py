"""Private perturbation contracts. Standard library only; no scientific execution."""
from pathlib import Path
import hashlib,json,math,re

ROOT=Path(__file__).resolve().parent
STATE='NOT_RUN_SERVER_UNAVAILABLE'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def write(path,value):
    with Path(path).open('x',encoding='utf8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()

def relative(root,name,directory=False):
    if not isinstance(name,str) or not name or ':' in name or '\\' in name or any(v in ('','.','..') for v in name.split('/')):raise ValueError('Use an exact project-relative path')
    base=Path(root).resolve();p=(base/name).resolve(strict=True)
    if not p.is_relative_to(base) or (not p.is_dir() if directory else not p.is_file()):raise ValueError('Selected file leaves project or is missing')
    return p

def catalog():return read(ROOT/'catalog.json')

def finite(x):
    if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('Finite numerical value required')
    return x

def strings(value,name,minimum=1):
    if not isinstance(value,list) or len(value)<minimum or any(not isinstance(x,str) or not x.strip() for x in value) or len(value)!=len(set(value)):raise ValueError('Unique explicit string list required: '+name)

def validate(project):
    methods=catalog()['methods'];key=project['method'];spec=methods[key];p=project['parameters']
    if project.get('public_upload') is not False or project.get('server_execution_authorized') is not False:raise ValueError('Private preparation only; dispatch remains explicit')
    if project.get('measurement_state')!='predicted':raise ValueError('A virtual perturbation is predicted, never observed evidence')
    if project.get('example_only') is True:raise ValueError('Example configurations contain no actual server evidence; replace placeholders and review real inputs first')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,70}',project.get('run_id','')):raise ValueError('Safe fresh run ID required')
    ids=[r['id'] for r in project['inputs']]
    if len(set(ids))!=len(ids) or not set(spec['inputs']+['context','qc_receipt','qc_measurements'])<=set(ids):raise ValueError('Missing or duplicate explicit input roles')
    for r in project['inputs']:
        if not re.fullmatch('[a-f0-9]{64}',r.get('sha256','')):raise ValueError('Actual input SHA256 required')
        name=r['path']
        if not isinstance(name,str) or not name or ':' in name or '\\' in name or any(v in ('','.','..') for v in name.split('/')):raise ValueError('Input paths must stay server-project-relative')
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,99}',r['id']):raise ValueError('Invalid input role')
    common={'expected_package_version','expected_backend_code_sha256','ko_genes','evaluation_units','seed'}
    if set(p)!=set(spec['parameters'])|common:raise ValueError('Missing or unknown method parameters; no implicit defaults')
    strings(p['ko_genes'],'ko_genes');strings(p['evaluation_units'],'evaluation_units')
    if type(p['seed']) is not int or not isinstance(p['expected_package_version'],str) or not p['expected_package_version']:raise ValueError('Exact installed package version and integer seed required')
    if not re.fullmatch('[a-f0-9]{64}',p['expected_backend_code_sha256']):raise ValueError('Review and bind the actual existing server package-code fingerprint')
    for name,rule in spec['parameters'].items():
        value=p[name];kind=rule['type']
        if kind=='integer' and type(value) is not int:raise ValueError('Integer required: '+name)
        if kind=='number':finite(value)
        if kind=='boolean' and type(value) is not bool:raise ValueError('Boolean required: '+name)
        if kind=='strings':strings(value,name,rule.get('min_items',1))
        if kind=='string' and (not isinstance(value,str) or not value):raise ValueError('String required: '+name)
        if 'minimum' in rule and value<rule['minimum']:raise ValueError('Below method bound: '+name)
        if 'maximum' in rule and value>rule['maximum']:raise ValueError('Above method bound: '+name)
        if 'enum' in rule and value not in rule['enum']:raise ValueError('Unsupported method choice: '+name)
    budget=project['resource_budget']
    if type(budget.get('cpus')) is not int or budget['cpus']<1 or type(budget.get('gpus')) is not int or budget['gpus']<0:raise ValueError('Explicit server resource allocation required')
    for name in ('cores','nproc'):
        if name in p and p[name]>budget['cpus']:raise ValueError('Method exceeds server CPU allocation')
    if p.get('device')=='cuda' and budget['gpus']<1:raise ValueError('CUDA needs an allocated GPU')
    if key=='geneformer' and budget['gpus']<1:raise ValueError('The reviewed native Geneformer perturbation path requires an allocated GPU; CPU compatibility has not been established')
    gates=project.get('acceptance_rules',[])
    if not gates:raise ValueError('Prespecify actual measured scientific diagnostics and thresholds')
    for gate in gates:
        if not all(gate.get(k) for k in ('variant','metric','definition','threshold_basis','unit')) or gate.get('operator') not in ('ge','le','eq'):raise ValueError('Define each numerical acceptance criterion, unit and threshold basis')
        finite(gate['bound'])
    if key=='bulk_virtual_ko':
        strings(p['training_units'],'training_units',p['min_training_units'])
        if set(p['training_units'])&set(p['evaluation_units']):raise ValueError('Training and evaluation donors overlap')
        if set(p['ko_genes'])&set(p['control_genes']):raise ValueError('Control targets overlap requested KO')
        if p['n_features']<=len(set(p['ko_genes']+p['control_genes'])):raise ValueError('Frozen feature budget too small')
    if key=='celloracle' and not p['clip_to_training_range']:raise ValueError('Out-of-support CellOracle extrapolation is disabled')
    if key=='gears' and any('_' in g for g in p['ko_genes']):raise ValueError('GEARS joins labels with underscores; ambiguous target identity is unsupported')
    if key=='gears' and p['max_control_cells']<p['min_control_cells']:raise ValueError('GEARS minimum exceeds selected control-cell budget')
    if key in ('cpa','scgpt') and p['max_control_cells']<max(p['min_control_cells'],p['min_cells_per_unit']):raise ValueError('Expression predictor control budget is below reviewed donor coverage')
    if key=='maboss' and (not re.fullmatch('[a-f0-9]{64}',p['expected_binary_sha256']) or p['time_tick']>=p['max_time']):raise ValueError('Exact MaBoSS binary identity and adequate time grid required')
    if key=='maboss' and not set(p['ko_genes'])<=set(p['output_nodes']):raise ValueError('MaBoSS target nodes must remain in the output to verify actual KO clamping')
    if key=='geneformer' and p['max_cells_per_unit']<p['min_cells_per_unit']:raise ValueError('Geneformer cell budget is below prespecified coverage')
    comparisons=project.get('sensitivity_variants',[])
    if len(comparisons)<2:raise ValueError('At least two distinct real method/seed reruns required')
    labels=set();deltas=set()
    for alt in comparisons:
        if set(alt)!={'label','parameters'} or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,40}',alt['label']) or alt['label']=='primary' or alt['label'] in labels:raise ValueError('Unique safe sensitivity label required')
        delta=alt['parameters']
        if not delta or not set(delta)<=set(spec['sensitivity_parameters']) or all(p[k]==v for k,v in delta.items()):raise ValueError('A sensitivity must change an approved method parameter or random seed')
        token=digest(delta)
        if token in deltas:raise ValueError('Duplicate sensitivity configuration')
        labels.add(alt['label']);deltas.add(token)
        changed={**project,'parameters':{**p,**delta},'sensitivity_variants':[]}
        # Validate the alternate parameter bounds without recursively requiring more alternates.
        _validate_alternate(changed,spec)
        if key in ('cpa','scgpt') and changed['parameters']['max_control_cells']<max(p['min_control_cells'],p['min_cells_per_unit']):raise ValueError('Alternate control budget fails required coverage')
        if key=='bulk_virtual_ko' and set(delta)=={'dpi_threshold'} and changed['parameters']['pruning']=='none':raise ValueError('Inactive DPI threshold is not a real sensitivity rerun')
        if key=='metabolic_gene_deletion' and set(delta)<=set(('room_delta','room_epsilon')) and changed['parameters']['solution_method']!='linear_ROOM':raise ValueError('ROOM parameters do not change an FBA/MOMA model')
    return spec

def _validate_alternate(project,spec):
    p=project['parameters']
    for k,v in p.items():
        if k=='seed':
            if type(v) is not int:raise ValueError('Integer seed required')
            continue
        if k not in spec['parameters']:continue
        rule=spec['parameters'][k]
        if rule['type']=='integer' and type(v) is not int:raise ValueError('Integer alternate required')
        if rule['type']=='number':finite(v)
        if rule['type']=='string' and (not isinstance(v,str) or not v):raise ValueError('Explicit string alternate required')
        if rule['type']=='boolean' and type(v) is not bool:raise ValueError('Boolean alternate required')
        if 'enum' in rule and v not in rule['enum']:raise ValueError('Unsupported alternate method')
        if 'minimum' in rule and v<rule['minimum'] or 'maximum' in rule and v>rule['maximum']:raise ValueError('Alternate method bound violated')

def source_hashes():
    files=[ROOT/'catalog.json']+list(ROOT.glob('*.py'))+[p for p in (ROOT/'server').rglob('*') if p.is_file() and p.suffix in ('.py','.R','.json')]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}

def prepare(project,out):
    import shutil
    validate(project);p={**project,'schema':'private-perturbation-request/1','submission_state':'NOT_SUBMITTED','source_sha256':source_hashes()}
    p['plan_sha256']=digest(p);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    write(out/'request.private.json',p)
    shutil.copytree(ROOT/'server',out/'server')
    for source in [ROOT/'catalog.json']+list(ROOT.glob('*.py')):shutil.copy2(source,out/source.name)
    write(out/'dispatch.private.json',{'state':'PREPARED_NOT_SUBMITTED','command_argv':['python3','server/runtime.py','request.private.json','FRESH_OUTPUT_DIRECTORY'],'scientific_runtime':STATE,'unknown_submission':'inspect_real_receipts_never_automatically_retry','automatic_install':False,'public_upload':False})
    return {'state':'PREPARED_NOT_SUBMITTED','method':project['method'],'scientific_runtime':STATE}
