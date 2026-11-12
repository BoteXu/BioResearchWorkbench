"""Fixed native child. Requires an actually isolated Linux network namespace."""
from pathlib import Path
import os,sys,platform
from runtime import read,write,sha

def main(request_file,out):
    if sys.platform!='linux' or 'microsoft' in platform.release().lower() or set(p.name for p in Path('/sys/class/net').iterdir())!={'lo'}:raise RuntimeError('Native scientific child requires the actual network namespace with loopback only; no network-enabled fallback')
    if not (os.environ.get('SLURM_JOB_ID') or os.environ.get('SSH_CONNECTION')):raise RuntimeError('Existing server execution context required')
    request=read(request_file);sources={p.name:sha(p) for p in Path(__file__).parent.iterdir() if p.is_file() and p.suffix in {'.py','.R','.json'}}
    if request['source_sha256']!=sources:raise ValueError('Scientific child source changed')
    ids={k:Path(v['path']).resolve(strict=True) for k,v in request['inputs'].items()}
    for k,v in request['inputs'].items():
        if sha(ids[k])!=v['sha256']:raise ValueError('Scientific child input changed')
    os.environ['BRW_ISOLATED_NATIVE_CHILD']='1';sys.dont_write_bytecode=True
    from completion_runtime import execute_isolated
    outputs=execute_isolated(ids,request['parameters'],out,request['mode'])
    write(out/'native_child_outputs.private.json',{'mode':request['mode'],'isolated_network':True,'outputs':[{'path':Path(p).relative_to(out).as_posix(),'role':role} for p,role in outputs]})

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('completion_child.py PRIVATE_REQUEST FRESH_PARENT_OUTPUT')
    main(Path(sys.argv[1]).resolve(strict=True),Path(sys.argv[2]).resolve(strict=True))
