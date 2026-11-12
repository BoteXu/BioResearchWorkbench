"""Bounded native-output checks; source integrity is separate from scientific truth."""
import math

SUMMARY_ROLES={
 'cnmf_programs':{'program_usage','program_loadings','k_stability','donor_program_table','diagnostics'},
 'composition_sccoda':{'composition_effects','composition_credible','composition_diagnostics','observed_counts','diagnostics'},
 'cellrank_multiview':{'fate_probabilities','fate_identity','diagnostics'},
 'perturbation_baselines':{'baseline_predictions','baseline_identity','diagnostics'},
 'seurat_workflow':{'cell_metadata','embedding','unintegrated_baseline','diagnostics','backend_versions'},
 'harmony_integrate':{'cell_metadata','integrated_representation','unintegrated_baseline','diagnostics','backend_versions'},
 'seurat_transfer':{'annotation_scores','diagnostics','backend_versions'},
 'singler_annotate':{'annotation','annotation_scores','reference_coverage','diagnostics','backend_versions'},
 'hdwgcna_network':{'modules','module_eigengenes','soft_threshold','diagnostics','backend_versions'},
 'palantir_trajectory':{'pseudotime','fate_probabilities','diagnostics','backend_versions'},
 'scgen_predict':{'prediction_identity','latent_shift_table','training_history','diagnostics','backend_versions'},
 'multivi_integrate':{'integrated_representation','cell_metadata','training_history','diagnostics','backend_versions'},
 'totalvi_integrate':{'integrated_representation','cell_metadata','training_history','diagnostics','backend_versions'},
 'monocle3_trajectory':{'pseudotime','principal_graph','diagnostics','backend_versions'},
 'diablo_fit':{'factor_scores','factor_loadings','sample_metadata','diagnostics','backend_versions'},
 'snf_fusion':{'fused_similarity','cluster_assignments','diagnostics','backend_versions'},
 'msstats_compare':{'protein_differential','missingness','diagnostics','backend_versions'},
 'mixscape_classify':{'perturbation_classification','classification_by_unit','diagnostics','backend_versions'},
 'cellot_predict':{'prediction_identity','prediction_summary','diagnostics','backend_versions'},
 'destvi_deconvolution':{'celltype_proportions','celltype_state_identity','training_history','spatial_identity','diagnostics','backend_versions'},
 'cell2location_reference':{'reference_signatures','reference_signature_uncertainty','training_history','diagnostics','backend_versions'},
 'cell2location_map':{'celltype_abundance','abundance_uncertainty','training_history','spatial_identity','diagnostics','backend_versions'},
 'muscat_pseudobulk':{'singlecell_differential','population_eligibility','design_matrix','contrast_matrix','result_identity','diagnostics','backend_versions'},
 'banksy_domains':{'spatial_domains','spatial_representations','section_identity','diagnostics','backend_versions'},
 'progeny_activity':{'pathway_activity','pathway_coverage','sample_metadata','diagnostics','backend_versions'},
 'drug2cell_score':{'drug_scores','target_coverage','unit_activity','diagnostics','backend_versions'},
 'cellphonedb_per_unit':{'lr_means','lr_pvalues','stratum_eligibility','diagnostics','backend_versions'},
 'paste_pairwise':{'coupling_source_identity','coupling_target_identity','diagnostics','backend_versions'},
 'squidpy_section_statistics':{'spatial_autocorrelation','neighborhood_enrichment','neighborhood_counts','section_diagnostics','diagnostics','backend_versions'},
 'spark_spatial':{'spatial_differential','spatial_filter','section_qc','diagnostics','backend_versions'},
 'vep_offline':{'variant_consequences','diagnostics','backend_versions'},
 'ldsc_h2':{'heritability_estimates','native_ldsc_log','diagnostics','backend_versions'},
 'seurat_to_anndata':{'diagnostics','backend_versions'},
 'cinemaot_effects':{'effect_identity','control_identity','unit_effect_summary','pair_diagnostics','diagnostics','backend_versions'},
 'cellcap_programs':{'basal_representation','program_usage','program_relevance','program_gene_projection','training_history','diagnostics','backend_versions'},
 'diffdock_pose':{'molecular_qc','diagnostics','backend_versions','native_engine_versions'},
 'diffsbdd_generate':{'molecular_qc','diagnostics','backend_versions','native_engine_versions'},
 'rfdiffusion_backbone':{'backbone_qc','diagnostics','backend_versions','native_engine_versions'},
 'mace_singlepoint':{'potential_energies','diagnostics','backend_versions'},
 'biolord_attributes':{'attribute_representation','split_identity','prediction_identity','training_history','diagnostics','backend_versions'},
 'scvidr_predict':{'prediction_identity','heldout_identity','prediction_attrition','latent_shift_table','training_history','diagnostics','backend_versions'},
 'native_unit_profile_handoff':{'profile_metadata','profile_eligibility','crossflow_lineage','diagnostics','backend_versions'},
 'proteintalks_predict':{'phenotype_predictions','diagnostics','backend_versions'},
 'prescient_trajectories':{'trajectory_identity','trajectory_time','diagnostics','backend_versions'},
 'batchie_posterior':{'combination_predictions','diagnostics','backend_versions'},
 'causcell_counterfactual_fit':{'concept_mapping','prediction_identity','observed_source_identity','diagnostics','backend_versions'},
 'igv_scoped_report':{'genome_view_scope','diagnostics','backend_versions'},
 'spatialglue_integrate':{'integrated_representation','modality_representation','modality_attention','spatial_identity','training_diagnostics','diagnostics','backend_versions'},
 'nestedcv_glmnet':{'oof_predictions','validation_metrics','split_identity','fold_provenance','diagnostics','backend_versions'},
 'xcms_preprocess':{'feature_definitions','sample_axis_map','sample_metadata','run_qc','processing_history','diagnostics','backend_versions'},
 'baysor_segment':{'cell_segmentation_qc','native_parameters','diagnostics','backend_versions'},
 'smr_heidi':{'genetic_evidence','allele_qc','diagnostics','backend_versions'},
 'systema_evaluate':{'centroid_accuracy','perturbation_metrics','observed_centroids','predicted_centroids','reference_profile','diagnostics','backend_versions'},
}

