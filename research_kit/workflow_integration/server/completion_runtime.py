"""Native routes dispatched after the existing exact server runtime guard."""
from pathlib import Path
import sys
import os
import platform
from completion_contracts import ROUTES,validate
from completion_common import context,versions,repo_binding,license_check,offline_python,prove_outputs,native_command
from runtime import read,write,sha

def analyze(ids,p,out,mode):
    if sys.platform!='linux' or 'microsoft' in platform.release().lower() or not (os.environ.get('SLURM_JOB_ID') or os.environ.get('SSH_CONNECTION')):raise RuntimeError('Use the existing allocated server; no local native scientific execution')
    validate(mode,p,ids)
    request=out/'native_child_request.private.json'
    write(request,{'mode':mode,'parameters':p,'inputs':{k:{'path':str(v),'sha256':sha(v)} for k,v in ids.items()},'source_sha256':{q.name:sha(q) for q in Path(__file__).parent.iterdir() if q.is_file() and q.suffix in {'.py','.R','.json'}}})
    log=native_command([sys.executable,Path(__file__).with_name('completion_child.py'),request,out],out,'native_isolated_child')
    returned=read(out/'native_child_outputs.private.json')
    if returned.get('mode')!=mode or returned.get('isolated_network') is not True:raise ValueError('Actual offline scientific child did not return the expected binding')
    outputs=[(out/row['path'],row['role']) for row in returned['outputs']]
    outputs.extend([(request,'native_internal_request'),(out/'native_child_outputs.private.json','native_internal_receipt'),(log,'native_launcher_log')])
    return outputs

def execute_isolated(ids,p,out,mode):
    # Called only by the fixed child after checking the actual network namespace.
    if sys.platform!='linux' or 'microsoft' in platform.release().lower() or os.environ.get('BRW_ISOLATED_NATIVE_CHILD')!='1' or not (os.environ.get('SLURM_JOB_ID') or os.environ.get('SSH_CONNECTION')) or set(q.name for q in Path('/sys/class/net').iterdir())!={'lo'}:raise RuntimeError('Actual isolated server child required; direct/local model entry is disabled')
    validate(mode,p,ids);ctx=context(ids);versions(p);source=repo_binding(mode,p);licenses=license_check(ids,mode,source)
    if source:
        repo=Path(source['path']);sys.path.insert(0,str(repo/'src' if mode=='stack_incontext' else repo))
    else:repo=None
    offline_python()
    if mode in {'gnps_offline_network','sirius_formulas','csi_result_import'}:
        from completion_spectra import gnps,sirius,csi_import
        outputs,metrics=gnps(ids,p,out,repo) if mode=='gnps_offline_network' else sirius(ids,p,out) if mode=='sirius_formulas' else csi_import(ids,p,out)
    elif mode in {'diann_quantify','magpie_coregister','dockovalent'}:
        from completion_engines import diann,magpie,dockovalent
        outputs,metrics=magpie(ids,p,out,repo) if mode=='magpie_coregister' else diann(ids,p,out) if mode=='diann_quantify' else dockovalent(ids,p,out)
    else:
        from completion_models import prnet,scdiffusion,squidiff,stack,cellnavi,morphdiff
        kind=ROUTES[mode]['kind']
        if mode=='prnet_predict':outputs,metrics=prnet(ids,p,out,kind)
        elif mode=='scdiffusion_generate':outputs,metrics=scdiffusion(ids,p,out,kind)
        elif mode=='squidiff_predict':outputs,metrics=squidiff(ids,p,out,kind)
        elif mode=='stack_incontext':outputs,metrics=stack(ids,p,out,kind)
        elif mode=='cellnavi_drivers':outputs,metrics=cellnavi(ids,p,out,kind,repo)
        elif mode.startswith('morphdiff_'):outputs,metrics=morphdiff(ids,p,out,kind,mode)
        else:raise ValueError('Unknown fixed native model route')
    if source and repo_binding(mode,p)!=source:raise ValueError('Author source changed during native inference')
    return prove_outputs(out,outputs,mode,p,metrics,source,licenses,ctx)
