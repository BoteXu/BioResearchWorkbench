# Actual upstream model calls on reproducible synthetic data, plus QC refusal.
if(!requireNamespace('jsonlite',quietly=TRUE)) stop('jsonlite required')
root <- normalizePath(getwd());source <- file.path(root,'bridge','clinical_backend.R')
folder <- tempfile('clinical-check-');dir.create(folder);set.seed(403)
n <- 300;x <- rnorm(n);a <- rbinom(n,1,plogis(.2*x))
d <- data.frame(id=paste0('unit',seq_len(n)),age=x,treatment=a,outcome=2*a+.2*x+rnorm(n,.0,.3),time=rexp(n,exp(.3*x))+0.01,event=rbinom(n,1,.7),status=sample(0:2,n,replace=TRUE,prob=c(.2,.5,.3)))
write.csv(d,file.path(folder,'data.csv'),row.names=FALSE)
run <- function(backend,wrong=FALSE) {
 config <- list(data=file.path(folder,'data.csv'),unit_column='id',estimand=if(backend=='propensity_iptw') 'ATE_mean_difference' else 'fixture',covariates='age',missingness_policy='reject',design='cohort',statistical_plan_reviewed=TRUE,
   time_column='time',status_column=if(backend=='competing_risks')'status' else 'event',treatment_column='treatment',outcome_column='outcome',overlap_bounds=c(.01,.99),backend=backend,
   bootstrap_replications=100L,seed=403L,output_directory=file.path(folder,paste0(backend,if(wrong)'_refusal' else '_success')))
 if(wrong) config$statistical_plan_reviewed <- FALSE
 path <- file.path(folder,paste0(backend,if(wrong)'_bad' else '_good','.json'));jsonlite::write_json(config,path,auto_unbox=TRUE)
 status <- suppressWarnings(system2(file.path(R.home('bin'),'Rscript'),c(shQuote(source),shQuote(path)),stdout=TRUE,stderr=TRUE))
 exit <- attr(status,'status');if(is.null(exit))exit <- 0L
 if(wrong) {stopifnot(exit!=0L,file.exists(file.path(config$output_directory,'failure.json')));return(invisible(NULL))}
 if(exit!=0L) stop(paste(status,collapse='\n'))
 summary <- jsonlite::fromJSON(file.path(config$output_directory,'summary.json'))
 stopifnot(file.exists(file.path(config$output_directory,'results.rds')),isTRUE(jsonlite::fromJSON(file.path(config$output_directory,'qc.json'))$gate_pass))
 if(backend=='cox_survival') stopifnot(length(summary$coefficients)==1L,is.finite(summary$coefficients),length(summary$ph_test)>0)
 if(backend=='propensity_iptw') stopifnot(abs(summary$mean_difference-2)<.2,summary$effective_sample_size>100,nrow(summary$balance)==1L,length(summary$confidence_interval)==2,summary$bootstrap$successful>=90)
 if(backend=='competing_risks') stopifnot(length(summary$coefficients)==1L,is.finite(summary$coefficients))
}
for(backend in c('cox_survival','competing_risks','propensity_iptw')) {run(backend);run(backend,TRUE)}
cat('CLINICAL_ACTUAL_METHODS_AND_REFUSALS_PASS\n')
