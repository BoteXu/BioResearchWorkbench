"""Result-only scientific panels. Data adapters belong to the caller."""
import numpy as np,pandas as pd,matplotlib as mpl,matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch,Rectangle
from design_system import *

def axes(o,aspect=.65,**kw):
    return plt.subplots(figsize=journal_size(o.get('width','double'),o.get('aspect',aspect)),layout='constrained',**kw)

def line_panel(d,o):
    curves=d['curves']; colors=identity_colors(o.setdefault('theme',{'palette':o.get('palette','muted')}),[x.get('color_id',x['label']) for x in curves])
    fig,ax=axes(o,.42 if len(curves)<=3 else .55)
    for c in curves:
        x=np.asarray(c['x'],float);y=np.asarray(c['y'],float)
        if x.shape!=y.shape or not np.isfinite(x).all() or not np.isfinite(y).all(): raise ValueError('Finite aligned curve coordinates required')
        color=colors[c.get('color_id',c['label'])]
        ax.plot(x,y,color=color,lw=1.2,label=wrap_label(c['label'],30),ls=c.get('linestyle','-'),marker='o' if len(x)<=20 else None,markersize=2.5,markeredgewidth=.4,markeredgecolor='white')
        if ('lo' in c)!=('hi' in c): raise ValueError('Both interval limits required')
        if 'lo' in c:
            cx=np.asarray(c.get('ci_x',x));lo=np.asarray(c['lo']);hi=np.asarray(c['hi'])
            if cx.shape!=lo.shape or lo.shape!=hi.shape or (lo>hi).any(): raise ValueError('Interval/grid contract invalid')
            ax.fill_between(cx,lo,hi,color=color,alpha=.12,lw=0)
    for t in d.get('reference_lines',[]):ax.axhline(t['value'],c=MUTED,lw=.7,ls='--',label=t.get('label','Configurable reference'))
    ax.set(xlabel=d['xlabel'],ylabel=d['ylabel']);ax.set_title(o.get('title',d.get('title','')),loc='left',pad=12)
    ax.grid(axis='y',color=GRID,lw=.4);ax.legend(loc=o.get('legend','best'))
    if o.get('xscale'):ax.set_xscale(o['xscale'])
    if o.get('yscale'):ax.set_yscale(o['yscale'])
    return fig,{'curves':[c['label'] for c in curves],'units':{'x':d['xlabel'],'y':d['ylabel']},'thresholds':d.get('reference_lines',[])}

