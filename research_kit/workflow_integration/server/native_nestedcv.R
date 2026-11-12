#!/usr/bin/env Rscript
# Native R nestedcv, real preassigned unit folds, no external test reuse.
suppressPackageStartupMessages(library(jsonlite))
r<-fromJSON(commandArgs(trailingOnly=TRUE)[1],simplifyVector=FALSE);p<-r$parameters;f<-r$inputs;out<-r$out;outputs<-list();set.seed(p$seed,'L\'Ecuyer-CMRG')
for(pkg in names(p$software_versions))if(!requireNamespace(pkg,quietly=TRUE)||as.character(packageVersion(pkg))!=p$software_versions[[pkg]])stop(paste('Different/missing existing package',pkg))
suppressPackageStartupMessages(library(nestedcv));suppressPackageStartupMessages(library(caret))
emit<-function(x,name,role){file<-paste0(name,'.tsv');write.table(x,file.path(out,file),sep='\t',quote=FALSE,row.names=TRUE,col.names=NA,na='NA');outputs[[length(outputs)+1]]<<-list(file=file,role=role)}
x<-as.matrix(read.delim(f$features,row.names=1,check.names=FALSE));storage.mode(x)<-'numeric';m<-read.delim(f$metadata,row.names=1,check.names=FALSE,colClasses='character');fold<-fromJSON(f$folds,simplifyVector=FALSE)
if(anyDuplicated(rownames(x))||anyDuplicated(colnames(x))||any(!is.finite(x))||!setequal(rownames(x),rownames(m))||!all(c(p$unit_key,p$outcome_key)%in%names(m)))stop('Finite selected independent-unit features and exact actual outcome metadata required')
m<-m[rownames(x),,drop=FALSE];if(anyNA(m)||anyDuplicated(m[[p$unit_key]])||any(!nzchar(m[[p$unit_key]])))stop('This branch supports one actual row per independent unit; repeated measures need a separately reviewed grouped model')
ids<-rownames(x);outer<-fold$outer_test_ids;inner<-fold$inner_test_ids;if(length(outer)<3||length(inner)!=length(outer))stop('At least three prespecified outer folds with corresponding nested inner folds required')
if(!setequal(unlist(outer),ids)||anyDuplicated(unlist(outer)))stop('Each real unit must appear in exactly one held-out outer fold')
outer_idx<-lapply(outer,function(v){if(!length(v)||!all(unlist(v)%in%ids))stop('Unknown outer unit identity');match(unlist(v),ids)})
inner_idx<-lapply(seq_along(outer),function(i){train_ids<-ids[-outer_idx[[i]]];tests<-inner[[i]];if(length(tests)<2||!setequal(unlist(tests),train_ids)||anyDuplicated(unlist(tests)))stop('Inner validation units must partition their own outer training set only');lapply(tests,function(v)match(unlist(v),train_ids))})
if(p$task=='binary_classification'){
  labels<-unlist(p$class_order);if(length(labels)!=2||anyDuplicated(labels)||!setequal(labels,unique(m[[p$outcome_key]]))||!identical(make.names(labels),labels)||p$positive_class!=labels[2])stop('Actual two caret-valid class labels with declared native second-level probability event required; no silent relabeling')
  y<-factor(m[[p$outcome_key]],levels=labels)
  check_classes<-function(ix){if(length(unique(y[ix]))!=2)stop('Every training and validation split must contain both actual classes')}
  for(i in seq_along(outer_idx)){oi<-outer_idx[[i]];ti<-setdiff(seq_along(ids),oi);check_classes(oi);check_classes(ti);for(ii in inner_idx[[i]]){check_classes(ti[ii]);check_classes(ti[-ii])}}
  control<-caret::trainControl(method='cv',classProbs=TRUE,summaryFunction=caret::twoClassSummary,savePredictions='final',allowParallel=FALSE);metric<-'ROC'
}else if(p$task=='regression'){
  y<-as.numeric(m[[p$outcome_key]]);if(any(!is.finite(y))||sd(y)==0)stop('Actual finite nonconstant continuous outcome required');control<-caret::trainControl(method='cv',savePredictions='final',allowParallel=FALSE);metric<-'RMSE'
}else stop('Unsupported native nestedcv task')
grid<-read.delim(f$tuning_grid,check.names=FALSE);if(!identical(sort(names(grid)),c('alpha','lambda'))||nrow(grid)<2||any(!is.finite(as.matrix(grid)))||any(grid$alpha<0|grid$alpha>1)||any(grid$lambda<=0)||anyDuplicated(grid))stop('Explicit finite multi-candidate glmnet tuning grid required')
# All centering/scaling and variance checks are performed by caret inside fits.
# No global supervised filter; only prespecified input features are admitted.
fit<-nestedcv::nestcv.train(y=y,x=x,method='glmnet',filterFUN=NULL,balance=NULL,outer_folds=outer_idx,inner_folds=inner_idx,cv.cores=p$workers,metric=metric,trControl=control,tuneGrid=grid,preProcess=c('nzv','center','scale'),outer_train_predict=FALSE,finalCV=NA,na.option='pass',savePredictions='final')
pred<-fit$output;if(is.null(pred)||!setequal(rownames(pred),ids)||anyDuplicated(rownames(pred)))stop('Native outer held-out predictions lack exact original unit identities')
pred<-pred[ids,,drop=FALSE];if(!'testy'%in%names(pred)||!identical(as.character(pred$testy),as.character(y)))stop('Native held-out outcome alignment changed')
if(p$task=='binary_classification'&&(!'predyp'%in%names(pred)||any(!is.finite(pred$predyp))||any(pred$predyp<0|pred$predyp>1)))stop('Actual native held-out probabilities required')
emit(pred,'nestedcv_outer_predictions','oof_predictions');emit(as.data.frame(fit$summary),'nestedcv_outer_summary','validation_metrics');emit(m,'nestedcv_unit_identity','split_identity')
saveRDS(fit,file.path(out,'nestedcv_native.rds'));outputs[[length(outputs)+1]]<-list(file='nestedcv_native.rds',role='model_object');write_json(fold,file.path(out,'nestedcv_folds.json'),pretty=TRUE,auto_unbox=TRUE);outputs[[length(outputs)+1]]<-list(file='nestedcv_folds.json',role='fold_provenance')
diag<-list(mode=r$mode,software_versions=p$software_versions,n_units=nrow(x),n_features=ncol(x),n_outer_folds=length(outer),outer_predictions_held_out=TRUE,final_full_data_fit=FALSE,scientific_acceptance='NOT_ESTABLISHED',interpretation='Native R nestedcv/caret glmnet with actual independent-unit outer/inner splits, fold-local preprocessing and no global supervised filter. OOF metrics assess this prespecified model workflow only; comparing many workflows on these same folds requires a separate selection-aware validation design. Not external or clinical validation.')
write_json(diag,file.path(out,'diagnostics.json'),pretty=TRUE,auto_unbox=TRUE);outputs[[length(outputs)+1]]<-list(file='diagnostics.json',role='diagnostics');capture.output(sessionInfo(),file=file.path(out,'R_session_info.txt'));outputs[[length(outputs)+1]]<-list(file='R_session_info.txt',role='backend_versions');write_json(outputs,file.path(out,'native_r_outputs.json'),pretty=TRUE,auto_unbox=TRUE)
