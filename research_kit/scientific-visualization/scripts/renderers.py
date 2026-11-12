"""Scientific visualization v2. Draw frozen result channels; do not fit models.

Public renderer functions accept documented dictionaries/DataFrames. Missing
scientific channels fail explicitly, rather than generating demo quantities.
"""
from pathlib import Path
import json, math, textwrap
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch,Rectangle,PathPatch
from matplotlib.path import Path as MPath
from scipy.cluster.hierarchy import linkage, dendrogram, leaves_list, is_valid_linkage
from scipy.spatial.distance import pdist
from design_system import *

def _axes(width='double',aspect=.68):
    fig,ax=plt.subplots(figsize=journal_size(width,aspect),layout='constrained')
    return fig,ax

def _matrix(d,key='matrix'):
    m=d.get(key,d)
    if isinstance(m,dict) and 'values' in m: return matrix_input(m['values'],m.get('rows'),m.get('columns'))
    return matrix_input(m)

def _colors(groups,options):
    theme=options.setdefault('theme',{'palette':options.get('palette','muted')})
    return identity_colors(theme,groups)

def _scatter(ax,x,y,group,order,colors,**kw):
    group=np.asarray(group)
    for g in order:
        sel=group==g
        opts={'edgecolors':'white','linewidths':.3};opts.update(kw)
        ax.scatter(np.asarray(x)[sel],np.asarray(y)[sel],color=colors[g],label=str(g),**opts)

def _legend(ax,**kw):
    return ax.legend(loc='upper left',bbox_to_anchor=(1.01,1),borderaxespad=0,**kw)

def draw_pca(d,o,kind='pca_samples'):
    pcs=np.asarray(d.get('pca',d.get('pcs')),float)
    if pcs.ndim!=2 or pcs.shape[1]<2 or not len(pcs) or not np.isfinite(pcs).all(): raise ValueError('Nonempty finite stored PC coordinates with at least two components required')
    groups=np.array(d['groups'],str)
    if len(groups)!=len(pcs): raise ValueError('PCA groups do not align')
    order=d.get('group_order',list(dict.fromkeys(groups))); colors=_colors(order,o)
    if len(set(order))!=len(order) or set(order)!=set(groups):raise ValueError('PCA group_order must preserve every observed condition exactly once')
    if 'sample_ids' in d and (len(d['sample_ids'])!=len(pcs) or len(set(d['sample_ids']))!=len(pcs)):raise ValueError('Unique literal sample identities must align with every PCA row')
    if d.get('pca_variance') is not None:
        variance=np.asarray(d['pca_variance'],float)
        if variance.ndim!=1 or len(variance)<2 or not np.isfinite(variance).all() or ((variance<0)|(variance>1)).any() or variance.sum()>1+1e-6:raise ValueError('Explained variance must use supplied fractions, not percentages or invented values')
    records=[]; joint=o.get('variant','joint')=='joint'
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.66)),layout='constrained')
    gs=fig.add_gridspec(2,3,height_ratios=[.25,1],width_ratios=[1,.24,.30],hspace=.04,wspace=.06)
    ax=fig.add_subplot(gs[1,0]); top=fig.add_subplot(gs[0,0],sharex=ax); side=fig.add_subplot(gs[1,1],sharey=ax); guide=fig.add_subplot(gs[:,2]);guide.axis('off')
    _scatter(ax,pcs[:,0],pcs[:,1],groups,order,colors,s=20 if len(pcs)<100 else 5,alpha=.85,zorder=3)
    small=all(sum(groups==g)<12 for g in order)
    global_xbins=np.linspace(pcs[:,0].min(),pcs[:,0].max(),14)
    global_ybins=np.linspace(pcs[:,1].min(),pcs[:,1].max(),14)
    for idx,g in enumerate(order):
        sub=pcs[groups==g]
        add_ellipse(ax,sub[:,0],sub[:,1],colors[g],records=records,label=g)
        if joint:
            if small:
                q=np.quantile(sub[:,0],[.25,.5,.75]);top.plot(q[[0,2]],[idx]*2,color=colors[g],lw=2.5,solid_capstyle='round');top.scatter(sub[:,0],np.full(len(sub),idx),s=7,c=colors[g],edgecolors='white',lw=.3,zorder=3);top.scatter([q[1]],[idx],s=11,c='white',edgecolors=colors[g],lw=.7,zorder=4)
                q=np.quantile(sub[:,1],[.25,.5,.75]);side.plot([idx]*2,q[[0,2]],color=colors[g],lw=2.5,solid_capstyle='round');side.scatter(np.full(len(sub),idx),sub[:,1],s=7,c=colors[g],edgecolors='white',lw=.3,zorder=3);side.scatter([idx],[q[1]],s=11,c='white',edgecolors=colors[g],lw=.7,zorder=4)
            else:
                top.hist(sub[:,0],bins=global_xbins,histtype='step',color=colors[g],lw=1.1)
                side.hist(sub[:,1],bins=global_ybins,histtype='step',orientation='horizontal',color=colors[g],lw=1.1)
    var=d.get('pca_variance'); lab=lambda i:f'PC{i+1}'+(f' ({100*var[i]:.1f}%)' if var is not None else '')
    ax.set(xlabel=lab(0),ylabel=lab(1)); ax.axhline(0,color=GRID,lw=.6,zorder=0);ax.axvline(0,color=GRID,lw=.6,zorder=0)
    top.axis('off');side.axis('off')
    if small: top.set_ylim(-.7,len(order)-.3);side.set_xlim(-.7,len(order)-.3)
    handles=[Line2D([],[],marker='o',ls='',color=colors[g],markersize=5,label=wrap_label(g,17)) for g in order]
    outlier_table=[]
    if kind=='pca_outlier':
        if 'outlier_scores' not in d:raise ValueError('QC outlier view requires frozen within-group squared Mahalanobis scores; no new outlier method is fitted by the renderer')
        if len(d['outlier_scores'])!=len(pcs) or 'sample_ids' not in d or any(s is not None and (not np.isfinite(s) or s<0) for s in d['outlier_scores']):raise ValueError('QC scores and literal sample IDs must cover every PCA row; no zip truncation or invalid D-squared')
        threshold=float(o.get('outlier_threshold',d.get('outlier_rule',{}).get('threshold',5.99)))
        if not np.isfinite(threshold) or threshold<=0:raise ValueError('Positive explicit outlier threshold required')
        for i,(score,name) in enumerate(zip(d['outlier_scores'],d['sample_ids'])):
            flag=score is not None and score>threshold;outlier_table.append({'sample':name,'group':str(groups[i]),'score':score,'reference':threshold,'flag':flag})
            if flag:
                ax.scatter(*pcs[i,:2],s=40,facecolors='none',edgecolors='#AC553F',linewidths=1,zorder=4);ax.annotate(name,pcs[i,:2],xytext=(4,4),textcoords='offset points',fontsize=6.3)
        handles.append(Line2D([],[],marker='o',ls='',markerfacecolor='none',markeredgecolor='#AC553F',label=f'D² > {threshold:g}\n(configurable)'))
    guide.legend(handles=handles,loc='upper left',title='Condition' if len(pcs)<100 else 'Cell identity',labelspacing=.9)
    if len(pcs)<100 and o.get('sample_labels',False):
        for x,y,s in zip(pcs[:,0],pcs[:,1],d['sample_ids']): ax.annotate(s,(x,y),xytext=(3,3),textcoords='offset points',fontsize=6)
    fig.suptitle(o.get('title','Sample architecture'),x=.01,ha='left',fontsize=11,fontweight='bold')
    return fig,{'ellipse_records':records,'coordinate_source':'supplied','variant':'joint_marginals' if joint else 'ellipse','outlier_table':outlier_table}

