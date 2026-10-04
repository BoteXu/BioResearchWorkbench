"""Explicit Slurm array dispatch of unchanged prepared tasks; no submission or retry."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


def run(configuration):
    cp=Path(configuration).resolve(strict=True);root=cp.parent;data=json.loads(cp.read_text())
    identity=os.environ.get('SLURM_ARRAY_TASK_ID','')
    if not identity.isdigit() or not 0<=int(identity)<len(data['tasks']):raise ValueError('Actual Slurm array task identity required')
    task=data['tasks'][int(identity)];name=PurePosixPath(task['task_file'])
    if name.is_absolute() or '..' in name.parts or '\\' in task['task_file']:raise ValueError('Owned relative task file required')
    p=(root/name).resolve(strict=True)
    if not p.is_relative_to(root) or hashlib.sha256(p.read_bytes()).hexdigest()!=task['sha256']:raise ValueError('Task scope/hash changed')
    if (p.parent/'array_dispatch.lock').exists():raise ValueError('Prior/unknown array dispatch; inspect receipts before recovery')
    with (p.parent/'array_dispatch.lock').open('x') as stream:stream.write(identity)
    return subprocess.run([sys.executable,str(root/'remote_runner.py'),str(p)],cwd=p.parent,check=False).returncode


if __name__=='__main__':sys.exit(run(sys.argv[1]))
