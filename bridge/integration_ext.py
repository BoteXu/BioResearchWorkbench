"""Optional MCP inventory and explicit read-only scheduler bundles."""
import hashlib
import json
import shutil
import time
from pathlib import Path
from academic_common import artifact, read_file
from slurm_monitor import validate


def inspect_mcp_components() -> dict:
    """Describe pinned optional processes and distinguish configuration from runtime acceptance."""
    path=Path(__file__).resolve().parent/'mcp_components.json'
    if not path.exists():path=path.parent.parent/'mcp_components.json'
    data=json.loads(path.read_text())
    return {'success':True,**data,'runtime_state':'not_probed','limitations':['A pinned manifest is not an installation or successful connection.','Read MCP_INTEGRATIONS.md before configuring a private scope.']}


def prepare_slurm_monitor(job_ids: list, submission_host: str, log_root: str = '', log_files: list = None) -> dict:
    """Prepare actual read-only squeue/sacct and bounded-log probes; no SSH or scheduler submission occurs here."""
    request=validate({'schema':1,'job_ids':job_ids,'submission_host':submission_host,'log_root':log_root,'log_files':log_files or []})
    digest=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result=artifact('slurm_monitor',{'request_sha256':digest,'state':'prepared','limitations':['Dispatch through the existing shared SSH session on the verified submission host.','Use a fresh receipt for every observation; no automatic submission, cancellation or retry.']},
                    {'monitor_request.json':json.dumps(request,indent=2),'slurm_monitor.py':Path(__file__).with_name('slurm_monitor.py').read_bytes()})
    return {**result,'command':'python3 slurm_monitor.py monitor_request.json monitor_receipt.json'}


def inspect_slurm_monitor(request_path: str, receipt_path: str, max_age_seconds: int = 300) -> dict:
    """Audit a returned live observation receipt, including request binding, age, unknown states and resource fields."""
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:raise ValueError('Bound receipt freshness explicitly')
    _,raw=read_file(request_path,100_000);request=validate(json.loads(raw))
    _,raw=read_file(receipt_path,5_000_000);receipt=json.loads(raw);issues=[]
    digest=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if receipt.get('schema')!=1 or receipt.get('request_sha256')!=digest:issues.append('request_binding_mismatch')
    if receipt.get('observed_host')!=request['submission_host']:issues.append('host_mismatch')
    stamp=receipt.get('observed_at_unix');age=time.time()-stamp if type(stamp) in (int,float) else None
    if age is None or not 0<=age<=max_age_seconds:issues.append('stale_or_invalid_timestamp')
    jobs=receipt.get('jobs',[])
    if not isinstance(jobs,list) or [r.get('job_id') for r in jobs]!=request['job_ids']:issues.append('job_scope_mismatch');jobs=[]
    if receipt.get('state')!='observed' or receipt.get('errors'):issues.append('probe_partial_or_unavailable')
    unknown=[r['job_id'] for r in jobs if r.get('state')=='UNKNOWN']
    return {'success':True,'receipt_consistent':not issues,'issues':issues,'age_seconds':age,'jobs':jobs,'unknown_jobs':unknown,
            'scientific_completion_verified':False,'limitations':['This is the most recent captured observation, not an ongoing live connection.','An empty queue or completed scheduler record is not validated analysis or successful result transfer.','Log tails and host information are private; never publish receipts.']}
