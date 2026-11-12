"""Metadata, privacy, route and rejection checks only; no scientific engines executed."""
from pathlib import Path
import unittest,json,copy,ast,tempfile,hashlib
from teaching_flow import plan,coverage
from server.teaching_contracts import qc_thresholds,unit_map,validate_kernels,validate_backend
HERE=Path(__file__).parent
class TeachingChecks(unittest.TestCase):
    def test_all_315_primary_pages_covered(self):
        c=coverage();self.assertEqual(len(c['stages']),43);self.assertEqual(set().union(*(set(s['slides']) for s in c['stages'] if s['id']!='delivery')),set(range(1,316)))
    def test_43_unique_stages(self):self.assertEqual(len({s['id'] for s in coverage()['stages']}),43)
    def test_all_stages_block_without_actual_channels(self):
        p=plan({'public_upload':False,'stages':'all'});self.assertEqual(p['state'],'HOLD');self.assertTrue(all(s['stage_state']=='HOLD' for s in p['stages']))
    def test_dependency_order_and_no_duplicate_execution(self):
        p=plan({'public_upload':False,'stages':['perturbation_benchmark','annotation']});ids=[s['id'] for s in p['stages']];self.assertEqual(len(ids),len(set(ids)))
        for s in p['stages']:
            for parent in s['requires']:self.assertLess(ids.index(parent),ids.index(s['id']))
    def test_unknown_stage_rejected(self):
        with self.assertRaises(ValueError):plan({'public_upload':False,'stages':['magic_analysis']})
    def test_public_route_rejected(self):
        with self.assertRaises(ValueError):plan({'public_upload':True,'stages':'all'})
    def test_null_channel_not_ready(self):
        p=plan({'public_upload':False,'stages':['design'],'channels':{'estimand':None}});self.assertIn('estimand',p['stages'][0]['missing_channels'])
    def test_plain_pass_not_qc(self):
        p=plan({'public_upload':False,'stages':['design'],'checks':{'design__1':'PASS'}});self.assertEqual(p['stages'][0]['checks'][0]['state'],'INVALID')
    def test_unbound_pass_is_not_validated(self):
        p=plan({'public_upload':False,'stages':['design'],'checks':{'design__1':{'state':'PASS'}}});self.assertEqual(p['stages'][0]['checks'][0]['state'],'UNBOUND_DECLARATION')
    def test_NA_does_not_bypass_mandatory_gate(self):
        p=plan({'public_upload':False,'stages':['design'],'checks':{'design__1':{'state':'NA','reason':'not available'}}});self.assertEqual(p['state'],'HOLD')
    def test_no_auto_dispatch_even_with_bound_evidence(self):
        s=coverage()['stages'][0];source={'source_sha256':'1'*64,'source_locator':'fixture-only'};e={'state':'PASS','source_sha256':'1'*64,'evidence_locator':'fixture-only','reviewer':'test','scope':'metadata only'}
        p=plan({'public_upload':False,'stages':['design'],'channels':{c:source for c in s['required_channels']},'checks':{'design__'+str(i):e for i in range(1,4)}});self.assertFalse(p['server_dispatch']);self.assertEqual(p['scientific_validity'],'NOT_ESTABLISHED')
    def test_sample_specific_thresholds(self):
        x=qc_thresholds(['sampleA','sampleB'],{'min_counts':5,'min_genes':2,'max_mito_percent':8},{'sampleB':{'max_mito_percent':12}});self.assertEqual(x['sampleA']['max_mito_percent'],8);self.assertEqual(x['sampleB']['max_mito_percent'],12)
    def test_unknown_sample_override_rejected(self):
        with self.assertRaises(ValueError):qc_thresholds(['A'],{}, {'B':{}})
    def test_bad_threshold_numeric_rejected(self):
        for v in [True,float('nan'),-1]:
            with self.subTest(v=v),self.assertRaises(ValueError):qc_thresholds(['A'],{'min_counts':v,'min_genes':2,'max_mito_percent':8})
    def test_mito_percent_range_rejected(self):
        with self.assertRaises(ValueError):qc_thresholds(['A'],{'min_counts':3,'min_genes':2,'max_mito_percent':101})
    def test_unknown_threshold_name_rejected(self):
        with self.assertRaises(ValueError):qc_thresholds(['A'],{'min_counts':3,'min_genes':2,'max_mito_percent':8,'magic':2})
    def test_sample_condition_map_conflict(self):
        with self.assertRaises(ValueError):unit_map([{'s':'S','u':'U','c':'A'},{'s':'S','u':'U','c':'B'}],'s','u','c')
    def test_literal_units_not_alias_merged(self):self.assertEqual(len(unit_map([{'s':'S_1','u':'U','c':'A'},{'s':'S-1','u':'U','c':'A'}],'s','u','c')),2)
    def test_kernel_direction_required(self):
        with self.assertRaises(ValueError):validate_kernels([{'kind':'connectivity','weight':1}])
    def test_no_fake_velocity_fallback(self):
        with self.assertRaises(ValueError):validate_kernels([{'kind':'unknown','weight':1}])
    def test_kernel_weights(self):
        with self.assertRaises(ValueError):validate_kernels([{'kind':'velocity','weight':.4}])
    def test_duplicate_kernels(self):
        with self.assertRaises(ValueError):validate_kernels([{'kind':'velocity','weight':.5},{'kind':'velocity','weight':.5}])
    def test_kernel_input_not_mutated(self):
        r=[{'kind':'velocity','weight':.8},{'kind':'connectivity','weight':.2}];old=copy.deepcopy(r);validate_kernels(r);self.assertEqual(old,r)
    def test_no_unpinned_optional_backend(self):
        with self.assertRaises(ValueError):validate_backend('cnmf_programs',{'seed':42})
    def test_formula_cannot_evaluate_arbitrary_source_code(self):
        p={'software_versions':{'pertpy':'fixture','arviz':'fixture','anndata':'fixture'},'est_fdr':.05,'chains':2,'diagnostic_var_names':['beta'],'covariates':['condition'],'formula':'dangerous_function(condition)'}
        with self.assertRaises(ValueError):validate_backend('composition_sccoda',p)
    def test_all71_original_method_ids_preserved(self):
        # Exact immutable original v3.1.1 bytes, verified before this review.
        # Do not require another private installation beside a portable package.
        expected='bf773dbd22a5b6b3059c753dd39da7886d34492ee5eec958025ac13c513d9116'
        self.assertEqual(hashlib.sha256((HERE/'server/branches71.json').read_bytes()).hexdigest(),expected)
    def test_six_new_routes_registered(self):
        p=json.loads((HERE/'profiles.json').read_text(encoding='utf8'));self.assertTrue({'cnmf_programs','composition_sccoda','cellrank_multiview','perturbation_baselines'}<=set(p['backends']));self.assertTrue({'edgeR_QL','limma_voom'}<=set(p['r_methods']))
    def test_new_backend_handoff_is_real_but_never_submitted(self):
        import workbench
        project={'backend':'cnmf_programs','public_upload':False,'server_execution_authorized':False,'parameters':{'unit_key':'unit','count_layer':'counts','components':[2,3],'selected_k':2,'n_iter':2,'seed':42,'density_threshold':.5,'local_neighborhood_size':.3,'hvg_count':20,'max_nmf_iterations':50,'top_genes':5,'software_versions':{'cnmf':'FIXTURE_NOT_INSTALLED','anndata':'FIXTURE_NOT_INSTALLED'}},'inputs':[{'id':'object','path':'fixture_not_a_real_dataset.h5ad','sha256':'1'*64}],'upstream_qc':{'scope':'metadata fixture, no scientific data'},'statistical_plan':{'estimand':'fixture','independent_unit':'fixture','missingness':'fixture','multiplicity':'fixture','sensitivity':'fixture'},'acceptance_rules':[{'role':'diagnostics','field':'0.selected_k','definition':'fixture-only declared K','unit':'count','threshold_basis':'engineering fixture','op':'eq','value':2}],'resource_budget':{'cpus':1,'gpus':0}}
        project['acceptance_rules']=[{'id':'fixture_selected_k','role':'diagnostics','field':'selected_k','definition':'fixture-only declared K','unit':'count','threshold_basis':'engineering fixture only','operator':'eq','bound':2}]
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'fixture.json';src.write_text(json.dumps(project),encoding='utf8');result=workbench.plan(src,Path(td)/'prepared')
            self.assertEqual(result['state'],'prepared_not_submitted');prepared=json.loads((Path(td)/'prepared/server_request.private.json').read_text(encoding='utf8'));self.assertFalse(prepared['server_execution_authorized']);self.assertIn('teaching_extensions.py',prepared['source_sha256']);self.assertTrue((Path(td)/'prepared/server/teaching_extensions.py').is_file())
    def test_server_guard_still_rejects_this_computer(self):
        from server.runtime import guard
        with self.assertRaises(RuntimeError):guard({})
    def test_scientific_module_has_no_numeric_import_at_top(self):
        tree=ast.parse((HERE/'server/teaching_extensions.py').read_text(encoding='utf8'));names=[]
        for n in tree.body:
            if isinstance(n,ast.Import):names.extend(a.name for a in n.names)
            if isinstance(n,ast.ImportFrom):names.append(n.module)
        self.assertFalse(set(names)&{'numpy','pandas','scanpy','cnmf','cellrank','pertpy'})
if __name__=='__main__':unittest.main(verbosity=2)
