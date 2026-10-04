"""Prepare fixed server code checks, workflows and private tool development artifacts."""
import html
import json
import math
import re
import shutil
from pathlib import Path
from academic_common import artifact, read_file, digest, rows, text
from code_common import relative, report, number, canon, sha

HERE=Path(__file__).resolve().parent
MODES={'python_syntax','r_syntax','python_run','python_tests','python_profile','notebook','dicom_metadata'}


def prepare_code_execution(mode: str, configuration: dict, remote_workdir: str, expected_host: str,
                           output_directory: str, context: dict, inputs: list) -> dict:
    """Prepare checksum-bound code/Notebook/profile/DICOM tasks for explicit server dispatch; no local source execution."""
    from workflow_ext import prepare_remote_task
    from scientific_backend_ext import _bind_bundle
    if mode not in MODES or not isinstance(configuration,dict):raise ValueError('Select a fixed server mode')
    if not inputs or len(inputs)>200:raise ValueError('Bounded checksum input manifest required')
    selected=configuration.get('files',[])
    if not selected or not isinstance(selected,list) or len(set(selected))!=len(selected):raise ValueError('Distinct selected server files required')
    for p in selected:relative(p)
    if not set(selected)<={x['path'] for x in inputs}:raise ValueError('Every source must be bound by input hash')
    timeout=configuration.get('timeout_seconds',600)
    if type(timeout) is not int or not 1<=timeout<=86400:raise ValueError('Bounded execution timeout required')
    relative(output_directory)
    if any(P==output_directory or P.startswith(output_directory+'/') for P in selected):raise ValueError('Outputs must be separate from selected sources')
    if mode not in {'python_syntax','r_syntax','dicom_metadata'} and configuration.get('reviewed_code') is not True:
        raise ValueError('Executing source needs an explicit reviewed-code declaration')
    if mode.startswith('python') and any(not p.endswith('.py') for p in selected):raise ValueError('Python source files required')
    if mode=='r_syntax' and any(not p.lower().endswith('.r') for p in selected):raise ValueError('R source files required')
    if mode=='notebook' and (len(selected)!=1 or not selected[0].endswith('.ipynb')):raise ValueError('One v4 notebook required')
    if mode in {'python_run','python_tests','python_profile'} and len(selected)!=1:raise ValueError('One explicit Python entrypoint required')
    arguments=configuration.get('arguments',[])
    if not isinstance(arguments,list) or len(arguments)>100 or any(not isinstance(a,str) or '\x00' in a for a in arguments):raise ValueError('Exact bounded script arguments required')
    config={**configuration,'mode':mode,'output_directory':output_directory,'timeout_seconds':timeout}
    bundle=prepare_remote_task(['python3','code_runner.py','code_config.json'],remote_workdir,expected_host,
      [output_directory+'/summary.json',output_directory+'/execution.json'],context,inputs)
    folder=Path(bundle['bundle']);(folder/'code_config.json').write_text(canon(config)+'\n',encoding='utf8')
    shutil.copyfile(HERE/'code_runner.py',folder/'code_runner.py')
    bundle=_bind_bundle(bundle,['code_config.json','code_runner.py'])
    return {**bundle,'mode':mode,'security_boundary':'owned_server_execution_not_a_sandbox',
      'limitations':bundle['limitations']+['Reviewed source can access its server account privileges. Isolate untrusted code using an existing approved container/account. No software installation or network confinement is performed by this adapter. Notebook failures retain partial output.']}


def inspect_code_execution(execution_path: str, expected_configuration_sha256: str) -> dict:
    """Inspect a returned code-adapter receipt snapshot and its declared source/configuration identity."""
    _,raw=read_file(execution_path,5_000_000);data=json.loads(raw)
    issues=[]
    if data.get('schema')!=1 or data.get('configuration_sha256')!=expected_configuration_sha256:issues.append('configuration_mismatch')
    if data.get('state')!='succeeded' or data.get('exit_code')!=0 or not data.get('finished_at'):issues.append('not_successful_completion')
    if not data.get('source_hashes') or any(not re.fullmatch('[a-f0-9]{64}',x.get('sha256','')) for x in data.get('source_hashes',[])):issues.append('missing_source_identity')
    return report('code_execution_review',receipt_sha256=digest(raw),issues=issues,completion_record_pass=not issues,
      mode=data.get('mode'),limitations=['Receipt fields are an unsigned snapshot. Check the enclosing server runner receipt and returned output checksums separately. Completion is not scientific validation.'])


