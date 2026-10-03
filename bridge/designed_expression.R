args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==2)
folder <- args[[1]]; method <- args[[2]]
if (!requireNamespace('limma',quietly=TRUE)) stop('limma is required')
y <- as.matrix(read.csv(file.path(folder,'expression.csv'),row.names=1,check.names=FALSE))
design <- as.matrix(read.csv(file.path(folder,'design_matrix.csv'),row.names=1,check.names=FALSE))
contrast <- as.matrix(read.csv(file.path(folder,'contrast.csv'),row.names=1,check.names=FALSE))
stopifnot(identical(colnames(y),rownames(design)),identical(colnames(design),rownames(contrast)))
if (method=='limma_ebayes') {
  fit <- limma::eBayes(limma::contrasts.fit(limma::lmFit(y,design),contrast))
  tab <- limma::topTable(fit,coef=1,number=Inf,sort.by='none')
  exploratory <- y
  stat <- tab$t
} else {
  if (!requireNamespace('edgeR',quietly=TRUE)) stop('edgeR is required')
  dge <- edgeR::calcNormFactors(edgeR::DGEList(counts=y))
  exploratory <- edgeR::cpm(dge,log=TRUE,prior.count=1)
  if (method=='edgeR_ql') {
    dge <- edgeR::estimateDisp(dge,design)
    fit <- edgeR::glmQLFit(dge,design)
    test <- edgeR::glmQLFTest(fit,contrast=contrast[,1])
    raw <- edgeR::topTags(test,n=Inf,sort.by='none')$table
    tab <- data.frame(logFC=raw$logFC,AveExpr=raw$logCPM,P.Value=raw$PValue,adj.P.Val=raw$FDR,row.names=rownames(raw))
    stat <- sign(raw$logFC)*sqrt(raw$F)
  } else if (method=='limma_voom') {
    v <- limma::voom(dge,design,plot=FALSE)
    fit <- limma::eBayes(limma::contrasts.fit(limma::lmFit(v,design),contrast))
    tab <- limma::topTable(fit,coef=1,number=Inf,sort.by='none')
    stat <- tab$t
  } else stop('Unsupported method')
}
result <- data.frame(log2FoldChange=tab$logFC,mean_log_expression=tab$AveExpr,stat=stat,pvalue=tab$P.Value,padj=tab$adj.P.Val,row.names=rownames(tab))
write.csv(result,file.path(folder,'differential_expression.csv'))
write.csv(exploratory,file.path(folder,'exploratory_expression.csv'))
writeLines(paste('limma',utils::packageVersion('limma'),if (method!='limma_ebayes') paste('edgeR',utils::packageVersion('edgeR')) else ''),file.path(folder,'backend_version.txt'))
