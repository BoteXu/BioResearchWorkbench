"""Run this standard-library adapter on an owned Slurm submission host; never performs local SSH."""
import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path


def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8');os.replace(temp,path)


def run(argv):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=30,shell=False)
    if p.returncode: raise RuntimeError('Scheduler command failed: '+p.stderr[:2000])
    return p.stdout


def operate(folder,action):
    folder=Path(folder).resolve(strict=True);profile=json.loads((folder/'scheduler.json').read_text());path=folder/'scheduler_receipt.json'
    if socket.gethostname()!=profile['submission_host']: raise ValueError('Submission hostname mismatch; verify the current route')
    if action=='submit':
        lock=folder/'scheduler_submit.lock'
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
        attempted=False
        try:
            if path.exists(): raise ValueError('Submission receipt already exists; inspect before recovery')
            attempted=True
            output=run(['sbatch','--parsable','--cpus-per-task='+str(profile['cpus']),'--mem='+str(profile['memory_mb']),'--time='+profile['walltime'],'--partition='+profile['partition'],'--chdir='+str(folder),'--output='+str(folder/'slurm-%j.log'),str(folder/'submit.sh')]).strip()
            match=re.fullmatch(r'(\d+)(?:;([A-Za-z0-9_.-]+))?',output)
            if not match:
                save(path,{'state':'submission_outcome_unknown','raw_output':output,'submitted_at_unix':time.time()})
                raise ValueError('Unrecognized scheduler response; do not resubmit automatically')
            receipt={'schema':1,'job_id':match.group(1),'cluster':match.group(2),'state':'submitted','submission_host':socket.gethostname(),'task_sha256':hashlib.sha256((folder/'task.json').read_bytes()).hexdigest(),'submitted_at_unix':time.time(),'raw_submission':output}
            save(path,receipt)
        except Exception:
            if attempted and not path.exists(): save(path,{'state':'submission_outcome_unknown','submitted_at_unix':time.time()})
            raise
        finally: lock.unlink()
    else:
        receipt=json.loads(path.read_text());job=receipt.get('job_id','')
        if not re.fullmatch(r'\d+',job): raise ValueError('No verified scheduler job ID; inspect unknown submission before recovery')
        if action=='cancel':
            run(['scancel',job]);receipt['cancellation_requested_at_unix']=time.time();receipt['state']='cancellation_requested'
        elif action=='status':
            queue=run(['squeue','--noheader','--jobs',job,'--format=%i|%T|%R|%N'])
            accounting=run(['sacct','--noheader','--parsable2','--jobs',job,'--format=JobIDRaw,State,ExitCode,ElapsedRaw,MaxRSS,AllocCPUS,NodeList'])
            records=[]
            for line in accounting.splitlines():
                values=line.split('|')
                if len(values)>=7: records.append(dict(zip(['job_id','state','exit_code','elapsed_seconds','max_rss','cpus','nodes'],values[:7])))
            exact=[r for r in records if r['job_id']==job];receipt.update(queue_raw=queue,accounting_raw=accounting,accounting_records=records,checked_at_unix=time.time())
            receipt['scheduler_state']=exact[0]['state'] if exact else 'UNKNOWN'
            receipt['state']='scheduler_completed' if exact and exact[0]['state']=='COMPLETED' and exact[0]['exit_code']=='0:0' else 'scheduler_snapshot'
            returned=folder/'remote_receipt.json'
            if returned.is_file():
                result=json.loads(returned.read_text());receipt['remote_execution_state']=result.get('state');receipt['remote_exit_code']=result.get('exit_code')
            receipt['analysis_completion_verified']=False
        else: raise ValueError('Unsupported scheduler operation')
        save(path,receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['submit','status','cancel']);p.add_argument('folder',nargs='?',default='.')
    args=p.parse_args();print(json.dumps(operate(args.folder,args.action),indent=2))
