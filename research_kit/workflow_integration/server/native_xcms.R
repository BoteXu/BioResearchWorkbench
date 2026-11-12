#!/usr/bin/env Rscript
# Existing server only: native xcms centWave -> obiwarp -> peak correspondence.
suppressPackageStartupMessages(library(jsonlite))
r<-fromJSON(commandArgs(trailingOnly=TRUE)[1],simplifyVector=FALSE);p<-r$parameters;f<-r$inputs;out<-r$out;outputs<-list();set.seed(p$seed)
for(pkg in names(p$software_versions))if(!requireNamespace(pkg,quietly=TRUE)||as.character(packageVersion(pkg))!=p$software_versions[[pkg]])stop(paste('Different/missing existing package',pkg))
suppressPackageStartupMessages(library(xcms));suppressPackageStartupMessages(library(MsExperiment));suppressPackageStartupMessages(library(BiocParallel))
emit<-function(x,name,role){file<-paste0(name,'.tsv');write.table(x,file.path(out,file),sep='\t',quote=FALSE,row.names=TRUE,col.names=NA,na='NA');outputs[[length(outputs)+1]]<<-list(file=file,role=role)}
meta<-read.delim(f$metadata,check.names=FALSE,colClasses='character');ids<-unlist(p$raw_input_ids,use.names=FALSE)
needed<-c('sample_id','input_id',p$unit_key,p$condition_key,p$sample_role_key,p$injection_order_key)
if(!all(needed%in%names(meta))||anyNA(meta[,needed])||any(!nzchar(as.matrix(meta[,needed])))||anyDuplicated(meta$sample_id)||anyDuplicated(meta$input_id)||!setequal(ids,meta$input_id))stop('Exact raw-file/sample/independent-unit/condition/role/injection-order map required')
meta<-meta[match(ids,meta$input_id),,drop=FALSE];paths<-vapply(ids,function(id)f[[id]],character(1));if(any(!file.exists(paths))||any(!grepl('\\.(mzML|mzXML|cdf)$',paths,ignore.case=TRUE)))stop('Native centroid open MS files required; no proprietary raw conversion')
order<-as.numeric(meta[[p$injection_order_key]]);if(any(!is.finite(order))||anyDuplicated(order))stop('Actual unique injection order required; no inferred acquisition order')
roles<-meta[[p$sample_role_key]];if(!all(roles%in%c('study','pooled_qc','blank','standard')))stop('Explicit study/pooled_qc/blank/standard sample roles required')
if(!any(roles=='study')||length(unique(meta[[p$condition_key]][roles=='study']))<2)stop('At least two actual study conditions required')
if(length(unique(p$polarity))!=1||!p$polarity%in%c('positive','negative')||p$acquisition_mode!='centroid')stop('Process one declared polarity in native centroid mode at a time')
rownames(meta)<-meta$sample_id;raw<-MsExperiment::readMsExperiment(spectraFiles=paths,sampleData=meta)
# Retention times are in seconds throughout. Do not combine acquisition batches
# or polarity modes here without a separately reviewed upstream protocol.
bp<-BiocParallel::SnowParam(workers=p$workers,progressbar=FALSE)
cw<-xcms::CentWaveParam(ppm=p$ppm,peakwidth=unlist(p$peak_width_seconds),snthresh=p$snr_threshold,prefilter=unlist(p$prefilter),mzCenterFun='wMean',integrate=1L)
detected<-xcms::findChromPeaks(raw,param=cw,BPPARAM=bp)
peaks_before<-as.data.frame(xcms::chromPeaks(detected));if(!nrow(peaks_before))stop('No native chromatographic peaks; not biological absence')
aligned<-xcms::adjustRtime(detected,param=xcms::ObiwarpParam(binSize=p$alignment_bin_mz,response=p$alignment_response,distFun='cor_opt'),BPPARAM=bp)
# Blanks never define features but retain their measured intensities. Pooled QC
# and standards only define groups if explicitly listed in the reviewed task.
groups<-meta[[p$condition_key]];groups[!roles%in%unlist(p$feature_definition_roles)]<-NA_character_
if(all(is.na(groups)))stop('No samples eligible to define features')
grouped<-xcms::groupChromPeaks(aligned,param=xcms::PeakDensityParam(sampleGroups=groups,bw=p$group_bandwidth_seconds,minFraction=p$group_min_fraction,minSamples=p$group_min_samples,binSize=p$group_bin_mz),BPPARAM=bp)
nofill<-xcms::featureValues(grouped,value='into',method='medret',filled=FALSE)
if(!nrow(nofill)||ncol(nofill)!=nrow(meta))stop('Native feature intensity dimensions differ')
if(p$fill_peaks)grouped<-xcms::fillChromPeaks(grouped,param=xcms::ChromPeakAreaParam(),BPPARAM=bp)
final<-xcms::featureValues(grouped,value='into',method='medret');definition<-as.data.frame(xcms::featureDefinitions(grouped))
if(!identical(dimnames(nofill),dimnames(final))||!identical(rownames(final),rownames(definition))||any(final<0,na.rm=TRUE)||any(!is.finite(final[!is.na(final)])))stop('Native feature identity/intensity QC failed')
# The native object follows its input file sequence. Preserve this explicit map;
# never infer biological identities from basenames, condition suffixes or peaks.
native_names<-colnames(final);if(anyDuplicated(native_names)||length(native_names)!=nrow(meta))stop('Ambiguous native file axes')
axis_map<-data.frame(native_sample_label=native_names,sample_id=meta$sample_id,input_id=ids);rownames(axis_map)<-native_names
colnames(nofill)<-colnames(final)<-meta$sample_id
emit(nofill,'xcms_detected_intensities','feature_intensities_detected');emit(final,'xcms_final_intensities','feature_intensities');emit(axis_map,'xcms_axis_map','sample_axis_map');emit(meta,'xcms_sample_metadata','sample_metadata')
definition$peakidx<-vapply(definition$peakidx,function(x)paste(x,collapse=','),character(1));emit(definition,'xcms_features','feature_definitions');emit(peaks_before,'xcms_detected_peaks','chromatographic_peaks')
rt_raw<-xcms::rtime(grouped,bySample=TRUE,adjusted=FALSE);rt_adj<-xcms::rtime(grouped,bySample=TRUE,adjusted=TRUE)
rt_qc<-do.call(rbind,lapply(seq_along(ids),function(i){if(length(rt_raw[[i]])!=length(rt_adj[[i]]))stop('Native alignment scan identity differs');d<-rt_adj[[i]]-rt_raw[[i]];data.frame(sample_id=meta$sample_id[i],n_scans=length(d),median_shift_seconds=median(d),maximum_absolute_shift_seconds=max(abs(d)),missing_detected_fraction=mean(is.na(nofill[,i])),missing_final_fraction=mean(is.na(final[,i])))}));rownames(rt_qc)<-rt_qc$sample_id;emit(rt_qc,'xcms_run_qc','run_qc')
saveRDS(grouped,file.path(out,'xcms_native.rds'));outputs[[length(outputs)+1]]<-list(file='xcms_native.rds',role='processed_object')
capture.output(xcms::processHistory(grouped),file=file.path(out,'xcms_process_history.txt'));outputs[[length(outputs)+1]]<-list(file='xcms_process_history.txt',role='processing_history')
diag<-list(mode=r$mode,software_versions=p$software_versions,n_samples=nrow(meta),n_features=nrow(final),sample_identity_bound=TRUE,missing_values_preserved=TRUE,intensity_unit='native integrated peak area',retention_time_unit='second',fill_peaks=p$fill_peaks,scientific_acceptance='NOT_ESTABLISHED',interpretation='Native centroid MS1 peak processing. medret selects the peak nearest median retention time when a sample has multiple peaks for a feature; retained original peak indices permit review. Gap integration is not zero filling, normalization or metabolite identification. Blank/QC evaluation and downstream independent-unit statistics remain separate gates.')
write_json(diag,file.path(out,'diagnostics.json'),pretty=TRUE,auto_unbox=TRUE);outputs[[length(outputs)+1]]<-list(file='diagnostics.json',role='diagnostics');capture.output(sessionInfo(),file=file.path(out,'R_session_info.txt'));outputs[[length(outputs)+1]]<-list(file='R_session_info.txt',role='backend_versions');write_json(outputs,file.path(out,'native_r_outputs.json'),pretty=TRUE,auto_unbox=TRUE)
