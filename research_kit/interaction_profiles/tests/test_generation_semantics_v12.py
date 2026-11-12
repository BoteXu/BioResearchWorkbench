"""Scalar contract/result semantics only; no molecules, numerical libraries or model execution."""
from pathlib import Path
import copy,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import read,validate
from generation_contracts import effective_conditioning,expected_alignment_steps,branch_ids
from server.generation import summarize_generation_counts,summarize_profile_fidelity
from server.constraint_qc import mapping_search_status


class EffectiveConditioning(unittest.TestCase):
    def fixture(self,branch='joint_profile'):
        r=read(ROOT/'examples/branches'/(branch+'.disabled.json'));r['example_only']=False;return r
    def test_all_image_channels_disabled_cannot_claim_joint_profile(self):
        r=self.fixture();r['parameters']['generation_options']['advanced_inpaint']={k:False for k in ('inpaint_x3_pos','inpaint_x3_x','inpaint_x4_pos','inpaint_x4_direction','inpaint_x4_type')}
        with self.assertRaises(ValueError):validate(r)
    def test_partial_overrides_change_actual_branch_label(self):
        r=self.fixture();r['parameters']['generation_options']['advanced_inpaint']={'inpaint_x3_x':False};validate(r)
        self.assertNotIn('joint_profile',branch_ids(r['parameters']));self.assertIn('modality_subset',branch_ids(r['parameters']))
        effective=effective_conditioning(r['parameters']);self.assertEqual(set(effective['effective_modalities']),{'shape','pharm'})
    def test_zero_length_application_is_not_an_image_condition(self):
        r=self.fixture('modality_subset');r['parameters']['generation_options']['advanced_inpaint']={'stop_inpainting_at_time_x3':0.0}
        with self.assertRaises(ValueError):validate(r)
    def test_override_cannot_claim_pharmacophores_from_an_empty_source_axis(self):
        r=self.fixture('modality_subset');g=r['parameters']['generation_options'];g['reference_conditions'][0]['expected_pharmacophore_count']=0;g['advanced_inpaint']={'inpaint_x4_pos':True}
        with self.assertRaises(ValueError):validate(r)
    def test_atom_inpainting_requires_an_actual_positive_duration(self):
        r=self.fixture('atom_bond_inpainting');r['parameters']['generation_options']['advanced_inpaint']={'inpaint_x1_pos':True,'stop_inpainting_at_time_x1_pos':0.}
        with self.assertRaises(ValueError):validate(r)
    def test_fixed_pharmacophores_remain_a_condition_without_inpainting_flags(self):
        r=self.fixture('pharm_full');validate(r);effective=effective_conditioning(r['parameters'])
        self.assertTrue(effective['fixed_pharmacophore_conditioning']);self.assertFalse(effective['native_inpainting_flags']['inpaint_x4_pos']);self.assertIn('pharm',effective['effective_modalities'])
    def test_resolved_all_high_priority_has_no_low_priority_inpainting(self):
        r=self.fixture('pharm_priority');g=r['parameters']['generation_options'];g['reference_conditions'][0]['pharm_selection']['values']=[1]*4
        effective=effective_conditioning(r['parameters'],[[1]*4]);self.assertFalse(effective['native_inpainting_flags']['inpaint_x4_direction'])
    def test_resolved_mask_cannot_have_boolean_priority_values(self):
        r=self.fixture('pharm_priority')
        with self.assertRaises(ValueError):effective_conditioning(r['parameters'],[[True,0,1,0]])
    def test_early_stop_cannot_make_requested_composition_alignment_a_noop(self):
        r=self.fixture('profile_composition');g=r['parameters']['generation_options'];g['composition_alignment'].update(mode='so3',start_fraction=.1);g['sampler']['early_stop_edm']=.5
        self.assertEqual(expected_alignment_steps(r['parameters']),[])
        with self.assertRaises(ValueError):validate(r)
    def test_expected_alignment_schedule_matches_interval_and_previous_prediction(self):
        r=self.fixture('profile_composition');g=r['parameters']['generation_options'];g['composition_alignment'].update(mode='so3',start_fraction=1.,interval=10)
        self.assertEqual(expected_alignment_steps(r['parameters']),list(range(10,400,10)));validate(r)
    def test_alignment_requires_effective_surface_and_ESP_channels(self):
        r=self.fixture('profile_composition');g=r['parameters']['generation_options'];g['composition_alignment'].update(mode='se3',start_fraction=1.);g['advanced_inpaint']={'inpaint_x3_x':False}
        with self.assertRaises(ValueError):validate(r)
    def test_literal_native_alignment_schedule_is_distinct_from_an_ineffective_window(self):
        r=self.fixture('profile_composition');g=r['parameters']['generation_options'];g['composition_alignment'].update(mode='so3',start_fraction=1.,interval=10);g['advanced_inpaint']={'stop_inpainting_at_time_x3':0.}
        self.assertEqual(expected_alignment_steps(r['parameters']),list(range(10,400,10)))
        with self.assertRaises(ValueError):validate(r)
    def test_neutralization_of_disabled_ESP_is_not_claimed(self):
        r=self.fixture('neutralized_esp');r['parameters']['generation_options']['advanced_inpaint']={'inpaint_x3_x':False}
        with self.assertRaises(ValueError):validate(r)
    def test_release_must_have_at_least_one_actual_fixed_step(self):
        r=self.fixture('scaffold_release');r['parameters']['generation_options']['advanced_inpaint']={'stop_inpainting_at_time_x1_pos':.0001}
        with self.assertRaises(ValueError):validate(r)