def scatter_panel(d,o):
    x=np.asarray(d['x'],float);y=np.asarray(d['y'],float)
    if x.shape!=y.shape or x.ndim!=1 or not np.isfinite(np.r_[x,y]).all(): raise ValueError('Finite aligned one-dimensional points required')
    fig,ax=axes(o)
    if 'color' in d:
        col=np.asarray(d['color']);sc=ax.scatter(x,y,c=col,s=o.get('point_size',9),cmap='viridis',lw=.2,edgecolors='white',alpha=.7)
        fig.colorbar(sc,ax=ax,shrink=.6,label=d.get('color_label','Supplied value'))
    else:ax.scatter(x,y,c=PALETTES['muted'][0],s=o.get('point_size',9),lw=.2,edgecolors='white',alpha=.65)
    if 'point_labels' in d:
        if len(d['point_labels'])!=len(x):raise ValueError('Point identity labels must align exactly')
        if len(x)>24:raise ValueError('Use selected point labels or facets for more than 24 observations')
        ax.margins(x=.10,y=.16)
        ax.set(xlabel=d['xlabel'],ylabel=d['ylabel']);ax.set_title(o.get('title',d.get('title','')),loc='left',pad=12)
        fig.canvas.draw()
        height_pt=ax.get_window_extent().height/fig.dpi*72
        label_gap=max(.075,9.5/height_pt)
        # Place labels on bounded rails in axes coordinates, preserving every point.
        xmin,xmax=ax.get_xlim();ymin,ymax=ax.get_ylim()
        for right in [False,True]:
            ids=[i for i in range(len(x)) if (x[i]>(x.min()+x.max())/2)==right]
            ids.sort(key=lambda i:y[i]);positions=[]
            for i in ids:positions.append(np.clip((y[i]-ymin)/(ymax-ymin)+.025,.08,.92))
            if (len(positions)-1)*label_gap>.84:raise ValueError('Point labels cannot fit at readable physical spacing; use explicit facets or a taller page')
            for j in range(1,len(positions)):positions[j]=max(positions[j],positions[j-1]+label_gap)
            if positions and positions[-1]>.94:positions=np.asarray(positions)-(positions[-1]-.94)
            for i,yy in zip(ids,positions):
                ax.annotate(wrap_label(d['point_labels'][i],24),(x[i],y[i]),xytext=(.98 if right else .02,float(yy)),textcoords='axes fraction',ha='right' if right else 'left',va='center',fontsize=7,arrowprops={'arrowstyle':'-','color':MUTED,'lw':.55},bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':.4})
    if d.get('zero_y'):ax.axhline(0,c=MUTED,lw=.7,ls='--')
    if d.get('diagonal'):
        lo=min(x.min(),y.min());hi=max(x.max(),y.max());ax.plot([lo,hi],[lo,hi],c=MUTED,ls='--',lw=.7)
    ax.set(xlabel=d['xlabel'],ylabel=d['ylabel']);ax.set_title(o.get('title',d.get('title','')),loc='left',pad=12)
    return fig,{'n':len(x),'refit':False}

def forest_panel(d,o):
    t=pd.DataFrame(d['table'])
    if not {'label','estimate','lo','hi'}<=set(t): raise ValueError('Forest requires supplied complete estimate, lo, hi per label; no fabricated CI')
    if t.empty or not np.isfinite(t[['estimate','lo','hi']]).all().all() or (t.lo>t.hi).any():raise ValueError('Invalid complete estimate/interval contract')
    if not d.get('allow_estimate_outside_interval',False) and ((t.lo>t.estimate).any() or (t.hi<t.estimate).any()):raise ValueError('Estimate outside interval: declare a legitimate interval definition rather than silently treating it as a conventional effect CI')
    width=journal_size(o.get('width','onehalf' if len(t)<10 else 'double'),1)[0]*25.4
    if o.get('layout')=='below' or width<=100 and o.get('layout','auto')!='side':return narrow_forest_panel(t,d,o,width)
    n=len(t);fig=plt.figure(figsize=journal_size(o.get('width','onehalf' if n<10 else 'double'),o.get('aspect',max(.45,.055*n+.20))),layout='constrained')
    gs=fig.add_gridspec(1,2,width_ratios=[1,.43],wspace=.04);ax=fig.add_subplot(gs[0,0]);tbl=fig.add_subplot(gs[0,1],sharey=ax)
    y=np.arange(n);cols=np.where(t.estimate>=d.get('null',0),'#C56D56','#39789E')
    for i in range(n):
        if i%2==0:ax.axhspan(i-.48,i+.48,color='#F4F7F8',lw=0);tbl.axhspan(i-.48,i+.48,color='#F4F7F8',lw=0)
        if o.get('variant','interval')=='distribution':
            if 'density' not in t or not isinstance(t.density.iloc[i],dict):raise ValueError('Distribution forest requires frozen density x/y for every row; intervals cannot imply a distribution')
            den=t.density.iloc[i];xx=np.asarray(den['x']);yy=np.asarray(den['y']);yy=yy/max(yy.max(),1e-12)*.30
            ax.fill_between(xx,i-.08,i-.08-yy,color=cols[i],alpha=.35,lw=0)
            ax.plot(xx,i-.08-yy,c=cols[i],lw=.7)
        ax.plot([t.lo.iloc[i],t.hi.iloc[i]],[i,i],c=cols[i],lw=1.5,solid_capstyle='round')
        ax.scatter([t.estimate.iloc[i]],[i],c=cols[i],s=28,edgecolors='white',linewidth=.7,zorder=3)
        tbl.text(.02,i,f'{t.estimate.iloc[i]:+.2f}  [{t.lo.iloc[i]:+.2f}, {t.hi.iloc[i]:+.2f}]',va='center',fontsize=7.5)
    ax.axvline(d.get('null',0),color=MUTED,lw=.8,ls='--');ax.set_yticks(y,[wrap_label(s,29) for s in t.label]);ax.set_xlabel(d.get('unit','Effect with supplied interval'));ax.set_ylim(n-.5,-.5);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',color=GRID,lw=.4);tbl.axis('off')
    tbl.set_title(wrap_label(d.get('interval_label','Estimate [supplied interval]'),23),fontsize=8,loc='left');fig.suptitle(wrap_label(o.get('title','Effect estimates & uncertainty'),60),x=.01,ha='left',fontsize=11,fontweight='bold')
    return fig,{'intervals':'supplied, no estimation in renderer','interval_label':d.get('interval_label','Estimate [supplied interval]'),'rows':n,'variant':o.get('variant','interval')}


def narrow_forest_panel(t,d,o,width):
    """Physical row spacing and a complete numeric table below a narrow forest."""
    labels=[wrap_label(s,19) for s in t.label]
    heights=np.array([1+.6*s.count('\n') for s in labels]);edges=np.r_[0,np.cumsum(heights)];y=(edges[:-1]+edges[1:])/2
    n=len(t);plot_mm=max(24.,float(edges[-1])*5.5);table_mm=9+float(edges[-1])*5.;top=14.;gap=16.;bottom=4.
    height=top+plot_mm+gap+table_mm+bottom
    if 'aspect' in o:height=max(height,width*o['aspect'])
    if height>480:raise ValueError('Narrow forest exceeds a readable page; select/paginate rows explicitly')
    fig=plt.figure(figsize=(width/25.4,height/25.4));left=min(width*.40,max(23.,max(len(line) for label in labels for line in label.split('\n'))*1.18+3))
    ax=fig.add_axes([left/width,(bottom+table_mm+gap)/height,(width-left-4)/width,plot_mm/height]);table=fig.add_axes([4/width,bottom/height,(width-8)/width,table_mm/height]);table.axis('off')
    cols=np.where(t.estimate>=d.get('null',0),'#C56D56','#39789E')
    for i in range(n):
        if i%2==0:ax.axhspan(edges[i]+.03,edges[i+1]-.03,color='#F4F7F8',lw=0)
        if o.get('variant','interval')=='distribution':
            if 'density' not in t or not isinstance(t.density.iloc[i],dict):raise ValueError('Distribution forest requires actual frozen density grids, never CIs converted to densities')
            den=t.density.iloc[i];xx=np.asarray(den['x']);yy=np.asarray(den['y']);yy=yy/max(yy.max(),1e-12)*.28
            ax.fill_between(xx,y[i]-.08,y[i]-.08-yy,color=cols[i],alpha=.35,lw=0);ax.plot(xx,y[i]-.08-yy,color=cols[i],lw=.7)
        ax.plot([t.lo.iloc[i],t.hi.iloc[i]],[y[i],y[i]],c=cols[i],lw=1.5,solid_capstyle='round');ax.scatter([t.estimate.iloc[i]],[y[i]],c=cols[i],s=24,edgecolors='white',linewidth=.7,zorder=3)
    ax.axvline(d.get('null',0),c=MUTED,lw=.8,ls='--');ax.set_ylim(edges[-1]+.05,-.05);ax.set_yticks(y,labels,fontsize=7);ax.tick_params(axis='y',length=0);ax.spines['left'].set_visible(False);ax.grid(axis='x',c=GRID,lw=.4);ax.set_xlabel(wrap_label(d.get('unit','Supplied effect'),33),fontsize=8)
    table.text(.01,.98,'Feature',va='top',fontsize=7,fontweight='bold');table.text(.99,.98,wrap_label(d.get('interval_label','Estimate [supplied interval]'),33),ha='right',va='top',fontsize=7,fontweight='bold')
    for i,label in enumerate(labels):
        yc=1-(9+y[i]*5)/table_mm;half=heights[i]*2.5/table_mm
        if i%2==0:table.axhspan(yc-half,yc+half,color='#F4F7F8',lw=0,zorder=0)
        table.text(.01,yc,label,va='center',fontsize=7);table.text(.99,yc,f'{t.estimate.iloc[i]:+.2f}  [{t.lo.iloc[i]:+.2f}, {t.hi.iloc[i]:+.2f}]',ha='right',va='center',fontsize=7)
    table.set(xlim=(0,1),ylim=(0,1));fig.suptitle(wrap_label(o.get('title','Effect estimates & uncertainty'),42),x=.02,y=.98,ha='left',fontsize=10,fontweight='bold')
    return fig,{'intervals':'supplied, no estimation in renderer','interval_label':d.get('interval_label','Estimate [supplied interval]'),'rows':n,'variant':o.get('variant','interval'),'layout':'numeric_table_below','row_spacing_mm':5.5}

def bars_panel(d,o,kind='bars'):
    t=pd.DataFrame(d['table']);labels=t['label'].astype(str).tolist();values=t['value'].to_numpy(float)
    n=len(t)
    if n>30 and not o.get('allow_dense'): raise ValueError('Paginate more than 30 labelled bars')
    o={**o,'width':o.get('width','onehalf' if n<=8 else 'double')};fig,ax=axes(o,max(.40,.035*n+.15));colors=o.get('colors')
    if colors is None: colors=np.where(values>=0,'#C56D56','#39789E').tolist() if np.any(values<0) else [PALETTES['muted'][0]]*n
    ax.barh(np.arange(n),values,color=colors,height=.62,edgecolor='white',lw=.5)
    if np.all(values==0):
        ax.scatter(np.zeros(n),np.arange(n),s=16,c=colors,edgecolors='white',lw=.5,zorder=3)
        ax.set_xticks([0]);ax.set_xlim(-.05,.05)
    if o.get('value_labels',n<=8):
        span=max(np.ptp(np.r_[0,values]),1e-9)
        for i,v in enumerate(values):ax.text(v+span*.02*(1 if v>=0 else -1),i,format(v,o.get('value_format','.4g')),ha='left' if v>=0 else 'right',va='center',fontsize=7)
        ax.margins(x=.13)
    if 'lo' in t or 'hi' in t:
        if not {'lo','hi'}<=set(t): raise ValueError('Both interval limits required')
        ax.errorbar(values,np.arange(n),xerr=np.vstack([values-t.lo,t.hi-values]),fmt='none',ecolor=INK,capsize=2,lw=.7)
    elif 'sem' in t:
        if (t['sem']<0).any() or not np.isfinite(t['sem']).all():raise ValueError('Finite nonnegative supplied SEM required')
        ax.errorbar(values,np.arange(n),xerr=t['sem'],fmt='none',ecolor=INK,capsize=2,lw=.7,label=d.get('error_label','Supplied SEM'))
        ax.legend(loc='lower right')
    ax.set_yticks(np.arange(n),[wrap_label(x,30) for x in labels]);ax.invert_yaxis();ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',color=GRID,lw=.4);ax.set_xlabel(d.get('unit','Supplied value'));ax.set_title(o.get('title',d.get('title','')),loc='left',pad=12)
    return fig,{'n':n,'unit':d.get('unit'),'uncertainty_supplied':'lo' in t or 'sem' in t,'uncertainty_kind':'source SEM, not CI' if 'sem' in t else 'supplied interval' if 'lo' in t else None}

def gsea_panel(d,o):
    paths=d['pathways'];n=len(paths); nr,nc=choose_grid(n,o.get('ncols',1),o.get('nrows'))
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.55*nr)),layout='constrained')
    outer=fig.add_gridspec(nr,nc,hspace=.10,wspace=.12)
    for i,p in enumerate(paths):
        gs=outer[i//nc,i%nc].subgridspec(3,1,height_ratios=[1,.18,.35],hspace=.02)
        a=fig.add_subplot(gs[0]);h=fig.add_subplot(gs[1],sharex=a);m=fig.add_subplot(gs[2],sharex=a)
        x=np.asarray(p['rank']);es=np.asarray(p['es']);metric=np.asarray(p['metric']);hits=np.asarray(p['hits'],int)
        if es.shape!=x.shape or metric.shape!=x.shape or (hits<0).any() or (hits>=len(x)).any():raise ValueError('GSEA rank/ES/metric/hits alignment invalid')
        a.plot(x,es,c=PALETTES['muted'][i%8],lw=1.5);a.axhline(0,c=GRID,lw=.7);a.set_ylabel('Running ES');a.tick_params(labelbottom=False)
        a.set_title(wrap_label(p['name'],60),loc='left',fontsize=9)
        if p.get('NES') is not None:a.text(.99,.95,f'NES {p["NES"]:.2f}  ·  FDR {p["fdr"]:.3g}',transform=a.transAxes,ha='right',va='top',fontsize=7)
        h.vlines(x[hits],0,1,color=PALETTES['muted'][i%8],lw=.45);h.set_ylim(0,1);h.axis('off')
        m.fill_between(x,metric,0,where=metric>=0,color='#C56D56',alpha=.55,lw=0);m.fill_between(x,metric,0,where=metric<0,color='#39789E',alpha=.55,lw=0);m.set(xlabel='Rank in supplied ordered gene universe',ylabel='Rank metric');m.axhline(0,c=GRID,lw=.5)
        if p.get('leading_edge') is not None:
            edge=p['leading_edge'];a.axvspan(x[min(edge)],x[max(edge)],color=PALETTES['muted'][i%8],alpha=.07,lw=0)
    return fig,{'pathways':[p['name'] for p in paths],'ES_refit':False,'lanes':'ES, hits, ranking','nrows':nr,'ncols':nc}

def effect_matrix_panel(d,o):
    # Complete CI contract: matrix axes must be identical; long tables require
    # unique explicit row/column identity. Never match by numeric position only.
    if 'table' in d:
        t=pd.DataFrame(d['table'])
        if not {'row','column','estimate','lo','hi'}<=set(t):raise ValueError('Long CI input requires row,column,estimate,lo,hi')
        if t.duplicated(['row','column']).any():raise ValueError('Duplicate effect matrix cell')
        cols=list(dict.fromkeys(t.column));rows=list(dict.fromkeys(t.row))
    else:
        if not {'estimate','lo','hi'}<=set(d):raise ValueError('Effect matrix requires complete estimate, lo and hi matrices, or an explicit long CI table')
        e=matrix_input(d['estimate']);lo=matrix_input(d['lo']);hi=matrix_input(d['hi'])
        if not e.index.equals(lo.index) or not e.index.equals(hi.index) or not e.columns.equals(lo.columns) or not e.columns.equals(hi.columns):raise ValueError('Estimate/CI named matrix axes do not align')
        rows=list(e.index);cols=list(e.columns);t=pd.DataFrame([{'row':r,'column':c,'estimate':e.loc[r,c],'lo':lo.loc[r,c],'hi':hi.loc[r,c]} for r in rows for c in cols])
    if len(cols)>4 or len(rows)>35:raise ValueError('Paginate CI matrices beyond 4 columns or 35 rows')
    if not np.isfinite(t[['estimate','lo','hi']]).all().all() or (t.lo>t.estimate).any() or (t.hi<t.estimate).any():raise ValueError('Complete finite CI containing estimate required')
    fig,aa=axes({**o,'width':o.get('width','onehalf' if len(cols)<=2 and len(rows)<=8 else 'double')},max(.33,len(rows)*.055+.16),ncols=len(cols),squeeze=False,sharex=True,sharey=True)
    limit=max(abs(t.lo.min()),abs(t.hi.max()))*1.1
    for ax,c in zip(aa.flat,cols):
        sub=t[t.column==c].set_index('row').reindex(rows)
        for i,row in enumerate(sub.itertuples()):
            color='#C56D56' if row.estimate>=0 else '#39789E'
            ax.axhspan(i-.45,i+.45,color='#F6F8F9' if i%2==0 else 'white',lw=0)
            ax.plot([row.lo,row.hi],[i,i],color=color,lw=1.35,solid_capstyle='round');ax.scatter([row.estimate],[i],s=21,c=color,edgecolor='white',lw=.5,zorder=3)
        ax.axvline(0,c=MUTED,lw=.7,ls='--');ax.set_xlim(-limit,limit);ax.set_yticks(range(len(rows)),[wrap_label(x,28) for x in rows]);ax.set_ylim(len(rows)-.5,-.5);ax.set_title(wrap_label(c,25),fontsize=8.5);ax.set_xlabel(d.get('unit','Effect'));ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',color=GRID,lw=.4)
    return fig,{'variant':'aligned interval matrix','CI_source':'provided','shared_effect_scale':True,'rows':rows,'columns':cols}

def marker_strip_panel(d,o):
    xy=np.asarray(d['embedding']);expr=np.asarray(d['expression']);group=np.asarray(d['groups']);order=d['group_order']
    selection=o.get('marker_map',{'CD4 T cells':['IL7R','CCR7'],'CD14+ Monocytes':['CD14','LYZ'],'B cells':['MS4A1','CD79A'],'CD8 T cells':['CD3D','LTB'],'NK cells':['NKG7','GNLY'],'FCGR3A+ Monocytes':['FCGR3A','MS4A7'],'Dendritic cells':['FCER1A','CST3'],'Megakaryocytes':['PPBP','LYZ']})
    selected=o.get('groups',order);pagesize=int(o.get('groups_per_page',4))
    if len(selected)>pagesize:raise ValueError('marker_strip requires explicit group page; use groups=... or groups_per_page, pagination is not silently omitted')
    cols=int(o.get('ncols',3));nr=len(selected)
    if cols<2:raise ValueError('Marker evidence strip needs identity and marker columns')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.33*nr)),layout='constrained');gs=fig.add_gridspec(nr,cols,wspace=.06,hspace=.14)
    cmap=LinearSegmentedColormap.from_list('marker',PALETTES['teal-depth'])
    for i,g in enumerate(selected):
        genes=selection[g]
        if len(genes)>cols-1:raise ValueError('Requested marker count exceeds available columns; expand ncols')
        for j in range(cols):
            ax=fig.add_subplot(gs[i,j]);ax.scatter(xy[:,0],xy[:,1],s=.55,c='#E0E6EA',lw=0)
            if j==0:
                hit=group==g;ax.scatter(xy[hit,0],xy[hit,1],s=1.4,c='#566F88',lw=0);title=wrap_label(g,22)
            elif j<=len(genes):
                gene=genes[j-1];idx=d['markers'].index(gene);v=expr[:,idx];ix=np.argsort(v,kind='stable');sc=ax.scatter(xy[ix,0],xy[ix,1],s=o.get('point_size',2.4),c=v[ix],cmap=cmap,norm=mpl.colors.PowerNorm(o.get('color_gamma',.5),vmin=0,vmax=float(expr.max())),lw=0);title=gene
            else:ax.remove();continue
            ax.set_title(title,fontsize=7.5,pad=3);ax.set_xticks([]);ax.set_yticks([]);ax.spines[:].set_visible(False);ax.set_aspect('equal')
    fig.suptitle(o.get('title','Each cell identity with its marker evidence'),fontsize=10,x=.01,ha='left',fontweight='bold')
    fig.colorbar(sc,ax=fig.axes,shrink=.35,label='Log1p expression',pad=.02)
    return fig,{'embedding_refit':False,'groups':selected,'marker_map':selection,'shared_color_scale':True,'columns':cols,'rows':nr}

