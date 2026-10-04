"""Private, revisioned research projects and receipt-driven workflow orchestration.

No network calls, shell commands, scheduler submissions or arbitrary plugins.
"""
import contextlib
import hashlib
import html
import json
import re
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from academic_common import artifact, read_file, rows, text, digest

HERE = Path(__file__).resolve().parent
CONTEXT = {'species', 'model', 'assay', 'biological_unit', 'contrast', 'limitations'}
STATES = {'planned', 'prepared', 'submitted', 'running', 'unknown', 'failed', 'completed', 'accepted'}


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _sha(value):
    return digest(_canon(value).encode())


def _now():
    return datetime.now(timezone.utc).isoformat()


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise ValueError('Use an opaque generated project ID')
    return value


@contextlib.contextmanager
def _db(identity):
    root = (HERE / 'data' / 'projects').resolve()
    path = root / _id(identity) / 'project.sqlite3'
    if not path.is_file() or path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Project is missing or outside its owned folder')
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _load(conn):
    return json.loads(conn.execute('SELECT data FROM project WHERE singleton=1').fetchone()[0])


def _save(conn, value, action):
    before = _load(conn)
    value['revision'] = before['revision'] + 1
    conn.execute('INSERT INTO history(time,action,before_json) VALUES(?,?,?)', (_now(), action, _canon(before)))
    conn.execute('UPDATE project SET data=? WHERE singleton=1', (_canon(value),))


def _validate_project(value):
    if value.get('schema') != 1 or not CONTEXT <= set(value.get('context', {})):
        raise ValueError('Complete scientific context is required')
    for key in CONTEXT:
        if not value['context'][key]: raise ValueError('Scientific context cannot be empty')
    text(value.get('question'), 10000)
    text(value.get('design'), 10000)
    for name in ('datasets', 'claims', 'evidence', 'figures', 'stages', 'edges'):
        items = rows(value.get(name, []), 1000)
        if name != 'edges' and len({text(x.get('id'), 200) for x in items}) != len(items):
            raise ValueError('Duplicate project record ID')
    ids = {x['id'] for name in ('datasets','claims','evidence','figures','stages') for x in value[name]}
    if len(ids) != sum(len(value[n]) for n in ('datasets','claims','evidence','figures','stages')):
        raise ValueError('IDs must be unique across the project')
    for e in value['edges']:
        if e.get('source') not in ids or e.get('target') not in ids:
            raise ValueError('Evidence/lineage edge references a missing record')
        text(e.get('relation'), 100)
    stages = {s['id']: s for s in value['stages']}
    visiting, done = set(), set()
    def visit(identity):
        if identity in visiting: raise ValueError('Stage dependency cycle')
        if identity in done: return
        visiting.add(identity)
        s = stages[identity]
        if s.get('state', 'planned') not in STATES: raise ValueError('Invalid stage state')
        if s.get('placement') not in {'local_review','server'}: raise ValueError('Explicit placement required')
        if s.get('kind') not in {'qc','analysis','check','figure','report'}: raise ValueError('Invalid stage kind')
        for dep in s.get('depends_on', []):
            if dep not in stages: raise ValueError('Missing stage dependency')
            visit(dep)
        visiting.remove(identity); done.add(identity)
    for identity in stages: visit(identity)
    # Analysis requires a QC ancestor; display order alone is not a gate.
    def ancestors(identity):
        return {d for d in stages[identity].get('depends_on', [])} | {a for d in stages[identity].get('depends_on', []) for a in ancestors(d)}
    for s in stages.values():
        if s['kind'] == 'analysis' and not any(stages[d]['kind']=='qc' for d in ancestors(s['id'])):
            raise ValueError('Formal analysis must depend on an explicit QC stage')
    return value