class IndependentCounts(unittest.TestCase):
    def records(self):
        return [dict(candidate_id='a',chemical_valid=True,constraints_passed=True,hard_constraints_assessed=True,eligible=True),
                dict(candidate_id='b',chemical_valid=True,constraints_passed=True,hard_constraints_assessed=True,eligible=False),
                dict(candidate_id='c',chemical_valid=True,constraints_passed=False,hard_constraints_assessed=True,eligible=False),
                dict(candidate_id='d',chemical_valid=False,constraints_passed=False,hard_constraints_assessed=False,eligible=False)]
    def test_chemical_constraint_and_eligibility_denominators_are_distinct(self):
        r=summarize_generation_counts(self.records(),4,1);m=r['metrics']
        self.assertEqual((m['chemical_valid_count'],m['constraint_pass_count'],m['eligible_count']),(3,2,1))
        self.assertEqual((m['chemical_valid_fraction'],m['constraint_pass_fraction'],m['eligible_fraction']),(.75,.5,.25))
    def test_legacy_chemical_count_is_not_an_eligible_count(self):
        r=summarize_generation_counts(self.records(),4,1);self.assertEqual(r['metrics']['chemical_qc_passed'],3);self.assertEqual(r['metrics']['valid_fraction'],.25);self.assertIn('eligible_fraction',r['deprecated_scope']['valid_fraction'])
    def test_missing_candidate_is_not_a_smaller_validity_denominator(self):
        with self.assertRaises(ValueError):summarize_generation_counts(self.records()[:-1],4,1)
    def test_constraint_pass_requires_a_real_assessment(self):
        rows=self.records();rows[1]['hard_constraints_assessed']=False
        with self.assertRaises(ValueError):summarize_generation_counts(rows,4,1)
    def test_eligibility_cannot_override_failed_chemistry(self):
        rows=self.records();rows[-1]['eligible']=True
        with self.assertRaises(ValueError):summarize_generation_counts(rows,4,1)


