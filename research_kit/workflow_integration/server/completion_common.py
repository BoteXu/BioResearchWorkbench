"""Native source, identity and output bindings. Scientific imports occur on the server."""
from pathlib import Path
import csv
import hashlib
import importlib.metadata
import os
import socket
import subprocess
import sys
from runtime import read,write,sha,selected
from completion_contracts import ROUTES,SOURCES

def offline_python():
    sys.dont_write_bytecode=True # Never create caches in the clean owned author checkout.
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='offline',TOKENIZERS_PARALLELISM='false')
    def denied(*a,**k):raise RuntimeError('Private native inference forbids outbound sockets')
    socket.create_connection=denied
    socket.socket.connect=denied
    socket.socket.connect_ex=denied

def versions(p):
    actual={k:importlib.metadata.version(k) for k in p['software_versions']}
    if actual!=p['software_versions']:raise ValueError('Existing native dependency versions differ from the reviewed plan')
    return actual

def repo_binding(mode,p):
    key=ROUTES[mode].get('source')
    if key is None:return None
    owner,commit=SOURCES[key];repo=Path(p['repository']).resolve(strict=True)
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True,encoding='utf8',timeout=60).strip()
    if git('rev-parse','HEAD')!=commit:raise ValueError('Author checkout commit differs from the reviewed source')
    if git('status','--porcelain','--untracked-files=normal'):raise ValueError('Use a clean owned author checkout, including untracked code; never modify it in place')
    # Verify tracked working bytes, not merely a HEAD label; also reject source symlinks.
    subprocess.run(['git','-C',str(repo),'diff','--exit-code','HEAD','--'],check=True,stdout=subprocess.DEVNULL,timeout=60)
    files=git('ls-files','-z').split('\0');records=[]
    for name in files:
        if not name:continue
        path=repo/name
        if path.is_symlink():raise ValueError('Review source symlink targets separately before native import')
        if path.is_file() and (path.suffix in {'.py','.yaml','.yml','.json','.R','.smk'} or path.name=='Snakefile'):records.append({'path':name,'sha256':sha(path)})
    return {'repository':owner,'commit':commit,'files':records,'path':str(repo)}

def license_check(ids,mode,source):
    if 'license_evidence' not in ids:return None
    d=read(ids['license_evidence'])
    if d.get('tool')!=ROUTES[mode]['tool'] or d.get('permitted_use')!='private_noncommercial_research' or d.get('reviewed') is not True:
        raise ValueError('Actual owner-reviewed tool/weight/output license evidence required; this adapter accepts no terms automatically')
    if not d.get('source_url') or not d.get('license_text_sha256') or not d.get('review_basis'):raise ValueError('License evidence must identify exact terms and their review basis')
    if source and d.get('source_commit')!=source['commit']:raise ValueError('License evidence is not bound to this reviewed author source')
    if mode.startswith(('morphdiff','prnet','scdiffusion','squidiff','cellnavi','stack')):
        if any(not d.get(k) for k in ['checkpoint_terms','output_terms']):raise ValueError('Model weights and generated outputs require separate actual-use review')
    return {'evidence_sha256':sha(ids['license_evidence']),'source_url':d['source_url'],'license_text_sha256':d['license_text_sha256'],'permitted_use':d['permitted_use']}

def model_manifest(ids,p,mode):
    d=read(ids['model_manifest'])
    if d.get('tool')!=ROUTES[mode]['tool'] or d.get('representation_kind')!=ROUTES[mode]['kind']:raise ValueError('Literal checkpoint task/output semantics required')
    for role in ['checkpoint','features','autoencoder_checkpoint','model_config','gene_vocabulary','class_order','latent_direction']:
        if role in ids and d.get('artifact_sha256',{}).get(role)!=sha(ids[role]):raise ValueError('Unbound model artifact: '+role)
    if d.get('inference_only') is not True or d.get('training_membership_reviewed') is not True or not d.get('training_scope') or not d.get('preprocessing'):
        raise ValueError('Actual inference-only model, training provenance and fixed preprocessing required')
    return d

def context(ids):
    c=read(ids['context'])
    for k in ['species','independent_unit','assay','reference_version','contrast','limitations']:
        if not c.get(k):raise ValueError('Missing scientific context: '+k)
    if c.get('public_upload') is not False:raise ValueError('This route is private and offline')
    return c

def table(path,identity=None):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter='\t');header=reader.fieldnames;data=list(reader)
    if not header or len(header)!=len(set(header)) or not data or any(None in r for r in data):raise ValueError('Nonempty rectangular TSV required')
    if identity:
        vals=[r.get(identity) for r in data]
        if any(not v for v in vals) or len(set(vals))!=len(vals):raise ValueError('Literal nonmissing unique identity required: '+identity)
    return header,data

def text_axis(path):
    names=Path(path).read_text(encoding='utf-8-sig').splitlines()
    if not names or any(not x or x!=x.strip() for x in names) or len(set(names))!=len(names):raise ValueError('Literal unique feature axis required, no trimming or aliases')
    return names

def metadata(ids,n=None):
    import pandas as pd
    d=pd.read_csv(ids['query_metadata'],sep='\t',dtype=str,keep_default_na=False)
    if d.empty or not {'query_id','unit_id'}<=set(d) or d.query_id.eq('').any() or d.unit_id.eq('').any() or d.query_id.duplicated().any():raise ValueError('Exact nonempty query and biological-unit metadata required')
    if n is not None and len(d)!=n:raise ValueError('Query rows and actual metadata differ')
    return d

