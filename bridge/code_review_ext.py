"""Private scientific software review, contracts and reviewed development artifacts."""
import ast
import collections
import difflib
import html
import json
import math
import re
import statistics
from pathlib import Path
from academic_common import artifact, digest, read_file, rows, text
from code_common import scoped_sources, report, table, number, binding, sha, canon, relative


def map_code_project(root_path: str, files: list) -> dict:
    """Map only selected Python ASTs and located non-Python declarations without importing source."""
    _,source=scoped_sources(root_path,files); result=[]; edges=[]
    for item in source:
        entry={k:v for k,v in item.items() if k!='text'};entry.update(definitions=[],imports=[],calls=[],issues=[])
        if item['path'].endswith('.py'):
            try: tree=ast.parse(item['text'])
            except SyntaxError as e:entry['issues'].append({'line':e.lineno,'kind':'syntax_error'});result.append(entry);continue
            for n in ast.walk(tree):
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    entry['definitions'].append({'name':n.name,'line':n.lineno,'end_line':n.end_lineno,'kind':type(n).__name__})
                if isinstance(n,(ast.Import,ast.ImportFrom)):
                    entry['imports'].append({'module':n.module if isinstance(n,ast.ImportFrom) else ','.join(a.name for a in n.names),'line':n.lineno})
                if isinstance(n,ast.Call):entry['calls'].append({'expression':ast.unparse(n.func)[:200],'line':n.lineno})
            entry['entrypoint']=any(isinstance(n,ast.Compare) and ast.unparse(n)=='__name__ == \'__main__\'' for n in ast.walk(tree))
        else:
            for i,line in enumerate(item['text'].splitlines(),1):
                if re.search(r'function\b|\bprocess\s+\w+|\brule\s+\w+|CREATE\s+TABLE',line,re.I):
                    entry['definitions'].append({'line':i,'declaration':line.strip()[:200],'kind':'lexical_candidate'})
            entry['issues'].append({'kind':'non_python_lexical_map_requires_review'})
        result.append(entry)
    modules={Path(i['path']).with_suffix('').as_posix().replace('/','.') for i in source if i['path'].endswith('.py')}
    for entry in result:
        for imp in entry['imports']:
            if imp['module'] in modules:edges.append({'source':entry['path'],'module':imp['module'],'line':imp['line']})
    return report('code_map',files=result,selected_import_edges=edges,coverage='explicit_selected_files_only')


def audit_scientific_code(root_path: str, files: list) -> dict:
    """Locate risky source constructs and scientific pitfalls; no imports, execution or semantic guarantees."""
    _,source=scoped_sources(root_path,files);findings=[]
    patterns={'shell_string_or_eval':r'\beval\s*\(|\bexec\s*\(|shell\s*=\s*True|\bos\.system\s*\(',
      'unsafe_deserialization':r'pickle\.load|yaml\.load\s*\(',
      'suppressed_failure':r'except\s*:\s*$|except\s+Exception\s*:\s*$|allow_errors\s*=\s*True',
      'absolute_or_identity_candidate':r'\b(?:password|api_key|access_token)\s*=|Path\.home\s*\(',
      'implicit_missing_exclusion':r'\.dropna\s*\(|na\.omit\s*\(|complete\.cases\s*\(',
      'join_cardinality_review':r'\.merge\s*\(|\bmerge\s*\(|\b(?:left|inner|full)_join\s*\(|\bJOIN\b',
      'transformation_review':r'log[12]?p?\s*\(|scale\s*\(|StandardScaler\s*\(',
      'randomness_review':r'np\.random|numpy\.random|\brandom\.|sample\s*\(|train_test_split\s*\(',
      'multiple_testing_review':r't\.test\s*\(|ttest_|wilcox|mannwhitney|\.pvalue',
      'destructive_write_review':r'rmtree\s*\(|unlink\s*\(|Remove-Item|\brm\s+-rf\b'}
    for item in source:
        for i,line in enumerate(item['text'].splitlines(),1):
            for kind,pattern in patterns.items():
                if re.search(pattern,line,re.I): findings.append({'file':item['path'],'line':i,'kind':kind,'decision':'review_candidate'})
    return report('scientific_code_audit',source_manifest=[{k:v for k,v in x.items() if k!='text'} for x in source],findings=findings,
                  severity='candidates_require_context',limitations=['Lexical matches may be comments or legitimate code; absence of a match does not establish safety.'])


