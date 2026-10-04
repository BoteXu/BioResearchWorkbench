# Execute actual upstream methods on synthetic fixtures in CI, never private data.
stopifnot(requireNamespace('jsonlite',quietly=TRUE), requireNamespace('coloc',quietly=TRUE),
          requireNamespace('susieR',quietly=TRUE),requireNamespace('decoupleR',quietly=TRUE),requireNamespace('metafor',quietly=TRUE))
root<-normalizePath('.',mustWork=TRUE);tmp<-tempfile('scientific_fixture_');dir.create(tmp)
script<-file.path(root,'bridge','scientific_backend.R')
csv<-function(value,name) {p<-file.path(tmp,name);write.csv(value,p,row.names=FALSE);p}
matrix_csv<-function(m,name) csv(data.frame(id=rownames(m),m,check.names=FALSE),name)
run<-function(config,name,expect_success=TRUE) {
 config$output_directory<-file.path(tmp,name);config$seed<-1;config$context<-list(species='synthetic',model='fixture',assay='simulated',biological_unit='study',contrast='simulation',limitations='Synthetic execution only')
 path<-file.path(tmp,paste0(name,'.json'));jsonlite::write_json(config,path,auto_unbox=TRUE)
 status<-system2(file.path(R.home('bin'),'Rscript'),c(shQuote(script),shQuote(path)),stdout=file.path(tmp,paste0(name,'.stdout')),stderr=file.path(tmp,paste0(name,'.stderr')))
 if (expect_success && status!=0) {cat(readLines(file.path(tmp,paste0(name,'.stderr'))),sep='\n');stop('Scientific fixture execution failed')}
 if (!expect_success && (status==0 || file.exists(file.path(config$output_directory,'summary.json')))) stop('Invalid inputs unexpectedly completed')
 if (expect_success) {s<-jsonlite::fromJSON(file.path(config$output_directory,'summary.json'));stopifnot(s$state=='succeeded',s$qc$state=='pass');return(s)}
 invisible(NULL)
}
# coloc/susie: use the package's multi-signal simulation and exact named LD.
env<-new.env();data('coloc_test_data',package='coloc',envir=env)
a<-env$coloc_test_data$D3;b<-env$coloc_test_data$D4
table_trait<-function(d) data.frame(snp=as.character(d$snp),beta=d$beta,varbeta=d$varbeta,effect_allele='A',other_allele='C',position=d$position,MAF=d$MAF,build='synthetic',ancestry='synthetic')
if(is.null(a$position)) a$position<-seq_along(a$snp)
if(is.null(b$position)) b$position<-seq_along(b$snp)
if(is.null(a$MAF)) a$MAF<-rep(.2,length(a$snp))
if(is.null(b$MAF)) b$MAF<-rep(.2,length(b$snp))
dimnames(a$LD)<-list(as.character(a$snp),as.character(a$snp));dimnames(b$LD)<-list(as.character(b$snp),as.character(b$snp))
coloc_config<-list(backend='coloc_susie',trait1=csv(table_trait(a),'trait1.csv'),trait2=csv(table_trait(b),'trait2.csv'),
 ld1=matrix_csv(a$LD,'ld1.csv'),ld2=matrix_csv(b$LD,'ld2.csv'),genome_build='synthetic',ancestry='synthetic',ld_provenance='upstream simulated LD',coverage_description='complete simulation',
 trait1_type='quant',trait2_type='quant',N1=a$N,N2=b$N,sdY1=if(is.null(a$sdY)) 1 else a$sdY,sdY2=if(is.null(b$sdY)) 1 else b$sdY,
 priors=list(list(p1=1e-4,p2=1e-4,p12=1e-5),list(p1=1e-4,p2=1e-4,p12=1e-6)))
co<-run(coloc_config,'coloc');stopifnot(co$converged,length(co$prior_sensitivity)==2)
bad<-a$LD;rownames(bad)<-rev(rownames(bad));bad_config<-coloc_config;bad_config$ld1<-matrix_csv(bad,'badld.csv');run(bad_config,'bad_coloc',FALSE)
# decoupleR: signed independent regulators; compare actual ULM and MLM estimates.
set.seed(3);net<-data.frame(source=rep(c('TF_A','TF_B'),each=8),target=paste0('g',1:16),weight=rep(c(1,-1),8))
mat<-matrix(rnorm(16*4,sd=.15),16,4,dimnames=list(net$target,paste0('s',1:4)))
mat[1:8,]<-mat[1:8,]+outer(net$weight[1:8],c(2,2,-2,-2));mat[9:16,]<-mat[9:16,]+outer(net$weight[9:16],c(-1,-1,1,1))
dec<-list(backend='decoupler_activity',matrix=matrix_csv(mat,'expression.csv'),network=csv(net,'network.csv'),network_source='synthetic',network_version='1',input_scale='normalized_expression',min_targets=5,methods=list('ulm','mlm'))
de<-run(dec,'activity');stopifnot(nrow(de$agreement)==8,all(de$agreement$sign_agreement))
badnet<-net;badnet$weight[1]<-0;dec$network<-csv(badnet,'badnetwork.csv');run(dec,'bad_activity',FALSE)
# metafor: multiple correlated effects per independent study; covariance is explicit.
effects<-data.frame(effect_id=paste0('e',1:12),study_id=rep(paste0('study',1:6),each=2),yi=c(.1,.2,.3,.25,.4,.3,.2,.25,.5,.4,.3,.35),vi=rep(.04,12))
V<-diag(effects$vi);for(i in seq(1,12,2)){V[i,i+1]<-.01;V[i+1,i]<-.01};dimnames(V)<-list(effects$effect_id,effects$effect_id)
meta<-list(backend='metafor_multilevel',effects=csv(effects,'effects.csv'),covariance=matrix_csv(V,'covariance.csv'),effect_scale='mean difference',estimand='mean simulated effect',independent_unit='study',moderators=list(),dependence_description='two correlated effects per study, covariance supplied')
me<-run(meta,'meta');stopifnot(nrow(me$coefficients)==1,NROW(me$leave_one_study_out)==6)
badV<-V;diag(badV)<-1;meta$covariance<-matrix_csv(badV,'badV.csv');run(meta,'bad_meta',FALSE)
cat('SCIENTIFIC_BACKENDS_SYNTHETIC_PASS: coloc/susie convergence and prior grid; ULM/MLM agreement; multilevel covariance/leave-study-out; 3 QC refusals\n')
