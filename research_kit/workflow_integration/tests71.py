"""Local stdlib-only contract/refusal tests. Fixtures are not scientific simulations."""
from pathlib import Path
import unittest,tempfile,json,copy,ast,sys,csv,importlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).parent
from server.analysis71 import contract,validate_context
from branch71_acceptance import inspect_branch
import acceptance as ac,workbench,workflow71
REG=ac.load(ROOT/'server/branches71.json')

def dump(path,x):Path(path).write_text(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')
def value(rule,offset=0):
    if 'enum' in rule:return rule['enum'][offset%len(rule['enum'])]
    return {'integer':lambda:20+offset,'number':lambda:1.+offset,'array':lambda:[] if not offset else ['FIXTURE_'+str(offset)],
      'boolean':lambda:bool(offset%2),'object':lambda:{'FIXTURE_STATE':['C1']},'string':lambda:'FIXTURE_'+str(offset),
      'contrast':lambda:{'groupTreatment':1.},'bins':lambda:4+offset}[rule['type']]()
def params(key):
    from fixtures71 import params as fixture_params
    return fixture_params(key,REG)

class BranchTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_all71_have_actual_source_branch(self):
        self.assertEqual(len(REG),71)
        for key,s in REG.items():
            file={'r':'analysis71.R','rna':'analysis71.R','native':'native71.py','cell':'cell71.py','cli':'cli71.py'}[s['worker']]
            with self.subTest(key=key):
                text=(ROOT/'server'/file).read_text(encoding='utf8')
                self.assertTrue(("'"+key+"'") in text or ('"'+key+'"') in text)
                self.assertTrue(s['required_roles'] and s['primary_columns_any'] and s['decision_fields'])
    def test_all71_positive_contracts(self):
        for key,s in REG.items():
            with self.subTest(key=key):self.assertEqual(contract(params(key),dict.fromkeys(s['required_inputs']))['implementation'],s['implementation'])
    def test_all71_missing_actual_inputs_refused(self):
        for key in REG:
            with self.subTest(key=key),self.assertRaises(ValueError):contract(params(key),{})
    def test_all71_wrong_method_name_refused(self):
        for key,s in REG.items():
            p=params(key);p['implementation']='candidate_package_is_not_verified'
            with self.subTest(key=key),self.assertRaises(ValueError):contract(p,dict.fromkeys(s['required_inputs']))
    def test_all71_missing_parameter_refused(self):
        for key,s in REG.items():
            p=params(key);del p[s['required_parameters'][0]]
            with self.subTest(key=key),self.assertRaises(ValueError):contract(p,dict.fromkeys(s['required_inputs']))
    def test_all71_must_have_actual_two_sensitivities(self):
        for key,s in REG.items():
            p=params(key);p['sensitivity_variants']=[]
            with self.subTest(key=key),self.assertRaises(ValueError):contract(p,dict.fromkeys(s['required_inputs']))
    def test_all71_sensitivity_cannot_change_test_population(self):
        for key,s in REG.items():
            p=params(key);p['sensitivity_variants'][0]['parameters']={'test_units':['CHANGED']}
            with self.subTest(key=key),self.assertRaises(ValueError):contract(p,dict.fromkeys(s['required_inputs']))
    def test_all71_duplicate_sensitivity_refused(self):
        for key,s in REG.items():
            p=params(key);p['sensitivity_variants'][1]['parameters']=copy.deepcopy(p['sensitivity_variants'][0]['parameters'])
            with self.subTest(key=key),self.assertRaises(ValueError):contract(p,dict.fromkeys(s['required_inputs']))
    def test_all71_runtime_not_misrepresented(self):
        for key,s in REG.items():
            with self.subTest(key=key):self.assertEqual(s['server_acceptance']['state'],'NOT_RUN_SERVER_UNAVAILABLE');self.assertFalse(s['server_acceptance']['interface_test_is_backend_test'])
    def test_all71_local_plan_is_disabled_and_hashes_registry(self):
        for key,s in REG.items():
            p=params(key);project={'backend':'omics71','analysis_id':key,'parameters':p,'run_id':'FIXTURE_NOT_A_SCIENTIFIC_RUN',
              'inputs':[{'id':role,'path':role+'.selected','sha256':'a'*64} for role in s['required_inputs']],
              'public_upload':False,'server_execution_authorized':False,'resource_budget':{'cpus':1,'gpus':0},
              'upstream_qc':{'state':'fixture_not_scientific_evidence'},'statistical_plan':{'estimand':'fixture','independent_unit':'donor','missingness':'specified','multiplicity':'specified','sensitivity':'specified'},
              'expected_host':'FIXTURE_NOT_REAL_HOST','node_role':'compute','acceptance_rules':[{'id':'fixture','role':'analysis_diagnostics','field':'0.metrics.measured','operator':'ge','bound':1,'definition':'metadata fixture only','unit':'fixture','threshold_basis':'not scientific evidence'}]}
            fn=self.root/(key+'.json');dump(fn,project)
            with self.subTest(key=key):
                result=workbench.plan(fn,self.root/key);self.assertEqual(result['state'],'prepared_not_submitted')
                r=ac.load(self.root/key/'server_request.private.json');self.assertFalse(r['server_execution_authorized']);self.assertIn('branches71.json',r['source_sha256'])
    def test_numerical_qc_status_string_refused(self):
        context={k:'fixture' for k in ('species','assembly','annotation_version','assay','scale','feature_unit','independent_unit','estimand','reference_versions','limitations')};context['public_upload']=False;context['qc_evidence']=[{'input_id':'matrix','sha256':'a'*64,'criterion':'fixture','observed':'passed','decision':'ACCEPT','operator':'ge','bound':1,'unit':'unit','source_receipt_sha256':'a'*64}]
        with self.assertRaises(ValueError):validate_context(context)
    def test_failed_numeric_upstream_qc_refused(self):
        context={k:'fixture' for k in ('species','assembly','annotation_version','assay','scale','feature_unit','independent_unit','estimand','reference_versions','limitations')};context.update(public_upload=False,qc_evidence=[dict(input_id='matrix',sha256='a'*64,criterion='fixture',observed=0,decision='ACCEPT',operator='ge',bound=2,unit='units',source_receipt_sha256='a'*64)])
        with self.assertRaises(ValueError):validate_context(context)
    def test_local_science_entry_refuses_before_numpy_import(self):
        from server import analysis71
        with self.assertRaises(RuntimeError):analysis71.analyze({}, {}, self.root,'omics71')
    def test_no_scientific_imports_in_local_helpers(self):
        for name in ('workbench.py','acceptance.py','branch71_acceptance.py','workflow71.py','tests71.py'):
            tree=ast.parse((ROOT/name).read_text(encoding='utf8'));names={a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,(ast.Import,)) for a in n.names}
            self.assertFalse(names&{'numpy','pandas','scipy','statsmodels','sklearn','scanpy','torch'})
    def test_dag_cannot_cycle_or_invent_predecessor(self):
        fn=self.root/'p.json';dump(fn,{'public_upload':False,'server_execution_authorized':False,'inputs':[],'statistical_plan':{'estimand':'fixture','independent_unit':'donor'}})
        plan={'public_upload':False,'automatic_dispatch':False,'nodes':[{'node_id':'A','project_path':'p.json','project_sha256':ac.sha(fn),'depends_on':['B']}]}
        with self.assertRaises(ValueError):workflow71.audit_plan(self.root,plan)
    def test_latest_failure_does_not_inherit_current_success(self):
        r=workflow71.current_acceptance(ROOT,{'state':'FAILED','source_sha256':{},'plan_sha256':'X','versions':{}},{'plan_sha256':'X'})
        self.assertFalse(r['current_environment_verified']);self.assertIn('last_attempt_not_completed',r['expiry_reasons'])
    def test_python_syntax(self):
        for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf8'),filename=str(p))
    def branch_fixture(self,key):
        spec=REG[key];p=params(key);local={};variants=['primary','alt1','alt2'];outputs=[];summary=[]
        for role in spec['required_roles']:
            cols=list(dict.fromkeys((spec['primary_result_rule']['required'] if role==spec['required_roles'][0] else ['fixture_id','fixture_value'])+['fixture_metadata_only']))
            row={c:('0.5' if c.lower() in {'p','pvalue','q','p.value','pval','padj','fdr','adj_pvalue','adj.p.val','posterior_inclusion_probability','cellular_prevalence','cellular_prevalence_std','frame0_fraction','gap_fraction','cluster_assignment_prob','se'} else '0') for c in cols}
            if 'ci_lower' in row:row['ci_lower']='-1'
            if 'ci_upper' in row:row['ci_upper']='1'
            fn=self.root/(key+'_'+role+'.tsv')
            with fn.open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fieldnames=cols,delimiter='\t');w.writeheader();w.writerow(row)
            local[role]=fn
            for v in variants:outputs.append({'path':v+'/'+role+'.tsv'});summary.append({'variant':v,'role':role,'rows':1,'columns':cols})
        request={'parameters':p,'statistical_plan':{'estimand':'fixture','independent_unit':'donor'},'inputs':[{'id':'matrix','sha256':'a'*64}]}
        receipt={'outputs':outputs,'source_sha256':{'fixture.py':'a'*64}}
        files={'analysis_qc':{'context':{'estimand':'fixture','independent_unit':'donor'},'executed_preflight':{'state':'EXECUTED_PREFLIGHT','observations':{'matrix':{'fixture':1}}},'upstream_evidence':[{'input_id':'matrix','sha256':'a'*64}]},
          'analysis_diagnostics':[{'variant':v,'fit_completed':True,'metrics':{'fixture_numeric_value':1}} for v in variants],
          'analysis_sensitivity':summary,'implementation_record':{'analysis_id':key,'implementation':p['implementation'],'public_upload':False,'source_sha256':receipt['source_sha256']}}
        for role,obj in files.items():fn=self.root/(key+'_'+role+'.json');dump(fn,obj);local[role]=fn
        proof=[]
        for entry in summary:
            role=entry['role'];proof.append({**entry,'path':entry['variant']+'/'+role+'.tsv','sha256':'a'*64,'bytes':10,'scope':'FULL_SERVER_FILE_SCAN_NOT_INDEPENDENT_SCIENTIFIC_VALIDATION','preview_path':entry['variant']+'/'+role+'.preview.tsv','preview_sha256':'a'*64,'preview_rows':1})
        for output in outputs:output.update(sha256='a'*64,bytes=10)
        outputs.extend({'path':v+'/'+role+'.preview.tsv','sha256':'a'*64,'bytes':10} for v in variants for role in spec['required_roles'])
        comparison=[{'variant':v,'scientific_robustness_established':False} for v in ('alt1','alt2')]
        for name,data in (('full_result_audit',proof),('actual_sensitivity_comparison',comparison)):
            fn=self.root/(key+'_'+name+'.json');dump(fn,data);local[name]=fn
        return request,receipt,local,spec
    def test_all71_bounded_result_shape_checks(self):
        for key in REG:
            with self.subTest(key=key):self.assertEqual(inspect_branch(*self.branch_fixture(key)),[])
    def test_all71_result_identity_change_refused(self):
        for key in REG:
            request,receipt,local,spec=self.branch_fixture(key);x=ac.load(local['implementation_record']);x['implementation']='WRONG_METHOD';dump(local['implementation_record'],x)
            with self.subTest(key=key):self.assertIn('method_identity_mismatch',inspect_branch(request,receipt,local,spec))
    def test_all71_missing_variant_result_refused(self):
        for key in REG:
            request,receipt,local,spec=self.branch_fixture(key);receipt['outputs']=receipt['outputs'][1:]
            with self.subTest(key=key):self.assertTrue(any(s.startswith('variant_data_not_returned') for s in inspect_branch(request,receipt,local,spec)))
    def test_all71_unit_drift_is_hold(self):
        for key in REG:
            request,receipt,local,spec=self.branch_fixture(key);x=ac.load(local['analysis_qc']);x['context']['independent_unit']='spot';dump(local['analysis_qc'],x)
            with self.subTest(key=key):self.assertIn('unit_estimand_handoff_changed',inspect_branch(request,receipt,local,spec))
    def test_probability_out_of_range_refused(self):
        request,receipt,local,spec=self.branch_fixture('differential_coexpression');f=local[spec['required_roles'][0]]
        text=f.read_text(encoding='utf8').replace('0.5','2.5');f.write_text(text,encoding='utf8')
        self.assertTrue(any('probability' in v for v in inspect_branch(request,receipt,local,spec)))

if __name__=='__main__':unittest.main(verbosity=2)
