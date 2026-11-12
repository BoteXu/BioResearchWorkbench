#!/usr/bin/env Rscript
# Called only by native_teaching_adapter.py behind the unchanged server guard.
suppressPackageStartupMessages(library(jsonlite))
args<-commandArgs(trailingOnly=TRUE);r<-fromJSON(args[1],simplifyVector=FALSE);p<-r$parameters;files<-r$inputs;out<-r$out;mode<-r$mode;outputs<-list();set.seed(p$seed)
for(pkg in names(p$software_versions)) if(!requireNamespace(pkg,quietly=TRUE)||as.character(packageVersion(pkg))!=p$software_versions[[pkg]]) stop(paste('Missing/different reviewed server package:',pkg))
emit<-function(value,name,role,rows=TRUE){file<-paste0(name,'.tsv');write.table(value,file.path(out,file),sep='\t',quote=FALSE,row.names=rows,col.names=if(rows) NA else TRUE,na='NA');outputs[[length(outputs)+1]]<<-list(file=file,role=role)}
save_obj<-function(value,name,role){saveRDS(value,file.path(out,name));outputs[[length(outputs)+1]]<<-list(file=name,role=role)}
diagnostics<-list(mode=mode,scientific_acceptance='NOT_ESTABLISHED',versions=p$software_versions)
if(mode=='singler_annotate') {
  suppressPackageStartupMessages(library(SingleR));test<-readRDS(files$object);ref<-readRDS(files$reference)
  if(anyDuplicated(colnames(test))||anyDuplicated(rownames(test))||anyDuplicated(rownames(ref))) stop('Unique literal expression identities required')
  if(p$label_key%in%colnames(SummarizedExperiment::colData(ref))) labels<-SummarizedExperiment::colData(ref)[[p$label_key]] else stop('Declared reference label field absent')
  if(anyNA(labels)) stop('Reference labels contain missing values')
  common<-intersect(rownames(test),rownames(ref));if(length(common)<p$minimum_reference_genes) stop('Insufficient explicit reference coverage')
  pred<-SingleR::SingleR(test=test,ref=ref,labels=labels,assay.type.test=p$test_assay,assay.type.ref=p$reference_assay,de.method=p$de_method,prune=TRUE)
  emit(data.frame(cell_id=rownames(pred),label=pred$labels,pruned_label=pred$pruned.labels,delta_next=pred$delta.next),'annotation','annotation',FALSE)
  emit(pred$scores,'annotation_scores','annotation_scores');emit(data.frame(feature_id=common),'reference_common_genes','reference_coverage',FALSE)
  save_obj(pred,'annotation_full.rds','annotation_object');diagnostics$unassigned_after_pruning<-sum(is.na(pred$pruned.labels));diagnostics$n_query_cells<-ncol(test);diagnostics$n_reference_common_genes<-length(common);diagnostics$interpretation<-'Reference-conditional labels; pruned labels remain NA, not biological negatives'
} else {
  suppressPackageStartupMessages(library(Seurat));obj<-readRDS(files$object)
  if(!inherits(obj,'Seurat')||anyDuplicated(colnames(obj))||anyDuplicated(rownames(obj))) stop('Unique real Seurat object required')
  meta<-obj[[]];needed<-unique(c(p$unit_key,p$sample_key,p$condition_key));if(!all(needed%in%names(meta))||anyNA(meta[,needed,drop=FALSE])) stop('Exact biological unit/sample/condition metadata required')
  for(s in unique(meta[[p$sample_key]])) if(length(unique(meta[meta[[p$sample_key]]==s,p$unit_key]))!=1||length(unique(meta[meta[[p$sample_key]]==s,p$condition_key]))!=1) stop('Technical sample maps to multiple units/conditions')
  DefaultAssay(obj)<-p$assay
  if(mode=='seurat_transfer') {
    ref<-readRDS(files$reference);if(!inherits(ref,'Seurat')||!p$reference_label_key%in%names(ref[[]])) stop('Actual labelled Seurat reference required')
    if(length(intersect(colnames(ref),colnames(obj)))) stop('Reference and query identities overlap')
    obj<-NormalizeData(obj,normalization.method='LogNormalize',scale.factor=p$target_sum,verbose=FALSE)
    anchors<-FindTransferAnchors(reference=ref,query=obj,normalization.method='LogNormalize',reference.assay=p$reference_assay,query.assay=p$assay,reference.reduction=p$reference_reduction,dims=seq_len(p$n_pcs),features=unlist(p$transfer_features),verbose=FALSE)
    predictions<-TransferData(anchorset=anchors,refdata=ref[[p$reference_label_key,drop=TRUE]],dims=seq_len(p$n_pcs),verbose=FALSE)
    if(!is.numeric(p$minimum_prediction_score)||p$minimum_prediction_score<0||p$minimum_prediction_score>1||!all(c('predicted.id','prediction.score.max')%in%colnames(predictions))) stop('Prespecified label-transfer confidence criterion required')
    predictions$accepted_label<-ifelse(predictions$prediction.score.max>=p$minimum_prediction_score,predictions$predicted.id,NA_character_)
    obj<-AddMetaData(obj,predictions);emit(predictions,'transferred_labels','annotation_scores');save_obj(anchors,'anchors.rds','anchor_object')
    diagnostics$reference_coverage<-'Explicit selected features; transferred labels require open-set and donor review';diagnostics$expression_modified_by_transfer<-FALSE
  } else if(mode=='hdwgcna_network') {
    suppressPackageStartupMessages(library(hdWGCNA))
    if(!p$celltype_key%in%names(meta)||anyNA(meta[[p$celltype_key]])) stop('Reviewed cell type annotations required')
    genes<-scan(files$network_genes,what=character(),quiet=TRUE)
    if(anyDuplicated(genes)||!all(genes%in%rownames(obj))||length(genes)>p$max_network_genes) stop('Select bounded exact non-DE-filtered network features')
    if(isTRUE(p$selected_by_de)) stop('Do not choose network genes by the target DE contrast')
    obj<-SetupForWGCNA(obj,wgcna_name='teaching_network',features=genes)
    obj<-MetacellsByGroups(obj,group.by=unique(c(p$celltype_key,p$unit_key,p$condition_key,p$sample_key)),ident.group=p$celltype_key,k=p$metacell_k,min_cells=p$minimum_cells,max_shared=p$max_shared,reduction=p$reduction,dims=seq_len(p$n_pcs),assay=p$assay,layer='counts',mode='sum',target_metacells=p$target_metacells)
    obj<-NormalizeMetacells(obj)
    obj<-SetDatExpr(obj,group_name=p$celltype,group.by=p$celltype_key,use_metacells=TRUE,assay=p$assay,layer='data')
    obj<-TestSoftPowers(obj,powers=unlist(p$powers),networkType=p$network_type)
    obj<-ConstructNetwork(obj,soft_power=p$selected_power,tom_outdir=file.path(out,'TOM'),tom_name='teaching',overwrite_tom=FALSE,maxBlockSize=p$max_block_size,networkType=p$network_type,TOMType=p$tom_type,randomSeed=p$seed,minModuleSize=p$minimum_module_size,mergeCutHeight=p$merge_cut_height)
    obj<-ModuleEigengenes(obj,group.by.vars=NULL,assay=p$assay)
    emit(GetModules(obj),'hdwgcna_modules','modules');emit(GetMEs(obj,harmonized=FALSE),'hdwgcna_eigengenes','module_eigengenes');emit(GetPowerTable(obj),'hdwgcna_power','soft_threshold')
    for(f in list.files(file.path(out,'TOM'),recursive=TRUE,full.names=TRUE)) outputs[[length(outputs)+1]]<-list(file=substring(f,nchar(out)+2),role='module_TOM')
    diagnostics$metacell_grouping<-unique(c(p$celltype_key,p$unit_key,p$condition_key,p$sample_key));diagnostics$independent_unit<-p$unit_key;diagnostics$n_network_genes<-length(genes);diagnostics$inference<-'Metacells not new donors; module-condition inference requires a separate unit-aware model'
  } else {
    raw<-GetAssayData(obj,assay=p$assay,layer='counts');raw_values<-if(inherits(raw,'sparseMatrix')) raw@x else as.vector(raw)
    if(any(!is.finite(raw_values))||any(raw_values<0)||any(raw_values!=floor(raw_values))) stop('Raw integer count layer required')
    qc<-read.delim(files$cell_qc,stringsAsFactors=FALSE);if(anyDuplicated(qc$cell_id)||!setequal(qc$cell_id,colnames(obj))||!all(tolower(as.character(qc$keep))%in%c('true','false'))) stop('Exact reviewed per-cell QC decisions required')
    qc<-qc[match(colnames(obj),qc$cell_id),];obj<-subset(obj,cells=colnames(obj)[tolower(as.character(qc$keep))=='true'])
    if(ncol(obj)<p$minimum_retained_cells) stop('Insufficient retained cells')
    obj<-NormalizeData(obj,normalization.method='LogNormalize',scale.factor=p$target_sum,verbose=FALSE);obj<-FindVariableFeatures(obj,selection.method='vst',nfeatures=p$hvg_count,verbose=FALSE);obj<-ScaleData(obj,features=VariableFeatures(obj),verbose=FALSE)
    obj<-RunPCA(obj,features=VariableFeatures(obj),npcs=p$n_pcs,seed.use=p$seed,verbose=FALSE);emit(Embeddings(obj,'pca'),'unintegrated_pca','unintegrated_baseline')
    reduction<-'pca'
    if(mode=='harmony_integrate') {
      if(!all(unlist(p$batch_keys)%in%names(obj[[]]))||anyNA(obj[[]][,unlist(p$batch_keys),drop=FALSE])) stop('Missing explicit batch covariates')
      obj<-harmony::RunHarmony(obj,group.by.vars=unlist(p$batch_keys),reduction.use='pca',dims.use=seq_len(p$n_pcs),theta=p$theta,max_iter_harmony=p$max_iterations,verbose=FALSE)
      reduction<-'harmony';emit(Embeddings(obj,'harmony'),'harmony_latent','integrated_representation');diagnostics$integration_acceptance<-'Batch mixing and biological preservation separately unassessed by this execution'
    } else if(mode!='seurat_workflow') stop('Unknown native R route')
    obj<-FindNeighbors(obj,reduction=reduction,dims=seq_len(p$n_pcs),k.param=p$neighbors,verbose=FALSE)
    obj<-FindClusters(obj,resolution=p$resolution,algorithm=p$cluster_algorithm,random.seed=p$seed,verbose=FALSE)
    obj<-RunUMAP(obj,reduction=reduction,dims=seq_len(p$n_pcs),seed.use=p$seed,verbose=FALSE)
    emit(obj[[]],'cell_metadata','cell_metadata');emit(Embeddings(obj,'umap'),'umap','embedding');diagnostics$disease_inference<-'Clusters and embeddings are descriptive; use original counts with donor-aware downstream models'
  }
  save_obj(obj,'processed_seurat.rds','processed_object')
  diagnostics$n_retained_cells<-ncol(obj);diagnostics$n_retained_features<-nrow(obj)
}
write_json(diagnostics,file.path(out,'diagnostics.json'),pretty=TRUE,auto_unbox=TRUE,na='null',null='null');outputs[[length(outputs)+1]]<-list(file='diagnostics.json',role='diagnostics')
capture.output(sessionInfo(),file=file.path(out,'R_session_info.txt'));outputs[[length(outputs)+1]]<-list(file='R_session_info.txt',role='backend_versions')
write_json(outputs,file.path(out,'native_r_outputs.json'),pretty=TRUE,auto_unbox=TRUE)
