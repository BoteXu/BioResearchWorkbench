"""Server preflight: explicit assay contracts, full axes and design prerequisites."""
from pathlib import Path
import csv,math,json,re

MATRIX_ROLES={'matrix','rna_matrix','atac_matrix','reference_counts','methylated','total','protein_matrix','genotype','ld','reference_signatures','target_prior','function_abundance','cell_counts','pseudotime','cell_weights'}
COUNTS={'apa_usage','exon_usage','isoform_switch','transcript_usage','differential_binding','translation_efficiency','microbe_differential','microbe_diversity','microbe_network','spatial_variable_genes','motif_deviation','cell_fraction_contrasts','bulk_deconvolution','spatial_deconvolution'}
SCALES={
 'camera_sets':{'log2_normalized_expression','voom_logCPM'},'gsva_scores':{'log2_normalized_expression'},
 'ssgsea_scores':{'log2_normalized_expression'},'tf_activity':{'log2_normalized_expression'},
 'kinase_activity':{'log2_abundance'},'protein_complexes':{'log2_abundance'},'ptm_adjustment':{'log2_abundance'},
 'differential_coexpression':{'log2_normalized_expression'},'longitudinal_effects':{'log2_normalized_expression'},
 'impulse_response':{'log2_normalized_expression'},'temporal_modules':{'log2_normalized_expression'},
 'singlecell_cnv':{'log2_normalized_expression'},'lr_consensus':{'log1p_normalized_expression'},
 'spatial_lr':{'nonnegative_normalized_expression'},'lr_differential':{'log1p_ligand_receptor_mean_product'},'lipid_chain_patterns':{'log2_abundance'}}
TABLE_COLUMNS={
 'samples':['sample_id','unit_id'],'feature_map':['feature_id','gene_id'],
 'site_qc':['feature_id','internal_priming_fraction','terminal_coverage'],
 'isoform_annotations':['feature_id','cds_length','domain_ids','nmd_annotation'],
 'edge_universe':['source','target'],'candidate_links':['peak','gene','distance_bp'],
 'junction_counts':['event_id','sample_id','included','total'],'event_definitions':['event_id','cluster_id','coordinate','event_type'],
 'enrichment':['term','q','NES'],'leading_members':['term','feature_id'],
 'regulatory_network':['source','target','mor'],'donor_lr':['sample_id','source','target','ligand','receptor','score'],
 'lipid_annotations':['feature_id','class'],'feature_stats':['feature_id','statistic'],
 'motif_hits':['peak_id','motif'],'peak_universe':['peak_id','foreground','gc','length'],
 'regions':['chromosome','start','end'],'probe_map':['probe_id','chromosome','position'],
 'psms':['spectrum_id','peptide','score','is_decoy','search_space','variant_space','sample_id'],
 'peptide_variants':['peptide','variant_id','unique_to_variant','reference_peptide'],
 'clone_cells':['cell_id','sample_id','clone_id'],'cell_metadata':['cell_id','unit_id'],
 'query_signature':['feature_id','statistic'],'signature_context':['signature_id','cell_model','dose','duration','source_record'],
 'normal_reference':['sample_id','reviewed_normal'],'gene_positions':['feature_id','chromosome','position'],
 'spatial_values':['spot_id','feature_id','value'],'coordinates':['spot_id','x','y','section_id','unit_id'],
 'boundaries':['section_id','x','y'],'cell_types':['spot_id','cell_type'],'lr_resource':['ligand','receptor'],
 'p_sites':['chromosome','position','strand','sample_id','count'],'orfs':['orf_id','chromosome','start','end','strand','transcript_id','orf_type'],
 'offset_qc':['sample_id','offset_validated','cds_frame0_fraction'],'orf_blocks':['orf_id','chromosome','start','end','strand','transcript_offset'],
 'study_effects':['study_id','effect','se','estimand'],'study_overlap':['study1','study2','overlap_n'],
 'summary':['variant_id','beta','se','effect_allele','other_allele'],'ld_variants':['variant_id','effect_allele','other_allele'],
 'trait1':['variant_id','beta','se','maf','effect_allele','other_allele'],'trait2':['variant_id','beta','se','maf','effect_allele','other_allele'],
 'clump_evidence':['SNP','ld_clumped','reference_version'],'variant_masks':['variant_id','mask'],
 'complex_members':['complex','protein'],'site_map':['site','protein'],
 'periodicity':['sample_id','frame0_fraction','offset_validated'],
 'histology':['spot_id','reviewed'],'root_evidence':['cluster','evidence','reviewed'],
 'reference_metadata':['cell_id'],'target_prior':[],
 'receiver_de':['feature_id','logFC','q'],'expressed_ligands':['ligand'],'expressed_receptors':['receptor'],'lr_prior':['ligand','receptor'],
 'nodes':['node_id'],'edges':['source','target','weight'],'seeds':['node_id','weight'],'holdout':['node_id','positive'],
 'segments':['chromosome','start','end','log2','probes'],'reference_qc':['reference_sex','normal_reviewed','read_bias_assessed'],
 'mutations':['mutation_id','sample_id','ref_counts','alt_counts','normal_cn','major_cn','minor_cn','tumour_content'],
 'genotype_variants':['variant_id','ref','alt'],'weights':['variant_id','effect_allele','beta'],'base_cohorts':['unit_id']}