def draw_volcano(d,o):
    de=pd.DataFrame(d['de']); required=['gene','log2FC','padj']
    if not all(k in de for k in required): raise ValueError('DE requires gene, log2FC, padj')
    if not de.padj.between(0,1).all(): raise ValueError('Adjusted p outside [0,1]')
    fc=float(o.get('log2fc',d.get('thresholds',{}).get('log2fc',1)))
    q=float(o.get('fdr',d.get('thresholds',{}).get('fdr',.05)))
    if not 0<q<1 or fc<0: raise ValueError('Invalid thresholds')
    x=de.log2FC.to_numpy();qvals=de.padj.to_numpy();zero=qvals==0
    finite_y=-np.log10(qvals[~zero]);finite_max=float(finite_y.max()) if len(finite_y) else -np.log10(q)
    cap=float(o.get('reported_zero_height',finite_max+max(1.,finite_max*.08))) if zero.any() else None
    y=np.empty(len(qvals));y[~zero]=finite_y
    if zero.any():y[zero]=cap
    groups=np.where((de.padj<q)&(x>fc),'Up',np.where((de.padj<q)&(x<-fc),'Down','Other'))
    colors={'Up':'#C56D56','Down':'#39789E','Other':'#C5CFD5'}
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.70)),layout='constrained')
    gs=fig.add_gridspec(2,3,height_ratios=[.22,1],width_ratios=[1,.24,.28],hspace=.03,wspace=.03)
    ax=fig.add_subplot(gs[1,0]); top=fig.add_subplot(gs[0,0],sharex=ax);side=fig.add_subplot(gs[1,1],sharey=ax);guide=fig.add_subplot(gs[:,2]);guide.axis('off')
    for g in ['Other','Down','Up']:
        m=(groups==g)&~zero; ax.scatter(x[m],y[m],s=3 if g=='Other' else 7,c=colors[g],alpha=.32 if g=='Other' else .8,linewidths=0,rasterized=False,zorder=1 if g=='Other' else 3)
        m=(groups==g)&zero
        if m.any():ax.scatter(x[m],y[m],s=19,c=colors[g],marker='^',edgecolors='white',linewidths=.4,zorder=4)
    edges=np.linspace(x.min(),x.max(),50)
    top.hist([x[groups==g] for g in ['Other','Down','Up']],bins=edges,stacked=True,color=[colors[g] for g in ['Other','Down','Up']],linewidth=0,alpha=.82)
    yedges=np.linspace(0,max(y.max(),1),40)
    side.hist([y[groups==g] for g in ['Other','Down','Up']],bins=yedges,stacked=True,orientation='horizontal',color=[colors[g] for g in ['Other','Down','Up']],linewidth=0,alpha=.82)
    ax.axvline(-fc,color=MUTED,ls='--',lw=.7);ax.axvline(fc,color=MUTED,ls='--',lw=.7);ax.axhline(-np.log10(q),color=MUTED,ls='--',lw=.7)
    n=int(o.get('labels_each',3));annotations=[]
    if n<0 or n>5:raise ValueError('Use at most five labels per direction per panel; paginate additional requested labels')
    for g,ha,sgn in [('Down','right',-1),('Up','left',1)]:
        indices=np.flatnonzero(groups==g);indices=indices[np.argsort(de.padj.to_numpy()[indices],kind='stable')][:n]
        # Separate text rails avoid the ceiling collision of labels attached to
        # several reported-zero p-values at the same display height.
        indices=indices[np.argsort(y[indices],kind='stable')[::-1]]
        for j,i in enumerate(indices):
            rail_x=.24 if sgn<0 else .80
            text=ax.annotate(wrap_label(de.gene.iloc[i],22),(x[i],y[i]),xytext=(rail_x,.96-.09*j),textcoords='axes fraction',ha='right' if sgn<0 else 'left',va='top',fontsize=6.3,color=INK,arrowprops={'arrowstyle':'-','lw':.4,'color':MUTED})
            annotations.append(text)
    effect_unit=d.get('effect_unit','log2 fold change')
    ax.set(xlabel=effect_unit,ylabel='−log10 adjusted P');ax.margins(x=.10)
    ax.set_ylim(0,(cap if zero.any() else y.max())*1.25)
    top.axis('off');side.axis('off')
    guide.legend(handles=[Patch(facecolor=colors[g],label=f'{g} ({sum(groups==g):,})') for g in ['Up','Down','Other']],loc='upper left',title=d.get('classification_label','Expression'))
    effect_symbol='log2FC' if effect_unit=='log2 fold change' else 'effect'
    guide.text(0,.48,f'FDR < {q:g}\n|{effect_symbol}| > {fc:g}',fontsize=7.5,va='top',color=MUTED)
    if zero.any():guide.text(0,.29,f'▲ Reported adjusted P = 0\n(n = {sum(zero)})',fontsize=7.3,va='top',color=MUTED,wrap=True)
    fig.suptitle(o.get('title','Differential expression'),x=.01,ha='left',fontsize=11,fontweight='bold')
    return fig,{'thresholds':{'fdr':q,'log2fc':fc},'counts':{g:int(sum(groups==g)) for g in colors},'contrast':d.get('contrast'),'variant':'stacked_marginals','reported_zero_count':int(sum(zero)),'reported_zero_display_height':cap,'zero_representation':'triangle at declared display height, never a measured finite -logP'}

