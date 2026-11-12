"""Explicit private frozen-result handoff to the selected visualization draft."""
from pathlib import Path
import sys
from acceptance import load,selected,sha

HERE=Path(__file__).resolve().parent

def prepare(root,spec):
    if spec.get('public_upload') is not False:raise ValueError('Private figure preparation only')
    skill=Path(spec['skill_root']).resolve(strict=True)
    if not (skill/'scripts/analysis_results.py').is_file():raise ValueError('Select the compatible scientific-visualization private draft; no installation or client switching is performed')
    for k in ['scientific_request','server_receipt','return_acceptance']:
        if k not in spec:raise ValueError('Exact completed-result request/receipt/QC files required')
    return_root=Path(root).resolve(strict=True)
    files={k:selected(return_root,spec[k]) for k in ['scientific_request','server_receipt','return_acceptance']}
    source={p.name:sha(p) for p in (HERE/'server').iterdir() if p.is_file() and p.suffix in {'.py','.R','.json'}}
    sys.path.insert(0,str(skill/'scripts'))
    from analysis_results import plan_result_figures
    return plan_result_figures(files['scientific_request'],files['server_receipt'],return_root,files['return_acceptance'],spec['selected_outputs'],source)