def proportion_panel(d,o):
    values=np.asarray(d['values'],float);categories=d['categories'];groups=d['labels']
    if values.shape!=(len(groups),len(categories)) or (values<0).any() or not np.isfinite(values).all():raise ValueError('Aligned nonnegative group × category values required')
    totals=values.sum(axis=1)
    if (totals<=0).any():raise ValueError('Empty denominator')
    supplied_proportions=d.get('already_proportions',False)
    if supplied_proportions and (np.any(values>1) or not np.allclose(totals,1,atol=1e-6,rtol=0)):raise ValueError('Already-proportion channel must sum to one without re-estimation')
    prop=values.copy() if supplied_proportions else values/totals[:,None];colors=identity_colors(o.setdefault('theme',{'palette':o.get('palette','muted')}),categories)
    if len(groups)==1 and not supplied_proportions and o.get('variant','composition_card')=='composition_card':
        ncol=int(o.get('legend_columns',2 if o.get('width')=='single' else 4));nrow=int(np.ceil(len(categories)/ncol))
        if ncol<1:raise ValueError('Positive composition legend column count required')
        width=o.get('width','double');aspect=o.get('aspect',(24+13*nrow)/WIDTH_MM[width])
        fig=plt.figure(figsize=journal_size(width,aspect),layout='constrained');gs=fig.add_gridspec(2,1,height_ratios=[.55,nrow],hspace=.04);ax=fig.add_subplot(gs[0]);key=fig.add_subplot(gs[1]);key.axis('off');left=0
        for j,c in enumerate(categories):ax.barh(0,prop[0,j],left=left,color=colors[c],height=.50,edgecolor='white',lw=.6);left+=prop[0,j]
        ax.set_xlim(0,1);ax.set_yticks([]);ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter(1));ax.spines[:].set_visible(False);ax.tick_params(axis='x',length=0,labelsize=6.5)
        for j,c in enumerate(categories):
            x=(j%ncol)/ncol;y=1-(j//ncol+.55)/nrow
            key.add_patch(Rectangle((x+.01,y-.02),.018,.055,transform=key.transAxes,facecolor=colors[c],clip_on=False))
            txt=wrap_label(c,19 if ncol>2 else 23)+'\n'+f'{values[0,j]:,.0f}  |  {prop[0,j]:.1%}'
            key.text(x+.045,y+.04,txt,transform=key.transAxes,ha='left',va='top',fontsize=7.2,linespacing=1.25)
        fig.suptitle(wrap_label(str(groups[0])+f' · n = {totals[0]:,.0f}',70),x=.02,ha='left',fontsize=10,fontweight='bold')
        return fig,{'denominators':totals.tolist(),'normalization':'within supplied row','variant':'stacked composition and full count/fraction key','categories':categories,'identity_colors':colors}
    width_mm=journal_size(o.get('width','double'),1)[0]*25.4
    aspect=max(.35,(24+6*len(groups))/width_mm) if supplied_proportions else max(.55,.1*len(groups)+.2)
    fig,ax=axes(o,aspect);left=np.zeros(len(groups))
    for j,c in enumerate(categories):
        ax.barh(np.arange(len(groups)),prop[:,j],left=left,color=colors[c],label=c,height=.55,edgecolor='white',lw=.7);left+=prop[:,j]
    ax.set_yticks(np.arange(len(groups)),[wrap_label(s,25) for s in groups]);ax.set_xlim(0,1);ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter(1));ax.set_xlabel(d.get('unit','Supplied proportion') if supplied_proportions else 'Fraction of supplied observations');ax.invert_yaxis();ax.spines[:].set_visible(False);ax.tick_params(axis='y',length=0)
    if supplied_proportions and width_mm<=120:
        handles,labels=ax.get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncols=min(3,len(categories)),fontsize=7)
    else:ax.legend(loc='upper left',bbox_to_anchor=(1.01,1))
    ax.set_title(o.get('title','Composition & denominators'),loc='left')
    return fig,{'denominators':None if supplied_proportions else totals.tolist(),'normalization':'none; supplied probabilities retained' if supplied_proportions else 'within supplied row, no replication assumption'}

