"""Run only reviewed fixed plotting argv on the existing authorized server."""
from pathlib import Path
import sys,subprocess,shutil,os,socket,platform
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import read,sha,write,digest
from server.anndata_snapshot import guard
def run(plan_path,out):
    p=read(plan_path);guard(p);root=Path(plan_path).resolve().parent
    if p['review_sha256']!=digest({k:v for k,v in p.items() if k not in ('dispatch_authorized','review_sha256')}):raise ValueError('Reviewed native plan changed; bind exact host/software configuration before dispatch')
    expected=['pyGenomeTracks','--tracks','tracks.ini','--region'] if p['backend']=='pyGenomeTracks' else ['Rscript','--vanilla','native_tracks.R']
    if p['argv'][:len(expected)]!=expected or p.get('public_upload') is not False:raise ValueError('Only fixed native plotting routes allowed')
    if p['backend']=='pyGenomeTracks':
        if len(p['argv'])!=9 or p['argv'][5:8]!=['--outFileName','native_tracks.pdf','--width']:raise ValueError('Native plotting argv shape changed')
        if float(p['argv'][8])<=0:raise ValueError('Positive physical plotting width required')
    elif p['backend']!='Gviz' or len(p['argv'])!=3:raise ValueError('Only exact Gviz script invocation allowed')
    executable=shutil.which(p['argv'][0])
    if not executable or sha(executable)!=p['expected_executable_sha256']:raise ValueError('Reviewed installed binary identity required')
    if not p['expected_versions']:raise ValueError('Record and review actual native versions before explicit server dispatch')
    if p['backend']=='pyGenomeTracks':version=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=30,check=True).stdout
    else:version=subprocess.run([executable,'--vanilla','-e','cat(as.character(packageVersion("Gviz")))'],capture_output=True,text=True,timeout=30,check=True).stdout
    expected_version=p['expected_versions'].get(p['backend'])
    if not isinstance(expected_version,str) or not expected_version or expected_version not in version:raise ValueError('Native package version differs from reviewed environment')
    for row in p['generated_files']+p['native_assets']:
        f=(root/row['path']).resolve(strict=True)
        if not f.is_relative_to(root) or sha(f)!=row['sha256']:raise ValueError('Track changed or escaped approved staged project')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    # Stage only reviewed inputs/scripts; do not execute from or overwrite source project.
    for row in p['generated_files']+p['native_assets']:
        f=(root/row['path']).resolve(strict=True);target=(out/row['path']).resolve()
        if not target.is_relative_to(out.resolve()):raise ValueError('Native staging path escaped output')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if sha(target)!=row['sha256']:raise ValueError('Conflicting native staged inputs')
        else:shutil.copy2(f,target)
    with (out/'engine.log').open('x',encoding='utf8') as log:r=subprocess.run([executable]+p['argv'][1:],cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=600,check=False)
    result=out/'native_tracks.pdf'
    for row in p['generated_files']+p['native_assets']:
        if sha(root/row['path'])!=row['sha256']:raise ValueError('Native source changed during rendering')
    receipt={'state':'NATIVE_PLOT_COMPLETED_UNREVIEWED' if r.returncode==0 and result.exists() and result.stat().st_size else 'FAILED','exit_code':r.returncode,'plan_sha256':sha(plan_path),'outputs':[{'path':f.name,'sha256':sha(f)} for f in out.iterdir() if f.is_file()],'visual_acceptance':False,'scientific_acceptance':'NOT_ESTABLISHED','public_upload':False};write(out/'receipt.private.json',receipt);return receipt
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
