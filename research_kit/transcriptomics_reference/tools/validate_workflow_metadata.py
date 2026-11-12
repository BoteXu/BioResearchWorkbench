"""Offline metadata checks. Does not read expression matrices, fit models or dispatch work."""
from pathlib import Path
from datetime import datetime
import argparse, csv, json, math

MISSING={'','NA','null','None','TBD'}
RELATIONS={
 'sample_of_donor':('sample','donor'),'sample_in_capture':('sample','capture'),
 'library_from_capture':('library','capture'),'library_from_sample':('library','sample'),
 'sequencing_of_library':('run','library'),'cell_from_capture':('cell','capture'),
 'cell_assigned_sample':('cell','sample'),'cell_assigned_donor':('cell','donor')
}
def absent(value):
    if value is None:return True
    if isinstance(value,str):return value.strip() in MISSING
    if isinstance(value,(list,dict)):return not value
    return False

def check_tables(dictionary,tables,allow_empty=False,cross_references=True):
    schemas={s['name']:s for s in dictionary['schemas']};issues=[]
    if not isinstance(tables,dict):
        return {'success':True,'metadata_contract_pass':False,'issues':['tables_not_object'],'formal_analysis_allowed':False,'server_submitted':False}
    clean={}
    for name,rows in tables.items():
        if name not in schemas:issues.append(f'{name}:unknown_table');continue
        if not isinstance(rows,list):issues.append(f'{name}:rows_not_list');continue
        columns={f['name'] for f in schemas[name]['fields']}
        clean[name]=[]
        for i,row in enumerate(rows):
            if not isinstance(row,dict) or set(row)!=columns:
                issues.append(f'{name}:{i+1}:columns');continue
            if any(not isinstance(x,(str,int,float,bool,type(None))) for x in row.values()):
                issues.append(f'{name}:{i+1}:non_scalar_metadata');continue
            clean[name].append(row)
    tables=clean
    for name,rows in tables.items():
        if name not in schemas:issues.append(f'{name}:unknown_table');continue
        s=schemas[name];columns={f['name'] for f in s['fields']}
        if not rows and not allow_empty:issues.append(f'{name}:empty_not_project_evidence')
        keys=[s['primary_key'],*s.get('unique_constraints',[])];seen=[set() for _ in keys]
        for i,row in enumerate(rows):
            at=f'{name}:{i+1}'
            if set(row)!=columns:issues.append(at+':columns');continue
            for f in s['fields']:
                value=row[f['name']];loc=at+':'+f['name']
                if absent(value):
                    if f['required']=='always' or f['name'] in s['primary_key']:issues.append(loc+':missing')
                    continue
                try:
                    t=f['type']
                    if t=='string' and not isinstance(value,str):raise ValueError()
                    if t=='enum' and value not in f['allowed_values']:raise ValueError()
                    if t=='boolean' and value not in {'true','false'}:raise ValueError()
                    if t in {'integer','number'}:
                        if isinstance(value,bool):raise ValueError()
                        n=float(value)
                        if not math.isfinite(n) or (t=='integer' and (not n.is_integer() or n<0)):raise ValueError()
                    if t=='datetime':datetime.fromisoformat(str(value).replace('Z','+00:00'))
                except (ValueError,TypeError,OverflowError):issues.append(loc+':type_or_enum')
            for j,cols in enumerate(keys):
                k=tuple(str(row[c]) for c in cols)
                if k in seen[j]:issues.append(at+':duplicate_key:'+','.join(cols))
                seen[j].add(k)
            if name=='availability':
                if row['mapping_status']=='unmapped' and not absent(row['feature_id']):issues.append(at+':unmapped_has_resolved_id')
                if row['resolution_status']=='resolved' and absent(row['feature_id']):issues.append(at+':resolved_missing_id')
            if name=='meta':
                if row['role'] in {'leave_one_out','subgroup'} and row['heldout_or_subgroup'] in {'none',*MISSING}:issues.append(at+':variant_definition_missing')
                if not absent(row['sampling_se']):
                    try:
                        if float(row['sampling_se'])<=0:issues.append(at+':nonpositive_sampling_se')
                    except (TypeError,ValueError):pass
            if name=='method_readiness':
                executed=row['engineering_state'] in {'example_executed','project_executed','independent_reproduction'}
                if executed and absent(row['receipt_manifest']):issues.append(at+':execution_receipt_missing')
                if not executed and row['numeric_state']=='pass':issues.append(at+':numeric_acceptance_without_execution')
                if row['scientific_state']=='adopt' and (row['engineering_state'] not in {'project_executed','independent_reproduction'} or row['numeric_state']!='pass'):issues.append(at+':scientific_adoption_without_project_acceptance')
            if name=='acceptance' and row['status']=='PASS':
                if absent(row['evidence_path_hash']) or row['evidence_path_hash']=='none':issues.append(at+':pass_without_evidence')
                if row['acceptance_layer'] in {'engineering','method_numeric','scientific'} and row['execution_state']!='completed':issues.append(at+':pass_without_completed_execution')
            if name=='trajectory_review' and row['mode']=='population_dynamic' and row['decision']=='ready_for_server':
                if str(row['independent_unit']).lower() in {'cell','cells','nucleus','spot','neighborhood'}:issues.append(at+':pseudoreplication_unit')
                if row['dependence_policy'] in {'none','unknown',*MISSING}:issues.append(at+':dependence_plan_missing')
    if cross_references:
        identity={r['identity_id']:r for r in tables.get('identity',[]) if 'identity_id' in r}
        for r in tables.get('identity_link',[]):
            a=identity.get(r.get('source_identity_id'));b=identity.get(r.get('target_identity_id'))
            if a is None or b is None:issues.append('identity_link:missing_entity_reference');continue
            if (a['record_level'],b['record_level'])!=RELATIONS.get(r['relation_type']):issues.append('identity_link:relation_endpoint_types')
        foreign=[('identity','dataset_id','dataset','dataset_id'),('availability','dataset_id','dataset','dataset_id'),('meta','model_id','model','model_id'),('trajectory_review','backend_readiness_id','method_readiness','readiness_id'),('method_readiness','request_id','analysis_request','request_id')]
        for source,key,target,pk in foreign:
            for row in tables.get(source,[]):
                if row.get(key) not in {r.get(pk) for r in tables.get(target,[])}:issues.append(source+':missing_reference:'+target+'.'+pk)
    variants={}
    for r in tables.get('meta',[]):
        k=(r.get('run_id'),r.get('analysis_variant_id'),r.get('scope_id'))
        v=tuple(r.get(x) for x in ['role','heldout_or_subgroup','model_id'])
        if k in variants and variants[k]!=v:issues.append('meta:inconsistent_variant_definition')
        variants[k]=v
    return {'success':True,'metadata_contract_pass':not issues,'issues':issues,'scope':'declared metadata only; source identity, receipt authenticity and scientific validity require independent review','formal_analysis_allowed':False,'server_submitted':False}