def summarize_performance(profile_path: str) -> dict:
    """Summarize the fixed adapter JSON profile; refuse arbitrary pickle-based profiler files."""
    _,raw=read_file(profile_path,5_000_000);profile=json.loads(raw)
    if profile.get('schema')!=1 or not isinstance(profile.get('functions'),list):raise ValueError('Use exported JSON profile from code_runner')
    data=rows(profile['functions'],10000)
    for r in data:
        if any(number(r[k])<0 for k in ('calls','total_seconds','cumulative_seconds')):raise ValueError('Invalid profile time')
    top=sorted(data,key=lambda r:number(r['cumulative_seconds']),reverse=True)[:30]
    return report('performance_review',source_sha256=digest(raw),top_functions=top,wall_seconds=profile.get('wall_seconds'),
      limitations=['Profiling overhead differs from benchmark timing. Child/native/GPU work and memory are not fully described by Python cProfile.'])


def estimate_compute_resources(pilots: list, target_units: int, scaling: str = 'linear', safety_factor: float = 1.5) -> dict:
    """Estimate resources from actual declared pilots with explicit scaling assumptions and observed range; never claim an exact runtime."""
    if type(target_units) is not int or target_units<1 or scaling not in {'linear','quadratic'} or not math.isfinite(safety_factor) or safety_factor<1:raise ValueError('Explicit positive target and conservative scaling required')
    samples=rows(pilots,30)
    if len(samples)<2:raise ValueError('At least two real pilot receipts required')
    estimates=[]
    for p in samples:
        if not p.get('receipt_sha256') or not re.fullmatch('[a-f0-9]{64}',p['receipt_sha256']):raise ValueError('Pilot receipt hash required')
        n=number(p['units']);seconds=number(p['wall_seconds']);memory=number(p['peak_memory_mb']);disk=number(p['output_mb'])
        if min(n,seconds,memory)<=0 or disk<0:raise ValueError('Positive observed pilot measurements required')
        ratio=target_units/n
        estimates.append({'seconds':seconds*ratio**(1 if scaling=='linear' else 2),'memory_mb':memory*max(1,ratio),'disk_mb':disk*ratio})
    result={k:{'observed_model_min':min(x[k] for x in estimates),'observed_model_max':max(x[k] for x in estimates),'suggested_budget':max(x[k] for x in estimates)*safety_factor} for k in estimates[0]}
    return report('resource_estimate',estimates=result,target_units=target_units,scaling=scaling,safety_factor=safety_factor,
      extrapolation=target_units>max(number(p['units']) for p in samples),limitations=['Pilot hashes are declared provenance, not independently authenticated observations. Memory/cache/I/O/GPU scaling may be nonlinear; validate near intended scale on the server.'])


def audit_parallel_execution(configuration: dict, tasks: list) -> dict:
    """Check nested thread allocation, deterministic seed assignment and shared output conflicts before parallel dispatch."""
    required={'allocated_cpus','workers','threads_per_worker','seed_policy'}
    if not required<=set(configuration) or any(type(configuration[k]) is not int or configuration[k]<1 for k in required-{'seed_policy'}):raise ValueError('Explicit positive CPU configuration required')
    if configuration['seed_policy'] not in {'per_task','deterministic_no_randomness'}:raise ValueError('Explicit randomness policy required')
    issues=[];records=rows(tasks,2000)
    if not records or len({r.get('id') for r in records})!=len(records):raise ValueError('Distinct task IDs required')
    if configuration['workers']*configuration['threads_per_worker']>configuration['allocated_cpus']:issues.append('cpu_oversubscription')
    outputs=[];seeds=[]
    for r in records:
        if not r.get('outputs'):raise ValueError('Declared task outputs required')
        outputs+=r['outputs']
        if configuration['seed_policy']=='per_task':
            if type(r.get('seed')) is not int:issues.append('missing_integer_seed')
            else:seeds.append(r['seed'])
    if len(set(outputs))!=len(outputs):issues.append('shared_output_collision')
    if len(set(seeds))!=len(seeds):issues.append('reused_task_seed')
    return report('parallel_audit',issues=issues,configuration_pass=not issues,task_count=len(records),
      limitations=['Distinct seeds alone do not establish independent RNG streams. BLAS/OpenMP/process settings and stochastic backend reproducibility need actual runtime review.'])


