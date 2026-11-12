# Native R result-only alternatives. No model, embedding or KDE fitting.
# source('biostyle.R') before this file.
render_result_r <- function(id,d,name,outdir,width=183,height=130,overwrite=FALSE,
                            identity_colors=NULL,font_dir=NULL) {
  if(!grepl('^[A-Za-z0-9][A-Za-z0-9_.-]*$',name)||grepl('..',name,fixed=TRUE))stop('Plain output stem required')
  dir.create(outdir,recursive=TRUE,showWarnings=FALSE)
  paths<-file.path(outdir,paste0(name,c('.png','.svg')))
  if(!overwrite&&any(file.exists(paths)))stop('Existing output; choose another version')
  if(!is.null(font_dir))systemfonts::register_font('Liberation Sans',plain=file.path(font_dir,'LiberationSans-Regular.ttf'),bold=file.path(font_dir,'LiberationSans-Bold.ttf'),italic=file.path(font_dir,'LiberationSans-Italic.ttf'),bolditalic=file.path(font_dir,'LiberationSans-BoldItalic.ttf'))
  base<-c('#3B6F91','#CA7354','#4C9685','#9279AE','#BE9848','#6E91AD','#B17890','#879878')
  colors<-function(names) {
    names<-unique(names);fixed<-unlist(identity_colors);present<-intersect(names,names(fixed));unused<-setdiff(base,unname(fixed[present]));missing<-setdiff(names,present)
    if(length(missing)>length(unused))stop('Explicit distinct colors/facets required for this many identities')
    fixed[missing]<-unused[seq_along(missing)];fixed[names]
  }
  wrap<-function(x,n=28)vapply(x,function(s)paste(strwrap(s,width=n),collapse='\n'),character(1))
  theme<-theme_biostyle()+ggplot2::theme(legend.position='bottom',plot.title.position='plot',plot.margin=grid::unit(c(4,5,4,4),'mm'))
  p<-NULL;drawer<-NULL;meta<-list(id=id,scope='Native R rendering of supplied frozen channels; not scientific inference')
  if(id=='volcano') {
    t<-as.data.frame(d$de);stopifnot(all(c('gene','log2FC','padj')%in%names(t)),all(is.finite(t$log2FC)),all(t$padj>=0&t$padj<=1))
    q<-if(is.null(d$thresholds$fdr)).05 else d$thresholds$fdr;fc<-if(is.null(d$thresholds$log2fc))1 else d$thresholds$log2fc
    finite<--log10(t$padj[t$padj>0]);cap<-if(length(finite))max(finite)+max(1,.08*max(finite)) else -log10(q)+1
    t$strength<--log10(pmax(t$padj,10^-cap));t$direction<-ifelse(t$padj<q&t$log2FC>fc,'Up',ifelse(t$padj<q&t$log2FC< -fc,'Down','Other'));t$zero<-t$padj==0
    p<-ggplot2::ggplot(t,ggplot2::aes(log2FC,strength,color=direction,shape=zero))+ggplot2::geom_point(size=.7,alpha=.55)+ggplot2::geom_vline(xintercept=c(-fc,fc),linetype=2,color='#7F919D',linewidth=.3)+ggplot2::geom_hline(yintercept=-log10(q),linetype=2,color='#7F919D',linewidth=.3)+ggplot2::scale_color_manual(values=c(Up='#C56D56',Down='#39789E',Other='#C5CFD5'))+ggplot2::scale_shape_manual(values=c('FALSE'=16,'TRUE'=17),labels=c('Finite adjusted P','Reported adjusted P = 0'))+ggplot2::labs(title='Differential expression \u00b7 supplied results',x='Log2 fold change',y='\u2212log10 adjusted P',color=NULL,shape=NULL)+theme
    meta$thresholds<-list(fdr=q,log2fc=fc);meta$zero_display_height<-cap
  } else if(id=='raincloud') {
    labels<-d$labels;pal<-colors(labels);pts<-list();dens<-list();summary<-list()
    for(i in seq_along(labels)) {
      v<-unlist(d$values[[i]]);stopifnot(all(is.finite(v)));off<-((seq_along(v)*.61803398875)%%1-.5)*.14
      pts[[i]]<-data.frame(value=v,y=i+.20+off,identity=labels[i]);q<-quantile(v,c(.25,.5,.75));summary[[i]]<-data.frame(y=i,q1=q[1],median=q[2],q3=q[3],identity=labels[i])
      den<-if(is.data.frame(d$densities))as.list(d$densities[i,]) else d$densities[[i]]
      if(!is.null(den)&&length(den$x))dens[[i]]<-data.frame(value=unlist(den$x),low=i-.08,high=i-.08-unlist(den$y)/max(unlist(den$y))*.35,identity=labels[i])
    }
    tt<-do.call(rbind,pts);ss<-do.call(rbind,summary);dd<-do.call(rbind,dens)
    p<-ggplot2::ggplot()+ggplot2::geom_ribbon(data=dd,ggplot2::aes(value,ymin=low,ymax=high,fill=identity),alpha=.35)+ggplot2::geom_point(data=tt,ggplot2::aes(value,y,color=identity),size=.45,alpha=.4)+ggplot2::geom_segment(data=ss,ggplot2::aes(x=q1,xend=q3,y=y,yend=y,color=identity),linewidth=1.5)+ggplot2::geom_point(data=ss,ggplot2::aes(median,y),shape=124,size=2)+ggplot2::scale_color_manual(values=pal)+ggplot2::scale_fill_manual(values=pal)+ggplot2::scale_y_reverse(breaks=seq_along(labels),labels=wrap(labels))+ggplot2::labs(x=d$unit,y=NULL,title='Observations, supplied densities & IQR')+theme+ggplot2::theme(legend.position='none')
    meta$density_fitting<-'none; original supplied grids'
  } else if(id%in%c('chord_go','cellcomm_chord')) {
    links<-as.data.frame(d$links);stopifnot(all(c('source','target','value')%in%names(links)),all(links$value>=0));nodes<-unique(c(links$source,links$target));pal<-colors(nodes)
    drawer<-function(){
      circlize::circos.clear();par(family='Liberation Sans',mar=c(1,1,1,1),xpd=NA)
      circlize::circos.par(start.degree=90,gap.degree=if(length(nodes)>8)3 else 5,track.margin=c(.005,.005))
      circlize::chordDiagram(links[,c('source','target','value')],grid.col=pal,transparency=.62,annotationTrack='grid',preAllocateTracks=list(track.height=.22),self.link=1)
      circlize::circos.trackPlotRegion(track.index=1,bg.border=NA,panel.fun=function(x,y){sector<-circlize::get.cell.meta.data('sector.index');xlim<-circlize::get.cell.meta.data('xlim');circlize::circos.text(mean(xlim),.5,paste(strwrap(sector,width=26),collapse='\n'),facing='bending.inside',niceFacing=TRUE,cex=.5)})
      circlize::circos.clear()
    };meta$link_sum<-sum(links$value);meta$weights<-'literal supplied link weights, no recomputed score'
  } else if(id=='alluvial') {
    t<-as.data.frame(d$links);pal<-colors(t$source)
    p<-ggplot2::ggplot(t,ggplot2::aes(axis1=source,axis2=target,y=value))+ggalluvial::geom_alluvium(ggplot2::aes(fill=source),alpha=.5,width=.12)+ggalluvial::geom_stratum(width=.12,fill='#D5DFE4',color='white',linewidth=.2)+ggplot2::scale_x_discrete(limits=c('Source identity','Supplied grouping'),expand=c(.32,.32))+ggplot2::scale_fill_manual(values=pal)+ggplot2::labs(x=NULL,y='Actual source observations',title='Identity-to-group composition')+theme+ggplot2::theme(legend.position='none',panel.grid=ggplot2::element_blank())
    labs<-ggplot2::ggplot_build(p)$data[[2]]
    p<-p+ggrepel::geom_text_repel(data=labs,ggplot2::aes(x=x,y=y,label=stratum),inherit.aes=FALSE,nudge_x=ifelse(labs$x==1,-.20,.20),direction='y',seed=42,min.segment.length=0,segment.color='#889DA8',segment.size=.25,size=2.1,max.overlaps=Inf,box.padding=.3,point.padding=.2,hjust=ifelse(labs$x==1,1,0),family='Liberation Sans')
    meta$semantics<-d$flow_semantics
  } else if(id=='km_curve') {
    t<-as.data.frame(d$table);strata<-unique(t$stratum);pal<-colors(strata)
    drawer<-function(){
      par(family='Liberation Sans',mar=c(3.8,4,1.4,1),las=1);layout(matrix(c(1,2),2,1),heights=c(4,1.6));xmax<-max(t$time)
      plot(NA,xlim=c(0,xmax),ylim=c(0,1),xlab='',ylab='Survival probability',bty='l',cex.axis=.8,cex.lab=.85)
      for(g in strata){z<-t[t$stratum==g,];x<-c(0,z$time);y<-c(1,z$survival);sx<-rep(x,each=2)[-1];sx<-sx[-length(sx)];slo<-rep(c(1,z$lower),each=2);slo<-slo[-c(1,length(slo))];shi<-rep(c(1,z$upper),each=2);shi<-shi[-c(1,length(shi))];polygon(c(sx,rev(sx)),c(slo,rev(shi)),col=adjustcolor(pal[g],alpha.f=.12),border=NA);lines(x,y,type='s',col=pal[g],lwd=1.3);hit<-z$ncensor>0;points(z$time[hit],z$survival[hit],pch=3,cex=.4,col=pal[g])}
      legend('topright',strata,col=pal[strata],lty=1,bty='n',cex=.75)
      par(mar=c(4,4,.2,1));plot(NA,xlim=c(0,xmax),ylim=c(length(strata)+.5,.5),xlab='',ylab='',axes=FALSE);ticks<-seq(0,xmax,length.out=6);axis(1,at=ticks,labels=round(ticks),cex.axis=.75);axis(2,at=seq_along(strata),labels=strata,las=1,tick=FALSE,cex.axis=.75);mtext(if(is.null(d$time_unit))'Time (supplied units)' else d$time_unit,side=1,line=2.5,cex=.8)
      for(i in seq_along(strata)){z<-t[t$stratum==strata[i],];for(k in ticks){future<-z[z$time>=k,];n<-if(nrow(future))future$nrisk[1] else 0;text(k,i,n,cex=.75,col=pal[strata[i]])}}
      layout(1)
    };meta$survival_fit<-'none; frozen source survival/risk/censor table'
  } else if(id=='oncoprint') {
    genes<-d$genes;samples<-d$samples;types<-d$event_types;pal<-colors(types);assay<-as.matrix(d$assayed);stopifnot(identical(dim(assay),c(length(genes),length(samples))))
    drawer<-function(){
      par(family='Liberation Sans',mar=c(7,5,3,1),xpd=NA);plot(NA,xlim=c(.5,length(samples)+.5),ylim=c(length(genes)+.5,.5),axes=FALSE,xlab='',ylab='')
      for(i in seq_along(genes))for(j in seq_along(samples)){
        rect(j-.44,i-.4,j+.44,i+.4,col=if(assay[i,j])'#F3F6F7' else '#DBD1C4',border=NA);ev<-d$events[[paste(genes[i],samples[j],sep='|')]]
        if(length(ev))for(k in seq_along(ev))rect(j-.44,i-.4+(k-1)*.8/length(ev),j+.44,i-.4+k*.8/length(ev),col=pal[ev[k]],border=NA)
      }
      axis(2,at=seq_along(genes),labels=genes,las=1,tick=FALSE,cex.axis=.7);axis(1,at=seq_along(samples),labels=samples,las=2,tick=FALSE,cex.axis=.5);legend('top',inset=c(0,-.09),horiz=TRUE,legend=c(types,'Unassayed'),fill=c(pal[types],'#DBD1C4'),bty='n',cex=.65)
    };meta$missing_semantics<-'unassayed, not no-event'
  } else stop(paste('No native result renderer for',id))
  if(!is.null(p))drawer<-function()print(p)
  ragg::agg_png(paths[1],width=width,height=height,units='mm',res=300,background='white');drawer();dev.off()
  svglite::svglite(paths[2],width=width/25.4,height=height/25.4,system_fonts=list(sans='Liberation Sans'));drawer();dev.off()
  meta$outputs<-paths;meta$width_mm<-width;meta$height_mm<-height;meta$status<-'RENDERED_UNREVIEWED';invisible(meta)
}
