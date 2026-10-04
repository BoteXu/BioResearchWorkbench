"""Read-only Slurm probe executed explicitly on an owned submission host."""
import argparse
import getpass
import hashlib
import json
import os
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path, PurePosixPath

FIELDS = ['job_id','state','exit_code','elapsed_seconds','max_rss','cpus','nodes','cpu_seconds','requested_memory','owner']


def validate(request):
    ids = request.get('job_ids')
    if request.get('schema') != 1 or not isinstance(ids,list) or not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids):
        raise ValueError('Select 1 to 100 distinct job IDs')
    if any(not isinstance(j,str) or not re.fullmatch(r'[1-9][0-9]{0,17}(?:_[0-9]{1,9})?',j) for j in ids):
        raise ValueError('Invalid job ID')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,252}',request.get('submission_host','')):
        raise ValueError('Explicit verified submission hostname required')
    logs=request.get('log_files',[])
    if not isinstance(logs,list) or len(logs)>10 or len(set(logs))!=len(logs):raise ValueError('Select at most 10 distinct logs')
    if logs and not PurePosixPath(request.get('log_root','')).is_absolute():raise ValueError('Explicit server log root required')
    for f in logs:
        p=PurePosixPath(f)
        if not isinstance(f,str) or not f or p.is_absolute() or '..' in p.parts or '\\' in f or ':' in f or f!=p.as_posix():raise ValueError('Relative scoped log names required')
    return request


def command(argv):
    # Temporary files bound memory usage even if a scheduler emits excessive output.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc=subprocess.Popen(argv,stdout=out,stderr=err,shell=False)
        try:proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait();raise TimeoutError('Read-only scheduler probe timed out')
        if proc.returncode:raise RuntimeError('Read-only scheduler probe failed')
        if out.tell()>2_000_000:raise ValueError('Scheduler output exceeds bound')
        out.seek(0);return out.read().decode('utf8',errors='replace')


def parse_accounting(raw,job_ids,owner):
    records=[]
    for line in raw.splitlines():
        values=line.rstrip('|').split('|')
        if len(values)!=len(FIELDS):continue
        record=dict(zip(FIELDS,values));base=record['job_id'].split('.')[0]
        # A numeric selection can include its steps, but not other users' jobs.
        if base in job_ids and record['owner']==owner:records.append(record)
    return records


def scoped_tail(root,name):
    initial=Path(root)
    if initial.is_symlink():raise ValueError('Linked log roots refused')
    base=initial.resolve(strict=True);p=base/name
    if any(x.is_symlink() for x in [p,*p.parents] if x.is_relative_to(base)):raise ValueError('Linked logs refused')
    p=p.resolve(strict=True)
    if not p.is_relative_to(base) or not p.is_file():raise ValueError('Log outside scope')
    with p.open('rb') as f:
        f.seek(max(0,p.stat().st_size-200_000));raw=f.read(200_000)
    return {'relative_name':name,'tail':raw.decode('utf8',errors='replace'),'tail_sha256':hashlib.sha256(raw).hexdigest(),'truncated':p.stat().st_size>len(raw)}


def monitor(request):
    validate(request)
    if socket.gethostname()!=request['submission_host']:raise ValueError('Submission host changed; reverify route')
    owner=getpass.getuser();jobs=','.join(request['job_ids']);errors=[]
    def probe(argv):
        try:return command(argv)
        except (OSError,RuntimeError,TimeoutError,ValueError) as e:
            errors.append(type(e).__name__);return ''
    queue=probe(['squeue','--noheader','--user',owner,'--jobs',jobs,'--format=%i|%T|%R|%N|%C|%m|%M'])
    acct=probe(['sacct','--noheader','--parsable2','--user',owner,'--jobs',jobs,'--format=JobIDRaw,State,ExitCode,ElapsedRaw,MaxRSS,AllocCPUS,NodeList,TotalCPU,ReqMem,User'])
    records=parse_accounting(acct,request['job_ids'],owner);summaries=[]
    for job in request['job_ids']:
        exact=[r for r in records if r['job_id']==job]
        row=exact[-1] if exact else None
        summaries.append({'job_id':job,'state':row['state'] if row else 'UNKNOWN','scheduler_completed':bool(row and row['state']=='COMPLETED' and row['exit_code']=='0:0'),'accounting':row})
    logs=[]
    for name in request.get('log_files',[]):
        try:logs.append(scoped_tail(request['log_root'],name))
        except (OSError,ValueError) as e:errors.append('log_'+type(e).__name__)
    return {'schema':1,'request_sha256':hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'observed_at_unix':time.time(),'observed_host':socket.gethostname(),'state':'observed' if not errors else 'partial_or_unavailable',
            'jobs':summaries,'queue_raw':queue,'accounting_records':records,'logs':logs,'errors':errors,'scientific_completion_verified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('request');p.add_argument('output');args=p.parse_args()
    target=Path(args.output)
    if target.exists():raise ValueError('Use a fresh receipt filename')
    data=monitor(json.loads(Path(args.request).read_text(encoding='utf8')))
    with target.open('x',encoding='utf8') as f:json.dump(data,f,indent=2)
    print('READ_ONLY_SLURM_RECEIPT_WRITTEN')