def audit_resume_compatibility(previous: dict, current: dict, scheduler_observation: dict, checkpoints: list) -> dict:
    """Compare input/code/parameter/environment identities and observed scheduler state before any reviewed recovery."""
    required={'inputs','code','parameters','environment'}
    if not required<=set(previous) or not required<=set(current):raise ValueError('Complete immutable execution identities required')
    changed=[k for k in sorted(required) if previous[k]!=current[k]]
    state=scheduler_observation.get('state');issues=[]
    if state not in {'completed','failed','cancelled','running','submitted','unknown'} or not scheduler_observation.get('observed_at') or not scheduler_observation.get('receipt_sha256'):raise ValueError('Actual scheduler observation provenance required')
    if state in {'running','submitted','unknown'}:issues.append('existing_or_unknown_submission_blocks_relaunch')
    if changed:issues.append('identity_changed')
    records=rows(checkpoints,200)
    for r in records:
        _,raw=read_file(r['path'],30_000_000)
        if digest(raw)!=r.get('sha256'):issues.append('checkpoint_integrity_mismatch')
    return report('resume_review',issues=issues,changed_dimensions=changed,checkpoint_count=len(records),
      compatible_for_reviewed_resume=not issues and bool(records),automatically_submitted=False,
      limitations=['This is a supplied scheduler snapshot, not a live poll. Hash equality does not establish backend checkpoint compatibility. Refresh real state before dispatch.'])


def _workflow(stages):
    data=rows(stages,100); ids=[s.get('id') for s in data]
    if not data or len(set(ids))!=len(ids) or any(not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,50}',s or '') for s in ids):raise ValueError('Distinct safe stage IDs required')
    by={s['id']:s for s in data};done=set();ordered=[]
    def visit(identity,active):
        if identity in active:raise ValueError('Workflow cycle')
        if identity in done:return
        s=by[identity]
        if s.get('kind') not in {'qc','analysis','check','report'} or not s.get('argv') or any(not isinstance(a,str) or not a or '\x00' in a for a in s['argv']):raise ValueError('Explicit stage type and argv required')
        for dep in s.get('depends_on',[]):
            if dep not in by:raise ValueError('Unknown dependency')
            visit(dep,active|{identity})
        for name in s.get('inputs',[])+s.get('outputs',[]):relative(name)
        if not s.get('outputs'):raise ValueError('Nonempty outputs required')
        for k in ('cpus','memory_mb','wall_minutes'):
            if type(s.get('resources',{}).get(k)) is not int or s['resources'][k]<1:raise ValueError('Explicit resource budgets required')
        done.add(identity);ordered.append(s)
    for i in ids:visit(i,set())
    def ancestry(i):return {d for d in by[i].get('depends_on',[])}|{a for d in by[i].get('depends_on',[]) for a in ancestry(d)}
    for s in ordered:
        if s['kind']=='analysis' and not any(by[d]['kind']=='qc' for d in ancestry(s['id'])):raise ValueError('Analysis requires QC ancestry')
    output=[p for s in data for p in s['outputs']]
    if len(set(output))!=len(output):raise ValueError('Conflicting workflow outputs')
    return ordered


