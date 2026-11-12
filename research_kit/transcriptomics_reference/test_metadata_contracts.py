"""Fictional metadata scenarios only. No scientific analysis or backend tests."""
from pathlib import Path
from copy import deepcopy
import importlib.util,json
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('checker',ROOT/'tools/validate_workflow_metadata.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
d=json.loads((ROOT/'templates/data_dictionary.json').read_text(encoding='utf8'));S={s['name']:s for s in d['schemas']}
req=json.loads((ROOT/'templates/task_requirements.json').read_text(encoding='utf8'))
tests=[]
def record(table,**kw):
    row={}
    for f in S[table]['fields']:
        row[f['name']]=(f['allowed_values'][0] if f['type']=='enum' else 'true' if f['type']=='boolean' else '1' if f['type'] in {'number','integer'} else '2026-10-24T00:00:00+00:00' if f['type']=='datetime' else 'DEMO')
    row.update(kw);return row
def check(name,condition):
    tests.append({'case':name,'passed':bool(condition)});assert condition,name

# One donor entity -> multiple sample entities; one capture -> multiple samples.
identity=[record('identity',identity_id=i,original_id=i,record_level=level,sample_id='NA' if level in {'donor','capture'} else i,condition='NA' if level in {'donor','capture'} else 'DEMO_CONDITION',time_region='NA' if level in {'donor','capture'} else 'DEMO_TIME') for i,level in [('D1','donor'),('D2','donor'),('S1','sample'),('S2','sample'),('S3','sample'),('C1','capture')]]
links=[record('identity_link',link_id=f'L{i}',source_identity_id=a,target_identity_id=b,relation_type=t,assignment_status='confirmed',confidence='NA') for i,(a,b,t) in enumerate([('S1','D1','sample_of_donor'),('S2','D1','sample_of_donor'),('S3','D2','sample_of_donor'),('S1','C1','sample_in_capture'),('S3','C1','sample_in_capture')])]
tables={'dataset':[record('dataset',dataset_id='DEMO')],'identity':identity,'identity_link':links}
check('donor_multiple_samples_and_mixed_capture_preserved',v.check_tables(d,tables)['metadata_contract_pass'])
bad=deepcopy(tables);bad['identity_link'][0]['target_identity_id']='ABSENT'
check('dangling_identity_edge_rejected',not v.check_tables(d,bad)['metadata_contract_pass'])
bad=deepcopy(tables);bad['identity_link'][0]['target_identity_id']='C1'
check('wrong_relation_endpoint_type_rejected',not v.check_tables(d,bad)['metadata_contract_pass'])
bad=deepcopy(tables);bad['identity'].append(deepcopy(identity[0]))
check('duplicate_identity_entity_rejected',not v.check_tables(d,bad)['metadata_contract_pass'])

av=[record('availability',availability_record_id=f'A{i}',original_feature_id=f'G{i}',feature_id='NA',mapping_status='unmapped',mapping_candidate_id='none',resolution_status='unresolved') for i in range(2)]
check('multiple_unmapped_features_preserved',v.check_tables(d,{'availability':av},cross_references=False)['metadata_contract_pass'])
av2=[record('availability',availability_record_id=f'A{i}',original_feature_id='G1',feature_id=f'F{i}',mapping_status='one_to_many',mapping_candidate_id=f'C{i}',resolution_status='unresolved') for i in range(2)]
check('one_to_many_candidates_preserved',v.check_tables(d,{'availability':av2},cross_references=False)['metadata_contract_pass'])
av3=[record('availability',availability_record_id=f'A{i}',original_feature_id=f'G{i}',feature_id='F1',mapping_status='many_to_one',mapping_candidate_id='F1',resolution_status='resolved') for i in range(2)]
check('many_to_one_sources_preserved',v.check_tables(d,{'availability':av3},cross_references=False)['metadata_contract_pass'])
bad=deepcopy(av2);bad[1]['mapping_candidate_id']='C0'
check('duplicate_mapping_candidate_rejected',not v.check_tables(d,{'availability':bad},cross_references=False)['metadata_contract_pass'])
bad=deepcopy(av);bad[0]['resolution_status']='resolved'
check('missing_resolved_gene_rejected',not v.check_tables(d,{'availability':bad},cross_references=False)['metadata_contract_pass'])

meta=[record('meta',estimate_id='EST0',analysis_variant_id='MAIN',scope_id='TYPE1',role='pooled',study_id='pooled',heldout_or_subgroup='none'),record('meta',estimate_id='EST1',analysis_variant_id='LOO_A',scope_id='TYPE1',role='leave_one_out',study_id='pooled',heldout_or_subgroup='STUDY_A'),record('meta',estimate_id='EST2',analysis_variant_id='LOO_B',scope_id='TYPE1',role='leave_one_out',study_id='pooled',heldout_or_subgroup='STUDY_B'),record('meta',estimate_id='EST3',analysis_variant_id='GROUP_A',scope_id='TYPE1',role='subgroup',study_id='pooled',heldout_or_subgroup='GROUP_A'),record('meta',estimate_id='EST4',analysis_variant_id='MAIN',scope_id='TYPE2',role='pooled',study_id='pooled',heldout_or_subgroup='none')]
check('main_all_leaveouts_subgroup_and_type_preserved',v.check_tables(d,{'meta':meta},cross_references=False)['metadata_contract_pass'])
bad=deepcopy(meta);bad.append(deepcopy(meta[0]));bad[-1]['estimate_id']='EST99'
check('duplicate_estimate_semantics_rejected',not v.check_tables(d,{'meta':bad},cross_references=False)['metadata_contract_pass'])
bad=deepcopy(meta);bad[1]['heldout_or_subgroup']='none'
check('undefined_leaveout_rejected',not v.check_tables(d,{'meta':bad},cross_references=False)['metadata_contract_pass'])

check('all_enums_have_allowed_values',all(f.get('allowed_values') for s in d['schemas'] for f in s['fields'] if f['type']=='enum'))
bad=[record('acceptance',status='PASS',execution_state='prepared',acceptance_layer='scientific')]
check('prepared_not_scientific_pass',not v.check_tables(d,{'acceptance':bad},cross_references=False)['metadata_contract_pass'])
bad=[record('method_readiness',engineering_state='static_review',numeric_state='pass',scientific_state='adopt')]
check('static_review_not_backend_acceptance',not v.check_tables(d,{'method_readiness':bad},cross_references=False)['metadata_contract_pass'])
bad=[record('trajectory_review',mode='population_dynamic',decision='ready_for_server',independent_unit='cell',dependence_policy='none')]
check('cell_not_population_dynamic_unit',not v.check_tables(d,{'trajectory_review':bad},cross_references=False)['metadata_contract_pass'])

project=json.loads((ROOT/'templates/project_template.json').read_text(encoding='utf8'))
check('empty_project_stays_blocked',not v.check_project(project,req)['planning_metadata_complete'])
def prepared_task(kind):return {f:'DEMO' for f in set(req['per_task_common']+req['tasks'][kind])}|{'request_id':'DEMO_REQUEST','module_id':'DEMO_MODULE','task_type':kind,'parameters':{'seed':42},'expected_outputs':['DEMO_TABLE'],'sensitivity_plan':{'purpose':'DEMO only; not a study plan'},'server_method_acceptance':'PENDING_REFERENCE_ONLY'}
base={f:'DEMO' for f in req['always']}|{'workflow_version':req['version'],'execution_authorized':False,'overwrite_outputs':False,'unknown_submission_policy':'inspect_existing_receipts_do_not_retry','selected_modules':['DEMO_MODULE']}
p=base|{'task_requests':[prepared_task('atlas')]}
check('atlas_does_not_require_count_de_model',v.check_project(p,req)['planning_metadata_complete'])
p=base|{'task_requests':[prepared_task('bulk_de')|{'matrix_kind':'raw_counts'}]}
check('count_de_planning_fields_present',v.check_project(p,req)['planning_metadata_complete'])
p['task_requests'][0].pop('count_layer')
check('count_de_missing_layer_rejected',not v.check_project(p,req)['planning_metadata_complete'])
p=base|{'task_requests':[prepared_task('trajectory_population')]};p['task_requests'][0].pop('dependence_policy')
check('population_dynamic_missing_dependence_rejected',not v.check_project(p,req)['planning_metadata_complete'])
p=base|{'task_requests':[prepared_task('atlas')],'execution_authorized':True}
check('template_cannot_authorize_execution',not v.check_project(p,req)['planning_metadata_complete'])
check('all_checker_outputs_deny_formal_execution',all(not r['formal_analysis_allowed'] for r in [v.check_tables(d,tables),v.check_project(project,req)]))
check('malformed_identity_row_returns_issue',not v.check_tables(d,{'identity':[{'identity_id':'PARTIAL'}],'identity_link':links})['metadata_contract_pass'])
check('non_scalar_metadata_returns_issue',not v.check_tables(d,{'identity':[record('identity',identity_id=['BAD'])]})['metadata_contract_pass'])
check('non_list_table_returns_issue',not v.check_tables(d,{'identity':{}})['metadata_contract_pass'])
check('non_object_tables_return_issue',not v.check_tables(d,[])['metadata_contract_pass'])
p=base|{'task_requests':[prepared_task('trajectory_population')|{'dependence_policy':[]}]}
check('malformed_dependence_returns_issue',not v.check_project(p,req)['planning_metadata_complete'])
report={'state':'METADATA_SCENARIOS_PASS','test_cases':tests,'passed':sum(x['passed'] for x in tests),'count':len(tests),'scientific_analysis_executed':False,'server_backend_validated':False,'note':'Fictional metadata only. Planning completeness is not receipt authenticity or scientific adoption.'}
(ROOT/'qa').mkdir(exist_ok=True)
(ROOT/'qa/metadata_scenarios.private.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='test_cases'}))