def create_research_project(title: str, question: str, design: str, context: dict, analysis_plan: dict) -> dict:
    """Create an empty private project with explicit design, scientific context and analysis plan."""
    identity = uuid.uuid4().hex
    value = _validate_project({'schema':1,'id':identity,'revision':0,'title':text(title,500),
        'question':question,'design':design,'context':context,'analysis_plan':analysis_plan,
        'datasets':[],'claims':[],'evidence':[],'figures':[],'stages':[],'edges':[]})
    if not isinstance(analysis_plan, dict) or not analysis_plan: raise ValueError('Provide an analysis plan')
    folder = HERE/'data'/'projects'/identity
    folder.mkdir(parents=True, exist_ok=False)
    conn = sqlite3.connect(folder/'project.sqlite3')
    try:
        conn.executescript('CREATE TABLE project(singleton INTEGER PRIMARY KEY CHECK(singleton=1),data TEXT NOT NULL); CREATE TABLE history(time TEXT,action TEXT,before_json TEXT);')
        conn.execute('INSERT INTO project VALUES(1,?)', (_canon(value),)); conn.commit()
    finally: conn.close()
    return {'success':True,'project_id':identity,'revision':0,'state':'empty_private_project'}


def inspect_research_project(project_id: str) -> dict:
    """Read one explicitly selected private project, including real state and pending gates."""
    with _db(project_id) as conn: value = _load(conn)
    return {'success':True,'project':value,'stages':[_stage_view(value,s) for s in value['stages']],
        'limitations':['Project state is a local receipt snapshot, not a live server status. Engineering acceptance is not scientific validity.']}


def prepare_project_revision(project_id: str, expected_revision: int, changes: dict) -> dict:
    """Preview a replacement of selected project fields; protect recorded execution states and history."""
    allowed = {'question','design','analysis_plan','datasets','claims','evidence','figures','stages','edges','title'}
    if not isinstance(changes,dict) or not set(changes)<=allowed: raise ValueError('Unsupported project change')
    with _db(project_id) as conn: before = _load(conn)
    if before['revision'] != expected_revision: raise ValueError('Project revision conflict')
    after = _validate_project({**before,**changes})
    old = {s['id']:s for s in before['stages']}
    for s in after['stages']:
        if s['id'] in old and old[s['id']].get('state','planned')!='planned' and s!=old[s['id']]:
            raise ValueError('Executed stages are immutable in plans; record a receipt or create a new stage')
        if s['id'] not in old and (s.get('state','planned')!='planned' or s.get('receipts')):
            raise ValueError('New stages must be planned with no invented receipts')
    if any(s.get('state','planned')!='planned' and s['id'] not in {x['id'] for x in after['stages']} for s in before['stages']):
        raise ValueError('Executed stages cannot be deleted')
    return artifact('project_revision_plan',{'schema':1,'project_id':project_id,'before_hash':_sha(before),'after':after})


def apply_project_revision(plan_file: str, expected_sha256: str, dispatch: bool = False) -> dict:
    """Commit an unchanged reviewed private project revision with a transaction and conflict check."""
    if dispatch is not True: raise ValueError('Explicit reviewed dispatch required')
    p,raw = read_file(plan_file)
    if digest(raw)!=expected_sha256 or not p.is_relative_to((HERE/'outputs').resolve()) or not p.parent.name.startswith('project_revision_plan_'):
        raise ValueError('Use the unchanged generated revision plan')
    plan=json.loads(raw)
    with _db(plan['project_id']) as conn:
        conn.execute('BEGIN IMMEDIATE');before=_load(conn)
        if _sha(before)!=plan['before_hash']: raise ValueError('Project changed after review')
        _save(conn,_validate_project(plan['after']),'reviewed_revision')
    return {'success':True,'revision':before['revision']+1}


def _stage_view(value, stage):
    stages={s['id']:s for s in value['stages']}
    blocked=[d for d in stage.get('depends_on',[]) if stages[d].get('state','planned')!='accepted']
    state=stage.get('state','planned')
    return {**stage,'state':state,'blocked_by':blocked,'ready':state=='planned' and not blocked,
        'recovery':'inspect real scheduler/process and runner receipts before any new dispatch' if state=='unknown' else None}


