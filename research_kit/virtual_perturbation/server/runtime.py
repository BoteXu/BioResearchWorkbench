"""Fixed scientific worker; only the user's existing allocated Linux server can run it."""
from pathlib import Path
import csv,os,sys,socket,platform,subprocess,datetime,math,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import read,write,sha,digest,validate,relative,source_hashes

def guard(request):
    if sys.platform!='linux' or 'microsoft' in platform.release().lower():raise RuntimeError('Scientific work must use the existing allocated Linux server; local scientific execution is disabled')
    host=socket.gethostname()
    if request.get('expected_host')!=host or request.get('node_role')!='compute' or any(v in host.lower() for v in ('login','headnode')):raise RuntimeError('Require a freshly verified compute host')
    if request.get('server_execution_authorized') is not True or not (os.environ.get('SLURM_JOB_ID') or os.environ.get('SSH_CONNECTION')):raise RuntimeError('Explicit dispatch through the existing authorized server route required')
    body={k:v for k,v in request.items() if k!='plan_sha256'};body['server_execution_authorized']=False
    if digest(body)!=request['plan_sha256'] or request['submission_state']!='NOT_SUBMITTED':raise RuntimeError('Plan changed or submission is unknown; never auto-retry')
    if source_hashes()!=request['source_sha256']:raise RuntimeError('Reviewed adapter source changed')
    validate({**request,'server_execution_authorized':False})
    cpus=request['resource_budget']['cpus']
    if 'SLURM_CPUS_PER_TASK' in os.environ and cpus>int(os.environ['SLURM_CPUS_PER_TASK']):raise RuntimeError('Requested CPUs exceed allocation')
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]=str(cpus)
    return host

def qc(inputs,request):
    context=read(inputs['context']);up=read(inputs['qc_receipt']);measured=read(inputs['qc_measurements'])
    for k in ('species','assembly','annotation_version','assay','scale','independent_unit','estimand','limitations'):
        if not context.get(k):raise ValueError('Missing scientific context: '+k)
    if context.get('public_upload') is not False or context.get('measurement_state')!='predicted':raise ValueError('Keep private, predicted context')
    if context['independent_unit'] not in ('donor','animal','independent_culture','metabolic_model','logical_model'):raise ValueError('Cells, genes and graph permutations are not independent biological replicates')
    if context['estimand']!=request['estimand']:raise ValueError('Estimand differs from reviewed context')
    scales={'bulk_virtual_ko':'nonnegative_normalized_expression','singlecell_virtual_ko':'raw_counts','genki':'GenKI_reviewed_norm_layer','celloracle':'oracle_imputed_expression','gears':'checkpoint_training_expression_scale','geneformer':'rank_tokenized','dynamo':'fitted_velocity_PCA','metabolic_gene_deletion':'SBML_flux_model'}
    scales.update(cpa='checkpoint_training_expression_scale',scgpt='checkpoint_training_expression_scale',boolnet='logical_state_probability',maboss='logical_state_probability')
    if context['scale']!=scales[request['method']]:raise ValueError('Assay/data scale is incompatible with the selected virtual-perturbation method')
    if up.get('state')!='COMPLETED' or up.get('exit_code')!=0:raise ValueError('Actual upstream QC did not complete')
    if not any(r.get('sha256')==sha(inputs['qc_measurements']) for r in up['outputs']):raise ValueError('QC measurements not bound to actual upstream output')
    evidence=context.get('qc_evidence',[])
    if not evidence:raise ValueError('Prespecified measured input QC required')
    for e in evidence:
        if e['input_id'] not in inputs or sha(inputs[e['input_id']])!=e['input_sha256'] or not any(r.get('sha256')==e['input_sha256'] for r in up['inputs']):raise ValueError('QC belongs to different inputs')
        value=measured
        for component in e['measurement_field'].split('.'):value=value[int(component)] if isinstance(value,list) else value[component]
        if type(value) not in (int,float) or not math.isfinite(value) or value!=e['observed']:raise ValueError('Declared QC differs from actual measured evidence')
        bound=e['bound'];op=e['operator']
        if type(bound) not in (int,float) or not math.isfinite(bound) or op not in ('ge','le','eq') or not {'ge':value>=bound,'le':value<=bound,'eq':value==bound}[op]:raise ValueError('Measured upstream QC fails its reviewed criterion')
    return context

def audit_table(path,rule):
    """Full-file streaming audit on server; never treats a small preview as the full denominator."""
    n=0;keys=set();preview=[];missing=0;unit_counts={}
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter='\t');columns=reader.fieldnames
        if not columns or len(set(columns))!=len(columns) or not set(rule['required'])<=set(columns):raise ValueError('Scientific result schema differs from reviewed method')
        for r in reader:
            if None in r or any(v is None for v in r.values()):raise ValueError('Ragged scientific result')
            n+=1;key=tuple(r[k] for k in rule.get('keys',[]))
            if 'unit_id' in r:unit_counts[r['unit_id']]=unit_counts.get(r['unit_id'],0)+1
            if rule.get('keys') and (not all(key) or key in keys):raise ValueError('Missing or duplicate scientific identities')
            keys.add(key)
            for k in rule.get('numeric',[]):
                if r[k] in ('','NA','NaN'):
                    missing+=1
                    if not rule.get('allow_missing',False):raise ValueError('Missing required numerical result')
                    continue
                x=float(r[k])
                if not math.isfinite(x):raise ValueError('Nonfinite scientific output')
                if k in rule.get('probabilities',[]) and not 0<=x<=1:raise ValueError('Invalid probability')
            from return_binding import algebra_issues
            if algebra_issues(r,rule):raise ValueError('Reported WT/KO/delta or ratio is internally inconsistent')
            if len(preview)<40:preview.append(r)
    if n==0 and not rule.get('empty_valid',False):raise ValueError('Empty required result denominator')
    return {'rows':n,'columns':columns,'sha256':sha(path),'bytes':Path(path).stat().st_size,'missing_numeric':missing,'unit_row_counts':unit_counts,'preview':preview,'scope':'full_server_stream_scan_not_independent_scientific_validation'}

