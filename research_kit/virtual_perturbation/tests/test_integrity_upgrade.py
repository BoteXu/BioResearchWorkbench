"""Adversarial metadata/result-check regressions. No scientific library is imported."""
from pathlib import Path
import sys,unittest,json,copy
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'server')]
import test_returns as fixtures
from training_partitions import inspect_ledger
from return_binding import algebra_issues,comparison_scope
class Integrity(unittest.TestCase):
    def setUp(self):self.fixture=fixtures.Returns();self.fixture.setUp()
    def tearDown(self):self.fixture.tearDown()
    def test_nonempty_result_cannot_have_empty_preview(self):
        self.fixture.change('primary/predicted_expression.preview.private.json',lambda p:p.update(preview_rows=[],is_full_result=False))
        self.assertIn('preview_row_count_mismatch',self.fixture.result()['issues'])
    def test_missing_receipt_identity_cannot_equal_missing_proof(self):
        self.fixture.change('full_result_audit.private.json',lambda p:p[0].update(path='UNREGISTERED.tsv',sha256=None,bytes=None))
        self.fixture.change('primary/predicted_expression.preview.private.json',lambda p:p.update(full_result_sha256=None))
        self.assertIn('full_result_path_not_canonical_or_registered',self.fixture.result()['issues'])
    def test_sensitivity_duplicate_is_not_complete_coverage(self):
        self.fixture.change('sensitivity_comparison.private.json',lambda p:p.append(dict(p[0])))
        self.assertIn('sensitivity_unit_denominators_missing_or_duplicate',self.fixture.result()['issues'])
    def test_full_result_cannot_switch_primary_and_alternate(self):
        self.fixture.change('full_result_audit.private.json',lambda p:p[0].update(path='alternate_1/predicted_expression.tsv'))
        self.assertIn('full_result_path_not_canonical_or_registered',self.fixture.result()['issues'])
    def test_reported_delta_requires_WT_KO_consistency(self):
        self.fixture.change('primary/predicted_expression.preview.private.json',lambda p:p['preview_rows'][0].update(model_delta='0.9'))
        self.assertIn('inconsistent_reported_difference_or_ratio',self.fixture.result()['issues'])
    def test_comparison_donor_cannot_be_invented(self):
        self.fixture.change('sensitivity_comparison.private.json',lambda p:p[0].update(unit_id='UNDECLARED_UNIT'))
        self.assertIn('sensitivity_unit_denominators_missing_or_duplicate',self.fixture.result()['issues'])
    def test_primary_missing_donor_is_explicit(self):
        self.fixture.change('full_result_audit.private.json',lambda p:p[0].update(unit_row_counts={}))
        self.assertIn('primary_unit_denominator_incomplete',self.fixture.result()['issues'])
    def test_model_selection_donor_is_not_heldout(self):
        with self.assertRaises(ValueError):inspect_ledger([{'unit_id':'TRAIN','role':'TRAINING'},{'unit_id':'EVAL','role':'VALIDATION'}],['TRAIN'],['EVAL'],'heldout_donor')
    def test_preprocessing_donor_is_not_heldout(self):
        with self.assertRaises(ValueError):inspect_ledger([{'unit_id':'TRAIN','role':'TRAINING'},{'unit_id':'EVAL','role':'PREPROCESSING_FIT'}],['TRAIN'],['EVAL'],'heldout_donor')
    def test_unknown_or_duplicate_ledger_partition_is_rejected(self):
        for rows in ([{'unit_id':'TRAIN','role':'UNKNOWN'}],[{'unit_id':'TRAIN','role':'TRAINING'}]*2):
            with self.subTest(rows=rows),self.assertRaises(ValueError):inspect_ledger(rows,['TRAIN'],['EVAL'],'heldout_donor')
    def test_scope_distinguishes_time_horizon_from_precision(self):
        self.assertEqual(comparison_scope({'max_time':20},{}),'finite_horizon_exploration_changes_time_estimand')
        self.assertEqual(comparison_scope({'trajectories':200,'seed':17},{'precision_only_parameters':['trajectories']}),'numerical_precision_and_randomness_only')
    def test_conditional_scope_keeps_overlap_disclosed(self):
        r=inspect_ledger([{'unit_id':'TRAIN','role':'TRAINING'}],['TRAIN'],['TRAIN'],'in_sample_conditional');self.assertEqual(r['evaluation_overlap_with_fitted_units'],['TRAIN']);self.assertFalse(r['external_generalization_established'])
    def test_current_compute_identity_is_required(self):
        self.fixture.receipt['host']='WRONG_COMPUTE';self.fixture.rebind();self.assertIn('compute_host_mismatch',self.fixture.result()['issues'])
    def test_no_local_scientific_import(self):
        self.assertNotIn('numpy',sys.modules);self.assertNotIn('torch',sys.modules)
