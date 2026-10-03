"""Select the fresh CI installation without publishing host-specific configuration."""
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from install import runtime_python

root=Path(os.environ['RUNNER_TEMP'])/'BiomniLocal'
binary=root/'.local'/'bin'/('vina.exe' if os.name=='nt' else 'vina')
subprocess.run([str(runtime_python(root)),'tests/analysis_check.py'],check=True,env={**os.environ,'VINA':str(binary),'PYTHONUTF8':'1','BIOMNI_COMPUTE_EDITION':'local','NUMBA_NUM_THREADS':'2','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})
subprocess.run([str(runtime_python(root)),'tests/advanced_check.py'],check=True,env={**os.environ,'PYTHONUTF8':'1','BIOMNI_COMPUTE_EDITION':'local','NUMBA_NUM_THREADS':'2','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})
