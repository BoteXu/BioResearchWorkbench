"""Contract choices and intentional refusals only; no scientific dependencies or inference."""
from pathlib import Path
import ast,copy,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import read,validate
from generation_contracts import validate_options,branch_ids,BRANCHES,completed_steps,selection_mask
from generation_reports import point_report_issues


class BranchContracts(unittest.TestCase):
    def fixture(self,branch='joint_profile'):
        r=read(ROOT/'examples/branches'/(branch+'.disabled.json'));r['example_only']=False;return r
    def reject(self,r):
        with self.assertRaises(ValueError):validate(r)
    def test_each_declared_branch_has_valid_disabled_review_example(self):
        seen=set()
        for name in BRANCHES:
            r=self.fixture(name);validate(r);seen.update(branch_ids(r['parameters']))
            with self.assertRaises(ValueError):validate({**r,'example_only':True})
        self.assertEqual(seen,set(BRANCHES))
    def test_boolean_scaffold_index_is_not_atom_zero_or_one(self):
        r=self.fixture('scaffold_fixed');r['parameters']['generation_options']['reference_conditions'][0]['scaffold_atom_indices']=[True];self.reject(r)
    def test_duplicate_scaffold_atom_is_not_two_atoms(self):
        r=self.fixture('scaffold_fixed');r['parameters']['generation_options']['reference_conditions'][0]['scaffold_atom_indices']=[0,0];self.reject(r)
    def test_scaffold_bound_includes_explicit_hydrogen_axis(self):
        r=self.fixture('scaffold_fixed');s=r['parameters']['generation_options']['reference_conditions'][0];s['scaffold_atom_indices']=[s['expected_atom_count']];self.reject(r)
    def test_empty_fixed_scaffold_is_not_silent_plain_conditioning(self):
        r=self.fixture('scaffold_fixed');r['parameters']['generation_options']['reference_conditions'][0]['scaffold_atom_indices']=[];self.reject(r)
    def test_selection_requires_exact_atom_and_point_axis_hashes(self):
        r=self.fixture('pharm_priority');r['parameters']['generation_options']['reference_conditions'][0]['pharmacophore_axis_sha256']='UNASSESSED';self.reject(r)
    def test_boolean_priority_mask_is_rejected(self):
        r=self.fixture('pharm_priority');r['parameters']['generation_options']['reference_conditions'][0]['pharm_selection']['values']=[True,0,1,0];self.reject(r)
    def test_short_priority_mask_is_rejected_before_native_truncation(self):
        r=self.fixture('pharm_priority_only');r['parameters']['generation_options']['reference_conditions'][0]['pharm_selection']['values']=[1,0];self.reject(r)
    def test_zero_priority_mask_is_not_silent_inpainting_fallback(self):
        r=self.fixture('pharm_priority');r['parameters']['generation_options']['reference_conditions'][0]['pharm_selection']['values']=[0,0,0,0];self.reject(r)
    def test_indices_selector_builds_complete_exact_mask(self):
        self.assertEqual(selection_mask({'kind':'indices','values':[1,3],'min_ring_atoms':1},8,4),[0,1,0,1])
    def test_atom_selector_is_deferred_to_native_source_not_guessed(self):
        self.assertIsNone(selection_mask({'kind':'atoms','values':[1,3],'min_ring_atoms':2},8,4))
    def test_pharmacophore_priority_requires_pharmacophore_modality(self):
        r=self.fixture('pharm_priority');r['parameters']['generation_options']['condition_modalities']=['shape'];self.reject(r)
    def test_individual_pharmacophore_fields_use_native_canonical_names(self):
        r=self.fixture();r['parameters']['generation_options']['condition_modalities']=['pharm_positions','pharm_type'];validate(r)
    def test_fixed_pharmacophores_cannot_carry_ignored_inpainting_release(self):
        r=self.fixture('pharm_full');r['parameters']['generation_options']['advanced_inpaint']={'stop_inpainting_at_time_x4':.5};self.reject(r)
    def test_scaffold_only_cannot_carry_ignored_surface_override(self):
        r=self.fixture('scaffold_only');r['parameters']['generation_options']['advanced_inpaint']={'inpaint_x3_pos':True};self.reject(r)
    def test_native_ESP_includes_shape_and_cannot_be_mislabeled_ESP_only(self):
        r=self.fixture();r['parameters']['generation_options']['condition_modalities']=['esp'];self.reject(r)
    def test_fixed_scaffold_cannot_secretly_release_bonds(self):
        r=self.fixture('scaffold_fixed');r['parameters']['generation_options']['advanced_inpaint']={'stop_inpainting_at_time_x1_bonds':.5};self.reject(r)
    def test_release_must_happen_before_early_sampler_finish(self):
        r=self.fixture('scaffold_release');r['parameters']['generation_options']['sampler']['early_stop_edm']=.5;self.reject(r)
    def test_release_scaffold_is_not_reported_as_fixed_branch(self):
        branches=branch_ids(self.fixture('scaffold_release')['parameters']);self.assertIn('scaffold_release',branches);self.assertNotIn('scaffold_fixed',branches)
    def test_native_composition_has_no_per_profile_priority_vector(self):
        r=self.fixture('profile_composition');g=r['parameters']['generation_options'];g['reference_conditions'][0]['pharm_mode']='pharm-priority';g['reference_conditions'][0]['pharm_selection']={'kind':'mask','values':[1,0,1,0],'min_ring_atoms':1};self.reject(r)
    def test_composition_cannot_ignore_exit_vector_selections(self):
        r=self.fixture('profile_composition');g=r['parameters']['generation_options'];s=g['reference_conditions'][0];s.update(scaffold_mode='inpaint',scaffold_atom_indices=[0,1],exit_vector_atom_indices=[1]);g['atom_condition_reference_id']=s['reference_id'];g['advanced_inpaint']={'inpaint_x1_bonds':True};self.reject(r)
    def test_negative_guidance_is_not_a_fixed_scaffold(self):
        r=self.fixture('profile_composition');g=r['parameters']['generation_options'];s=g['reference_conditions'][1];s.update(scaffold_mode='fixed',scaffold_atom_indices=[0]);g['atom_condition_reference_id']=s['reference_id'];self.reject(r)
    def test_composition_frame_cannot_be_ignored_without_atom_condition(self):
        r=self.fixture('profile_composition');r['parameters']['generation_options']['condition_frame']='auto';self.reject(r)
    def test_composition_cannot_claim_unsupported_second_order_flag(self):
        r=self.fixture('profile_composition');r['parameters']['generation_options']['sampler']['use_2nd_order_correction']=True;self.reject(r)
    def test_unconditional_control_carries_no_hidden_inpainting(self):
        r=self.fixture('unconditional_control');r['parameters']['generation_options']['advanced_inpaint']={'inpaint_x3_x':True};self.reject(r)
    def test_boolean_early_stop_is_not_one_step(self):
        with self.assertRaises(ValueError):completed_steps(True,400)
    def test_early_stop_integer_and_fraction_keep_native_distinct_semantics(self):
        self.assertEqual(completed_steps(1,400),1);self.assertEqual(completed_steps(1.0,400),400);self.assertEqual(completed_steps(-1,400),400)
    def test_per_sample_counts_cover_requested_denominator(self):
        r=self.fixture();r['parameters']['generation_options']['sizes']={'mode':'per_sample','atoms':[20],'pharms':[4]};self.reject(r)
    def test_count_range_endpoints_cannot_be_reversed(self):
        r=self.fixture('variable_counts');r['parameters']['generation_options']['sizes']['atoms']=[3,-2];self.reject(r)
    def test_evaluation_ALPHA_interpolation_domain_is_explicit(self):
        r=self.fixture();r['parameters']['surface_points']=1000;self.reject(r)
    def test_uncalibrated_constraint_threshold_requires_stated_basis(self):
        r=self.fixture();r['parameters']['generation_options']['constraint_qc']['threshold_basis']='';self.reject(r)
    def test_actual_molecular_pharmacophore_recovery_cannot_be_disabled(self):
        r=self.fixture();r['parameters']['generation_options']['constraint_qc']['require_actual_pharmacophore_recovery']=False;self.reject(r)
    def test_empty_reference_pharmacophores_are_not_silent_conditioning(self):
        r=self.fixture();r['parameters']['generation_options']['reference_conditions'][0]['expected_pharmacophore_count']=0;self.reject(r)
    def test_direct_constraint_auditor_cannot_import_scientific_stack_locally(self):
        from server.constraint_qc import ConstraintAuditor
        with self.assertRaises(RuntimeError):ConstraintAuditor({})
        self.assertFalse(any(x in sys.modules for x in ('numpy','rdkit','scipy','torch')))
    def test_direct_generation_cannot_bypass_server_guard(self):
        from server.generation import run_generation
        with self.assertRaises(RuntimeError):run_generation({},None,None,None,None,None,None,None,None,None,None,None)
        self.assertNotIn('torch',sys.modules)
    def test_native_method_signatures_cover_all_explicit_forwarded_settings(self):
        api=read(ROOT/'native_api_contract.json')['functions']
        common={'batch_size','N_x1','N_x4','condition_modalities','condition_center_of_mass','inpaint','scaffold_conditioning','pharmacophore_conditioning','num_steps','early_stop_edm','sigma_max','sigma_min','rho','use_stochastic','S_churn','S_noise','shepherd_pred','verbose'}
        for name in ('generate','generate_composition'):
            self.assertTrue(common<=set(api[name]['positional_arguments']+api[name]['keyword_only_arguments']))
        self.assertIn('pharmacophore_prioritization',api['generate']['positional_arguments']);self.assertNotIn('pharmacophore_prioritization',api['generate_composition']['keyword_only_arguments'])
    def test_every_advanced_option_exists_in_pinned_dataclass(self):
        from generation_contracts import BOOL_OPTIONS,STOP_OPTIONS,NOISE_OPTIONS
        # Metadata-only statement list generated from the author AST, without imports.
        metadata=read(ROOT/'native_api_contract.json')
        self.assertTrue(BOOL_OPTIONS|STOP_OPTIONS|NOISE_OPTIONS <= set(metadata['inpaint_dataclass_fields']))


