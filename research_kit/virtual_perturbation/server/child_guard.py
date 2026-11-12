"""Bind the specialist child invocation to the same authorized immutable server request."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import read,sha,relative,digest,catalog
from runtime import guard

def verify(job):
    request=read(job['request_path']);guard(request)
    variants={'primary':request['parameters'],**{v['label']:{**request['parameters'],**v['parameters']} for v in request['sensitivity_variants']}}
    p={k:v for k,v in job['parameters'].items() if k!='implementation'}
    if job['method']!=request['method'] or digest(p)!=digest(variants[job['variant']]):raise ValueError('Child method or parameters differ from authorized plan')
    root=Path(job['request_path']).resolve().parent
    spec=catalog()['methods'][request['method']]
    if digest(job['resource_budget'])!=digest(request['resource_budget']) or job['required_roles']!=spec['roles'] or job['implementation']!=spec['implementation'] or job['parameters'].get('implementation')!=spec['implementation']:raise ValueError('Child resources, scientific roles or implementation differ from approved request')
    if Path(job['project_root']).resolve()!=root or Path(job['python_executable']).resolve()!=Path(sys.executable).resolve():raise ValueError('Child root or interpreter differs from owned worker')
    if set(job['inputs'])!={r['id'] for r in request['inputs']}:raise ValueError('Child input scope differs from reviewed request')
    for r in request['inputs']:
        actual=relative(root,r['path'])
        if str(actual)!=job['inputs'][r['id']] or sha(actual)!=r['sha256']:raise ValueError('Child scientific inputs changed')
    if digest(job['context'])!=digest(read(job['inputs']['context'])):raise ValueError('Child scientific context differs from the actual bound input')
    if job['method']=='boolnet':
        review=read(job['inputs']['logical_review'])
        if review.get('network_sha256')!=sha(job['inputs']['network']):raise ValueError('Boolean rule review belongs to another network')
        from logic_contract import boolnet_grammar
        boolnet_grammar(Path(job['inputs']['network']).read_text(encoding='utf-8-sig'))

if __name__=='__main__':verify(read(sys.argv[1]))
