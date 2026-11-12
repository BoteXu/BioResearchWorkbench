"""Adversarial metadata and bounded-return tests, never scientific engine tests."""
from pathlib import Path
import unittest,json,copy,math,tempfile,sys,ast
from server.native_teaching_contracts import PACKAGES,validate,check_split
from native_acceptance import SUMMARY_ROLES,inspect_native
HERE=Path(__file__).parent

def parameters(mode):
    p={'software_versions':{k:'1.4.0' for k in PACKAGES[mode]},'seed':42}
    p.update({
     'palantir_trajectory':dict(terminal_cells={'A':'cell2','B':'cell3'},representation_kind='unintegrated_pca',direction_evidence='metadata fixture only'),
     'scgen_predict':dict(representation='log_normalized_expression',control='C',treatment='T',holdout_axis='unit',accelerator='cpu',early_stopping=True),
     'multivi_integrate':dict(observation_scope='fully_paired_observed_modalities',accelerator='cpu',modalities={'rna_layer':'rna','atac_layer':'atac'},layers={'rna_layer':'counts','atac_layer':'counts'}),
     'totalvi_integrate':dict(observation_scope='fully_paired_observed_modalities',accelerator='cpu',modalities={'rna_layer':'rna','protein_layer':'adt'},layers={'rna_layer':'counts','protein_layer':'counts'}),
     'hdwgcna_network':dict(selected_by_de=False),
     'diablo_fit':dict(view_ids=['rna','protein'],standardize=True,parameter_selection='prespecified_external_to_this_cohort'),
     'snf_fusion':dict(view_ids=['rna','protein'],standardize=True),
     'msstats_compare':dict(mb_impute=False),
     'monocle3_trajectory':dict(root_cells=['cell1'],direction_evidence='metadata fixture',close_loop=False),
     'mixscape_classify':dict(expression_scale='log1p_normalized',scale_signature=True,perturbation_type='KO'),
     'cellot_predict':dict(holdout_axis='unit',representation='author_model_feature_space',control='C',treatment='T'),
     'destvi_deconvolution':dict(accelerator='cpu'),
     'cell2location_reference':dict(accelerator='cpu'),
     'cell2location_map':dict(accelerator='cpu',cells_per_location=8,prior_basis='metadata fixture'),
     'muscat_pseudobulk':dict(paired=False,gene_filter='genes',celltype_universe=['A','B']),
     'banksy_domains':dict(algorithm='leiden',use_agf=False,standardize=True,**{'lambda':.2},k_geom=[15]),
     'progeny_activity':dict(organism='Human',scale_scores=False),
     'drug2cell_score':dict(method='mean'),
     'cellphonedb_per_unit':dict(species='Homo sapiens',gene_identifier_type='hgnc_symbol'),
     'paste_pairwise':dict(dissimilarity='kl',normalize_distances=False,align_coordinates=False),
     'squidpy_section_statistics':dict(distance_intervals=[0,10,20],nhood_normalization='none',two_tailed=True),
     'vep_offline':dict(vep_executable_sha256='1'*64,assembly='FIXTURE',species='homo_sapiens'),
     'ldsc_h2':dict(ldsc_script_sha256='1'*64,assembly='FIXTURE',ancestry='FIXTURE',heritability_scale='observed'),
     'seurat_to_anndata':dict(r_software_versions={k:'FIXTURE' for k in ['Seurat','Matrix','jsonlite']},metadata_keys=['unit','sample','condition'],categorical_keys=['condition'],reduction_names=['pca'],normalization_scale='log1p_normalized'),
     'cinemaot_effects':dict(expression_scale='log1p_normalized',representation_kind='unintegrated_pca',causal_assumptions='metadata fixture only',control='C',treatments=['T']),
     'cellcap_programs':dict(validation_scope='descriptive_fit_optimizer_cell_split_only',use_gpu=False,early_stopping=True,target_order=['T'],control='C',n_programs=3,n_heads=2,minimum_units=2,optimization_train_fraction=.9),
     'diffdock_pose':dict(accelerator='cpu',model_loading_scope='existing_reviewed_trusted_artifacts_only'),
     'diffsbdd_generate':dict(accelerator='cpu',model_loading_scope='existing_reviewed_trusted_artifacts_only',pocket_residues=['A:1','A:2']),
     'rfdiffusion_backbone':dict(accelerator='cpu',model_loading_scope='existing_reviewed_trusted_artifacts_only',design_scope='unconditional_fixed_length_backbone'),
     'mace_singlepoint':dict(accelerator='cpu',model_loading_scope='existing_reviewed_trusted_artifacts_only',dtype='float64',model_energy_unit='eV',model_length_unit='angstrom',supported_elements=['H','C','N','O']),
     'biolord_attributes':dict(expression_scale='log_normalized_expression',early_stopping=True,optimization_train_fraction=.9,categorical_attributes=['condition','celltype'],ordered_attributes=[],prediction_attributes=['condition'],unit_key='unit',accelerator='cpu',validation_scope='descriptive_attribute_fit_optimizer_cell_split_only'),
     'scvidr_predict':dict(expression_scale='log_normalized_expression',early_stopping=True,optimization_train_fraction=.9,regression=True,use_gpu=False,holdout_scope='celltype_treated_response_only_controls_in_training',control='C',treatment='T'),
     'native_unit_profile_handoff':dict(unit_key='unit',scenario_columns=['celltype','model_target_condition'],selected_scenarios={},celltype_key='celltype',aggregation_scope='within_unit_and_celltype',data_kind='model_decoded_expression',minimum_cells_per_profile=10,maximum_cells=10000),
     'proteintalks_predict':dict(accelerator='cpu',phenotype_definition='FIXTURE_BINARY_LABEL_ONLY',expression_scale='FIXTURE_SCALE',maximum_cases=20),
     'prescient_trajectories':dict(accelerator='cpu',representation_kind='checkpoint_training_metric_space',model_time_unit='normalized_training_time',initial_cells=['C1','C2'],n_simulations=2,n_steps=5,maximum_trajectory_entries=1000,dt=.1,noise_sd=.1),
     'batchie_posterior':dict(n_chains=2,posterior_draws=20,burnin=20,thin=1,maximum_experiments=100,maximum_prediction_entries=10000,minimum_units=2,dose_unit='micromolar',control_treatment_name='control',maximum_rhat=1.01,minimum_ess=400),
     'causcell_counterfactual_fit':dict(concepts=['A','B'],causal_dag=[[0,0,0],[1,0,0],[0,0,0]],interventions=[dict(concept='A',reference='control',target='treated')],accelerator='gpu',validation_scope='descriptive_fit_assumed_dag_no_predictive_validation',expression_scale='log_normalized_expression',profile_size=100,training_steps=10,checkpoint_every=5,diffusion_steps=20,minimum_source_cells=10,minimum_units=2),
     'igv_scoped_report':dict(asset_scope='existing_reviewed_offline_template',assembly='FIXTURE',maximum_sites=20,maximum_variant_length=100,maximum_reads_per_site=1000,flank_bp=100,initial_window_bp=41,exclude_flags=1536),
     'spatialglue_integrate':dict(datatype='SPOTS',accelerator='cpu',coordinate_unit='micron',max_epochs=600,weight_factors=[1,5,1,1]),
     'nestedcv_glmnet':dict(task='binary_classification',class_order=['control','case'],positive_class='case'),
     'xcms_preprocess':dict(raw_input_ids=['raw1','raw2'],acquisition_mode='centroid',polarity='positive',fill_peaks=False,feature_definition_roles=['study'],peak_width_seconds=[5,30],prefilter=[3,100]),
     'baysor_segment':dict(implementation='Baysor_CPP',dimensions=2,coordinate_unit='micron',cluster_method='mrf',baysor_executable_sha256='1'*64,baysor_version_output='FIXTURE',prior_confidence=.2),
     'smr_heidi':dict(smr_executable_sha256='1'*64,heidi_method=1,assembly='FIXTURE',ancestry='FIXTURE',maf=.01,frequency_difference=.2,maximum_frequency_exclusion_fraction=.05,instrument_pvalue=5e-8,heidi_instrument_pvalue=.00157,ld_lower=.05,ld_upper=.9,smr_result_pvalue=.001,heidi_result_pvalue=.01,heidi_minimum_snps=3,heidi_maximum_snps=20),
     'systema_evaluate':dict(holdout_axis='unit',analysis_scale='FIXTURE_ONLY'),
    }.get(mode,{}))
    if mode=='squidpy_section_statistics':p['software_versions']['squidpy']='1.8.4'
    if mode=='scvidr_predict':p['software_versions']['scvi-tools']='0.12.2'
    if mode in {'diffdock_pose','diffsbdd_generate','rfdiffusion_backbone'}:
        names={'torch','numpy'}|({'fair-esm','torch-geometric','PyYAML'} if mode=='diffdock_pose' else {'pytorch-lightning','rdkit'} if mode=='diffsbdd_generate' else {'hydra-core','omegaconf'})
        p['native_software_versions']={k:'FIXTURE_ONLY_NOT_INSTALLED' for k in names}
    return p

