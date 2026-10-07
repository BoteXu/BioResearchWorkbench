# Isolated CI/public-server reference checks. No private data, local installation or clinical modelling.
suppressPackageStartupMessages(library(DESeq2))
suppressPackageStartupMessages(library(pasilla))
count_file <- system.file('extdata', 'pasilla_gene_counts.tsv', package='pasilla')
meta_file <- system.file('extdata', 'pasilla_sample_annotation.csv', package='pasilla')
counts <- as.matrix(read.csv(count_file, sep='\t', row.names='gene_id'))
meta <- read.csv(meta_file, row.names=1)
rownames(meta) <- sub('fb$', '', rownames(meta))
stopifnot(setequal(colnames(counts), rownames(meta)), all(counts>=0), all(counts==floor(counts)))
meta <- meta[colnames(counts),,drop=FALSE]
meta$condition <- relevel(factor(meta$condition), ref='untreated')
dds <- DESeqDataSetFromMatrix(counts, meta, design=~condition)
dds <- DESeq(dds, quiet=TRUE)
result <- results(dds, contrast=c('condition','treated','untreated'))
lfc <- result['FBgn0039155','log2FoldChange']; q <- result['FBgn0039155','padj']
stopifnot(is.finite(lfc), lfc>=-4.8, lfc<=-4.4, is.finite(q), q<1e-6)
t <- subset(datasets::ToothGrowth, dose==0.5)
estimate <- t.test(t$len[t$supp=='OJ'], t$len[t$supp=='VC'], paired=FALSE, var.equal=FALSE)
stopifnot(abs(diff(rev(estimate$estimate))-5.25)<1e-6, estimate$p.value>0.0063, estimate$p.value<0.0064)
out <- file.path(tempdir(),'bioresearch-public-benchmarks');dir.create(out,showWarnings=FALSE)
jsonlite::write_json(list(schema=1,benchmark_id='pasilla_deseq2',state='completed',exit_code=0,
  backend_version=as.character(packageVersion('DESeq2')),dataset_version=as.character(packageVersion('pasilla')),
  input_sha256=digest::digest(file=count_file,algo='sha256'),annotation_sha256=digest::digest(file=meta_file,algo='sha256'),
  design='~ condition; treated versus untreated; all supplied samples',metrics=list(FBgn0039155_log2_fold_change=unname(lfc),FBgn0039155_adjusted_pvalue=unname(q))),file.path(out,'pasilla.json'),auto_unbox=TRUE,digits=16)
jsonlite::write_json(list(schema=1,benchmark_id='toothgrowth_welch',state='completed',exit_code=0,
  backend_version=as.character(getRversion()),dataset_version=as.character(packageVersion('datasets')),
  input_sha256=digest::digest(t,algo='sha256'),design='dose 0.5 only; OJ minus VC; unpaired Welch',
  metrics=list(mean_difference=unname(diff(rev(estimate$estimate))),pvalue=estimate$p.value)),file.path(out,'welch.json'),auto_unbox=TRUE,digits=16)
cat('PUBLIC_PASILLA_DESEQ2_AND_WELCH_REFERENCE_CHECKS_OK\n')
