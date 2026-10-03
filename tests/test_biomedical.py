"""Synthetic acceptance and failure cases for all ten biomedical helpers."""
import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
import biomedical_ext as bio
FIXTURES = json.loads((ROOT/'examples'/'biomedical_inputs.json').read_text(encoding='utf8'))


class BiomedicalChecks(unittest.TestCase):
    def args(self,name):
        return copy.deepcopy(FIXTURES[name])

    def test_drug_units_binding_and_censored_activity(self):
        args = self.args('audit_drug_target_records')
        result = bio.audit_drug_target_records(**args)['records'][0]
        self.assertEqual(result['value_nM'],100)
        self.assertEqual(result['negative_log_molar'],7)
        self.assertTrue(result['binding_assay_candidate'])
        args['records'][0].update(standard_relation='<',assay_type='F')
        result = bio.audit_drug_target_records(**args)['records'][0]
        self.assertIsNone(result['negative_log_molar'])
        self.assertFalse(result['binding_assay_candidate'])

    def test_drug_duplicates_species_and_mass_units_rejected(self):
        args = self.args('audit_drug_target_records')
        args['records'] *= 2
        self.assertIn('duplicate_or_source_flagged_duplicate',bio.audit_drug_target_records(**args)['records'][1]['issues'])
        args['records'][0].update(species='mus_musculus',standard_units='mg/L',standard_value=float('nan'))
        result = bio.audit_drug_target_records(**args)['records'][0]
        self.assertFalse(result['record_check_pass'])
        self.assertIn('species_missing_or_mismatch',result['issues'])

    def test_cohort_eligibility_and_overlap(self):
        args = self.args('assess_cohort_eligibility')
        self.assertEqual(bio.assess_cohort_eligibility(**args)['studies'][0]['decision'],'eligible_under_supplied_criteria')
        args['studies'][0]['cohort_id']='synthetic_cohort'
        args['studies'].append({**args['studies'][0],'study_id':'synthetic_second'})
        self.assertTrue(bio.assess_cohort_eligibility(**args)['overlapping_cohort_ids'])

    def test_cohort_missing_metadata_differs_from_exclusion(self):
        args = self.args('assess_cohort_eligibility')
        args['studies'][0].pop('matrix_type')
        self.assertEqual(bio.assess_cohort_eligibility(**args)['studies'][0]['decision'],'needs_review')
        args['studies'][0]['biological_unit']='cell'
        self.assertEqual(bio.assess_cohort_eligibility(**args)['studies'][0]['decision'],'exclude')

    def test_genetic_beta_swap_preserves_original_and_interval(self):
        args = self.args('audit_genetic_alignment')
        original = copy.deepcopy(args)
        result = bio.audit_genetic_alignment(**args)['rows'][0]
        self.assertTrue(result['alignment_pass'])
        self.assertEqual(result['aligned_right']['effect'],0.4)
        self.assertEqual(result['aligned_right']['confidence_interval'],[0.2,0.6])
        self.assertAlmostEqual(result['aligned_right']['effect_allele_frequency'],0.3)
        self.assertEqual(args,original)

    def test_genetic_or_reciprocal_and_strand_complement(self):
        args = self.args('audit_genetic_alignment')
        right = args['rows'][0]['right']
        right.update(effect_type='OR',effect=2,confidence_interval=[1.5,3])
        result = bio.audit_genetic_alignment(**args)['rows'][0]
        self.assertEqual(result['aligned_right']['effect'],0.5)
        self.assertEqual(result['aligned_right']['confidence_interval'],[1/3,1/1.5])
        right.update(effect_allele='T',other_allele='G',effect_allele_frequency=0.3)
        self.assertIn('complement_strand',bio.audit_genetic_alignment(**args)['rows'][0]['actions'])

    def test_genetic_palindrome_build_and_coordinate_rejected(self):
        args = self.args('audit_genetic_alignment')
        args['rows'][0]['left']['other_allele']='T'
        args['rows'][0]['right'].update(assembly='GRCh37',position=102)
        result = bio.audit_genetic_alignment(**args)['rows'][0]
        self.assertFalse(result['alignment_pass'])
        self.assertIsNone(result['aligned_right'])
        self.assertIn('build_missing_or_mismatch',result['issues'])
        self.assertIn('position_missing_or_mismatch',result['issues'])
        self.assertIn('palindromic_variant_requires_explicit_reference_review',result['issues'])

    def test_evidence_matrix_keeps_absence_separate_from_negative(self):
        result = bio.build_evidence_matrix(**self.args('build_evidence_matrix'))
        self.assertIn('human_genetics',result['candidates'][0]['absent_classes'])
        self.assertEqual(len(result['candidates'][0]['evidence']['binding']),1)
        self.assertEqual(result['scientific_validity'],'not_established')

    def test_evidence_conflict_null_and_context_difference(self):
        args = self.args('compare_evidence')
        self.assertEqual(bio.compare_evidence(**args)['comparisons'][0]['classification'],'direction_conflict')
        args['records'][1]['outcome']='null'
        self.assertEqual(bio.compare_evidence(**args)['comparisons'][0]['classification'],'null_or_detection_difference')
        args['records'][1]['time']='different_time'
        self.assertEqual(bio.compare_evidence(**args)['comparisons'][0]['classification'],'not_comparable')

    def test_structure_coverage_and_missing_functional_region(self):
        args = self.args('audit_structure_context')
        self.assertTrue(bio.audit_structure_context(**args)['structures'][0]['context_check_pass'])
        args['records'][0]['mapped_intervals'].append([30,60])
        self.assertEqual(bio.audit_structure_context(**args)['structures'][0]['mapped_fraction'],0.6)
        args['records'][0]['missing_residues']=[20]
        self.assertFalse(bio.audit_structure_context(**args)['structures'][0]['context_check_pass'])

    def test_structure_wrong_isoform_and_mutation_require_review(self):
        args = self.args('audit_structure_context')
        args['records'][0].update(isoform='isoform_2',mutations=['synthetic_mutation'])
        result = bio.audit_structure_context(**args)['structures'][0]
        self.assertIn('isoform_requires_review',result['issues'])
        self.assertIn('mutations_require_review',result['issues'])

    def test_disease_mapping_relations_never_automatically_merge(self):
        args = self.args('map_disease_terms')
        result = bio.map_disease_terms(**args)['mappings'][0]
        self.assertFalse(result['asserted_exact'])
        self.assertFalse(result['automatic_merge_allowed'])
        args['mappings'][0]['relation']='exact'
        self.assertTrue(bio.map_disease_terms(**args)['mappings'][0]['asserted_exact'])
        args['mappings'][0].pop('ontology_version')
        self.assertFalse(bio.map_disease_terms(**args)['mappings'][0]['asserted_exact'])

    def test_disease_public_query_consent_and_candidate_semantics(self):
        fake = types.ModuleType('http_client')
        fake.get_json = lambda *a: {'response':{'docs':[{'obo_id':'MONDO:0000001','label':'synthetic disease'}]}}
        with patch.dict(sys.modules,{'http_client':fake}):
            with self.assertRaises(ValueError):
                bio.map_disease_terms(['synthetic disease'],sensitive_data=True)
            result = bio.map_disease_terms(['synthetic disease'])
        self.assertFalse(result['terms'][0]['automatic_merge_allowed'])

    def test_cell_rules_donor_counts_and_conflicting_markers(self):
        args = self.args('audit_cell_annotations')
        self.assertFalse(bio.audit_cell_annotations(**args)['clusters'][0]['annotation_review_required'])
        args['clusters'][0].update(donor_count=1,markers=['GENE_A','GENE_C'],doublet_flag=True)
        result = bio.audit_cell_annotations(**args)['clusters'][0]
        self.assertTrue(result['annotation_review_required'])
        self.assertIn('conflicting_markers',result['issues'])
        self.assertIn('insufficient_or_unknown_donors',result['issues'])

    def test_enrichment_background_mapping_loss_and_driver_concentration(self):
        args = self.args('audit_enrichment_results')
        result = bio.audit_enrichment_results(**args)
        self.assertTrue(result['mapping_loss_warning'])
        self.assertFalse(result['terms'][0]['issues'])
        args['results'][0]['driver_contributions']={'GENE_A':9,'GENE_B':1}
        args['background_genes']=['GENE_B']
        result = bio.audit_enrichment_results(**args)['terms'][0]
        self.assertIn('drivers_outside_background',result['issues'])
        self.assertIn('concentrated_driver_contribution',result['issues'])

    def test_enrichment_duplicates_nes_and_nonfinite_weights(self):
        args = self.args('audit_enrichment_results')
        args['results']*=2
        args['results'][0].update(method='GSEA',NES=-1,direction='positive',driver_contributions={'GENE_A':float('inf')})
        result = bio.audit_enrichment_results(**args)['terms']
        self.assertIn('nes_direction_mismatch',result[0]['issues'])
        self.assertIn('invalid_driver_contributions',result[0]['issues'])
        self.assertIn('duplicate_term_version_contrast',result[1]['issues'])

    def test_study_passages_located_without_inventing_values(self):
        result = bio.extract_study_elements(str(ROOT/'examples'/'study_fixture.md'))
        self.assertIsNone(result['fields']['randomization']['value'])
        self.assertIn('not randomized',result['fields']['randomization']['excerpts'][0]['excerpt'])
        self.assertEqual(result['fields']['sample']['excerpts'][0]['location_type'],'line')
        self.assertTrue(result['fields']['statistical_unit']['excerpts'])

    def test_missing_study_element_remains_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder)/'fixture.txt'
            file.write_text('Synthetic empty report',encoding='utf8')
            result = bio.extract_study_elements(str(file))
        self.assertEqual(result['fields']['dose']['state'],'not_located_by_rules')

    def test_source_integrity_checks_do_not_verify_assertion(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)/'source.json'
            data.write_text('{}')
            receipt = Path(folder)/'receipt.json'
            receipt.write_text(json.dumps({'result_file':str(data),'sha256':hashlib.sha256(data.read_bytes()).hexdigest()}))
            args = self.args('build_evidence_matrix')
            args['records'][0]['receipt_file']=str(receipt)
            provenance = bio.build_evidence_matrix(**args)['candidates'][0]['evidence']['binding'][0]['provenance']
            self.assertEqual(provenance['receipt_integrity'],'verified')
            self.assertFalse(provenance['assertion_verified'])
            data.write_text('{"changed":true}')
            with self.assertRaises(ValueError):
                bio.build_evidence_matrix(**args)


if __name__=='__main__':
    unittest.main()
