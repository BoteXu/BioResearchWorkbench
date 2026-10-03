"""Private research-library index beside Zotero; explicit ingest plans, local search and reading notes."""
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from academic_common import HERE, artifact, digest, read_file, rows, text
from evidence import utc
from library_ext import load_library


def _folder(library_id):
    if not isinstance(library_id,str) or not re.fullmatch(r'[0-9a-f]{32}',library_id):raise ValueError('Provide a generated personal-library ID')
    return HERE/'data'/'personal_libraries'/library_id


@contextmanager
def _db(library_id):
    p=_folder(library_id)/'index.sqlite3'
    if not p.is_file():raise ValueError('Personal library does not exist')
    if p.is_symlink() or p.parent.is_symlink() or not p.resolve().is_relative_to((HERE/'data'/'personal_libraries').resolve()):raise ValueError('Private index must stay within its owned data folder')
    conn=sqlite3.connect(p,timeout=15);conn.row_factory=sqlite3.Row
    try:
        meta=dict(conn.execute('SELECT key,value FROM metadata'))
        if meta.get('schema')!='1' or meta.get('library_id')!=library_id:raise ValueError('Personal library identity/schema mismatch')
        yield conn,meta
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()


def _canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def _hash(value):return digest(_canonical(value).encode())
def _tags(value):
    if not isinstance(value,list) or len(value)>30:raise ValueError('Provide up to 30 private tags')
    return sorted(set(text(t,100) for t in value))


def create_personal_library(title: str, purpose: str, set_as_default: bool = False) -> dict:
    """Create a fresh private SQLite research index with an opaque ID; do not read/import Zotero or configure cloud synchronization."""
    default=HERE/'data'/'personal_library_default.json'
    if type(set_as_default) is not bool or set_as_default and default.exists():raise ValueError('Default index already configured; select it explicitly instead of overwriting')
    title=text(title,500);purpose=text(purpose,3000);identity=uuid.uuid4().hex;folder=_folder(identity);folder.mkdir(parents=True)
    conn=sqlite3.connect(folder/'index.sqlite3')
    try:
        conn.executescript('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE refs(id TEXT PRIMARY KEY,namespace TEXT NOT NULL,source_id TEXT NOT NULL,data TEXT NOT NULL,fingerprint TEXT NOT NULL,tags TEXT NOT NULL,state TEXT NOT NULL,note TEXT NOT NULL,search_text TEXT NOT NULL); CREATE TABLE history(time TEXT NOT NULL,id TEXT NOT NULL,action TEXT NOT NULL,before_json TEXT);')
        conn.executemany('INSERT INTO metadata VALUES(?,?)',[('schema','1'),('library_id',identity),('title',title),('purpose',purpose),('revision','0')]);conn.commit()
    finally:conn.close()
    if set_as_default:
        with default.open('x',encoding='utf8') as f:json.dump({'library_id':identity},f)
    return {'success':True,'library_id':identity,'title':title,'purpose':purpose,'revision':0,
        'limitations':['This private index is separate from the Zotero source library. No source data has been imported.','It has no public API or automatic synchronization. Backups and artifacts must remain private.']}


def inspect_personal_library(library_id: str = '') -> dict:
    """Read explicit/default private index metadata and reading-state counts without returning paper content or notes."""
    if not library_id:
        default=HERE/'data'/'personal_library_default.json'
        if not default.exists():return {'success':False,'state':'not_configured'}
        library_id=json.loads(default.read_text(encoding='utf8'))['library_id']
    with _db(library_id) as (conn,meta):
        states={r[0]:r[1] for r in conn.execute('SELECT state,COUNT(*) FROM refs GROUP BY state')}
        return {'success':True,'library_id':library_id,'title':meta['title'],'purpose':meta['purpose'],'revision':int(meta['revision']),'reading_state_counts':states,
                'limitations':['This reports index metadata only. No source library scan, note retrieval or network call occurs.']}