class SearchCompleteness(unittest.TestCase):
    def test_capped_search_without_witness_is_unassessed(self):
        r=mapping_search_status(10000,0,False);self.assertEqual(r['assessment_state'],'SEARCH_INCOMPLETE');self.assertFalse(r['assessment_complete'])
    def test_capped_graph_matches_without_a_position_witness_are_unassessed(self):
        r=mapping_search_status(10000,5,False);self.assertEqual(r['assessment_state'],'SEARCH_INCOMPLETE')
    def test_verified_witness_is_sufficient_even_if_other_matches_are_capped(self):
        r=mapping_search_status(10000,1,True);self.assertTrue(r['assessment_complete']);self.assertTrue(r['match_cap_reached']);self.assertFalse(r['match_enumeration_complete'])
    def test_exhaustive_no_witness_can_be_failed_without_claiming_biological_negativity(self):
        r=mapping_search_status(10,0,False);self.assertEqual(r['assessment_state'],'FAILED');self.assertTrue(r['assessment_complete'])
    def test_search_denominator_is_not_boolean(self):
        with self.assertRaises(ValueError):mapping_search_status(True,0,False)


class ProfileFidelity(unittest.TestCase):
    def records(self):
        refs=[{'id':'positive'},{'id':'negative'}];weights=[1.,-.2]
        def scores(state,value):return [dict(reference_id=r['id'],guidance_weight=w,guidance_direction='positive' if w>0 else 'negative',scoring_state=state,shape_similarity=value,esp_surface_similarity=value,pharmacophore_similarity=None) for r,w in zip(refs,weights)]
        return refs,weights,[dict(candidate_id='constraint_failed',chemical_valid=True,eligible=False,profile_fidelity_scores=scores('SCORED',.8)),dict(candidate_id='score_failed',chemical_valid=True,eligible=False,profile_fidelity_scores=scores('FAILED',None)),dict(candidate_id='chem_failed',chemical_valid=False,eligible=False,profile_fidelity_scores=scores('NOT_ASSESSED',None))]
    def test_scores_of_constraint_failed_candidates_are_retained(self):
        refs,w,reports=self.records();r=summarize_profile_fidelity(refs,w,reports,3)
        self.assertEqual(r[0]['scored_count'],1);self.assertEqual(r[0]['metrics']['shape_similarity']['mean'],.8)
    def test_failed_and_unassessed_results_stay_in_requested_denominator(self):
        refs,w,reports=self.records();r=summarize_profile_fidelity(refs,w,reports,3)
        self.assertEqual(r[0]['requested_count'],3);self.assertEqual(r[0]['failed_scoring_count'],1);self.assertEqual(r[0]['unassessed_count'],1);self.assertEqual(r[0]['metrics']['shape_similarity']['missing_count'],2)
    def test_negative_guidance_is_labeled_without_a_selectivity_claim(self):
        refs,w,reports=self.records();r=summarize_profile_fidelity(refs,w,reports,3)
        self.assertEqual(r[1]['guidance_direction'],'negative');self.assertIn('not_selectivity',r[1]['scope'])
    def test_missing_reference_fidelity_status_is_rejected(self):
        refs,w,reports=self.records();reports[0]['profile_fidelity_scores'].pop()
        with self.assertRaises(ValueError):summarize_profile_fidelity(refs,w,reports,3)
    def test_reference_direction_cannot_be_replaced_by_positive_guidance(self):
        refs,w,reports=self.records();reports[0]['profile_fidelity_scores'][1]['guidance_direction']='positive'
        with self.assertRaises(ValueError):summarize_profile_fidelity(refs,w,reports,3)
    def test_extra_unrequested_reference_is_not_part_of_the_fidelity_axis(self):
        refs,w,reports=self.records();extra=copy.deepcopy(reports[0]['profile_fidelity_scores'][0]);extra['reference_id']='extra';reports[0]['profile_fidelity_scores'].append(extra)
        with self.assertRaises(ValueError):summarize_profile_fidelity(refs,w,reports,3)
    def test_failed_scores_cannot_retain_accepted_partial_values(self):
        refs,w,reports=self.records();reports[1]['profile_fidelity_scores'][0]['shape_similarity']=.9
        with self.assertRaises(ValueError):summarize_profile_fidelity(refs,w,reports,3)
    def test_contract_only_checks_import_no_scientific_stack(self):
        self.assertFalse(any(name in sys.modules for name in ('numpy','rdkit','torch','scipy','open3d')))
