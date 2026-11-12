"""Common server-only execution and immutable receipts. Importing this file fits nothing."""
from pathlib import Path
import hashlib
import json
import os
import re
import platform
import socket
import sys
from datetime import datetime, timezone
import importlib.metadata

def encode(v):
    return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf8')

def write(path,v):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(encode(v))

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def selected(root,name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or name.startswith('/') or any(p in ('','..','.') for p in name.split('/')):
        raise ValueError('Select a project-relative file')
    p=(Path(root)/name).resolve(strict=True)
    if not p.is_relative_to(Path(root).resolve()) or not p.is_file():raise ValueError('Input leaves selected project')
    return p

def guard(request):
    host=socket.gethostname()
    if sys.platform!='linux' or 'microsoft' in platform.release().lower():
        raise RuntimeError('Scientific execution is allowed only on the existing Linux server, never Windows or local WSL')
    if host!=request.get('expected_host') or request.get('server_execution_authorized') is not True:
        raise RuntimeError('Fresh exact compute-host identity and explicit dispatch required')
    if any(x in host.lower() for x in ('login','headnode')) or request.get('node_role')!='compute':
        raise RuntimeError('No scientific work on login nodes')
    if not os.environ.get('SLURM_JOB_ID') and not os.environ.get('SSH_CONNECTION'):
        raise RuntimeError('Require existing scheduler or authorized SSH execution context')
    if request.get('public_upload') is not False or request.get('submission_state')!='not_submitted':
        raise RuntimeError('Private new run only; inspect unknown/existing submissions before dispatch')
    body={k:v for k,v in request.items() if k!='plan_sha256'}
    body['server_execution_authorized']=False
    expected=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()
    if request.get('plan_sha256')!=expected:raise RuntimeError('Scientific parameters changed after review; regenerate the plan')
    sources={p.name:sha(p) for p in Path(__file__).parent.glob('*') if p.is_file() and p.suffix in {'.py','.R','.json'}}
    if request.get('source_sha256')!=sources:raise RuntimeError('Server adapter source differs from reviewed code')
    return host

def versions():
    result={'python':sys.version.split()[0]}
    for name in ('numpy','pandas','scipy','scikit-learn','scanpy','anndata','scvi-tools','torch','rdkit','posebusters','MDAnalysis','xgboost','lightgbm','catboost','scikit-survival','lifelines','mofapy2','pymbar'):
        try:result[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    return result

def run(request_path,output):
    request_path=Path(request_path).resolve();root=request_path.parent
    request=read(request_path);host=guard(request)
    resources=request['resource_budget'];cpus=resources['cpus']
    if type(cpus) is not int or cpus<1:raise ValueError('Explicit allocated server CPU budget required')
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]=str(cpus)
    if 'SLURM_CPUS_PER_TASK' in os.environ and cpus>int(os.environ['SLURM_CPUS_PER_TASK']):raise ValueError('Thread request exceeds scheduler allocation')
    if request['parameters'].get('threads',request['parameters'].get('cpu',cpus))>cpus:raise ValueError('Backend exceeds explicit CPU budget')
    if any(request['parameters'].get(k,cpus)>cpus for k in ('cores','workers')):raise ValueError('Specialist process count exceeds explicit server allocation')
    if request['backend']=='af3' and resources.get('gpus',0)<1:raise ValueError('AF3 requires explicit server GPU allocation')
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('Use a fresh output directory, never overwrite or silently resume')
    out.mkdir(parents=True)
    started=datetime.now(timezone.utc).isoformat()
    receipt={'schema':'private-scientific-run/2','run_id':request['run_id'],'request_sha256':sha(request_path),
      'plan_sha256':request['plan_sha256'],'host':host,'scheduler_job_id':os.environ.get('SLURM_JOB_ID'),
      'state':'RUNNING','started_at':started,'versions':versions(),'source_sha256':{p.name:sha(p) for p in Path(__file__).parent.glob('*') if p.is_file() and p.suffix in {'.py','.R','.json'}},
      'inputs':[],'outputs':[],'public_upload':False,'scientific_validity':'not_established','automatic_retry':False}
    try:
        for row in request['inputs']:
            if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,99}',str(row.get('id',''))):raise ValueError('Invalid scientific input role ID')
            path=selected(root,row['path'])
            if sha(path)!=row['sha256']:raise ValueError('Input source version changed: '+row['id'])
            receipt['inputs'].append({'id':row['id'],'path':row['path'],'sha256':row['sha256'],'bytes':path.stat().st_size})
        ids={r['id']:selected(root,r['path']) for r in request['inputs']}
        if len(ids)!=len(request['inputs']):raise ValueError('Duplicate input IDs')
        mode=request['backend'];params=request['parameters']
        if params.get('accelerator')=='gpu' and resources.get('gpus',0)<1:raise ValueError('Native model requires an explicitly allocated server GPU')
        if params.get('use_gpu') is True and resources.get('gpus',0)<1:raise ValueError('Legacy native model requires an explicitly allocated server GPU')
        if mode=='ml':
            from ml import analyze
        elif mode=='survival':
            from survival import analyze
        elif mode=='graph_training':
            from graph_training import analyze
        elif mode=='vina_docking':
            from docking import analyze
        elif mode=='matrix_qc':
            from matrix_qc import analyze
        elif mode=='structure_qc':
            from structure_qc import analyze
        elif mode in {'af3','af3_data_pipeline'}:
            from af3 import analyze
        elif mode in {'msa_search','msa_align','msa_qc','msa_filter','msa_pair'}:
            from msa import analyze
        elif mode in {'singlecell','scvi','pseudobulk','multiomics_concordance'}:
            from omics_python import analyze
        elif mode in {'molecular_qc','pose_qc','md_analysis','free_energy','kinetics'}:
            from cadd import analyze
        elif mode=='r_omics':
            from r_adapter import analyze
        elif mode in {'seurat_workflow','harmony_integrate','seurat_transfer','singler_annotate','hdwgcna_network','monocle3_trajectory','diablo_fit','snf_fusion','msstats_compare','muscat_pseudobulk','banksy_domains','progeny_activity','spark_spatial','xcms_preprocess','nestedcv_glmnet'}:
            from native_teaching_adapter import analyze
        elif mode in {'palantir_trajectory','scgen_predict','multivi_integrate','totalvi_integrate'}:
            from native_teaching_python import analyze
        elif mode in {'mixscape_classify','cellot_predict','destvi_deconvolution','cell2location_reference','cell2location_map'}:
            from native_spatial_perturbation import analyze
        elif mode in {'drug2cell_score','cellphonedb_per_unit'}:
            from native_gene_activity import analyze
        elif mode in {'paste_pairwise','squidpy_section_statistics'}:
            from native_spatial_statistics import analyze
        elif mode in {'vep_offline','ldsc_h2'}:
            from native_genetics import analyze
        elif mode=='seurat_to_anndata':
            from native_interop import analyze
        elif mode in {'cinemaot_effects','cellcap_programs'}:
            from native_response_programs import analyze
        elif mode in {'diffdock_pose','diffsbdd_generate','rfdiffusion_backbone','mace_singlepoint'}:
            from native_cadd_models import analyze
        elif mode in {'biolord_attributes','scvidr_predict'}:
            from native_response_legacy import analyze
        elif mode=='native_unit_profile_handoff':
            from native_profile_handoff import analyze
        elif mode=='proteintalks_predict':
            from native_proteintalks import analyze
        elif mode=='prescient_trajectories':
            from native_prescient import analyze
        elif mode=='batchie_posterior':
            from native_batchie import analyze
        elif mode=='causcell_counterfactual_fit':
            from native_causcell import analyze
        elif mode=='igv_scoped_report':
            from native_igv import analyze
        elif mode=='spatialglue_integrate':
            from native_spatialglue import analyze
        elif mode=='baysor_segment':
            from native_baysor import analyze
        elif mode=='smr_heidi':
            from native_smr import analyze
        elif mode=='systema_evaluate':
            from native_perturbation_evaluation import analyze
        elif mode in {'cnmf_programs','composition_sccoda','cellrank_multiview','perturbation_baselines'}:
            from teaching_extensions import analyze
        elif mode=='omics71':
            from analysis71 import analyze
        elif mode in {'magpie_coregister','diann_quantify','sirius_formulas','csi_result_import','gnps_offline_network','dockovalent','prnet_predict','scdiffusion_generate','squidiff_predict','cellnavi_drivers','stack_incontext','morphdiff_gene2image','morphdiff_image2image'}:
            from completion_runtime import analyze
        else:raise ValueError('Unknown fixed scientific backend')
        import warnings
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always')
            outputs=analyze(ids,params,out,mode)
        write(out/'runtime_warnings.json',[{'category':w.category.__name__,'message':str(w.message)} for w in observed])
        outputs.append((out/'runtime_warnings.json','runtime_warnings'))
        for path,role in outputs:
            path=Path(path).resolve()
            if not path.is_relative_to(out) or not path.is_file() or path.stat().st_size==0:raise ValueError('Missing actual required output')
            receipt['outputs'].append({'path':path.relative_to(out).as_posix(),'role':role,'sha256':sha(path),'bytes':path.stat().st_size})
        missing=set(request['required_roles'])-{r['role'] for r in receipt['outputs']}
        if missing:raise ValueError('Backend failed to return required roles: '+','.join(sorted(missing)))
        for row in receipt['inputs']:
            if sha(ids[row['id']])!=row['sha256']:raise ValueError('Input changed during run')
        receipt.update(state='COMPLETED',exit_code=0)
    except Exception as exc:
        receipt.update(state='FAILED',exit_code=1,error_type=type(exc).__name__,error=str(exc))
        receipt['partial_outputs']=[{'path':q.relative_to(out).as_posix(),'bytes':q.stat().st_size,'sha256':sha(q)} for q in out.rglob('*') if q.is_file()]
    finally:
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        write(out/'server_receipt.private.json',receipt)
    if receipt['state']!='COMPLETED':raise RuntimeError(receipt['error'])
    return receipt

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('runtime.py REQUEST_JSON FRESH_OUTPUT_DIR')
    print(json.dumps(run(sys.argv[1],sys.argv[2]),ensure_ascii=False))
