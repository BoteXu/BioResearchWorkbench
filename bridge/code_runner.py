"""Fixed modes for explicitly dispatched, reviewed server source. Not a security sandbox."""
import ast
import cProfile
import hashlib
import json
import os
import platform
import pstats
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def now():return datetime.now(timezone.utc).isoformat()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def local(root,name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:raise ValueError('Relative path required')
    file=root/name
    if file.is_symlink() or any(q.is_symlink() for q in file.parents if q.is_relative_to(root)):raise ValueError('Linked input/output refused')
    target=file.resolve()
    if not target.is_relative_to(root):raise ValueError('Scope escape')
    return target


def run(config_path):
    cp=Path(config_path).resolve(strict=True);cfg=json.loads(cp.read_text(encoding='utf8'));root=Path.cwd().resolve()
    output=local(root,cfg['output_directory']);output.mkdir(parents=True,exist_ok=False)
    files=[local(root,p) for p in cfg['files']]
    before=[{'path':p.relative_to(root).as_posix(),'sha256':digest(p)} for p in files]
    receipt={'schema':1,'mode':cfg['mode'],'configuration_sha256':digest(cp),'source_hashes':before,'state':'running','started_at':now(),'environment':{'python':platform.python_version(),'platform':platform.system()}}
    start=time.perf_counter();exit_code=1
    try:
        mode=cfg['mode'];timeout=cfg.get('timeout_seconds',600)
        if mode=='python_syntax':
            for p in files:ast.parse(p.read_text(encoding='utf-8-sig'),filename=p.name)
            exit_code=0
        elif mode=='r_syntax':
            executable=cfg.get('rscript','Rscript')
            if Path(executable).stem.lower()!='rscript':raise ValueError('Existing Rscript required')
            command=[executable,'--vanilla','-e','for (p in commandArgs(TRUE)) parse(file=p)',*[str(p) for p in files]]
            with (output/'stdout.txt').open('wb') as out,(output/'stderr.txt').open('wb') as err:
                exit_code=subprocess.run(command,stdout=out,stderr=err,timeout=timeout,check=False).returncode
        elif mode in {'python_run','python_tests','python_profile'}:
            if cfg.get('reviewed_code') is not True or len(files)!=1:raise ValueError('Reviewed single entrypoint required')
            argv=[sys.executable]
            if mode=='python_profile':argv+=['-m','cProfile','-o',str(output/'profile.pstats')]
            argv += [str(files[0]),*cfg.get('arguments',[])]
            with (output/'stdout.txt').open('wb') as out,(output/'stderr.txt').open('wb') as err:
                exit_code=subprocess.run(argv,stdout=out,stderr=err,cwd=root,timeout=timeout,check=False).returncode
            if mode=='python_profile' and exit_code==0:
                # Only deserialize the profiler file produced by this exact adapter run.
                stats=pstats.Stats(str(output/'profile.pstats'));functions=[]
                for (file,line,name),(primitive,calls,total,cumulative,callers) in stats.stats.items():
                    functions.append({'file':Path(file).name,'line':line,'function':name,'calls':calls,'primitive_calls':primitive,'total_seconds':total,'cumulative_seconds':cumulative})
                (output/'profile.json').write_text(json.dumps({'schema':1,'functions':functions,'wall_seconds':time.perf_counter()-start}),encoding='utf8')
        elif mode=='notebook':
            if cfg.get('reviewed_code') is not True:raise ValueError('Reviewed notebook required')
            import nbformat
            from nbclient import NotebookClient
            nb=nbformat.read(files[0],as_version=4)
            for c in nb.cells:
                if c.cell_type=='code':c.outputs=[];c.execution_count=None
            try:
                NotebookClient(nb,timeout=timeout,kernel_name=cfg.get('kernel_name','python3'),allow_errors=False,store_widget_state=False,
                    resources={'metadata':{'path':str(root)}}).execute();exit_code=0
            finally:nbformat.write(nb,output/'executed.ipynb')
        elif mode=='dicom_metadata':
            import pydicom
            selected=[]
            for p in files:
                d=pydicom.dcmread(p,stop_before_pixels=True)
                selected.append({'file_sha256':digest(p),'patient_token':hashlib.sha256(str(d.get('PatientID','')).encode()).hexdigest() if d.get('PatientID') else None,
                    'modality':str(d.get('Modality','')),'rows':d.get('Rows'),'columns':d.get('Columns'),
                    'pixel_spacing':list(d.get('PixelSpacing',[])),'slice_thickness':d.get('SliceThickness'),'manufacturer':str(d.get('Manufacturer',''))})
            (output/'metadata.json').write_text(json.dumps({'schema':1,'records':selected,'privacy':'private_pseudonymous_metadata_not_anonymized'},default=str),encoding='utf8');exit_code=0
        else:raise ValueError('Unknown fixed mode')
        after=[{'path':p.relative_to(root).as_posix(),'sha256':digest(p)} for p in files]
        receipt['source_unchanged']=after==before
        if after!=before:raise ValueError('Selected sources changed during execution')
        receipt['state']='succeeded' if exit_code==0 else 'failed'
    except BaseException as e:
        receipt['state']='failed';receipt['error_type']=type(e).__name__;exit_code=1
        (output/'failure.txt').write_text(str(e),encoding='utf8')
    finally:
        receipt.update(exit_code=exit_code,finished_at=now(),wall_seconds=time.perf_counter()-start)
        try:
            import resource
            maximum=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            receipt['peak_child_memory_mb']=maximum/(1048576 if platform.system()=='Darwin' else 1024)
            receipt['memory_measurement_scope']='maximum_waited_child_RSS_not_full_tree_or_GPU'
        except ImportError:receipt['memory_measurement_scope']='not_available_on_this_platform'
        receipt['output_bytes']=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
        (output/'execution.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        (output/'summary.json').write_text(json.dumps({'schema':1,'state':receipt['state'],'mode':receipt['mode'],'execution':'execution.json','scientific_validation':'not_established'}),encoding='utf8')
    return exit_code


if __name__=='__main__':sys.exit(run(sys.argv[1]))