def advance_workflow_stage(project_id: str, stage_id: str, expected_revision: int, event: str,
                           receipt_path: str, assessment: dict = None) -> dict:
    """Advance one stage using an immutable saved receipt; fail closed on unknown submissions and unmet QC gates."""
    p,raw=read_file(receipt_path,10_000_000);receipt=json.loads(raw)
    if not isinstance(receipt,dict): raise ValueError('Receipt must be an object')
    assessment=assessment or {}
    with _db(project_id) as conn:
        conn.execute('BEGIN IMMEDIATE');value=_load(conn)
        if value['revision']!=expected_revision: raise ValueError('Project revision conflict')
        stage=next((s for s in value['stages'] if s['id']==stage_id),None)
        if stage is None: raise ValueError('Unknown stage')
        view=_stage_view(value,stage);old=view['state']
        transitions={'prepare':({'planned'},'prepared'),'submit':({'prepared'},'submitted'),
            'observe_running':({'submitted','running','unknown'},'running'),
            'observe_unknown':({'submitted','running'},'unknown'),
            'observe_failure':({'prepared','submitted','running','unknown'},'failed'),
            'observe_completion':({'prepared','submitted','running','unknown'},'completed'),
            'accept':({'completed'},'accepted')}
        if event not in transitions or old not in transitions[event][0]: raise ValueError('Invalid stage transition; unknown tasks cannot be resubmitted')
        if event in {'prepare','submit'} and view['blocked_by']: raise ValueError('Dependencies/QC are not accepted')
        # Existing bridge runner receipt vocabulary. Completion requires actual outputs.
        if event=='observe_completion':
            local_receipt=receipt.get('success') is True and receipt.get('result_file') and receipt.get('sha256')
            if local_receipt:
                _,result_raw=read_file(receipt['result_file'])
                if digest(result_raw)!=receipt['sha256']:raise ValueError('Local result hash mismatch')
            elif receipt.get('state')!='succeeded' or receipt.get('exit_code')!=0 or not receipt.get('outputs') or any(not o.get('exists') or not o.get('bytes') or not re.fullmatch(r'[a-f0-9]{64}',o.get('sha256','')) for o in receipt['outputs']):
                raise ValueError('Completion requires a successful runner receipt with outputs')
            prepared=[r for r in stage.get('receipts',[]) if r['event']=='prepare']
            if prepared:
                _,prep_raw=read_file(prepared[-1]['path']);prep=json.loads(prep_raw)
                if digest(prep_raw)!=prepared[-1]['sha256']:raise ValueError('Saved preparation receipt integrity mismatch')
                expected=prep.get('request_sha256')
                if expected and receipt.get('request_sha256')!=expected:raise ValueError('Completion receipt belongs to a different prepared task')
        if event=='submit' and not (receipt.get('job_id') or receipt.get('pid')):
            raise ValueError('Submission requires a real scheduler/process identifier')
        if event=='accept' and (assessment.get('decision')!='pass' or not assessment.get('checks') or not assessment.get('limitations')):
            raise ValueError('Acceptance requires checks, pass decision and explicit limitations')
        stage['state']=transitions[event][1]
        saved=artifact('workflow_observation',{'event':event,'original_sha256':digest(raw)}, {'source_receipt.json':raw})
        stage.setdefault('receipts',[]).append({'event':event,'path':str(Path(saved['output_directory'])/'source_receipt.json'),'sha256':digest(raw),'observed_at':_now(),'assessment':assessment})
        _save(conn,value,event+':'+stage_id)
    return {'success':True,'stage_id':stage_id,'state':stage['state'],'revision':value['revision'],'submitted_by_this_tool':False}


