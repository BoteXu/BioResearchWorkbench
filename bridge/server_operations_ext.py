"""Bounded server budgets, explicit unknown-submission review and incremental return plans; no SSH dispatch."""
import hashlib
import json
import time
from academic_common import artifact, rows, text
from code_common import relative, number


def plan_server_budget(pilots: list, target_units: int, cpus: int, safety_factor: float = 1.5, rates: dict = None) -> dict:
    """Extend observed resource pilots with declared CPU/memory-hour budgets and optional user-supplied prices; not a queue or price lookup."""
    if type(cpus) is not int or not 1 <= cpus <= 4096: raise ValueError('Explicit bounded CPU allocation required')
    from code_execution_ext import estimate_compute_resources
    estimate = estimate_compute_resources(pilots, target_units, 'linear', safety_factor)
    # Estimate fields are read from the original helper's actual returned artifact.
    estimates = []
    for p in rows(pilots, 100):
        ratio = target_units / number(p['units'])
        hours = number(p['wall_seconds']) * ratio * number(safety_factor) / 3600
        gb = number(p['peak_memory_mb']) * max(1, ratio) * number(safety_factor) / 1024
        estimates.append({'wall_hours': hours, 'cpu_hours': hours*cpus, 'memory_gib_hours': gb*hours})
    pricing = None
    if rates is not None:
        if not isinstance(rates, dict) or set(rates) != {'currency','cpu_hour','memory_gib_hour'}: raise ValueError('Explicit currency and both rates required')
        text(rates['currency'],20);a=number(rates['cpu_hour']);b=number(rates['memory_gib_hour'])
        if min(a,b)<0: raise ValueError('Rates cannot be negative')
        pricing = {'currency':rates['currency'],'estimated_range':[min(e['cpu_hours']*a+e['memory_gib_hours']*b for e in estimates),max(e['cpu_hours']*a+e['memory_gib_hours']*b for e in estimates)],'rate_source':'caller_supplied_not_verified'}
    return artifact('server_budget', {'resource_estimate':estimate,'allocation_cpus':cpus,'pilot_estimates':estimates,'pricing':pricing,
                    'state':'estimate_only','submitted':False,
                    'limitations':['Linear pilot scaling may fail at different data sizes, parallelism, storage or GPU workloads.',
                                    'Queue wait, charged allocation, storage, transfers and site-specific minimum charges are not included.',
                                    'Use current server inventory and scheduler observations before resource selection.']})


def review_unknown_submission(request_sha256: str, observations: list, maximum_age_seconds: int = 300) -> dict:
    """Review explicit scheduler/runner observations for an ambiguous submission; automatic resubmission is always disabled."""
    if not isinstance(request_sha256,str) or len(request_sha256)!=64 or any(c not in 'abcdef0123456789' for c in request_sha256):raise ValueError('Exact reviewed request hash required')
    if type(maximum_age_seconds) is not int or not 1<=maximum_age_seconds<=86400:raise ValueError('Bound observation freshness')
    decisions=[];jobs=set();issues=[]
    for row in rows(observations,100):
        problems=[];stamp=row.get('observed_at_unix')
        if type(stamp) not in (int,float) or not 0<=time.time()-stamp<=maximum_age_seconds:problems.append('stale_or_missing_observation')
        if row.get('request_sha256')!=request_sha256:problems.append('request_binding_mismatch')
        if row.get('receipt_reviewed') is not True:problems.append('unreviewed_observation')
        if row.get('source') not in {'squeue','sacct','runner','submission_receipt'}:problems.append('unknown_observation_source')
        job=row.get('job_id')
        if not isinstance(job,str) or not job.isdigit():problems.append('unverified_job_id')
        if not problems:jobs.add(job)
        decisions.append({'source':row.get('source'),'job_id':job,'state':row.get('state','UNKNOWN'),'issues':problems})
        issues.extend(problems)
    if len(jobs)>1:issues.append('multiple_jobs_for_request_require_manual_reconciliation')
    if not jobs:issues.append('no_fresh_bound_job_observation')
    return artifact('submission_review',{'request_sha256':request_sha256,'observations':decisions,'issues':sorted(set(issues)),
                    'candidate_job_ids':sorted(jobs),'identity_observed':len(jobs)==1 and not issues,
                    'automatic_resubmission_allowed':False,'next_action':'inspect_owned_scheduler_and_runner_receipts_in_shared_terminal',
                    'limitations':['Caller-supplied receipt review is not a live query or independent authentication.',
                                    'An empty queue, no accounting row or missing local receipt does not prove that no job was submitted.',
                                    'Job identity, completion, returned-file integrity and scientific acceptance are separate.']})


def plan_incremental_return(previous_manifest: list, current_manifest: list, maximum_bytes: int = 100_000_000) -> dict:
    """Plan changed bounded result files from explicit checksum snapshots, retaining missing/oversized/unstable results; transfer nothing."""
    if type(maximum_bytes) is not int or not 1<=maximum_bytes<=10**12:raise ValueError('Explicit transfer budget required')
    def index(value, current=False):
        out={}
        for r in rows(value,2000):
            name=relative(r['path'])
            if name in out or not isinstance(r.get('sha256'),str) or len(r['sha256'])!=64 or any(c not in 'abcdef0123456789' for c in r['sha256']):raise ValueError('Distinct filenames and SHA256 required')
            if type(r.get('bytes')) is not int or r['bytes']<0:raise ValueError('Nonnegative byte count required')
            out[name]=r
        return out
    old=index(previous_manifest);new=index(current_manifest,True);selected=[];deferred=[];used=0
    for name,r in sorted(new.items()):
        if name in old and r['sha256']==old[name]['sha256'] and r['bytes']==old[name]['bytes']:continue
        if r.get('stable_snapshot_reviewed') is not True:deferred.append({'path':name,'reason':'active_or_unreviewed_writer'});continue
        if used+r['bytes']>maximum_bytes:deferred.append({'path':name,'reason':'transfer_budget'});continue
        selected.append(r);used+=r['bytes']
    manifest={'schema':1,'files':selected,'total_bytes':used,'source_manifest_sha256':hashlib.sha256(json.dumps(current_manifest,sort_keys=True).encode()).hexdigest()}
    return artifact('incremental_return',{'state':'prepared_not_transferred','manifest':manifest,'deferred':deferred,
                    'missing_from_current':sorted(set(old)-set(new)),'deletion_authorized':False,
                    'limitations':['Snapshots need refresh and active-writer checks through the existing shared terminal.',
                                    'Copy selected files on the existing authorized route and verify their bytes/hashes after return.',
                                    'No files are downloaded or deleted; incomplete manifests are not exhaustive result inventories.']},
                    {'return_manifest.json':json.dumps(manifest,indent=2),'selected-files.txt':'\n'.join(r['path'] for r in selected)+'\n'})
