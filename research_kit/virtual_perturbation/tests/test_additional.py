"""New route contracts/unsafe-source refusal tests only; no science executed."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'server'))
from contracts import validate,read,catalog
from logic_contract import boolnet_grammar
from model_contracts import cpa_dose_string,cpa_setup_contract,scgpt_architecture_contract
def fixture(key):
    x=read(ROOT/'examples'/(key+'.project.example.json'));x['example_only']=False;return x
class Additional(unittest.TestCase):
    def test_41_all_four_have_real_worker_source(self):
        for key in ('cpa','scgpt','boolnet','maboss'):
            spec=catalog()['methods'][key];validate(fixture(key));source=(ROOT/'server'/('boolnet.R' if key=='boolnet' else 'additional_methods.py')).read_text(encoding='utf8');self.assertIn('BoolNet::stateTransition' if key=='boolnet' else 'def '+key+'(',source);self.assertEqual(spec['scientific_runtime'],'NOT_RUN_SERVER_UNAVAILABLE')
    def test_42_CPA_unknown_ignored_parameters_refused(self):
        x=fixture('cpa');x['parameters']['legacy_API_predict_kwargs']={}
        with self.assertRaises(ValueError):validate(x)
    def test_43_scGPT_reconstruction_gate_required(self):
        x=fixture('scgpt');x['parameters'].pop('max_control_reconstruction_rmse')
        with self.assertRaises(ValueError):validate(x)
    def test_44_CPA_dose_cannot_change_as_same_estimand(self):
        x=fixture('cpa');x['sensitivity_variants'][0]['parameters']={'dose':2}
        with self.assertRaises(ValueError):validate(x)
    def test_45_MaBoSS_full_target_output_required(self):
        x=fixture('maboss');x['parameters']['output_nodes']=['ANOTHER_NODE']
        with self.assertRaises(ValueError):validate(x)
    def test_46_MaBoSS_binary_must_be_bound(self):
        x=fixture('maboss');x['parameters']['expected_binary_sha256']='unknown'
        with self.assertRaises(ValueError):validate(x)
    def test_47_boolnet_R_code_refused(self):
        with self.assertRaises(ValueError):boolnet_grammar('targets, factors\nNODE_A, system("ignored")\n')
    def test_48_boolnet_unknown_node_refused(self):
        with self.assertRaises(ValueError):boolnet_grammar('targets, factors\nNODE_A, NODE_B\n')
    def test_49_boolnet_nonbinary_literal_refused(self):
        with self.assertRaises(ValueError):boolnet_grammar('targets, factors\nNODE_A, 2\n')
    def test_50_valid_Boolean_grammar_is_only_parsed(self):
        self.assertEqual(set(boolnet_grammar('targets, factors\nNODE_A, NODE_B & !NODE_A\nNODE_B, 1\n')),{'NODE_A','NODE_B'});self.assertNotIn('numpy',sys.modules);self.assertNotIn('torch',sys.modules)
    def test_51_CPA_each_target_has_a_dose(self):
        self.assertEqual(cpa_dose_string(2,['A','B']),'2.0+2.0')
        with self.assertRaises(ValueError):cpa_dose_string(float('nan'),['A'])
    def test_52_CPA_registry_uses_actual_checkpoint_axes(self):
        saved={'perturbation_key':'condition','dosage_key':'dose','control_group':'ctrl','max_comb_len':2,'categorical_covariate_keys':['cell_type','batch'],'batch_key':'batch'}
        e={**saved,'perturbation_vocabulary':['A'],'covariate_support':{'cell_type':['TYPE'],'batch':['BATCH']}}
        result=cpa_setup_contract(saved,e,['A'],{'<PAD>':0,'ctrl':1,'A':2},{'cell_type':{'TYPE':0},'batch':{'BATCH':0}})
        self.assertEqual(result['categorical_covariate_keys'],['cell_type']);self.assertEqual(saved['categorical_covariate_keys'],['cell_type','batch'])
    def test_53_CPA_unknown_checkpoint_gene_is_refused(self):
        saved={'perturbation_key':'condition','dosage_key':'dose','control_group':'ctrl','max_comb_len':2}
        with self.assertRaises(ValueError):cpa_setup_contract(saved,{**saved,'perturbation_vocabulary':['UNKNOWN'],'covariate_support':{}},['UNKNOWN'],{'<PAD>':0,'ctrl':1,'A':2},{})
    def test_54_scGPT_padding_must_not_alias_intervention(self):
        with self.assertRaises(ValueError):scgpt_architecture_contract({'explicit_zero_prob':False,'pert_pad_id':1,'d_model':64,'nhead':4})
    def test_55_scGPT_unimplemented_sampling_is_refused(self):
        with self.assertRaises(ValueError):scgpt_architecture_contract({'explicit_zero_prob':True,'pert_pad_id':2,'d_model':64,'nhead':4})
    def test_56_model_source_contracts_do_not_import_scientific_engines(self):
        scgpt_architecture_contract({'explicit_zero_prob':False,'pert_pad_id':2,'d_model':64,'nhead':4})
        self.assertNotIn('numpy',sys.modules);self.assertNotIn('torch',sys.modules)