def execute_workflow_stage(project_id: str, stage_id: str, expected_revision: int, dispatch: bool = False) -> dict:
    """Run one reviewed allowlisted local QC/check stage, persist its real bridge receipt and stop before manual acceptance; server stages require separate explicit dispatch."""
    if dispatch is not True:raise ValueError('Explicit stage execution required')
    allowed={('workflow','audit_sample_metadata'),('workflow','audit_result_table'),
        ('biomedical','audit_enrichment_results'),('biomedical','audit_cell_annotations'),
        ('biomedical','audit_genetic_alignment'),('reporting','audit_analysis_result'),
        ('statistics','guide_study_statistics'),('statistics','audit_statistical_dataset')}
    with _db(project_id) as conn:
        conn.execute('BEGIN IMMEDIATE');value=_load(conn)
        if value['revision']!=expected_revision:raise ValueError('Project revision conflict')
        stage=next((s for s in value['stages'] if s['id']==stage_id),None)
        if stage is None or not _stage_view(value,stage)['ready'] or stage['placement']!='local_review' or stage['kind'] not in {'qc','check'}:raise ValueError('Only ready local QC/check stages can execute here')
        tool=stage.get('tool',{})
        if (tool.get('category'),tool.get('name')) not in allowed:raise ValueError('Tool is outside the fixed local review allowlist')
        stage['state']='running';_save(conn,value,'local_stage_started:'+stage_id)
    import bridge
    try:
        receipt=bridge.run_tool(tool['category'],tool['name'],tool.get('parameters',{}))
    except Exception:
        with _db(project_id) as conn:
            conn.execute('BEGIN IMMEDIATE');value=_load(conn);stage=next(s for s in value['stages'] if s['id']==stage_id)
            stage['state']='unknown';_save(conn,value,'local_stage_unknown:'+stage_id)
        raise
    with _db(project_id) as conn:
        conn.execute('BEGIN IMMEDIATE');value=_load(conn);stage=next(s for s in value['stages'] if s['id']==stage_id)
        stage['state']='completed' if receipt.get('success') else 'failed'
        path,raw=read_file(receipt['receipt_file']);saved=artifact('workflow_observation',{'event':'local_execution'},{'source_receipt.json':raw})
        stage.setdefault('receipts',[]).append({'event':'local_execution','path':str(Path(saved['output_directory'])/'source_receipt.json'),'sha256':digest(raw),'observed_at':_now()})
        _save(conn,value,'local_stage_finished:'+stage_id)
    return {'success':True,'state':stage['state'],'revision':value['revision'],'receipt':receipt,'acceptance':'review_required_before_dependent_stages'}


def audit_project_lineage(project_id: str, changed_source_ids: list = None) -> dict:
    """Locate overlapping cohort/subject tokens and downstream claims affected by changed sources; never infer independence from different accession IDs."""
    with _db(project_id) as conn: value=_load(conn)
    overlaps=[];datasets=value['datasets']
    for i,a in enumerate(datasets):
        for b in datasets[i+1:]:
            tokens=set(a.get('subject_tokens',[]))&set(b.get('subject_tokens',[]))
            cohort=bool(set(a.get('cohort_ids',[]))&set(b.get('cohort_ids',[])))
            if tokens or cohort: overlaps.append({'datasets':[a['id'],b['id']],'shared_subject_count':len(tokens),'shared_cohort':cohort,'decision':'review_dependent_evidence'})
    affected=set(changed_source_ids or [])
    all_ids={x['id'] for n in ('datasets','claims','evidence','figures','stages') for x in value[n]}
    if not affected<=all_ids: raise ValueError('Changed source is outside selected project')
    while True:
        new=affected|{e['target'] for e in value['edges'] if e['source'] in affected}
        if new==affected:break
        affected=new
    return artifact('project_lineage',{'overlaps':overlaps,'affected_ids':sorted(affected),
        'coverage_unknown':[d['id'] for d in datasets if not d.get('subject_tokens') or not d.get('cohort_ids')],
        'limitations':['Only supplied lineage and private pseudonymous tokens are compared. Absence of a match does not prove cohort independence. No tokens are sent to public endpoints.']})


