"""Standard-library-only structural/refusal tests; no model, data analysis or inference is run."""
from pathlib import Path
import sys,unittest,tempfile,copy,json,csv,importlib.util
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'server'))
from contracts import read,write,sha,validate,catalog,prepare,relative,source_hashes
from runtime import guard,audit_table,qc
from handoff import hypothesis_link

def fixture(key='bulk_virtual_ko'):
    r=read(ROOT/'examples'/(key+'.project.example.json'));r['example_only']=False;return r

class Contracts(unittest.TestCase):
    def test_01_all_eight_method_contracts(self):
        for key in catalog()['methods']:
            with self.subTest(method=key):validate(fixture(key))
    def test_02_examples_are_disabled(self):
        for path in (ROOT/'examples').glob('*.json'):
            with self.subTest(method=path.stem),self.assertRaises(ValueError):validate(read(path))
    def test_03_observed_prediction_refused(self):
        p=fixture();p['measurement_state']='observed'
        with self.assertRaises(ValueError):validate(p)
    def test_04_public_upload_refused(self):
        p=fixture();p['public_upload']=True
        with self.assertRaises(ValueError):validate(p)
    def test_05_truthy_false_not_false(self):
        p=fixture();p['server_execution_authorized']='False'
        with self.assertRaises(ValueError):validate(p)
    def test_06_training_leakage_refused(self):
        p=fixture();p['parameters']['evaluation_units'][0]=p['parameters']['training_units'][0]
        with self.assertRaises(ValueError):validate(p)
    def test_07_no_missing_code_identity(self):
        p=fixture();p['parameters']['expected_backend_code_sha256']='unknown'
        with self.assertRaises(ValueError):validate(p)
    def test_08_no_inactive_DPI_sensitivity(self):
        p=fixture();p['sensitivity_variants'][0]['parameters']={'dpi_threshold':.2}
        with self.assertRaises(ValueError):validate(p)
    def test_09_no_inactive_ROOM_sensitivity(self):
        p=fixture('metabolic_gene_deletion');p['sensitivity_variants'][0]['parameters']={'room_delta':.2}
        with self.assertRaises(ValueError):validate(p)
    def test_10_no_comparison_target_switch(self):
        p=fixture();p['sensitivity_variants'][0]['parameters']={'ko_genes':['OTHER_GENE']}
        with self.assertRaises(ValueError):validate(p)
    def test_11_distinct_alternates(self):
        p=fixture();p['sensitivity_variants'][1]['parameters']=p['sensitivity_variants'][0]['parameters']
        with self.assertRaises(ValueError):validate(p)
    def test_12_no_nan_parameter(self):
        p=fixture();p['parameters']['alpha']=float('nan')
        with self.assertRaises(ValueError):validate(p)
    def test_13_no_float_threads(self):
        p=fixture();p['parameters']['cores']=2.0
        with self.assertRaises(ValueError):validate(p)
    def test_14_no_excess_cpu(self):
        p=fixture();p['parameters']['cores']=3
        with self.assertRaises(ValueError):validate(p)
    def test_15_required_measured_gates(self):
        p=fixture();p['acceptance_rules']=[]
        with self.assertRaises(ValueError):validate(p)
    def test_16_no_missing_input_hash(self):
        p=fixture();p['inputs'][0]['sha256']=''
        with self.assertRaises(ValueError):validate(p)
    def test_17_input_traversal_refused(self):
        p=fixture();p['inputs'][0]['path']='inputs/../private.tsv'
        with self.assertRaises(ValueError):validate(p)
    def test_18_no_unknown_parameters(self):
        p=fixture();p['parameters']['shell_command']='anything'
        with self.assertRaises(ValueError):validate(p)
    def test_19_candidates_are_not_execution_routes(self):
        p=fixture();p['method']='UNREGISTERED_METHOD'
        with self.assertRaises(KeyError):validate(p)
    def test_20_local_worker_refusal_before_scientific_import(self):
        with self.assertRaises(RuntimeError):guard({})
        self.assertNotIn('numpy',sys.modules);self.assertNotIn('torch',sys.modules)
    def test_21_package_plan_copy_source_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'prepared';prepare(fixture(),out);p=read(out/'request.private.json')
            self.assertFalse(p['server_execution_authorized']);self.assertEqual(p['submission_state'],'NOT_SUBMITTED')
            self.assertTrue(all(sha(out/name)==value for name,value in p['source_sha256'].items()))
            self.assertEqual(p['source_sha256'],source_hashes())
    def table(self,text,rule):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'result.tsv';p.write_text(text,encoding='utf8');return audit_table(p,rule)
    def test_22_duplicate_feature_rejected(self):
        with self.assertRaises(ValueError):self.table('id\tscore\na\t1\na\t2\n',{'required':['id','score'],'keys':['id'],'numeric':['score']})
    def test_23_missing_value_rejected(self):
        with self.assertRaises(ValueError):self.table('id\tscore\na\tNA\n',{'required':['id','score'],'keys':['id'],'numeric':['score']})
    def test_24_probability_out_of_range_rejected(self):
        with self.assertRaises(ValueError):self.table('id\tq\na\t1.2\n',{'required':['id','q'],'keys':['id'],'numeric':['q'],'probabilities':['q']})
    def test_25_header_only_not_success(self):
        with self.assertRaises(ValueError):self.table('id\tscore\n',{'required':['id','score'],'keys':['id'],'numeric':['score']})
    def test_26_empty_is_explicit_not_negative(self):
        z=self.table('id\tscore\n',{'required':['id','score'],'keys':['id'],'numeric':['score'],'empty_valid':True});self.assertEqual(z['rows'],0)
    def test_27_preview_is_not_full_denominator(self):
        z=self.table('id\tscore\n'+''.join(str(n)+'\t1\n' for n in range(43)),{'required':['id','score'],'keys':['id'],'numeric':['score']});self.assertEqual(z['rows'],43);self.assertEqual(len(z['preview']),40)
    def test_28_crosslink_observed_upgrade_rejected(self):
        r={'state':'COMPLETED','exit_code':0,'plan_sha256':'a','measurement_state':'predicted','outputs':[]}
        with self.assertRaises(ValueError):hypothesis_link({'plan_sha256':'a'},r,{'destination_measurement_state':'observed'})
    def test_29_crosslink_unknown_submission_rejected(self):
        with self.assertRaises(ValueError):hypothesis_link({'plan_sha256':'a'},{'state':'UNKNOWN','exit_code':0,'plan_sha256':'a'}, {})
    def test_30_root_escape_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):relative(tmp,'../outside')
    def test_31_assay_scale_cannot_be_relabeled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c={k:'EXPLICIT' for k in ('species','assembly','annotation_version','assay','limitations')};c.update(scale='rank_tokenized',independent_unit='donor',estimand='conditional',public_upload=False,measurement_state='predicted')
            write(root/'context.json',c);write(root/'receipt.json',{});write(root/'measure.json',{})
            with self.assertRaisesRegex(ValueError,'scale'):
                qc({'context':root/'context.json','qc_receipt':root/'receipt.json','qc_measurements':root/'measure.json'},{'estimand':'conditional','method':'bulk_virtual_ko'})
    def test_32_QC_must_be_actual_receipt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c={k:'EXPLICIT' for k in ('species','assembly','annotation_version','assay','limitations')};c.update(scale='raw_counts',independent_unit='donor',estimand='conditional',public_upload=False,measurement_state='predicted')
            write(root/'context.json',c);write(root/'receipt.json',{'state':'COMPLETED','exit_code':0,'outputs':[]});write(root/'measure.json',{'accepted':1})
            with self.assertRaisesRegex(ValueError,'bound'):
                qc({'context':root/'context.json','qc_receipt':root/'receipt.json','qc_measurements':root/'measure.json'},{'estimand':'conditional','method':'singlecell_virtual_ko'})

if __name__=='__main__':unittest.main()