class NativeChecks(unittest.TestCase):
    def test_all_new_native_routes_have_profiles_dispatch_and_return_inspection(self):
        profiles=json.loads((HERE/'profiles.json').read_text(encoding='utf8'));source=(HERE/'server/runtime.py').read_text(encoding='utf8')
        self.assertEqual(len(PACKAGES),49)
        for mode in PACKAGES:
            with self.subTest(mode=mode):
                self.assertIn(mode,profiles['backends']);self.assertIn(repr(mode),source);self.assertIn(mode,SUMMARY_ROLES)
                self.assertEqual(profiles['backends'][mode]['runtime_status'],'NOT_RUN_THIS_UPGRADE');self.assertFalse(profiles['backends'][mode]['local_execution'])
    def test_every_registered_native_parameter_contract_accepts_metadata_only_fixture(self):
        for mode in PACKAGES:
            with self.subTest(mode=mode):self.assertTrue(validate(mode,parameters(mode)))
    def test_missing_required_package_pin_rejected_before_import(self):
        for mode in PACKAGES:
            p=parameters(mode);p['software_versions'].pop(PACKAGES[mode][0])
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate(mode,p)
    def test_parameter_nonfinite_budget_rejected(self):
        for value in [float('nan'),float('inf'),True,-1]:
            p=parameters('palantir_trajectory');p['max_epochs']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate('palantir_trajectory',p)
    def test_modality_alias_cannot_replace_two_measured_channels(self):
        p=parameters('multivi_integrate');p['modalities']['atac_layer']='rna'
        with self.assertRaises(ValueError):validate('multivi_integrate',p)
    def test_old_multivi_api_not_silently_called(self):
        p=parameters('multivi_integrate');p['software_versions']['scvi-tools']='1.3.3'
        with self.assertRaises(ValueError):validate('multivi_integrate',p)
    def test_unpaired_multimodal_not_claimed_covered(self):
        p=parameters('totalvi_integrate');p['observation_scope']='fabricate_absent_modality_as_zero'
        with self.assertRaises(ValueError):validate('totalvi_integrate',p)
    def test_UMAP_not_used_as_palantir_metric_features(self):
        p=parameters('palantir_trajectory');p['representation_kind']='UMAP'
        with self.assertRaises(ValueError):validate('palantir_trajectory',p)
    def test_de_selected_network_gene_set_rejected(self):
        p=parameters('hdwgcna_network');p['selected_by_de']=True
        with self.assertRaises(ValueError):validate('hdwgcna_network',p)
    def test_imputed_unobserved_channel_not_a_species_mapping(self):
        p=parameters('cellphonedb_per_unit');p['species']='Mus musculus'
        with self.assertRaises(ValueError):validate('cellphonedb_per_unit',p)
    def test_unknown_celltype_does_not_become_measured_zero(self):
        p=parameters('muscat_pseudobulk');p['celltype_universe']=['A','A']
        with self.assertRaises(ValueError):validate('muscat_pseudobulk',p)
    def test_auto_sample_deletion_not_enabled_by_gene_filter(self):
        p=parameters('muscat_pseudobulk');p['gene_filter']='both'
        with self.assertRaises(ValueError):validate('muscat_pseudobulk',p)
    def test_spatial_harmonic_budget_is_explicit(self):
        p=parameters('banksy_domains');p['use_agf']=True
        with self.assertRaises(ValueError):validate('banksy_domains',p)
    def test_no_fake_abundance_prior(self):
        p=parameters('cell2location_map');p['prior_basis']=''
        with self.assertRaises(ValueError):validate('cell2location_map',p)
    def test_tuned_training_diablo_not_external_validation(self):
        p=parameters('diablo_fit');p['parameter_selection']='use_test_labels'
        with self.assertRaises(ValueError):validate('diablo_fit',p)
    def test_measured_view_cannot_overwrite_metadata(self):
        p=parameters('snf_fusion');p['view_ids']=['rna','metadata']
        with self.assertRaises(ValueError):validate('snf_fusion',p)
    def test_donor_holdout_leakage_rejected(self):
        train=[dict(cell_id='a',unit='D1',type='A',condition=c) for c in ['C','T']];train[1]['cell_id']='b';q=[dict(cell_id='c',unit='D1',type='A',condition='C')]
        with self.assertRaises(ValueError):check_split(train,q,'unit','type','condition','C','T','unit')
    def test_heldout_treated_celltype_cannot_enter_shift_training(self):
        train=[dict(cell_id='a',unit='D1',type='A',condition='C'),dict(cell_id='b',unit='D2',type='A',condition='T')];q=[dict(cell_id='c',unit='D3',type='A',condition='C')]
        with self.assertRaises(ValueError):check_split(train,q,'unit','type','condition','C','T','celltype')
    def test_disjoint_literal_donors_accepted_without_alias_merging(self):
        train=[dict(cell_id='a',unit='D1',type='A',condition='C'),dict(cell_id='b',unit='D2',type='A',condition='T')];q=[dict(cell_id='c',unit='D_1',type='A',condition='C')]
        self.assertTrue(check_split(train,q,'unit','type','condition','C','T','unit'))
    def test_missing_convergence_keeps_composition_on_hold(self):
        request={'backend':'composition_sccoda','parameters':{'software_versions':{}}}
        issues=inspect_native(request,{'diagnostics':'x'},lambda p:{'mode':'composition_sccoda','software_versions':{}},lambda p:([],[]))
        self.assertIn('composition_chain_diagnostics_failed_or_missing',issues)
    def test_changed_backend_diagnostics_rejected(self):
        p=parameters('seurat_workflow');r={'backend':'seurat_workflow','parameters':p}
        issues=inspect_native(r,{'diagnostics':'x'},lambda p:{'mode':'harmony_integrate','versions':{}},lambda p:([],[]))
        self.assertIn('native_diagnostic_backend_mismatch',issues);self.assertIn('native_software_version_binding_mismatch',issues)
    def test_numerically_invalid_fate_table_rejected(self):
        r={'backend':'palantir_trajectory','parameters':parameters('palantir_trajectory')};diag={'mode':r['backend'],'software_versions':r['parameters']['software_versions']}
        issues=inspect_native(r,{'diagnostics':'d','fate_probabilities':'p'},lambda p:diag,lambda p:(['cell_id','A','B'],[{'cell_id':'a','A':'.8','B':'.8'}]))
        self.assertIn('invalid_native_fate_probabilities',issues)
    def test_unreachable_pseudotime_not_replaced_by_zero(self):
        r={'backend':'monocle3_trajectory','parameters':parameters('monocle3_trajectory')};diag={'mode':r['backend'],'software_versions':r['parameters']['software_versions'],'finite_pseudotime_fraction':.9}
        issues=inspect_native(r,{'diagnostics':'d','pseudotime':'p'},lambda p:diag,lambda p:(['cell_id','pseudotime'],[{'cell_id':'a','pseudotime':'inf'}]))
        self.assertIn('unreachable_monocle3_cells',issues);self.assertIn('invalid_native_pseudotime',issues)
    def test_server_guard_rejects_local_computer_before_optional_imports(self):
        from server.runtime import guard
        with self.assertRaises(RuntimeError):guard({})
    def test_new_modules_import_no_analysis_libraries_at_module_load(self):
        for name in ['native_teaching_python.py','native_spatial_perturbation.py','native_gene_activity.py']:
            tree=ast.parse((HERE/'server'/name).read_text(encoding='utf8'));imports=[]
            for n in tree.body:
                if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
                elif isinstance(n,ast.ImportFrom):imports.append(n.module)
            self.assertFalse(set(imports)&{'numpy','pandas','anndata','torch','scvi','cell2location','cellot','drug2cell'})
    def shap_config(self):return dict(algorithm='permutation',output='probability',models=['ridge'],background_units=['D1','D2'],explain_units=['D3'],maximum_background_units=10,maximum_explain_units=10,max_evals=25,software_version='FIXTURE_NO_ENGINE',additivity_tolerance=1e-6)
    def test_shap_contract_is_available_without_importing_engine(self):
        from server.shap_native import contract
        self.assertTrue(contract(self.shap_config(),['D1','D2'],['D3'],['g1','g2']))
    def test_shap_background_cannot_use_heldout_results(self):
        from server.shap_native import contract
        p=self.shap_config();p['background_units']=['D3']
        with self.assertRaises(ValueError):contract(p,['D1','D2'],['D3'],['g1','g2'])
    def test_shap_approximation_budget_covers_feature_axis(self):
        from server.shap_native import contract
        p=self.shap_config();p['max_evals']=4
        with self.assertRaises(ValueError):contract(p,['D1','D2'],['D3'],['g1','g2'])
    def test_old_squidpy_rng_stream_not_silently_substituted(self):
        p=parameters('squidpy_section_statistics');p['software_versions']['squidpy']='1.8.3'
        with self.assertRaises(ValueError):validate('squidpy_section_statistics',p)
    def test_spatial_distance_intervals_must_be_ordered_and_finite(self):
        for edges in [[0,20,10],[0,float('nan'),20],[-1,0,20]]:
            p=parameters('squidpy_section_statistics');p['distance_intervals']=edges
            with self.subTest(edges=edges),self.assertRaises(ValueError):validate('squidpy_section_statistics',p)
    def fixture_project(self,mode):
        profiles=json.loads((HERE/'profiles.json').read_text(encoding='utf8'));spec=profiles['backends'][mode];p={k:'FIXTURE_ONLY' for k in spec['required_parameters']};p.update(parameters(mode))
        p.update(unit_key='unit',sample_key='sample',condition_key='condition',seed=42,n_components=3,knn=4,num_waypoints=10,max_iterations=5,n_pcs=3,hvg_count=20,neighbors=4,minimum_retained_cells=8,target_sum=10000,resolution=.5,cluster_algorithm=4,alpha=.5,n_eigs=None,scale_components=True)
        if mode=='snf_fusion':p.update(view_ids=['rna','protein'],sigma=.5,iterations=5,n_clusters=2,symmetry_tolerance=1e-8)
        ids=spec['required_inputs']+(p['view_ids'] if mode=='snf_fusion' else [])
        return {'backend':mode,'parameters':p,'public_upload':False,'server_execution_authorized':False,'inputs':[{'id':key,'path':key+'_NOT_A_REAL_DATASET','sha256':'1'*64} for key in ids],'upstream_qc':{'scope':'metadata-only handoff test; no scientific observations'},'statistical_plan':{k:'engineering fixture only' for k in ['estimand','independent_unit','missingness','multiplicity','sensitivity']},'acceptance_rules':[{'id':'fixture','role':'diagnostics','field':'mode','operator':'eq','bound':mode,'definition':'metadata-only backend name','unit':'string','threshold_basis':'engineering test; not scientific acceptance'}],'resource_budget':{'cpus':1,'gpus':0}}
    def test_native_R_python_and_multiview_handoffs_bind_real_source_without_execution(self):
        import workbench
        for mode in ['seurat_workflow','palantir_trajectory','snf_fusion']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as td:
                root=Path(td);src=root/'request.json';src.write_text(json.dumps(self.fixture_project(mode)),encoding='utf8');workbench.plan(src,root/'prepared')
                prepared=json.loads((root/'prepared/server_request.private.json').read_text(encoding='utf8'));self.assertFalse(prepared['server_execution_authorized']);self.assertIn('native_teaching_contracts.py',prepared['source_sha256']);self.assertTrue((root/'prepared/server/native_teaching_contracts.py').is_file())
                self.assertEqual(prepared['submission_state'],'not_submitted')
    def test_invalid_result_rule_cannot_survive_until_server_return(self):
        import workbench
        for change in [{'operator':'magic'},{'operator':'le','bound':float('nan')},{'role':'nonexistent_output'},{'field':''}]:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
                root=Path(td);p=self.fixture_project('seurat_workflow');p['acceptance_rules'][0].update(change);src=root/'request.json';src.write_text(json.dumps(p),encoding='utf8')
                with self.assertRaises(ValueError):workbench.plan(src,root/'prepared')
    def test_cellcap_optimizer_monitoring_is_not_donor_validation(self):
        p=parameters('cellcap_programs');p['validation_scope']='independent_donor_validation'
        with self.assertRaises(ValueError):validate('cellcap_programs',p)
    def test_cellcap_attention_dimension_must_match_heads(self):
        p=parameters('cellcap_programs');p['n_latent']=3
        with self.assertRaises(ValueError):validate('cellcap_programs',p)
    def test_cinemaot_control_cannot_be_a_treatment(self):
        p=parameters('cinemaot_effects');p['treatments']=['C']
        with self.assertRaises(ValueError):validate('cinemaot_effects',p)
    def test_systema_cellwise_split_not_reported_as_unit_holdout(self):
        p=parameters('systema_evaluate');p['holdout_axis']='cell'
        with self.assertRaises(ValueError):validate('systema_evaluate',p)