def build_project_dashboard(project_id: str, software_states: list = None) -> dict:
    """Render a private static task board with blocked stages, receipt snapshots and unverified software states."""
    result=inspect_research_project(project_id);value=result['project']
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(s.get(k,'')))+'</td>' for k in ('id','kind','placement','state','blocked_by','recovery'))+'</tr>' for s in result['stages'])
    page='<html><meta charset="utf-8"><title>Research project</title><h1>'+html.escape(value['title'])+'</h1><p>Private receipt snapshot. Refresh real task state before recovery.</p><table><tr><th>Stage</th><th>Kind</th><th>Placement</th><th>State</th><th>Blocked by</th><th>Recovery</th></tr>'+table+'</table><h2>Software</h2><pre>'+html.escape(_canon(rows(software_states or [],100)))+'</pre></html>'
    return artifact('project_dashboard',result,{'dashboard.html':page})


def freeze_reproduction_package(project_id: str, files: list, environment: dict, commands: list) -> dict:
    """Freeze explicitly selected bounded result files, parameters, environment and commands in a private reproducibility bundle."""
    with _db(project_id) as conn: value=_load(conn)
    if not isinstance(environment,dict) or not environment or not commands or len(commands)>100:
        raise ValueError('Provide tool/reference versions and exact command records')
    payload={};manifest=[];total=0
    for item in rows(files,100):
        name=text(item.get('name'),200)
        if Path(name).name!=name or name in payload or name=='reproduction.json': raise ValueError('Distinct basenames required')
        p,raw=read_file(item['path'],30_000_000);total+=len(raw)
        if total>100_000_000: raise ValueError('Export a bounded server summary instead of large results')
        payload[name]=raw;manifest.append({'name':name,'bytes':len(raw),'sha256':digest(raw)})
    return artifact('reproduction',{'schema':1,'project':value,'environment':environment,'commands':commands,'files':manifest,
        'limitations':['Private bundle may contain sensitive results and commands. Hash integrity does not establish reproducibility or scientific validity.']},payload)


def create_private_backup(project_ids: list = None, library_ids: list = None, configuration_files: list = None) -> dict:
    """Create an explicit scoped private archive using transaction-consistent SQLite backup; never discover or scan whole libraries."""
    import io
    import personal_library_ext as library
    payload={}
    def snapshot(conn):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'snapshot.sqlite3';dest=sqlite3.connect(target)
            try:conn.backup(dest)
            finally:dest.close()
            return target.read_bytes()
    for identity in project_ids or []:
        with _db(identity) as conn: payload['projects/'+_id(identity)+'/project.sqlite3']=snapshot(conn)
    for identity in library_ids or []:
        with library._db(identity) as (conn,meta): payload['personal_libraries/'+_id(identity)+'/index.sqlite3']=snapshot(conn)
    for item in rows(configuration_files or [],20):
        name=text(item.get('name'),100)
        if Path(name).name!=name or not name.endswith('.json'): raise ValueError('Named JSON configurations only')
        _,raw=read_file(item['path'],1_000_000);json.loads(raw);payload['configurations/'+name]=raw
    if not payload or len(payload)>100 or sum(map(len,payload.values()))>100_000_000: raise ValueError('Select a bounded nonempty private backup')
    entries=[{'path':n,'sha256':digest(raw),'bytes':len(raw)} for n,raw in payload.items()]
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,raw in payload.items():archive.writestr(name,raw)
        archive.writestr('backup_manifest.json',_canon({'schema':1,'created_at':_now(),'files':entries}))
    return artifact('private_backup',{'schema':1,'files':entries,'confidential':True},{'backup.zip':buf.getvalue()})


def _backup(path):
    import io
    _,raw=read_file(path,100_000_000)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist()
        if len(entries)>101 or len({e.filename for e in entries})!=len(entries) or sum(e.file_size for e in entries)>100_000_000:raise ValueError('Invalid/oversized archive')
        manifest=json.loads(archive.read('backup_manifest.json'));payload={}
        if manifest.get('schema')!=1:raise ValueError('Unsupported backup schema')
        for e in manifest['files']:
            n=e['path']
            if not re.fullmatch(r'(projects/[a-f0-9]{32}/project\.sqlite3|personal_libraries/[a-f0-9]{32}/index\.sqlite3|configurations/[A-Za-z0-9_.-]+\.json)',n):raise ValueError('Unsafe backup member')
            data=archive.read(n)
            if digest(data)!=e['sha256'] or len(data)!=e['bytes']:raise ValueError('Backup integrity mismatch')
            payload[n]=data
        if set(archive.namelist())!=set(payload)|{'backup_manifest.json'}:raise ValueError('Unlisted archive member')
    return raw,manifest,payload


