"""Synthetic receipt-format fixtures only. No scientific result or server run is asserted."""
from pathlib import Path
import sys,tempfile,unittest,json,csv
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'server'))
from contracts import read,write,sha,prepare,catalog
from acceptance import inspect
from runtime import audit_table

class Returns(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);p=read(ROOT/'examples/bulk_virtual_ko.project.example.json');p['example_only']=False
        prepare(p,self.base/'prepared');self.request=self.base/'prepared/request.private.json';r=read(self.request);self.root=self.base/'return';self.root.mkdir();s=catalog()['methods']['bulk_virtual_ko'];proof=[]
        self.selected=['full_result_audit.private.json','sensitivity_comparison.private.json','claim_boundaries.private.json','backend_identity.private.json']
        for label in ('primary','alternate_1','alternate_2'):
            folder=self.root/label;folder.mkdir();self.selected.append(label+'/diagnostics.private.json');write(folder/'diagnostics.private.json',{'fit_completed':True,'metrics':{'maximum_fixed_point_residual':0.0}})
            for role,rule in s['output_rules'].items():
                f=folder/(role+'.tsv');columns=rule['required'];values={k:'IDENTITY_'+k for k in columns};values.update({k:'0.1' for k in rule['numeric']})
                if 'model_KO' in values:values['model_KO']='0.2'
                if 'biological_effect_observed' in values:values['biological_effect_observed']='False'
                with f.open('w',encoding='utf8',newline='') as file:
                    w=csv.DictWriter(file,fieldnames=columns,delimiter='\t');w.writeheader()
                    for unit in r['parameters']['evaluation_units'] if 'unit_id' in columns else [None]:w.writerow({**values,**({'unit_id':unit} if unit is not None else {})})
                a=audit_table(f,rule);preview=a.pop('preview');proof.append({'variant':label,'role':role,'path':f.relative_to(self.root).as_posix(),**a})
                name=label+'/'+role+'.preview.private.json';write(self.root/name,{'full_result_sha256':a['sha256'],'full_rows':a['rows'],'preview_rows':preview,'is_full_result':True})
                if label=='primary':self.selected.append(name)
        write(self.root/'full_result_audit.private.json',proof)
        from server.return_binding import comparison_scope
        write(self.root/'sensitivity_comparison.private.json',[{'variant':v['label'],'unit_id':unit,'shared_features':1,'primary_features':1,'alternate_features':1,'primary_missing_in_alternate':0,'alternate_new_features':0,'top_k':1,'comparison_score':'model_delta','comparison_scope':comparison_scope(v['parameters'],s),'biological_replication_established':False,'scientific_robustness_established':False} for v in r['sensitivity_variants'] for unit in r['parameters']['evaluation_units']])
        write(self.root/'claim_boundaries.private.json',{'measurement_state':'predicted','real_KO_observed':False,'causal_effect_established':False,'survival_benefit_established':False})
        write(self.root/'backend_identity.private.json',{'code_sha256':r['parameters']['expected_backend_code_sha256']})
        self.receipt={'state':'COMPLETED','exit_code':0,'method':r['method'],'run_id':r['run_id'],'host':r['expected_host'],'request_sha256':sha(self.request),'plan_sha256':r['plan_sha256'],'source_sha256':r['source_sha256'],'inputs':r['inputs'],'outputs':[],'measurement_state':'predicted','public_upload':False}
        self.rebind()
    def tearDown(self):self.temp.cleanup()
    def change(self,name,update):
        f=self.root/name;v=read(f);update(v);f.write_text(json.dumps(v,allow_nan=False),encoding='utf8');self.rebind()
    def rebind(self):
        self.receipt['outputs']=[{'path':f.relative_to(self.root).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in self.root.rglob('*') if f.is_file() and f.name!='receipt.private.json'];(self.root/'receipt.private.json').write_text(json.dumps(self.receipt),encoding='utf8')
    def result(self):return inspect(self.request,self.root,self.selected)
    def test_33_consistent_format_still_not_scientific_acceptance(self):
        r=self.result();self.assertEqual(r['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW');self.assertEqual(r['scientific_acceptance'],'NOT_ESTABLISHED');self.assertFalse(r['current_server_environment_verified'])
    def test_34_no_missing_variant_diagnostic(self):
        self.selected.remove('alternate_1/diagnostics.private.json')
        with self.assertRaises(ValueError):self.result()
    def test_35_no_forged_full_result_hash(self):
        self.change('full_result_audit.private.json',lambda p:p[0].update(sha256='a'*64));self.assertIn('full_result_proof_changed',self.result()['issues'])
    def test_36_no_causal_upgrade(self):
        self.change('claim_boundaries.private.json',lambda p:p.update(causal_effect_established=True));self.assertIn('prediction_promoted_to_causal_or_observed_evidence',self.result()['issues'])
    def test_37_no_nonnumeric_preview(self):
        self.change('primary/predicted_expression.preview.private.json',lambda p:p['preview_rows'][0].update(model_delta='not_a_number'));self.assertIn('preview_invalid_numerical_value',self.result()['issues'])
    def test_38_prespecified_diagnostic_gate(self):
        self.change('primary/diagnostics.private.json',lambda p:p['metrics'].update(maximum_fixed_point_residual=.2));self.assertIn('prespecified_measured_gate_failed:maximum_fixed_point_residual',self.result()['issues'])
    def test_39_no_score_kind_switch(self):
        self.change('sensitivity_comparison.private.json',lambda p:p[0].update(comparison_score='logFC'));self.assertIn('invalid_sensitivity_interpretation',self.result()['issues'])
    def test_40_no_historical_source_as_current(self):
        self.receipt['source_sha256']={'changed':'a'*64};self.rebind();self.assertIn('reviewed_source_expired',self.result()['issues'])

if __name__=='__main__':unittest.main()