def draw_heatmap(d,o,kind='heatmap'):
    m=_matrix(d,'heatmap' if 'heatmap' in d else 'matrix')
    a=m.to_numpy(); nr,nc=a.shape
    groups=d.get('groups'); cols=list(map(str,m.columns));rows=list(map(str,m.index))
    if groups is not None and len(groups)!=nc: raise ValueError('Heatmap annotation length mismatch')
    if groups is not None:
        group_order=d.get('group_order',list(dict.fromkeys(groups)))
        if len(set(group_order))!=len(group_order) or set(group_order)!=set(groups):raise ValueError('Heatmap group_order must cover every actual condition exactly once; no dropped columns')
    if np.isinf(a).any(): raise ValueError('Infinite heatmap values')
    # Missing values are visible; clustering requires complete values or supplied linkage.
    cluster=o.get('cluster',True); mode=o.get('cluster_mode','free')
    method=o.get('linkage','average'); rd=o.get('row_distance','euclidean');cd=o.get('column_distance','euclidean')
    zr=zc=None; block_trees=[];ri=np.arange(nr);ci=np.arange(nc)
    source_hierarchy=cluster and ('row_linkage' in d or 'column_linkage' in d)
    if source_hierarchy:
        if mode!='free':raise ValueError('A supplied source hierarchy cannot also request newly sorted condition blocks')
        for key,n in [('row_linkage',nr),('column_linkage',nc)]:
            if key not in d:continue
            if d.get(key+'_ids')!=(rows if key=='row_linkage' else cols):raise ValueError('Source linkage needs the exact unchanged literal axis identities: '+key+'_ids')
            z=np.asarray(d[key],float)
            if n<2 or z.shape!=(n-1,4) or not np.isfinite(z).all() or not is_valid_linkage(z):raise ValueError('Invalid source linkage for the unchanged literal matrix axis: '+key)
            if key=='row_linkage':zr=z;ri=leaves_list(z)
            else:zc=z;ci=leaves_list(z)
    elif cluster:
        if not np.isfinite(a).all(): raise ValueError('Clustering with missing values requires upstream finite distances/order; no silent imputation')
        if nr>1:
            zr=linkage(pdist(a,rd),method=method);ri=leaves_list(zr)
        if nc>1 and mode=='free': zc=linkage(pdist(a.T,cd),method=method);ci=leaves_list(zc)
        elif nc>1 and mode=='condition_blocks':
            if groups is None: raise ValueError('Condition-block mode requires aligned groups')
            gs=np.array(groups);ci=[]
            for g in d.get('group_order',list(dict.fromkeys(groups))):
                ids=np.flatnonzero(gs==g)
                if len(ids)>1:
                    zblock=linkage(pdist(a[:,ids].T,cd),method=method)
                    block_trees.append((len(ci),zblock))
                    ci.extend(ids[leaves_list(zblock)])
                else:ci.extend(ids)
            ci=np.asarray(ci,dtype=int)
        elif mode not in ('free','condition_blocks'): raise ValueError('Unknown cluster mode')
    mat=a[np.ix_(ri,ci)]
    limit=o.get('display_limit');cmap=o.get('cmap','blue-coral'); cmap=LinearSegmentedColormap.from_list(cmap,PALETTES.get(cmap,PALETTES['blue-coral']))
    vmin,vmax=o.get('vmin'),o.get('vmax')
    if limit is not None: vmin,vmax=-abs(limit),abs(limit)
    # Enlarge height or paginate upstream; never shrink fonts to fit dense rows.
    compact=nr<=8 and nc<=8
    numeric_symmetric=o.get('dense_numeric_axes',False) and nr==nc and rows==cols
    aspect=o.get('aspect',.98 if numeric_symmetric else max(.32,.28+nr*.035) if nr<=8 else max(.65,min(1.8,.22+nr*.022)))
    width_name=o.get('width','onehalf' if compact else 'double');panel_width_mm=journal_size(width_name,1)[0]*25.4
    guide_below=panel_width_mm<=120 and (groups is not None or np.isnan(a).any())
    fig=plt.figure(figsize=journal_size(width_name,aspect),layout='constrained')
    heights=[.15 if zc is not None or block_trees else .002,.025 if groups is not None else .002,1]
    if guide_below:
        guide_rows=math.ceil(((len(set(groups)) if groups is not None else 0)+int(np.isnan(a).any()))/2)
        heights+=[(5+4*guide_rows)/max(25,nr*3),.028]
    else:heights+=[.028]
    gs=fig.add_gridspec(len(heights),4,height_ratios=heights,width_ratios=[.13 if zr is not None else .002,1,.025,.002 if guide_below else .30 if groups is not None else .002],hspace=.025,wspace=.02)
    tree=fig.add_subplot(gs[0,1]); rtree=fig.add_subplot(gs[2,0]);strip=fig.add_subplot(gs[1,1]); ax=fig.add_subplot(gs[2,1]); cbax=fig.add_subplot(gs[4 if guide_below else 3,1]);guide=fig.add_subplot(gs[3,1] if guide_below else gs[1:3,3]);guide.axis('off');guide_handles=[]
    if zc is not None: dendrogram(zc,ax=tree,no_labels=True,color_threshold=0,above_threshold_color=MUTED)
    elif block_trees:
        for offset,zblock in block_trees:
            branch=dendrogram(zblock,no_plot=True)
            for xx,yy in zip(branch['icoord'],branch['dcoord']):tree.plot(np.array(xx)/10-.5+offset,yy,color=MUTED,lw=.8)
        tree.set_xlim(-.5,nc-.5);tree.set_ylim(bottom=0)
    if zr is not None: dendrogram(zr,ax=rtree,orientation='left',no_labels=True,color_threshold=0,above_threshold_color=MUTED)
    tree.axis('off');rtree.axis('off')
    if groups is not None:
        colors=_colors(d.get('group_order',list(dict.fromkeys(groups))),o); cc=[colors[str(groups[i])] for i in ci]
        strip.imshow(np.array([mpl.colors.to_rgb(c) for c in cc])[None,:,:],aspect='auto');strip.set_xlim(-.5,nc-.5)
        guide_handles.extend(Patch(color=colors[g],label=wrap_label(g,14 if guide_below else 18)) for g in colors)
    if np.isnan(a).any():
        guide_handles.append(Patch(color='#E3DBD2',label=wrap_label(o.get('missing_label','Missing value'),20)))
    if guide_handles:guide.legend(handles=guide_handles,loc='center' if guide_below else 'upper left',ncol=min(2,len(guide_handles)) if guide_below else 1,title='Condition' if groups is not None and not np.isnan(a).any() else 'Key',fontsize=6.8,columnspacing=1.0,handlelength=1.2)
    strip.axis('off')
    cm=cmap.copy();cm.set_bad('#E3DBD2')
    display_rows=d.get('display_rows',{});display_columns=d.get('display_columns',{})
    if set(display_rows)-set(rows) or set(display_columns)-set(cols):raise ValueError('Display label map must use exact source identities')
    row_text=[wrap_label(display_rows.get(rows[i],rows[i]),int(o.get('row_wrap',30))) for i in ri]
    row_heights=np.array([1.+.78*(s.count('\n')) for s in row_text])
    yedges=np.r_[0,np.cumsum(row_heights)];ycenters=(yedges[:-1]+yedges[1:])/2
    im=ax.pcolormesh(np.arange(nc+1)-.5,yedges,np.ma.masked_invalid(mat),cmap=cm,vmin=vmin,vmax=vmax,shading='flat',edgecolors='none',rasterized=False)
    ax.set_ylim(yedges[-1],0)
    if zr is not None:
        old=5+10*np.arange(nr)
        for collection in rtree.collections:
            segments=collection.get_segments()
            for segment in segments:segment[:,1]=np.interp(segment[:,1],old,ycenters)
            collection.set_segments(segments)
        rtree.set_ylim(yedges[-1],0)
    rotation=int(o.get('label_rotation',0 if nc<=4 else 90 if nc>12 or panel_width_mm<=120 or max(map(len,cols))>15 else 45))
    def heat_label(s):
        s=display_columns.get(s,s)
        if rotation==90:return s
        return s.rsplit('_',1)[0]+'_\n'+s.rsplit('_',1)[1] if '_LL' in s else wrap_label(s,18)
    col_step=max(1,int(o.get('column_label_step',math.ceil(nc/32))))
    ax.set_xticks(np.arange(0,nc,col_step),[heat_label(cols[ci[i]]) for i in range(0,nc,col_step)],rotation=rotation,ha='center' if rotation==90 else 'right',fontsize=6.6)
    # Explicit pagination is required for huge row counts; 80-row upper readable view.
    if nr>80 and not o.get('dense_numeric_axes'): raise ValueError('More than 80 named rows: paginate explicitly; numerical fields may request dense_numeric_axes')
    row_step=max(1,math.ceil(nr/20)) if o.get('dense_numeric_axes') else int(o.get('row_label_step',1))
    ax.set_yticks(ycenters[::row_step],row_text[::row_step],fontsize=6.6)
    ax.tick_params(length=0,pad=2)
    ax.spines[:].set_visible(False)
    cb=fig.colorbar(im,cax=cbax,orientation='horizontal');cb.outline.set_visible(False);cb.set_label(o.get('color_label','Row Z-score'))
    if 'color_ticks' in o:cb.set_ticks(o['color_ticks'],labels=o.get('color_tick_labels'))
    if o.get('annotate',False):
        for i in range(nr):
            for j in range(nc):
                if np.isfinite(mat[i,j]):
                    rgb=im.cmap(im.norm(mat[i,j]))[:3];lum=np.dot(rgb,[.2126,.7152,.0722]);ax.text(j,ycenters[i],format(mat[i,j],o.get('number_format','.2f')),ha='center',va='center',fontsize=6.5,color='white' if lum<.5 else INK)
    fig.suptitle(o.get('title','Expression architecture'),x=.01,ha='left',fontsize=11,fontweight='bold')
    # Constrained layout spends space on titles, long column labels and trees.
    # Reserve physical row height after that allocation rather than assuming a
    # fixed aspect ratio can accommodate every matrix at every column width.
    fig.canvas.draw();required_mm=float(row_heights.sum())*6.6/72*25.4*1.30
    actual_mm=ax.get_position().height*fig.get_figheight()*25.4
    expanded=False
    if actual_mm<required_mm and not o.get('dense_numeric_axes'):
        # Tree heights scale with the canvas; titles and tick labels consume
        # fixed millimetres. Dividing by the current tiny axes fraction would
        # vastly overestimate growth on a narrow panel with long column labels.
        new_height=fig.get_figheight()+(required_mm-actual_mm)*1.25/25.4
        if new_height*25.4>500:raise ValueError('Named heatmap exceeds readable page height; paginate rows')
        fig.set_figheight(new_height);fig.canvas.draw();expanded=True
        for _ in range(3):
            actual_mm=ax.get_position().height*fig.get_figheight()*25.4
            if actual_mm>=required_mm*.98:break
            fig.set_figheight(fig.get_figheight()+(required_mm-actual_mm)*1.25/25.4);fig.canvas.draw()
    return fig,{'row_order':[rows[i] for i in ri],'column_order':[cols[i] for i in ci],'display_rows':display_rows,'display_columns':display_columns,'height_expanded_for_labels':expanded,'guide_location':'below' if guide_below else 'right','label_rotation':rotation,'linkage':d.get('hierarchy_method','upstream supplied') if source_hierarchy else method,'row_distance':d.get('hierarchy_row_distance','upstream supplied') if source_hierarchy else rd,'column_distance':d.get('hierarchy_column_distance','upstream supplied') if source_hierarchy else cd,'hierarchy_source':'supplied frozen linkage' if source_hierarchy else 'display clustering on unclipped supplied matrix' if cluster else 'source order; no clustering','cluster_mode':mode,'cluster_on_unclipped':True,'vmin':vmin,'vmax':vmax,'row_display_heights':row_heights.tolist(),'source_values_sha256':__import__('hashlib').sha256(a.tobytes()).hexdigest()}