def check_project(project,requirements):
    issues=[]
    if not isinstance(project,dict):return {'success':True,'planning_metadata_complete':False,'issues':['project_not_object'],'formal_analysis_allowed':False,'server_submitted':False}
    if project.get('workflow_version')!=requirements['version']:issues.append('workflow_version')
    if project.get('execution_authorized') is not False:issues.append('planning_template_must_not_authorize_execution')
    if project.get('overwrite_outputs') is not False:issues.append('overwrite_policy')
    if project.get('unknown_submission_policy')!='inspect_existing_receipts_do_not_retry':issues.append('unknown_submission_policy')
    for f in requirements['always']:
        if absent(project.get(f)):issues.append('missing:'+f)
    requests=project.get('task_requests',[])
    selected=project.get('selected_modules',[])
    if not isinstance(selected,list) or any(not isinstance(x,str) or absent(x) for x in selected):
        issues.append('selected_modules_type');selected=[]
    if not isinstance(requests,list):requests=[];issues.append('task_requests_type')
    seen=set()
    for i,r in enumerate(requests):
        if not isinstance(r,dict):issues.append(f'task:{i}:not_object');continue
        rid=r.get('request_id');kind=r.get('task_type')
        if not isinstance(rid,str) or absent(rid):issues.append(f'task:{i}:request_id_type')
        elif rid in seen:issues.append('duplicate_request_id')
        else:seen.add(rid)
        if not isinstance(kind,str) or kind not in requirements['tasks']:issues.append(f'task:{i}:unsupported_task');continue
        for f in [*requirements['per_task_common'],*requirements['tasks'][kind]]:
            if absent(r.get(f)):issues.append(f'task:{i}:missing:{f}')
        if r.get('module_id') not in selected:issues.append(f'task:{i}:module_not_selected')
        if not isinstance(r.get('parameters'),dict):issues.append(f'task:{i}:parameters_not_object')
        outputs=r.get('expected_outputs')
        if not isinstance(outputs,list) or not outputs or any(not isinstance(x,str) or absent(x) for x in outputs):issues.append(f'task:{i}:expected_outputs_type')
        if kind in {'bulk_de','celltype_de'} and r.get('matrix_kind') not in {'raw_counts','estimated_counts_with_valid_import','log2_normalized'}:issues.append(f'task:{i}:unsupported_expression_scale')
        if kind=='trajectory_population' and (not isinstance(r.get('dependence_policy'),str) or r.get('dependence_policy') in {'none','unknown'}):issues.append(f'task:{i}:population_dependence_unspecified')
    return {'success':True,'planning_metadata_complete':not issues,'issues':issues,'formal_analysis_allowed':False,'server_submitted':False,'server_backend_validated':False,'scope':'Checks declared planning fields only. A nonempty acceptance reference is not authenticated by this checker; review its scope and actual receipts before server work.'}

def read_tables(path,dictionary):
    tables={};errors=[]
    for s in dictionary['schemas']:
        f=path/(s['name']+'.tsv')
        if not f.is_file():errors.append(s['name']+':missing_file');continue
        if f.stat().st_size>10_000_000:errors.append(s['name']+':not_bounded_metadata');continue
        with f.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream,delimiter='\t')
            if reader.fieldnames!=[x['name'] for x in s['fields']]:errors.append(s['name']+':header_mismatch');continue
            rows=[]
            for i,row in enumerate(reader):
                if i>=10000:errors.append(s['name']+':row_bound');break
                rows.append(row)
            tables[s['name']]=rows
    return tables,errors

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--templates',type=Path,required=True);ap.add_argument('--project',type=Path);ap.add_argument('--allow-empty-templates',action='store_true');a=ap.parse_args()
    d=json.loads((a.templates/'data_dictionary.json').read_text(encoding='utf8'))
    tables,errors=read_tables(a.templates,d);r=check_tables(d,tables,a.allow_empty_templates)
    r['issues']=errors+r['issues'];r['metadata_contract_pass']=not r['issues']
    if a.project:r['project']=check_project(json.loads(a.project.read_text(encoding='utf8')),json.loads((a.templates/'task_requirements.json').read_text(encoding='utf8')))
    print(json.dumps(r,ensure_ascii=False,indent=2))
    raise SystemExit(0 if r['metadata_contract_pass'] and r.get('project',{}).get('planning_metadata_complete',True) else 2)
