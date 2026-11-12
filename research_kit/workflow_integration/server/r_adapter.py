from pathlib import Path
import json
import subprocess
from runtime import write,read,sha

def analyze(inputs,p,out,mode):
    if p['method'] in {'DESeq2','limma','WGCNA','edgeR_QL','limma_voom'}:
        qc=read(inputs['matrix_qc']);review=read(inputs['qc_host_review']);receipt=read(inputs['matrix_qc_receipt'])
        if qc.get('numerical_qc_pass') is not True or qc.get('matrix_sha256')!=sha(inputs['matrix']) or qc.get('metadata_sha256')!=sha(inputs['metadata']):
            raise ValueError('Formal inference requires successful QC of these exact real matrix/metadata bytes')
        if review.get('qc_sha256')!=sha(inputs['matrix_qc']) or review.get('reviewed_by_host') is not True or not review.get('outlier_batch_decisions'):
            raise ValueError('Actual QC plots/outliers/batches require an exact source-bound host review before inference')
        if receipt.get('state')!='COMPLETED' or receipt.get('exit_code')!=0 or receipt.get('source_sha256',{}).get('matrix_qc.py')!=sha(Path(__file__).with_name('matrix_qc.py')):
            raise ValueError('Matrix-QC runtime/source receipt is absent or stale')
        if not any(r.get('role')=='matrix_qc' and r.get('sha256')==sha(inputs['matrix_qc']) for r in receipt.get('outputs',[])):
            raise ValueError('QC runtime receipt does not bind the actual numerical report')
    exe=Path(p['rscript'])
    if not exe.is_absolute() or not exe.is_file() or exe.name!='Rscript':raise ValueError('Select existing absolute server Rscript executable')
    script=Path(__file__).with_name('omics.R')
    config={'inputs':{k:str(v) for k,v in inputs.items()},'parameters':p,'out':str(out)}
    write(out/'r_request.private.json',config)
    with (out/'r.stdout.log').open('xb') as log,(out/'r.stderr.log').open('xb') as err:
        proc=subprocess.run([str(exe),str(script),str(out/'r_request.private.json')],stdout=log,stderr=err,check=False)
    if proc.returncode:raise RuntimeError('R backend failed; inspect preserved r.stderr.log')
    roles=json.loads((out/'r_outputs.json').read_text(encoding='utf8'))
    outputs=[(out/row['file'],row['role']) for row in roles]
    for filename,role in [('r.stdout.log','backend_stdout'),('r.stderr.log','backend_stderr')]:
        if (out/filename).stat().st_size:outputs.append((out/filename,role))
    return outputs
