# Native R result-only renderers. The Python implementation is an additional
# backend and does not replace these original R capabilities.
render_heatmap_r <- function(mat, name, outdir, meta=NULL, quantity='Supplied value',
                             width=183,height=150, linkage='average',
                             row_distance='euclidean',column_distance='euclidean',
                             vlim=NULL, color_limits=NULL, overwrite=FALSE,font_dir=NULL) {
  stopifnot(is.matrix(mat),is.numeric(mat),all(is.finite(mat)),nrow(mat)>0,ncol(mat)>0)
  if(!grepl('^[A-Za-z0-9][A-Za-z0-9_.-]*$',name)||grepl('..',name,fixed=TRUE))stop('Plain output stem required')
  dir.create(outdir,recursive=TRUE,showWarnings=FALSE)
  paths<-file.path(outdir,paste0(name,c('.png','.svg')))
  if(!overwrite&&any(file.exists(paths)))stop('Existing figure; choose a new version')
  if(!is.null(font_dir))systemfonts::register_font('Liberation Sans',
    plain=file.path(font_dir,'LiberationSans-Regular.ttf'),
    bold=file.path(font_dir,'LiberationSans-Bold.ttf'),
    italic=file.path(font_dir,'LiberationSans-Italic.ttf'),
    bolditalic=file.path(font_dir,'LiberationSans-BoldItalic.ttf'))
  font<-'Liberation Sans'
  if(!is.null(font_dir)) {
    # ComplexHeatmap measures names on a temporary PDF device. Register exact
    # metrics from the bundled TTFs in this R process as well as ragg/systemfonts.
    afms<-file.path(font_dir,paste0('LiberationSans-',c('Regular','Bold','Italic','BoldItalic'),'.afm'))
    if(all(file.exists(afms)) && !font %in% names(grDevices::pdfFonts()))grDevices::pdfFonts('Liberation Sans'=grDevices::Type1Font('Liberation Sans',metrics=c(afms,'Symbol.afm')))
  }
  zrow<-if(nrow(mat)>1)hclust(dist(mat,method=row_distance),method=linkage) else FALSE
  zcol<-if(ncol(mat)>1)hclust(dist(t(mat),method=column_distance),method=linkage) else FALSE
  lim<-if(is.null(vlim))max(abs(range(mat))) else vlim
  if(lim==0)lim<-1
  breaks<-if(is.null(color_limits))c(-lim,0,lim) else seq(color_limits[1],color_limits[2],length.out=3)
  cc<-circlize::colorRamp2(breaks,if(is.null(color_limits))c('#316C98','#FAFAF8','#C16A54') else c('#F3F7FA','#5796BB','#1B537A'))
  ha<-NULL
  if(!is.null(meta)) {
    if(nrow(meta)!=ncol(mat)||!identical(rownames(meta),colnames(mat)))stop('Metadata sample axis mismatch')
    ha<-ComplexHeatmap::HeatmapAnnotation(Condition=meta$condition,
      col=list(Condition=c(Untreated='#3B6F91',Dex='#CA7354',Alb='#4C9685',Alb_Dex='#9279AE')),
      annotation_name_gp=grid::gpar(fontfamily=font,fontsize=7),simple_anno_size=grid::unit(2,'mm'))
  }
  rowlabels<-vapply(rownames(mat),function(s)paste(strwrap(gsub('_',' ',s,fixed=TRUE),width=29),collapse='\n'),character(1))
  drawit<-function(){
  ht<-ComplexHeatmap::Heatmap(mat,name=quantity,col=cc,cluster_rows=zrow,cluster_columns=zcol,
    row_labels=rowlabels,row_names_max_width=grid::unit(max(12,max(nchar(unlist(strsplit(rowlabels,'\n'))))*1.8+4),'mm'),
    row_names_gp=grid::gpar(fontfamily=font,fontsize=7),column_names_gp=grid::gpar(fontfamily=font,fontsize=6.5),
    column_names_rot=55,row_names_side='left',row_dend_side='right',top_annotation=ha,
    border=FALSE,rect_gp=grid::gpar(col=NA),use_raster=FALSE,
    heatmap_legend_param=list(at=breaks,labels=formatC(breaks,digits=3,format='fg'),direction='horizontal',legend_width=grid::unit(38,'mm'),
       title_gp=grid::gpar(fontfamily=font,fontsize=8),labels_gp=grid::gpar(fontfamily=font,fontsize=7)))
  ComplexHeatmap::draw(ht,heatmap_legend_side='bottom',annotation_legend_side='right',
    padding=grid::unit(c(3,3,3,3),'mm'))
  }
  ragg::agg_png(paths[1],width=width,height=height,units='mm',res=300,background='white');drawit();dev.off()
  svglite::svglite(paths[2],width=width/25.4,height=height/25.4,system_fonts=list(sans=font));drawit();dev.off()
  invisible(list(outputs=paths,row_order=if(isFALSE(zrow))rownames(mat) else rownames(mat)[zrow$order],
    column_order=if(isFALSE(zcol))colnames(mat) else colnames(mat)[zcol$order],
    linkage=linkage,row_distance=row_distance,column_distance=column_distance,width_mm=width,height_mm=height))
}
