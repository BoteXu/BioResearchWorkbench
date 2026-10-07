import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_acceptance import finalize_report

class AcceptanceLayerChecks(unittest.TestCase):
    def report(self):
        return {'offline':{'failures':[],'errors':[],'skipped':[]},'network_state':'completed','network':[{'case':'fixture','pass':False,'invocation_success':False,'receipt_integrity_verified':True,'http_status':500}]}
    def test_strict_network_failure_stays_false_under_explicit_ci_gate(self):
        r=finalize_report(self.report());self.assertFalse(r['pass']);self.assertFalse(r['ci_gate_pass'])
        r=finalize_report(self.report(),True);self.assertFalse(r['pass']);self.assertFalse(r['network_pass']);self.assertTrue(r['ci_gate_pass']);self.assertEqual(r['network'][0]['availability_state'],'external_unavailable')
    def test_identity_input_and_receipt_failures_never_bypass_gate(self):
        for updates in [{'http_status':None},{'invocation_success':True},{'receipt_integrity_verified':False},{'http_status':400},{'http_status':401}]:
            r=self.report();r['network'][0].update(updates);self.assertFalse(finalize_report(r,True)['ci_gate_pass'])
    def test_offline_failure_or_other_network_failure_is_blocking(self):
        r=self.report();r['offline']['errors']=['fixture'];self.assertFalse(finalize_report(r,True)['ci_gate_pass'])
        r=self.report();r['network'].append({'case':'wrong_identity','pass':False});self.assertFalse(finalize_report(r,True)['ci_gate_pass'])

if __name__=='__main__':unittest.main()