class NativeAdditionalBoundaryTests(unittest.TestCase):
    def test_child_model_environment_is_not_proved_by_qc_interpreter(self):
        p=parameters('diffdock_pose');p['native_software_versions'].pop('torch')
        with self.assertRaises(ValueError):validate('diffdock_pose',p)
    def test_mace_physical_units_cannot_use_arbitrary_conversion(self):
        p=parameters('mace_singlepoint');p['energy_units_to_ev']=27.211386245988
        with self.assertRaises(ValueError):validate('mace_singlepoint',p)
    def test_repeated_native_tables_all_checked_even_when_last_one_valid(self):
        mode='palantir_trajectory';p=parameters(mode);d={'mode':mode,'software_versions':p['software_versions']}
        def table(path):return (['cell_id','A','B'],[{'cell_id':'C','A':'.8' if path=='bad' else '.2','B':'.8'}])
        issues=inspect_native({'backend':mode,'parameters':p},{'diagnostics':'d','fate_probabilities':'good','_by_role':{'fate_probabilities':['bad','good']}},lambda _:d,table)
        self.assertIn('invalid_native_fate_probabilities',issues)
    def test_profile_handoff_rejects_collapsed_technical_field(self):
        p=parameters('native_unit_profile_handoff');p['scenario_columns']=['state']
        with self.assertRaises(ValueError):validate('native_unit_profile_handoff',p)
    def test_profile_handoff_is_not_implicitly_observed_counts(self):
        p=parameters('native_unit_profile_handoff');p['data_kind']='raw_counts'
        with self.assertRaises(ValueError):validate('native_unit_profile_handoff',p)
    def test_causcell_cyclic_assumptions_rejected_before_training(self):
        p=parameters('causcell_counterfactual_fit');p['causal_dag']=[[0,1,0],[1,0,0],[0,0,0]]
        with self.assertRaises(ValueError):validate('causcell_counterfactual_fit',p)
    def test_prescient_umap_not_substituted_for_training_coordinates(self):
        p=parameters('prescient_trajectories');p['representation_kind']='umap'
        with self.assertRaises(ValueError):validate('prescient_trajectories',p)
    def test_batchie_one_chain_cannot_establish_mcmc_acceptance(self):
        p=parameters('batchie_posterior');p['n_chains']=1
        with self.assertRaises(ValueError):validate('batchie_posterior',p)
    def test_batchie_missing_diagnostics_not_reported_as_pass(self):
        mode='batchie_posterior';p=parameters(mode);d={'mode':mode,'software_versions':p['software_versions']}
        issues=inspect_native({'backend':mode,'parameters':p},{'diagnostics':'d'},lambda _:d,lambda _:([],[]))
        self.assertIn('batchie_posterior_diagnostics_failed_or_unassessed',issues)
    def test_igv_no_implicit_public_asset_scope(self):
        p=parameters('igv_scoped_report');p['asset_scope']='download_cdn'
        with self.assertRaises(ValueError):validate('igv_scoped_report',p)
    def test_blank_ms_runs_cannot_define_native_features(self):
        p=parameters('xcms_preprocess');p['feature_definition_roles']=['study','blank']
        with self.assertRaises(ValueError):validate('xcms_preprocess',p)
    def test_mass_peak_width_is_explicitly_ordered_in_seconds(self):
        p=parameters('xcms_preprocess');p['peak_width_seconds']=[30,5]
        with self.assertRaises(ValueError):validate('xcms_preprocess',p)
    def test_baysor_old_implementation_not_misidentified_as_cpp(self):
        p=parameters('baysor_segment');p['implementation']='Baysor_Julia'
        with self.assertRaises(ValueError):validate('baysor_segment',p)
    def test_native_heidi_interval_cannot_be_reversed(self):
        p=parameters('smr_heidi');p['ld_lower']=.95
        with self.assertRaises(ValueError):validate('smr_heidi',p)
    def test_spatialglue_silent_author_override_is_rejected(self):
        p=parameters('spatialglue_integrate');p['max_epochs']=200
        with self.assertRaises(ValueError):validate('spatialglue_integrate',p)
    def test_nestedcv_positive_event_must_match_native_output(self):
        p=parameters('nestedcv_glmnet');p['positive_class']='control'
        with self.assertRaises(ValueError):validate('nestedcv_glmnet',p)
    def test_native_models_refuse_implicit_download_scope(self):
        for mode in ['diffdock_pose','diffsbdd_generate','mace_singlepoint','rfdiffusion_backbone']:
            p=parameters(mode);p['model_loading_scope']='download_latest'
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate(mode,p)
    def test_backbone_sampling_is_not_functional_protein_design(self):
        p=parameters('rfdiffusion_backbone');p['design_scope']='validated_binder'
        with self.assertRaises(ValueError):validate('rfdiffusion_backbone',p)
    def test_biolord_cannot_rewrite_original_independent_unit(self):
        p=parameters('biolord_attributes');p['categorical_attributes'].append('unit');p['prediction_attributes']=['unit']
        with self.assertRaises(ValueError):validate('biolord_attributes',p)
    def test_scvidr_response_holdout_is_not_donor_holdout(self):
        p=parameters('scvidr_predict');p['holdout_scope']='independent_donor'
        with self.assertRaises(ValueError):validate('scvidr_predict',p)

if __name__=='__main__':unittest.main(verbosity=2)
