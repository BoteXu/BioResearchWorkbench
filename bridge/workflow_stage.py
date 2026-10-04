"""Fixed workflow stage runner with actual dependency receipts and mandatory QC JSON."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def run(config_path,stage_id):
    cp=Path(config_path).resolve(strict=True);root=cp.parent;config=json.loads(cp.read_text());stages={s['id']:s for s in config['stages']};s=stages[stage_id]
    configuration_sha256=hashlib.sha256(cp.read_bytes()).hexdigest();receipts=root/'.receipts';receipts.mkdir(exist_ok=True)
    outputs={p for stage in stages.values() for p in stage['outputs']}
    external={p for stage in stages.values() for p in stage.get('inputs',[]) if p not in outputs}
    external_hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sorted(external)}
    external_hashes['workflow_stage.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    receipt_path=receipts/(stage_id+'.json')
    # One durable exclusive lock: unknown/interrupted writes require inspection, never auto retry.
    with (receipts/(stage_id+'.lock')).open('x') as stream:stream.write(configuration_sha256)
    for d in s.get('depends_on',[]):
        r=json.loads((receipts/(d+'.json')).read_text())
        if r.get('configuration_sha256')!=configuration_sha256 or r.get('state')!='succeeded' or r.get('qc_pass') is False:raise ValueError('Dependency/QC not accepted')
        if r.get('external_input_hashes')!=external_hashes:raise ValueError('QC/input/code binding changed')
        for out in r.get('outputs',[]):
            p=root/out['path']
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=out['sha256']:raise ValueError('Dependency output changed')
    targets=[]
    for name in s['outputs']:
        p=(root/name).resolve()
        if not p.is_relative_to(root) or p.exists():raise ValueError('Fresh output within project required')
        targets.append(p)
    subprocess.run(s['argv'],cwd=root,timeout=s['resources']['wall_minutes']*60,check=True)
    manifest=[]
    for p in targets:
        if not p.is_file() or not p.stat().st_size:raise ValueError('Output missing or empty')
        manifest.append({'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    qc=None
    if s['kind']=='qc':
        gate=s.get('qc_gate_output')
        if gate not in s['outputs'] or json.loads((root/gate).read_text()).get('gate_pass') is not True:raise ValueError('QC gate JSON did not pass')
        qc=True
    if any(hashlib.sha256((root/p).read_bytes()).hexdigest()!=h for p,h in external_hashes.items() if p!='workflow_stage.py'):
        raise ValueError('External source/input changed during workflow stage')
    data={'schema':1,'stage':stage_id,'configuration_sha256':configuration_sha256,'external_input_hashes':external_hashes,'state':'succeeded','qc_pass':qc,'outputs':manifest}
    receipt_path.write_text(json.dumps(data),encoding='utf8')
    # Nextflow requires an output in its task working directory; source receipt remains in owned project.
    current=Path.cwd().resolve()
    if current!=root:
        destination=current/'.receipts';destination.mkdir(exist_ok=True)
        with (destination/(stage_id+'.json')).open('x',encoding='utf8') as stream:json.dump(data,stream)
    return 0


if __name__=='__main__':sys.exit(run(sys.argv[1],sys.argv[2]))
