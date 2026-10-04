"""Create an explicit digest-pinned static gateway candidate; never enroll or launch containers automatically."""
import argparse
import hashlib
import json
from pathlib import Path

IMAGE='mcp/fetch@sha256:1a7a0996a565a0b8ca5c41b42830d4e5f334d33f851596bbd9debb2beedb22d3'


def prepare(output_dir,catalog_dir=None):
    out=Path(output_dir)
    if out.exists():raise ValueError('Fresh private gateway profile directory required')
    catalog_root=Path(catalog_dir) if catalog_dir else Path.home()/'.docker'/'mcp'/'catalogs'
    if any(p.is_symlink() for p in [catalog_root,*catalog_root.parents]):raise ValueError('Linked catalog roots refused')
    catalog_root.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True)
    catalog={'name':'workbench-pinned-fetch','displayName':'Workbench pinned public fetch','registry':{'fetch':{'title':'Public fetch only','description':'Explicit public URLs only; never send private paths, queries or content.','type':'server','image':IMAGE,'tools':[{'name':'fetch'}],'env':[],'secrets':[],'volumes':[]}}}
    raw=json.dumps(catalog,indent=2);sha=hashlib.sha256(raw.encode()).hexdigest();path=catalog_root/('workbench-'+sha[:16]+'.yaml')
    if path.exists() and path.read_text()!=raw:raise ValueError('Catalog revision conflict')
    if not path.exists():path.write_text(raw,encoding='utf8')  # JSON is a strict YAML subset.
    secrets=out/'empty-secrets.env';secrets.write_text('',encoding='utf8')
    config=out/'empty-config.yaml';config.write_text('{}',encoding='utf8')
    argv=['mcp','gateway','run','--catalog',str(path.resolve()),'--config',str(config.resolve()),'--secrets',str(secrets.resolve()),'--servers','fetch','--tools','fetch','--transport','stdio','--cpus','1','--memory','256Mb','--block-secrets','--block-network','--log-calls=false','--watch=false','--static']
    data={'schema':1,'private':True,'runtime_acceptance':'required','image':IMAGE,'catalog_sha256':sha,'mcpServers':{'brw-docker-gateway':{'command':'docker','args':argv}}}
    (out/'gateway-candidate.private.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    return data


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);a=p.parse_args();prepare(a.output_dir)
    print('PINNED_STATIC_GATEWAY_CANDIDATE_PREPARED; ENGINE_AND_TOOL_ACCEPTANCE_REQUIRED')
