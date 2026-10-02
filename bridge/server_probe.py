"""Read-only server software inventory; no imports of scientific stacks or installs."""
import importlib.metadata
import json
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

data = {'host': socket.gethostname(), 'platform': platform.platform(), 'python': sys.version, 'python_executable': sys.executable, 'executables': {}, 'python_packages': {}, 'r_packages': None}
for name in ['Rscript', 'python3', 'conda', 'mamba', 'sbatch', 'squeue', 'qsub', 'qstat', 'gmx', 'gmx_mpi', 'salmon', 'STAR', 'fastqc', 'multiqc', 'samtools', 'plink', 'plink2']:
    data['executables'][name] = shutil.which(name)
for name in ['numpy', 'pandas', 'scipy', 'scanpy', 'anndata', 'pydeseq2', 'torch', 'SimpleITK', 'scikit-image']:
    try:
        data['python_packages'][name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        data['python_packages'][name] = None
if data['executables']['Rscript']:
    script = "for(n in c('DESeq2','edgeR','limma','coloc','TwoSampleMR','metafor','Seurat')) { ok <- requireNamespace(n,quietly=TRUE); cat(n,if(ok) as.character(packageVersion(n)) else 'unavailable',sep='=',fill=TRUE) }"
    try:
        r = subprocess.run([data['executables']['Rscript'], '--vanilla', '-e', script], capture_output=True, text=True, timeout=90)
        data['r_packages'] = {'exit_code': r.returncode, 'versions': r.stdout[-10000:], 'diagnostics': r.stderr[-2000:]}
    except Exception as exc:
        data['r_packages'] = {'error': str(exc)}
data['limitations'] = ['Active Python/R environment only; other conda/container environments may contain additional tools.', 'Package presence is not runtime or scientific validation.', 'No dependency installation or analysis was performed.']
Path('remote_environment.json').write_text(json.dumps(data, indent=2), encoding='utf8')