def header(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        h=next(csv.reader(f,delimiter='\t'),[])
    if not h or len(h)!=len(set(h)):raise ValueError('Duplicate or empty raw table header: '+Path(path).name)
    return h

def matrix_qc(path,integer=False):
    h=header(path);ids=set();n=0;minimum=math.inf;maximum=-math.inf
    if len(h)<2:raise ValueError('Matrix needs feature IDs and explicit samples')
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        rows=csv.reader(f,delimiter='\t');next(rows)
        for row in rows:
            if len(row)!=len(h) or not row[0] or row[0] in ids:raise ValueError('Ragged matrix or duplicate feature identifier')
            ids.add(row[0]);n+=1
            for value in row[1:]:
                x=float(value)
                if not math.isfinite(x) or (integer and (x<0 or x!=round(x))):raise ValueError('Missing/nonfinite or noninteger count value')
                minimum=min(minimum,x);maximum=max(maximum,x)
    if not n:raise ValueError('Empty input feature denominator')
    return {'features':n,'columns':len(h)-1,'minimum':minimum,'maximum':maximum,'integer_required':integer}

def preflight(inputs,p,context,spec):
    key=p['analysis_id'];observations={}
    if key in COUNTS and context['scale']!='raw_counts':raise ValueError('This chosen method requires raw count input, not normalized abundance')
    if key in SCALES and context['scale'] not in SCALES[key]:raise ValueError('Assay scale incompatible with chosen actual method')
    resolved=context.get('resolved_decisions',{})
    if any(not resolved.get(k) for k in spec['decision_fields']):raise ValueError('Missing branch-specific scientific decisions: '+str(spec['decision_fields']))
    if context.get('unit_map_reviewed') is not True or context.get('reference_identity_reviewed') is not True:raise ValueError('Independent-unit and reference identity review required')
    for role,path in inputs.items():
        if role!='context':observations[role]={'bytes':Path(path).stat().st_size}
        if role in MATRIX_ROLES:
            integer=(key in COUNTS and role in {'matrix','cell_counts','reference_counts'}) or role in {'methylated','total'}
            observations[role]=matrix_qc(path,integer)
        elif role in TABLE_COLUMNS:
            h=header(path)
            if not set(TABLE_COLUMNS[role])<=set(h):raise ValueError('Missing required '+role+' columns: '+str(set(TABLE_COLUMNS[role])-set(h)))
            observations[role]={'header_columns':len(h)}
    for name,value in p.items():
        if name in {'bootstraps','permutations','n_perms','simulations','stars_reps','null_permutations','donor_resamples'} and (type(value) is not int or value<20):raise ValueError('Use >=20 explicit diagnostic resamples; production precision must be chosen in the statistical plan')
        if name in {'fdr','coverage','auc_threshold','expr_prop','lambda_min_ratio'} and (type(value) not in (int,float) or not 0<value<1):raise ValueError('Invalid probability/fraction parameter '+name)
    if key in {'fine_mapping','colocalization','two_sample_mr','polygenic_score','rare_variant_burden'}:
        for k in ('allele_alignment_reviewed','ancestry_compatibility_reviewed','sample_overlap_assessed'):
            if resolved.get(k) is not True:raise ValueError('Genetics identity/design QC absent: '+k)
    if key in {'junction_events','exon_usage','transcript_usage','isoform_switch','apa_usage','uorf_translation','translation_efficiency'}:
        if resolved.get('protocol_supports_claim') is not True or not resolved.get('feature_definition_version'):raise ValueError('RNA event/translation protocol and version evidence required')
    if key=='multiomics_mediation':
        if not all(resolved.get(k) is True for k in ('temporal_order_supported','confounding_reviewed','mediator_outcome_confounding_reviewed')):raise ValueError('Mediation causal identification assumptions unresolved')
    if key in {'microbe_network','microbe_pathways','microbe_differential','microbe_diversity'}:
        if resolved.get('contamination_reviewed') is not True or not resolved.get('zero_handling'):raise ValueError('Microbial contamination/zero treatment QC absent')
    return {'state':'EXECUTED_PREFLIGHT','observations':observations,'resolved_decisions':resolved,
      'scientific_acceptance':'not_established_by_preflight'}
