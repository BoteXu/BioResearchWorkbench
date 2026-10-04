"""Prepare explicitly scoped private semantic indexing; no implicit library scans or uploads."""
import json
import re
from pathlib import Path
from academic_common import artifact, digest, rows, text


def prepare_semantic_index(records: list, collection: str, index_path: str, authorized_source_scope: bool = False) -> dict:
    """Build a reviewed, source-hashed bounded index plan; large embedding workloads belong on the server."""
    if authorized_source_scope is not True:raise ValueError('Specific source-scope authorization required')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',collection):raise ValueError('Explicit collection name required')
    path=Path(index_path).expanduser()
    if path.exists() or not path.is_absolute() or any(p.is_symlink() for p in path.parents):raise ValueError('Fresh absolute private index path required')
    selected=rows(records,200)
    if not selected:raise ValueError('Select source records explicitly')
    ids=set();entries=[]
    for row in selected:
        if set(row)!={'id','text','source_version','source_location'}:raise ValueError('Source ID, text, version and location required')
        rid=text(row['id'],200)
        if rid in ids:raise ValueError('Duplicate source ID')
        ids.add(rid);body=text(row['text'],20000)
        entries.append({**row,'id':rid,'text':body,'source_version':text(row['source_version'],200),'source_location':text(row['source_location'],1000),'text_sha256':digest(body.encode())})
    if sum(len(r['text'].encode()) for r in entries)>2_000_000:raise ValueError('Bounded index plan exceeded; prepare large indexing on server')
    plan={'schema':1,'collection':collection,'index_path':str(path),'model':'sentence-transformers/all-MiniLM-L6-v2','records':entries}
    raw=json.dumps(plan,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    return artifact('semantic_index_plan',{'state':'prepared','plan_sha256':digest(raw.encode()),'record_count':len(entries),
            'limitations':['Execute the fixed runner only after reviewing this exact source-scoped plan.','Model files must be provisioned separately; the runner uses offline embedding only.','Do not ingest an entire library or interpret similarity as scientific evidence.']},
            {'index_plan.json':raw,'semantic_index_runner.py':Path(__file__).with_name('semantic_index_runner.py').read_bytes(),'qdrant_readonly.py':Path(__file__).with_name('qdrant_readonly.py').read_bytes(),
             'mcp_embedding_model.json':(Path(__file__).with_name('mcp_embedding_model.json') if Path(__file__).with_name('mcp_embedding_model.json').exists() else Path(__file__).resolve().parent.parent/'mcp_embedding_model.json').read_bytes()})


def audit_semantic_results(results: list, source_records: list) -> dict:
    """Verify returned semantic-hit source IDs, versions and text hashes against an explicit source snapshot."""
    records=rows(source_records,200);sources={r['id']:r for r in records}
    if len(sources)!=len(records):raise ValueError('Duplicate source identifiers')
    checked=[]
    for row in rows(results,100):
        metadata=row.get('metadata',{});source=sources.get(metadata.get('id'));issues=[]
        if source is None:issues.append('source_not_in_scope')
        else:
            if metadata.get('text_sha256')!=digest(source['text'].strip().encode()):issues.append('source_hash_mismatch')
            if metadata.get('source_version')!=source['source_version']:issues.append('source_version_mismatch')
        checked.append({'source_id':metadata.get('id'),'issues':issues,'source_binding_consistent':not issues})
    return {'success':True,'results':checked,'all_source_bindings_consistent':all(not r['issues'] for r in checked),
            'limitations':['Source binding and embedding similarity do not establish that a paper supports a claim.','Review located source text, species, model, assay and outcome before interpretation.']}