class PointReportContracts(unittest.TestCase):
    def setUp(self):
        self.limits={'max_priority_distance_angstrom':.5,'min_direction_cosine':.8}
        self.row={'source_point_index':0,'source_type':0,'matched_actual_point_index':2,'distance_angstrom':.1,'direction_cosine':.9,'passed':True}
    def report(self,rows):return {'required':len(rows),'matched':len(rows),'passed':True,'points':rows}
    def test_reported_pass_does_not_override_distance(self):
        r={**self.row,'distance_angstrom':2};self.assertTrue(point_report_issues(self.report([r]),[0],self.limits,[0]))
    def test_reported_pass_does_not_override_direction(self):
        r={**self.row,'direction_cosine':0};self.assertTrue(point_report_issues(self.report([r]),[0],self.limits,[0]))
    def test_actual_point_cannot_satisfy_two_required_points(self):
        rows=[self.row,{**self.row,'source_point_index':1}];self.assertIn('actual_pharmacophore_reused_for_multiple_required_points',point_report_issues(self.report(rows),[0,1],self.limits,[0,0]))
    def test_boolean_actual_point_is_not_point_one(self):
        r={**self.row,'matched_actual_point_index':True};self.assertTrue(point_report_issues(self.report([r]),[0],self.limits,[0]))
    def test_missing_required_point_is_not_negative_evidence(self):
        self.assertTrue(point_report_issues({'required':1,'matched':0,'passed':False,'points':[]},[0],self.limits,[0]))
    def test_type_mismatch_is_not_accepted_by_proximity(self):
        r={**self.row,'source_type':3};self.assertIn('actual_point_type_changed',point_report_issues(self.report([r]),[0],self.limits,[0]))
