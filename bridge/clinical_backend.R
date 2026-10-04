# Original fixed orchestration around upstream survival/cmprsk/base R methods.
args <- commandArgs(TRUE)
if (length(args)!=1L) stop('One config required')
if (!requireNamespace('jsonlite',quietly=TRUE)) stop('Existing jsonlite required')
c <- jsonlite::fromJSON(args[1],simplifyVector=TRUE)
out <- c$output_directory
if (dir.exists(out) || file.exists(out)) stop('Fresh output required')
dir.create(out,recursive=TRUE)
write_json <- function(x,name) jsonlite::write_json(x,file.path(out,name),auto_unbox=TRUE,pretty=TRUE,null='null',na='null')
tryCatch({
 d <- read.csv(c$data,check.names=FALSE,stringsAsFactors=FALSE)
 required <- unique(c(c$unit_column,c$covariates,if(c$backend=='propensity_iptw') c(c$treatment_column,c$outcome_column) else c(c$time_column,c$status_column)))
 if (!all(required %in% names(d)) || anyDuplicated(names(d)) || nrow(d)<20) stop('Column/sample QC failed')
 if (anyNA(d[,required,drop=FALSE]) || any(d[[c$unit_column]]=='') || anyDuplicated(d[[c$unit_column]])) stop('Missing/duplicate independent unit')
 nums <- setdiff(required,c$unit_column)
 if (any(vapply(d[,nums,drop=FALSE],function(x)!is.numeric(x)||any(!is.finite(x)),logical(1)))) stop('Finite numeric columns required')
 if (!identical(c$statistical_plan_reviewed,TRUE) || c$missingness_policy!='reject' || !nzchar(c$estimand) || !nzchar(c$design)) stop('Reviewed design gate failed')
 qc <- list(gate_pass=TRUE,independent_units=nrow(d),estimand=c$estimand,missingness_policy=c$missingness_policy)
 covariates <- c$covariates
 rhs <- if(length(covariates)) paste(covariates,collapse='+') else '1'
 mm <- model.matrix(as.formula(paste('~',rhs)),d)
 if (qr(mm)$rank<ncol(mm)) stop('Rank-deficient covariates')
 if (c$backend=='cox_survival') {
   if (!requireNamespace('survival',quietly=TRUE)) stop('Existing survival required')
   t <- d[[c$time_column]];s <- d[[c$status_column]]
   if (any(t<=0)||!all(s %in% c(0,1))||sum(s)<10||sum(s)<=length(covariates)+2) stop('Event/time QC failed')
   f <- as.formula(paste('survival::Surv(',c$time_column,',',c$status_column,')~',rhs))
   fit <- survival::coxph(f,data=d,x=TRUE,y=TRUE,singular.ok=FALSE)
   if (any(!is.finite(coef(fit)))) stop('Nonfinite Cox estimates')
   ph <- survival::cox.zph(fit)
   summary <- list(backend=c$backend,coefficients=unname(coef(fit)),terms=names(coef(fit)),confidence_interval=unname(confint(fit)),ph_test=unname(ph$table),ph_terms=rownames(ph$table),events=sum(s),interpretation='association_under_declared_model')
   result <- list(model=fit,proportional_hazards=ph)
 } else if(c$backend=='competing_risks') {
   if (!requireNamespace('cmprsk',quietly=TRUE)) stop('Existing cmprsk required')
   t <- d[[c$time_column]];s <- d[[c$status_column]]
   if(any(t<=0)||!all(s %in% c(0,1,2))||sum(s==1)<10||sum(s==2)<1) stop('Explicit censor/target/competing statuses required')
   ci <- cmprsk::cuminc(t,s,cencode=0)
   result <- list(cumulative_incidence=ci)
   summary <- list(backend=c$backend,event_counts=as.list(table(factor(s,levels=0:2))),interpretation='cumulative_incidence_with_competing_event')
   if(length(covariates)) {
     x <- mm[,-1,drop=FALSE]
     fit <- cmprsk::crr(t,s,cov1=x,failcode=1,cencode=0)
     if(!isTRUE(fit$converged)||any(!is.finite(fit$coef))) stop('Fine-Gray did not converge')
     result$model <- fit;summary$coefficients <- unname(fit$coef);summary$standard_errors <- sqrt(diag(fit$var));summary$terms <- colnames(x)
   }
 } else if(c$backend=='propensity_iptw') {
   a <- d[[c$treatment_column]];y <- d[[c$outcome_column]]
   if(!all(a %in% c(0,1))||min(table(factor(a,levels=0:1)))<5||!length(covariates)) stop('Two treatment groups and covariates required')
   if(c$estimand!='ATE_mean_difference'||is.null(c$overlap_bounds)||length(c$overlap_bounds)!=2||any(c$overlap_bounds<=0)||any(c$overlap_bounds>=1)||c$overlap_bounds[1]>=c$overlap_bounds[2]) stop('Explicit ATE and overlap bounds required')
   psfit <- glm(as.formula(paste(c$treatment_column,'~',rhs)),family=binomial(),data=d)
   if(!psfit$converged||any(!is.finite(coef(psfit)))) stop('Propensity model failed')
   p <- fitted(psfit)
   if(any(p<c$overlap_bounds[1]|p>c$overlap_bounds[2])) stop('Propensity overlap gate failed; no automatic trimming')
   w <- ifelse(a==1,1/p,1/(1-p))
   mean1 <- weighted.mean(y[a==1],w[a==1]);mean0 <- weighted.mean(y[a==0],w[a==0])
   smd <- function(x,weights) {
     m <- sapply(0:1,function(g)weighted.mean(x[a==g],weights[a==g]))
     v <- sapply(0:1,function(g)weighted.mean((x[a==g]-m[g+1])^2,weights[a==g]))
     den <- sqrt(mean(v));if(den==0) if(diff(m)==0) 0 else Inf else (m[2]-m[1])/den
   }
   balance <- data.frame(covariate=covariates,unweighted=sapply(d[,covariates,drop=FALSE],smd,weights=rep(1,nrow(d))),weighted=sapply(d[,covariates,drop=FALSE],smd,weights=w))
   summary <- list(backend=c$backend,estimand=c$estimand,mean_difference=mean1-mean0,effective_sample_size=sum(w)^2/sum(w^2),weight_range=range(w),propensity_range=range(p),balance=balance,
      interpretation='requires_exchangeability_positivity_consistency_and_sensitivity_review')
   if(is.null(c$bootstrap_replications)||c$bootstrap_replications<100||c$bootstrap_replications>2000||c$bootstrap_replications!=as.integer(c$bootstrap_replications)||is.null(c$seed)) stop('Prespecified bounded bootstrap and seed required')
   set.seed(c$seed);replicates <- rep(NA_real_,c$bootstrap_replications)
   for(i in seq_along(replicates)) {
      indices <- sample.int(nrow(d),replace=TRUE);bd <- d[indices,,drop=FALSE];ba <- bd[[c$treatment_column]];by <- bd[[c$outcome_column]]
      replicates[i] <- tryCatch({
        fitb <- suppressWarnings(glm(as.formula(paste(c$treatment_column,'~',rhs)),family=binomial(),data=bd));pb <- fitted(fitb)
        if(!fitb$converged||length(unique(ba))<2||any(!is.finite(pb))||any(pb<=0|pb>=1)) stop('Bootstrap nuisance fit failed')
        wb <- ifelse(ba==1,1/pb,1/(1-pb))
        weighted.mean(by[ba==1],wb[ba==1])-weighted.mean(by[ba==0],wb[ba==0])
      },error=function(e)NA_real_)
   }
   summary$bootstrap <- list(requested=c$bootstrap_replications,successful=sum(is.finite(replicates)),failed=sum(!is.finite(replicates)),seed=c$seed,unit='independent_patient_rows',nuisance_refitted=TRUE)
   if(mean(is.finite(replicates))<.9)stop('Bootstrap failure rate requires review')
   summary$confidence_interval <- unname(quantile(replicates[is.finite(replicates)],c(.025,.975)))
   summary$uncertainty <- 'percentile_independent_unit_bootstrap_not_unmeasured_confounding'
   result <- list(propensity_model=psfit,weights=w,balance=balance)
 } else stop('Unknown clinical backend')
 write_json(qc,'qc.json');write_json(summary,'summary.json');saveRDS(result,file.path(out,'results.rds'));writeLines(capture.output(sessionInfo()),file.path(out,'session.txt'))
},error=function(e){write_json(list(gate_pass=FALSE,error=conditionMessage(e)),'failure.json');quit(status=1)})
