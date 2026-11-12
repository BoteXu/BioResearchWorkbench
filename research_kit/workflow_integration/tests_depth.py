"""Offline tests of safety, result logic and contract completeness; never fit/analyze raw data."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
import acceptance as ac
import workbench
from cross_domain import audit

def write(p,v):
    Path(p).write_text(json.dumps(v,ensure_ascii=False,allow_nan=False),encoding='utf8')
def import_runtime():
    spec=importlib.util.spec_from_file_location('private_server_runtime',HERE/'server/runtime.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class DepthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='private_depth_');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def sample_request(self):
        profiles=ac.load(HERE/'profiles.json');p={k:'synthetic declared value' for k in profiles['backends']['ml']['required_parameters']}
        p.update(features=['feature1'],train_units=['U1','U2'],test_units=['U3'],calibration_units=[],models={'baseline':{}},task='classification',unit_key='donor',sample_key='sample',outcome='outcome',outer_folds=2,inner_folds=2,select_k='all',seed=1,threads=1,max_candidates=2)
        req=dict(run_id='SYNTHETIC_NO_SCIENCE',backend='ml',parameters=p,inputs=[dict(id='table',path='input.tsv',sha256='a'*64)],
           public_upload=False,server_execution_authorized=False,resource_budget={'cpus':1,'gpus':0},expected_host='synthetic-compute',node_role='compute',
           upstream_qc={'state':'requires real selected server QC'},statistical_plan=dict(estimand='synthetic',independent_unit='donor',missingness='no hidden fill',multiplicity='prespecified',sensitivity='prespecified'),
           acceptance_rules=[dict(id='diagnostic',role='feature_contract',field='test_used_for_early_stopping',operator='eq',bound=False,definition='test policy',unit='boolean',threshold_basis='locked test')])
        return req
    def fixture(self):
        req=dict(backend='molecular_qc',plan_sha256='a'*64,expected_host='synthetic-compute',node_role='compute',required_roles=['chemical_qc','diagnostics'],
          parameters={},inputs=[],acceptance_rules=[dict(id='no_failed',role='diagnostics',field='failed_records',operator='eq',bound=0,definition='failed input states',unit='records',threshold_basis='selected all-pass input policy')])
        req['source_sha256']={p.name:ac.sha(p) for p in (HERE/'server').glob('*') if p.suffix in {'.py','.R','.json'}}
        write(self.root/'request.json',req)
        (self.root/'chemical_qc.tsv').write_text('source_record\tstate_id\tstatus\n0\tSTATE1\tparsed\n',encoding='utf8')
        write(self.root/'diagnostics.json',{'failed_records':0});write(self.root/'runtime_warnings.json',[])
        outputs=[dict(path=name,role=role,sha256=ac.sha(self.root/name),bytes=(self.root/name).stat().st_size) for name,role in [('chemical_qc.tsv','chemical_qc'),('diagnostics.json','diagnostics'),('runtime_warnings.json','runtime_warnings')]]
        receipt=dict(state='COMPLETED',exit_code=0,host=req['expected_host'],plan_sha256=req['plan_sha256'],request_sha256=ac.sha(self.root/'request.json'),outputs=outputs,
            source_sha256={p.name:ac.sha(p) for p in (HERE/'server').glob('*') if p.suffix in {'.py','.R','.json'}})
        write(self.root/'receipt.json',receipt)
        return req,receipt,[r['path'] for r in outputs]
    def review(self,files):return ac.inspect_result(self.root/'request.json',self.root/'receipt.json',self.root,HERE/'server',files)
    def test_python_syntax_all_backends(self):
        for p in HERE.rglob('*.py'):ast.parse(p.read_text(encoding='utf8'),filename=str(p))
    def test_no_scientific_imports_in_local_review(self):
        for p in (HERE/'workbench.py',HERE/'acceptance.py',HERE/'cross_domain.py'):
            tree=ast.parse(p.read_text(encoding='utf8'));names={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}
            self.assertFalse(names&{'numpy','pandas','scipy','sklearn','scanpy','torch','rdkit'})
    def test_profile_completeness(self):
        p=ac.load(HERE/'profiles.json');self.assertEqual(len(p['omics_workflows']),28);self.assertEqual(len(p['analysis_branches']),81);self.assertEqual(len(p['cadd_modules']),34);self.assertEqual(len(p['transcriptomics_sop_modules']),65)
        self.assertEqual(sum(len(v) for v in p['model_families'].values()),27)
        self.assertTrue(all(b['result_roles'] and b['required_parameters'] for b in p['backends'].values()))
    def test_local_science_guard_before_import(self):
        rt=import_runtime();write(self.root/'request.json',self.sample_request())
        with self.assertRaises(RuntimeError):rt.run(self.root/'request.json',self.root/'must_not_exist')
        self.assertFalse((self.root/'must_not_exist').exists())
    def test_plan_contains_real_source_hashes_and_disabled_dispatch(self):
        write(self.root/'request.json',self.sample_request());result=workbench.plan(self.root/'request.json',self.root/'bundle')
        self.assertEqual(result['state'],'prepared_not_submitted');p=ac.load(self.root/'bundle/server_request.private.json');self.assertFalse(p['server_execution_authorized'])
        self.assertEqual(p['source_sha256']['ml.py'],ac.sha(HERE/'server/ml.py'))
    def test_string_statistics_is_not_a_plan(self):
        r=self.sample_request();r['statistical_plan']='passed';write(self.root/'request.json',r)
        with self.assertRaises(ValueError):workbench.plan(self.root/'request.json',self.root/'bundle')
    def test_no_acceptance_criteria_rejected(self):
        r=self.sample_request();r['acceptance_rules']=[];write(self.root/'request.json',r)
        with self.assertRaises(ValueError):workbench.plan(self.root/'request.json',self.root/'bundle')
    def test_r_specific_required_parameters(self):
        r=self.sample_request();r['backend']='r_omics';r['parameters']={'rscript':'/synthetic/Rscript','method':'DESeq2','seed':1};write(self.root/'request.json',r)
        with self.assertRaises(ValueError):workbench.plan(self.root/'request.json',self.root/'bundle')
    def test_actual_selected_outputs_can_pass_result_checks_only(self):
        _,_,files=self.fixture();r=self.review(files);self.assertEqual(r['state'],'RETURN_CHECKS_PASS');self.assertFalse(r['server_live_process_observed'])
    def test_status_only_without_diagnostics_is_hold(self):
        req,rec,files=self.fixture();rec['outputs']=[];write(self.root/'receipt.json',rec)
        self.assertEqual(self.review([])['state'],'HOLD')
    def test_changed_result_refused(self):
        _,_,files=self.fixture();write(self.root/'diagnostics.json',{'failed_records':1})
        self.assertIn('returned_file_changed:diagnostics.json',self.review(files)['issues'])
    def test_failed_actual_diagnostic_refused(self):
        _,rec,files=self.fixture();write(self.root/'diagnostics.json',{'failed_records':2})
        for row in rec['outputs']:
            if row['path']=='diagnostics.json':row.update(sha256=ac.sha(self.root/row['path']),bytes=(self.root/row['path']).stat().st_size)
        write(self.root/'receipt.json',rec);self.assertIn('observed_diagnostic_failed:no_failed',self.review(files)['issues'])
    def test_caller_boolean_not_numeric_qc(self):
        with self.assertRaises(ValueError):ac.number(True)
    def test_nan_is_not_a_result(self):
        (self.root/'nan.json').write_text('{"value":NaN}',encoding='utf8')
        with self.assertRaises(ValueError):ac.load(self.root/'nan.json')
    def test_source_drift_expires_acceptance(self):
        _,rec,files=self.fixture();rec['source_sha256']['ml.py']='b'*64;write(self.root/'receipt.json',rec)
        self.assertIn('server_source_changed:ml.py',self.review(files)['issues'])
    def test_missing_source_manifest_is_hold(self):
        _,rec,files=self.fixture();rec['source_sha256']={};write(self.root/'receipt.json',rec)
        self.assertIn('incomplete_backend_source_binding',self.review(files)['issues'])
    def test_unobserved_qc_field_is_hold(self):
        req,rec,files=self.fixture();req['acceptance_rules'][0]['field']='nonexistent';write(self.root/'request.json',req);rec['request_sha256']=ac.sha(self.root/'request.json');write(self.root/'receipt.json',rec)
        self.assertIn('required_observation_missing:no_failed',self.review(files)['issues'])
    def test_convergence_warning_is_hold(self):
        _,rec,files=self.fixture();write(self.root/'runtime_warnings.json',[{'category':'ConvergenceWarning','message':'synthetic'}])
        for row in rec['outputs']:
            if row['path']=='runtime_warnings.json':row.update(sha256=ac.sha(self.root/row['path']),bytes=(self.root/row['path']).stat().st_size)
        write(self.root/'receipt.json',rec);self.assertIn('model_convergence_or_fit_warning',self.review(files)['issues'])
    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):ac.selected(self.root,'../secret')
    def test_failed_execution_is_hold(self):
        _,rec,files=self.fixture();rec.update(state='FAILED',exit_code=1);write(self.root/'receipt.json',rec)
        self.assertIn('server_run_not_completed',self.review(files)['issues'])
    def test_changed_request_is_hold(self):
        req,_,files=self.fixture();req['plan_sha256']='b'*64;write(self.root/'request.json',req)
        self.assertIn('request_or_plan_binding_changed',self.review(files)['issues'])
    def test_cross_domain_requires_isoform(self):
        entities='entity_id\tentity_type\tspecies\tnamespace\tversion\tsource_id\nG\tgene\tsynthetic\tgene\t1\tsrc\nT\ttranscript\tsynthetic\ttranscript\t1\tsrc\nP\tprotein\tsynthetic\tprotein\t1\tsrc\nS\tstructure\tsynthetic\tstructure\t1\tsrc\n'
        mapping='from_id\tto_id\trelation\tmapping_status\tevidence_file_id\nG\tT\tencodes\tunique\tsource\nT\tP\tencodes\tunique\tsource\nP\tS\tmaps\tunique\tsource\n'
        candidates='candidate_id\tgene_id\ttranscript_id\tprotein_id\tstructure_id\ttissue\tcell_context\tcontrast\teffect_scale\tsource_cohort_id\tevidence_file_id\tmeasurement_state\teffect_direction\nC\tG\tT\tP\tS\tsynthetic\tsynthetic\tB-A\tlog2\tcohort1\tsource\tobserved\tup\n'
        for name,text in [('entities',entities),('mapping',mapping),('candidates',candidates),('source','Synthetic located evidence only')]:(self.root/(name+'.tsv')).write_text(text,encoding='utf8')
        request={'files':[{'id':n,'path':n+'.tsv','bytes':(self.root/(n+'.tsv')).stat().st_size,'sha256':ac.sha(self.root/(n+'.tsv'))} for n in ('entities','mapping','candidates','source')],
             'entity_file_id':'entities','mapping_file_id':'mapping','candidate_file_id':'candidates'}
        r=audit(self.root,request);self.assertEqual(r['handoffs'][0]['state'],'HOLD');self.assertFalse(r['handoffs'][0]['binding_activity_established'])
    def af3_input(self):
        return dict(name='SYNTHETIC_AF3_INPUT',dialect='alphafold3',version=3,modelSeeds=[1,2],
          sequences=[{'protein':{'id':'A','sequence':'ACDE','unpairedMsa':'','pairedMsa':'','templates':[]}}])
    def test_sequence_lookup_needs_public_identifier_authorization(self):
        from sequence_af3 import sequence_plan
        with self.assertRaises(ValueError):sequence_plan('uniprot','P12345','protein')
    def test_isoform_lookup_is_not_silently_canonicalized(self):
        from sequence_af3 import sequence_plan
        p=sequence_plan('uniprot','P12345-2','protein',True)
        self.assertIn('P12345-2.fasta',p['parameters']['endpoint'])
    def test_ensembl_version_not_silently_dropped(self):
        from sequence_af3 import sequence_plan
        with self.assertRaises(ValueError):sequence_plan('ensembl','ENST00000000001.2','cdna',True)
    def test_af3_explicit_empty_msa_is_valid_input_only(self):
        from sequence_af3 import audit_af3_input
        p=audit_af3_input(self.af3_input());self.assertEqual(p['chain_ids'],['A']);self.assertFalse(p['inference_executed'])
    def test_af3_duplicate_chains_rejected(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();p['sequences']*=2
        with self.assertRaises(ValueError):audit_af3_input(p)
    def test_af3_missing_msa_is_not_assumed_empty(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();del p['sequences'][0]['protein']['templates']
        with self.assertRaises(ValueError):audit_af3_input(p)
    def test_af3_ambiguous_sequence_rejected(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();p['sequences'][0]['protein']['sequence']='ACDX'
        with self.assertRaises(ValueError):audit_af3_input(p)
    def test_af3_path_fields_rejected(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();p['userCCDPath']='../private.cif'
        with self.assertRaises(ValueError):audit_af3_input(p)
    def test_af3_chain_sequence_provenance_required(self):
        from server.af3_input import audit_af3_input,audit_chain_provenance
        with self.assertRaises(ValueError):audit_chain_provenance(audit_af3_input(self.af3_input()),{'chains':[]})
    def test_af3_rna_modification_uses_base_axis(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();p['sequences']=[{'rna':{'id':'R','sequence':'ACGU','unpairedMsa':'','modifications':[{'basePosition':2,'modificationType':'5MC'}]}}]
        self.assertEqual(audit_af3_input(p)['chain_ids'],['R'])
    def test_af3_null_msa_not_silently_empty(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();p['sequences'][0]['protein']['unpairedMsa']=None
        with self.assertRaises(ValueError):audit_af3_input(p)
    def test_af3_covalent_position_bound(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();p['bondedAtomPairs']=[[['A',99,'CA'],['A',1,'CA']]]
        with self.assertRaises(ValueError):audit_af3_input(p)
    def test_af3_smiles_not_used_as_covalent_atom_mapping(self):
        from sequence_af3 import audit_af3_input
        p=self.af3_input();p['sequences'].append({'ligand':{'id':'L','smiles':'CCO'}});p['bondedAtomPairs']=[[['A',1,'CA'],['L',1,'C1']]]
        with self.assertRaises(ValueError):audit_af3_input(p)
    def test_a3m_insertion_case_preserves_query_coordinates(self):
        from server.msa_format import parse
        r=parse('>q\nACDE\n>h\nAcCD-\n','ACDE')
        self.assertEqual(r[1]['match'],'ACD-')
    def test_a3m_uppercase_insertion_is_column_error(self):
        from server.msa_format import parse
        with self.assertRaises(ValueError):parse('>q\nACDE\n>h\nACGDE\n','ACDE')
    def test_a3m_query_isoform_change_is_rejected(self):
        from server.msa_format import parse
        with self.assertRaises(ValueError):parse('>q\nACDF\n','ACDE')
    def test_a3m_duplicate_header_is_rejected(self):
        from server.msa_format import parse
        with self.assertRaises(ValueError):parse('>q\nACDE\n>q\nACDE\n','ACDE')
    def test_aligned_fasta_conversion_retains_insertions(self):
        from server.msa_format import from_aligned_fasta,parse
        text=from_aligned_fasta([('q','AC-DE'),('h','ACGDE')],'q','ACDE')
        self.assertEqual(parse(text,'ACDE')[1]['a3m'],'ACgDE')
    def test_protein_asparagine_is_not_ambiguous_nucleotide_N(self):
        from sequence_af3 import audit_fasta
        path=self.root/'protein.fasta';path.write_text('>q\nACDENT\n',encoding='utf8')
        self.assertEqual(audit_fasta(path,'protein',['q'])['records'][0]['ambiguous_symbols'],0)

if __name__=='__main__':
    import io
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DepthTests))
    qa=HERE/'qa';qa.mkdir(exist_ok=True)
    (qa/'depth_tests.private.txt').write_text(stream.getvalue(),encoding='utf8')
    write(qa/'depth_tests.private.json',{'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'passed':r.wasSuccessful(),
       'scientific_engines_executed':False,'scientific_server_validation':'not_run','scope':'bounded result/adversarial/plan/syntax tests only'})
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