def prepare_code_workflow(stages: list, engine: str = 'snakemake', approved_code: bool = False) -> dict:
    """Generate executable Snakemake/Nextflow orchestration with explicit dependencies, resources and pre-analysis QC receipts; no dispatch."""
    ordered=_workflow(stages)
    if engine not in {'snakemake','nextflow'} or approved_code is not True:raise ValueError('Select engine and review executable stage argv')
    configuration={'schema':1,'stages':ordered};files={'workflow.json':canon(configuration)+'\n','workflow_stage.py':(HERE/'workflow_stage.py').read_text(encoding='utf8')}
    if engine=='snakemake':
        lines=['rule all:','    input: '+repr([f'.receipts/{s["id"]}.json' for s in ordered])]
        for s in ordered:
            ins=s.get('inputs',[])+[f'.receipts/{d}.json' for d in s.get('depends_on',[])]+['workflow.json','workflow_stage.py']
            lines += [f'rule {s["id"]}:','    input: '+repr(ins),'    output: '+repr([f'.receipts/{s["id"]}.json']),f'    threads: {s["resources"]["cpus"]}',f'    resources: mem_mb={s["resources"]["memory_mb"]}, runtime={s["resources"]["wall_minutes"]}',
              '    shell: '+repr('python3 workflow_stage.py workflow.json '+s['id'])]
        files['Snakefile']='\n'.join(lines)+'\n'
    else:
        lines=['nextflow.enable.dsl=2']
        for s in ordered:
            lines += [f'process {s["id"]} {{',' cache false',f' cpus {s["resources"]["cpus"]}',f' memory \'{s["resources"]["memory_mb"]} MB\'',f' time \'{s["resources"]["wall_minutes"]} min\'',
              ' input:', ' val dependencies',' output:',f' path ".receipts/{s["id"]}.json"',' script:', ' """',f' python3 "${{projectDir}}/workflow_stage.py" "${{projectDir}}/workflow.json" {s["id"]}', ' """','}']
        lines += ['workflow {']
        for s in ordered:
            deps=s.get('depends_on',[])
            expr='Channel.value(true)' if not deps else (deps[0]+'.out' if len(deps)==1 else deps[0]+'.out.combine('+').combine('.join(d+'.out' for d in deps[1:])+')')
            lines.append(f' {s["id"]}({expr})')
        lines.append('}');files['main.nf']='\n'.join(lines)+'\n'
    return artifact('code_workflow',{'schema':1,'engine':engine,'configuration':configuration,'state':'generated_not_dispatched','stage_order':[s['id'] for s in ordered],
       'limitations':['Workflow engines and stage dependencies must already exist on the server. Nextflow stages run commands in the declared shared project workspace with serialized dependency receipts; unrelated stages may overlap and must have disjoint outputs. QC stages must write their declared gate JSON with gate_pass=true. No implicit acceptance of scientific validity.']},files)


def preview_code_workflow(workflow_path: str, available_inputs: list) -> dict:
    """Perform a no-execution workflow dependency/resource preview and identify missing external inputs."""
    _,raw=read_file(workflow_path);data=json.loads(raw);ordered=_workflow(data['stages']);produced=set();missing=set()
    for s in ordered:
        missing|=set(s.get('inputs',[]))-set(available_inputs)-produced;produced|=set(s['outputs'])
    return report('workflow_preview',source_sha256=digest(raw),stage_order=[s['id'] for s in ordered],missing_external_inputs=sorted(missing),
      maximum_declared_stage_resources={k:max(s['resources'][k] for s in ordered) for k in ('cpus','memory_mb','wall_minutes')},
      external_input_pass=not missing,limitations=['Resource budgets are declarations, not actual usage; this preview does not check executable availability or submit jobs.'])


