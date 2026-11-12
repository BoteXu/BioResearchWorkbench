"""Real vector-panel composition with ID/clip isolation and controlled width."""
from pathlib import Path
import io,re,xml.etree.ElementTree as ET,json
import matplotlib.pyplot as plt
from design_system import WIDTH_MM,choose_grid,identity_colors,wrap_label,panel_viewport,finish_figure
NS='http://www.w3.org/2000/svg';ET.register_namespace('',NS)
ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
RECIPES={
 'scrna-fig1':['umap_clusters','dot_plot','proportion_stack','qc_triplet'],
 'bulk-de-story':['pca_samples','sample_corr','volcano','deg_heatmap'],
 'md-summary':['rmsd_overlay','rmsf','dccm','fel_2d'],
 'ml-benchmark-composite':['roc_multi','pr_curve','calibration','confusion'],
 'docking-triage':['vs_funnel','score_heatmap','pose_grid_3d'],
 'qm-photo':['emission_stokes','orbitals','irc'],
 'qc_dashboard':['libsize_bar','pca_outlier','rle_plot','qc_sample_corr']}

def compose_panels(panels,outdir,stem,*,ncols=None,nrows=None,width='double',gap_mm=5,overwrite=False,legend_items=None,layout='auto'):
    """panels: sequence of (label, Matplotlib Figure); never blank placeholders.

    Child figures must be rendered at their intended physical size. Scaling
    below 85% is rejected to prevent silent tiny text. Use pagination instead.
    """
    nr,nc=choose_grid(len(panels),ncols,nrows,max_cols=2);W=WIDTH_MM[width]
    col=(W-gap_mm*(nc-1))/nc;parts=[];heights=[]
    for i,(label,fig) in enumerate(panels):
        if not fig.axes or not any(a.has_data() for a in fig.axes):raise ValueError('Empty composite panel: '+label)
        text=io.StringIO();fig.savefig(text,format='svg',bbox_inches=None);root=ET.fromstring(text.getvalue());vb=list(map(float,root.attrib['viewBox'].split()));actual=fig.get_figwidth()*25.4
        scale=col/actual
        if scale<.85:raise ValueError('Panel too wide for requested grid; render panels at column width or paginate')
        h=fig.get_figheight()*25.4*scale;heights.append(h)
        prefix=f'p{i}_';s=ET.tostring(root,encoding='unicode');ids=re.findall(r'\bid="([^"]+)"',s)
        for ident in sorted(ids,key=len,reverse=True):
            s=s.replace('id="'+ident+'"','id="'+prefix+ident+'"').replace('url(#'+ident+')','url(#'+prefix+ident+')').replace('href="#'+ident+'"','href="#'+prefix+ident+'"')
        parts.append((label,ET.fromstring(s),vb,col/vb[2],h))
    if layout not in ('auto','grid','balanced_columns'):raise ValueError('Composition layout: auto, grid, balanced_columns')
    balanced=nc==2 and (layout=='balanced_columns' or (layout=='auto' and max(heights)>1.5*min(heights)))
    positions={}
    if balanced:
        columns=[[],[]];loads=[0.,0.]
        for i in sorted(range(len(heights)),key=lambda j:-heights[j]):
            col=min(range(2),key=lambda j:loads[j]);columns[col].append(i);loads[col]+=heights[i]+(gap_mm if columns[col][:-1] else 0)
        columns.sort(key=lambda items:min(items) if items else len(parts))
        for col,items in enumerate(columns):
            y=5.
            for i in sorted(items):positions[i]=(col*(W+gap_mm)/2,y);y+=heights[i]+gap_mm
        H=max((y+heights[i] for i,(x,y) in positions.items()),default=0)+1
    else:
        rowheights=[max(heights[r*nc:min((r+1)*nc,len(heights))]) for r in range(nr)];H=sum(rowheights)+gap_mm*(nr-1)+6
        positions={i:((i%nc)*(col+gap_mm),sum(rowheights[:i//nc])+(i//nc)*gap_mm+5) for i in range(len(parts))}
    legend_y=H+2
    if legend_items:H+=max(1,(len(legend_items)+3)//4)*10+4
    svg=ET.Element('{'+NS+'}svg',{'width':f'{W}mm','height':f'{H:.4f}mm','viewBox':f'0 0 {W} {H}'})
    ET.SubElement(svg,'{'+NS+'}rect',{'width':str(W),'height':str(H),'fill':'white'})
    for i,(label,root,vb,scale,h) in enumerate(parts):
        x,y=positions[i]
        group=ET.SubElement(svg,'{'+NS+'}g',{'transform':f'translate({x:.5f},{y:.5f}) scale({scale:.9f})'})
        for child in list(root):group.append(child)
        tag=ET.SubElement(svg,'{'+NS+'}text',{'x':str(x+1),'y':str(y-1),'font-family':'Liberation Sans','font-size':'3.4','font-weight':'bold','fill':'#253442'});tag.text=label
    for i,(name,color) in enumerate(legend_items or []):
        x=2+(i%4)*(W/4);y=legend_y+(i//4)*10
        ET.SubElement(svg,'{'+NS+'}rect',{'x':str(x),'y':str(y),'width':'2.5','height':'2.5','fill':color})
        for j,line in enumerate(wrap_label(name,23).split('\n')):
            label=ET.SubElement(svg,'{'+NS+'}text',{'x':str(x+4),'y':str(y+2.1+j*3),'font-family':'Liberation Sans','font-size':'2.5','fill':'#253442'});label.text=line
    out=Path(outdir);out.mkdir(exist_ok=True,parents=True);path=out/(stem+'.svg')
    if path.exists() and not overwrite:raise FileExistsError(path)
    ET.ElementTree(svg).write(path,encoding='utf-8',xml_declaration=True)
    return path,{'rows':nr,'columns':nc,'composition_layout':'balanced_columns' if balanced else 'grid','panel_positions_mm':{panels[i][0]:list(xy) for i,xy in positions.items()},'width_mm':W,'height_mm':H,'panels':[p[0] for p in panels],'shared_identity_legend':legend_items or [],'actual_vector_panels':True,'status':'RENDERED_UNREVIEWED'}

def render_composite(recipe,data,*,outdir,stem=None,ncols=None,nrows=None,overwrite=False,**options):
    from renderers import render_template
    if recipe not in RECIPES:raise KeyError(recipe)
    ids=options.pop('panel_ids',RECIPES[recipe]);panel_options=options.pop('panel_options',{});missing=[k for k in ids if k not in data]
    if missing:raise ValueError('Missing actual composite channels: '+', '.join(missing))
    figures=[]
    nr,nc=choose_grid(len(ids),ncols,nrows,max_cols=2)
    width_name=options.get('width','double');page_width=WIDTH_MM[width_name];gap=options.get('gap_mm',5)
    panel_width=(page_width-gap*(nc-1))/nc
    if panel_width<70:raise ValueError('Composite panels below 70 mm require fewer columns or a wider page; no silent font shrinking')
    allgroups=[g for k in ids for g in data[k].get('group_order',[])];shared=sorted({g for g in allgroups if allgroups.count(g)>1});theme=options.setdefault('theme',{})
    fixed=dict(theme.get('identity_colors',{}))
    for opts in panel_options.values():
        for name,color in opts.get('theme',{}).get('identity_colors',{}).items():
            if name in fixed and fixed[name]!=color:raise ValueError('Conflicting composite identity colors for '+name)
            fixed[name]=color
    theme['identity_colors']=fixed;mapping=identity_colors(theme,shared) if shared else {}
    composition_key=next((k for k in ids if k=='proportion_stack' and set(shared)<=set(data[k].get('categories',[]))),None)
    try:
        for i,k in enumerate(ids):
            payload=data[k];opts={**options,**panel_options.get(k,{})};opts.setdefault('width','double' if nc==1 else 'single')
            if k=='umap_clusters' and composition_key and nc>1:opts.setdefault('show_labels',False)
            if k=='qc_triplet' and nc>1:opts.setdefault('aspect',1.15)
            with panel_viewport(panel_width):fig,meta=render_template(k,payload,**opts)
            for ax in list(fig.axes):
                leg=ax.get_legend()
                if leg:
                    texts={s.get_text().replace('\n',' ') for s in leg.get_texts()}
                    if texts and texts<=set(shared):
                        leg.remove()
                        if not ax.axison and not ax.texts and not ax.has_data():
                            spec=ax.get_subplotspec()
                            if spec is None:continue
                            grid=spec.get_gridspec();ratios=grid.get_width_ratios()
                            column=spec.colspan.start
                            other_in_column=any(other is not ax and other.get_subplotspec() is not None and other.get_subplotspec().get_gridspec() is grid and column in other.get_subplotspec().colspan for other in fig.axes if hasattr(other,'get_subplotspec'))
                            if ratios and spec.colspan.stop-spec.colspan.start==1 and not other_in_column:ratios[column]=.002;grid.set_width_ratios(ratios)
                            ax.remove()
            finish_figure(fig);figures.append((chr(65+i),fig))
        path,meta=compose_panels(figures,outdir,stem or recipe,ncols=nc,nrows=nr,width=width_name,gap_mm=gap,overwrite=overwrite,legend_items=None if composition_key else list(mapping.items()),layout=options.get('composition_layout','grid' if nrows is not None else 'auto'))
        meta['shared_identity_legend_source']=composition_key or 'figure legend'
        meta.update(recipe=recipe,actual_template_ids=ids,default_panels=RECIPES[recipe],variant='default' if ids==RECIPES[recipe] else 'explicit supplied-channel panels')
        return path,meta
    finally:
        for _,fig in figures:plt.close(fig)

__all__=['RECIPES','compose_panels','render_composite']
