"""Strict source/receipt format tests only; no scientific execution."""
import unittest
import tests71 as fixtures
from branch71_acceptance import inspect_branch
from acceptance import load
class Binding(unittest.TestCase):
    def setUp(self):self.fixture=fixtures.BranchTests();self.fixture.setUp()
    def tearDown(self):self.fixture.tearDown()
    def case(self):return self.fixture.branch_fixture('colocalization')
    def test_primary_and_alternate_roles_cannot_be_swapped(self):
        request,receipt,local,spec=self.case();data=load(local['full_result_audit']);data[0]['path']='alt1/'+data[0]['role']+'.tsv';fixtures.dump(local['full_result_audit'],data)
        self.assertIn('full_result_path_not_canonical_or_registered',inspect_branch(request,receipt,local,spec))
    def test_duplicate_comparison_is_rejected(self):
        request,receipt,local,spec=self.case();data=load(local['actual_sensitivity_comparison']);data.append(dict(data[0]));fixtures.dump(local['actual_sensitivity_comparison'],data)
        self.assertIn('actual_result_comparison_incomplete',inspect_branch(request,receipt,local,spec))
    def test_preview_must_be_registered(self):
        request,receipt,local,spec=self.case();receipt['outputs']=[r for r in receipt['outputs'] if not r['path'].endswith('.preview.tsv')]
        self.assertIn('preview_not_registered_in_completion_receipt',inspect_branch(request,receipt,local,spec))
    def test_result_count_is_not_a_boolean(self):
        request,receipt,local,spec=self.case();data=load(local['full_result_audit']);data[0]['rows']=True;fixtures.dump(local['full_result_audit'],data)
        self.assertIn('malformed_full_result_denominator',inspect_branch(request,receipt,local,spec))
