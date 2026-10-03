"""Persistent server workflow contracts and real scheduler adapters, dispatched through the shared terminal."""
import json
import re
import shutil
from pathlib import Path,PurePosixPath
from evidence import atomic_json
from workflow_ext import prepare_remote_task,_hash

HERE=Path(__file__).resolve().parent


def prepare_scheduler_task(argv: list, remote_workdir: str, expected_compute_host: str, submission_host: str, expected_outputs: list, context: dict, partition: str, cpus: int = 4, memory_mb: int = 8000, walltime: str = '01:00:00', inputs: list = None) -> dict:
    """Build a Slurm adapter that really submits/polls/cancels when explicitly dispatched on the verified server; preparation itself connects nowhere."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',partition) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,252}',submission_host): raise ValueError('Provide verified submission host and explicit partition')
    if type(cpus) is not int or not 1<=cpus<=256 or type(memory_mb) is not int or not 100<=memory_mb<=2000000 or not re.fullmatch(r'(?:\d+-)?\d{1,3}:[0-5]\d:[0-5]\d',walltime): raise ValueError('Invalid resource request')
    result=prepare_remote_task(argv,remote_workdir,expected_compute_host,expected_outputs,context,inputs)
    folder=Path(result['bundle']);profile={'schema':1,'scheduler':'slurm','submission_host':submission_host,'partition':partition,'cpus':cpus,'memory_mb':memory_mb,'walltime':walltime}
    atomic_json(folder/'scheduler.json',profile);shutil.copy2(HERE/'scheduler_agent.py',folder/'scheduler_agent.py')
    (folder/'submit.sh').write_text('#!/bin/sh\nset -eu\nexec python3 remote_runner.py task.json\n',encoding='utf8',newline='\n')
    return {**result,'scheduler':'slurm','commands':{'submit':'python3 scheduler_agent.py submit .','status':'python3 scheduler_agent.py status .','cancel':'python3 scheduler_agent.py cancel .'},'limitations':result['limitations']+['Copy the bundle and execute commands through the existing shared SSH terminal.','The compute hostname must be current and match the allocated node; a dynamic allocation may need a newly prepared task.','Submission is not completion; review scheduler and portable-runner receipts separately.','Cancellation is an explicit operation and preserves logs; no automatic requeue or stale-lock deletion.']}


def inspect_scheduler_receipt(task_file: str, scheduler_receipt_path: str, remote_receipt_path: str = '') -> dict:
    """Review a returned scheduler snapshot with exact task identity and separate scheduler/analysis completion states."""
    receipt=json.loads(Path(scheduler_receipt_path).read_text(encoding='utf8'));issues=[]
    if receipt.get('task_sha256')!=_hash(task_file): issues.append('task_hash_mismatch')
    if not re.fullmatch(r'\d+',receipt.get('job_id','')): issues.append('missing_verified_job_id')
    completed=receipt.get('state')=='scheduler_completed';execution=False
    if remote_receipt_path:
        from workflow_ext import inspect_remote_task
        review=inspect_remote_task(task_file,remote_receipt_path);execution=review['receipt_consistent'] and review['state']=='succeeded';issues+=review['issues']
    return {'success':True,'receipt_consistent':not issues,'issues':issues,'scheduler_completed':completed,'execution_receipt_completed':execution,'job_id':receipt.get('job_id'),'recorded_nodes':[x.get('nodes') for x in receipt.get('accounting_records',[])],'checked_at_unix':receipt.get('checked_at_unix'),'limitations':['Returned snapshots are not live process checks.','Output transfer integrity still needs verify_remote_results; scientific validity needs substantive review.','An empty squeue response does not prove success; inspect accounting and runner receipts.']}


def prepare_standard_pipeline(pipeline: str, parameters: dict, remote_workdir: str, expected_host: str, expected_outputs: list, context: dict, inputs: list = None) -> dict:
    """Prepare pinned nf-core RNA-seq, tximport, dream, molecular preparation or GROMACS analysis tasks using existing server environments; submit nothing."""
    if not isinstance(parameters,dict): raise ValueError('Provide explicit pipeline parameters')
    if pipeline=='nfcore_rnaseq':
        required={'revision','samplesheet','fasta','gtf','outdir','profile'}
        if not required<=set(parameters) or not re.fullmatch(r'\d+\.\d+\.\d+',parameters['revision']): raise ValueError('Pin a numeric pipeline release and provide samplesheet/fasta/gtf/outdir/profile')
        if parameters['profile'] not in {'singularity','apptainer','docker','conda'}: raise ValueError('Select an existing supported server runtime')
        argv=['nextflow','run','nf-core/rnaseq','-r',parameters['revision'],'-profile',parameters['profile'],'--input',parameters['samplesheet'],'--fasta',parameters['fasta'],'--gtf',parameters['gtf'],'--outdir',parameters['outdir']]
        if parameters.get('resume') is True: argv.append('-resume')
    elif pipeline in {'tximport','dream'}:
        required={'config_path','output_directory'}
        if not required<=set(parameters): raise ValueError('Provide a server JSON config path and fresh output directory')
        script='tximport_pipeline.R' if pipeline=='tximport' else 'dream_pipeline.R'
        # R helpers are copied into the task bundle; caller dispatches the returned bundle script.
        argv=['Rscript','--vanilla',parameters.get('script_path',script),parameters['config_path'],parameters['output_directory']]
    elif pipeline=='gromacs_summary':
        if parameters.get('analysis') not in {'rms','rmsf','gyrate','energy','hbond'}: raise ValueError('Select an explicit fixed GROMACS analysis')
        analysis=parameters['analysis'];output=parameters.get('output')
        if not output: raise ValueError('Provide a fresh output filename')
        if analysis=='energy': argv=['gmx','energy','-f',parameters['energy'],'-o',output]
        else: argv=['gmx',analysis,'-s',parameters['topology'],'-f',parameters['trajectory'],'-o',output]
        if 'begin' in parameters: argv+=['-b',str(float(parameters['begin']))]
        if 'end' in parameters: argv+=['-e',str(float(parameters['end']))]
        # Interactive GROMACS selections must be explicit and are passed by a fixed stdin wrapper.
        selection=parameters.get('selection')
        if not isinstance(selection,str) or len(selection)>1000 or '\x00' in selection: raise ValueError('Provide explicit GROMACS index/menu selection text')
        code='import subprocess,sys; p=subprocess.run(sys.argv[2:],input=sys.argv[1],text=True); raise SystemExit(p.returncode)'
        argv=['python3','-c',code,selection,*argv]
    elif pipeline=='meeko_receptor':
        if not parameters.get('input') or not parameters.get('output_basename'): raise ValueError('Provide reviewed receptor input and fresh output basename')
        argv=['mk_prepare_receptor.py','-i',parameters['input'],'-o',parameters['output_basename'],'-p']
    else: raise ValueError('Unsupported fixed pipeline')
    if any(not isinstance(v,str) or not v or '\x00' in v for v in argv): raise ValueError('Invalid pipeline argument')
    result=prepare_remote_task(argv,remote_workdir,expected_host,expected_outputs,context,inputs)
    if pipeline in {'tximport','dream'}:
        shutil.copy2(HERE/('tximport_pipeline.R' if pipeline=='tximport' else 'dream_pipeline.R'),Path(result['bundle'])/('tximport_pipeline.R' if pipeline=='tximport' else 'dream_pipeline.R'))
    return {**result,'pipeline':pipeline,'argv':argv,'limitations':result['limitations']+['Software/package presence is not assumed and must be checked on the actual server.','The task bundle R helper must be reachable at script_path from remote_workdir.','Nextflow resume is valid only with retained work/cache and compatible inputs; an existing final output is not silently accepted.','GROMACS units, group choices and periodic-boundary processing require review before analysis.']}


def inspect_multiqc_report(path: str) -> dict:
    """Inspect a returned MultiQC JSON summary, retain module values and missing fields; no universal QC pass inferred."""
    p=Path(path).resolve(strict=True)
    if p.stat().st_size>20000000: raise ValueError('Export a smaller server summary')
    data=json.loads(p.read_text(encoding='utf8'));stats=data.get('report_general_stats_data',[]);headers=data.get('report_general_stats_headers',[])
    if not isinstance(stats,list) or not isinstance(headers,list): raise ValueError('Unexpected MultiQC JSON schema')
    return {'success':True,'multiqc_version':data.get('config',{}).get('version',data.get('multiqc_version')),'general_stats':stats,'general_stats_headers':headers,'modules':data.get('report_modules',[]),'input_sha256':_hash(path),'limitations':['Thresholds differ by assay, reference, library and module; source values must be reviewed.','MultiQC summary absence is not a passed QC check.','No samples are automatically excluded.']}
