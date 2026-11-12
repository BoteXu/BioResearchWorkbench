"""Exact origin-generation lineage; never reinterpret historical success as current science."""
from pathlib import Path
from contracts import read,sha,selected,sources
from postanalysis_contracts import lineage_spec
def load_origin(request,ids,root):
    from acceptance import inspect
    spec=lineage_spec(read(ids['structure_manifest']),request['method']);path=selected(root,spec['origin_request'])
    if sha(path)!=spec['origin_request_sha256']:raise ValueError('Origin generation request changed')
    origin=read(path);returned=(Path(root)/spec['origin_return_root']).resolve(strict=True)
    if not returned.is_relative_to(Path(root).resolve()) or not returned.is_dir():raise ValueError('Origin returned root escaped selected project')
    receipt_path=selected(returned,'receipt.private.json')
    if sha(receipt_path)!=spec['origin_receipt_sha256']:raise ValueError('Origin generation receipt changed')
    if origin.get('method')!='shepherd2_generate' or origin.get('source_sha256')!=sources():raise ValueError('Old/different generation source needs migration or re-review')
    result=inspect(path,returned,spec['selected_return_files'])
    allowed={'prespecified_chemical_valid_fraction_failed','prespecified_constraint_pass_fraction_failed'}
    qc_only=lambda x:x in allowed or x.startswith('prespecified_actual_QC_gate_failed:')
    if result['state']!='RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW':
        if request['method']!='paper_native_evaluation' or not result['issues'] or not all(qc_only(x) for x in result['issues']):raise ValueError('Origin integrity or source candidate qualification is on HOLD')
    variant=spec['origin_variant'];variants={'primary'}|{x['label'] for x in origin['sensitivity_variants']}
    if variant not in variants:raise ValueError('Unknown origin generation variant')
    receipt=read(receipt_path);outputs={x['path']:x for x in receipt['outputs']};context=selected(returned,'source_context.private.json')
    if sha(ids['context'])!=sha(context):raise ValueError('Post-analysis context differs from exact origin')
    structures=read(selected(returned,'source_structures.private.json'));contract=read(selected(returned,variant+'/generation_contract.private.json'))
    eligible=[x for x in read(selected(returned,'eligible_candidate_outputs.private.json')) if x['variant']==variant]
    if request['method']=='prepare_generated_identities' and not set(spec['candidate_ids'])<={x['candidate_id'] for x in eligible}:raise ValueError('Selected source candidate failed generation qualification')
    return {'spec':spec,'origin':origin,'origin_path':path,'origin_root':path.parent,'returned':returned,'receipt':receipt,'outputs':outputs,'variant':variant,'context':read(context),'structures':structures,'contract':contract,'eligible':eligible,'source_review':result}
def bound_output(origin,path):
    row=origin['outputs'].get(path)
    if row is None:raise ValueError('Required origin output is unregistered')
    f=selected(origin['returned'],path)
    if sha(f)!=row['sha256'] or f.stat().st_size!=row['bytes']:raise ValueError('Original scientific artifact bytes changed')
    return f
