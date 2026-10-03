"""Statistical guidance, privacy refusals and source-boundary contracts without optional packages."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import statistics_ext as st
import privacy_ext as privacy
import advanced_ext as advanced
import server_ext
import scheduler_agent
import reporting_ext


class StatisticsContracts(unittest.TestCase):
    def study(self):
        return dict(question='Does a prespecified exposure change the mean outcome?',design='observational',outcome_type='continuous',independent_unit='donor',estimand='adjusted mean difference',groups=2,repeated=True,clustered=False,primary_endpoints=['outcome'],missing_data='unknown reasons; assess before fitting',covariates=['age'])

    def test_guidance_repetition_and_missingness(self):
        r=st.guide_study_statistics(self.study())
        self.assertEqual(r['state'],'guidance_only');self.assertIn('paired',r['candidate_methods'][0]);self.assertTrue(r['missing_data_guidance']);self.assertIn('causal',r['causal_boundary'])

    def test_guidance_requires_estimand(self):
        d=self.study();d.pop('estimand')
        with self.assertRaises(ValueError): st.guide_study_statistics(d)

    def test_guidance_does_not_choose_from_p(self):
        r=st.guide_study_statistics(self.study());self.assertTrue(any('normality' in v for v in r['required_checks']))

    def test_bh_known_values_and_order(self):
        r=st.adjust_pvalues([.01,.04,.03],'prespecified fixture family')
        for a,b in zip(r['adjusted_pvalues'],[.03,.04,.04]): self.assertAlmostEqual(a,b)

    def test_holm_known_values(self):
        self.assertEqual(st.adjust_pvalues([.01,.04,.03],'fixture','holm')['adjusted_pvalues'],[.03,.06,.06])

    def test_multiplicity_rejects_invalid(self):
        for p in [[float('nan')],[-.1],[1.1]]:
            with self.assertRaises(ValueError): st.adjust_pvalues(p,'fixture')

    def test_leakage_is_detected(self):
        r=st.audit_prediction_split(['a','b'],['b','c'],['a','c'],['c'])
        self.assertFalse(r['leakage_gate_pass']);self.assertIn('validation_used_for_tuning',r['issues'])

    def test_independent_split_is_passed(self):
        self.assertTrue(st.audit_prediction_split(['a','b'],['c','d'],['a','b'],['a'])['leakage_gate_pass'])

    def test_dataset_repeated_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.csv';p.write_text('unit,group,value\na,c,1\na,c,NA\nb,t,2\n')
            r=st.audit_statistical_dataset(str(p),'unit',['value'],'group')
            self.assertFalse(r['qc_gate_pass']);self.assertEqual(r['missing']['value'],1);self.assertEqual(r['independent_units'],2)

    def test_privacy_blocks_categories_without_values(self):
        with patch.object(privacy,'policy',return_value={'mode':'public_data_only','deny_terms':['fixture-private-person']}):
            value='fixture-private-person'
            r=privacy.audit_outbound_parameters({'query':value})
            self.assertFalse(r['outbound_gate_pass']);self.assertNotIn(value,json.dumps(r))

    def test_privacy_paths_and_addresses(self):
        with patch.object(privacy,'policy',return_value={'mode':'public_data_only','deny_terms':[]}):
            local_path='Q'+chr(58)+chr(92)+'private'+chr(92)+'data'
            address='.'.join(['10','1','2','3'])
            r=privacy.audit_outbound_parameters({'path':local_path,'address':address})
            self.assertEqual(set(r['issues']),{'absolute_local_path','address_literal'})

    def test_offline_policy_blocks_public(self):
        with patch.object(privacy,'policy',return_value={'mode':'offline','deny_terms':[]}):
            with self.assertRaises(ValueError): privacy.enforce_outbound({'query':'INS'})

    def test_release_version_exception_is_narrow(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from audit_release import scan_text
        version='.'.join(['3','1','1','23'])
        self.assertNotIn('address_literal',scan_text('openbabel-wheel=='+version))
        self.assertIn('address_literal',scan_text('address='+version))

    def test_communication_donor_gate(self):
        rows=[dict(donor='d'+str(i),condition=g,sender='A',receiver='B',ligand='L',receptor='R',score=1,source='synthetic',method='fixture') for g,i in [('c',0),('c',1),('t',2),('t',3)]]
        result=advanced.audit_cell_communication(rows,['c','t'])
        self.assertFalse(result['pairs'][0]['eligible_for_independent_donor_comparison'])

    def test_coloc_invalid_posterior_and_coverage(self):
        row=dict(locus='fixture',assembly1='buildA',assembly2='buildB',trait1='a',trait2='b',tissue='fixture',method='coloc',signal_model='single_causal_variant',matched_variants=5,variants_trait1=100,variants_trait2=100,priors={'p1':.0001,'p2':.0001,'p12':.00001},posterior={'H0':0,'H1':0,'H2':0,'H3':0,'H4':2},source='synthetic')
        r=advanced.audit_colocalization_results([row]);self.assertFalse(r['records'][0]['eligible_for_interpretation']);self.assertIn('invalid_posterior_probabilities',r['records'][0]['issues'])

    def test_redocking_known_translation(self):
        with tempfile.TemporaryDirectory() as d:
            def atom(i,x): return f'ATOM  {i:5d}  C   UNK A   1    {x:8.3f}{0.:8.3f}{0.:8.3f}  1.00  0.00           C\n'
            p,q=Path(d)/'ref.pdb',Path(d)/'pred.pdb';p.write_text(''.join(atom(i,float(i)) for i in range(1,4)));q.write_text(''.join(atom(i,float(i)+.5) for i in range(1,4)))
            r=advanced.audit_redocking_coordinates(str(p),str(q),[['1','1'],['2','2'],['3','3']],True)
            self.assertAlmostEqual(r['heavy_atom_rmsd_angstrom'],.5);self.assertEqual(r['reference_coverage'],1.)

    def test_md_ranges_and_time(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'md.csv';p.write_text('time,temp\n'+''.join(f'{i},{300 if i<19 else 500}\n' for i in range(20)))
            r=advanced.audit_md_summary(str(p),'time',{'temp':[290,310]},[0,19],5,'ns')
            self.assertFalse(r['review_gate_pass']);self.assertEqual(r['metrics']['temp']['outside_review_range'],1)

    def test_report_escapes_active_content(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);reporting_ext.render_report(p,{'workflow':'fixture','context':{'question':'<script>bad()</script>'},'outputs':[]})
            s=(p/'report.html').read_text();self.assertNotIn('<script>',s);self.assertIn('&lt;script&gt;',s)

    def test_scheduler_unknown_receipt_is_not_completion(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);task=p/'task.json';receipt=p/'scheduler_receipt.json';task.write_text('{}');receipt.write_text('{"state":"submission_outcome_unknown"}')
            result=server_ext.inspect_scheduler_receipt(str(task),str(receipt));self.assertFalse(result['receipt_consistent']);self.assertFalse(result['scheduler_completed'])

    def test_scheduler_submit_and_accounting_contract(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'scheduler.json').write_text(json.dumps(dict(submission_host='fixture-host',cpus=2,memory_mb=1000,walltime='00:05:00',partition='fixture')));(p/'task.json').write_text('{}');(p/'submit.sh').write_text('fixture')
            with patch.object(scheduler_agent.socket,'gethostname',return_value='fixture-host'),patch.object(scheduler_agent,'run',return_value='12345;fixture\n'):
                r=scheduler_agent.operate(p,'submit');self.assertEqual(r['job_id'],'12345')
                with self.assertRaises(ValueError): scheduler_agent.operate(p,'submit')
            with patch.object(scheduler_agent.socket,'gethostname',return_value='fixture-host'),patch.object(scheduler_agent,'run',side_effect=['','12345|COMPLETED|0:0|5||2|fixture-node\n']):
                r=scheduler_agent.operate(p,'status');self.assertEqual(r['state'],'scheduler_completed');self.assertFalse(r['analysis_completion_verified'])


if __name__=='__main__': unittest.main()