def prepare_code_task_array(tasks: list, maximum_concurrent: int, resources: dict) -> dict:
    """Prepare a fixed Slurm array of reviewed checksum-bound task files with per-task receipts and concurrency limits; never submit."""
    data=rows(tasks,500)
    if not data or type(maximum_concurrent) is not int or not 1<=maximum_concurrent<=len(data):raise ValueError('Bounded array concurrency required')
    if not {'cpus','memory_mb','wall_minutes'}<=set(resources) or any(type(resources[k]) is not int or resources[k]<1 for k in ('cpus','memory_mb','wall_minutes')):raise ValueError('Explicit array resource limits required')
    ids=[]
    for t in data:
        relative(t['task_file'])
        if not re.fullmatch('[a-f0-9]{64}',t.get('sha256','')):raise ValueError('Reviewed task-file hash required')
        ids.append(t['task_file'])
    if len(set(ids))!=len(ids):raise ValueError('Duplicate array tasks')
    config={'schema':1,'tasks':data,'maximum_concurrent':maximum_concurrent,'resources':resources}
    script='\n'.join(['#!/bin/sh',f'#SBATCH --array=0-{len(data)-1}%{maximum_concurrent}',f'#SBATCH --cpus-per-task={resources["cpus"]}',f'#SBATCH --mem={resources["memory_mb"]}M',f'#SBATCH --time={resources["wall_minutes"]}',
       '#SBATCH --output=array-%A_%a.out','set -eu','python3 array_runner.py array.json'])+'\n'
    return artifact('code_task_array',{'schema':1,'configuration':config,'state':'prepared_not_submitted',
      'limitations':['Copy the reviewed bundle to the owned compute workspace and explicitly dispatch with the existing scheduler workflow. Actual job IDs and scheduler state need separate receipts. Each task must use distinct working/output directories; unknown submissions must not be retried.']},
      {'array.json':canon(config)+'\n','array.slurm':script,'array_runner.py':(HERE/'array_runner.py').read_text(encoding='utf8'),'remote_runner.py':(HERE/'remote_runner.py').read_text(encoding='utf8')})


def prepare_adapter_development(contract: dict, interface: str = 'cli') -> dict:
    """Generate a typed fixed-adapter development scaffold, contract tests and private escaped documentation; no registration or exposure."""
    from workbench_ext import validate_adapter_contract
    validation=validate_adapter_contract(contract)
    if validation['decision']!='pass':raise ValueError('Adapter contract failed validation')
    if interface not in {'cli','mcp','sdk','private_panel'}:raise ValueError('Select a development interface')
    fields=contract.get('parameters',{});name=contract['id']
    if not isinstance(fields,dict) or any(not re.fullmatch('[A-Za-z_]\\w*',k) or v.get('type') not in {'string','integer','number','boolean','array','object'} for k,v in fields.items()):raise ValueError('Typed parameter fields required')
    # Contract source is data. The generated client does not embed executable configuration, paths or keys.
    docs='# Reviewed adapter development\n\nInterface: '+interface+'\n\nSupply an owned fixed adapter implementation. Validate fixtures and real receipts before registration. Never expose private host settings.\n'
    schema={'type':'object','properties':{k:{'type':v['type']} for k,v in fields.items()},'required':[k for k,v in fields.items() if v.get('required')], 'additionalProperties':False}
    files={'contract.json':canon(contract)+'\n','parameters.schema.json':canon(schema)+'\n','README.md':docs}
    client='''import argparse, json
from pathlib import Path
def validate(value):
    schema=json.loads((Path(__file__).parent/'parameters.schema.json').read_text())
    types={'string':str,'integer':int,'number':(int,float),'boolean':bool,'array':list,'object':dict}
    if not isinstance(value,dict) or set(value)-set(schema['properties']) or not set(schema['required'])<=set(value): raise ValueError('Parameter contract mismatch')
    for key,item in value.items():
        allowed=types[schema['properties'][key]['type']]
        if type(item) not in (allowed if isinstance(allowed,tuple) else (allowed,)): raise ValueError('Parameter type mismatch')
    return value
def parameters(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--params-file', required=True)
    args=parser.parse_args(argv)
    with open(args.params_file,encoding='utf8') as stream: value=json.load(stream)
    if not isinstance(value,dict): raise ValueError('Parameters must be an object')
    return validate(value)
'''
    files['client.py']=client
    files['panel.html']='<html><meta charset="utf-8"><title>Private adapter review</title><h1>'+html.escape(str(name))+'</h1><pre>'+html.escape(canon(contract))+'</pre><p>Private development review. No endpoint or executable is configured.</p></html>'
    return artifact('adapter_development',{'schema':1,'interface':interface,'contract_validation':validation,'state':'scaffold_requires_implementation_and_runtime_acceptance',
       'limitations':['Scaffolds are not registered tools or network services. They do not supply a runtime implementation or OS sandbox. Use the existing fixed bridge adapter after review.']},files)
