"""Scoped fulltext, incremental source snapshots and independent review ledgers."""
import contextlib
import json
import re
import sqlite3
import uuid
from pathlib import Path
from academic_common import artifact, read_file, digest, rows, text
from evidence import atomic_json

HERE=Path(__file__).resolve().parent


def _identity(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{32}',value):raise ValueError('Use a generated opaque index/search ID')
    return value


def _path(kind,identity):
    root=(HERE/'data'/kind).resolve();path=root/(_identity(identity)+'.json')
    if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Unsafe state path')
    return path


def index_selected_fulltext(pdf_files: list, zotero_snapshot_path: str = '', min_characters_per_page: int = 40) -> dict:
    """Index explicitly selected PDFs and a saved scoped Zotero annotation snapshot with page locators and extraction QC; never upload content or perform implicit OCR."""
    if type(min_characters_per_page) is not int or not 0<=min_characters_per_page<=1000:raise ValueError('Invalid page QC threshold')
    selected=rows(pdf_files,25);identity=uuid.uuid4().hex;units=[];qc=[]
    if not selected and not zotero_snapshot_path:raise ValueError('Select PDFs or an explicit annotation snapshot')
    total=0
    if selected:
        import io
        from pypdf import PdfReader
        for item in selected:
            paper=text(item.get('reference_id'),200);p,raw=read_file(item['path'],20_000_000);source=digest(raw)
            reader=PdfReader(io.BytesIO(raw))
            if reader.is_encrypted or len(reader.pages)>300:raise ValueError('Export a bounded unencrypted PDF')
            for i,page in enumerate(reader.pages,1):
                value=page.extract_text() or '';total+=len(value)
                if total>2_000_000:raise ValueError('Use a server batch for larger fulltext collections')
                low=len(value.strip())<min_characters_per_page
                qc.append({'reference_id':paper,'page':i,'characters':len(value),'state':'ocr_or_manual_review_required' if low else 'text_extracted_not_verified'})
                units.append({'reference_id':paper,'location':'page:'+str(i),'text':value,'source_sha256':source,'kind':'pdf_text','qc':'low_text' if low else 'extracted'})
    if zotero_snapshot_path:
        _,raw=read_file(zotero_snapshot_path,5_000_000);snapshot=json.loads(raw)
        candidates=list(snapshot.get('records',[]))
        for child in snapshot.get('children',[]):candidates.extend(child.get('records',[]))
        for item in rows(candidates,3000):
            data=item.get('data',{})
            if data.get('itemType')!='annotation':continue
            key=text(item.get('key'),200);parent=text(data.get('parentItem'),200)
            for field in ('annotationText','annotationComment'):
                if data.get(field):
                    value=text(data[field],20000);total+=len(value)
                    units.append({'reference_id':parent,'location':'annotation:'+key+':page_label:'+str(data.get('annotationPageLabel','unknown')),
                        'text':value,'source_sha256':digest(raw),'kind':field,'qc':'annotation_source_unverified','position':data.get('annotationPosition')})
    if total>2_000_000 or len(units)>5000:raise ValueError('Use a server batch for larger fulltext collections')
    root=HERE/'data'/'fulltext';root.mkdir(parents=True,exist_ok=True);database=root/(identity+'.sqlite3')
    conn=sqlite3.connect(database)
    try:
        conn.execute('CREATE TABLE units(id INTEGER PRIMARY KEY,reference_id TEXT,location TEXT,text TEXT,source_sha256 TEXT,kind TEXT,qc TEXT,position TEXT)')
        conn.executemany('INSERT INTO units(reference_id,location,text,source_sha256,kind,qc,position) VALUES(?,?,?,?,?,?,?)',
            [(u['reference_id'],u['location'],u['text'],u['source_sha256'],u['kind'],u['qc'],json.dumps(u.get('position'))) for u in units]);conn.commit()
    finally:conn.close()
    return artifact('fulltext_index',{'index_id':identity,'unit_count':len(units),'qc':qc,
        'limitations':['Extracted text and annotations are private. Page labels in annotations are not necessarily physical PDF page numbers. No OCR, whole-library scan or evidence assessment has occurred.']})


def search_selected_fulltext(index_id: str, query: str, reference_ids: list = None, limit: int = 25) -> dict:
    """Search a selected private index by literal text and return page/annotation positions, hashes and nearby text."""
    identity=_identity(index_id);query=text(query,500)
    if type(limit) is not int or not 1<=limit<=100:raise ValueError('Bounded result limit required')
    root=(HERE/'data'/'fulltext').resolve();p=root/(identity+'.sqlite3')
    if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Missing private fulltext index')
    conn=sqlite3.connect(p);conn.row_factory=sqlite3.Row
    try:
        expression=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_');params=['%'+expression+'%'];sql="SELECT * FROM units WHERE text LIKE ? ESCAPE '\\'"
        if reference_ids:
            if len(reference_ids)>100:raise ValueError('Bounded reference scope required')
            sql+=' AND reference_id IN ('+','.join('?' for _ in reference_ids)+')';params+=reference_ids
        found=[dict(r) for r in conn.execute(sql+' LIMIT ?',params+[limit+1])]
        for r in found[:limit]:
            offset=r['text'].casefold().find(query.casefold());r['match_offset']=offset
            r['excerpt']=r.pop('text')[max(0,offset-150):offset+len(query)+300]
        return {'success':True,'records':found[:limit],'truncated':len(found)>limit,'matching':'literal_phrase',
            'limitations':['Search does not establish source support. Inspect negation, model, assay and outcome in the original page. OCR gaps remain searchable coverage gaps.']}
    finally:conn.close()


def prepare_zotero_incremental_sync(library_id: str, snapshot_path: str, source_namespace: str, scope: dict) -> dict:
    """Preview incremental metadata ingestion from an explicitly scoped saved Zotero snapshot; preserve notes/tags/history and never delete missing entries."""
    import personal_library_ext as personal
    _,raw=read_file(snapshot_path,20_000_000);snapshot=json.loads(raw)
    if snapshot.get('source')!='local_zotero' or not isinstance(scope,dict) or not (scope.get('collection_key') or scope.get('item_keys')):
        raise ValueError('Explicit local Zotero snapshot and collection/item scope required')
    if scope.get('library')!=snapshot.get('library') or scope.get('collection_key','')!=snapshot.get('collection_key',''):
        raise ValueError('Snapshot does not match selected source scope')
    if scope.get('item_keys') and any(r['key'] not in scope['item_keys'] for r in snapshot.get('records',[])):
        raise ValueError('Snapshot contains items outside selected keys')
    plan=personal.prepare_personal_library_ingest(library_id,snapshot_path,source_namespace)
    conflicts=[]
    for change in plan['changes']:
        before=change.get('before')
        if before and change['action']=='update':
            old=json.loads(before['data']).get('source_fields',{});new=change['data'].get('source_fields',{})
            if old.get('version',0)>new.get('version',0):conflicts.append({'id':change['id'],'issue':'source_version_regressed'})
    return artifact('zotero_incremental_sync',{'ingest_plan_file':plan['output_directory']+'/review.json','ingest_plan_sha256':digest(Path(plan['output_directory'],'review.json').read_bytes()),
        'scope':scope,'coverage_complete':bool(snapshot.get('coverage_complete')),'conflicts':conflicts,'sync_state':'blocked' if conflicts else 'review_required',
        'changes':[{'id':c['id'],'action':c['action']} for c in plan['changes']],
        'limitations':['This updates the separate private index only after explicit apply. It does not write Zotero or synchronize to a cloud service. Missing entries are retained. Partial snapshot coverage is not deletion evidence.']})


def apply_zotero_incremental_sync(plan_file: str, expected_sha256: str, dispatch: bool = False) -> dict:
    """Apply a reviewed conflict-free incremental index plan; never write the source Zotero library."""
    import personal_library_ext as personal
    p,raw=read_file(plan_file)
    if dispatch is not True or digest(raw)!=expected_sha256 or not p.is_relative_to((HERE/'outputs').resolve()) or not p.parent.name.startswith('zotero_incremental_sync_'):
        raise ValueError('Explicit unchanged generated sync plan required')
    plan=json.loads(raw)
    if plan['conflicts']:raise ValueError('Resolve source-version conflicts before ingestion')
    return personal.apply_personal_library_ingest(plan['ingest_plan_file'],plan['ingest_plan_sha256'],True)


def create_review_search(public_queries: list, public_query_authorized: bool = False) -> dict:
    """Create a private resumable Europe PMC search ledger for exact approved public queries; no retrieval yet."""
    from privacy_ext import enforce_outbound
    if public_query_authorized is not True or not isinstance(public_queries,list) or not 1<=len(public_queries)<=10:raise ValueError('Approve exact public queries')
    queries=[text(q,1000) for q in public_queries];enforce_outbound({'queries':queries});identity=uuid.uuid4().hex
    state={'schema':1,'id':identity,'revision':0,'queries':[{'query':q,'cursor':'*','hit_count':None,'returned':0,'complete':False,'pages':[]} for q in queries],'records':{},'decisions':[],'resolutions':[]}
    atomic_json(_path('review_searches',identity),state)
    return {'success':True,'search_id':identity,'revision':0,'state':'approved_queries_saved_no_retrieval'}


@contextlib.contextmanager
def _search(identity,expected_revision):
    path=_path('review_searches',identity)
    if not path.is_file():raise ValueError('Missing selected search')
    lock=path.with_suffix('.lock')
    try:
        stream=lock.open('x');stream.close()
    except FileExistsError:raise ValueError('Search is locked; inspect current process before recovery')
    try:
        state=json.loads(path.read_text(encoding='utf8'))
        if state['revision']!=expected_revision:raise ValueError('Search revision conflict')
        yield state
        state['revision']+=1;atomic_json(path,state)
    finally:lock.unlink()


def retrieve_review_search_page(search_id: str, query_index: int, expected_revision: int, page_size: int = 50,
                               public_query_authorized: bool = False) -> dict:
    """Retrieve one approved cursor page and atomically persist coverage and source records; failed pages do not advance the cursor."""
    from literature_ext import query_europepmc
    from privacy_ext import enforce_outbound
    if public_query_authorized is not True or type(page_size) is not int or not 1<=page_size<=100:raise ValueError('Explicit public retrieval authorization and bounded page required')
    with _search(search_id,expected_revision) as state:
        if type(query_index) is not int or not 0<=query_index<len(state['queries']):raise ValueError('Unknown query index')
        q=state['queries'][query_index]
        if q['complete']:raise ValueError('Selected query is already exhausted')
        enforce_outbound({'query':q['query']})
        response=query_europepmc(q['query'],page_size,q['cursor'])
        if not response.get('success'):raise RuntimeError('Search failed; cursor retained')
        result=response['result'];found=rows(result.get('resultList',{}).get('result',[]),100)
        if len(state['records'])+len(found)>10000:raise ValueError('Server retrieval required beyond 10000 records')
        next_cursor=result.get('nextCursorMark');hit=int(result['hitCount'])
        for r in found:state['records'][str(r['source'])+':'+str(r['id'])]=r
        q['pages'].append({'cursor':q['cursor'],'next_cursor':next_cursor,'returned':len(found),'response_sha256':digest(json.dumps(result,sort_keys=True).encode()),'hit_count':hit})
        q['returned']+=len(found);q['hit_count']=hit
        exhausted=not found or q['returned']>=hit
        if not exhausted and (not next_cursor or next_cursor==q['cursor']):raise ValueError('Cursor did not advance; coverage remains incomplete')
        q['complete']=exhausted;q['cursor']=next_cursor or q['cursor']
        summary={'success':True,'search_id':search_id,'revision':expected_revision+1,'query_coverage':state['queries'],'unique_records':len(state['records']),
            'limitations':['Database coverage and eligibility remain separate. Search terms and hit counts may change over time; page receipts retain the history.']}
    return summary


def record_independent_screening(search_id: str, expected_revision: int, record_id: str, reviewer_id: str,
                                 decision: str, reason: str, independent_review_attested: bool = False) -> dict:
    """Record one actual reviewer decision with identity and independence attestation; never invent a second reviewer."""
    if decision not in {'include','exclude','uncertain'} or independent_review_attested is not True:raise ValueError('Explicit independent reviewer attestation and decision required')
    reviewer_id=text(reviewer_id,200);reason=text(reason,3000)
    with _search(search_id,expected_revision) as state:
        if record_id not in state['records']:raise ValueError('Record outside selected search')
        if any(d['record_id']==record_id and d['reviewer_id']==reviewer_id for d in state['decisions']):raise ValueError('Reviewer decision already recorded; retain history and use resolution')
        state['decisions'].append({'record_id':record_id,'reviewer_id':reviewer_id,'decision':decision,'reason':reason,'independence_attested':True})
    return {'success':True,'revision':expected_revision+1,'record_id':record_id,'state':'decision_saved'}


def resolve_screening_conflict(search_id: str, expected_revision: int, record_id: str, resolver_id: str,
                               decision: str, rationale: str) -> dict:
    """Save an explicit adjudication after at least two different reviewers have disagreed; preserve original decisions."""
    if decision not in {'include','exclude','uncertain'}:raise ValueError('Invalid adjudication')
    with _search(search_id,expected_revision) as state:
        selected=[d for d in state['decisions'] if d['record_id']==record_id]
        if len({d['reviewer_id'] for d in selected})<2 or len({d['decision'] for d in selected})<2:raise ValueError('No independently recorded conflict to resolve')
        state['resolutions'].append({'record_id':record_id,'resolver_id':text(resolver_id,200),'decision':decision,'rationale':text(rationale,3000),'original_decisions':selected})
    return {'success':True,'revision':expected_revision+1,'state':'adjudication_recorded'}


def inspect_review_search(search_id: str) -> dict:
    """Inspect saved retrieval coverage, outstanding second reviews and conflicts; no public request."""
    state=json.loads(_path('review_searches',search_id).read_text(encoding='utf8'));pending=[];conflicts=[]
    for identity in state['records']:
        decisions=[d for d in state['decisions'] if d['record_id']==identity]
        if len({d['reviewer_id'] for d in decisions})<2:pending.append(identity)
        elif len({d['decision'] for d in decisions})>1 and not any(r['record_id']==identity for r in state['resolutions']):conflicts.append(identity)
    return artifact('review_search_inspection',{'search':state,'pending_independent_second_review':pending,'unresolved_conflicts':conflicts,
        'limitations':['Stored attestation is not proof of independence or eligibility. Review original full text and document exclusions. This does not calculate risk of bias or GRADE automatically.']})
