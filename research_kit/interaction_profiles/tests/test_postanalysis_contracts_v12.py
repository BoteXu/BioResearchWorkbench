"""Post-analysis source/lineage format rejection only; no native chemistry execution."""
from pathlib import Path
import sys,unittest,copy
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'server')]
from contracts import read,validate
from postanalysis_contracts import lineage_spec

def project(method):
    r=read(ROOT/'examples'/(method+'.project.example.json'));r['example_only']=False;return r

class PostanalysisContracts(unittest.TestCase):
    def test_new_routes_have_explicit_disabled_examples(self):
        for method in ('paper_native_evaluation','prepare_generated_identities'):
            self.assertEqual(validate(project(method))['method'],method)
            with self.assertRaises(ValueError):validate(read(ROOT/'examples'/(method+'.project.example.json')))
    def test_native_parallel_workers_refused_without_worker_audit(self):
        r=project('paper_native_evaluation');r['parameters']['workers']=2
        with self.assertRaises(ValueError):validate(r)
    def test_xtb_cores_must_fit_allocation(self):
        r=project('paper_native_evaluation');r['parameters']['xtb_cores']=8
        with self.assertRaises(ValueError):validate(r)
    def test_postanalysis_cannot_request_cuda(self):
        r=project('paper_native_evaluation');r['parameters']['device']='cuda';r['resource_budget']['gpus']=1
        with self.assertRaises(ValueError):validate(r)
    def test_priority_requires_native_pharmacophore_assessment(self):
        r=project('paper_native_evaluation');r['parameters']['condition']='surface'
        with self.assertRaises(ValueError):validate(r)
    def test_missing_installed_dependency_is_not_inferred(self):
        r=project('paper_native_evaluation');del r['parameters']['expected_versions']['pandas']
        with self.assertRaises(ValueError):validate(r)
    def test_parent_policy_stereo_choices_are_explicit_booleans(self):
        r=project('prepare_generated_identities');r['parameters']['tautomer_remove_sp3_stereo']='false'
        with self.assertRaises(ValueError):validate(r)
    def test_identity_rules_require_native_binary_hash(self):
        r=project('prepare_generated_identities');r['parameters']['expected_standardize_sha256']='unknown'
        with self.assertRaises(ValueError):validate(r)
    def test_no_implicit_parent_normalization(self):
        r=project('prepare_generated_identities');r['parameters']['parent_policy']='automatic'
        with self.assertRaises(ValueError):validate(r)
    def spec(self,method):return read(ROOT/'templates'/(method+'.lineage.example.json'))
    def test_full_native_campaign_denominator_cannot_filter_eligible(self):
        s=self.spec('paper_native_evaluation');s['candidate_ids']=['generated_0']
        with self.assertRaises(ValueError):lineage_spec(s,'paper_native_evaluation')
    def test_identity_requires_explicit_unique_eligible_selection(self):
        s=self.spec('prepare_generated_identities');s['candidate_ids']=['generated_0','generated_0']
        with self.assertRaises(ValueError):lineage_spec(s,'prepare_generated_identities')
    def test_origin_path_escape_and_old_receipt_not_allowed(self):
        s=self.spec('paper_native_evaluation');s['origin_return_root']='../elsewhere'
        with self.assertRaises(ValueError):lineage_spec(s,'paper_native_evaluation')
        s=self.spec('paper_native_evaluation');s['origin_receipt_sha256']='historical_success'
        with self.assertRaises(ValueError):lineage_spec(s,'paper_native_evaluation')
    def test_direct_postanalysis_routes_refuse_local_before_imports(self):
        from server.identity_preparation import run_identity_preparation
        with self.assertRaises(RuntimeError):run_identity_preparation({}, {}, ROOT, ROOT, 1)
        self.assertNotIn('rdkit',sys.modules);self.assertNotIn('numpy',sys.modules)
