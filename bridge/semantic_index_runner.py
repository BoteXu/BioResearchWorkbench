"""Explicit one-time source-scoped Qdrant ingest; dependency environment and model cache supplied by owner."""
import argparse
import hashlib
import json
import uuid
from pathlib import Path
from qdrant_readonly import provider


def run(plan_path,reviewed_sha256,cache):
    path=Path(plan_path).resolve(strict=True);raw=path.read_bytes()
    if len(raw)>3_000_000 or hashlib.sha256(raw).hexdigest()!=reviewed_sha256:raise ValueError('Reviewed bounded plan hash required')
    plan=json.loads(raw)
    if plan.get('schema')!=1 or not 1<=len(plan.get('records',[]))<=200:raise ValueError('Unsupported bounded plan')
    root=Path(plan['index_path'])
    if root.exists() or not root.is_absolute() or any(p.is_symlink() for p in root.parents):raise ValueError('Fresh private index path required')
    ledger=path.with_name('index_execution_receipt.json')
    with ledger.open('x',encoding='utf8') as f:json.dump({'state':'execution_outcome_unknown','plan_sha256':reviewed_sha256},f)
    from qdrant_client import QdrantClient,models
    model=provider(Path(cache).resolve(strict=True));dimension=model.get_vector_size();vector_name=model.get_vector_name()
    client=QdrantClient(path=str(root))
    try:
        client.create_collection(plan['collection'],vectors_config={vector_name:models.VectorParams(size=dimension,distance=models.Distance.COSINE)})
        records=plan['records'];vectors=list(model.embedding_model.passage_embed([r['text'] for r in records]))
        points=[]
        for r,vec in zip(records,vectors):
            if hashlib.sha256(r['text'].encode()).hexdigest()!=r['text_sha256']:raise ValueError('Source hash mismatch')
            metadata={k:v for k,v in r.items() if k!='text'}
            points.append(models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL,r['id'])),vector={vector_name:vec.tolist()},payload={'document':r['text'],'metadata':metadata}))
        client.upsert(plan['collection'],points=points,wait=True)
        count=client.count(plan['collection'],exact=True).count
        if count!=len(records):raise ValueError('Index acceptance count mismatch')
    finally:client.close()
    receipt={'state':'indexed','plan_sha256':reviewed_sha256,'record_count':count,'model':plan['model'],'source_bindings':[{k:r[k] for k in ['id','text_sha256','source_version']} for r in records],'scientific_validation':False}
    ledger.write_text(json.dumps(receipt,indent=2),encoding='utf8');return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan');p.add_argument('--reviewed-sha256',required=True);p.add_argument('--cache',required=True);a=p.parse_args()
    run(a.plan,a.reviewed_sha256,a.cache);print('SCOPED_INDEX_COMPLETION_RECEIPT_WRITTEN')