def draw_dot(d,o):
    mean=np.asarray(d['dot_mean'],float); frac=np.asarray(d['dot_fraction'],float)
    if mean.shape!=frac.shape or not np.isfinite(mean).all() or not np.isfinite(frac).all() or (frac<0).any() or (frac>1).any(): raise ValueError('Aligned finite mean/fraction matrices (fraction in [0,1]) required')
    rows=d['group_order']; genes=d['markers']
    if mean.shape!=(len(rows),len(genes)): raise ValueError('Marker/group axis mismatch')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',max(.55,.065*len(rows)))),layout='constrained')
    gs=fig.add_gridspec(2,3,height_ratios=[1,.035],width_ratios=[.23,1,.26],wspace=.04)
    ax=fig.add_subplot(gs[0,1]); count=fig.add_subplot(gs[0,0],sharey=ax);guide=fig.add_subplot(gs[:,2]);guide.axis('off');cbax=fig.add_subplot(gs[1,1])
    x,y=np.meshgrid(np.arange(len(genes)),np.arange(len(rows)))
    sc=ax.scatter(x.ravel(),y.ravel(),s=frac.ravel()*o.get('max_dot_area',90),c=mean.ravel(),cmap=LinearSegmentedColormap.from_list('teal-depth',PALETTES['teal-depth']),vmin=0,vmax=float(mean.max()),edgecolors=INK,linewidths=.22)
    rotation=o.get('label_rotation',60)
    ax.set_xticks(np.arange(len(genes)),genes,rotation=rotation,ha='center' if rotation==90 else 'right',fontsize=6.8);ax.set_yticks(np.arange(len(rows)),[],fontsize=7)
    ax.set(xlim=(-.65,len(genes)-.35),ylim=(len(rows)-.5,-.5));ax.spines[:].set_visible(False)
    ax.grid(axis='both',color=GRID,lw=.4);ax.set_axisbelow(True);ax.tick_params(length=0)
    colors=_colors(rows,o);counts=d.get('cluster_counts',[1]*len(rows))
    count.barh(np.arange(len(rows)),counts,color=[colors[g] for g in rows],height=.54)
    count.set_yticks(np.arange(len(rows)),[wrap_label(g,19) for g in rows]);count.set_xlabel('Cells');count.invert_xaxis();count.spines[:].set_visible(False);count.tick_params(axis='y',length=0)
    ax.tick_params(axis='y',labelleft=False)
    guide.legend(handles=[plt.scatter([],[],s=v*o.get('max_dot_area',90),facecolor='#A7C6BA',edgecolor=INK,linewidth=.3,label=f'{v:.0%}') for v in [.1,.25,.5,1]],title='Detected',loc='upper left',labelspacing=1.3,scatterpoints=1)
    cb=fig.colorbar(sc,cax=cbax,orientation='horizontal');cb.outline.set_visible(False);cb.set_label('Mean log1p expression')
    fig.suptitle(o.get('title','Cell identity × marker evidence'),x=.01,ha='left',fontsize=11,fontweight='bold')
    return fig,{'size_semantics':'point area = detected fraction','color_semantics':'mean supplied log1p expression','representation':d.get('representation')}

