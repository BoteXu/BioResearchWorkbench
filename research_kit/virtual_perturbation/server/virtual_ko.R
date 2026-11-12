# Allocated-server only: preserve original method identity and model-conditional claims.
suppressPackageStartupMessages(library(jsonlite))
args<-commandArgs(TRUE);j<-fromJSON(args[1],simplifyVector=FALSE);out<-args[2];p<-j$parameters;I<-j$inputs;set.seed(p$seed)
if(Sys.info()[['sysname']]!='Linux' || grepl('microsoft',tolower(paste(readLines('/proc/version',warn=FALSE),collapse=' '))))stop('Scientific R workers cannot run locally')
script_file<-sub('^--file=','',commandArgs(FALSE)[grepl('^--file=',commandArgs(FALSE))])
guard_code<-file.path(dirname(normalizePath(script_file)), 'child_guard.py')
approved_python<-Sys.getenv('BRW_APPROVED_PYTHON');if(!nzchar(approved_python)||normalizePath(approved_python)!=normalizePath(j$python_executable))stop('Unapproved child interpreter')
if(system2(j$python_executable,c(shQuote(guard_code),shQuote(args[1])))!=0)stop('Scientific child differs from reviewed allocated-server request')
read_matrix<-function(f){h<-names(read.delim(f,nrows=0,check.names=FALSE));cl<-rep(NA_character_,length(h));cl[1]<-"character";z<-read.delim(f,check.names=FALSE,colClasses=cl);x<-as.matrix(z[,-1,drop=FALSE]);storage.mode(x)<-"double";rownames(x)<-z[[1]];if(anyDuplicated(rownames(x))||anyDuplicated(colnames(x))||any(!is.finite(x)))stop("Invalid KO matrix axes/values");x}
x<-read_matrix(I$matrix);m<-read.delim(I$samples,stringsAsFactors=FALSE,colClasses="character");if(!all(c("sample_id","unit_id")%in%names(m))||anyDuplicated(m$sample_id)||!setequal(m$sample_id,colnames(x)))stop("KO sample and independent-unit axes invalid");x<-x[,m$sample_id,drop=FALSE]
genes<-unlist(p$ko_genes);if(!length(genes)||anyDuplicated(genes)||!all(genes%in%rownames(x)))stop("Every selected KO gene must be present exactly once")
tables<-list();metrics<-list();pkg<-if(j$analysis_id=="bulk_virtual_ko")"bulkKnk"else"scTenifoldKnk"
if(!requireNamespace(pkg,quietly=TRUE))stop(paste("Missing existing server package",pkg))
if(as.character(packageVersion(pkg))!=p$expected_package_version)stop("Installed virtual-KO package version differs from reviewed plan")
write_json(list(package=pkg,version=as.character(packageVersion(pkg)),remote_sha=packageDescription(pkg)$RemoteSha,claims="model_conditional_prediction_not_observed_intervention"),file.path(out,"package_identity.private.json"),auto_unbox=TRUE,pretty=TRUE)
writeLines(capture.output(sessionInfo()),file.path(out,'R_session_info.private.txt'))
if(j$analysis_id=="bulk_virtual_ko"){
 if(anyDuplicated(m$unit_id)||any(x<0)||j$context$scale!="nonnegative_normalized_expression")stop("bulkKnk requires independent cohort units and an explicit nonnegative normalized linear scale")
 train<-m$unit_id%in%unlist(p$training_units);test<-m$unit_id%in%unlist(p$evaluation_units)
 if(any(train&test)||!all(train|test)||sum(train)<p$min_training_units||sum(test)<3)stop("Explicit disjoint complete training/evaluation cohort required")
 source_sha<-packageDescription("bulkKnk")$RemoteSha
 if(is.null(source_sha)||source_sha!="c49b106a4383e44ee19d08a75d7edcc99a865ea7")stop("bulkKnk source is not the reviewed commit; review its source before running")
 vars<-apply(x[,train,drop=FALSE],1,var);eligible<-names(vars)[is.finite(vars)&vars>0]
 if(!all(genes%in%eligible))stop("KO gene lacks training-cohort variation")
 ordered<-eligible[order(vars[eligible],decreasing=TRUE)];forced<-unique(c(genes,unlist(p$control_genes)));if(!all(forced%in%eligible))stop("KO/control genes lack training variation");features<-unique(c(forced,head(setdiff(ordered,forced),p$n_features-length(forced))))
 if(length(features)!=p$n_features||p$n_features<=length(forced))stop("Explicit frozen training feature budget invalid")
 data<-t(x[features,train,drop=FALSE]);network<-bulkKnk::infer_causal_network(data,threshold_method="top_quantile",q_val=p$network_quantile,n_cores=p$cores)$clean_matrix
 if(p$pruning=="heuristic_dpi_fast")network<-bulkKnk::prune_network_dpi_fast(network,dpi_threshold=p$dpi_threshold)
 else if(p$pruning!="none")stop("This adapter does not claim GENIE3-weight heuristic pruning is standard mutual-information ARACNE")
 if(!identical(rownames(network),features)||!identical(colnames(network),features)||any(network<0)||any(!is.finite(network)))stop("Frozen GENIE3 network axes/weights invalid")
 diag(network)<-0;w<-t(network);den<-colSums(w);nonzero<-den>0;w[,nonzero]<-sweep(w[,nonzero,drop=FALSE],2,den[nonzero],"/")
 ids<-which(test);predictions<-list();summary<-list();nulls<-list();diagnostics<-list()
 # A null propagation is necessary: unperturbed raw expression is generally not a network fixed point.
 run_state<-function(anchor,targets){z<-bulkKnk::run_virtual_knockout(target_genes=targets,E_init=anchor,adj_matrix=w,alpha=p$alpha,steps=p$steps,check_convergence=FALSE);ww<-w;aa<-anchor;if(length(targets)){ww[targets,]<-0;ww[,targets]<-0;aa[targets]<-0};residual<-max(abs(z-(p$alpha*as.vector(ww%*%z)+(1-p$alpha)*aa)));if(!is.finite(residual)||residual>p$convergence_tolerance)stop("bulkKnk steady-state residual exceeds prespecified tolerance");list(value=z,residual=residual)}
 targets_control<-unlist(p$control_genes);if(length(targets_control)<3||any(targets_control%in%genes)||!all(targets_control%in%features))stop("At least three distinct prespecified covered control targets required")
 for(k in seq_along(ids)){
   id<-ids[k];anchor<-setNames(x[features,id],features);wt<-run_state(anchor,NULL);ko<-run_state(anchor,genes)
   if(any(abs(ko$value[genes])>p$convergence_tolerance))stop("KO target was not clamped in every modeled sample")
   delta<-ko$value-wt$value
   predictions[[k]]<-data.frame(unit_id=m$unit_id[id],sample_id=m$sample_id[id],feature_id=features,observed_baseline=anchor,model_WT=wt$value,model_KO=ko$value,model_delta=delta,biological_effect_observed=FALSE)
   diagnostics[[k]]<-data.frame(unit_id=m$unit_id[id],WT_residual=wt$residual,KO_residual=ko$residual,target_zero_verified=TRUE)
   nulls[[k]]<-do.call(rbind,lapply(targets_control,function(g){control<-run_state(anchor,g);data.frame(unit_id=m$unit_id[id],control_gene=g,out_degree=sum(network[g,]>0),mean_training_expression=mean(x[g,train]),model_shift_L1=sum(abs(control$value-wt$value)))}))
 }
 tables[[1]]<-do.call(rbind,predictions);tables[[2]]<-data.frame(regulator=rep(rownames(network),ncol(network)),target=rep(colnames(network),each=nrow(network)),weight=as.vector(network));tables[[3]]<-do.call(rbind,diagnostics);tables[[4]]<-do.call(rbind,nulls)
 metrics<-list(training_units=sum(train),evaluation_units=sum(test),selected_genes=length(features),network_edges=sum(network>0),maximum_fixed_point_residual=max(tables[[3]]$WT_residual,tables[[3]]$KO_residual))
 write.table(data.frame(unit_id=m$unit_id,role=ifelse(train,"TRAINING","EVALUATION")),file.path(out,"unit_split.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
}else if(j$analysis_id=="singlecell_virtual_ko"){
 if(j$context$scale!="raw_counts"||any(x<0)||any(x!=round(x)))stop("scTenifoldKnk is a single-cell raw-count method; bulk samples are not cells")
 if(!all(c("cell_type","qc_accepted")%in%names(m))||!all(tolower(m$qc_accepted)%in%c("true","1")))stop("Actual reviewed cell QC and cell-type identities required")
 use<-m$cell_type==p$cell_type & m$unit_id%in%unlist(p$evaluation_units);m<-m[use,,drop=FALSE];x<-x[,use,drop=FALSE]
 if(!setequal(unique(m$unit_id),unlist(p$evaluation_units)))stop("Requested scTenifoldKnk donor/cell-type absent")
 if(length(unique(m$unit_id))<2||any(table(m$unit_id)<p$min_cells_per_unit))stop("Independent donor/cell-type coverage insufficient")
 if(length(genes)>1&&packageVersion(pkg)<"1.1.2")stop("This installed scTenifoldKnk version does not support the requested multi-gene KO")
 records<-list();coverage<-list();native_files<-list();fn<-getExportedValue(pkg,"scTenifoldKnk");formal<-names(formals(fn))
 for(unit in unique(m$unit_id)){
   chosen<-which(m$unit_id==unit);xx<-x[,chosen,drop=FALSE];keep_gene<-rowMeans(xx>0)>=p$min_gene_prevalence & apply(xx,1,var)>0
   if(!all(genes%in%rownames(xx)[keep_gene]))stop("KO target fails donor-specific expression/variation QC")
   xx<-xx[keep_gene,,drop=FALSE];if(p$n_components>=min(dim(xx))||p$n_components<=2)stop("Invalid scTenifoldKnk PCA dimension")
   values<-list(countMatrix=xx,gKO=genes,qc=FALSE,nc_nNet=p$n_networks,nc_nCells=min(p$cells_per_network,length(chosen)),nc_nComp=p$n_components,nCores=p$cores,seed=p$seed)
   if(!all(names(values)%in%formal))stop("Installed scTenifoldKnk API differs from the reviewed adapter")
   result<-do.call(fn,values);z<-as.data.frame(result$diffRegulation)
   if(!all(c("gene","distance","p.adj")%in%names(z)))stop("Unknown native scTenifoldKnk result schema")
   z$unit_id<-unit;z$p_scope<-"within_donor_gene_space_model_not_donor_population_effect";records[[unit]]<-z
   filename<-paste0("native_scTenifold_",length(native_files)+1,".rds");saveRDS(result,file.path(out,filename));native_files[[unit]]<-filename
   coverage[[unit]]<-data.frame(unit_id=unit,cells=length(chosen),genes=nrow(xx),networks=p$n_networks,cells_per_network=values$nc_nCells)
 }
 tables[[1]]<-do.call(rbind,records);tables[[2]]<-do.call(rbind,coverage);tables[[3]]<-data.frame(unit_id=names(native_files),native_result_file=unlist(native_files));tables[[4]]<-data.frame(ko_gene=genes,method="scTenifoldKnk",independent_donor_replication_established=FALSE)
 metrics<-list(independent_units=length(unique(m$unit_id)),cells=ncol(x),genes=nrow(x),modeled_gene_unit_records=nrow(tables[[1]]))
}else stop("Unknown virtual KO R branch")
roles<-unlist(j$required_roles);mapping<-list()
for(k in seq_along(roles)){file<-paste0(roles[k],".tsv");write.table(tables[[k]],file.path(out,file),sep="\t",quote=FALSE,row.names=FALSE,na="NA");mapping[[roles[k]]]<-file}
write_json(mapping,file.path(out,"outputs.private.json"),auto_unbox=TRUE,pretty=TRUE)
write_json(list(fit_completed=TRUE,metrics=metrics,method=p$implementation,causal_effect_established=FALSE,therapeutic_or_survival_benefit_established=FALSE),file.path(out,"diagnostics.private.json"),auto_unbox=TRUE,pretty=TRUE)