def prepare_personal_library_ingest(library_id: str, references_path: str, source_namespace: str, tags: list = None) -> dict:
    """Preview a bounded reference snapshot with source-scoped IDs, updates and duplicate-DOI candidates; apply nothing."""
    if not isinstance(source_namespace,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,60}',source_namespace):raise ValueError('Provide a stable source namespace')
    records,source=load_library(references_path);tags=_tags(tags or []);changes=[];duplicates=[]
    with _db(library_id) as (conn,meta):
        existing={r['id']:dict(r) for r in conn.execute('SELECT * FROM refs')};dois={}
        new_ids={source_namespace+'::'+r['id'] for r in records}-set(existing)
        if len(existing)+len(new_ids)>10000:raise ValueError('Bounded private index supports at most 10000 records; split research collections')
        for r in existing.values():
            doi=json.loads(r['data']).get('doi')
            if doi:dois.setdefault(doi,[]).append(r['id'])
        for r in records:
            identity=source_namespace+'::'+r['id'];data={**r,'id':identity,'source_id':r['id'],'source_namespace':source_namespace};fingerprint=_hash(data)
            before=existing.get(identity)
            if data.get('doi'):
                same=[k for k in dois.get(data['doi'],[]) if k!=identity]
                if same:duplicates.append({'record_id':identity,'other_ids':same,'doi':data['doi'],'state':'review_required_no_merge'})
                dois.setdefault(data['doi'],[]).append(identity)
            action='insert' if before is None else 'unchanged' if before['fingerprint']==fingerprint and set(tags)<=set(json.loads(before['tags'])) else 'update'
            changes.append({'id':identity,'action':action,'data':data,'fingerprint':fingerprint,'before':before,'tags':tags})
        return artifact('personal_ingest_plan',{'schema':1,'library_id':library_id,'source_namespace':source_namespace,'source':source,'expected_revision':int(meta['revision']),
            'changes':changes,'duplicate_candidates':duplicates,
            'limitations':['No records have been applied or merged. Updates are scoped to the same namespace/source ID.','Missing records in a partial snapshot are never treated as deletions. Review duplicates, versions and library source before dispatch.']})


def apply_personal_library_ingest(plan_file: str, expected_sha256: str, dispatch: bool = False) -> dict:
    """Atomically apply an unchanged reviewed private ingest plan with revision/conflict checks and history; never modify Zotero."""
    if dispatch is not True:raise ValueError('Explicitly dispatch the reviewed local ingest plan')
    p,raw=read_file(plan_file,30_000_000)
    if digest(raw)!=expected_sha256:raise ValueError('Reviewed ingest plan hash mismatch')
    if not p.is_relative_to((HERE/'outputs').resolve()) or p.name!='review.json' or not p.parent.name.startswith('personal_ingest_plan_'):raise ValueError('Use a generated private ingest plan')
    plan=json.loads(raw)
    if plan.get('schema')!=1:raise ValueError('Unsupported ingest schema')
    changes=rows(plan.get('changes'),5000);counts={'insert':0,'update':0,'unchanged':0}
    with _db(plan['library_id']) as (conn,meta):
        conn.execute('BEGIN IMMEDIATE');revision=int(conn.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0])
        if revision!=plan['expected_revision']:raise ValueError('Personal index changed since preview; prepare a new plan')
        for c in changes:
            if c.get('action') not in counts or c.get('fingerprint')!=_hash(c.get('data')):raise ValueError('Invalid ingest action/data fingerprint')
            current=conn.execute('SELECT * FROM refs WHERE id=?',(c['id'],)).fetchone()
            if (dict(current) if current else None)!=c.get('before'):raise ValueError('Record changed since ingest preview')
            counts[c['action']]+=1
            if c['action']=='unchanged':continue
            before=dict(current) if current else None;tags=sorted(set(_tags(c.get('tags',[]))+(json.loads(current['tags']) if current else [])))
            state=current['state'] if current else 'unread';note=current['note'] if current else '';data=c['data']
            if data.get('id')!=c['id'] or data.get('source_namespace')!=plan['source_namespace']:raise ValueError('Ingest source identity mismatch')
            conn.execute('INSERT INTO history VALUES(?,?,?,?)',(utc(),c['id'],c['action'],_canonical(before) if before else None))
            conn.execute('INSERT OR REPLACE INTO refs VALUES(?,?,?,?,?,?,?,?,?)',(c['id'],data['source_namespace'],data['source_id'],_canonical(data),c['fingerprint'],_canonical(tags),state,note,(_canonical(data)+' '+note).casefold()))
        if conn.execute('SELECT COUNT(*) FROM refs').fetchone()[0]>10000:raise ValueError('Private index size exceeds bounded limit')
        conn.execute("UPDATE metadata SET value=? WHERE key='revision'",(str(revision+1),))
    return artifact('personal_ingest_receipt',{'library_id':plan['library_id'],'revision':revision+1,'counts':counts,'plan_sha256':expected_sha256,
        'limitations':['Only the private index changed. Zotero, exported source files and original papers remain unchanged.','Duplicate-DOI records remain distinct. History records support local recovery; no scientific eligibility judgment is inferred.']})