def draw_embedding(d,o,kind='umap_clusters'):
    if kind != 'feature_grid':
        from embedding_views import embedding_atlas
        return embedding_atlas(d,o,kind)
    xy=np.asarray(d.get('embedding'),float); groups=np.asarray(d['groups']);order=d['group_order'];colors=_colors(order,o)
    if xy.shape!=(len(groups),2): raise ValueError('Aligned two-dimensional supplied embedding required')
    if kind in ('feature_grid','dim_facet','dim_highlight','onevsrest_grid'):
        features=o.get('features',d.get('markers',[])[:6]) if kind=='feature_grid' else order
        if not features: raise ValueError('No facets selected')
        nr,nc=choose_grid(len(features),o.get('ncols'),o.get('nrows'))
        fig,axes=plt.subplots(nr,nc,figsize=journal_size(o.get('width','double'),o.get('aspect',.42*nr)),squeeze=False,layout='constrained',sharex=True,sharey=True)
        v=np.asarray(d.get('expression',[]));vmax=np.nanmax(v) if v.size else 1
        for ax,f in zip(axes.flat,features):
            ax.scatter(xy[:,0],xy[:,1],s=1.3,c='#DDE4E8',lw=0,zorder=0,rasterized=False)
            if kind=='feature_grid':
                j=d['markers'].index(f);orderpt=np.argsort(v[:,j],kind='stable')
                sc=ax.scatter(xy[orderpt,0],xy[orderpt,1],s=o.get('point_size',3.2),c=v[orderpt,j],cmap=LinearSegmentedColormap.from_list('expr',PALETTES['teal-depth']),norm=mpl.colors.PowerNorm(o.get('color_gamma',.5),vmin=0,vmax=vmax),lw=0)
            else:
                m=groups==f;ax.scatter(xy[m,0],xy[m,1],s=2.5,c=colors[f],lw=0)
            ax.set_title(wrap_label(f,23),fontsize=8);ax.set_aspect('equal',adjustable='box');ax.set_xticks([]);ax.set_yticks([]);ax.spines[:].set_visible(False)
        for ax in axes.flat[len(features):]:ax.remove()
        if kind=='feature_grid': fig.colorbar(sc,ax=list(axes.flat)[:len(features)],shrink=.5,label='Log1p expression')
    return fig,{'embedding_refit':False,'nrows':nr,'ncols':nc,'shared_color_scale':kind=='feature_grid','vmax':vmax,'color_gamma':o.get('color_gamma',.5),'vmin':0}
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.64)),layout='constrained')
    gs=fig.add_gridspec(1,2,width_ratios=[1,.31]);ax=fig.add_subplot(gs[0,0]);guide=fig.add_subplot(gs[0,1]);guide.axis('off')
    _scatter(ax,xy[:,0],xy[:,1],groups,order,colors,s=o.get('point_size',3),alpha=.7,linewidths=0)
    for g in order:
        sub=xy[groups==g]; pos=np.median(sub,axis=0)
        ax.text(*pos,wrap_label(g,16),ha='center',va='center',fontsize=7,bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1.2})
    ax.set(xlabel='UMAP 1',ylabel='UMAP 2');ax.set_aspect('equal',adjustable='box');ax.set_xticks([]);ax.set_yticks([]);ax.spines[:].set_visible(False)
    guide.legend(handles=[Line2D([],[],marker='o',ls='',color=colors[g],label=wrap_label(g,19)) for g in order],loc='upper left',title='Cell identity',labelspacing=.8)
    fig.suptitle(o.get('title','Cell-state landscape'),x=.01,ha='left',fontsize=11,fontweight='bold')
    return fig,{'embedding_refit':False,'points':len(xy)}

