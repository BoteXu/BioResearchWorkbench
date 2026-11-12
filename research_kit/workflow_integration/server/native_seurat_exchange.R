#!/usr/bin/env Rscript
# Exact observed-layer exchange, never an analysis or re-fit.
suppressPackageStartupMessages(library(jsonlite));r<-fromJSON(commandArgs(trailingOnly=TRUE)[1],simplifyVector=FALSE);p<-r$parameters;out<-r$out
for(pkg in c('Seurat','Matrix','jsonlite'))if(!requireNamespace(pkg,quietly=TRUE)||as.character(packageVersion(pkg))!=p$r_software_versions[[pkg]])stop(paste('Missing/different reviewed R package:',pkg))
obj<-readRDS(r$input);if(!inherits(obj,'Seurat')||anyDuplicated(rownames(obj))||anyDuplicated(colnames(obj)))stop('Actual unique Seurat axes required')
counts<-Seurat::GetAssayData(obj,assay=p$assay,layer='counts');expression<-Seurat::GetAssayData(obj,assay=p$assay,layer='data')
if(!identical(rownames(counts),rownames(expression))||!identical(colnames(counts),colnames(expression))||!identical(colnames(counts),colnames(obj)))stop('Observed and normalized layers do not have the same literal ordered axes; no padding or positional relabelling')
c<-if(inherits(counts,'sparseMatrix'))counts@x else as.vector(counts);e<-if(inherits(expression,'sparseMatrix'))expression@x else as.vector(expression)
if(any(!is.finite(c))||any(c<0)||any(c!=floor(c))||any(!is.finite(e))||any(e<0))stop('Actual integer counts and nonnegative log-normalized expression required')
if(p$normalization_scale!='log1p_normalized')stop('Explicit observed normalized-expression semantics required')
meta<-obj[[]];fields<-unlist(p$metadata_keys);if(!all(fields%in%names(meta))||!all(c(p$unit_key,p$sample_key,p$condition_key)%in%fields)||anyNA(meta[,c(p$unit_key,p$sample_key,p$condition_key),drop=FALSE]))stop('Explicit selected metadata and complete scientific identity fields required')
meta<-meta[colnames(counts),fields,drop=FALSE];for(k in c(p$unit_key,p$sample_key,p$condition_key))meta[[k]]<-as.character(meta[[k]])
Matrix::writeMM(as(counts,'dgCMatrix'),file.path(out,'counts.mtx'));Matrix::writeMM(as(expression,'dgCMatrix'),file.path(out,'log_expression.mtx'))
write_json(list(gene_ids=rownames(counts),cell_ids=colnames(counts)),file.path(out,'axes.json'),auto_unbox=FALSE);write_json(meta,file.path(out,'metadata.json'),dataframe='rows',auto_unbox=TRUE,na='null')
reductions<-unlist(p$reduction_names);map<-list()
for(i in seq_along(reductions)){
  key<-reductions[i];if(!key%in%Seurat::Reductions(obj))stop('Requested actual reduction absent')
  z<-Seurat::Embeddings(obj,key);if(!identical(rownames(z),colnames(counts))||any(!is.finite(z)))stop('Actual reduction does not match exact cell order')
  fn<-paste0('reduction_',i,'.tsv');write.table(z,file.path(out,fn),sep='\t',quote=FALSE,row.names=FALSE,col.names=FALSE);map[[key]]<-fn
}
write_json(map,file.path(out,'reductions.json'),auto_unbox=TRUE);capture.output(sessionInfo(),file=file.path(out,'R_session_info.txt'))