def prepare_private_restore(backup_path: str, destination: str) -> dict:
    """Preview restoring a checked backup to a fresh private staging folder; never overwrite active indexes/configuration."""
    raw,manifest,_=_backup(backup_path);target=Path(destination).absolute()
    if target.exists() or not target.parent.is_dir() or target.parent.is_symlink() or target.parent.resolve()!=target.parent:raise ValueError('Fresh destination under a physical existing parent required')
    return artifact('private_restore_plan',{'schema':1,'backup_path':str(Path(backup_path).resolve()),'backup_sha256':digest(raw),'destination':str(target),'manifest':manifest})


def apply_private_restore(plan_file: str, expected_sha256: str, dispatch: bool = False) -> dict:
    """Restore an unchanged reviewed archive into a fresh folder; check SQLite integrity and roll back only newly owned files on error."""
    import shutil
    if dispatch is not True:raise ValueError('Explicit restore dispatch required')
    p,raw=read_file(plan_file)
    if digest(raw)!=expected_sha256 or not p.is_relative_to((HERE/'outputs').resolve()) or not p.parent.name.startswith('private_restore_plan_'):raise ValueError('Unchanged generated restore plan required')
    plan=json.loads(raw);raw,manifest,payload=_backup(plan['backup_path'])
    if digest(raw)!=plan['backup_sha256']:raise ValueError('Backup changed after preview')
    target=Path(plan['destination']);parent=target.parent
    if target.exists() or parent.is_symlink() or parent.resolve()!=parent:raise ValueError('Restore destination changed')
    target.mkdir(exist_ok=False)
    try:
        for name,data in payload.items():
            out=target/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
            if out.suffix=='.sqlite3':
                conn=sqlite3.connect(out)
                try:
                    if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity check failed')
                finally:conn.close()
    except Exception:
        if target.resolve().parent==parent.resolve():shutil.rmtree(target)
        raise
    return {'success':True,'state':'restored_private_staging','file_count':len(payload),'active_installation_modified':False}


def validate_adapter_contract(contract: dict) -> dict:
    """Validate a versioned adapter SDK contract without importing or executing third-party code."""
    required={'schema','id','version','license','source','placement','inputs','outputs','resources','invocation','parser','runtime_state'}
    issues=[]
    if not isinstance(contract,dict) or not required<=set(contract):raise ValueError('Incomplete adapter contract')
    if contract['schema']!=1:issues.append('unsupported_schema')
    if contract['placement'] not in {'server','bounded_local'}:issues.append('invalid_placement')
    if contract['runtime_state'] not in {'unverified','synthetic_pass','real_pass','failed'}:issues.append('invalid_runtime_state')
    if not isinstance(contract['invocation'],list) or not contract['invocation'] or any(not isinstance(a,str) or '\x00' in a for a in contract['invocation']):issues.append('invalid_fixed_argv')
    if not isinstance(contract['resources'],dict) or not {'cpus','memory_mb','walltime_minutes'}<=set(contract['resources']):issues.append('missing_resource_limits')
    elif any(type(contract['resources'][k]) is not int or contract['resources'][k]<=0 for k in ('cpus','memory_mb','walltime_minutes')):issues.append('invalid_resource_limits')
    for n in ('inputs','outputs'):
        if not isinstance(contract[n],list) or not contract[n] or any(not isinstance(i,dict) or not {'name','format','required'}<=set(i) for i in contract[n]):issues.append('invalid_'+n)
    for n in ('id','version','license','source','parser'):text(contract[n],1000)
    return {'success':True,'decision':'fail' if issues else 'pass','issues':issues,'contract_sha256':_sha(contract),
        'limitations':['Contract validation does not register executable code, authorize dispatch or validate a scientific method. Fixed adapters require code review and real runtime receipts.']}
