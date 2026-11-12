"""Fail-closed contracts for additional native tools. Imports fit no data."""
import math,re

PACKAGES={
 'palantir_trajectory':['palantir','anndata','pandas','numpy'],
 'scgen_predict':['scgen','scvi-tools','anndata','torch'],
 'multivi_integrate':['scvi-tools','mudata','anndata','torch'],
 'totalvi_integrate':['scvi-tools','mudata','anndata','torch'],
 'seurat_workflow':['Seurat','jsonlite'], 'harmony_integrate':['Seurat','harmony','jsonlite'],
 'seurat_transfer':['Seurat','jsonlite'], 'singler_annotate':['SingleR','SummarizedExperiment','jsonlite'],
 'hdwgcna_network':['Seurat','hdWGCNA','WGCNA','jsonlite'],
 'monocle3_trajectory':['monocle3','SingleCellExperiment','igraph','jsonlite'],
 'diablo_fit':['mixOmics','jsonlite'], 'snf_fusion':['SNFtool','jsonlite'],
 'msstats_compare':['MSstats','jsonlite'],
 'mixscape_classify':['pertpy','anndata','scanpy'],
 'cellot_predict':['cellot','anndata','torch'],
 'destvi_deconvolution':['scvi-tools','anndata','torch'],
 'cell2location_reference':['cell2location','scvi-tools','anndata','torch'],
 'cell2location_map':['cell2location','scvi-tools','anndata','torch'],
 'muscat_pseudobulk':['muscat','edgeR','SingleCellExperiment','BiocParallel','jsonlite'],
 'banksy_domains':['Banksy','SpatialExperiment','SingleCellExperiment','jsonlite'],
 'progeny_activity':['progeny','jsonlite'],
 'drug2cell_score':['drug2cell','anndata','scanpy'],
 'cellphonedb_per_unit':['cellphonedb','anndata'],
 'paste_pairwise':['paste-bio','POT','anndata'],
 'squidpy_section_statistics':['squidpy','anndata'],
 'spark_spatial':['SPARK','jsonlite'],
 'vep_offline':['pysam','pandas','numpy'],
 'ldsc_h2':['pandas','numpy'],
 'seurat_to_anndata':['anndata','pandas','scipy','numpy'],
 'cinemaot_effects':['pertpy','anndata','numpy','pandas'],
 'cellcap_programs':['cellcap','scvi-tools','anndata','torch'],
 'systema_evaluate':['numpy','pandas','scipy'],
 'xcms_preprocess':['xcms','MsExperiment','Spectra','BiocParallel','jsonlite'],
 'baysor_segment':['pandas','numpy'],
 'smr_heidi':['pandas','numpy'],
 'spatialglue_integrate':['anndata','torch','numpy','pandas','scipy','scikit-learn'],
 'nestedcv_glmnet':['nestedcv','caret','glmnet','jsonlite'],
 'diffdock_pose':['rdkit','biopython','numpy','pandas'],
 'diffsbdd_generate':['rdkit','biopython','numpy','pandas'],
 'rfdiffusion_backbone':['biopython','numpy','pandas'],
 'mace_singlepoint':['mace-torch','ase','torch','numpy','pandas'],
 'biolord_attributes':['biolord','scvi-tools','anndata','torch','numpy','pandas'],
 'scvidr_predict':['scvi-tools','anndata','torch','numpy','pandas','scanpy'],
 'igv_scoped_report':['igv-reports','pysam','pandas'],
 'causcell_counterfactual_fit':['causcell','anndata','torch','numpy','pandas','scanpy'],
 'batchie_posterior':['batchie','numpy','pandas','arviz','h5py','xarray'],
 'prescient_trajectories':['prescient','anndata','numpy','pandas','torch'],
 'proteintalks_predict':['numpy','pandas','torch','torchdyn'],
 'native_unit_profile_handoff':['anndata','numpy','pandas','scipy'],
}

