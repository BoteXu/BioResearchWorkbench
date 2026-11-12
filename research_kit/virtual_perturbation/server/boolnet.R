suppressPackageStartupMessages(library(jsonlite))
args<-commandArgs(TRUE);j<-fromJSON(args[1],simplifyVector=FALSE);p<-j$parameters;I<-j$inputs;out<-args[2]
if(Sys.info()[['sysname']]!='Linux'||grepl('microsoft',tolower(paste(readLines('/proc/version',warn=FALSE),collapse=' '))))stop('No local scientific execution')
script<-sub('^--file=','',commandArgs(FALSE)[grepl('^--file=',commandArgs(FALSE))]);guard<-file.path(dirname(normalizePath(script)),'child_guard.py')
approved_python<-Sys.getenv('BRW_APPROVED_PYTHON');if(!nzchar(approved_python)||normalizePath(approved_python)!=normalizePath(j$python_executable))stop('Unapproved child interpreter')
if(system2(j$python_executable,c(shQuote(guard),shQuote(args[1])))!=0)stop('Invalid authorized request')
if(!requireNamespace('BoolNet',quietly=TRUE)||as.character(packageVersion('BoolNet'))!=p$expected_package_version)stop('Existing exact reviewed BoolNet version required')
review<-fromJSON(I$logical_review);if(review$logic_review!='ACCEPT'||!identical(review$model_id,unlist(p$evaluation_units)))stop('Explicit model rule review and model unit required')
# BoolNet files may be untrusted: accept only Boolean expressions, never R expressions/functions.
lines<-readLines(I$network,warn=FALSE);lines<-trimws(lines[nzchar(trimws(lines))&!grepl('^\\s*#',lines)])
if(!length(lines)||tolower(gsub(' ','',lines[1]))!='targets,factors')stop('Require native BoolNet targets,factors format')
for(line in lines[-1]){
 pieces<-strsplit(line,',',fixed=TRUE)[[1]]
 if(length(pieces)!=2||!grepl('^[A-Za-z][A-Za-z0-9_]*$',trimws(pieces[1]))||!grepl('^[A-Za-z0-9_ &|!()]+$',trimws(pieces[2])))stop('Only reviewed Boolean grammar is accepted')
}
net<-BoolNet::loadNetwork(I$network,filetype='boolnet',symbolic=FALSE)
if(!inherits(net,'BooleanNetwork')||length(net$genes)>p$max_nodes||anyDuplicated(net$genes)||!all(unlist(p$ko_genes)%in%net$genes))stop('Unsupported logical network/node scope')
initial<-read.delim(I$initial_states,check.names=FALSE,stringsAsFactors=FALSE,colClasses=c(initial_id='character'))
if(!all(c('initial_id','weight',net$genes)%in%names(initial))||anyDuplicated(initial$initial_id)||any(!is.finite(initial$weight))||any(initial$weight<=0)||abs(sum(initial$weight)-1)>1e-8)stop('Reviewed complete weighted initial-state set required')
states<-as.matrix(initial[,net$genes,drop=FALSE]);if(anyNA(states)||!all(states%in%c(0,1)))stop('Initial states must be exact binary node vectors')
KO<-BoolNet::fixGenes(net,unlist(p$ko_genes),0);traces<-list();totals<-list(WT=rep(0,length(net$genes)),KO=rep(0,length(net$genes)));rows<-list();k<-0
for(label in c('WT','KO'))for(a in seq_len(nrow(states)))for(rep in seq_len(p$trajectories_per_initial)){
 set.seed(p$seed+a*100000+rep);network<-if(label=='WT')net else KO;s<-as.integer(states[a,]);if(label=='KO')s[match(unlist(p$ko_genes),net$genes)]<-0
 seen<-new.env(hash=TRUE,parent=emptyenv());history<-list();status<-'UNRESOLVED_FINITE_HORIZON';period<-0;summary<-s
 for(step in seq_len(p$max_steps)){
   token<-paste0(s,collapse='');old<-get0(token,envir=seen,inherits=FALSE)
   if(p$update_type=='synchronous'&&!is.null(old)){cycle<-do.call(rbind,history[seq.int(old,length(history))]);summary<-colMeans(cycle);period<-nrow(cycle);status<-if(period==1)'FIXED_POINT'else'OBSERVED_SYNCHRONOUS_CYCLE';break}
   assign(token,length(history)+1,envir=seen);history[[length(history)+1]]<-s
   nxt<-BoolNet::stateTransition(network,s,type=p$update_type)
   if(label=='KO'&&any(nxt[match(unlist(p$ko_genes),net$genes)]!=0))stop('Logical KO was not clamped')
   if(identical(as.integer(BoolNet::stateTransition(network,s,type='synchronous')),as.integer(s))){summary<-s;status<-'FIXED_POINT';period<-1;break}
   s<-as.integer(nxt);summary<-s
 }
 if(p$update_type=='synchronous'&&status=='UNRESOLVED_FINITE_HORIZON')stop('Synchronous attractor unresolved within declared step budget; never report final transient as an attractor')
 totals[[label]]<-totals[[label]]+initial$weight[a]*summary/p$trajectories_per_initial
 k<-k+1;rows[[k]]<-data.frame(scenario=label,initial_id=initial$initial_id[a],trajectory=rep,node=net$genes,terminal_activity=summary)
 traces[[k]]<-data.frame(scenario=label,initial_id=initial$initial_id[a],trajectory=rep,steps=step,cycle_length=period,terminal_status=status,initial_weight=initial$weight[a],update_type=p$update_type)
}
main<-data.frame(unit_id=review$model_id,feature_id=net$genes,WT_activity=totals$WT,KO_activity=totals$KO,state_activity_delta=totals$KO-totals$WT)
tables<-list(main,do.call(rbind,rows),initial,do.call(rbind,traces));mapping<-list();roles<-unlist(j$required_roles)
for(a in seq_along(roles)){fn<-paste0(roles[a],'.tsv');write.table(tables[[a]],file.path(out,fn),sep='\t',quote=FALSE,row.names=FALSE);mapping[[roles[a]]]<-fn}
write_json(mapping,file.path(out,'outputs.private.json'),auto_unbox=TRUE,pretty=TRUE)
write_json(list(fit_completed=TRUE,metrics=list(nodes=length(net$genes),initial_states=nrow(initial),simulated_trajectories=k,unresolved_fraction=mean(tables[[4]]$terminal_status=='UNRESOLVED_FINITE_HORIZON')),interpretation='Logical finite-initial-state distribution; asynchronous final states are finite-horizon simulations, not proof of attractor/stationarity or biological replicate inference'),file.path(out,'diagnostics.private.json'),auto_unbox=TRUE,pretty=TRUE)
writeLines(capture.output(sessionInfo()),file.path(out,'R_session_info.private.txt'))
