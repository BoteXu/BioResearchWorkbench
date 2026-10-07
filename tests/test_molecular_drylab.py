import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import molecular_biology_ext as m
import server_operations_ext as s
import validation_ext as v

C={'species':'synthetic','model':'synthetic cells','biological_unit':'independent donor','contrast':'case vs control','source_version':'v1','assembly':'synthetic-assembly'}
def record():
    return {'id':'one',**C,'assay':'synthetic','source_location':'figure 1','source_sha256':'a'*64,'source_reviewed':True,'independent_units':['u1','u2']}
def splice():
    return {**record(),'analysis_level':'exon_event','gene_id':'g','feature_id':'event1','annotation_version':'v1','method_version':'v1','library_type':'paired stranded',
            'mapping_qc_pass':True,'coverage_qc_pass':True,'design_qc_pass':True,'evidence_type':'junction_counts','effect':0.2,'effect_unit':'delta_psi_fraction','adjusted_pvalue':0.02,'tested_universe_recorded':True}
def regulatory():
    return {**record(),'regulator_id':'A','target_id':'B','evidence_type':'chip_binding','claim':'binding','direction':'unsigned','feature_mapping_reviewed':True,'background_qc_pass':True,'replicate_qc_pass':True}
def interaction():
    return {**record(),'participant_a':'A','participant_b':'B','evidence_type':'direct_binding','claim':'direct_binding','pairwise_assay_reviewed':True,'expansion':'none','negative':False,'direction':'unsigned','participant_mapping_reviewed':True,'assay_controls_reviewed':True}
def perturbation():
    return {**record(),'target_id':'A','endpoint':'B','method_version':'v1','design_qc_pass':True,'matched_controls_reviewed':True,'target_specificity_reviewed':True,'confounding_reviewed':True,'tested_universe_recorded':True,'effect':1,'ci_low':0.3,'ci_high':2,'effect_unit':'log2_fold_change','ci_method':'declared independent-unit model','adjusted_pvalue':0.01,'direction':'positive'}

