"""Source/contract checks only, in independent processes; scientific engines remain unrun."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parent
bridge=Path(os.environ['BIORESEARCH_BRIDGE_ROOT']).resolve(strict=True) if os.environ.get('BIORESEARCH_BRIDGE_ROOT') else ROOT.parent/'bridge'
if not (bridge/'statistics_ext.py').is_file():
 raise SystemExit('Select the existing core via BIORESEARCH_BRIDGE_ROOT; no placeholder statistics tool is used')
env={**os.environ,'PYTHONPATH':str(bridge),'PYTHONDONTWRITEBYTECODE':'1','MPLBACKEND':'Agg','PYTHONUTF8':'1'}
groups=[('bulk_optional','bulk_optional/tests','test_private_bulk.py'),('workflow_integration','workflow_integration','tests*.py'),('virtual_perturbation','virtual_perturbation/tests','test_*.py'),('interaction_profiles','interaction_profiles/tests','test_*.py'),('figure_result_consumers','tests','test_figure*.py')]
failed=[]
for label,folder,pattern in groups:
 path=ROOT/folder;cwd=path.parent if path.name=='tests' else path
 start='tests' if path.name=='tests' else '.'
 print('Contract group:',label,flush=True)
 r=subprocess.run([sys.executable,'-X','utf8','-m','unittest','discover','-s',start,'-p',pattern],cwd=cwd,env=env,timeout=300)
 if r.returncode:failed.append(label)
print('Failed groups:',failed,'; native scientific engine runs: 0',flush=True)
raise SystemExit(bool(failed))
