#!/usr/bin/env Rscript
# Actual package calls on the existing server; no installs or network retrieval.
suppressPackageStartupMessages(library(jsonlite))
r<-fromJSON(commandArgs(trailingOnly=TRUE)[1],simplifyVector=FALSE);p<-r$parameters;files<-r$inputs;out<-r$out;mode<-r$mode;outputs<-list();set.seed(p$seed)
for(pkg in names(p$software_versions)) if(!requireNamespace(pkg,quietly=TRUE)||as.character(packageVersion(pkg))!=p$software_versions[[pkg]]) stop(paste('Missing/different reviewed server package:',pkg))
emit<-function(x,name,role,rows=TRUE){fn<-paste0(name,'.tsv');write.table(x,file.path(out,fn),sep='\t',quote=FALSE,row.names=rows,col.names=if(rows) NA else TRUE,na='NA');outputs[[length(outputs)+1]]<<-list(file=fn,role=role)}
save_obj<-function(x,name,role){saveRDS(x,file.path(out,name));outputs[[length(outputs)+1]]<<-list(file=name,role=role)}
matrix_input<-function(name){x<-as.matrix(read.delim(files[[name]],row.names=1,check.names=FALSE));storage.mode(x)<-'numeric';if(anyDuplicated(rownames(x))||anyDuplicated(colnames(x))||any(!is.finite(x)))stop('Finite exact sample-by-feature matrix required');x}
diagnostics<-list(mode=mode,scientific_acceptance='NOT_ESTABLISHED',software_versions=p$software_versions)
if(mode=='spark_spatial') {
  suppressPackageStartupMessages(library(SPARK));counts<-matrix_input('counts');meta<-read.delim(files$metadata,row.names=1,check.names=FALSE);covariates<-matrix_input('covariates')
  if(any(counts<0)||any(counts!=floor(counts))||!setequal(colnames(counts),rownames(meta))||!setequal(colnames(counts),rownames(covariates)))stop('Raw integer genes-by-spots counts, actual spot metadata and numeric covariates required')
  keys<-c(p$unit_key,p$section_key,p$x_key,p$y_key);if(!all(keys%in%names(meta))||anyNA(meta[,keys,drop=FALSE])||!nzchar(p$coordinate_unit))stop('Actual unit, section and spatial coordinate identities/units required');meta<-meta[colnames(counts),,drop=FALSE]
  sections<-unique(meta[[p$section_key]]);results<-list();ledgers<-list()
  for(i in seq_along(sections)){
    s<-sections[i];ids<-rownames(meta)[meta[[p$section_key]]==s];loc<-as.matrix(meta[ids,c(p$x_key,p$y_key)]);storage.mode(loc)<-'numeric'
    if(any(!is.finite(loc))||length(unique(meta[ids,p$unit_key]))!=1||length(ids)<p$minimum_spots)stop('Finite actual coordinates with enough spots in one independent unit required per section')
    object<-SPARK::CreateSPARKObject(counts=counts[,ids,drop=FALSE],location=loc,percentage=p$minimum_expression_fraction,min_total_counts=p$minimum_library_counts)
    retained<-colnames(object@counts);cov<-covariates[retained,,drop=FALSE]
    if(!length(retained)||nrow(cov)<=ncol(cov)+1||qr(cbind(1,cov))$rank<ncol(cov)+1)stop('Spatial covariate design is confounded or under-supported after native input filtering; no zero filling')
    object@lib_size<-colSums(object@counts)
    object<-SPARK::spark.vc(object,covariates=cov,lib_size=object@lib_size,num_core=p$threads,verbose=TRUE)
    object<-SPARK::spark.test(object,check_positive=TRUE,verbose=TRUE)
    table<-as.data.frame(object@res_mtest)
    if(!all(c('combined_pvalue','adjusted_pvalue')%in%colnames(table))||!all(rownames(table)%in%rownames(counts)))stop('Native SPARK output schema or gene identity differs')
    known<-!is.na(table$combined_pvalue)&!is.na(table$adjusted_pvalue)
    if(any(!is.finite(as.matrix(table[known,c('combined_pvalue','adjusted_pvalue'),drop=FALSE])))||any(table$combined_pvalue[known]<0|table$combined_pvalue[known]>1)||any(table$adjusted_pvalue[known]<0|table$adjusted_pvalue[known]>1))stop('Invalid native spatial test probabilities')
    emit(table,paste0('spark_section_',i),'spatial_differential');results[[as.character(i)]]<-object
    ledgers[[i]]<-data.frame(section_index=i,section_id=s,unit_id=meta[ids[1],p$unit_key],input_spots=length(ids),retained_spots=length(retained),tested_features=nrow(table),untestable_features=sum(!known));emit(data.frame(spot_id=ids,retained=ids%in%retained),paste0('spark_section_',i,'_spot_filter'),'spatial_filter',FALSE)
  }
  ledger<-do.call(rbind,ledgers);emit(ledger,'spark_section_qc','section_qc',FALSE);save_obj(results,'spark_native_models.rds','model_object');diagnostics$n_sections<-length(sections);diagnostics$n_tested_features<-sum(ledger$tested_features);diagnostics$interpretation<-'Original SPARK spatial count model per actual section, not SPARK-X or donor-level condition inference. Untestable feature p-values remain missing; native threshold attrition is recorded'
} else if(mode=='progeny_activity') {
  suppressPackageStartupMessages(library(progeny));expr<-matrix_input('expression');meta<-read.delim(files$metadata,row.names=1,check.names=FALSE)
  if(!setequal(colnames(expr),rownames(meta))||anyDuplicated(rownames(meta))||!p$unit_key%in%names(meta)||anyNA(meta[[p$unit_key]])||p$expression_scale!='reviewed_log_expression')stop('Observed gene-by-sample log expression, exact sample identity and biological units required')
  meta<-meta[colnames(expr),,drop=FALSE];model<-progeny::getModel(organism=p$organism,top=p$top_genes)
  present<-intersect(rownames(model),rownames(expr));coverage<-data.frame(pathway=colnames(model),model_nonzero=colSums(model!=0),observed_nonzero=colSums(model[present,,drop=FALSE]!=0))
  emit(coverage,'progeny_gene_coverage','pathway_coverage',FALSE);if(any(coverage$observed_nonzero<p$minimum_model_genes))stop('Insufficient observed responsive genes in a pathway; review coverage instead of inventing pathway activity')
  # Descriptive native footprint scores only. Gene permutations are a different
  # reference null and do not create independent sample-level hypothesis tests.
  scores<-progeny::progeny(expr,scale=p$scale_scores,organism=p$organism,top=p$top_genes,perm=1,verbose=TRUE)
  if(!setequal(rownames(scores),colnames(expr))||any(!is.finite(scores)))stop('Native activity output identity/finite-value QC failed')
  scores<-scores[colnames(expr),,drop=FALSE];emit(scores,'progeny_activity','pathway_activity');emit(meta,'progeny_sample_identity','sample_metadata');save_obj(model,'progeny_resource_weights.rds','resource_model')
  diagnostics$n_observations<-nrow(scores);diagnostics$n_pathways<-ncol(scores);diagnostics$minimum_covered_genes<-min(coverage$observed_nonzero);diagnostics$scale_scores<-p$scale_scores;diagnostics$interpretation<-'Native PROGENy responsive-footprint scores, not GSVA gene-set expression or direct protein/pathway activity measurements; formal condition inference requires biological-unit modelling'
} else if(mode=='muscat_pseudobulk') {
  suppressPackageStartupMessages(library(muscat));sce<-readRDS(files$object)
  if(!inherits(sce,'SingleCellExperiment')||anyDuplicated(colnames(sce))||anyDuplicated(rownames(sce)))stop('Actual unique SCE required')
  meta<-as.data.frame(SummarizedExperiment::colData(sce));keys<-unique(c(p$unit_key,p$sample_key,p$condition_key,p$celltype_key));if(!all(keys%in%names(meta))||anyNA(meta[,keys,drop=FALSE]))stop('Complete sample, independent unit, condition and annotation required')
  for(s in unique(meta[[p$sample_key]]))if(length(unique(meta[meta[[p$sample_key]]==s,p$unit_key]))!=1||length(unique(meta[meta[[p$sample_key]]==s,p$condition_key]))!=1)stop('Each sample must map to one unit and condition')
  units<-unique(meta[,c(p$sample_key,p$unit_key,p$condition_key),drop=FALSE]);rownames(units)<-units[[p$sample_key]]
  if(anyDuplicated(units[,c(p$unit_key,p$condition_key)]))stop('Pool technical libraries explicitly upstream; they are not new biological replicates')
  if(!p$paired&&anyDuplicated(units[[p$unit_key]]))stop('Repeated donors require an explicitly paired design')
  qc<-read.delim(files$cell_qc,stringsAsFactors=FALSE);if(anyDuplicated(qc$cell_id)||!setequal(qc$cell_id,colnames(sce))||!all(tolower(as.character(qc$keep))%in%c('true','false')))stop('Exact reviewed per-cell QC decisions required')
  qc<-qc[match(colnames(sce),qc$cell_id),];sce<-sce[,tolower(as.character(qc$keep))=='true'];meta<-as.data.frame(SummarizedExperiment::colData(sce))
  counts<-SummarizedExperiment::assay(sce,p$count_assay);v<-if(inherits(counts,'sparseMatrix'))counts@x else as.vector(counts)
  if(any(!is.finite(v))||any(v<0)||any(v!=floor(v)))stop('Actual raw integer counts required')
  population<-unlist(p$celltype_universe);if(anyDuplicated(population)||!all(unique(meta[[p$celltype_key]])%in%population))stop('Explicit reviewed celltype universe must cover all observed labels')
  tab<-table(factor(meta[[p$sample_key]],levels=units[[p$sample_key]]),factor(meta[[p$celltype_key]],levels=population))
  ledger<-as.data.frame(tab,stringsAsFactors=FALSE);names(ledger)<-c('sample_id','celltype','n_cells');ledger$unit<-units[ledger$sample_id,p$unit_key];ledger$condition<-units[ledger$sample_id,p$condition_key];ledger$status<-ifelse(ledger$n_cells==0,'NOT_CAPTURED_AFTER_QC',ifelse(ledger$n_cells<p$minimum_cells,'INSUFFICIENT_CELLS','ELIGIBLE'));emit(ledger,'muscat_population_eligibility','population_eligibility',FALSE)
  if(!all(units[[p$sample_key]]%in%meta[[p$sample_key]]))stop('An entire sample was removed by QC; review the design before formal inference')
  sce<-muscat::prepSCE(sce,kid=p$celltype_key,sid=p$sample_key,gid=p$condition_key,drop=FALSE)
  pb<-muscat::aggregateData(sce,assay=p$count_assay,fun='sum',by=c('cluster_id','sample_id'))
  design<-matrix_input('design');contrast<-matrix_input('contrast')
  if(!setequal(rownames(design),colnames(pb))||!identical(rownames(contrast),colnames(design)))stop('Exact sample-labelled full-rank design and coefficient-labelled contrasts required');design<-design[colnames(pb),,drop=FALSE]
  if(qr(design)$rank<ncol(design)||nrow(design)<=ncol(design))stop('Confounded design or insufficient residual degrees of freedom')
  if(p$paired){
    # Verify that the declared donor indicator subspace is actually represented
    # in the reviewed design; a caller boolean does not create a paired model.
    donor<-model.matrix(~0+factor(units[colnames(pb),p$unit_key]));if(qr(cbind(design,donor))$rank!=qr(design)$rank)stop('Paired design does not span the actual donor indicators')
  }
  if(!p$gene_filter%in%c('genes','none'))stop('No automatic sample-outlier removal in this route; use reviewed upstream QC')
  fit<-muscat::pbDS(pb,method='edgeR',design=design,contrast=contrast,min_cells=p$minimum_cells,filter=p$gene_filter,treat=FALSE,verbose=FALSE,BPPARAM=BiocParallel::SerialParam())
  native_paths<-list();counter<-0
  export_tables<-function(x,path=character()){
    if(is.data.frame(x)){
      if(!all(c('gene','logFC','p_val','p_adj.loc','p_adj.glb')%in%names(x)))stop('Native muscat output schema differs')
      counter<<-counter+1;x$native_result_path<-paste(path,collapse='/');emit(x,paste0('muscat_ds_',counter),'singlecell_differential',FALSE);native_paths[[as.character(counter)]]<<-path
    }else if(is.list(x)){for(i in seq_along(x)){nm<-names(x)[i];if(is.null(nm)||is.na(nm))nm<-as.character(i);export_tables(x[[i]],c(path,nm))}}
  }
  export_tables(fit$table);if(counter==0)stop('No actual eligible differential-state result; preserve eligibility ledger and inspect skipped populations')
  emit(design,'muscat_design','design_matrix');emit(contrast,'muscat_contrast','contrast_matrix');save_obj(pb,'muscat_pseudobulk.rds','pseudobulk_object');save_obj(fit,'muscat_full_fit.rds','model_object');write_json(native_paths,file.path(out,'muscat_result_paths.json'),auto_unbox=FALSE);outputs[[length(outputs)+1]]<-list(file='muscat_result_paths.json',role='result_identity')
  diagnostics$n_result_tables<-counter;diagnostics$n_samples<-ncol(pb);diagnostics$n_retained_cells<-ncol(sce);diagnostics$n_missing_population_samples<-sum(ledger$n_cells==0);diagnostics$paired<-p$paired;diagnostics$inference<-'Native donor/sample-level muscat edgeR pseudobulk DS; missing populations are not fabricated zero-expression samples; native skipped tests remain unassessed'
} else if(mode=='banksy_domains') {
  suppressPackageStartupMessages(library(Banksy));spe<-readRDS(files$object)
  if(!inherits(spe,'SpatialExperiment')||anyDuplicated(colnames(spe))||anyDuplicated(rownames(spe)))stop('Actual unique SpatialExperiment required')
  meta<-as.data.frame(SummarizedExperiment::colData(spe));coords<-SpatialExperiment::spatialCoords(spe)
  if(!all(c(p$unit_key,p$section_key)%in%names(meta))||anyNA(meta[,c(p$unit_key,p$section_key),drop=FALSE])||any(!is.finite(coords))||nrow(coords)!=ncol(spe)||!nzchar(p$coordinate_unit))stop('Actual spatial coordinates, section and biological units with units required')
  sections<-unique(meta[[p$section_key]]);results<-list()
  for(i in seq_along(sections)){
    s<-sections[i];z<-spe[,meta[[p$section_key]]==s];m<-as.data.frame(SummarizedExperiment::colData(z));if(length(unique(m[[p$unit_key]]))!=1)stop('Section maps to multiple independent units')
    x<-SummarizedExperiment::assay(z,p$expression_assay);v<-if(inherits(x,'sparseMatrix'))x@x else as.vector(x)
    if(any(!is.finite(v))||p$assay_scale!='reviewed_log_normalized_expression'||ncol(z)<=max(unlist(p$k_geom),p$knn)||p$n_pcs>=min(dim(x)))stop('Reviewed finite expression and feasible section-specific neighborhood/PCA budgets required')
    z<-Banksy::computeBanksy(z,assay_name=p$expression_assay,compute_agf=p$use_agf,k_geom=unlist(p$k_geom),spatial_mode=p$spatial_mode,seed=p$seed,parallel=FALSE)
    z<-Banksy::runBanksyPCA(z,assay_name=p$expression_assay,use_agf=p$use_agf,lambda=unique(c(0,p$lambda)),npcs=p$n_pcs,scale=p$standardize,seed=p$seed,lazy=FALSE)
    z<-Banksy::clusterBanksy(z,assay_name=p$expression_assay,use_agf=p$use_agf,lambda=p$lambda,npcs=p$n_pcs,algo=p$algorithm,k_neighbors=p$knn,resolution=p$resolution,seed=p$seed)
    emit(as.data.frame(SummarizedExperiment::colData(z)),paste0('banksy_section_',i),'spatial_domains');emb<-SingleCellExperiment::reducedDims(z);for(k in seq_along(emb))emit(emb[[k]],paste0('banksy_section_',i,'_embedding_',k),'spatial_representations')
    results[[as.character(i)]]<-z
  }
  save_obj(results,'banksy_sections.rds','processed_object');emit(data.frame(output_section_index=seq_along(sections),section=sections),'banksy_section_identity','section_identity',FALSE)
  diagnostics$n_sections<-length(sections);diagnostics$n_spots<-ncol(spe);diagnostics$lambda<-p$lambda;diagnostics$cross_section_neighbors<-0;diagnostics$interpretation<-'Native neighborhood-augmented BANKSY domains with lambda=0 expression baseline. Section-specific cluster numbers are not automatically aligned cell types or disease effects'
} else if(mode=='monocle3_trajectory') {
  suppressPackageStartupMessages(library(monocle3));cds<-readRDS(files$object)
  if(!inherits(cds,'cell_data_set')||anyDuplicated(colnames(cds))||anyDuplicated(rownames(cds)))stop('Actual unique Monocle3 cell_data_set required')
  meta<-as.data.frame(SummarizedExperiment::colData(cds));if(!p$unit_key%in%names(meta)||anyNA(meta[[p$unit_key]]))stop('Actual biological units required')
  # Existing reviewed UMAP is used literally; not replaced or re-fitted.
  coords<-SingleCellExperiment::reducedDims(cds)$UMAP
  if(is.null(coords)||nrow(coords)!=ncol(cds)||any(!is.finite(coords)))stop('Finite reviewed existing UMAP required for this Monocle3 graph route')
  roots<-unlist(p$root_cells);if(!length(roots)||anyDuplicated(roots)||!all(roots%in%colnames(cds))||!nzchar(p$direction_evidence))stop('Actual prespecified roots and independent direction evidence required')
  cds<-cluster_cells(cds,reduction_method='UMAP',k=p$knn,resolution=p$resolution,random_seed=p$seed)
  parts<-partitions(cds);if(!all(unique(parts)%in%parts[roots]))stop('Each disconnected partition needs a justified actual root; no fabricated finite pseudotime')
  cds<-learn_graph(cds,use_partition=TRUE,close_loop=p$close_loop,learn_graph_control=list(minimal_branch_len=p$minimal_branch_len))
  cds<-order_cells(cds,reduction_method='UMAP',root_cells=roots);pt<-pseudotime(cds)
  if(any(!is.finite(pt))||!identical(coords,SingleCellExperiment::reducedDims(cds)$UMAP))stop('Nonfinite pseudotime or upstream embedding changed')
  emit(data.frame(cell_id=names(pt),pseudotime=as.numeric(pt),partition=as.character(parts[names(pt)]),unit=meta[names(pt),p$unit_key]),'monocle3_pseudotime','pseudotime',FALSE)
  g<-principal_graph(cds)$UMAP;emit(igraph::as_data_frame(g,what='edges'),'monocle3_principal_edges','principal_graph',FALSE);save_obj(cds,'monocle3_result.rds','processed_object')
  diagnostics$n_cells<-ncol(cds);diagnostics$n_partitions<-length(unique(parts));diagnostics$finite_pseudotime_fraction<-mean(is.finite(pt));diagnostics$method_difference<-'Monocle3 graph method on reviewed UMAP; not the original 2014 Monocle algorithm or Slingshot';diagnostics$direction_evidence<-p$direction_evidence
} else if(mode %in% c('diablo_fit','snf_fusion')) {
  views<-unlist(p$view_ids);if(length(views)<2||anyDuplicated(views))stop('At least two distinct measured views required')
  x<-setNames(lapply(views,matrix_input),views);ids<-rownames(x[[1]])
  if(any(vapply(x,function(z)!identical(rownames(z),ids),logical(1))))stop('All views require the same actual ordered independent units; no row position relabelling or unpaired matching')
  meta<-read.delim(files$metadata,row.names=1,check.names=FALSE)
  if(!setequal(rownames(meta),ids)||anyDuplicated(rownames(meta)))stop('Exact metadata identities required');meta<-meta[ids,,drop=FALSE]
  if(!p$unit_key%in%names(meta)||anyNA(meta[[p$unit_key]])||anyDuplicated(meta[[p$unit_key]]))stop('This route supports one row per independent unit; repeated samples need a different model')
  if(any(vapply(x,function(z)any(apply(z,2,sd)==0),logical(1))))stop('Resolve constant features upstream and record decisions, do not silently drop them')
  if(mode=='snf_fusion') {
    suppressPackageStartupMessages(library(SNFtool));if(p$knn<2||p$knn>=length(ids)||p$n_clusters<2||p$n_clusters>=length(ids))stop('SNF graph/cluster budgets outside actual sample support')
    processed<-if(p$standardize)lapply(x,SNFtool::standardNormalization) else x
    aff<-lapply(processed,function(z)SNFtool::affinityMatrix(SNFtool::dist2(z,z),K=p$knn,sigma=p$sigma))
    fused<-SNFtool::SNF(aff,K=p$knn,t=p$iterations);dimnames(fused)<-list(ids,ids)
    if(any(!is.finite(fused))||any(fused<0)||max(abs(fused-t(fused)))>p$symmetry_tolerance)stop('Native fused network fails numerical QC')
    labels<-SNFtool::spectralClustering(fused,K=p$n_clusters);emit(fused,'snf_fused_similarity','fused_similarity');emit(data.frame(sample_id=ids,cluster=labels,unit=meta[[p$unit_key]]),'snf_clusters','cluster_assignments',FALSE)
    save_obj(list(affinity=aff,fused=fused,clusters=labels,parameters=p),'snf_result.rds','model_object');diagnostics$maximum_asymmetry<-max(abs(fused-t(fused)));diagnostics$inference<-'Unsupervised cohort structure, not heldout classification or causal evidence'
  } else {
    suppressPackageStartupMessages(library(mixOmics));if(!p$condition_key%in%names(meta)||anyNA(meta[[p$condition_key]]))stop('Observed complete training labels required')
    if(p$parameter_selection!='prespecified_external_to_this_cohort')stop('This fit route cannot report tuned training performance as validation; use a distinct nested-validation route')
    y<-factor(meta[[p$condition_key]]);if(nlevels(y)<2)stop('At least two observed classes required')
    design<-matrix(unlist(p$design),nrow=length(views),byrow=TRUE,dimnames=list(views,views))
    if(any(!is.finite(design))||any(design<0|design>1)||max(abs(design-t(design)))>1e-12||any(diag(design)!=0))stop('Explicit symmetric zero-diagonal DIABLO design in [0,1] required')
    keep<-lapply(p$keepX,unlist);if(!setequal(names(keep),views)||any(vapply(views,function(v)length(keep[[v]])!=p$ncomp||any(keep[[v]]<1|keep[[v]]>ncol(x[[v]])),logical(1))))stop('Prespecified per-view, per-component feature counts required')
    fit<-mixOmics::block.splsda(X=x,Y=y,ncomp=p$ncomp,keepX=keep,design=design,scale=p$standardize,max.iter=p$max_iterations)
    for(v in views){emit(fit$variates[[v]],paste0('diablo_variates_',v),'factor_scores');emit(fit$loadings[[v]],paste0('diablo_loadings_',v),'factor_loadings')}
    save_obj(fit,'diablo_model.rds','model_object');emit(data.frame(sample_id=ids,unit=meta[[p$unit_key]],condition=y),'diablo_training_identity','sample_metadata',FALSE)
    diagnostics$inference<-'DIABLO fit and features on training cohort only. Generalization not evaluated by fitted variates; independent validation required';diagnostics$ncomp<-p$ncomp
  }
  diagnostics$n_independent_units<-length(ids);diagnostics$view_ids<-views
} else if(mode=='msstats_compare') {
  suppressPackageStartupMessages(library(MSstats));d<-read.delim(files$feature_table,check.names=FALSE,stringsAsFactors=FALSE)
  required<-c('ProteinName','PeptideSequence','PrecursorCharge','FragmentIon','ProductCharge','IsotopeLabelType','Condition','BioReplicate','Run','Intensity')
  if(!all(required%in%names(d))||anyNA(d[,setdiff(required,'Intensity')]))stop('Native MSstats feature-level schema and real biological replicate/run identities required')
  if(any(is.infinite(d$Intensity))||any(d$Intensity<0,na.rm=TRUE))stop('Nonnegative observed intensities with explicit missingness required')
  for(run in unique(d$Run))if(length(unique(d[d$Run==run,'BioReplicate']))!=1||length(unique(d[d$Run==run,'Condition']))!=1)stop('Each acquisition run must map to one biological unit and condition')
  contrast<-matrix_input('contrast');levels<-sort(unique(d$Condition));if(!setequal(colnames(contrast),levels))stop('Exact explicit condition-labelled contrasts required');contrast<-contrast[,levels,drop=FALSE]
  if(any(abs(rowSums(contrast))>1e-12)||any(rowSums(abs(contrast))==0))stop('Nonzero zero-sum contrasts required')
  processed<-MSstats::dataProcess(d,normalization=p$normalization,featureSubset=p$feature_subset,summaryMethod=p$summary_method,censoredInt=p$censored_int,MBimpute=p$mb_impute)
  # MSstats sorts condition levels alphabetically. Validate against returned data,
  # rather than trusting an undocumented positional assignment.
  actual<-levels(processed$ProcessedData$GROUP_ORIGINAL)
  if(!identical(actual,colnames(contrast)))stop('Native processed condition order differs from reviewed contrast; inspect rather than guess')
  fit<-MSstats::groupComparison(contrast.matrix=contrast,data=processed)
  result<-fit$ComparisonResult;if(is.null(result)||!nrow(result)||!all(c('log2FC','pvalue','adj.pvalue')%in%names(result)))stop('Native protein comparison output schema differs')
  if(any(result$pvalue<0|result$pvalue>1,na.rm=TRUE)||any(result$adj.pvalue<0|result$adj.pvalue>1,na.rm=TRUE))stop('Invalid native protein test probabilities')
  emit(result,'msstats_comparisons','protein_differential',FALSE);save_obj(processed,'msstats_processed.rds','processed_object');save_obj(fit,'msstats_fit.rds','model_object')
  emit(as.data.frame(table(d$Run,is.na(d$Intensity))),'input_missingness_by_run','missingness',FALSE);diagnostics$n_protein_results<-nrow(result);diagnostics$missing_intensity_fraction<-mean(is.na(d$Intensity));diagnostics$normalization<-p$normalization;diagnostics$imputation<-p$mb_impute;diagnostics$interpretation<-'Feature-level protein inference with declared missingness; no invented zero intensities or proteomic evidence of phosphorylation/site activity'
} else stop('Unsupported fixed native omics expansion')
write_json(diagnostics,file.path(out,'diagnostics.json'),pretty=TRUE,auto_unbox=TRUE,na='null',null='null');outputs[[length(outputs)+1]]<-list(file='diagnostics.json',role='diagnostics')
capture.output(sessionInfo(),file=file.path(out,'R_session_info.txt'));outputs[[length(outputs)+1]]<-list(file='R_session_info.txt',role='backend_versions');write_json(outputs,file.path(out,'native_r_outputs.json'),pretty=TRUE,auto_unbox=TRUE)
