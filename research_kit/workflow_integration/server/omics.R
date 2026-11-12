#!/usr/bin/env Rscript
# Scientific execution is invoked only behind runtime.py's server guard.
suppressPackageStartupMessages(library(jsonlite))
args <- commandArgs(trailingOnly=TRUE); request <- fromJSON(args[[1]], simplifyVector=FALSE)
p <- request$parameters; files <- request$inputs; out <- request$out
outputs <- list()
emit <- function(value,name,role,row_names=FALSE) {
  if (file.exists(file.path(out,name))) stop('Existing result must not be overwritten')
  write.table(value,file.path(out,name),sep='\t',quote=FALSE,row.names=row_names,col.names=if(row_names) NA else TRUE)
  outputs[[length(outputs)+1]] <<- list(file=name,role=role)
}
jwrite <- function(value,name,role) {
  write_json(value,file.path(out,name),pretty=TRUE,auto_unbox=TRUE,na='null',null='null')
  outputs[[length(outputs)+1]] <<- list(file=name,role=role)
}
readmat <- function(path) {
  x <- read.delim(path,row.names=1,check.names=FALSE,stringsAsFactors=FALSE)
  if (anyDuplicated(rownames(x))||anyDuplicated(colnames(x))||!all(vapply(x,is.numeric,TRUE))) stop('Unique numeric features x samples required')
  as.matrix(x)
}
method <- p$method
set.seed(p$seed)
diagnostics <- list(method=method,scientific_validity='not_established',missing_values_imputed=FALSE)
if(method %in% c('DESeq2','limma','WGCNA','edgeR_QL','limma_voom')) {
  mat <- readmat(files$matrix); meta <- read.delim(files$metadata,check.names=FALSE,stringsAsFactors=FALSE)
  sid <- meta[[p$sample_key]]; uid <- meta[[p$unit_key]]
  if (anyNA(sid)||anyNA(uid)||anyDuplicated(sid)||!setequal(sid,colnames(mat))) stop('Exact unique sample identity required; no silent intersection')
  meta <- meta[match(colnames(mat),sid),,drop=FALSE];uid <- meta[[p$unit_key]]
  if(any(is.infinite(mat))) stop('Infinite values')
  if(!isTRUE(p$paired)&&anyDuplicated(uid)) stop('Independent-unit reuse requires a specific repeated model')
  if(method!='WGCNA') {
    group <- factor(meta[[p$condition_key]])
    if(!p$case %in% levels(group)||!p$control %in% levels(group)||p$case==p$control) stop('Explicit contrast not found')
    independent <- tapply(uid,group,function(v)length(unique(v)))
    if(any(independent[c(p$case,p$control)]<p$minimum_units)) stop('Independent support below prespecified design minimum')
    if(isTRUE(p$paired)) {
      a <- uid[group==p$case];b <- uid[group==p$control]
      if(anyDuplicated(a)||anyDuplicated(b)||!setequal(a,b)) stop('Paired design is incomplete or duplicated')
    }
    covariates <- unlist(p$covariates)
    if(length(covariates)&&any(!grepl('^[A-Za-z][A-Za-z0-9_]*$',covariates))) stop('Unsafe covariate name')
    data <- data.frame(group=group,check.names=FALSE)
    for(k in covariates) {
      if(anyNA(meta[[k]])) stop('Missing covariate; choose a separate reviewed missingness model')
      data[[k]] <- if(p$covariate_types[[k]]=='numeric') as.numeric(meta[[k]]) else factor(meta[[k]])
    }
    if(isTRUE(p$paired)) data$subject <- factor(uid)
    rownames(data) <- colnames(mat)
    terms <- c('group',covariates,if(isTRUE(p$paired)) 'subject')
    form <- reformulate(terms,intercept=FALSE)
    design <- model.matrix(form,data=data)
    if(qr(design)$rank<ncol(design)||nrow(design)<=ncol(design)) stop('Rank deficient/confounded or no residual degrees of freedom')
    contrast <- rep(0,ncol(design));names(contrast)<-colnames(design)
    if(!all(c(paste0('group',p$case),paste0('group',p$control)) %in% names(contrast))) stop('Group labels do not map exactly to model columns')
    contrast[paste0('group',p$case)]<-1;contrast[paste0('group',p$control)]<--1
    emit(data.frame(sample_id=colnames(mat),group=group,unit_id=uid),'sample_identity.tsv','sample_identity')
    emit(design,'design_matrix.tsv','design_matrix',TRUE)
    diagnostics$independent_units <- independent;diagnostics$design_rank <- qr(design)$rank
  }
}
if(method=='DESeq2') {
  suppressPackageStartupMessages(library(DESeq2))
  if(p$scale!='raw_counts'||anyNA(mat)||any(mat<0)||any(mat!=floor(mat))) stop('DESeq2 requires explicit nonnegative raw integer counts')
  if(any(colSums(mat)==0)) stop('Empty count library')
  emit(data.frame(sample_id=colnames(mat),library_size=colSums(mat),detected_genes=colSums(mat>0)),'library_qc.tsv','sample_qc')
  keep <- rowSums(mat>=p$min_count)>=p$min_samples
  emit(data.frame(feature_id=rownames(mat),retained=keep),'feature_filter.tsv','feature_filter')
  if(!any(keep)) stop('No eligible genes')
  dds <- DESeqDataSetFromMatrix(mat[keep,,drop=FALSE],data,design=design)
  dds <- DESeq(dds,sfType=p$size_factor_type,quiet=FALSE)
  result <- results(dds,contrast=contrast,alpha=p$fdr,independentFiltering=TRUE)
  emit(data.frame(feature_id=rownames(result),as.data.frame(result),check.names=FALSE),'differential.tsv','differential')
  normalized <- counts(dds,normalized=TRUE);emit(normalized,'normalized_counts.tsv','normalization',TRUE)
  vst <- assay(varianceStabilizingTransformation(dds,blind=FALSE))
  emit(vst,'vst_expression.tsv','transformed_expression',TRUE)
  emit(cor(vst,method='spearman'),'sample_correlation.tsv','correlation',TRUE)
  pcs <- prcomp(t(vst),center=TRUE,scale.=FALSE)
  emit(pcs$x,'pca_scores.tsv','pca_scores',TRUE)
  diagnostics$dispersion <- summary(dispersions(dds));diagnostics$size_factors <- sizeFactors(dds)
  diagnostics$na_pvalue <- sum(is.na(result$pvalue));diagnostics$na_padj <- sum(is.na(result$padj));diagnostics$reference_contrast <- paste(p$case,'minus',p$control)
  diagnostics$package_version <- as.character(packageVersion('DESeq2'))
} else if(method %in% c('edgeR_QL','limma_voom')) {
  suppressPackageStartupMessages(library(edgeR));suppressPackageStartupMessages(library(limma))
  if(!p$normalization_method%in%c('TMM','TMMwsp','RLE','upperquartile','none')||!is.logical(p$robust)||length(p$robust)!=1) stop('Explicit supported count normalization and boolean robust choice required')
  if(method=='limma_voom'&&(!is.numeric(p$confidence_level)||length(p$confidence_level)!=1||!is.finite(p$confidence_level)||p$confidence_level<=0||p$confidence_level>=1)) stop('Confidence level must be in (0,1)')
  if(p$scale!='raw_counts'||anyNA(mat)||any(mat<0)||any(mat!=floor(mat))||any(colSums(mat)==0)) stop('Count-aware branch requires actual nonnegative integer counts and nonempty libraries')
  y<-DGEList(counts=mat);keep<-filterByExpr(y,design=design,min.count=p$min_count,min.total.count=p$min_total_count)
  emit(data.frame(feature_id=rownames(mat),retained=keep),'feature_filter.tsv','feature_filter')
  if(!any(keep)) stop('No eligible genes after design-aware filtering')
  y<-calcNormFactors(y[keep,,keep.lib.sizes=FALSE],method=p$normalization_method)
  emit(data.frame(sample_id=colnames(y),y$samples),'normalization_factors.tsv','normalization')
  emit(data.frame(sample_id=colnames(mat),library_size=colSums(mat),detected_genes=colSums(mat>0)),'library_qc.tsv','sample_qc')
  if(method=='edgeR_QL') {
    y<-estimateDisp(y,design,robust=isTRUE(p$robust));fit<-glmQLFit(y,design,robust=isTRUE(p$robust));test<-glmQLFTest(fit,contrast=contrast)
    tab<-topTags(test,n=Inf,sort.by='none')$table
    diagnostics$uncertainty<-'QL F test and FDR; coefficient confidence intervals not generated by this adapter'
    diagnostics$dispersion<-summary(y$tagwise.dispersion);diagnostics$package_version<-as.character(packageVersion('edgeR'))
  } else {
    v<-voom(y,design,plot=FALSE);fit<-eBayes(contrasts.fit(lmFit(v,design),contrast),robust=isTRUE(p$robust))
    tab<-topTable(fit,number=Inf,sort.by='none',confint=p$confidence_level)
    emit(v$weights,'voom_weights.tsv','precision_weights',TRUE)
    diagnostics$package_version<-as.character(packageVersion('limma'));diagnostics$confidence_level<-p$confidence_level
  }
  emit(data.frame(feature_id=rownames(tab),tab),'differential.tsv','differential')
  diagnostics$reference_contrast<-paste(p$case,'minus',p$control);diagnostics$filter_method<-'edgeR filterByExpr with the actual design'
} else if(method=='limma') {
  suppressPackageStartupMessages(library(limma))
  if(p$scale!='log2_normalized') stop('Intensity backend requires explicitly reviewed log2 scale; no automatic log/imputation')
  observed <- rowSums(!is.na(mat));keep <- observed>=p$min_samples
  emit(data.frame(feature_id=rownames(mat),observed_samples=observed,retained=keep),'feature_filter.tsv','feature_filter')
  emit(data.frame(sample_id=colnames(mat),missing_fraction=colMeans(is.na(mat)),median_intensity=apply(mat,2,median,na.rm=TRUE)),'intensity_qc.tsv','sample_qc')
  fit <- contrasts.fit(lmFit(mat[keep,,drop=FALSE],design),contrast)
  if(p$inference=='treat') fit <- treat(fit,lfc=p$minimum_log2_effect,trend=isTRUE(p$trend),robust=isTRUE(p$robust)) else fit <- eBayes(fit,trend=isTRUE(p$trend),robust=isTRUE(p$robust))
  tab <- if(p$inference=='treat') topTreat(fit,number=Inf,sort.by='none') else topTable(fit,number=Inf,sort.by='none')
  emit(data.frame(feature_id=rownames(tab),tab),'differential.tsv','differential')
  diagnostics$package_version <- as.character(packageVersion('limma'));diagnostics$na_pvalue <- sum(is.na(tab$P.Value))
} else if(method %in% c('ORA','fgsea')) {
  lines <- strsplit(readLines(files$gene_sets),'\t',fixed=TRUE)
  if(any(lengths(lines)<3)||anyDuplicated(vapply(lines,`[[`,'',1))) stop('Invalid/duplicated GMT sets')
  sets <- setNames(lapply(lines,function(x)unique(x[-c(1,2)])),vapply(lines,`[[`,'',1))
  if(method=='ORA') {
    universe <- unique(read.delim(files$universe,stringsAsFactors=FALSE)$gene_id)
    foreground <- read.delim(files$foreground,stringsAsFactors=FALSE)$gene_id
    if(anyDuplicated(foreground)||!all(foreground%in%universe)) stop('Foreground must be unique subset of actual tested universe')
    sets <- lapply(sets,intersect,y=universe);sizes <- lengths(sets);sets <- sets[sizes>=p$min_set_size & sizes<=p$max_set_size]
    rows <- lapply(names(sets),function(id){s<-sets[[id]];overlap<-intersect(s,foreground);data.frame(set_id=id,overlap=length(overlap),set_size=length(s),foreground_size=length(foreground),universe_size=length(universe),pvalue=phyper(length(overlap)-1,length(s),length(universe)-length(s),length(foreground),lower.tail=FALSE),genes=paste(overlap,collapse=';'))})
    if(!length(rows)) stop('No eligible gene sets')
    tab <- do.call(rbind,rows);tab$fdr<-p.adjust(tab$pvalue,'BH');emit(tab,'enrichment.tsv','enrichment')
  } else {
    suppressPackageStartupMessages(library(fgsea))
    ranking <- read.delim(files$ranking,stringsAsFactors=FALSE)
    if(anyDuplicated(ranking$gene_id)||any(!is.finite(ranking$rank_value))) stop('Unique finite signed full ranking required')
    ranks <- setNames(ranking$rank_value,ranking$gene_id)
    if(!is.numeric(p$gsea_param)||length(p$gsea_param)!=1||!is.finite(p$gsea_param)||p$gsea_param<0) stop('Explicit nonnegative GSEA weighting exponent required')
    ranks<-sort(ranks,decreasing=TRUE)
    tab <- fgseaMultilevel(sets,ranks,minSize=p$min_set_size,maxSize=p$max_set_size,eps=p$eps,gseaParam=p$gsea_param)
    requested_tracks<-unlist(p$plot_set_ids)
    if(length(requested_tracks)>20||anyDuplicated(requested_tracks)) stop('Choose at most 20 unique GSEA sets for full track export; full enrichment table remains complete')
    diagnostics$unavailable_requested_tracks<-setdiff(requested_tracks,tab$pathway)
    tracks<-lapply(intersect(requested_tracks,tab$pathway),function(id) {
      hit<-names(ranks)%in%sets[[id]];nh<-sum(hit);n<-length(ranks)
      if(nh==0||nh==n) return(NULL)
      w<-abs(ranks)^p$gsea_param;den<-sum(w[hit])
      if(den<=0) return(NULL)
      running<-cumsum(ifelse(hit,w/den,-1/(n-nh)))
      data.frame(set_id=id,rank_index_0=seq_along(ranks)-1L,gene_id=names(ranks),rank_metric=as.numeric(ranks),is_hit=hit,running_ES=running)
    })
    if(length(Filter(Negate(is.null),tracks))) emit(do.call(rbind,tracks),'gsea_tracks.tsv','rank_hit_tracks')
    tab$leadingEdge <- vapply(tab$leadingEdge,paste,collapse=';',FUN.VALUE='')
    emit(as.data.frame(tab),'enrichment.tsv','enrichment');diagnostics$rank_ties<-sum(duplicated(ranks));diagnostics$gsea_param<-p$gsea_param
  }
  diagnostics$null_model<-p$null_model;diagnostics$multiplicity_family<-p$multiplicity_family;diagnostics$gene_set_version<-p$gene_set_version
} else if(method=='WGCNA') {
  suppressPackageStartupMessages(library(WGCNA))
  if(p$scale!='log2_normalized'||anyNA(mat)||any(!is.finite(mat))||anyDuplicated(uid)) stop('Network backend needs finite reviewed transformed expression and independent units')
  if(ncol(mat)<p$minimum_units||isTRUE(p$selected_by_de)) stop('Insufficient network units or circular DE-selected gene input')
  dat <- t(mat);quality<-goodSamplesGenes(dat,verbose=0)
  emit(data.frame(feature_id=colnames(dat),good=quality$goodGenes),'network_gene_qc.tsv','network_qc')
  if(!quality$allOK) stop('Resolve bad samples/genes explicitly before network fitting')
  soft <- pickSoftThreshold(dat,powerVector=unlist(p$powers),networkType=p$network_type,verbose=0)
  emit(soft$fitIndices,'soft_threshold.tsv','soft_threshold')
  net <- blockwiseModules(dat,power=p$selected_power,networkType=p$network_type,TOMType=p$tom_type,
     minModuleSize=p$minimum_module_size,mergeCutHeight=p$merge_cut_height,numericLabels=FALSE,maxBlockSize=p$max_block_size,
     saveTOMs=FALSE,verbose=0)
  emit(data.frame(feature_id=colnames(dat),module=net$colors),'modules.tsv','modules')
  emit(net$MEs,'eigengenes.tsv','module_eigengenes',TRUE)
  membership <- cor(dat,net$MEs);emit(membership,'membership.tsv','module_membership',TRUE)
  sample_tree<-hclust(dist(dat),method='average')
  saveRDS(list(sample_tree=sample_tree,gene_dendrograms=net$dendrograms,block_genes=net$blockGenes,colors=net$colors,eigengenes=net$MEs,
               gene_ids=colnames(dat),sample_ids=rownames(dat),network_type=p$network_type,TOM_type=p$tom_type,power=p$selected_power),file.path(out,'network_plot_objects.rds'))
  outputs[[length(outputs)+1]]<-list(file='network_plot_objects.rds',role='network_plot_objects')
  diagnostics$TOM_export<-'not_selected; no substitute or unrelated heatmap generated'
  if(!is.null(p$tom_export_blocks)) {
    blocks<-unlist(p$tom_export_blocks)
    if(anyDuplicated(blocks)||any(blocks!=floor(blocks))||any(blocks<1)||any(blocks>length(net$blockGenes))||is.null(p$max_tom_genes)) stop('Select exact bounded TOM blocks')
    for(b in blocks) {
      ids<-net$blockGenes[[b]]
      if(length(ids)>p$max_tom_genes) stop('Selected TOM block exceeds reviewed server output budget')
      tom<-TOMsimilarityFromExpr(dat[,ids,drop=FALSE],power=p$selected_power,networkType=p$network_type,TOMType=p$tom_type,verbose=0)
      dimnames(tom)<-list(colnames(dat)[ids],colnames(dat)[ids]);name<-paste0('TOM_block_',b,'.rds');saveRDS(tom,file.path(out,name));outputs[[length(outputs)+1]]<-list(file=name,role='module_TOM')
    }
    diagnostics$TOM_export<-'Actual selected block TOM; same source axis and network parameters; color clipping is presentation only'
  }
  if(!is.null(files$traits)) {
    traits<-read.delim(files$traits,row.names=1,check.names=FALSE)
    if(!setequal(rownames(traits),rownames(dat))||!all(vapply(traits,is.numeric,TRUE))) stop('Trait matrix identity/scale mismatch')
    traits<-as.matrix(traits[rownames(dat),,drop=FALSE]);if(any(!is.finite(traits))) stop('Missing trait requires separately reviewed model')
    r<-cor(net$MEs,traits);pv<-corPvalueStudent(r,nrow(dat))
    tab<-expand.grid(module=rownames(r),trait=colnames(r),stringsAsFactors=FALSE)
    tab$correlation<-as.vector(r);tab$pvalue<-as.vector(pv);tab$fdr<-p.adjust(tab$pvalue,'BH')
    emit(tab,'module_traits.tsv','module_trait_association')
  }
  if(!is.null(files$reference_matrix)) {
    ref<-readmat(files$reference_matrix);rm<-read.delim(files$reference_metadata,check.names=FALSE)
    if(anyDuplicated(rm[[p$unit_key]])||anyDuplicated(rm[[p$sample_key]])||!setequal(rm[[p$sample_key]],colnames(ref))) stop('Independent reference identity invalid')
    if(length(intersect(uid,rm[[p$unit_key]]))) stop('Discovery and preservation reference units overlap')
    if(!setequal(rownames(ref),colnames(dat))) stop('Preservation requires explicitly reconciled feature set, no silent intersection')
    ref<-t(ref[colnames(dat),,drop=FALSE]);if(any(!is.finite(ref))) stop('Nonfinite preservation reference')
    mp<-modulePreservation(list(discovery=list(data=dat),validation=list(data=ref)),list(discovery=net$colors),referenceNetworks=1,
                           nPermutations=p$preservation_permutations,randomSeed=p$seed,verbose=0)
    saveRDS(mp,file.path(out,'preservation.rds'));outputs[[length(outputs)+1]]<-list(file='preservation.rds',role='module_preservation_full')
    emit(mp$preservation$Z[[1]][[2]],'preservation_z.tsv','module_preservation',TRUE)
    diagnostics$preservation<-'assessed on independent reference; interpret Z with module size and permutation uncertainty'
  }
  diagnostics$selected_power<-p$selected_power;diagnostics$package_version<-as.character(packageVersion('WGCNA'))
  if(is.null(diagnostics$preservation)) diagnostics$preservation<-'not_assessed_without_independent_reference'
  diagnostics$hub_interpretation<-'association, not causal target evidence'
} else if(method=='MOFA2') {
  suppressPackageStartupMessages(library(MOFA2))
  view_ids <- unlist(p$view_ids);views<-lapply(view_ids,function(id)readmat(files[[id]]));names(views)<-view_ids
  samples<-unlist(p$sample_axis)
  for(k in names(views)) {
    if(!setequal(colnames(views[[k]]),samples)) stop('Explicit aligned sample axis including missing views required')
    views[[k]]<-views[[k]][,samples,drop=FALSE]
    if(any(is.infinite(views[[k]]))||any(rowSums(!is.na(views[[k]]))==0)) stop('Infinite or entirely missing feature')
  }
  if(any(Reduce(`+`,lapply(views,function(x)colSums(!is.na(x))))==0)) stop('A sample has no observed modality')
  fit<-create_mofa(views);mopt<-get_default_model_options(fit);mopt$num_factors<-p$num_factors
  dopt<-get_default_data_options(fit);dopt$scale_views<-isTRUE(p$scale_views)
  topt<-get_default_training_options(fit);topt$seed<-p$seed;topt$maxiter<-p$max_iterations
  fit<-prepare_mofa(fit,data_options=dopt,model_options=mopt,training_options=topt)
  fit<-run_mofa(fit,outfile=file.path(out,'model.hdf5'),use_basilisk=FALSE)
  factors<-get_factors(fit);for(k in names(factors)) emit(factors[[k]],paste0('factors_',k,'.tsv'),'factor_scores',TRUE)
  weights<-get_weights(fit);for(k in names(weights)) emit(weights[[k]],paste0('weights_',k,'.tsv'),'factor_loadings',TRUE)
  jwrite(get_variance_explained(fit),'view_variance.json','view_variance')
  outputs[[length(outputs)+1]]<-list(file='model.hdf5',role='model_artifact')
  diagnostics$package_version<-as.character(packageVersion('MOFA2'));diagnostics$missingness<-lapply(views,function(x)mean(is.na(x)))
  diagnostics$factor_association<-'separate prespecified unit-aware test required; not inferred from latent separation'
} else stop('Unknown fixed R method')
jwrite(diagnostics,'diagnostics.json','diagnostics')
capture.output(sessionInfo(),file=file.path(out,'R_session_info.txt'))
outputs[[length(outputs)+1]]<-list(file='R_session_info.txt',role='backend_versions')
write_json(outputs,file.path(out,'r_outputs.json'),auto_unbox=TRUE,pretty=TRUE)
cat('Completed fixed R backend:',method,'\n')
