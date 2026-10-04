"""Private scoped code, numerical and medical contracts; synthetic acceptance/refusal checks."""
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import academic_common as common
import code_review_ext as code
import code_execution_ext as execution
import clinical_research_ext as clinical
import workflow_ext as workflow
import code_runner

ROOT=Path(__file__).resolve().parents[1]
CONTEXT=dict(species='synthetic',model='fixture',assay='fixture',biological_unit='patient',contrast='fixture',limitations=['Synthetic check'])


class CodeClinicalChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.patches=[patch.object(m,'HERE',self.root) for m in (common,execution,clinical,workflow)]
        for p in self.patches:p.start()
        for name in ('code_runner.py','workflow_stage.py','remote_runner.py','clinical_backend.R'):
            (self.root/name).write_bytes((ROOT/'bridge'/name).read_bytes())
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def save(self,name,data):
        p=self.root/name;p.write_text(json.dumps(data) if not isinstance(data,str) else data,encoding='utf8');return str(p)
    def table(self,name,header,data):
        p=self.root/name
        with p.open('w',encoding='utf8',newline='') as stream:
            w=csv.writer(stream);w.writerow(header);w.writerows(data)
        return str(p)
    def sha(self,path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def csv_fixture(self):return self.table('data.csv',['id','value','unit'],[['a',1,'mg'],['b',2,'mg']])
    def contract(self):return {'columns':{'id':{'type':'string'},'value':{'type':'number','minimum':0},'unit':{'type':'string'}},'primary_key':['id'],'units':{'value':'mg'},'observed_units':{'value':'mg'}}
    def stage(self,identity,kind,deps=None):return {'id':identity,'kind':kind,'depends_on':deps or [],'argv':['python3','fixture.py'],'inputs':['fixture.py'],'outputs':[identity+'.json'],'resources':{'cpus':1,'memory_mb':128,'wall_minutes':1},**({'qc_gate_output':identity+'.json'} if kind=='qc' else {})}
    def study(self):return dict(question='Fixture question',design='observational',outcome_type='survival',independent_unit='patient',estimand='fixture',groups=2,repeated=False,clustered=False,primary_endpoints=['event'],missing_data='reject',covariates=['age'])
    def test_map_does_not_import_source(self):
        self.save('source.py','raise RuntimeError("do not import")\nimport helper\ndef score(x):\n return x+1\n')
        self.save('helper.py','def identity(x): return x\n')
        r=code.map_code_project(str(self.root),['source.py','helper.py'])
        self.assertEqual(r['files'][0]['definitions'][0]['name'],'score');self.assertEqual(len(r['selected_import_edges']),1)
    def test_scope_traversal_refused(self):
        with self.assertRaises(ValueError):code.map_code_project(str(self.root),['../outside.py'])
    def test_secret_file_refused(self):
        self.save('.env','fixture')
        with self.assertRaises(ValueError):code.map_code_project(str(self.root),['.env'])
    def test_source_security_locations(self):
        self.save('source.py','import subprocess\nsubprocess.run(cmd,shell=True)\nx=df.dropna()\n')
        r=code.audit_scientific_code(str(self.root),['source.py']);self.assertTrue(any(x['line']==2 and x['kind']=='shell_string_or_eval' for x in r['findings']))
    def test_notebook_disorder_and_saved_failure(self):
        p=self.save('n.ipynb',{'nbformat':4,'cells':[{'cell_type':'code','source':['x=1'],'execution_count':3,'outputs':[]},{'cell_type':'code','source':['print(y)'],'execution_count':2,'outputs':[{'output_type':'error'}]}]})
        issues=code.audit_notebook(p)['issues'];self.assertTrue(any(x['kind']=='nonmonotone_execution' for x in issues));self.assertTrue(any(x['kind']=='name_use_candidate' for x in issues))
    def test_data_contract_pass_and_units(self):
        p=self.csv_fixture();spec=self.contract();self.assertTrue(code.audit_data_contract(p,spec)['contract_pass'])
        spec['observed_units']['value']='g';self.assertFalse(code.audit_data_contract(p,spec)['contract_pass'])
    def test_duplicate_primary_unit_blocks(self):
        p=self.table('bad.csv',['id','value','unit'],[['a',1,'mg'],['a',2,'mg']]);self.assertFalse(code.audit_data_contract(p,self.contract())['contract_pass'])
    def test_many_to_many_expansion_detected(self):
        a=self.table('a.csv',['id'],[['a'],['a']]);b=self.table('b.csv',['id'],[['a'],['a'],['a']])
        r=code.audit_table_join(a,b,['id']);self.assertEqual(r['expected_output_rows'],6);self.assertFalse(r['contract_pass'])
    def test_join_missing_keys_block(self):
        a=self.table('a.csv',['id'],[['']]);b=self.table('b.csv',['id'],[['']]);self.assertIn('missing_join_key',code.audit_table_join(a,b,['id'])['issues'])
    def test_exchange_category_change(self):
        a=self.table('a.csv',['id','v'],[['a','01']]);b=self.table('b.csv',['id','v'],[['a','1']]);self.assertFalse(code.compare_data_exchange(a,b,['id'],['v'])['equivalent'])
        self.assertTrue(code.compare_data_exchange(a,b,['id'],['v'],numeric_columns=['v'])['equivalent'])
    def test_numeric_nonfinite_and_interval(self):
        p=self.table('num.csv',['lo','v','hi'],[[0,2,1],[0,'NaN',1]])
        r=code.audit_numeric_results(p,{'columns':{'v':{}},'intervals':[['lo','v','hi']]});self.assertFalse(r['numeric_pass'])
    def test_scientific_diff_tolerances(self):
        a=self.table('a.csv',['id','v'],[['a',1]]);b=self.table('b.csv',['id','v'],[['a',1.01]])
        self.assertTrue(code.compare_scientific_results(a,b,['id'],{'v':{'atol':.02}})['within_tolerance']);self.assertFalse(code.compare_scientific_results(a,b,['id'],{'v':{'atol':.001}})['within_tolerance'])
    def test_qc_input_design_reference_binding(self):
        p=self.csv_fixture();receipt=self.save('qc.json',{'contract_pass':True});inputs=[{'id':'data','path':p}]
        r=code.bind_analysis_qc(inputs,{'contrast':'a-b'},{'annotation':'v1'},receipt,{'decision':'pass','checks':['unit QC'],'limitations':['fixture']})
        path=str(Path(r['output_directory'])/'review.json');h=self.sha(path)
        self.assertTrue(code.check_analysis_qc(path,h,inputs,{'contrast':'a-b'},{'annotation':'v1'})['qc_current'])
        self.assertFalse(code.check_analysis_qc(path,h,inputs,{'contrast':'b-a'},{'annotation':'v1'})['qc_current'])
        Path(p).write_text('id,value\na,3\n');self.assertFalse(code.check_analysis_qc(path,h,inputs,{'contrast':'a-b'},{'annotation':'v1'})['qc_current'])
    def test_qc_false_receipt_refused(self):
        p=self.csv_fixture();receipt=self.save('qc.json',{'contract_pass':False})
        with self.assertRaises(ValueError):code.bind_analysis_qc([{'id':'d','path':p}],{'a':1},{'ref':1},receipt,{'decision':'pass','checks':['x'],'limitations':['x']})
    def test_patch_preview_preserves_original(self):
        p=self.save('f.py','def f(): return 1\n');h=self.sha(p)
        r=code.prepare_code_revision(str(self.root),[{'path':'f.py','new_source':'def f(): return 2\n'}],'Fixture correction',[[sys.executable,'f.py']]);self.assertEqual(self.sha(p),h);self.assertIn('-def f()',Path(r['output_directory'],'changes.patch').read_text())
    def test_generated_scientific_suite_actually_runs(self):
        self.save('fixture.py','def total(values): return sum(values)\n')
        c={'module':'fixture','function':'total','arguments':{'values':[1,2]},'kind':'permutation_invariance','argument':'values','rationale':'Order should not change sum'}
        r=code.prepare_scientific_test_suite([c],[{'path':'fixture.py','sha256':self.sha(self.root/'fixture.py')}]);test=Path(r['output_directory'])/'test_scientific.py'
        env={**os.environ,'PYTHONPATH':str(self.root)};p=subprocess.run([sys.executable,str(test)],env=env,cwd=self.root,capture_output=True,timeout=15);self.assertEqual(p.returncode,0)
    def test_method_missing_parameter_is_gap(self):
        r=code.prepare_method_reproduction({'citation':'public fixture','version':'1','objective':'sum'},[{'id':'a','source_location':'line:1','source_sha256':'a'*64,'method_element':'parameter','implementation_location':'pending','status':'missing'}],{'dataset_source':'synthetic','acceptance_metrics':['value']});self.assertEqual(r['unresolved'],['a'])
    def test_plan_changes_and_unassessed(self):
        plan={k:'fixture' for k in ['estimand','independent_unit','endpoints','contrast','covariates','missingness','exclusions','multiplicity']}
        r=code.audit_plan_implementation(plan,[{'element':'contrast','location':'line:1','source_sha256':'a'*64,'observed':'reverse'}]);self.assertEqual(r['issues'][0]['kind'],'plan_deviation');self.assertEqual(len(r['unassessed']),7)
    def test_api_version_mismatch(self):
        r=code.prepare_api_migration({'fixture':'1'},[{'package':'fixture','tested_version':'2','official_source':'https://example.invalid/docs','location':'line:1','old_api':'a','replacement':'b'}]);self.assertFalse(r['changes'][0]['version_match'])
    def test_renv_lock_read_not_source_profile(self):
        self.save('renv.lock',{'R':{'Version':'4'},'Packages':{'fixture':{'Version':'1'}}});r=code.inspect_dependency_locks(str(self.root),['renv.lock']);self.assertEqual(r['locks'][0]['packages']['fixture'],'1')
    def test_environment_missing_dimensions_visible(self):
        r=code.compare_environments({'runtime':'1'},{'runtime':'2'});self.assertTrue(r['revalidation_required']);self.assertIn('system_libraries',r['unassessed'])
    def test_migration_copy_and_changed_source_refusal(self):
        p=self.save('config.json',{'old':1});r=code.prepare_configuration_migration(p,[{'operation':'rename','from':'old','to':'new'}],{'new':'integer'});plan=str(Path(r['output_directory'])/'review.json')
        out=str(self.root/'new.json');code.apply_configuration_migration(plan,self.sha(plan),out,True);self.assertEqual(json.loads(Path(out).read_text()),{'new':1});self.assertEqual(json.loads(Path(p).read_text()),{'old':1})
        Path(p).write_text('{}')
        with self.assertRaises(ValueError):code.apply_configuration_migration(plan,self.sha(plan),str(self.root/'other.json'),True)
    def test_components_unverified_not_safe(self):
        r=code.audit_dependency_components([{'name':'fixture','version':'1'}]);self.assertIn('vulnerability_status_unverified',r['components'][0]['issues'])
    def test_release_scan_does_not_echo_secret(self):
        secret='sk-'+'A'*30;self.save('source.py','key='+repr(secret));r=code.audit_release_scope(str(self.root),['source.py']);self.assertFalse(r['pattern_pass']);self.assertNotIn(secret,json.dumps(r))
    def test_server_bundle_not_submission(self):
        r=execution.prepare_code_execution('python_syntax',{'files':['f.py']},'/analysis','compute-fixture','out',CONTEXT,[{'path':'f.py','sha256':'a'*64}]);self.assertEqual(r['state'],'prepared_not_submitted')
        task=json.loads(Path(r['task_file']).read_text());self.assertTrue({'code_runner.py','code_config.json'}<={x['path'] for x in task['inputs']})
    def test_server_source_execution_needs_review(self):
        with self.assertRaises(ValueError):execution.prepare_code_execution('python_run',{'files':['f.py']},'/analysis','compute-fixture','out',CONTEXT,[{'path':'f.py','sha256':'a'*64}])
    def test_runner_success_and_syntax_refusal(self):
        self.save('good.py','x=1\n');self.save('bad.py','if :\n')
        for name,expected in [('good.py',0),('bad.py',1)]:
            p=self.save('run.json',{'mode':'python_syntax','files':[name],'output_directory':name+'.out'})
            result=subprocess.run([sys.executable,str(ROOT/'bridge'/'code_runner.py'),p],cwd=self.root,capture_output=True,timeout=15);self.assertEqual(result.returncode,expected)
            r=json.loads((self.root/(name+'.out')/'execution.json').read_text());self.assertEqual(r['exit_code'],expected)
    def test_real_profile_and_private_json_summary(self):
        self.save('profiled.py','sum(range(1000))\n');p=self.save('run.json',{'mode':'python_profile','files':['profiled.py'],'output_directory':'prof','reviewed_code':True,'timeout_seconds':15})
        r=subprocess.run([sys.executable,str(ROOT/'bridge'/'code_runner.py'),p],cwd=self.root,capture_output=True,timeout=20);self.assertEqual(r.returncode,0)
        self.assertTrue(execution.summarize_performance(str(self.root/'prof'/'profile.json'))['top_functions'])
    def test_execution_wrong_configuration_refused(self):
        p=self.save('exec.json',{'schema':1,'state':'succeeded','exit_code':0,'finished_at':'fixture','configuration_sha256':'a'*64,'source_hashes':[{'sha256':'b'*64}]});self.assertFalse(execution.inspect_code_execution(p,'c'*64)['completion_record_pass'])
    def test_resource_extrapolation_explicit(self):
        pilots=[{'units':n,'wall_seconds':n,'peak_memory_mb':10,'output_mb':n,'receipt_sha256':'a'*64} for n in [10,20]];r=execution.estimate_compute_resources(pilots,100);self.assertTrue(r['extrapolation']);self.assertEqual(r['estimates']['seconds']['suggested_budget'],150)
    def test_parallel_overallocation_seed_and_output(self):
        r=execution.audit_parallel_execution({'allocated_cpus':2,'workers':2,'threads_per_worker':2,'seed_policy':'per_task'},[{'id':'a','seed':1,'outputs':['x']},{'id':'b','seed':1,'outputs':['x']}]);self.assertEqual(set(r['issues']),{'cpu_oversubscription','shared_output_collision','reused_task_seed'})
    def test_unknown_resume_blocks(self):
        identity={k:'fixture' for k in ['inputs','code','parameters','environment']};p=self.save('check.txt','fixture')
        r=execution.audit_resume_compatibility(identity,identity,{'state':'unknown','observed_at':'fixture','receipt_sha256':'a'*64},[{'path':p,'sha256':self.sha(p)}]);self.assertFalse(r['compatible_for_reviewed_resume'])
    def test_workflow_requires_qc_and_disjoint_outputs(self):
        with self.assertRaises(ValueError):execution.prepare_code_workflow([self.stage('analysis','analysis')],approved_code=True)
        a=self.stage('qc','qc');b=self.stage('analysis','analysis',['qc']);b['outputs']=a['outputs']
        with self.assertRaises(ValueError):execution.prepare_code_workflow([a,b],approved_code=True)
    def test_workflow_generation_and_missing_input(self):
        r=execution.prepare_code_workflow([self.stage('qc','qc'),self.stage('analysis','analysis',['qc'])],approved_code=True);self.assertTrue(Path(r['output_directory'],'Snakefile').is_file())
        result=execution.preview_code_workflow(str(Path(r['output_directory'])/'workflow.json'),[]);self.assertEqual(result['missing_external_inputs'],['fixture.py'])
    def test_guideline_located_region_version(self):
        p=self.save('guide.txt','Recommendation for fixture population.\n')
        s={'id':'g','path':p,'publisher':'fixture','version':'1','published_on':'2020-01-01','retrieved_on':'2020-01-02','region':'A','population':'adult','official_source':'https://example.invalid'}
        r=clinical.audit_medical_guidelines([s],[{'source_id':'g','location':'line:1','excerpt':'Recommendation','topic':'fixture','declared_action':'review'}],{'population':'adult','region':'B','question':'fixture'},'2020-01-03');self.assertIn('region_applicability_review',r['recommendations'][0]['issues'])
    def test_guideline_wrong_excerpt_refused(self):
        p=self.save('guide.txt','fixture');s=dict(id='g',path=p,publisher='fixture',version='1',published_on='2020-01-01',retrieved_on='2020-01-02',region='A',population='adult',official_source='https://example.invalid')
        with self.assertRaises(ValueError):clinical.audit_medical_guidelines([s],[{'source_id':'g','location':'line:1','excerpt':'absent'}],{'population':'adult','region':'A','question':'fixture'},'2020-01-03')
    def test_drug_query_requires_specific_public_approval(self):
        with self.assertRaises(ValueError):clinical.query_drug_reference('acetaminophen')
    def test_clinical_time_units_repetition(self):
        p=self.table('clinical.csv',['id','visit','value','unit','start','event'],[['p',1,10,'g','2020-01-02','2020-01-01'],['p',2,11,'mg','2020-01-02','2020-01-03']])
        spec={'unit_column':'id','visit_column':'visit','independent_unit':'patient','design':'cohort','measurements':[{'value_column':'value','unit_column':'unit','unit':'mg','reference_source':'fixture'}],'time_order':[['start','event']]}
        r=clinical.audit_clinical_dataset(p,spec);self.assertFalse(r['qc_pass']);self.assertEqual(r['independent_unit_count'],1);self.assertEqual(r['repeated_unit_count'],1)
    def test_clinical_mapping_unresolved(self):
        r=clinical.audit_clinical_mapping([{'source_field':'code','source_value':'fixture','target_table':'condition','target_field':'concept','concept_id':0,'domain':'condition','mapping_source':'fixture'}],'fixture');self.assertIn('unresolved_concept',r['mappings'][0]['issues'])
    def test_prediction_auc_calibration_net_benefit_and_leakage(self):
        p=self.table('pred.csv',['id','y','p'],[['a',0,.1],['b',0,.2],['c',1,.8],['d',1,.9]])
        spec={'unit_column':'id','outcome_column':'y','probability_column':'p','validation_type':'held_out','thresholds':[.5],'training_unit_tokens':[],'preprocessing_fitted_on_training':True,'tuning_separate':True}
        r=clinical.audit_clinical_prediction(p,spec);self.assertEqual(r['overall']['auc'],1);self.assertEqual(r['decision_curve'][0]['model'],.5)
        spec['training_unit_tokens']=['a'];self.assertFalse(clinical.audit_clinical_prediction(p,spec)['validation_gate_pass'])
    def test_reporting_needs_actual_located_text(self):
        p=self.save('paper.txt','Patients were held out by center.');check={'name':'caller supplied','version':'1','official_source':'https://example.invalid','items':[{'id':'a'},{'id':'b'}]}
        r=clinical.audit_medical_reporting(p,check,[{'item_id':'a','decision':'reported','reviewer':'reviewer-a','location':'line:1','excerpt':'held out by center'}]);self.assertEqual(r['unassessed'],['b'])
    def test_effect_extraction_real_second_review_and_conflict(self):
        p=self.save('paper.txt','Effect 0.2, variance 0.1.');r={'source_id':'s','location':'line:1','excerpt':'Effect 0.2','study_id':'s','cohort_id':'c','outcome':'o','timepoint':'t','scale':'difference','effect':.2,'variance':.1,'reviewer':'one','independent_review':True}
        a=clinical.extract_review_effects([{'id':'s','path':p}],[r]);self.assertEqual(len(a['pending_second_review']),1)
        b=clinical.extract_review_effects([{'id':'s','path':p}],[r,{**r,'reviewer':'two','effect':.3}]);self.assertEqual(b['conflicts'][0]['kind'],'effect_disagreement')
    def test_bias_not_automatically_graded(self):
        p=self.save('paper.txt','Allocation was concealed.');r=clinical.record_bias_assessment({'name':'caller tool','version':'1','official_source':'https://example.invalid','license':'review','design':'trial'},[{'study_id':'s','outcome':'o','domain':'allocation','judgment':'reviewed','reason':'source','reviewer':'one','source_path':p,'location':'line:1','excerpt':'concealed'}]);self.assertEqual(len(r['assessments']),1)
    def test_adverse_event_case_version_dedup(self):
        p=self.table('ae.csv',['case','version','drug','event'],[['a',1,'D','E'],['a',2,'D','E'],['a',2,'D','E'],['b',1,'D','X'],['c',1,'X','E'],['d',1,'X','X']])
        spec=dict(case_column='case',version_column='version',drug_column='drug',event_column='event',target_drug='D',target_event='E',source='synthetic',retrieved_on='2020-01-01',continuity_correction=.5)
        r=clinical.audit_adverse_event_reports(p,spec);self.assertEqual(r['reporting_odds']['ror'],1);self.assertEqual(sum(r['case_counts'].values()),4);self.assertEqual(r['duplicate_latest_pairs'],1)
    def test_imaging_patient_split_blocks(self):
        r={'patient_token':'fixture','series_token':'s','split':'train','modality':'CT','acquisition':{'spacing':1},'label_review':'independent_reviewed'}
        out=clinical.audit_imaging_metadata([r,{**r,'series_token':'t','split':'test'}],{'required_acquisition_fields':['spacing']});self.assertFalse(out['qc_pass'])
    def test_teaching_private_case_requires_approval(self):
        with self.assertRaises(ValueError):clinical.prepare_medical_teaching('fixture',[],[],{'kind':'synthetic','content':{}})
    def test_clinical_backend_requires_statistics_guidance(self):
        config={'data':'d.csv','unit_column':'id','estimand':'fixture','covariates':['age'],'missingness_policy':'reject','design':'cohort','statistical_plan_reviewed':True,'time_column':'time','status_column':'event'}
        with self.assertRaises(ValueError):clinical.prepare_clinical_backend('cox_survival',config,'/analysis','compute-fixture','out',CONTEXT,[{'path':'d.csv','sha256':'a'*64}])
        config['statistics_study']=self.study();r=clinical.prepare_clinical_backend('cox_survival',config,'/analysis','compute-fixture','out',CONTEXT,[{'path':'d.csv','sha256':'a'*64}]);self.assertEqual(r['state'],'prepared_not_submitted')

    def test_materialized_revision_keeps_original_and_refuses_stale_source(self):
        p=self.save('f.py','value=1\n');r=code.prepare_code_revision(str(self.root),[{'path':'f.py','new_source':'value=2\n'}],'fixture',[[sys.executable,'f.py']]);plan=str(Path(r['output_directory'])/'review.json')
        out=self.root/'staged';code.materialize_code_revision(plan,self.sha(plan),str(out),True);self.assertEqual((out/'f.py').read_text(),'value=2');self.assertEqual(Path(p).read_text(),'value=1\n')
        Path(p).write_text('value=3\n')
        with self.assertRaises(ValueError):code.materialize_code_revision(plan,self.sha(plan),str(self.root/'other'),True)
    def test_task_array_concurrency_and_duplicate_refusal(self):
        (self.root/'array_runner.py').write_bytes((ROOT/'bridge'/'array_runner.py').read_bytes())
        resources={'cpus':1,'memory_mb':128,'wall_minutes':1};tasks=[{'task_file':'a/task.json','sha256':'a'*64},{'task_file':'b/task.json','sha256':'b'*64}]
        r=execution.prepare_code_task_array(tasks,1,resources);self.assertIn('--array=0-1%1',Path(r['output_directory'],'array.slurm').read_text())
        with self.assertRaises(ValueError):execution.prepare_code_task_array([tasks[0],tasks[0]],1,resources)
    def test_typed_adapter_client_rejects_extra_parameters(self):
        contract=dict(schema=1,id='fixture',version='1',license='MIT',source='https://example.invalid',placement='server',inputs=[{'name':'in','format':'csv','required':True}],outputs=[{'name':'out','format':'json','required':True}],resources={'cpus':1,'memory_mb':128,'walltime_minutes':1},invocation=['python3','fixed.py'],parser='fixed',runtime_state='unverified',parameters={'count':{'type':'integer','required':True}})
        r=execution.prepare_adapter_development(contract);client=Path(r['output_directory'])/'client.py'
        import importlib.util
        spec=importlib.util.spec_from_file_location('fixture_client',client);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.validate({'count':2}),{'count':2})
        with self.assertRaises(ValueError):module.validate({'count':True})
        with self.assertRaises(ValueError):module.validate({'count':2,'extra':1})


if __name__=='__main__':unittest.main()