def spectra_panel(d,o):
    # Physical panel width matters: a long vertical label can protrude above
    # a short spectrum even when constrained_layout has enough horizontal room.
    narrow=journal_size(o.get('width','double'),1)[0]*25.4<=120
    o={**o}
    if narrow:o['aspect']=max(float(o.get('aspect',.58)),.58)
    ylabel=wrap_label(d['ylabel'],24 if narrow else 38)
    if o.get('facet',False):
        nr,nc=choose_grid(len(d['spectra']),o.get('ncols',1),o.get('nrows'));fig,aa=axes(o,.36*nr,nrows=nr,ncols=nc,squeeze=False)
        for ax,s in zip(aa.flat,d['spectra']):
            x=np.asarray(s['x']);y=np.asarray(s['y']);ax.plot(x,y,color='#3B6F91',lw=1.1);ax.fill_between(x,y,0,color='#3B6F91',alpha=.12,lw=0)
            if 'sticks_x' in s:ax.vlines(s['sticks_x'],0,s['sticks_y'],color='#CA7354',lw=.6,alpha=.5)
            ax.set(xlabel=d['xlabel'],ylabel=ylabel,title=s['label']);ax.set_xlim(x.min(),x.max())
            if d.get('reverse_x'):ax.invert_xaxis()
        for ax in aa.flat[len(d['spectra']):]:ax.remove()
        return fig,{'curves':[s['label'] for s in d['spectra']],'faceted':True,'independent_spectral_x_ranges':True,'broadening_recomputed':False}
    full_range=(min(min(s['x']) for s in d['spectra']),max(max(s['x']) for s in d['spectra']));focus_range=None
    if o.get('signal_focus',True):
        active=[]
        for spectrum in d['spectra']:
            x=np.asarray(spectrum['x']);y=np.asarray(spectrum['y']);cut=float(o.get('signal_display_fraction',.003))*max(np.max(np.abs(y)),1e-30)
            active.extend(x[np.abs(y)>cut].tolist())
        if active and max(active)-min(active)<.65*(full_range[1]-full_range[0]):
            padding=(max(active)-min(active))*.12
            focus_range=(max(full_range[0],min(active)-padding),min(full_range[1],max(active)+padding))
    if focus_range:
        fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.49)),layout='constrained')
        gs=fig.add_gridspec(1,2,width_ratios=[1,.42],wspace=.12);ax=fig.add_subplot(gs[0,0]);overview=fig.add_subplot(gs[0,1],sharey=ax)
    else:fig,ax=axes(o,.40);overview=None
    for i,spectrum in enumerate(d['spectra']):
        x=np.asarray(spectrum['x']);y=np.asarray(spectrum['y']);color=PALETTES['muted'][i]
        if x.shape!=y.shape or not np.isfinite(np.r_[x,y]).all():raise ValueError('Finite aligned spectral grid required')
        ax.plot(x,y,color=color,label=wrap_label(spectrum['label'],45),lw=1.3)
        if 'sticks_x' in spectrum:ax.vlines(spectrum['sticks_x'],0,spectrum['sticks_y'],lw=.6,color=color,alpha=.4)
        if o.get('fill',True):ax.fill_between(x,y,0,color=color,alpha=.10,lw=0)
        if overview is not None:overview.plot(x,y,c=color,lw=.8)
    ax.axhline(0,color=GRID,lw=.6);ax.set(xlabel=d['xlabel'],ylabel=ylabel);ax.set_xlim(*(focus_range or full_range))
    if overview is not None:
        overview.set_xlim(*full_range);overview.axvspan(*focus_range,color='#C3D0D9',alpha=.25,lw=0);overview.set_title('Full supplied range',fontsize=8);overview.set_xlabel(d['xlabel']);overview.tick_params(axis='y',labelleft=False)
        fig.legend(*ax.get_legend_handles_labels(),loc='outside lower center',ncols=1)
        fig.suptitle(o.get('title',d.get('title','')),x=.01,ha='left',fontweight='bold')
    else:ax.set_title(o.get('title',d.get('title','')),loc='left',pad=12);ax.legend(loc='best')
    if d.get('reverse_x'):
        ax.invert_xaxis()
        if overview is not None:overview.invert_xaxis()
    return fig,{'broadening_recomputed':False,'curves':[spectrum['label'] for spectrum in d['spectra']],'x_unit':d['xlabel'],'full_supplied_x_range':full_range,'main_display_focus':focus_range,'full_range_side_panel':focus_range is not None,'display_cutoff_fraction':o.get('signal_display_fraction',.003)}

