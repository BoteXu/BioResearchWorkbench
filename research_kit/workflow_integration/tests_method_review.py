"""Adversarial source contracts and bounded result checks; never run scientific fits."""
from pathlib import Path
import unittest,tempfile,json,csv,sys
ROOT=Path(__file__).parent
from server.analysis71 import contract
from server.method_contract71 import strict_bool,validate_rows
from fixtures71 import params
from acceptance import load
from workflow71 import current_acceptance
REG=load(ROOT/'server/branches71.json')

class MethodReview(unittest.TestCase):
    def test_all71_reject_unconsumed_parameters(self):
        for key,s in REG.items():
            p=params(key,REG);p['ignored_method_setting']='not allowed'
            with self.subTest(method=key),self.assertRaises(ValueError):contract(p,dict.fromkeys(s['required_inputs']))
    def test_coloc_susie_requires_real_LD_roles(self):
        p=params('colocalization',REG);p['coloc_mode']='SuSiE';ids=dict.fromkeys(REG['colocalization']['required_inputs'])
        with self.assertRaises(ValueError):contract(p,ids)
        ids.update(dict.fromkeys(['ld1','ld2','ld1_variants','ld2_variants']));self.assertEqual(contract(p,ids)['scientific_runtime'],'NOT_RUN_THIS_UPGRADE')
    def test_ORF_donor_branch_requires_control_and_units(self):
        p=params('uorf_translation',REG);p['periodicity_inference']='donor_controlled';ids=dict.fromkeys(REG['uorf_translation']['required_inputs'])
        with self.assertRaises(ValueError):contract(p,ids)
        ids.update(samples=None,orf_negative_controls=None);contract(p,ids)
    def test_Welch_cannot_ignore_covariates(self):
        p=params('lr_differential',REG);p.update(contrast_method='unpaired_welch',covariates=['age'])
        with self.assertRaises(ValueError):contract(p,dict.fromkeys(REG['lr_differential']['required_inputs']))
    def test_false_text_is_false(self):self.assertIs(strict_bool('False'),False)
    def test_missing_boolean_is_not_false(self):
        with self.assertRaises(ValueError):strict_bool(None)
    def test_coloc_posterior_value_bounds(self):
        issues=validate_rows(['signal_pair','hypothesis','value'],[dict(signal_pair='pair',hypothesis='H4',value='2')],REG['colocalization']['primary_result_rule']);self.assertIn('probability_out_of_range:value',issues)
    def test_duplicate_omics_identity_is_rejected(self):
        row={'source':'A','target':'B','p':'.1','q':'.2'};issues=validate_rows(list(row),[row,row],{'keys':['source','target']});self.assertIn('duplicate_result_key',issues)
    def test_empty_enrichment_is_valid_without_negative_claim(self):
        self.assertEqual(validate_rows(['term','feature_id'],[],REG['leading_edge']['primary_result_rule']),[])
    def test_full_denominator_exceeds_preview(self):
        sys.path.insert(0,str(ROOT/'server'))
        from result_audit71 import audit
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f=root/'result.tsv';f.write_text('feature_id\tvalue\n'+''.join(str(i)+'\t.1\n' for i in range(47)),encoding='utf8');r=audit(f,{'required':['feature_id'],'keys':['feature_id']},root/'preview.tsv');self.assertEqual(r['rows'],47);self.assertEqual(r['preview_rows'],40)
    def test_historical_receipt_is_not_current_environment(self):
        state=current_acceptance(ROOT,{'state':'COMPLETED','source_sha256':{},'versions':{'fixture':'0'},'plan_sha256':'a'},{'plan_sha256':'a'});self.assertTrue(state['historical_success']);self.assertFalse(state['current_environment_verified'])
    def test_rerun_comparison_must_not_establish_scientific_robustness(self):
        self.assertTrue(all('scientific' in s['sensitivity_interpretation'] for s in REG.values()))
    def test_declared_maximum_is_enforced(self):
        p=params('isoform_switch',REG);p['min_switch_delta']=.9
        with self.assertRaises(ValueError):contract(p,dict.fromkeys(REG['isoform_switch']['required_inputs']))
    def test_disabled_template_is_never_prepared(self):
        import workbench
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'disabled.json';path.write_text(json.dumps({'template_not_executable':True}),encoding='utf8')
            with self.assertRaises(ValueError):workbench.plan(path,root/'out')
            self.assertFalse((root/'out').exists())

if __name__=='__main__':unittest.main()
