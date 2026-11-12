"""Materialize fixed result-to-input transforms on the authorized server only. Never submit."""
from pathlib import Path
import csv,json,shutil,sys,platform,os
import hashlib
from runtime import read,write,sha,selected,guard

def materialize(server_request,receipt_file,review_file,returned_root,spec,out):
    request=read(server_request);guard(request)
    receipt=read(receipt_file);review=read(review_file)
    spec_hash=hashlib.sha256(json.dumps(spec,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()
    if review.get('handoff_spec_sha256')!=spec_hash:raise ValueError('Scientific review must bind the exact transform, mapping, target template and intended use')
    if review.get('transform_source_sha256')!=sha(Path(__file__)):raise ValueError('Scientific transform code changed after the reviewed plan')
    if receipt.get('state')!='COMPLETED' or receipt.get('exit_code')!=0 or receipt.get('request_sha256')!=sha(server_request):raise ValueError('Real bound upstream completion receipt required')
    if review.get('state')!='RETURN_CHECKS_PASS' or review.get('receipt_sha256')!=sha(receipt_file) or not review.get('scientific_reviewer') or review.get('scientific_decision')!='ACCEPT_FOR_SPECIFIED_NEXT_STAGE':raise ValueError('Engineering receipt alone cannot authorize scientific handoff')
    if spec.get('target_analysis_id') not in review.get('allowed_next_analyses',[]):raise ValueError('Review did not accept this next scientific use')
    if spec.get('expected_context')!=review.get('reviewed_context'):raise ValueError('Species/assembly/unit/reference context differs from review')
    contexts=[r for r in request['inputs'] if r['id']=='context']
    if len(contexts)!=1:raise ValueError('Exact upstream scientific context input is required')
    context_file=selected(Path(server_request).parent,contexts[0]['path'])
    if sha(context_file)!=contexts[0]['sha256']:raise ValueError('Actual source context changed')
    actual_context=read(context_file)
    for key in ('species','assembly','annotation_version','independent_unit','estimand','scale','reference_versions'):
        if spec['expected_context'].get(key)!=actual_context.get(key) or not actual_context.get(key):raise ValueError('Handoff context does not match actual source: '+key)
    records={r['path']:r for r in receipt['outputs']};source=spec['source_path']
    if source not in records:raise ValueError('Unregistered upstream result')
    if records[source]['role']!=spec['source_role']:raise ValueError('Selected source is not the reviewed scientific result role')
    target_template=selected(returned_root,spec['target_template_path'])
    if sha(target_template)!=spec['target_template_sha256']:raise ValueError('Target scientific template changed')
    target=read(target_template)
    if target.get('public_upload') is not False or target.get('server_execution_authorized') is not False or target.get('analysis_id')!=spec['target_analysis_id'] or spec['target_input_id'] not in {r['id'] for r in target['inputs']}:raise ValueError('Reviewed disabled target stage/input does not match the transform')
    f=selected(returned_root,source)
    if sha(f)!=records[source]['sha256'] or f.stat().st_size!=records[source]['bytes']:raise ValueError('Upstream result changed after completion')
    out=Path(out)
    if out.exists():raise FileExistsError('Fresh handoff target only')
    out.parent.mkdir(parents=True,exist_ok=True);transform=spec['transform'];rows_written=0
    if transform=='identity':
        with f.open(encoding='utf-8-sig',newline='') as h:
            reader=csv.DictReader(h,delimiter='\t')
            if not set(spec['target_required_columns'])<=set(reader.fieldnames or []):raise ValueError('Identity transform lacks the exact target table schema')
            rows_written=sum(1 for _ in reader)
        with f.open('rb') as source_handle,out.open('xb') as target_handle:shutil.copyfileobj(source_handle,target_handle)
    else:
        with f.open(encoding='utf-8-sig',newline='') as handle:reader=csv.DictReader(handle,delimiter='\t');rows=list(reader)
        if not rows:raise ValueError('Empty upstream denominator is not usable evidence')
        if transform=='liana_to_donor_lr':
            cols=['sample_id','unit_id','source','target','ligand','receptor','score','score_kind'];result=[];unit_to_sample=spec['unit_to_sample']
            if len(set(unit_to_sample.values()))!=len(unit_to_sample):raise ValueError('One-to-one donor/sample mapping required')
            for r in rows:
                if 'abundance_score' not in r:raise ValueError('Per-donor rank normalization is not comparable abundance; select the actual donor abundance-score output')
                score=float(r['abundance_score'])
                if not __import__('math').isfinite(score) or score<0:raise ValueError('Invalid common-scale LR abundance score')
                result.append({'sample_id':unit_to_sample[r['unit_id']],'source':r['source'],'target':r['target'],
                  'unit_id':r['unit_id'],'ligand':r['ligand'],'receptor':r['receptor'],'score':score,'score_kind':'log1p_ligand_receptor_mean_product'})
            keys=[tuple(r[k] for k in ('sample_id','source','target','ligand','receptor')) for r in result]
            if len(keys)!=len(set(keys)):raise ValueError('Resolve duplicate donor interactions explicitly before contrast')
        elif transform=='scirpy_to_clone_cells':
            metadata=selected(returned_root,spec['metadata_path'])
            if sha(metadata)!=spec['metadata_sha256']:raise ValueError('Phenotype/barcode metadata changed')
            with metadata.open(encoding='utf8',newline='') as h:metadata_rows=list(csv.DictReader(h,delimiter='\t'))
            md={r['cell_id']:r for r in metadata_rows}
            if len(md)!=len(metadata_rows):raise ValueError('Duplicate cell identity in selected phenotype metadata')
            result=[]
            for r in rows:
                if r['cell_id'] not in md or r['unit_id']!=md[r['cell_id']]['unit_id'] or r['sample_id']!=md[r['cell_id']]['sample_id']:raise ValueError('Clone/phenotype sample or independent unit mismatch')
                result.append({**md[r['cell_id']],**r,'clone_id':r['donor_clone']})
            cols=list(result[0])
        elif transform=='fgsea_leading_members':
            if spec.get('delimiter') not in (';',',','|'):raise ValueError('Explicit source leading-edge delimiter required')
            cols=['term','feature_id'];result=[]
            for r in rows:
                for gene in r[spec['members_column']].split(spec['delimiter']):
                    if gene:result.append({'term':r[spec['term_column']],'feature_id':gene})
        elif transform=='stable_one_to_one_identifiers':
            mp=selected(returned_root,spec['mapping_path'])
            if sha(mp)!=spec['mapping_sha256'] or not spec.get('mapping_version'):raise ValueError('Exact reviewed identifier map/version required')
            with mp.open(encoding='utf8',newline='') as h:mapping=list(csv.DictReader(h,delimiter='\t'))
            if len({r['source_id'] for r in mapping})!=len(mapping) or len({r['target_id'] for r in mapping})!=len(mapping):raise ValueError('Many-to-one/ambiguous mapping cannot be silently collapsed')
            lookup={r['source_id']:r['target_id'] for r in mapping};result=[];col=spec['identifier_column']
            for r in rows:
                if r[col] not in lookup:raise ValueError('Identifier map incomplete for selected denominator')
                result.append({**r,col:lookup[r[col]]})
            cols=list(result[0])
        else:raise ValueError('Unsupported scientific handoff transform')
        if not set(spec['target_required_columns'])<=set(cols):raise ValueError('Transform does not provide target scientific input schema')
        with out.open('x',encoding='utf8',newline='') as h:
            writer=csv.DictWriter(h,fieldnames=cols,delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(result)
        rows_written=len(result)
    receipt_out=out.with_name(out.name+'.lineage.private.json')
    write(receipt_out,{'source_receipt_sha256':sha(receipt_file),'source_request_sha256':sha(server_request),'source_output_sha256':sha(f),
      'review_sha256':sha(review_file),'transform':transform,'transform_source_sha256':sha(Path(__file__)),'output_sha256':sha(out),
      'rows_materialized':rows_written,'target_analysis_id':spec['target_analysis_id'],'context':spec['expected_context'],
      'next_state':'INPUT_MATERIALIZED_REQUIRES_NEW_QC_AND_NEW_PLAN','server_submission':False,'public_upload':False})
    return receipt_out

if __name__=='__main__':
    if len(sys.argv)!=8:raise SystemExit('handoff71.py SERVER_REQUEST RECEIPT REVIEW RETURN_ROOT SPEC_JSON FRESH_TARGET CONFIRM_PRIVATE')
    if sys.argv[7]!='PRIVATE_NO_SUBMISSION':raise SystemExit('Explicit private handoff purpose required')
    result=materialize(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],read(sys.argv[5]),sys.argv[6])
    print(json.dumps({'lineage_receipt':str(result),'server_submission':False,'public_upload':False}))
