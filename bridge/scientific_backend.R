# Fixed server adapters. Original methods are provided by coloc/susieR,
# decoupleR and metafor; this file supplies QC, orchestration and receipts.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==1, requireNamespace('jsonlite',quietly=TRUE))
c <- jsonlite::fromJSON(args[1],simplifyVector=FALSE)
out <- c$output_directory
if (dir.exists(out) || file.exists(out)) stop('Fresh output directory required')
dir.create(out,recursive=TRUE)
write_json <- function(value,name) jsonlite::write_json(value,file.path(out,name),auto_unbox=TRUE,pretty=TRUE,null='null')
read_csv <- function(path) {
  d <- read.csv(path,check.names=FALSE,stringsAsFactors=FALSE)
  if (anyDuplicated(names(d)) || nrow(d)==0) stop('Empty table or duplicate columns')
  d
}
numeric_finite <- function(x) is.numeric(x) && all(is.finite(x))
required <- function(d,names) if (!all(names %in% colnames(d))) stop('Missing required table columns')
unique_id <- function(x) if (anyNA(x) || any(!nzchar(as.character(x))) || anyDuplicated(x)) stop('Missing or duplicate IDs')
read_matrix <- function(path,ids=NULL) {
  d <- read_csv(path); unique_id(d[[1]])
  mat <- as.matrix(d[,-1,drop=FALSE]); storage.mode(mat)<-'double';rownames(mat)<-d[[1]]
  if (any(!is.finite(mat))) stop('Nonfinite matrix values')
  if (!is.null(ids) && (!identical(rownames(mat),ids) || !identical(colnames(mat),ids))) stop('Matrix order must exactly match effect/variant IDs')
  mat
}
qc <- list(state='started',backend=c$backend,context=c$context)
write_json(qc,'qc.json')
set.seed(as.integer(c$seed))
result <- tryCatch({
 if (c$backend=='coloc_susie') {
  stopifnot(requireNamespace('coloc',quietly=TRUE),requireNamespace('susieR',quietly=TRUE))
  a <- read_csv(c$trait1);b <- read_csv(c$trait2)
  for (d in list(a,b)) {
   required(d,c('snp','beta','varbeta','effect_allele','other_allele','position','MAF','build','ancestry'))
   unique_id(d$snp)
   if (!numeric_finite(d$beta) || !numeric_finite(d$varbeta) || any(d$varbeta<=0) ||
       !numeric_finite(d$MAF) || any(d$MAF<=0 | d$MAF>=1) || any(d$position<=0) ||
       any(d$build!=c$genome_build) || any(d$ancestry!=c$ancestry)) stop('Trait numeric/build/ancestry QC failed')
   if (any(!d$effect_allele %in% c('A','C','G','T')) || any(!d$other_allele %in% c('A','C','G','T')) || any(d$effect_allele==d$other_allele)) stop('Invalid alleles')
   if (any(paste0(d$effect_allele,d$other_allele) %in% c('AT','TA','CG','GC'))) stop('Resolve palindromic variants explicitly upstream')
  }
  if (!identical(a$snp,b$snp) || !identical(a$position,b$position) || !identical(a$effect_allele,b$effect_allele) || !identical(a$other_allele,b$other_allele)) stop('Harmonize trait variants, positions and effect alleles upstream')
  ld1<-read_matrix(c$ld1,a$snp);ld2<-read_matrix(c$ld2,b$snp)
  for (ld in list(ld1,ld2)) {
   if (nrow(ld)!=ncol(ld) || max(abs(ld-t(ld)))>1e-6 || max(abs(diag(ld)-1))>1e-6 || any(abs(ld)>1+1e-6) || min(eigen(ld,symmetric=TRUE,only.values=TRUE)$values)< -1e-6) stop('LD correlation matrix QC failed')
  }
  dataset <- function(d,ld,type,N,sdY,s) {
   x<-list(beta=d$beta,varbeta=d$varbeta,snp=d$snp,position=d$position,MAF=d$MAF,LD=ld,type=type,N=N)
   if (type=='quant') {if (is.null(sdY) || !is.finite(sdY) || sdY<=0) stop('Quantitative sdY required');x$sdY<-sdY}
   else {if (is.null(s) || s<=0 || s>=1) stop('Case fraction required');x$s<-s}
   coloc::check_dataset(x,req='LD');x
  }
  d1<-dataset(a,ld1,c$trait1_type,c$N1,c$sdY1,c$s1);d2<-dataset(b,ld2,c$trait2_type,c$N2,c$sdY2,c$s2)
  qc$state<-'pass';qc$n_variants<-nrow(a);qc$coverage<-c$coverage_description;qc$ld_provenance<-c$ld_provenance;write_json(qc,'qc.json')
  s1<-coloc::runsusie(d1);s2<-coloc::runsusie(d2)
  if (!isTRUE(s1$converged) || !isTRUE(s2$converged)) stop('SuSiE did not converge')
  sensitivity<-lapply(c$priors,function(p) {
   if (!all(c('p1','p2','p12') %in% names(p)) || any(unlist(p)<=0) || p$p12>min(p$p1,p$p2)) stop('Invalid prior grid')
   x<-coloc::coloc.susie(s1,s2,p1=p$p1,p2=p$p2,p12=p$p12)
   list(priors=p,summary=x$summary)
  })
  list(fit1=s1,fit2=s2,credible_sets1=summary(s1),credible_sets2=summary(s2),prior_sensitivity=sensitivity,converged=TRUE,
   interpretation='Signal-pair posterior is not proof of causality; inspect LD ancestry, sample overlap, variant coverage and prior sensitivity.')
 } else if (c$backend=='decoupler_activity') {
  stopifnot(requireNamespace('decoupleR',quietly=TRUE))
  mat<-read_matrix(c$matrix);net<-read_csv(c$network);required(net,c('source','target','weight'))
  if (anyNA(net$source) || anyNA(net$target) || any(!nzchar(net$source)) || any(!nzchar(net$target)) || !numeric_finite(net$weight) || any(net$weight==0) || anyDuplicated(paste(net$source,net$target,sep='::'))) stop('Invalid signed weighted network')
  if (!c$input_scale %in% c('normalized_expression','signed_statistic','log_fold_change')) stop('Unsupported input scale')
  overlap<-net[net$target %in% rownames(mat),,drop=FALSE];coverage<-aggregate(target~source,overlap,length)
  names(coverage)[2]<-'covered_targets'
  retained<-coverage$source[coverage$covered_targets>=c$min_targets]
  if (!length(retained)) stop('No regulator meets target-coverage QC')
  net<-net[net$source %in% retained,,drop=FALSE]
  qc$state<-'pass';qc$coverage<-coverage;qc$network_source<-c$network_source;qc$network_version<-c$network_version;write_json(qc,'qc.json')
  scores<-lapply(c$methods,function(m) {
   if (m=='ulm') decoupleR::run_ulm(mat,net,.source='source',.target='target',.mor='weight',minsize=c$min_targets)
   else if (m=='mlm') decoupleR::run_mlm(mat,net,.source='source',.target='target',.mor='weight',minsize=c$min_targets)
   else stop('Unsupported fixed method')
  });names(scores)<-unlist(c$methods)
  agreement<-NULL
  if (all(c('ulm','mlm') %in% names(scores))) {
   agreement<-merge(scores$ulm[,c('source','condition','score')],scores$mlm[,c('source','condition','score')],by=c('source','condition'),suffixes=c('_ulm','_mlm'))
   agreement$sign_agreement<-sign(agreement$score_ulm)==sign(agreement$score_mlm)
  }
  list(scores=scores,agreement=agreement,coverage=coverage,interpretation='Inferred network activity is not direct TF, pathway or kinase activity measurement. Sample columns are not automatically independent replicates.')
 } else if (c$backend=='metafor_multilevel') {
  stopifnot(requireNamespace('metafor',quietly=TRUE))
  d<-read_csv(c$effects);required(d,c('effect_id','study_id','yi','vi'));unique_id(d$effect_id)
  if (!numeric_finite(d$yi) || !numeric_finite(d$vi) || any(d$vi<=0) || anyNA(d$study_id) || any(!nzchar(d$study_id)) || length(unique(d$study_id))<3) stop('Insufficient independent studies or invalid effects/variances')
  V<-read_matrix(c$covariance,as.character(d$effect_id))
  if (max(abs(V-t(V)))>1e-8 || any(abs(diag(V)-d$vi)>1e-8) || min(eigen(V,symmetric=TRUE,only.values=TRUE)$values)<=0) stop('Invalid sampling covariance matrix')
  moderators<-unlist(c$moderators)
  if (length(moderators) && (any(!grepl('^[A-Za-z][A-Za-z0-9_]*$',moderators)) || !all(moderators %in% names(d)))) stop('Unsafe/missing moderator columns')
  mods<-if(length(moderators)) reformulate(moderators) else ~1
  mm<-model.matrix(mods,d)
  if (nrow(mm)!=nrow(d) || any(!is.finite(mm)) || qr(mm)$rank<ncol(mm)) stop('Missing or collinear moderators')
  if (length(unique(d$study_id))<=ncol(mm)+1) stop('Insufficient independent studies for moderator model')
  qc$state<-'pass';qc$studies<-length(unique(d$study_id));qc$effects<-nrow(d);qc$dependence<-c$dependence_description;write_json(qc,'qc.json')
  fit<-metafor::rma.mv(yi=yi,V=V,mods=mods,random=~1|study_id/effect_id,data=d,method='REML')
  leave<-lapply(unique(d$study_id),function(s) {
   keep<-d$study_id!=s
   tryCatch({f<-metafor::rma.mv(yi=yi,V=V[keep,keep,drop=FALSE],mods=mods,random=~1|study_id/effect_id,data=d[keep,,drop=FALSE],method='REML');list(excluded_study=s,coefficients=as.numeric(coef(f)),state='fit')},error=function(e)list(excluded_study=s,state='failed',reason=conditionMessage(e)))
  })
  list(fit=fit,coefficients=as.data.frame(coef(summary(fit))),prediction=predict(fit),leave_one_study_out=leave,residuals=residuals(fit),
    estimand=c$estimand,effect_scale=c$effect_scale,interpretation='Dependence and cohort overlap must be represented in the supplied covariance. Model diagnostics do not replace study-level bias and applicability review.')
 } else stop('Unknown fixed scientific adapter')
}, error=function(e) {write_json(list(state='failed',reason=conditionMessage(e)),'failure.json');stop(e)})
saveRDS(result,file.path(out,'results.rds'))
capture.output(sessionInfo(),file=file.path(out,'session.txt'))
summary <- list(state='succeeded',backend=c$backend,qc=qc,packages=lapply(c('jsonlite','coloc','susieR','decoupleR','metafor'),function(p)list(name=p,version=if(requireNamespace(p,quietly=TRUE)) as.character(packageVersion(p)) else NULL)),
   context=c$context,scientific_validity='requires_review',outputs=c('results.rds','session.txt','qc.json'))
if (c$backend=='coloc_susie') {summary$converged<-result$converged;summary$prior_sensitivity<-result$prior_sensitivity;summary$credible_sets1<-result$credible_sets1;summary$credible_sets2<-result$credible_sets2}
if (c$backend=='decoupler_activity') {summary$scores<-result$scores;summary$agreement<-result$agreement;summary$coverage<-result$coverage}
if (c$backend=='metafor_multilevel') {summary$coefficients<-result$coefficients;summary$leave_one_study_out<-result$leave_one_study_out;summary$prediction<-result$prediction}
summary$interpretation<-result$interpretation
write_json(summary,'summary.json')