def draw_raincloud(d,o):
    vals=d['values'];groups=d['labels'];colors=_colors(groups,o);densities=d.get('densities')
    if len(vals)!=len(groups): raise ValueError('Group axes differ')
    fig,ax=_axes(o.get('width','onehalf' if len(groups)<=3 else 'double'),o.get('aspect',max(.28,.080*len(groups)+.12)))
    for i,(g,raw) in enumerate(zip(groups,vals)):
        x=np.asarray(raw,float);x=x[np.isfinite(x)]
        if len(x)==0: raise ValueError('Empty raincloud group: '+g)
        # Each raw observation remains visible. Deterministic display-only spread.
        offsets=((np.arange(len(x))*.61803398875)%1-.5)*.14
        ax.scatter(x,np.full(len(x),i)+.20+offsets,c=colors[g],s=5,alpha=.5,lw=.2,edgecolors=INK,zorder=3)
        q1,med,q3=np.quantile(x,[.25,.5,.75]);lo=max(x.min(),q1-1.5*(q3-q1));hi=min(x.max(),q3+1.5*(q3-q1))
        ax.plot([lo,hi],[i,i],c=INK,lw=.7);ax.plot([q1,q3],[i,i],c=colors[g],lw=5,solid_capstyle='butt');ax.scatter([med],[i],marker='|',s=35,c='white',zorder=4)
        den=densities[i] if densities else None
        if den:
            xx=np.asarray(den['x']);yy=np.asarray(den['y']);yy=yy/max(yy.max(),1e-12)*.35
            ax.fill_between(xx,i-.08,i-.08-yy,color=colors[g],alpha=.45,lw=0);ax.plot(xx,i-.08-yy,c=colors[g],lw=.8)
    ax.set_yticks(range(len(groups)),[wrap_label(g,25) for g in groups]);ax.set_xlabel(d.get('unit','Supplied expression'));ax.set_ylim(len(groups)-.5,-.55);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',color=GRID,lw=.4)
    ax.set_title(o.get('title','Distribution, observations & robust summaries'),loc='left',pad=12)
    return fig,{'density_refit':False,'n':[len(v) for v in vals],'summary':'median, IQR, 1.5 IQR whisker rule; not CI'}

def resolve_id(identifier,source=None):
    if source is not None:
        cat=json.loads((Path(__file__).resolve().parents[1]/'assets/figure_catalog.json').read_text(encoding='utf8'))
        key=source+':'+identifier
        if key not in cat['compatibility']: raise KeyError(key)
        return cat['compatibility'][key]
    return identifier

