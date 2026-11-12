"""Fixed private native routes; importing contracts initializes no engine."""
import math
import re

SOURCES={
 'magpie':('Core-Bioinformatics/magpie','51bf32f999ff30e7fff7d12bd3cb0f33b9d2acc1'),
 'prnet':('Perturbation-Response-Prediction/PRnet','f19174bde3ed2633f54c7831799cc38c4ffc7a0d'),
 'scdiffusion':('EperLuo/scDiffusion','e20ee19090739a874fd8ae001d8337e4d480e52b'),
 'squidiff':('siyuh/Squidiff','abdfc27d84947dcccd745d1067c0840a41d32eb8'),
 'cellnavi':('DLS5-Omics/CellNavi','ea1660fc3057c63ecd849d506f24241bdc4b3f33'),
 'stack':('ArcInstitute/stack','cacc2e4b09435c3e536d46237d10b50f222dd144'),
 'morphdiff':('biomap-research/MorphDiff','80f79ca30a269599b7b10caa0c86fa9739496b0e'),
 'gnps':('mwang87/GNPS_Workflows','af4bd66d4faf00da8faa6f3dd6c7d023d39ff438'),
}
ROUTES={
 'magpie_coregister':dict(tool='MAGPIE',source='magpie',inputs=['context','license_evidence','registration_inputs','landmark_validation'],params=['cores','registration_scope'],roles=['registration_outputs','registration_validation'],kind='registered_measured_MSI'),
 'diann_quantify':dict(tool='DIA-NN Academia',inputs=['context','license_evidence','run_manifest','spectral_library'],params=['executable','executable_sha256','raw_input_ids','qvalue','mass_accuracy_ms1_ppm','mass_accuracy_ms2_ppm','scan_window','threads','native_version'],roles=['quantification_report','run_qc'],kind='measured_DIA_intensity'),
 'sirius_formulas':dict(tool='SIRIUS',inputs=['context','spectra','spectrum_identity'],params=['executable','executable_sha256','native_version','instrument','ppm_ms1','ppm_ms2','formula_candidates'],roles=['formula_candidates','spectrum_qc'],kind='computed_formula_candidates'),
 'csi_result_import':dict(tool='CSI:FingerID',inputs=['context','structure_results','spectrum_identity','native_result_receipt','spectra'],params=['result_columns'],roles=['structure_candidates','spectrum_qc'],kind='imported_author_computed_structure_candidates'),
 'gnps_offline_network':dict(tool='GNPS legacy alignment',source='gnps',inputs=['context','license_evidence','spectra','spectrum_identity'],params=['fragment_tolerance_da','minimum_matched_peaks','cosine_cutoff','top_k','maximum_spectra'],roles=['spectral_edges','spectral_nodes','spectrum_qc'],kind='spectral_similarity_not_structure_identification'),
 'dockovalent':dict(tool='DOCKovalent 3.7',inputs=['context','license_evidence','dock_inputs','reaction_mapping','receptor'],params=['executable','executable_sha256','native_version','prepared_input_ids','native_score_columns','pose_glob','score_file','bond_distance_angstrom'],roles=['docking_scores','covalent_geometry','ligand_coverage','pose_files'],kind='predicted_covalent_pose_not_affinity_or_reactivity'),
 'prnet_predict':dict(tool='PRnet',source='prnet',inputs=['context','license_evidence','model_manifest','checkpoint','features','query_expression','condition_embeddings','query_metadata'],params=['architecture','batch_size','maximum_cases','accelerator','gaussian_sampling'],roles=['prediction_matrix','prediction_mean','prediction_sd','prediction_identity'],kind='model_predicted_expression'),
 'scdiffusion_generate':dict(tool='scDiffusion',source='scdiffusion',inputs=['context','license_evidence','model_manifest','checkpoint','autoencoder_checkpoint','features'],params=['diffusion_config','n_samples','batch_size','latent_dim','accelerator','sampling_method','clip_denoised','guidance'],roles=['prediction_matrix','latent_representation','prediction_identity'],kind='generated_expression_not_perturbation_effect'),
 'squidiff_predict':dict(tool='Squidiff',source='squidiff',inputs=['context','license_evidence','model_manifest','checkpoint','features','query_expression','query_metadata','latent_direction'],params=['diffusion_config','direction_scale','batch_size','maximum_cases','accelerator','clip_denoised'],roles=['prediction_matrix','latent_representation','prediction_identity'],kind='model_predicted_expression_assumed_direction'),
 'cellnavi_drivers':dict(tool='CellNavi',source='cellnavi',inputs=['context','license_evidence','model_manifest','checkpoint','query_object','gene_vocabulary','adjacency','distance_graph','class_order'],params=['maximum_cases','accelerator','top_k'],roles=['driver_logits','driver_ranking','prediction_identity'],kind='model_driver_ranking_not_expression_or_causality'),
 'stack_incontext':dict(tool='Stack',source='stack',inputs=['context','license_evidence','model_manifest','checkpoint','features','context_object','query_object'],params=['batch_size','maximum_cases','accelerator','mask_rate','prompt_ratio','context_ratio'],roles=['prediction_matrix','prediction_identity'],kind='incontext_model_prediction_not_independent_validation'),
 'morphdiff_gene2image':dict(tool='MorphDiff',source='morphdiff',inputs=['context','license_evidence','model_manifest','checkpoint','model_config','gene_condition','query_metadata'],params=['batch_size','maximum_cases','accelerator','steps','guidance_scale','eta','image_height','image_width'],roles=['predicted_images','prediction_identity','channel_summary'],kind='generated_morphology_not_observed_image'),
 'morphdiff_image2image':dict(tool='MorphDiff',source='morphdiff',inputs=['context','license_evidence','model_manifest','checkpoint','model_config','gene_condition','query_metadata','source_images'],params=['batch_size','maximum_cases','accelerator','steps','guidance_scale','eta','image_height','image_width','strength'],roles=['predicted_images','prediction_identity','channel_summary'],kind='generated_morphology_conditioned_on_observed_image'),
}
COMMON_ROLES=['primary_results','qc_metrics','diagnostics','backend_versions','result_channel_proof']
QUALITY_METRICS={
 'magpie_coregister':{'heldout_TRE_mean_pixels','maximum_mixed_orientation_fraction'},
 'diann_quantify':{'runs_with_results_fraction','missing_quantity_fraction'},
 'sirius_formulas':{'returned_feature_fraction'},'csi_result_import':{'returned_feature_fraction'},
 'gnps_offline_network':{'isolated_spectra','selected_edges'},
 'dockovalent':{'ligands_with_pose_fraction','poses_outside_declared_distance'},
 'prnet_predict':{'minimum_predictive_sd'},'scdiffusion_generate':{'negative_decoded_fraction'},
 'squidiff_predict':{'training_unit_overlap'},'cellnavi_drivers':{'literal_vocabulary_coverage'},
 'stack_incontext':{'unit_overlap'},
 'morphdiff_gene2image':{'fraction_at_display_bounds'},'morphdiff_image2image':{'fraction_at_display_bounds'},
}
PACKAGES={
 'magpie_coregister':['snakemake','numpy','pandas','scikit-image','scipy','h5py','scanpy'],
 'diann_quantify':['numpy','pandas','pyarrow'], 'sirius_formulas':['pandas'],
 'csi_result_import':['pandas'], 'gnps_offline_network':['pandas'],
 'dockovalent':['numpy','pandas'],
 'prnet_predict':['torch','numpy','pandas','anndata','scanpy','scipy'],
 'scdiffusion_generate':['torch','numpy','pandas','scipy'],
 'squidiff_predict':['torch','numpy','pandas','scipy'],
 'cellnavi_drivers':['torch','numpy','pandas','scipy','anndata','scanpy','lmdb'],
 'stack_incontext':['torch','numpy','pandas','scipy','anndata'],
 'morphdiff_gene2image':['torch','numpy','pandas','omegaconf','pytorch-lightning'],
 'morphdiff_image2image':['torch','numpy','pandas','omegaconf','pytorch-lightning'],
}