def matrix(ids,role,features,p):
    import numpy as np
    import pandas as pd
    with Path(ids[role]).open(encoding='utf-8-sig',newline='') as stream:header=next(csv.reader(stream,delimiter='\t'))
    if len(set(header))!=len(header) or len(header)<2:raise ValueError('Duplicate or missing raw matrix header')
    x=pd.read_csv(ids[role],sep='\t',index_col=0,dtype=str,keep_default_na=False)
    if list(x.columns)!=features or x.index.has_duplicates or x.index.isna().any() or x.size>p['maximum_output_entries']:raise ValueError('Exact matrix feature axis, identity and explicit budget required')
    if any(not k for k in x.index):raise ValueError('Missing literal query identity')
    x=x.apply(pd.to_numeric,errors='raise');a=x.to_numpy(dtype=float)
    if not np.isfinite(a).all():raise ValueError('Unassessed/nonfinite inputs cannot be silently imputed')
    return x

def save_matrix(out,name,a,identity,columns,role,outputs):
    import numpy as np
    import pandas as pd
    a=a.toarray() if hasattr(a,'toarray') else np.asarray(a)
    if a.shape!=(len(identity),len(columns)) or not np.isfinite(a).all():raise ValueError('Invalid native scientific output shape or values: '+role)
    path=out/name;pd.DataFrame(a,index=pd.Index(identity,name='query_id'),columns=columns).to_csv(path,sep='\t');outputs.append((path,role))

def native_command(argv,out,stem,cwd=None):
    """OS-level network namespace; failure is a block, never a network-enabled retry."""
    log=out/(stem+'.log')
    namespace_active=os.environ.get('BRW_ISOLATED_NATIVE_CHILD')=='1' and sys.platform=='linux' and set(p.name for p in Path('/sys/class/net').iterdir())=={'lo'}
    prefix=[] if namespace_active else ['unshare','--user','--map-root-user','--net','--']
    with log.open('xb') as stream:
        subprocess.run([*prefix,*map(str,argv)],cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,check=True)
    if log.stat().st_size==0:log.write_text('Adapter observation: command exited with status 0 and produced no stdout/stderr.\n',encoding='utf8')
    return log

def checked_executable(p):
    path=Path(p['executable']).resolve(strict=True)
    if not path.is_file() or sha(path)!=p['executable_sha256']:raise ValueError('Native executable bytes differ from owner-reviewed installation')
    return path

def safe_state(path,torch):
    # No whole-object pickle loading, downloads, missing-key transfer or fake fallback.
    d=torch.load(str(path),map_location='cpu',weights_only=True)
    if not isinstance(d,dict):raise ValueError('Native checkpoint must contain a weights-only state dictionary')
    return d

def model_device(p):
    import torch
    if p['accelerator']=='gpu' and not torch.cuda.is_available():raise ValueError('Requested allocated GPU is unavailable in the selected environment')
    torch.manual_seed(p['seed'])
    if torch.cuda.is_available():torch.cuda.manual_seed_all(p['seed'])
    return torch,torch.device('cuda' if p['accelerator']=='gpu' else 'cpu')

def prove_outputs(out,outputs,mode,p,metrics,source,licenses,ctx):
    import math
    proof=[];previews=[];seen=set()
    for index,(path,role) in enumerate(outputs):
        path=Path(path)
        if path.resolve() in seen:raise ValueError('Native output path listed twice')
        seen.add(path.resolve())
        row={'role':role,'path':path.relative_to(out).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,'data_kind':ROUTES[mode]['kind']}
        if path.suffix=='.tsv':
            # Full bounded file scan, not just a screenshot or a preview count.
            with path.open(encoding='utf-8-sig',newline='') as f:
                rd=csv.reader(f,delimiter='\t');header=next(rd);n=0;display=[]
                for record in rd:
                    if len(record)!=len(header):raise ValueError('Malformed returned scientific table')
                    if n<40:display.append(record[:100])
                    n+=1
            row.update(columns=header,rows=n)
            preview=out/('preview_'+role+'_'+str(index)+'.tsv')
            with preview.open('x',encoding='utf8',newline='') as stream:
                writer=csv.writer(stream,delimiter='\t',lineterminator='\n');writer.writerow(header[:100]);writer.writerows(display)
            row['preview']={'path':preview.relative_to(out).as_posix(),'sha256':sha(preview),'rows':len(display),'columns':header[:100],'scope':'first_40_rows_first_100_columns_navigation_only_not_a_representative_scientific_subset'}
            previews.append((preview,'preview_'+role))
        proof.append(row)
    write(out/'result_channel_proof.private.json',{'schema':'native-completion-proof/1','mode':mode,'outputs':proof,'input_semantics':ROUTES[mode]['kind'],'scientific_acceptance':'NOT_ESTABLISHED'})
    outputs.append((out/'result_channel_proof.private.json','result_channel_proof'))
    outputs.extend(previews)
    with (out/'qc_metrics.tsv').open('x',encoding='utf8',newline='') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(['metric','value','interpretation'])
        for k,v in metrics.items():
            if type(v) in (int,float) and not math.isfinite(v):raise ValueError('Invalid computed QC metric')
            w.writerow([k,v,'descriptive_actual_output_requires_prespecified_acceptance'])
    outputs.append((out/'qc_metrics.tsv','qc_metrics'))
    actual=versions(p);write(out/'backend_versions.private.json',actual);outputs.append((out/'backend_versions.private.json','backend_versions'))
    write(out/'diagnostics.private.json',{'mode':mode,'software_versions':actual,'metrics':metrics,'scientific_acceptance':'NOT_ESTABLISHED','data_kind':ROUTES[mode]['kind'],'source_binding':source,'license_binding':licenses,'context':ctx,'public_upload':False,'upstream_analysis_replaced':False,'automatic_retry':False})
    outputs.append((out/'diagnostics.private.json','diagnostics'))
    return outputs