def execute(request_path,out_path):
    path=Path(request_path).resolve();r=read(path);host=guard(r);root=path.parent
    out=Path(out_path).resolve();out.mkdir(parents=True,exist_ok=False)
    receipt={'schema':'private-perturbation-receipt/1','run_id':r['run_id'],'method':r['method'],'request_sha256':sha(path),'plan_sha256':r['plan_sha256'],'source_sha256':r['source_sha256'],'state':'RUNNING','host':host,'scheduler_job_id':os.environ.get('SLURM_JOB_ID'),'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs':[],'outputs':[],'measurement_state':'predicted','public_upload':False,'automatic_retry':False,'scientific_acceptance':'NOT_ESTABLISHED'}
    try:
        inputs={}
        for row in r['inputs']:
            p=relative(root,row['path'])
            if sha(p)!=row['sha256']:raise ValueError('Input bytes changed after plan')
            inputs[row['id']]=p;receipt['inputs'].append({**row,'bytes':p.stat().st_size})
        context=qc(inputs,r);spec=read(Path(__file__).parents[1]/'catalog.json')['methods'][r['method']]
        import shutil
        shutil.copyfile(inputs['context'],out/'source_context.private.json')
        from identity import fingerprint
        import importlib.metadata
        environment={}
        for package in ('numpy','pandas','scipy','torch','torch-geometric','transformers','datasets','anndata','scanpy','scikit-learn','scvelo','celloracle','GenKI','cell-gears','geneformer','dynamo-release','cpa-tools','scgpt','maboss','cobra','optlang','swiglpk','gurobipy','cplex'):
            try:environment[package]=importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:pass
        receipt['environment_versions']=environment
        backend_identity=fingerprint(r['method'])
        if backend_identity['code_sha256']!=r['parameters']['expected_backend_code_sha256']:raise ValueError('Installed specialist code differs from reviewed exact backend source')
        write(out/'backend_identity.private.json',backend_identity)
        os.environ['BRW_APPROVED_PYTHON']=sys.executable
        audits=[]
        for label,parameters in [('primary',r['parameters'])]+[(v['label'],{**r['parameters'],**v['parameters']}) for v in r['sensitivity_variants']]:
            folder=out/label;folder.mkdir();j={'analysis_id':r['method'],'method':r['method'],'implementation':spec['implementation'],'parameters':{**parameters,'implementation':spec['implementation']},'inputs':{k:str(v) for k,v in inputs.items()},'context':context,'required_roles':spec['roles'],'project_root':str(root),'resource_budget':r['resource_budget'],'request_path':str(path),'variant':label,'python_executable':sys.executable}
            write(folder/'invocation.private.json',j)
            worker=Path(__file__).with_name('methods.py')
            r_worker='boolnet.R' if r['method']=='boolnet' else 'virtual_ko.R'
            cmd=['Rscript','--vanilla',str(Path(__file__).with_name(r_worker)),str(folder/'invocation.private.json'),str(folder)] if spec['worker']=='r' else [sys.executable,str(worker),str(folder/'invocation.private.json'),str(folder)]
            with (folder/'engine.log').open('xb') as log:subprocess.run(cmd,cwd=folder,stdout=log,stderr=subprocess.STDOUT,check=True)
            mapping=read(folder/'outputs.private.json')
            if set(mapping)!=set(spec['roles']):raise ValueError('Incomplete actual method outputs')
            for role,name in mapping.items():
                f=relative(folder,name);a=audit_table(f,spec['output_rules'][role]);preview=a.pop('preview');previewfile=folder/(role+'.preview.private.json');write(previewfile,{'role':role,'full_result_sha256':a['sha256'],'full_rows':a['rows'],'preview_rows':preview,'is_full_result':len(preview)==a['rows']});audits.append({'variant':label,'role':role,'path':f.relative_to(out).as_posix(),**a})
            d=read(folder/'diagnostics.private.json')
            if d.get('fit_completed') is not True or not d.get('metrics') or any(type(v) not in (int,float) or not math.isfinite(v) for v in d['metrics'].values()):raise ValueError('Measured finite diagnostics missing')
        write(out/'full_result_audit.private.json',audits)
        from comparison import compare
        write(out/'sensitivity_comparison.private.json',compare(out,spec,r['sensitivity_variants']))
        write(out/'claim_boundaries.private.json',{'measurement_state':'predicted','real_KO_observed':False,'causal_effect_established':False,'survival_benefit_established':False,'comparison_metric':spec['score_kind'],'must_not_relabel_as':'observed_expression_or_experimental_target_validation','cross_flow':'only_predicted_hypothesis_channel; exact source hashes + species + gene version + measured-data revalidation required'})
        receipt.update(state='COMPLETED',exit_code=0)
    except Exception as e:
        receipt.update(state='FAILED',exit_code=1,error=str(e));(out/'failure.private.log').write_text(traceback.format_exc(),encoding='utf8')
    receipt['outputs']=[{'path':f.relative_to(out).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(out.rglob('*')) if f.is_file()]
    receipt['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(out/'receipt.private.json',receipt)
    return receipt

if __name__=='__main__':
    result=execute(sys.argv[1],sys.argv[2]);print(result['state']);sys.exit(result['exit_code'])