def validate(mode,p,verify_versions=False):
    if mode not in PACKAGES:raise ValueError('Unrecognized native route')
    versions=p.get('software_versions')
    if not isinstance(versions,dict) or any(not isinstance(versions.get(k),str) or not versions[k] for k in PACKAGES[mode]):raise ValueError('Pin every required package from the existing server environment')
    if type(p.get('seed')) is not int or not 0<=p['seed']<2**32:raise ValueError('Explicit admissible integer seed required')
    for k in ['n_components','knn','num_waypoints','max_iterations','max_epochs','batch_size','n_hidden','n_latent','n_layers','n_pcs','hvg_count','neighbors','minimum_retained_cells','target_metacells','metacell_k','minimum_cells','max_network_genes','max_block_size','minimum_module_size','minimum_reference_genes','n_neighbors','n_dims','min_de_genes','reference_max_epochs','vamp_prior_p','ncomp','iterations','n_clusters','minimal_branch_len','top_genes','minimum_model_genes','minimum_targets','n_bins','ctrl_size','minimum_cells_per_type','threads','maximum_coupling_entries','maximum_spots_per_section','minimum_spots','n_perms','maximum_variants','cache_version']:
        if k in p and (type(p[k]) is not int or p[k]<1):raise ValueError('Positive integer required: '+k)
    for k in ['dropout_rate','alpha','merge_cut_height','minimum_prediction_score','pvalue_cutoff','minimum_expression_fraction','maximum_island_fraction']:
        if k in p and (type(p[k]) not in (int,float) or not math.isfinite(p[k]) or not 0<=p[k]<=1):raise ValueError('Finite proportion required: '+k)
    for k in ['target_sum','resolution','selected_power','learning_rate','detection_alpha','sigma','symmetry_tolerance','marginal_tolerance','radius']:
        if k in p and (type(p[k]) not in (int,float) or not math.isfinite(p[k]) or p[k]<=0):raise ValueError('Positive finite value required: '+k)
    if 'cluster_algorithm' in p and (type(p['cluster_algorithm']) is not int or p['cluster_algorithm'] not in {1,2,3,4}):raise ValueError('Explicit native Seurat graph algorithm 1/2/3/4 required')
    for k in ['dimension','minimum_cells_per_arm','maximum_dense_expression_entries','maximum_coupling_entries']:
        if k in p and (type(p[k]) is not int or p[k]<1):raise ValueError('Positive explicit native dimension/data budget required: '+k)
    for k in ['effect_reconstruction_tolerance','smoothness','solver_tolerance','ard_weight','reconstruction_weight']:
        if k in p and (type(p[k]) not in (int,float) or not math.isfinite(p[k]) or p[k]<=0):raise ValueError('Positive finite native method setting required: '+k)
    for k in ['adversarial_weight','kl_weight']:
        if k in p and (type(p[k]) not in (int,float) or not math.isfinite(p[k]) or p[k]<0):raise ValueError('Finite nonnegative native loss weight required: '+k)
    if mode=='palantir_trajectory':
        if not isinstance(p.get('terminal_cells'),dict) or len(p['terminal_cells'])<2 or len(set(p['terminal_cells'].values()))!=len(p['terminal_cells']):raise ValueError('At least two uniquely named exact terminal-cell identities required')
        if p.get('representation_kind') not in {'unintegrated_pca','reviewed_integrated_latent'} or not p.get('direction_evidence'):raise ValueError('Reviewed metric representation and independent root/direction evidence required; no UMAP distance substitution')
        if 'scale_components' in p and type(p['scale_components']) is not bool:raise ValueError('Explicit diffusion component scaling decision required')
        if 'n_eigs' in p and p['n_eigs'] is not None and (type(p['n_eigs']) is not int or p['n_eigs']<1):raise ValueError('Positive fixed multiscale eigenvector count or explicit native automatic selection None required')
    if mode=='scgen_predict':
        if p.get('representation')!='log_normalized_expression' or p.get('control')==p.get('treatment'):raise ValueError('scGen needs explicitly log-normalized expression and distinct observed conditions')
        if p.get('holdout_axis') not in {'unit','celltype'}:raise ValueError('Explicit supported heldout-unit or heldout-celltype task required')
        if p.get('accelerator') not in {'cpu','gpu'}:raise ValueError('Explicit existing CPU or allocated GPU required')
        if type(p.get('early_stopping')) is not bool:raise ValueError('Explicit early-stopping decision required')
    if mode in {'multivi_integrate','totalvi_integrate'}:
        if p.get('observation_scope')!='fully_paired_observed_modalities':raise ValueError('This route supports real paired modalities only; unpaired MuData requires a separately reviewed missing-modality route')
        if p.get('accelerator') not in {'cpu','gpu'} or not isinstance(p.get('modalities'),dict):raise ValueError('Explicit modality roles and accelerator required')
        required={'rna_layer','atac_layer'} if mode=='multivi_integrate' else {'rna_layer','protein_layer'}
        if set(p['modalities'])!=required or len(set(p['modalities'].values()))!=len(required):raise ValueError('Distinct literal RNA/ATAC or RNA/protein modality roles required')
        if set(p.get('layers',{}))!=required or any(not isinstance(v,str) or not v for v in p['layers'].values()):raise ValueError('Explicit actual count layers for every observed modality required')
        m=re.match(r'^(\d+)\.(\d+)',versions['scvi-tools'])
        if not m or tuple(map(int,m.groups()))<(1,4):raise ValueError('Current MuData routes require the reviewed scvi-tools >=1.4 API')
    if mode=='hdwgcna_network' and p.get('selected_by_de') is not False:raise ValueError('Network genes must not be selected by the tested DE contrast')
    if mode in {'diablo_fit','snf_fusion'}:
        views=p.get('view_ids',[])
        if not isinstance(views,list) or len(views)<2 or len(set(views))!=len(views) or any(not isinstance(v,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',v) or v=='metadata' for v in views):raise ValueError('Unique safe exact measured view IDs required, distinct from the metadata input')
        if type(p.get('standardize')) is not bool:raise ValueError('Explicit standardization decision required')
    if mode=='diablo_fit' and p.get('parameter_selection')!='prespecified_external_to_this_cohort':raise ValueError('DIABLO fit route requires prespecified hyperparameters; it does not supply a nested-validation estimate')
    if mode=='msstats_compare' and type(p.get('mb_impute')) is not bool:raise ValueError('Explicit MSstats missing-intensity imputation decision required')
    if mode=='monocle3_trajectory' and (type(p.get('close_loop')) is not bool or not p.get('root_cells') or not p.get('direction_evidence')):raise ValueError('Monocle3 requires explicit roots, direction evidence and graph-loop choice')
    if mode=='cellot_predict' and (p.get('holdout_axis') not in {'unit','cell'} or p.get('representation')!='author_model_feature_space' or p.get('control')==p.get('treatment')):raise ValueError('Explicit supported CellOT control-to-target prediction task and heldout axis required')
    if mode=='mixscape_classify':
        if p.get('expression_scale')!='log1p_normalized' or type(p.get('scale_signature')) is not bool or p.get('perturbation_type') not in {'KO','KD','OE'}:raise ValueError('Explicit observed expression scale and supported perturbation semantics required')
    if mode in {'destvi_deconvolution','cell2location_reference','cell2location_map'}:
        if p.get('accelerator') not in {'cpu','gpu'}:raise ValueError('Explicit allocated server CPU/GPU required')
        if mode=='cell2location_map' and (type(p.get('cells_per_location')) not in (int,float) or not math.isfinite(p['cells_per_location']) or p['cells_per_location']<=0 or not p.get('prior_basis')):raise ValueError('Biologically justified positive abundance prior required')
    if mode=='muscat_pseudobulk' and (type(p.get('paired')) is not bool or p.get('gene_filter') not in {'genes','none'} or not isinstance(p.get('celltype_universe'),list) or not p['celltype_universe'] or len(set(p['celltype_universe']))!=len(p['celltype_universe'])):raise ValueError('Reviewed celltype universe, explicit pairing and gene-only/no filtering required; no automatic sample removal')
    if mode=='banksy_domains':
        if p.get('algorithm') not in {'leiden','louvain'} or type(p.get('use_agf')) is not bool or type(p.get('standardize')) is not bool or type(p.get('lambda')) not in (int,float) or not math.isfinite(p['lambda']) or not 0<p['lambda']<1:raise ValueError('Explicit native BANKSY algorithm, AGF and nonzero bounded spatial weighting required')
        if not isinstance(p.get('k_geom'),list) or len(p['k_geom'])!=(2 if p['use_agf'] else 1) or any(type(k) is not int or k<2 for k in p['k_geom']):raise ValueError('One or two actual neighborhood budgets matching the selected harmonic scope required')
    if mode=='progeny_activity' and (p.get('organism') not in {'Human','Mouse'} or type(p.get('scale_scores')) is not bool):raise ValueError('Exact supported PROGENy organism and score scaling decision required')
    if mode=='drug2cell_score' and p.get('method') not in {'mean','seurat'}:raise ValueError('Choose the actual native Drug2cell scoring method')
    if mode=='cellphonedb_per_unit' and (p.get('species')!='Homo sapiens' or p.get('gene_identifier_type') not in {'ensembl','hgnc_symbol','gene_name'}):raise ValueError('Reviewed human database and actual gene namespace required; no automatic ortholog mapping')
    if mode=='paste_pairwise' and (p.get('dissimilarity') not in {'kl','euclidean'} or type(p.get('normalize_distances')) is not bool or type(p.get('align_coordinates')) is not bool):raise ValueError('Explicit native PASTE cost, distance normalization and coordinate alignment decisions required')
    if mode=='squidpy_section_statistics':
        version=re.match(r'^(\d+)\.(\d+)\.(\d+)',versions['squidpy'])
        if not version or tuple(map(int,version.groups()))<(1,8,4):raise ValueError('Reviewed spatial-statistics route requires Squidpy >=1.8.4 RNG/graph API; older streams are not silently substituted')
        edges=p.get('distance_intervals')
        if not isinstance(edges,list) or len(edges)<3 or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in edges) or any(b<=a for a,b in zip(edges,edges[1:])):raise ValueError('Explicit increasing physical distance intervals required')
        if p.get('nhood_normalization') not in {'none','total','conditional'} or type(p.get('two_tailed')) is not bool:raise ValueError('Explicit native neighborhood normalization and autocorrelation tail required')
    if mode in {'vep_offline','ldsc_h2'}:
        field='vep_executable_sha256' if mode=='vep_offline' else 'ldsc_script_sha256'
        if not re.fullmatch('[a-f0-9]{64}',str(p.get(field,''))):raise ValueError('Exact independently reviewed native executable/script hash required')
        if not isinstance(p.get('assembly'),str) or not p['assembly']:raise ValueError('Explicit reference genome assembly required')
        if mode=='vep_offline' and p.get('species')!='homo_sapiens':raise ValueError('This VEP route is scoped to reviewed human sequence variants')
        if mode=='ldsc_h2' and (not p.get('ancestry') or p.get('heritability_scale')!='observed'):raise ValueError('Matched LD-reference ancestry and observed h2 scale required; no implicit liability conversion')
    if mode=='seurat_to_anndata':
        if not isinstance(p.get('r_software_versions'),dict) or any(not isinstance(p['r_software_versions'].get(k),str) or not p['r_software_versions'][k] for k in ['Seurat','Matrix','jsonlite']):raise ValueError('Pin existing R exchange dependencies separately from the existing Python environment')
        for key in ['metadata_keys','categorical_keys','reduction_names']:
            if not isinstance(p.get(key),list) or len(set(p[key]))!=len(p[key]) or any(not isinstance(k,str) or not k for k in p[key]):raise ValueError('Explicit unique selected exchange fields/reductions required')
        if not set(p['categorical_keys'])<=set(p['metadata_keys']) or p.get('normalization_scale')!='log1p_normalized':raise ValueError('Declared categorical fields and actual nonnegative log-normalized expression required')
    if mode=='cinemaot_effects':
        if p.get('expression_scale')!='log1p_normalized' or p.get('representation_kind') not in {'unintegrated_pca','reviewed_integrated_latent'} or not p.get('causal_assumptions'):raise ValueError('CINEMA-OT needs explicit observed expression, metric representation and reviewed counterfactual assumptions')
        if not isinstance(p.get('treatments'),list) or not p['treatments'] or len(set(p['treatments']))!=len(p['treatments']) or p.get('control') in p['treatments']:raise ValueError('Unique observed target conditions distinct from control required')
    if mode=='cellcap_programs':
        if p.get('validation_scope')!='descriptive_fit_optimizer_cell_split_only' or type(p.get('use_gpu')) is not bool or type(p.get('early_stopping')) is not bool:raise ValueError('Legacy CellCap cell-split validation is optimizer monitoring only, not independent-unit predictive validation')
        if not isinstance(p.get('target_order'),list) or not p['target_order'] or len(set(p['target_order']))!=len(p['target_order']) or p.get('control') in p['target_order']:raise ValueError('Explicit observed perturbation order and separate control required')
        for key in ['n_programs','n_heads','minimum_units']:
            if type(p.get(key)) is not int or p[key]<1:raise ValueError('Positive explicit CellCap model/support budget required')
        if 'n_latent' in p and p['n_latent']%p['n_heads']:raise ValueError('CellCap latent dimension must support its native attention heads')
        if type(p.get('optimization_train_fraction')) not in (int,float) or not 0<p['optimization_train_fraction']<1:raise ValueError('Explicit bounded optimizer training/monitoring split required')
    if mode=='systema_evaluate' and (p.get('holdout_axis') not in {'unit','perturbation'} or not p.get('analysis_scale')):raise ValueError('Explicit heldout unit or perturbation benchmark and common source scale required')
    if mode=='igv_scoped_report':
        if p.get('asset_scope')!='existing_reviewed_offline_template' or not p.get('assembly'):raise ValueError('Scoped actual assembly and owned offline IGV assets required, no public reference/track endpoints')
        for key in ['maximum_sites','maximum_variant_length','maximum_reads_per_site','initial_window_bp']:
            if type(p.get(key)) is not int or p[key]<1:raise ValueError('Positive bounded actual genome-view scope required')
        if type(p.get('flank_bp')) is not int or p['flank_bp']<0 or type(p.get('exclude_flags')) is not int or p['exclude_flags']<0:raise ValueError('Explicit native read-view filtering/window settings required')
    if mode=='native_unit_profile_handoff':
        reserved={'profile_id','n_source_cells','state','data_kind','source_producer','selected_for_handoff'};columns=p.get('scenario_columns')
        if not isinstance(columns,list) or not columns or len(set(columns))!=len(columns) or p.get('unit_key') in columns or any(not isinstance(v,str) or not v or v in reserved for v in columns) or p.get('unit_key') in reserved:raise ValueError('Exact distinct actual scenario/unit fields without technical-field collisions required')
        if p.get('data_kind') not in {'observed_log_expression','model_decoded_expression'} or p.get('aggregation_scope') not in {'within_unit_and_celltype','within_unit_all_cells'}:raise ValueError('Explicit unchanged expression kind and actual within-unit aggregation scope required')
        if not isinstance(p.get('selected_scenarios'),dict) or any(k not in columns or not isinstance(v,list) for k,v in p['selected_scenarios'].items()):raise ValueError('Only explicit selections of actual scenario fields are supported')
        for key in ['minimum_cells_per_profile','maximum_cells']:
            if type(p.get(key)) is not int or p[key]<1:raise ValueError('Positive explicit actual profile-support budget required')
    if mode=='proteintalks_predict':
        if p.get('accelerator') not in {'cpu','gpu'} or not p.get('phenotype_definition') or not p.get('expression_scale'):raise ValueError('Actual checkpoint binary phenotype/scale and device required; no unnamed efficacy/synergy interpretation')
        if type(p.get('maximum_cases')) is not int or p['maximum_cases']<1:raise ValueError('Bounded actual case prediction budget required')
    if mode=='prescient_trajectories':
        if p.get('accelerator') not in {'cpu','gpu'} or p.get('representation_kind')!='checkpoint_training_metric_space' or not p.get('model_time_unit'):raise ValueError('Actual native model coordinate/time scale and device required; no UMAP substitution')
        ids=p.get('initial_cells')
        if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids) or any(not isinstance(v,str) or not v for v in ids):raise ValueError('Literal actual initial-cell identities required')
        for key in ['n_simulations','n_steps','maximum_trajectory_entries']:
            if type(p.get(key)) is not int or p[key]<1:raise ValueError('Positive explicit native trajectory budget required')
        if type(p.get('dt')) not in (int,float) or not math.isfinite(p['dt']) or p['dt']<=0 or type(p.get('noise_sd')) not in (int,float) or not math.isfinite(p['noise_sd']) or p['noise_sd']<0:raise ValueError('Actual finite native training time/noise calibration required')
    if mode=='batchie_posterior':
        for key in ['n_chains','posterior_draws','burnin','thin','maximum_experiments','maximum_prediction_entries','minimum_units']:
            if type(p.get(key)) is not int or p[key]<1:raise ValueError('Positive explicit actual BATCHIE chain/support budget required')
        if p['n_chains']<2 or p['posterior_draws']<20 or not p.get('dose_unit') or not isinstance(p.get('control_treatment_name'),str):raise ValueError('Independent native chains/draws, actual dose units and control identity required')
        if type(p.get('maximum_rhat')) not in (int,float) or not math.isfinite(p['maximum_rhat']) or p['maximum_rhat']<=1 or type(p.get('minimum_ess')) not in (int,float) or not math.isfinite(p['minimum_ess']) or p['minimum_ess']<=0:raise ValueError('Explicit finite native posterior diagnostic criteria required')
    if mode=='causcell_counterfactual_fit':
        names=p.get('concepts');dag=p.get('causal_dag');targets=p.get('interventions')
        if not isinstance(names,list) or not names or len(set(names))!=len(names) or any(not isinstance(v,str) or not v for v in names):raise ValueError('Unique explicit observed concept names required')
        size=len(names)+1
        if not isinstance(dag,list) or len(dag)!=size or any(not isinstance(r,list) or len(r)!=size or any(type(v) is not int or v not in {0,1} for v in r) for r in dag):raise ValueError('Explicit native child-by-parent DAG including unexplained concept required')
        if any(dag[i][i] for i in range(size)) or any(dag[-1]) or any(r[-1] for r in dag):raise ValueError('No self-parent links; original unexplained concept is isolated in this fixed native route')
        remaining=set(range(size))
        while remaining:
            roots={i for i in remaining if not any(dag[i][j] for j in remaining)}
            if not roots:raise ValueError('Assumed concept graph contains a directed cycle')
            remaining-=roots
        if not isinstance(targets,list) or not targets or any(not isinstance(r,dict) or r.get('concept') not in names or r.get('reference')==r.get('target') for r in targets) or len({r['concept'] for r in targets})!=len(targets):raise ValueError('Distinct explicit reference-to-target concept interventions required')
        if p.get('accelerator')!='gpu' or p.get('validation_scope')!='descriptive_fit_assumed_dag_no_predictive_validation' or p.get('expression_scale')!='log_normalized_expression':raise ValueError('Actual original CUDA implementation, observed expression and descriptive assumed-DAG scope required')
        for key in ['profile_size','training_steps','checkpoint_every','diffusion_steps','minimum_source_cells','minimum_units']:
            if type(p.get(key)) is not int or p[key]<1:raise ValueError('Positive bounded original CausCell model/support setting required')
    if mode in {'biolord_attributes','scvidr_predict'}:
        if p.get('expression_scale')!='log_normalized_expression' or type(p.get('early_stopping')) is not bool or type(p.get('optimization_train_fraction')) not in (int,float) or not 0<p['optimization_train_fraction']<1:raise ValueError('Actual observed log expression and explicit bounded optimizer-only cell split required')
    if mode=='biolord_attributes':
        categorical=p.get('categorical_attributes');ordered=p.get('ordered_attributes');target=p.get('prediction_attributes')
        if any(not isinstance(v,list) for v in [categorical,ordered,target]) or not categorical+ordered or len(set(categorical+ordered))!=len(categorical+ordered) or 'source_cell_id' in categorical+ordered or not target or not set(target)<=set(categorical+ordered) or p.get('unit_key') in target:raise ValueError('Distinct observed attribute roles and supported counterfactual attributes required; never rewrite original unit IDs')
        if p.get('accelerator') not in {'cpu','gpu'} or p.get('validation_scope')!='descriptive_attribute_fit_optimizer_cell_split_only':raise ValueError('Native fitted-cell attribute model is not independent-donor response validation')
    if mode=='scvidr_predict':
        if not re.match(r'^0\.1[0-3]\.',versions['scvi-tools']) or type(p.get('regression')) is not bool or type(p.get('use_gpu')) is not bool:raise ValueError('Original scVIDR needs its isolated reviewed legacy scvi setup API, not a modern API substitution')
        if p.get('holdout_scope')!='celltype_treated_response_only_controls_in_training' or p.get('control')==p.get('treatment'):raise ValueError('State the actual native response holdout; query controls are part of VAE training')
    if mode=='spatialglue_integrate':
        settings={'SPOTS':(600,[1,5,1,1]),'Stereo-CITE-seq':(1500,[1,10,1,10]),'10x':(200,[1,5,1,10]),'Spatial-epigenome-transcriptome':(1600,[1,5,1,1])}
        if p.get('datatype') not in settings or p.get('accelerator') not in {'cpu','gpu'} or not p.get('coordinate_unit'):raise ValueError('Explicit source-supported native datatype/device and physical coordinate unit required')
        epochs,weights=settings[p['datatype']]
        if p.get('max_epochs')!=epochs or p.get('weight_factors')!=weights:raise ValueError('Native datatype overrides epoch/loss settings; declare the actual native values')
        if p['datatype'] in {'Stereo-CITE-seq','Spatial-epigenome-transcriptome'} and p.get('spatial_neighbors')!=6:raise ValueError('This native datatype fixes spatial neighbor count at six')
    if mode=='nestedcv_glmnet':
        if p.get('task') not in {'binary_classification','regression'}:raise ValueError('Explicit native binary/regression task required')
        if p['task']=='binary_classification' and (not isinstance(p.get('class_order'),list) or len(p['class_order'])!=2 or len(set(p['class_order']))!=2 or p.get('positive_class')!=p['class_order'][1]):raise ValueError('Native outer probability uses the explicitly declared second class level')
    if mode in {'diffdock_pose','diffsbdd_generate','rfdiffusion_backbone','mace_singlepoint'}:
        if p.get('accelerator') not in {'cpu','gpu'} or p.get('model_loading_scope')!='existing_reviewed_trusted_artifacts_only':raise ValueError('Explicit allocated accelerator and exact existing trusted model-loading scope required; no automatic downloads')
    if mode in {'diffdock_pose','diffsbdd_generate','rfdiffusion_backbone'}:
        required={'torch','numpy'}|({'fair-esm','torch-geometric','PyYAML'} if mode=='diffdock_pose' else {'pytorch-lightning','rdkit'} if mode=='diffsbdd_generate' else {'hydra-core','omegaconf'})
        native=p.get('native_software_versions')
        if not isinstance(native,dict) or not required<=set(native) or any(not isinstance(v,str) or not v for v in native.values()):raise ValueError('Pin actual scientific child-interpreter dependencies separately from the preparation/QC interpreter')
    if mode=='diffsbdd_generate':
        residues=p.get('pocket_residues')
        if not isinstance(residues,list) or not residues or len(set(residues))!=len(residues) or any(not isinstance(v,str) or not re.fullmatch('[A-Za-z0-9]:-?[0-9]+',v) for v in residues):raise ValueError('Literal native chain:residue pocket identities required')
    if mode=='rfdiffusion_backbone' and p.get('design_scope')!='unconditional_fixed_length_backbone':raise ValueError('This original native route supports unconditional backbone geometry only, not binder sequence/function design')
    if mode=='mace_singlepoint':
        if p.get('dtype') not in {'float32','float64'} or p.get('model_energy_unit') not in {'eV','hartree','kcal_per_mol','kJ_per_mol'} or p.get('model_length_unit') not in {'angstrom','bohr','nm'}:raise ValueError('Explicit actual model precision and physical units required')
        if not isinstance(p.get('supported_elements'),list) or not p['supported_elements'] or len(set(p['supported_elements']))!=len(p['supported_elements']):raise ValueError('Actual model supported element universe required')
        for key,expected in [('energy_units_to_ev',{'eV':1.,'hartree':27.211386245988,'kcal_per_mol':.043364104241800934,'kJ_per_mol':.010364269656262174}[p['model_energy_unit']]),('length_units_to_angstrom',{'angstrom':1.,'bohr':.529177210903,'nm':10.}[p['model_length_unit']])]:
            if key in p and (type(p[key]) not in (int,float) or not math.isfinite(p[key]) or not math.isclose(p[key],expected,rel_tol=1e-8,abs_tol=1e-12)):raise ValueError('Declared physical model units do not match the numerical conversion: '+key)
    for key in ['n_samples','backbone_length','maximum_structures','maximum_atoms','inference_steps','ligand_atoms']:
        if key in p and (type(p[key]) is not int or p[key]<1):raise ValueError('Positive bounded actual native inference budget required: '+key)
    for key in ['energy_units_to_ev','length_units_to_angstrom']:
        if key in p and (type(p[key]) not in (int,float) or not math.isfinite(p[key]) or p[key]<=0):raise ValueError('Actual positive model-to-output unit conversion required')
    for key in ['minimum_molecules','maximum_molecules','minimum_ld_reference_units','heidi_minimum_snps','heidi_maximum_snps','cis_window_kb','spatial_neighbors','maximum_dense_graph_entries','group_min_samples','workers']:
        if key in p and (type(p[key]) is not int or p[key]<1):raise ValueError('Positive integer native support/budget required: '+key)
    for key in ['cell_radius','coordinate_roundtrip_tolerance','attention_sum_tolerance','ppm','snr_threshold','alignment_bin_mz','group_bandwidth_seconds','group_bin_mz']:
        if key in p and (type(p[key]) not in (int,float) or not math.isfinite(p[key]) or p[key]<=0):raise ValueError('Positive finite native setting required: '+key)
    if mode=='xcms_preprocess':
        ids=p.get('raw_input_ids')
        if not isinstance(ids,list) or len(ids)<2 or len(set(ids))!=len(ids) or any(not isinstance(s,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',s) or s=='metadata' for s in ids):raise ValueError('Distinct literal native MS input role IDs required')
        if p.get('acquisition_mode')!='centroid' or p.get('polarity') not in {'positive','negative'} or type(p.get('fill_peaks')) is not bool:raise ValueError('One explicit actual centroid polarity and gap-integration decision required')
        if not set(p.get('feature_definition_roles',[]))<=set(['study','pooled_qc','standard']) or not p.get('feature_definition_roles'):raise ValueError('Explicit feature-definition roles required; blanks must not define features')
        for key in ['peak_width_seconds','prefilter']:
            v=p.get(key)
            if not isinstance(v,list) or len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in v):raise ValueError('Explicit bounded native peak setting required: '+key)
        if p['peak_width_seconds'][0]>=p['peak_width_seconds'][1]:raise ValueError('Increasing peak width in seconds required')
    if mode=='baysor_segment':
        if p.get('implementation')!='Baysor_CPP' or p.get('dimensions') not in {2,3} or not p.get('coordinate_unit') or p.get('cluster_method') not in {'mrf','leiden','louvain','none'}:raise ValueError('Explicit supported native Baysor C++ scope, dimension, physical unit and prior method required')
        if not re.fullmatch('[a-f0-9]{64}',p.get('baysor_executable_sha256','')) or not p.get('baysor_version_output'):raise ValueError('Exact installed Baysor binary/version binding required')
        if type(p.get('prior_confidence')) not in (int,float) or not 0<=p['prior_confidence']<=1:raise ValueError('Explicit admissible prior confidence required')
    if mode=='smr_heidi':
        if not re.fullmatch('[a-f0-9]{64}',p.get('smr_executable_sha256','')) or p.get('heidi_method') not in {0,1} or not p.get('assembly') or not p.get('ancestry'):raise ValueError('Exact native SMR binary, HEIDI method and ancestry/build required')
        for key in ['maf','frequency_difference','maximum_frequency_exclusion_fraction','instrument_pvalue','heidi_instrument_pvalue','ld_lower','ld_upper','smr_result_pvalue','heidi_result_pvalue']:
            if type(p.get(key)) not in (int,float) or not math.isfinite(p[key]) or not 0<p[key]<1:raise ValueError('Explicit admissible native SMR/HEIDI threshold required: '+key)
        if p['ld_lower']>=p['ld_upper'] or p.get('heidi_minimum_snps',0)<3 or p.get('heidi_maximum_snps',0)<p['heidi_minimum_snps']:raise ValueError('Ordered LD interval and native HEIDI support bounds required')
    if verify_versions:
        import importlib.metadata
        for name,version in versions.items():
            if importlib.metadata.version(name)!=version:raise ValueError('Installed Python package differs from the reviewed exact version: '+name)
    return True

def check_split(train_rows,query_rows,unit_key,celltype_key,condition_key,control,treatment,axis):
    """Metadata-only leakage contract, preserving literal identifiers."""
    if not train_rows or not query_rows:raise ValueError('Actual nonempty training and query cell metadata required')
    allrows=train_rows+query_rows
    if any(any(not isinstance(r.get(k),str) or not r[k] for k in ['cell_id',unit_key,celltype_key,condition_key]) for r in allrows):raise ValueError('Exact complete cell, unit, celltype and condition strings required')
    if len({r['cell_id'] for r in allrows})!=len(allrows):raise ValueError('Training/query cell identities overlap or duplicate')
    if set(r[condition_key] for r in train_rows)!={control,treatment} or any(r[condition_key]!=control for r in query_rows):raise ValueError('Train on declared observed control/treatment only; predict actual query controls')
    if axis=='unit':
        if {r[unit_key] for r in train_rows}&{r[unit_key] for r in query_rows}:raise ValueError('Heldout-unit leakage')
    elif axis=='celltype':
        if {r[celltype_key] for r in train_rows if r[condition_key]==treatment}&{r[celltype_key] for r in query_rows}:raise ValueError('Heldout cell type treatment leakage')
    else:raise ValueError('Unsupported holdout axis')
    return True
