"""Separate benchmark contracts, actual engine completion and reference agreement."""
import json
import re
from pathlib import Path
from academic_common import artifact, read_file


def inspect_scientific_benchmarks() -> dict:
    """List small licensed public benchmark contracts; installation and runtime acceptance are not inferred."""
    path=Path(__file__).with_name('benchmark_catalog.json')
    if not path.exists():path=path.parent.parent/path.name
    return {'success':True,**json.loads(path.read_text(encoding='utf8')),'runtime_state':'requires_actual_receipt'}


def audit_benchmark_receipt(receipt_path: str, expected_receipt_sha256: str, benchmark_id: str) -> dict:
    """Check a selected returned benchmark receipt and report three acceptance layers; never collapse a reference match into general scientific validity."""
    import hashlib, math
    _,raw=read_file(receipt_path,2_000_000)
    if hashlib.sha256(raw).hexdigest()!=expected_receipt_sha256:raise ValueError('Benchmark receipt changed')
    r=json.loads(raw);spec=next((x for x in inspect_scientific_benchmarks()['benchmarks'] if x['id']==benchmark_id),None)
    if spec is None:raise ValueError('Unknown public benchmark')
    interface=r.get('schema')==1 and r.get('benchmark_id')==benchmark_id and isinstance(r.get('metrics'),dict)
    backend=interface and r.get('state')=='completed' and type(r.get('exit_code')) is int and r['exit_code']==0 and bool(r.get('backend_version')) and bool(r.get('dataset_version')) and r.get('design')==spec['design']
    issues=[]
    if not interface:issues.append('interface_contract_failed')
    if not backend:issues.append('backend_completion_or_design_unverified')
    if not re.fullmatch('[a-f0-9]{64}',str(r.get('input_sha256',''))):backend=False;issues.append('missing_input_binding')
    checks=[]
    for name,bounds in spec['reference_metrics'].items():
        value=r.get('metrics',{}).get(name);valid=type(value) in (int,float) and math.isfinite(value) and bounds['minimum']<=value<=bounds['maximum']
        checks.append({'metric':name,'reference_match':valid,'value':value})
    match=backend and all(x['reference_match'] for x in checks)
    return artifact('benchmark_audit',{'benchmark_id':benchmark_id,'receipt_sha256':expected_receipt_sha256,
                    'interface_correct':interface,'backend_completed':bool(backend),'reference_agreement':bool(match),
                    'checks':checks,'issues':issues,'scientific_validity':'not_established','acceptance_scope':spec['acceptance_scope'],
                    'limitations':['A returned receipt can be fabricated; inspect real runner logs and source files independently.',
                                    'A fixed benchmark tests one design and input version, not every method or biomedical interpretation.']})