def render_template(identifier,data,*,source=None,outdir=None,formats=('png','svg'),overwrite=False,**options):
    identifier=resolve_id(identifier,source)
    if identifier in ('umap-dashboard','condition-toggle','pose-3d-html','trajectory-gif'):
        if outdir is None:raise ValueError('Interactive output requires outdir')
        stem=options.pop('stem','fig_'+identifier.replace('-','_'))
        if identifier=='trajectory-gif':
            from animate import trajectory_gif
            path,meta=trajectory_gif(data,outdir,stem,overwrite,**options)
        else:
            from interactive import embedding_view,molecular_view
            path=molecular_view(data,outdir,stem,overwrite) if identifier=='pose-3d-html' else embedding_view(data,outdir,stem,overwrite,theme=options.get('theme'))
            meta={'outputs':[str(path)],'status':'RENDERED_UNREVIEWED'}
        meta['template_id']=identifier
        return None,meta
    use_style(options.get('style','journal'))
    catalog=json.loads((Path(__file__).resolve().parents[1]/'assets/figure_catalog.json').read_text(encoding='utf8'))
    entry=next((x for x in catalog['figures'] if x['id']==identifier),None)
    if entry is None:raise KeyError(identifier)
    options.setdefault('title',data.get('title',entry['name']) if isinstance(data,dict) else entry['name'])
    from renderers_extra import line_panel,scatter_panel,forest_panel,bars_panel,gsea_panel,proportion_panel,spectra_panel,ml_panel,effect_matrix_panel,marker_strip_panel
    from renderers_domains import qc_panel,small_cell_panel,surface_panel,orbital_panel,trajectory_panel,phase_panel,oncoprint_panel
    from renderers_relations import enrichment_panel,chord_panel,alluvial_panel,molecule_panel,poses_panel,energy_panel
    from renderers_layouts import paired_panel,upset_panel,km_panel,scatter3d_panel,multi_volcano_panel,funnel_panel
    from renderers_remaining import bubble_panel,genescore_panel,rank_matrix_panel,trajectory_pca_panel,stages_panel,barcode_panel
    ml_ids=('roc_multi','pr_curve','confusion','calibration','gain_lift','feat_importance','shap_summary','shap_dependence','shap_interaction','learning_curve','grid_heatmap','reg_scatter','reg_diagnostics','decision_boundary','silhouette','k_selection','cv_box','training_dashboard','radar','parallel_coords','pdp_ice')
    if identifier in ('shap_summary','shap_dependence','feat_importance') and isinstance(data,dict) and ('explanation' in data or identifier=='shap_summary' and 'class_contributions' in data):
        from shap_channels import prepare_shap_display
        display,channel_meta=prepare_shap_display(data)
        if identifier=='shap_summary' and options.get('variant','reference_classic')=='reference_classic':
            from shap_classic import classic_contribution_page
            fig,meta=classic_contribution_page(display,options)
        else:
            fig,meta=ml_panel(display,options,identifier)
        meta.update(channel_meta)
        if outdir is not None:
            options['_shap_display_summary']={'features':display['features'],'mean_abs':channel_meta['full_feature_magnitude'],'shares':channel_meta['full_feature_shares']}
    elif identifier=='ifp_barcode':fig,meta=barcode_panel(data,options)
    elif identifier in ('base_composition','per_base_quality','norm_density') and 'stages' in data:fig,meta=stages_panel(data,options)
    elif identifier=='traj_pca':fig,meta=trajectory_pca_panel(data,options)
    elif identifier=='cellcomm_bubble':fig,meta=bubble_panel(data,options)
    elif identifier=='genescore':fig,meta=genescore_panel(data,options)
    elif identifier=='consensus_rank':fig,meta=rank_matrix_panel(data,options)
    elif identifier=='batch_umap':
        from embedding_views import matched_embeddings
        fig,meta=matched_embeddings(data,options)
    elif identifier in ('per_base_quality','dup_insert','qc_triplet','rle_plot','norm_density'):fig,meta=qc_panel(data,options,identifier)
    elif identifier=='missing_pattern':fig,meta=qc_panel(data,options,identifier)
    elif identifier=='onevsrest_grid':
        if 'contrasts' not in data:raise ValueError('onevsrest_grid requires actual per-cluster DE tables with log2FC and adjusted p-values; use dim_highlight for embedding highlights')
        fig,meta=multi_volcano_panel(data,options)
    elif identifier=='butterfly' and options.get('variant','program_scores')!='marker_means':
        from single_cell_views import program_butterfly
        fig,meta=program_butterfly(data,options)
    elif identifier=='expr_density' and 'density_grids' in data:
        from single_cell_views import weighted_density_view
        fig,meta=weighted_density_view(data,options)
    elif identifier in ('marker_heatmap','expr_density','butterfly','proportion_dots','feature_overlay'):fig,meta=small_cell_panel(data,options,identifier)
    elif identifier in ('trajectory','velocity_stream'):fig,meta=trajectory_panel(data,options,identifier)
    elif identifier=='velocity_phase':fig,meta=phase_panel(data,options)
    elif identifier=='oncoprint':fig,meta=oncoprint_panel(data,options)
    elif identifier in ('fel_2d','pes_2d'):fig,meta=surface_panel(data,options,identifier)
    elif identifier=='orbitals':fig,meta=orbital_panel(data,options)
    elif identifier=='enrich_dot':fig,meta=enrichment_panel(data,options)
    elif identifier in ('chord_go','cellcomm_chord'):fig,meta=chord_panel(data,options)
    elif identifier=='alluvial':fig,meta=alluvial_panel(data,options)
    elif identifier in ('interaction_2d','charge_2d'):fig,meta=molecule_panel(data,options)
    elif identifier=='pose_grid_3d':fig,meta=poses_panel(data,options)
    elif identifier=='mmpbsa_stack':fig,meta=energy_panel(data,options)
    elif identifier=='paired_trajectory':fig,meta=paired_panel(data,options)
    elif identifier=='upset':fig,meta=upset_panel(data,options)
    elif identifier=='km_curve':fig,meta=km_panel(data,options)
    elif identifier=='scatter3d_projections':fig,meta=scatter3d_panel(data,options)
    elif identifier=='contrast_grid':fig,meta=multi_volcano_panel(data,options)
    elif identifier=='vs_funnel':fig,meta=funnel_panel(data,options)
    elif identifier in ml_ids and 'models' in data:fig,meta=ml_panel(data,options,identifier)
    elif identifier in ('pca_samples','pca_marginal','pca_outlier','traj_pca'): fig,meta=draw_pca(data,options,identifier)
    elif identifier in ('volcano','volcano_marginal'):fig,meta=draw_volcano(data,options)
    elif identifier=='effect_matrix':fig,meta=effect_matrix_panel(data,options)
    elif identifier=='marker_strip':fig,meta=marker_strip_panel(data,options)
    elif identifier in ('deg_heatmap','enrich_heatmap','module_trait','qc_sample_corr','sample_corr','score_heatmap','dccm','contact_map','rmsd_2d','feat_corr','missing_pattern','cnv_heatmap','pseudotime_heat','marker_heatmap','pose_rmsd_cluster','wiberg','confounder_assoc','ifp_barcode'):fig,meta=draw_heatmap(data,options,identifier)
    elif identifier=='dot_plot':fig,meta=draw_dot(data,options)
    elif identifier in ('umap_clusters','feature_grid','dim_facet','dim_highlight','onevsrest_grid'):fig,meta=draw_embedding(data,options,identifier)
    elif identifier in ('ridge_expr','split_violin','stacked_violin'):
        from distribution_views import distribution_view
        fig,meta=distribution_view(data,options,identifier)
    elif identifier in ('raincloud','cv_box','score_violin','dist_ridge'):fig,meta=draw_raincloud(data,options)
    elif identifier=='gsea_tracks' and options.get('variant','overlay')=='overlay' and len(data['pathways'])>1:
        from gsea_views import gsea_overlay
        fig,meta=gsea_overlay(data,options)
    elif identifier in ('gsea_running','gsea_tracks'):fig,meta=gsea_panel(data,options)
    elif identifier=='forest':fig,meta=forest_panel(data,options)
    elif identifier in ('proportion_stack','mapping_summary','state_occupancy'):fig,meta=proportion_panel(data,options)
    elif identifier in ('ir_spectrum','uvvis','emission_stokes','ecd','dos','nmr_spectrum'):fig,meta=spectra_panel(data,{'facet':identifier=='nmr_spectrum',**options})
    elif identifier=='mmpbsa_residue' and 'matrix' in data:fig,meta=draw_heatmap(data,options,identifier)
    elif identifier=='gap_compare':
        from renderers_remaining import frontier_gap_panel
        fig,meta=frontier_gap_panel(data,options)
    elif identifier in ('libsize_bar','affinity_bar','contact_freq','res_contrib','mmpbsa_residue','charges','charge_diff','boltzmann','consensus_rank'):fig,meta=bars_panel(data,options,identifier)
    elif identifier=='pseudotime_lines' and options.get('variant','facets')!='overlay':
        from renderers_remaining import gene_profile_panels
        fig,meta=gene_profile_panels(data,options)
    elif identifier in ('rmsd_overlay','rmsf','rg_sasa','hbond','pmf_1d','convergence','irc','scan_curve','opt_convergence','gene_body_coverage','saturation_curve','knee_rank','adapter_content','base_composition','cv_density','barcode_rank','pseudotime_lines'):fig,meta=line_panel(data,options)
    elif identifier in ('ma_plot','validation_scatter','ligand_efficiency','ramachandran','nci_rdg'):fig,meta=scatter_panel(data,options)
    else: raise NotImplementedError('No accepted renderer registered for '+identifier)
    finish_figure(fig)
    meta.update(template_id=identifier,status='RENDERED_UNREVIEWED',width_mm=fig.get_figwidth()*25.4,height_mm=fig.get_figheight()*25.4)
    if outdir is not None:
        cat=json.loads((Path(__file__).resolve().parents[1]/'assets/figure_catalog.json').read_text(encoding='utf8'));item=next(x for x in cat['figures'] if x['id']==identifier)
        stem=options.get('stem',item.get('outputs','fig_'+identifier).split('.')[0])
        summary_path=Path(outdir)/(stem+'_display_summary.tsv') if options.get('_shap_display_summary') else None
        if summary_path is not None and summary_path.exists() and not overwrite:raise FileExistsError(summary_path)
        meta['outputs']=safe_save(fig,stem,outdir,formats,overwrite=overwrite)
        if options.get('_shap_display_summary'):
            summary=options['_shap_display_summary'];rows=[]
            for output,(magnitude,shares) in enumerate(zip(summary['mean_abs'],summary['shares'])):
                for feature,value,share in zip(summary['features'],magnitude,shares):rows.append({'output_index':output,'feature_id':feature,'mean_abs_shap':value,'all_feature_share':share,'contribution_unit':meta['unit']})
            pd.DataFrame(rows).to_csv(summary_path,sep='\t',index=False);meta['outputs'].append(str(summary_path))
        if meta.get('outlier_table'):
            table_path=Path(outdir)/(stem+'_scores.tsv');pd.DataFrame(meta['outlier_table']).to_csv(table_path,sep='\t',index=False);meta['outputs'].append(str(table_path))
    return fig,meta

__all__=['render_template','resolve_id']