def ml_panel(d,o,kind):
    models=d.get('models',{});names=list(models);colors=identity_colors(o.setdefault('theme',{'palette':o.get('palette','muted')}),names)
    evaluation=d.get('evaluation',{});scope=evaluation.get('scope','UNSPECIFIED_NOT_VALIDATED')
    positive=d.get('positive_class','Positive');class_labels=d.get('class_labels',['Negative',positive])
    if kind in ('roc_multi','pr_curve','calibration'):
        key={'roc_multi':'roc','pr_curve':'pr','calibration':'calibration'}[kind]
        curves=[]
        for n,m in models.items():
            curve=m[key];statistic='auc' if key=='roc' else 'ap' if key=='pr' else None
            lab=n+(f' · {statistic.upper()} {curve[statistic]:.3f}' if statistic is not None and statistic in curve else '')
            x,y=np.asarray(curve['x'],float),np.asarray(curve['y'],float)
            if x.ndim!=1 or x.shape!=y.shape or not len(x) or not np.isfinite(np.r_[x,y]).all() or ((x<0)|(x>1)|(y<0)|(y>1)).any():raise ValueError('Supplied ROC/PR/calibration axes must be finite aligned coordinates in [0,1]')
            curves.append({'label':lab,'x':curve['x'],'y':curve['y']})
        if key=='calibration' and o.get('variant','distribution')=='distribution':
            fig=plt.figure(figsize=journal_size(o.get('width','onehalf'),o.get('aspect',1.16)),layout='constrained');gs=fig.add_gridspec(2,len(names),height_ratios=[1,.30],hspace=.09);ax=fig.add_subplot(gs[0,:]);bottom=[]
            for i,name in enumerate(names):
                hist=fig.add_subplot(gs[1,i]);hist.hist(models[name]['probability'],bins=np.linspace(0,1,16),color=colors[name],edgecolor='white',lw=.3,alpha=.8);hist.set(xlabel='Predicted probability',ylabel='Observations',title=name);hist.set_xlim(0,1);bottom.append(hist)
        else:
            o={**o,'width':o.get('width','onehalf')};fig,ax=axes(o,.95)
        for i,c in enumerate(curves):
            ax.plot(c['x'],c['y'],color=colors[names[i]],lw=1.3,label=c['label'],drawstyle='steps-post' if key=='pr' else 'default',marker='o' if key=='calibration' else None,markersize=3,markeredgewidth=.5,markeredgecolor='white')
        if key in ('roc','calibration'):ax.plot([0,1],[0,1],c=MUTED,ls='--',lw=.75)
        if key=='pr':ax.axhline(np.mean(d['y']),c=MUTED,ls='--',lw=.75,label='Positive prevalence')
        ax.set(xlim=(0,1),ylim=(0,1.02),xlabel={'roc':'False positive rate','pr':'Recall','calibration':'Mean predicted probability'}[key],ylabel={'roc':'Sensitivity','pr':'Precision','calibration':'Observed positive fraction'}[key]);ax.set_aspect('equal');ax.grid(color=GRID,lw=.4);ax.legend(loc='lower right' if key=='roc' else 'best');ax.set_title(o.get('title',{'roc':'ROC discrimination','pr':'Precision–recall','calibration':'Probability calibration'}[key]),loc='left',pad=12)
        return fig,{'predictions':scope,'evaluation':evaluation,'CI':'not supplied; not fabricated','positive':positive}
    if kind=='training_dashboard':
        h=pd.DataFrame(d['additional']['history']);width=journal_size(o.get('width','double'),1)[0]*25.4
        nr,nc=choose_grid(2+len(names),ncols=o.get('ncols',2 if width>=150 else 1),nrows=o.get('nrows'))
        fig,aa=axes(o,max(.65,nr*.45),nrows=nr,ncols=nc,squeeze=False)
        for ax,metric in zip(list(aa.flat)[:2],['loss','auc']):
            for i,split in enumerate(['train','validation']):ax.plot(h.epoch,h[split+'_'+metric],c=PALETTES['muted'][i],label=split.title(),lw=1.3)
            ax.axvline(d['additional']['checkpoint_epoch'],c=MUTED,ls='--',lw=.7);ax.set(xlabel='Epoch',ylabel='Log loss' if metric=='loss' else 'ROC AUC',title='Objective' if metric=='loss' else 'Discrimination');ax.legend()
        for ax,name in zip(list(aa.flat)[2:],names):
            pr=np.array(models[name]['probability']);y=np.array(d['y'])
            for k,label in enumerate(class_labels):ax.hist(pr[y==k],bins=np.linspace(0,1,21),histtype='stepfilled',alpha=.35,color=PALETTES['muted'][k],label=label)
            ax.set(xlabel='Predicted positive probability',ylabel='Observed samples',title=name+' · supplied predictions');ax.legend()
        for ax in list(aa.flat)[2+len(names):]:ax.set_visible(False)
        return fig,{'history':'supplied recorded optimization history','evaluation':evaluation,'predictions':scope,'checkpoint_epoch':d['additional']['checkpoint_epoch']}
    if kind=='decision_boundary':
        b=d['additional']['boundary'];fig,ax=axes(o,.65);z=np.array(b['z']);points=np.array(b['points']);cl=np.array(b['classes']);im=ax.contourf(b['x'],b['y'],z,levels=np.linspace(0,1,21),cmap=LinearSegmentedColormap.from_list('boundary',PALETTES['blue-coral']),alpha=.24);ax.contour(b['x'],b['y'],z,levels=[.5],colors=INK,linewidths=1)
        for k,label in enumerate(class_labels):
            p=points[cl==k];ax.scatter(p[:,0],p[:,1],s=8,c=PALETTES['muted'][k],edgecolors='white',lw=.3,label=label,alpha=.8)
        ax.set(xlabel=b['features'][0],ylabel=b['features'][1],title='Two-feature descriptive classifier');fig.colorbar(im,ax=ax,shrink=.7,label='Predicted probability',ticks=[0,.25,.5,.75,1]);ax.legend();return fig,{'two_feature_model':True,'not_full_model_boundary':True}
    if kind=='shap_interaction':
        from renderers import draw_heatmap
        from shap_channels import contribution_unit
        inter=d['additional']['interaction'];matrix=np.asarray(inter['matrix'],float).copy();kind=inter.get('matrix_kind')
        unit=inter.get('unit') or contribution_unit(d)
        if kind not in ('full_shap_interaction','off_diagonal_only'):raise ValueError('Declare matrix_kind: full_shap_interaction includes main effects on the diagonal; off_diagonal_only omits them')
        if matrix.shape!=(len(inter['features']),len(inter['features'])):raise ValueError('Interaction feature axes must match the square matrix')
        if kind=='off_diagonal_only':np.fill_diagonal(matrix,np.nan)
        finite=matrix[np.isfinite(matrix)]
        if not len(finite) or np.isinf(matrix).any():raise ValueError('At least one finite supplied interaction value is required')
        extent=float(np.abs(finite).max());constant_zero=extent==0;extent=1. if constant_zero else extent
        color_ticks=[0] if constant_zero else [-extent,0,extent]
        fig,meta=draw_heatmap({'matrix':{'values':matrix,'rows':inter['features'],'columns':inter['features']}},{**o,'cluster':False,'vmin':o.get('vmin',-extent),'vmax':o.get('vmax',extent),'color_ticks':color_ticks,'color_tick_labels':[f'{v:.2g}' for v in color_ticks],'color_label':'Supplied pairwise contribution ('+unit+')','title':'Additive model · off-diagonal pairwise terms' if kind=='off_diagonal_only' else 'Supplied SHAP interaction matrix','annotate':True,'aspect':.80,'missing_label':'Diagonal omitted: main effects not supplied'})
        meta.update(unit=unit,matrix_kind=kind,all_supplied_interactions_zero=constant_zero,diagonal='omitted, not zero main effects' if kind=='off_diagonal_only' else 'supplied main effects',interaction_method=inter.get('scope','supplied upstream'))
        return fig,meta
    if kind=='parallel_coords':
        fig,ax=axes(o,.55);labels=['ROC AUC','Average precision','Sensitivity','Specificity']
        for name in names:
            cm=np.array(models[name]['confusion']);v=[models[name]['roc']['auc'],models[name]['pr']['ap'],cm[1,1]/sum(cm[1]),cm[0,0]/sum(cm[0])];ax.plot(range(4),v,color=colors[name],marker='o',ms=4,lw=1.3,label=name)
        ax.set_xticks(range(4),labels);ax.set(ylim=(0,1),ylabel='Supplied metric on common [0,1] scale',title='Comparable model profiles');ax.grid(axis='x',color=GRID,lw=.8);ax.legend();return fig,{'metrics':'all higher is better; no normalization to hide differences','predictions':scope,'evaluation':evaluation}
    if kind=='confusion':
        width=journal_size(o.get('width','double'),1)[0]*25.4
        nc=o.get('ncols',min(len(names),2 if width>=150 else 1));nr,nc=choose_grid(len(names),ncols=nc,nrows=o.get('nrows'))
        if width/nc<55:raise ValueError('Confusion panels need at least 55 mm; choose fewer columns')
        fig,aa=plt.subplots(nr,nc,squeeze=False,figsize=(width/25.4,(nr*(width/nc*.80+12))/25.4),layout='constrained')
        for ax,name in zip(aa.flat,names):
            m=np.asarray(models[name]['confusion'],float)
            if len(class_labels)!=2 or len(set(class_labels))!=2 or m.shape!=(2,2) or not np.isfinite(m).all() or (m<0).any() or not np.equal(m,np.floor(m)).all():raise ValueError('Binary confusion matrix requires literal two-class order and nonnegative observed integer counts')
            r=np.divide(m,m.sum(axis=1)[:,None],out=np.full_like(m,np.nan),where=m.sum(axis=1)[:,None]>0);ax.imshow(np.ma.masked_invalid(r),vmin=0,vmax=1,cmap=LinearSegmentedColormap.from_list('blue-depth',PALETTES['blue-depth']))
            for i in range(2):
                for j in range(2):ax.text(j,i,f'{m[i,j]:g}\n'+(f'{r[i,j]:.1%}' if np.isfinite(r[i,j]) else 'NA'),ha='center',va='center',color='white' if r[i,j]>.55 else INK,fontsize=8.5)
            ax.set_xticks([0,1],[wrap_label(x,14) for x in class_labels]);ax.set_yticks([0,1],[wrap_label(x,14) for x in class_labels]);ax.set(xlabel='Predicted',ylabel='Observed',title=name);ax.tick_params(length=0);ax.spines[:].set_visible(False)
        for ax in aa.flat[len(names):]:ax.set_visible(False)
        return fig,{'threshold':evaluation.get('threshold'),'color':'row fraction; undefined rows are NA','text':'count and row fraction','predictions':scope,'class_labels':class_labels,'layout':{'rows':nr,'columns':nc}}
    if kind=='shap_summary':
        if o.get('variant') in ('rose','beeswarm_rose'):
            from shap_views import shap_summary_view
            return shap_summary_view(d,o)
        shap=np.asarray(d['explanation']['shap']);values=np.asarray(d['explanation']['feature_values']);names=d['features'];imp=np.mean(np.abs(shap),axis=0);ix=np.argsort(imp)[-min(12,len(names)):]
        fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.8)),layout='constrained');gs=fig.add_gridspec(1,3,width_ratios=[1,.4,.035],wspace=.07);ax=fig.add_subplot(gs[0,0]);bar=fig.add_subplot(gs[0,1],sharey=ax);cbax=fig.add_subplot(gs[0,2])
        norm=mpl.colors.Normalize(*d['feature_value_limits']);cmap=LinearSegmentedColormap.from_list('SHAP',PALETTES['blue-coral'])
        for i,j in enumerate(ix):
            s=shap[:,j];order=np.argsort(s,kind='stable'); offset=np.zeros(len(s));bins=np.round((s-s.min())/max(np.ptp(s),1e-9)*45)
            maximum=max(np.sum(bins==b) for b in np.unique(bins));step=.33/max(1,np.ceil(maximum/2))
            for b in np.unique(bins):
                ind=np.flatnonzero(bins==b);rank=np.arange(len(ind));offset[ind]=((rank//2+1)*np.where(rank%2,1,-1))*step
            ax.scatter(s,i+offset,s=4,c=values[:,j],cmap=cmap,norm=norm,alpha=.65,lw=0,rasterized=False)
        ax.axvline(0,color=GRID,lw=.8);ax.set_yticks(range(len(ix)),[wrap_label(names[j],25) for j in ix]);ax.set_xlabel('SHAP contribution ('+d['explanation']['unit']+')');ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
        bar.barh(range(len(ix)),imp[ix],color='#698AA0',height=.58);bar.tick_params(axis='y',labelleft=False,length=0);bar.spines['left'].set_visible(False);bar.set_xlabel('Mean |contribution|');bar.grid(axis='x',color=GRID,lw=.4)
        cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cbax,extend='both');cb.set_label(d['feature_value_label']);cb.outline.set_visible(False)
        if d.get('feature_value_mode')=='within_feature_range':cb.set_ticks([0,1],labels=['Low','High'])
        fig.suptitle(o.get('title','SHAP · distribution & global magnitude'),x=.01,ha='left',fontsize=11,fontweight='bold')
        return fig,{'explainer':d['explanation'].get('algorithm','supplied upstream'),'scope':d['explanation'].get('scope','UNSPECIFIED_NOT_VALIDATED'),'unit':d['explanation']['unit'],'beeswarm':'deterministic binned collision offsets'}
    if kind=='shap_dependence':
        sh=np.asarray(d['explanation']['shap']);v=np.asarray(d['explanation']['original_feature_values']);j=int(np.argmax(np.abs(sh).mean(axis=0)));k=int(np.argsort(np.abs(sh).mean(axis=0))[-2]) if sh.shape[1]>1 else j;return scatter_panel({'x':v[:,j],'y':sh[:,j],'color':v[:,k],'xlabel':d['features'][j]+' (supplied value)','ylabel':'SHAP contribution ('+d['explanation']['unit']+')','color_label':d['features'][k],'title':'Contribution dependence'},o)
    if kind=='feat_importance':
        sh=np.asarray(d['explanation']['shap']);imp=np.mean(np.abs(sh),axis=0);ix=np.argsort(imp)[-12:][::-1];return bars_panel({'table':[{'label':d['features'][j],'value':imp[j]} for j in ix],'unit':'Mean |SHAP| ('+d['explanation']['unit']+')','title':'Feature contribution magnitude'},o)
    if kind in ('learning_curve','grid_heatmap'):
        if kind=='learning_curve':
            lr=d['learning'];c=[]
            for k in ['train','validation']:
                v=np.asarray(lr[k]);c.append({'label':k.title(),'x':lr['n'],'y':v.mean(axis=1).tolist(),'lo':v.min(axis=1).tolist(),'hi':v.max(axis=1).tolist()})
            return line_panel({'curves':c,'xlabel':'Training samples per fold','ylabel':'ROC AUC','title':'Learning curve · fold range (not CI)'},o)
        from renderers import draw_heatmap
        g=d['grid'];fold_count=len(g[0]['auc'])
        if not fold_count or any(len(row['auc'])!=fold_count for row in g):raise ValueError('Complete actual same-fold validation scores required for each setting')
        return draw_heatmap({'matrix':{'values':[x['auc'] for x in g],'rows':[f'C={x["C"]}' for x in g],'columns':[f'Fold {i+1}' for i in range(fold_count)]}},{**o,'cluster':False,'cmap':'teal-depth','color_label':'Supplied validation AUC','annotate':True,'number_format':'.3f','title':'Predeclared regularization settings'})
    if kind=='cv_box':
        from renderers import draw_raincloud
        return draw_raincloud({'labels':names,'values':[models[n]['fold_auc'] for n in names],'unit':'Supplied validation fold AUCs'},o)
    if kind in ('reg_scatter','reg_diagnostics'):
        r=d['regression']
        if kind=='reg_diagnostics' and o.get('variant','diagnostic_panels')!='residual_only':
            nr,nc=choose_grid(4,o.get('ncols',2),o.get('nrows'));fig,aa=axes(o,.43*nr,nrows=nr,ncols=nc,squeeze=False);a,b,c,e=aa.flat[:4];yp=np.asarray(r['prediction']);res=np.asarray(r['residual']);observed=np.asarray(r['y'])
            a.scatter(yp,res,s=6,c='#3B6F91',alpha=.6,lw=0);a.axhline(0,c=MUTED,ls='--',lw=.7);a.set(xlabel='Supplied prediction',ylabel='Residual',title='Signed error')
            b.hist(res,bins=22,color='#6E91AD',edgecolor='white',lw=.4);b.axvline(0,c=MUTED,ls='--',lw=.7);b.set(xlabel='Residual',ylabel='Observed samples',title='Error distribution')
            c.scatter(yp,np.abs(res),s=6,c='#4C9685',alpha=.6,lw=0);c.set(xlabel='Supplied prediction',ylabel='Absolute error',title='Error magnitude')
            e.scatter(observed,yp,s=6,c='#CA7354',alpha=.6,lw=0);lo=min(observed.min(),yp.min());hi=max(observed.max(),yp.max());e.plot([lo,hi],[lo,hi],c=MUTED,ls='--',lw=.7);e.set(xlabel=r.get('response_label','Observed '+r.get('unit','response')),ylabel='Supplied prediction',title='Observed versus predicted')
            for ax in aa.flat[:4]:ax.grid(axis='y',color=GRID,lw=.4)
            for ax in aa.flat[4:]:ax.remove()
            fig.suptitle('Regression · complementary diagnostics',x=.01,ha='left',fontweight='bold');return fig,{'predictions':r.get('evaluation_scope',r.get('scope',scope)),'refit':False,'diagnostics':['signed residual','residual histogram','absolute error','observed vs predicted'],'no_leverage_proxy':True,'nrows':nr,'ncols':nc}
        return scatter_panel({'x':r['y'] if kind=='reg_scatter' else r['prediction'],'y':r['prediction'] if kind=='reg_scatter' else r['residual'],'xlabel':r.get('response_label','Observed '+r.get('unit','response')) if kind=='reg_scatter' else 'Supplied prediction','ylabel':'Supplied prediction' if kind=='reg_scatter' else 'Residual','diagonal':kind=='reg_scatter','zero_y':kind=='reg_diagnostics','title':'Observed versus predicted' if kind=='reg_scatter' else 'Residual diagnostics · no leverage proxy'},o)
    if kind in ('k_selection','silhouette'):
        if kind=='k_selection':
            cs=d['clusters'];ks=[c['k'] for c in cs];fig,aa=axes(o,.42,ncols=2)
            for ax,values,label,color in [(aa[0],[c['inertia'] for c in cs],'Within-cluster squared distance','#3B6F91'),(aa[1],[np.mean(c['silhouette']) for c in cs],'Mean silhouette coefficient','#4C9685')]:
                if not np.isfinite(values).all():raise ValueError('Finite supplied clustering summaries required')
                ax.plot(ks,values,c=color,lw=1.3,marker='o',ms=4,mec='white',mew=.6);ax.set(xlabel='Number of clusters k',ylabel=label);ax.set_xticks(ks);ax.grid(axis='y',color=GRID,lw=.4)
            fig.suptitle(o.get('title','Elbow & silhouette diagnostics'),x=.01,ha='left',fontweight='bold');return fig,{'k':ks,'silhouette':'arithmetic mean of supplied per-observation coefficients','selection':'none; neither a selected k nor scientific cluster validity'}
        c=d['clusters'][0];s=np.array(c['silhouette']);lab=np.array(c['labels']);fig,ax=axes(o,.6);pos=0
        for i,k in enumerate(np.unique(lab)):
            v=np.sort(s[lab==k]);y=pos+np.arange(len(v));ax.fill_betweenx(y,0,v,color=PALETTES['muted'][i],alpha=.8,lw=0);pos+=len(v)+15
        ax.axvline(s.mean(),c=MUTED,ls='--',lw=.8);ax.set(xlabel='Silhouette coefficient',ylabel='Observations ordered within cluster',title='Descriptive k=2 silhouette');ax.set_yticks([]);return fig,{'k':2,'scientific_cluster_validity':'not established'}
    if kind=='radar':
        metrics=o.get('metrics',['ROC AUC','Average precision','Sensitivity','Specificity']);fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.63)),layout='constrained');ax=fig.add_subplot(111,projection='polar');theta=np.linspace(0,2*np.pi,len(metrics),endpoint=False)
        for name in names:
            m=models[name];cm=np.array(m['confusion']);v=[m['roc']['auc'],m['pr']['ap'],cm[1,1]/cm[1].sum(),cm[0,0]/cm[0].sum()];ax.plot(np.r_[theta,theta[0]],v+[v[0]],color=colors[name],lw=1.3,label=name);ax.fill(np.r_[theta,theta[0]],v+[v[0]],color=colors[name],alpha=.06)
        ax.set_xticks(theta,metrics);ax.set_ylim(0,1);ax.set_yticks([.25,.5,.75,1]);ax.tick_params(labelsize=7.5);ax.grid(color=GRID,lw=.6);ax.spines['polar'].set_visible(False);ax.legend(loc='upper left',bbox_to_anchor=(1.1,1));ax.set_title('Supplied performance profile',pad=20,loc='left');return fig,{'axes':'all [0,1], higher better','zero_baseline':True,'predictions':scope,'caution':'polygon area is not a scalar performance score'}
    if kind=='pdp_ice':
        p=d['pdp'];fig,ax=axes(o,.62)
        for v in p['individual']:ax.plot(p['x'],v,c='#A1B6C3',lw=.4,alpha=.25)
        ax.plot(p['x'],p['mean'],c='#C56D56',lw=1.8,label='Partial dependence');ax.set(xlabel=p['feature'],ylabel='Predicted malignant probability',title='Partial dependence & 50 supplied ICE curves');ax.legend();return fig,{'fit_in_renderer':False,'causality':'not established'}
    if kind=='gain_lift':
        fig,ax=axes(o,.65);y=np.asarray(d['y'])
        for n in names:
            pr=np.asarray(models[n]['probability']);order=np.argsort(-pr,kind='stable');x=np.arange(1,len(y)+1)/len(y);gain=np.cumsum(y[order])/sum(y);ax.plot(x,gain,label=n,color=colors[n],lw=1.5)
        ax.plot([0,1],[0,1],c=MUTED,ls='--',lw=.7);ax.set(xlabel='Fraction screened',ylabel='Fraction of positives recovered',title='Supplied cumulative gain');ax.legend();return fig,{'predictions':scope,'ties':'stable source order; descriptive only'}
    raise NotImplementedError('No accepted ML renderer for '+kind)

__all__=['line_panel','scatter_panel','forest_panel','bars_panel','gsea_panel','proportion_panel','spectra_panel','ml_panel']