def search_personal_library(library_id: str, query: str = '', tags: list = None, reading_state: str = '', limit: int = 50, start: int = 0) -> dict:
    """Search one explicit private index by literal phrase/tags/reading state with bounded pagination; no online semantic service."""
    if not isinstance(query,str) or len(query)>500 or type(limit) is not int or not 1<=limit<=100 or type(start) is not int or start<0:raise ValueError('Select bounded private search/pagination')
    if reading_state not in {'','unread','reading','reviewed','excluded'}:raise ValueError('Invalid reading state')
    tags=_tags(tags or []);records=[]
    with _db(library_id) as (conn,meta):
        pattern='%'+query.casefold().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        found=conn.execute("SELECT * FROM refs WHERE search_text LIKE ? ESCAPE '\\' ORDER BY id",(pattern,)).fetchall()
        for r in found:
            rowtags=json.loads(r['tags'])
            if not set(tags)<=set(rowtags) or reading_state and r['state']!=reading_state:continue
            records.append({**json.loads(r['data']),'tags':rowtags,'reading_state':r['state'],'private_note':r['note'],'fingerprint':r['fingerprint']})
        total=len(records)
        return artifact('personal_library_search',{'library_id':library_id,'revision':int(meta['revision']),'records':records[start:start+limit],'total_results':total,
            'next_start':start+limit if start+limit<total else None,'coverage_complete':start==0 and total<=limit,
            'limitations':['Literal phrase search is not vector/semantic retrieval or exhaustive external literature discovery.','Private notes and metadata remain local. A partial page must not be labeled complete.']})


def annotate_personal_reference(library_id: str, record_id: str, expected_fingerprint: str, expected_revision: int, reading_state: str, tags: list, note: str) -> dict:
    """Update explicit private reading state/tags/note with conflict checks and retained before history; no Zotero/cloud write."""
    text(record_id,300)
    if reading_state not in {'unread','reading','reviewed','excluded'} or not isinstance(note,str) or len(note)>30000 or type(expected_revision) is not int:raise ValueError('Provide explicit bounded annotation/state')
    tags=_tags(tags)
    with _db(library_id) as (conn,meta):
        conn.execute('BEGIN IMMEDIATE');revision=int(conn.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0]);r=conn.execute('SELECT * FROM refs WHERE id=?',(record_id,)).fetchone()
        if r is None or revision!=expected_revision or r['fingerprint']!=expected_fingerprint:raise ValueError('Reference/index changed since review')
        conn.execute('INSERT INTO history VALUES(?,?,?,?)',(utc(),record_id,'annotate',_canonical(dict(r))))
        conn.execute('UPDATE refs SET tags=?,state=?,note=?,search_text=? WHERE id=?',(_canonical(tags),reading_state,note,(r['data']+' '+note).casefold(),record_id))
        conn.execute("UPDATE metadata SET value=? WHERE key='revision'",(str(revision+1),))
    return {'success':True,'library_id':library_id,'record_id':record_id,'revision':revision+1,'reading_state':reading_state,
        'limitations':['Reading state is caller-declared, not scientific evidence validation. This update remains in the private index only.']}


def export_personal_library(library_id: str, output_format: str, query: str = '', tags: list = None, limit: int = 100) -> dict:
    """Export an explicit bounded private selection to RIS/BibTeX/CSL-JSON, retaining partial coverage; no public upload."""
    from library_ext import export_reference_library
    found=search_personal_library(library_id,query,tags,limit=limit)
    path=str(__import__('pathlib').Path(found['output_directory'])/'review.json')
    result=export_reference_library(path,output_format)
    result['selection_coverage_complete']=found['coverage_complete'];result['selection_total_results']=found['total_results']
    return result