class MolecularTests(unittest.TestCase):
    def setUp(self):
        for module in [m,s,v]:
            p=patch.object(module,'artifact',side_effect=lambda kind,data,*args:{'success':True,**data});p.start();self.addCleanup(p.stop)
    def codes(self,r):return {i['code'] for i in r['issues']}
    def test_splicing_pass_and_expression_is_not_isoform(self):
        self.assertTrue(m.audit_splicing_results([splice()],C)['qc_gate_pass'])
        r=splice();r['evidence_type']='gene_expression';self.assertIn('gene_expression_not_isoform_evidence',self.codes(m.audit_splicing_results([r],C)))
    def test_splicing_percent_wrong_assembly_and_protein_claim(self):
        r=splice();r['effect']=20
        with self.assertRaises(ValueError):m.audit_splicing_results([r],C)
        r=splice();r.update(assembly='other',claims_protein_change=True)
        codes=self.codes(m.audit_splicing_results([r],C));self.assertIn('assembly_mismatch_or_missing',codes);self.assertIn('rna_result_not_protein_validation',codes)
    def test_transcript_structure_not_quantitative_proxy(self):
        r=splice();r['analysis_level']='transcript_structure'
        self.assertFalse(m.audit_splicing_results([r],C)['qc_gate_pass'])
        r['evidence_type']='full_length_structure';self.assertTrue(m.audit_splicing_results([r],C)['qc_gate_pass'])
    def test_usage_does_not_accept_abundance_effect(self):
        r=splice();r.update(analysis_level='transcript_usage',effect_unit='log2_fold_change')
        self.assertIn('usage_estimand_mismatch',self.codes(m.audit_splicing_results([r],C)))
    def test_nonfinite_boolean_duplicate_and_missing_context(self):
        for effect in [True,float('nan'),float('inf')]:
            r=splice();r['effect']=effect
            with self.assertRaises(ValueError):m.audit_splicing_results([r],C)
        with self.assertRaises(ValueError):m.audit_splicing_results([splice(),splice()],C)
        with self.assertRaises(ValueError):m.audit_splicing_results([splice()],{})
    def test_motif_and_unsigned_binding_boundary(self):
        self.assertTrue(m.audit_regulatory_links([regulatory()],C)['qc_gate_pass'])
        r=regulatory();r.update(evidence_type='motif',direction='positive')
        codes=self.codes(m.audit_regulatory_links([r],C));self.assertIn('prediction_not_measured_binding',codes);self.assertIn('binding_or_prediction_not_regulatory_sign',codes)
    def test_ribosome_occupancy_needs_rna_interaction_model(self):
        r=regulatory();r.update(evidence_type='ribosome_occupancy',claim='translation_efficiency')
        self.assertFalse(m.audit_regulatory_links([r],C)['qc_gate_pass'])
        r.update(paired_rna_reviewed=True,interaction_model_reviewed=True);self.assertTrue(m.audit_regulatory_links([r],C)['qc_gate_pass'])
    def protein(self):
        return {**record(),'annotation_type':'go','protein_id':'P','isoform_id':'P-1','annotation_id':'GO:synthetic','annotation_version':'v1','sequence_sha256':'b'*64,'residue_mapping_reviewed':True,'evidence_type':'experimental','evidence_code':'IDA','qualifiers':[],'positive_claim':True}
    def test_go_not_and_computational_validation(self):
        p=self.protein();self.assertTrue(m.audit_protein_annotations([p],C)['qc_gate_pass'])
        p.update(qualifiers=['NOT'],evidence_code='IEA',claims_experimental_validation=True)
        codes=self.codes(m.audit_protein_annotations([p],C));self.assertIn('negated_annotation_not_positive_support',codes);self.assertIn('go_code_not_direct_experimental_validation',codes)
    def test_ptm_residue_probability_and_function_boundary(self):
        p=self.protein();p.update(annotation_type='ptm',start=20,end=20,protein_length=10,site_probability=0.5,declared_min_site_probability=0.8,claims_functional_effect=True)
        codes=self.codes(m.audit_protein_annotations([p],C));self.assertIn('residue_outside_sequence',codes);self.assertIn('ambiguous_ptm_site',codes);self.assertIn('ptm_detection_not_functional_effect',codes)
    def test_direct_association_spoke_expansion_and_negative(self):
        self.assertTrue(m.audit_interaction_records([interaction()],C)['qc_gate_pass'])
        for updates in [{'evidence_type':'physical_association'},{'expansion':'spoke'},{'negative':True},{'direction':'positive'}]:
            r=interaction();r.update(updates);self.assertFalse(m.audit_interaction_records([r],C)['qc_gate_pass'])
    def test_perturbation_independent_unit_ci_sign_and_causality(self):
        self.assertTrue(m.audit_perturbation_results([perturbation()],C)['qc_gate_pass'])
        r=perturbation();r.update(independent_units=['u1','u1'],ci_high=0.5,direction='negative',claims_general_causality=True)
        codes=self.codes(m.audit_perturbation_results([r],C));self.assertIn('duplicated_independent_units',codes);self.assertIn('inconsistent_effect_interval',codes);self.assertIn('effect_direction_mismatch',codes);self.assertIn('context_specific_effect_not_general_causality',codes)
    def graph(self):
        return [{'id':'a','identifier':'A','species':C['species'],'mapping_reviewed':True},{'id':'b','identifier':'B','species':C['species'],'mapping_reviewed':True}], [{'id':'ab','source':'a','target':'b','claim':'binding','direction':'unsigned','evidence_ids':['one']}]
    def test_graph_participants_and_self_labelled_evidence(self):
        nodes,edges=self.graph();r={**interaction(),'kind':'interaction'}
        self.assertTrue(m.audit_mechanism_graph(nodes,edges,[r],C)['qc_gate_pass'])
        r['participant_b']='different';self.assertIn('edge_participant_mismatch',self.codes(m.audit_mechanism_graph(nodes,edges,[r],C)))
        r={**interaction(),'kind':'interaction'};r['evidence_type']='prediction';self.assertFalse(m.audit_mechanism_graph(nodes,edges,[r],C)['qc_gate_pass'])
    def test_graph_null_evidence_ids_are_reported(self):
        nodes,edges=self.graph();edges[0]['evidence_ids']=None
        self.assertFalse(m.audit_mechanism_graph(nodes,edges,[{**interaction(),'kind':'interaction'}],C)['qc_gate_pass'])
    def test_no_private_retrieval_without_exact_public_authorization(self):
        for function,args in [(m.query_intact_interactions,('P01308',9606)),(m.query_complex_record,('CPX-2158',)),(m.query_cell_line,('CVCL_0030',))]:
            with self.assertRaises(ValueError):function(*args)
    def test_query_identity_schema_and_pagination(self):
        with patch.dict(sys.modules,{'http_client':SimpleNamespace(get_json=Mock(return_value={'content':[{'ac':'EBI-1','taxIdA':9606,'taxIdB':9606}],'number':0,'size':1,'totalElements':3,'last':False}))}):
            r=m.query_intact_interactions('P01308',9606,True,page_size=1);self.assertFalse(r['candidate_coverage_complete']);self.assertEqual(r['next_page'],1)
        with patch.dict(sys.modules,{'http_client':SimpleNamespace(get_json=Mock(return_value={'complexAc':'CPX-999','participants':[]}))}):
            with self.assertRaises(ValueError):m.query_complex_record('CPX-2158',True)
        with patch.dict(sys.modules,{'http_client':SimpleNamespace(get_json=Mock(return_value={'content':[],'number':0,'size':100,'totalElements':0}))}):
            with self.assertRaises(ValueError):m.query_intact_interactions('P01308',9606,True)
    def test_budget_and_unknown_submission_are_not_observation(self):
        with patch('code_execution_ext.estimate_compute_resources',return_value={'state':'estimate'}):
            r=s.plan_server_budget([{'units':10,'wall_seconds':3600,'peak_memory_mb':1024}],20,4,rates={'currency':'example','cpu_hour':1,'memory_gib_hour':0})
            self.assertEqual(r['pricing']['estimated_range'],[12,12]);self.assertFalse(r['submitted'])
        r=s.review_unknown_submission('a'*64,[]);self.assertFalse(r['automatic_resubmission_allowed']);self.assertFalse(r['identity_observed'])
    def test_incremental_transfer_preserves_missing_and_defers_active_files(self):
        old=[{'path':'old.tsv','bytes':2,'sha256':'a'*64}]
        cur=[{'path':'new.tsv','bytes':10,'sha256':'b'*64,'stable_snapshot_reviewed':True},{'path':'active.tsv','bytes':1,'sha256':'c'*64}]
        r=s.plan_incremental_return(old,cur,5);self.assertEqual(r['manifest']['files'],[]);self.assertEqual(len(r['deferred']),2);self.assertEqual(r['missing_from_current'],['old.tsv']);self.assertFalse(r['deletion_authorized'])
    def test_all_routes_plan_only_and_unknown_method_refused(self):
        with patch.dict(sys.modules,{'bridge':SimpleNamespace(tool_catalog=Mock(return_value={'tools':[]}))}):
            for task in m.ROUTES:self.assertFalse(m.guide_molecular_drylab(task,C)['submitted'])
        with self.assertRaises(ValueError):m.guide_molecular_drylab('arbitrary',C)
    def test_pipeline_refuses_absent_bound_qc_and_extra_flags(self):
        with self.assertRaises(ValueError):m.prepare_molecular_pipeline('atacseq',{},'missing','a'*64,[],{}, {},'synthetic','synthetic',[],C,[])
    def test_benchmark_layers_are_distinct(self):
        catalog=v.inspect_scientific_benchmarks();spec=catalog['benchmarks'][1]
        r={'schema':1,'benchmark_id':'toothgrowth_welch','metrics':{'mean_difference':5.25,'pvalue':0.00635},'state':'prepared','exit_code':0,'backend_version':'fixture','dataset_version':'fixture','input_sha256':'a'*64,'design':spec['design']}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'receipt.json';p.write_text(json.dumps(r));h=hashlib.sha256(p.read_bytes()).hexdigest()
            result=v.audit_benchmark_receipt(str(p),h,r['benchmark_id']);self.assertTrue(result['interface_correct']);self.assertFalse(result['backend_completed']);self.assertFalse(result['reference_agreement'])
            r['state']='completed';p.write_text(json.dumps(r));h=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertTrue(v.audit_benchmark_receipt(str(p),h,r['benchmark_id'])['reference_agreement'])
            with self.assertRaises(ValueError):v.audit_benchmark_receipt(str(p),'b'*64,r['benchmark_id'])

if __name__=='__main__':unittest.main()