def inspect_native(request,local,load,rows):
    mode=request['backend'];p=request['parameters'];issues=[]
    if 'diagnostics' not in local:return issues
    d=load(local['diagnostics'])
    if not isinstance(d,dict):return ['native_diagnostics_not_object']
    if d.get('mode')!=mode:issues.append('native_diagnostic_backend_mismatch')
    versions=d.get('software_versions',d.get('versions'))
    if versions!=p['software_versions']:issues.append('native_software_version_binding_mismatch')
    if mode in {'diffdock_pose','diffsbdd_generate','rfdiffusion_backbone'} and 'native_engine_versions' in local:
        native=load(local['native_engine_versions'])
        if native.get('mode')!=mode or native.get('actual_package_versions')!=p['native_software_versions']:issues.append('native_child_software_version_binding_mismatch')
    if mode=='xcms_preprocess' and (d.get('sample_identity_bound') is not True or d.get('missing_values_preserved') is not True):issues.append('native_peak_identity_or_missingness_not_preserved')
    if mode=='baysor_segment' and (d.get('source_molecule_identity_preserved') is not True or d.get('counts_equal_molecule_assignments') is not True):issues.append('native_segmentation_identity_or_count_consistency_failed')
    for backend,fields in {'native_unit_profile_handoff':['source_receipt_bound'],'proteintalks_predict':['literal_checkpoint_channels_preserved'],'causcell_counterfactual_fit':['feature_axes_preserved','concept_mapping_stable'],'prescient_trajectories':['initial_identity_preserved','time_calibration_preserved'],'spatialglue_integrate':['matched_identity_and_coordinates'],'mace_singlepoint':['source_coordinates_unchanged']}.items():
        if mode==backend:
            for field in fields:
                if d.get(field) is not True:issues.append('native_required_binding_failed_or_missing:'+field)
    if mode=='batchie_posterior' and d.get('mcmc_qc_pass') is not True:issues.append('batchie_posterior_diagnostics_failed_or_unassessed')
    if mode=='composition_sccoda' and d.get('mcmc_qc_pass') is not True:issues.append('composition_chain_diagnostics_failed_or_missing')
    if mode in {'multivi_integrate','totalvi_integrate'} and d.get('observed_counts_unchanged') is not True:issues.append('observed_modality_count_preservation_failed_or_missing')
    if mode=='monocle3_trajectory' and d.get('finite_pseudotime_fraction')!=1:issues.append('unreachable_monocle3_cells')
    if mode=='seurat_to_anndata' and (d.get('literal_cell_gene_axes_preserved') is not True or d.get('counts_and_expression_readback_equal') is not True):issues.append('observed_layer_exchange_identity_failed_or_missing')
    for role in ['pseudotime','fate_probabilities','celltype_proportions','modality_attention','integrated_representation','program_usage','cluster_assignments','annotation','protein_differential']:
        if role not in local:continue
        paths=local.get('_by_role',{}).get(role,[local[role]])
        for selected_path in paths:
            header,data=rows(selected_path)
            if not data:issues.append('empty_native_table:'+role);continue
            identity='cell_id' if 'cell_id' in header else header[0]
            ids=[r.get(identity) for r in data]
            if role!='protein_differential' and (any(not v for v in ids) or len(ids)!=len(set(ids))):issues.append('duplicate_or_missing_native_identity:'+role)
            if role=='pseudotime':
                for r in data:
                    try:ok=math.isfinite(float(r['pseudotime'])) and float(r['pseudotime'])>=0
                    except (ValueError,KeyError):ok=False
                    if not ok:issues.append('invalid_native_pseudotime');break
            if role in {'fate_probabilities','celltype_proportions','modality_attention'}:
                for r in data:
                    try:
                        values=[float(r[k]) for k in header if k!=identity]
                        ok=bool(values) and all(math.isfinite(v) and 0<=v<=1 for v in values) and abs(sum(values)-1)<=1e-6
                    except ValueError:ok=False
                    if not ok:issues.append('invalid_native_fate_probabilities');break
            if role=='protein_differential':
                if not {'log2FC','pvalue','adj.pvalue'}<=set(header):issues.append('protein_result_schema_missing')
                for r in data:
                    for key in ['pvalue','adj.pvalue']:
                        if r.get(key) in {'NA','NaN','',None}:continue # retained untestable results are not zero/non-significant
                        try:ok=math.isfinite(float(r[key])) and 0<=float(r[key])<=1
                        except ValueError:ok=False
                        if not ok:issues.append('invalid_protein_test_probability')
    if mode=='diablo_fit':
        selected=set(local.get('_by_path',{}))
        for v in p['view_ids']:
            for prefix in ['diablo_variates_','diablo_loadings_']:
                if prefix+v+'.tsv' not in selected:issues.append('native_view_output_not_selected:'+prefix+v)
    return issues