def audit_notebook(notebook_path: str) -> dict:
    """Locate execution disorder, stale/error outputs, magic commands and Python name-use candidates without running cells."""
    _,raw=read_file(notebook_path,12_000_000);nb=json.loads(raw)
    if nb.get('nbformat')!=4 or not isinstance(nb.get('cells'),list) or len(nb['cells'])>1000:raise ValueError('Bounded v4 notebook required')
    issues=[];last=0;defined=set();cells=[]
    for index,cell in enumerate(nb['cells']):
        if cell.get('cell_type')!='code':continue
        src=cell.get('source',[]);src=''.join(src) if isinstance(src,list) else src
        count=cell.get('execution_count');outputs=cell.get('outputs',[])
        if count is not None:
            if type(count) is not int or count<=last:issues.append({'cell':index,'kind':'nonmonotone_execution'})
            if type(count) is int:last=count
        if outputs and count is None:issues.append({'cell':index,'kind':'output_without_execution_count'})
        if any(o.get('output_type')=='error' for o in outputs):issues.append({'cell':index,'kind':'saved_error'})
        if re.search(r'(?m)^\s*[!%]',src):issues.append({'cell':index,'kind':'magic_or_shell_requires_review'});continue
        try:tree=ast.parse(src)
        except SyntaxError:issues.append({'cell':index,'kind':'python_parse_failure'});continue
        loads={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
        stores={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
        stores|={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        stores|={a.asname or a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for a in n.names}
        candidates=loads-defined-stores-set(dir(__import__('builtins')))
        if candidates:issues.append({'cell':index,'kind':'name_use_candidate','names':sorted(candidates)})
        defined|=stores;cells.append({'cell':index,'source_sha256':digest(src.encode()),'output_sha256':sha(outputs)})
    return report('notebook_audit',source_sha256=digest(raw),cells=cells,issues=issues,
      limitations=['Name analysis is conservative and not scope-aware. Clean execution requires the reviewed server notebook adapter; saved outputs do not prove freshness.'])


def audit_data_contract(table_path: str, contract: dict) -> dict:
    """Check explicit columns, types, units metadata, missingness, keys, categories and ranges before analysis."""
    header,data,h=table(table_path); specs=contract.get('columns');issues=[]
    if not isinstance(specs,dict) or not specs:raise ValueError('Nonempty column contract required')
    missing=set(specs)-set(header)
    issues += [{'kind':'missing_column','column':c} for c in sorted(missing)]
    if contract.get('exact_columns') and set(header)!=set(specs):issues.append({'kind':'unexpected_columns'})
    keys=contract.get('primary_key',[])
    if not isinstance(keys,list) or not set(keys)<=set(header):raise ValueError('Primary keys must be present')
    missing_values=set(contract.get('missing_values',['','NA','NaN']))
    seen=set()
    for i,row in enumerate(data,2):
        if keys:
            key=tuple(row[k] for k in keys)
            if any(v in missing_values for v in key) or key in seen:issues.append({'row':i,'kind':'missing_or_duplicate_key'})
            seen.add(key)
        for c,spec in specs.items():
            if c not in row:continue
            if spec.get('type') not in {'string','number','integer','date','boolean'}:raise ValueError('Unsupported contract type')
            v=row[c]
            if v in missing_values:
                if not spec.get('nullable',False):issues.append({'row':i,'column':c,'kind':'missing_value'})
                continue
            try:
                if spec['type'] in {'number','integer'}:
                    x=number(v)
                    if spec['type']=='integer' and x!=int(x):raise ValueError()
                    if 'minimum' in spec and x<number(spec['minimum']) or 'maximum' in spec and x>number(spec['maximum']):raise ValueError()
                if spec['type']=='boolean' and v not in {'0','1','true','false'}:raise ValueError()
                if spec['type']=='date':__import__('datetime').date.fromisoformat(v)
                if 'enum' in spec and v not in spec['enum']:raise ValueError()
            except (ValueError,OverflowError):issues.append({'row':i,'column':c,'kind':'type_range_or_category'})
    for c,expected in contract.get('units',{}).items():
        if contract.get('observed_units',{}).get(c)!=expected:issues.append({'column':c,'kind':'unit_metadata_mismatch'})
    if 'expected_row_count' in contract and len(data)!=contract['expected_row_count']:issues.append({'kind':'row_count_mismatch'})
    order=contract.get('expected_key_order')
    if order is not None and [list(tuple(row[k] for k in keys)) for row in data]!=order:issues.append({'kind':'key_order_mismatch'})
    return report('data_contract',input_sha256=h,contract_sha256=sha(contract),row_count=len(data),issues=issues,contract_pass=not issues,
      limitations=['Units are checked against supplied metadata, not inferred from values. No rows are removed or imputed.'])


def audit_table_join(left_path: str, right_path: str, keys: list, relationship: str = 'one_to_one', join: str = 'left') -> dict:
    """Compute join cardinality, null keys, unmatched counts and row expansion before joining; do not emit private identifiers."""
    lh,left,a=table(left_path);rh,right,b=table(right_path)
    if not keys or not set(keys)<=set(lh)&set(rh) or relationship not in {'one_to_one','one_to_many','many_to_one','many_to_many'} or join not in {'left','inner','full'}:raise ValueError('Explicit valid join contract required')
    def counts(data):return collections.Counter(tuple(r[k] for k in keys) for r in data)
    lc,rc=counts(left),counts(right);issues=[]
    if any(any(v in {'','NA','NaN'} for v in k) for k in set(lc)|set(rc)):issues.append('missing_join_key')
    if relationship in {'one_to_one','one_to_many'} and max(lc.values(),default=0)>1:issues.append('left_key_not_unique')
    if relationship in {'one_to_one','many_to_one'} and max(rc.values(),default=0)>1:issues.append('right_key_not_unique')
    output=sum(n*(rc.get(k,0) or (1 if join in {'left','full'} else 0)) for k,n in lc.items())
    if join=='full':output+=sum(n for k,n in rc.items() if k not in lc)
    return report('join_audit',input_hashes=[a,b],relationship=relationship,join=join,issues=issues,contract_pass=not issues,
      left_rows=len(left),right_rows=len(right),expected_output_rows=output,
      unmatched_left_rows=sum(n for k,n in lc.items() if k not in rc),unmatched_right_rows=sum(n for k,n in rc.items() if k not in lc),
      limitations=['Missing SQL NULL keys and pandas missing keys have different semantics; null keys block acceptance.'])


def compare_data_exchange(before_path: str, after_path: str, keys: list, columns: list, tolerance: float = 0.0, numeric_columns: list = None) -> dict:
    """Compare serialized cross-language values by explicit unique keys, types and declared numeric tolerance."""
    ah,a,ha=table(before_path);bh,b,hb=table(after_path);numeric=set(numeric_columns or [])
    if tolerance<0 or not math.isfinite(tolerance) or not keys or not set(keys+columns)<=set(ah)&set(bh) or not numeric<=set(columns):raise ValueError('Explicit columns/keys and finite nonnegative tolerance required')
    def index(data):
        out={}
        for r in data:
            k=tuple(r[c] for c in keys)
            if k in out or any(not v for v in k):raise ValueError('Unique nonmissing exchange keys required')
            out[k]=r
        return out
    ai,bi=index(a),index(b);differences=[]
    for k in ai.keys()&bi.keys():
        for c in columns:
            x,y=ai[k][c],bi[k][c]
            if c in numeric:
                if x in {'','NA','NaN'} or y in {'','NA','NaN'}:equal=x==y
                else:equal=abs(number(x)-number(y))<=tolerance
            else:equal=x==y
            if not equal:differences.append({'key_sha256':sha(k),'column':c,'kind':'value_changed'})
    result={'input_hashes':[ha,hb],'missing_keys':len(ai.keys()-bi.keys()),'added_keys':len(bi.keys()-ai.keys()),'differences':differences,
            'row_order_changed':list(ai)!=list(bi),'tolerance':tolerance}
    return report('data_exchange',**result,equivalent=not differences and set(ai)==set(bi))


def audit_numeric_results(table_path: str, rules: dict) -> dict:
    """Check finite values, explicit bounds, uncertainty ordering and declared probability sums without fitting models."""
    header,data,h=table(table_path);issues=[]
    columns=rules.get('columns',{})
    if not columns or not set(columns)<=set(header):raise ValueError('Explicit numeric columns required')
    for i,row in enumerate(data,2):
        for c,spec in columns.items():
            try:
                v=number(row[c])
                if 'minimum' in spec and v<number(spec['minimum']) or 'maximum' in spec and v>number(spec['maximum']):raise ValueError()
            except ValueError:issues.append({'row':i,'column':c,'kind':'nonfinite_or_out_of_range'})
        for interval in rules.get('intervals',[]):
            if not set(interval)<=set(header) or len(interval)!=3:raise ValueError('Use lower/estimate/upper columns')
            try:
                lo,est,hi=[number(row[c]) for c in interval]
                if not lo<=est<=hi:issues.append({'row':i,'kind':'invalid_interval'})
            except ValueError:issues.append({'row':i,'kind':'invalid_interval_number'})
        for group in rules.get('probability_sums',[]):
            if not set(group)<=set(header):raise ValueError('Probability columns absent')
            try:
                vals=[number(row[c]) for c in group]
                if any(not 0<=v<=1 for v in vals) or abs(sum(vals)-1)>number(rules.get('sum_tolerance',1e-6)):issues.append({'row':i,'kind':'probability_sum'})
            except ValueError:issues.append({'row':i,'kind':'invalid_probability'})
    return report('numeric_audit',input_sha256=h,rules_sha256=sha(rules),issues=issues,numeric_pass=not issues)


def compare_scientific_results(before_path: str, after_path: str, keys: list, metrics: dict) -> dict:
    """Compare prespecified result metrics by keys with absolute/relative tolerances and contrast metadata."""
    ah,a,ha=table(before_path);bh,b,hb=table(after_path)
    if not keys or not metrics or not set(keys+list(metrics))<=set(ah)&set(bh):raise ValueError('Explicit result keys and metrics required')
    def idx(data):
        out={}
        for r in data:
            k=tuple(r[c] for c in keys)
            if k in out or any(not x for x in k):raise ValueError('Result keys must be unique and nonmissing')
            out[k]=r
        return out
    ai,bi=idx(a),idx(b);changed=[]
    for key in ai.keys()&bi.keys():
        for c,spec in metrics.items():
            av,rv=number(spec.get('atol',0)),number(spec.get('rtol',0))
            if min(av,rv)<0:raise ValueError('Tolerances cannot be negative')
            x,y=number(ai[key][c]),number(bi[key][c]);difference=y-x
            if abs(difference)>av+rv*abs(x):changed.append({'key_sha256':sha(key),'metric':c,'difference':difference,'before':x,'after':y})
    return report('scientific_result_diff',input_hashes=[ha,hb],changed=changed,removed_count=len(ai.keys()-bi.keys()),added_count=len(bi.keys()-ai.keys()),
      within_tolerance=not changed and set(ai)==set(bi),limitations=['Tolerances are declared acceptance rules, not proof that either analysis is valid. Review sample counts, estimand and contrast separately.'])


def bind_analysis_qc(inputs: list, design: dict, references: dict, qc_receipt_path: str, assessment: dict) -> dict:
    """Bind an actual passing QC result and reviewed assessment to exact input/design/reference versions."""
    _,raw=read_file(qc_receipt_path);receipt=json.loads(raw)
    if receipt.get('result_file'):
        _,result=read_file(receipt['result_file'])
        if digest(result)!=receipt.get('sha256') or receipt.get('success') is not True:raise ValueError('QC bridge receipt/result mismatch')
        receipt=json.loads(result)
    passes=[receipt.get(k) for k in ('contract_pass','numeric_pass','qc_pass','gate_pass') if k in receipt]
    if not passes or any(x is not True for x in passes) or assessment.get('decision')!='pass' or not assessment.get('checks') or not assessment.get('limitations'):
        raise ValueError('A concrete passing QC result and reviewed limitations required')
    value=binding(inputs,design,references)
    return report('analysis_qc_binding',binding=value,binding_sha256=sha(value),qc_source_sha256=digest(raw),assessment=assessment,
      accepted_for_bound_inputs=True)


def check_analysis_qc(binding_file: str, expected_sha256: str, inputs: list, design: dict, references: dict) -> dict:
    """Invalidate acceptance when an input, scientific design or reference changes; no automatic recalculation."""
    _,raw=read_file(binding_file)
    if digest(raw)!=expected_sha256:raise ValueError('Reviewed QC binding changed')
    previous=json.loads(raw)
    if previous.get('accepted_for_bound_inputs') is not True or sha(previous.get('binding'))!=previous.get('binding_sha256'):raise ValueError('Invalid QC binding')
    current=binding(inputs,design,references);old=previous['binding'];changed=[k for k in ('inputs','design','references') if current[k]!=old[k]]
    return report('qc_binding_check',qc_current=not changed,changed_dimensions=changed,
      next_action='review_new_qc_before_analysis' if changed else 'bound_engineering_qc_current')


def prepare_code_revision(root_path: str, replacements: list, rationale: str, validation_commands: list) -> dict:
    """Produce a source-hash-bound patch for explicit full-file replacements and validation commands; no execution or overwrite."""
    selected=[r['path'] for r in rows(replacements,30)];_,source=scoped_sources(root_path,selected)
    if not validation_commands or len(validation_commands)>30 or any(not isinstance(a,list) or not a or any(not isinstance(v,str) or '\x00' in v for v in a) for a in validation_commands):raise ValueError('Exact validation argv required')
    plans=[];patch=[]
    for item,change in zip(source,replacements):
        new=text(change.get('new_source'),2_000_000)
        if item['path'].endswith('.py'):ast.parse(new)
        plans.append({'path':item['path'],'before_sha256':item['sha256'],'after_sha256':digest(new.encode()),'new_source':new})
        patch.extend(difflib.unified_diff(item['text'].splitlines(True),new.splitlines(True),fromfile='a/'+item['path'],tofile='b/'+item['path']))
    return artifact('code_revision',{'schema':1,'root_path':str(Path(root_path).resolve()),'rationale':text(rationale),'replacements':plans,
       'validation_commands':validation_commands,'execution_state':'not_executed','scientific_result_review':'required'}, {'changes.patch':''.join(patch)})


def prepare_method_reproduction(method: dict, mappings: list, baseline: dict) -> dict:
    """Validate located method-to-code mappings and produce a gap ledger; do not invent unspecified paper parameters."""
    if not {'citation','version','objective'}<=set(method) or not baseline.get('dataset_source') or not baseline.get('acceptance_metrics'):raise ValueError('Method provenance and public/synthetic baseline required')
    result=[]
    for row in rows(mappings,200):
        if not {'id','source_location','source_sha256','method_element','implementation_location','status'}<=set(row):raise ValueError('Located mappings required')
        if not re.fullmatch('[a-f0-9]{64}',row['source_sha256']) or row['status'] not in {'specified','assumption','missing','implemented_unverified','validated'}:raise ValueError('Explicit mapping state required')
        if row['status']=='validated' and not row.get('receipt_sha256'):raise ValueError('Validated mapping needs actual receipt hash')
        result.append(row)
    if not result or len({r['id'] for r in result})!=len(result):raise ValueError('Distinct method mappings required')
    return report('method_reproduction',method=method,mappings=result,baseline=baseline,unresolved=[r['id'] for r in result if r['status'] in {'missing','assumption'}],
      limitations=['Located text and receipt hashes need substantive review; a mapping does not establish implementation equivalence.'])


def materialize_code_revision(plan_file: str, expected_sha256: str, destination_directory: str, dispatch: bool = False) -> dict:
    """Save reviewed source replacements in a fresh staging directory, with original hashes and patch; never overwrite the active project."""
    if dispatch is not True:raise ValueError('Explicit reviewed staging dispatch required')
    _,raw=read_file(plan_file)
    if digest(raw)!=expected_sha256:raise ValueError('Code revision plan changed')
    plan=json.loads(raw);replacements=rows(plan.get('replacements'),30)
    _,originals=scoped_sources(plan['root_path'],[r['path'] for r in replacements])
    payload=[]
    for r,o in zip(replacements,originals):
        if o['sha256']!=r['before_sha256'] or digest(r['new_source'].encode())!=r['after_sha256']:raise ValueError('Code changed after review')
        payload.append((r['path'],r['new_source']))
    dest=Path(destination_directory).expanduser()
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():raise ValueError('Fresh owned staging folder required')
    dest.mkdir(exist_ok=False)
    for name,source in payload:
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x',encoding='utf8',newline='\n') as stream:stream.write(source)
    with (dest/'revision.json').open('x',encoding='utf8') as stream:json.dump({'plan_sha256':expected_sha256,'validation_commands':plan['validation_commands'],'state':'staged_not_executed'},stream)
    return {'success':True,'state':'staged_not_executed','destination':str(dest.resolve()),'original_sources_unchanged':True,
      'limitations':['Only explicitly revised files are materialized. Copy other selected dependencies separately; validate on the server before integrating the change.']}


def audit_plan_implementation(plan: dict, observations: list) -> dict:
    """Compare declared endpoints, estimand, units, contrasts, filtering and missingness with located actual implementation observations."""
    required={'estimand','independent_unit','endpoints','contrast','covariates','missingness','exclusions','multiplicity'}
    if not required<=set(plan):raise ValueError('Complete prespecified analysis plan required')
    issues=[];covered=set()
    for r in rows(observations,200):
        if r.get('element') not in required or not r.get('location') or not re.fullmatch('[a-f0-9]{64}',r.get('source_sha256','')) or 'observed' not in r:raise ValueError('Located implementation observations required')
        covered.add(r['element'])
        if r['observed']!=plan[r['element']]:issues.append({'element':r['element'],'location':r['location'],'kind':'plan_deviation','justification':r.get('justification')})
    return report('implementation_audit',plan_sha256=sha(plan),issues=issues,unassessed=sorted(required-covered),
      limitations=['Observed values are supplied by a reviewer; this tool does not infer every statistical choice from arbitrary source.'])


def prepare_api_migration(installed_versions: dict, changes: list) -> dict:
    """Create a version-specific migration ledger from supplied official documentation and located source uses."""
    if not installed_versions:raise ValueError('Actual installed version records required')
    findings=[]
    for r in rows(changes,200):
        if not {'package','tested_version','official_source','location','old_api','replacement'}<=set(r) or not r['official_source'].startswith('https://'):raise ValueError('Official source and located API changes required')
        findings.append({**r,'version_match':installed_versions.get(r['package'])==r['tested_version'],'status':'review_required'})
    return report('api_migration',installed_versions=installed_versions,changes=findings,
      limitations=['URLs are recorded, never fetched. Reviewer must confirm the publisher and applicability to the installed version.'])


def inspect_dependency_locks(root_path: str, files: list) -> dict:
    """Read scoped uv, renv, requirements and environment records without sourcing profiles, restoring or installing packages."""
    _,sources=scoped_sources(root_path,files);out=[]
    for s in sources:
        kind=Path(s['path']).name;v={'path':s['path'],'sha256':s['sha256'],'issues':[]}
        if kind=='renv.lock':
            data=json.loads(s['text']);v['packages']={k:x.get('Version') for k,x in data.get('Packages',{}).items()};v['runtime']=data.get('R',{}).get('Version')
        elif kind in {'uv.lock','pyproject.toml'}:
            import tomllib
            data=tomllib.loads(s['text']);v['packages']={x['name']:x.get('version') for x in data.get('package',[])};v['runtime']=data.get('requires-python',data.get('project',{}).get('requires-python'))
        elif kind.endswith('.json'):v['environment']=json.loads(s['text'])
        elif 'requirements' in kind:
            v['packages']={}
            for i,line in enumerate(s['text'].splitlines(),1):
                line=line.strip()
                if not line or line.startswith('#'):continue
                match=re.fullmatch(r'([A-Za-z0-9_.-]+)==([^;\s]+)(?:\s*;.*)?',line)
                if match:v['packages'][match[1]]=match[2]
                else:v['issues'].append({'line':i,'kind':'not_exact_version_or_external_source'})
        else:v['issues'].append({'kind':'unsupported_lock_format_review_required'})
        out.append(v)
    return report('dependency_locks',locks=out,limitations=['Package locks do not reproduce OS libraries, compilers, reference data or scientific results. No dependency is installed.'])


def compare_environments(before: dict, after: dict) -> dict:
    """Compare supplied actual environment snapshots and expose missing runtime/platform/library dimensions."""
    required={'runtime','platform','packages','system_libraries','references'};changes=[]
    for dim in sorted(required):
        if before.get(dim)!=after.get(dim):changes.append({'dimension':dim,'before':before.get(dim),'after':after.get(dim)})
    return report('environment_diff',changes=changes,unassessed=sorted(required-(set(before)&set(after))),revalidation_required=bool(changes))


def prepare_scientific_test_suite(cases: list, source_manifest: list) -> dict:
    """Generate executable unittest cases for reviewed fixed Python module/functions and explicit expected values or refusal cases."""
    checked=[];body=['import importlib, math, unittest, hashlib','from pathlib import Path','class ScientificChecks(unittest.TestCase):']
    if not source_manifest or any(not re.fullmatch('[a-f0-9]{64}',s.get('sha256','')) for s in source_manifest):raise ValueError('Source hashes required')
    for s in source_manifest:relative(s['path'])
    body += ['    @classmethod','    def setUpClass(cls):',f'        manifest={source_manifest!r}', '        for source in manifest:', '            raw=Path(source["path"]).read_bytes()', '            if hashlib.sha256(raw).hexdigest()!=source["sha256"]: raise ValueError("Scientific test source binding changed")']
    for i,c in enumerate(rows(cases,100)):
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',c.get('module','')) or not re.fullmatch(r'[A-Za-z_]\w*',c.get('function','')):raise ValueError('Explicit module/function required')
        if c.get('kind') not in {'equals','numeric','refuses','permutation_invariance'} or not c.get('rationale'):raise ValueError('Meaningful assertion kind and rationale required')
        args=c.get('arguments',{});canon(args)
        body += [f'    def test_case_{i}(self):',f'        fn=getattr(importlib.import_module({c["module"]!r}),{c["function"]!r})',f'        args={args!r}']
        if c['kind']=='refuses':body+=['        with self.assertRaises((ValueError, TypeError)):', '            fn(**args)']
        elif c['kind']=='equals':body += [f'        self.assertEqual(fn(**args), {c.get("expected")!r})']
        elif c['kind']=='numeric':
            expected=number(c['expected']);atol=number(c.get('atol',0));rtol=number(c.get('rtol',0))
            if min(atol,rtol)<0:raise ValueError('Nonnegative test tolerances required')
            body += ['        value=float(fn(**args))','        self.assertTrue(math.isfinite(value))',f'        self.assertLessEqual(abs(value-{expected!r}), {atol!r}+{rtol!r}*abs({expected!r}))']
        else:
            key=c['argument'];values=args.get(key)
            if not isinstance(values,list) or len(values)<2:raise ValueError('Explicit permutation argument required')
            body += ['        value=fn(**args)',f'        args[{key!r}]=list(reversed(args[{key!r}]))','        self.assertEqual(fn(**args), value)']
        checked.append(c)
    if not checked:raise ValueError('Nonempty test suite required')
    body+=['if __name__=="__main__": unittest.main()']
    return artifact('scientific_tests',{'schema':1,'cases':checked,'source_manifest':source_manifest,'state':'generated_not_executed',
      'limitations':['Generated tests import and execute selected source only when explicitly dispatched in an owned isolated server environment. They are not a sandbox.']},
      {'test_scientific.py':'\n'.join(body)+'\n'})


def prepare_configuration_migration(configuration_path: str, operations: list, target_schema: dict) -> dict:
    """Preview explicit JSON key renames/additions with source hash, validation and reversible original snapshot."""
    p,raw=read_file(configuration_path);before=json.loads(raw)
    if not isinstance(before,dict) or not isinstance(target_schema,dict):raise ValueError('JSON objects required')
    after=dict(before)
    for op in rows(operations,100):
        if op.get('operation')=='rename':
            old,new=text(op.get('from'),200),text(op.get('to'),200)
            if old not in after or new in after:raise ValueError('Rename conflict')
            after[new]=after.pop(old)
        elif op.get('operation')=='add':
            key=text(op.get('key'),200)
            if key in after:raise ValueError('Existing configuration must not be overwritten')
            after[key]=op.get('value')
        else:raise ValueError('Only reversible rename/add operations supported')
    types={'string':str,'object':dict,'array':list,'boolean':bool,'integer':int}
    for key,kind in target_schema.items():
        if kind not in types or key not in after or type(after[key]) is not types[kind]:raise ValueError('Target schema violation')
    return artifact('configuration_migration',{'schema':1,'source_path':str(p),'source_sha256':digest(raw),'operations':operations,'before':before,'after':after,'target_schema':target_schema,
       'state':'reviewed_copy_required'}, {'original.json':raw,'migrated.json':canon(after)+'\n'})


def apply_configuration_migration(plan_file: str, expected_sha256: str, destination: str, dispatch: bool = False) -> dict:
    """Write a reviewed migration to a fresh destination only; preserve original and refuse changed source/plan."""
    if dispatch is not True:raise ValueError('Explicit reviewed dispatch required')
    _,raw=read_file(plan_file)
    if digest(raw)!=expected_sha256:raise ValueError('Migration plan changed')
    p=json.loads(raw);_,original=read_file(p['source_path'])
    if digest(original)!=p['source_sha256']:raise ValueError('Configuration changed since review')
    out=Path(destination).expanduser()
    if out.exists() or out.is_symlink() or out.suffix!='.json' or not out.parent.is_dir():raise ValueError('Fresh JSON destination required')
    data=(canon(p['after'])+'\n').encode()
    with out.open('xb') as stream:stream.write(data)
    return {'success':True,'state':'saved_fresh_copy','sha256':digest(data),'source_unchanged':True,'destination':str(out.resolve())}


def audit_dependency_components(components: list) -> dict:
    """Audit supplied package provenance, licenses, pins and vulnerability-review dates; no online lookup or install."""
    out=[]
    for c in rows(components,500):
        issues=[]
        for key in ('name','version','source','license','reviewed_at','checksum'):
            if not c.get(key):issues.append('missing_'+key)
        if c.get('checksum') and not re.fullmatch('[a-f0-9]{64}',c['checksum']):issues.append('invalid_checksum')
        if not c.get('vulnerability_source'):issues.append('vulnerability_status_unverified')
        out.append({'name':c.get('name'),'issues':issues,'declared_license':c.get('license')})
    return report('component_audit',components=out,limitations=['License compatibility and vulnerability status require current upstream review; this ledger does not resolve them automatically.'])


def audit_release_scope(root_path: str, files: list, deny_terms: list = None) -> dict:
    """Scan explicit text sources/notebook outputs for sensitive patterns without echoing matching private values."""
    from privacy_ext import PATTERNS
    _,sources=scoped_sources(root_path,files);findings=[]
    if deny_terms is not None and (not isinstance(deny_terms,list) or any(not isinstance(v,str) or not v for v in deny_terms)):raise ValueError('Explicit private deny terms required')
    for s in sources:
        for kind,pattern in PATTERNS.items():
            if re.search(pattern,s['text']):findings.append({'file':s['path'],'kind':kind})
        if any(v.casefold() in s['text'].casefold() for v in deny_terms or []):findings.append({'file':s['path'],'kind':'private_deny_term'})
    return report('code_release_review',files_reviewed=len(sources),findings=findings,pattern_pass=not findings,
      limitations=['This scoped scan does not scan Git history, binaries, images or unselected files. The release audit separately checks full tracked history. No anonymity guarantee.'])