def number(v,key,lo=0,hi=None,inclusive=False):
    if type(v) not in (int,float) or not math.isfinite(v) or (v<lo if inclusive else v<=lo) or hi is not None and v>hi:raise ValueError('Invalid finite native parameter: '+key)

def validate(mode,p,ids=None):
    if mode not in ROUTES:raise ValueError('Unknown completion route')
    r=ROUTES[mode]
    allowed=set(r['params'])|{'seed','software_versions','maximum_output_entries'}|({'repository'} if 'source' in r else set())|({'guidance_start_step'} if mode=='scdiffusion_generate' else set())
    if set(p)-allowed:raise ValueError('Unconsumed native parameters are forbidden: '+','.join(sorted(set(p)-allowed)))
    for key in r['params']+['seed','software_versions','maximum_output_entries']:
        if key not in p:raise ValueError('Missing explicit native parameter: '+key)
    if type(p['seed']) is not int or not 0<=p['seed']<2**32:raise ValueError('Explicit integer seed required')
    if type(p['maximum_output_entries']) is not int or p['maximum_output_entries']<1:raise ValueError('Positive server output bound required')
    if not isinstance(p['software_versions'],dict) or not p['software_versions'] or any(not isinstance(k,str) or not isinstance(v,str) or not v for k,v in p['software_versions'].items()):raise ValueError('Pin existing server dependencies')
    if not set(PACKAGES[mode])<=set(p['software_versions']):raise ValueError('Pin every required native scientific dependency')
    required=list(r['inputs'])
    if mode=='scdiffusion_generate':
        guidance=p['guidance']
        if not isinstance(guidance,list) or len(guidance)>2:raise ValueError('Explicit empty, single or two-classifier guidance list required')
        for g in guidance:
            if not isinstance(g,dict) or set(g)!={'input_id','config','target_class','class_label','scale'} or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,99}',str(g['input_id'])) or type(g['target_class']) is not int or g['target_class']<0 or not isinstance(g['class_label'],str) or not g['class_label']:raise ValueError('Exact classifier artifact, architecture and native class identity required')
            number(g['scale'],'classifier guidance scale');required.append(g['input_id'])
        if len(required)!=len(set(required)):raise ValueError('Distinct classifier/checkpoint input roles required')
        if guidance and p['sampling_method']=='ddpm':
            if type(p.get('guidance_start_step')) is not int or not 0<p['guidance_start_step']<=p['diffusion_config'].get('diffusion_steps',0):raise ValueError('Explicit DDPM classifier-guidance start step required')
        elif 'guidance_start_step' in p:raise ValueError('An unused guidance-start parameter must not be ignored')
    for key in ['raw_input_ids','prepared_input_ids']:
        if key not in p:continue
        x=p[key]
        if not isinstance(x,list) or not x or len(set(x))!=len(x) or any(not isinstance(v,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,99}',v) for v in x):raise ValueError('Unique literal native input roles required')
        required+=x
    if ids is not None and not set(required)<=set(ids):raise ValueError('Missing native scientific inputs')
    if 'source' in r and not isinstance(p.get('repository'),str):raise ValueError('Existing owned source-locked repository required')
    for key in ['repository','executable','native_version']:
        if key in p and (not isinstance(p[key],str) or not p[key]):raise ValueError('Explicit nonempty native identity required: '+key)
    if 'executable_sha256' in p and not re.fullmatch('[a-f0-9]{64}',str(p['executable_sha256'])):raise ValueError('Reviewed native executable hash required')
    for key in ['batch_size','maximum_cases','n_samples','latent_dim','steps','image_height','image_width','cores','threads','top_k','maximum_spectra','minimum_matched_peaks','formula_candidates']:
        if key in p and (type(p[key]) is not int or p[key]<1):raise ValueError('Positive integer required: '+key)
    for key in ['ppm_ms1','ppm_ms2','fragment_tolerance_da','mass_accuracy_ms1_ppm','mass_accuracy_ms2_ppm','scan_window','guidance_scale']:
        if key in p:number(p[key],key)
    for key in ['qvalue','cosine_cutoff','mask_rate','prompt_ratio','context_ratio']:
        if key in p:number(p[key],key,0,1)
    for key in ['eta','strength']:
        if key in p:number(p[key],key,0,1,True)
    if 'direction_scale' in p:number(p['direction_scale'],'direction_scale',0,None,True)
    if 'accelerator' in p and p['accelerator'] not in {'cpu','gpu'}:raise ValueError('Explicit existing accelerator required')
    if mode.startswith('morphdiff') and p['accelerator']!='gpu':raise ValueError('Pinned MorphDiff DDIM register_buffer forces CUDA; this adapter requires an existing server GPU')
    for key in ['gaussian_sampling','clip_denoised']:
        if key in p and type(p[key]) is not bool:raise ValueError('Explicit boolean required: '+key)
    if mode=='scdiffusion_generate' and p['sampling_method'] not in {'ddpm','ddim'}:raise ValueError('Select native DDPM or DDIM sampler')
    if mode=='sirius_formulas' and p['instrument'] not in {'qtof','orbitrap'}:raise ValueError('Explicit native instrument profile required')
    if mode=='diann_quantify' and 'Academia' not in p['native_version']:raise ValueError('Commercial Enterprise edition is excluded')
    if mode=='dockovalent':
        if not p['native_version'].startswith('DOCK 3.7'):raise ValueError('Reviewed DOCKovalent 3.7 engine required')
        x=p['bond_distance_angstrom']
        if not isinstance(x,list) or len(x)!=2:raise ValueError('Reaction-specific distance range required')
        number(x[0],'minimum bond distance');number(x[1],'maximum bond distance',x[0])
        for key in ['pose_glob','score_file']:
            if not isinstance(p[key],str) or not re.fullmatch('[A-Za-z0-9_./*-]+',p[key]) or '..' in p[key] or p[key].startswith('/'):raise ValueError('Scoped fresh native output path required')
    if mode.startswith('morphdiff') and (p['image_height']%4 or p['image_width']%4):raise ValueError('Pinned MorphDiff five-channel model has factor-four latent grid')
    return {'required_inputs':required,'required_roles':COMMON_ROLES+r['roles'],'kind':r['kind']}
