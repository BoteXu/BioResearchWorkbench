"""Preserved H36/R11 design: class swarms, calibrated roses and share rings.

Ported from the project's own figure_reference.plot_multiclass_contributions.
Data and class axes are supplied; this module does not train or explain a model.
"""
import math,numpy as np,matplotlib as mpl,matplotlib.pyplot as plt
from matplotlib.patches import Wedge,Circle,Patch
from matplotlib.colors import LinearSegmentedColormap,Normalize
from design_system import *

def classic_contribution_page(d,o):
    classes=d.get('class_contributions')
    if classes is None:
        classes=[{'label':d.get('positive_class','Supplied output'),'shap':d['explanation']['shap'],'feature_values':d['explanation']['feature_values']}]
    if not classes:raise ValueError('At least one actual explained output is required')
    names=list(d['features']);unit=d.get('explanation',{}).get('unit',d.get('unit'))
    if not names or len(set(names))!=len(names):raise ValueError('Nonempty unique feature names required')
    if not unit:raise ValueError('Explicit SHAP contribution unit required')
    labels=[c['label'] for c in classes]
    if len(set(labels))!=len(labels):raise ValueError('Unique explained output names required')
    matrices=[np.asarray(c['shap'],float) for c in classes];features=[np.asarray(c['feature_values'],float) for c in classes]
    for a,v in zip(matrices,features):
        if a.ndim!=2 or a.shape!=v.shape or a.shape[0]==0 or a.shape[1]!=len(names) or not np.isfinite(a).all() or not np.isfinite(v).all():raise ValueError('Finite nonempty aligned SHAP and feature matrices required per output')
    magnitudes=np.array([np.abs(a).mean(axis=0) for a in matrices]);totals=magnitudes.sum(axis=1)
    if (totals<=0).any():raise ValueError('Zero total absolute contribution: use a zero table')
    # All features enter the share denominator; the rose displays eight plus an explicit remainder.
    selected=np.argsort(-magnitudes.mean(axis=0),kind='stable')[:min(8,len(names))];rest=[j for j in range(len(names)) if j not in selected]
    keys=[names[j] for j in selected]+([f'Other {len(rest)} features'] if rest else [])
    supplied=d.get('share_table')
    if supplied is not None:
        shares=np.asarray(supplied,float)
        if shares.shape!=magnitudes.shape or not np.isfinite(shares).all() or (shares<0).any() or not np.allclose(shares.sum(axis=1),1,rtol=0,atol=1e-8):raise ValueError('Full supplied nonnegative per-output feature shares summing to one required')
        if not np.allclose(shares,magnitudes/totals[:,None],rtol=1e-6,atol=1e-9):raise ValueError('Declared mean-absolute SHAP shares disagree with the supplied complete contributions')
    else:raise ValueError('Freeze full mean-absolute SHAP share_table upstream; renderer will not infer share statistics')
    shown=np.column_stack([shares[:,j] for j in selected]+([shares[:,rest].sum(axis=1)] if rest else []))
    if len(classes)==1 and o.get('layout','inset')=='inset':
        return inset_output_page(d,o,matrices[0],features[0],names,magnitudes[0],labels[0],unit)
    if len(classes)==1 and o.get('layout','inset')=='compact':
        return single_output_page(d,o,matrices[0],features[0],names,magnitudes[0],shown[0],keys,labels[0],unit)
    palette=dict(zip(keys,PALETTES[o.get('feature_palette','muted')][:len(selected)]+(['#B5BEC5'] if rest else [])))
    ncols=o.get('ncols',min(2,len(classes)));nr,nc=choose_grid(len(classes),ncols=ncols,nrows=o.get('nrows'),max_cols=2)
    if nc>2:raise ValueError('Use up to two class columns at 183 mm and paginate further outputs')
    maximum=o.get('max_features',len(names))
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1<=maximum<=len(names):raise ValueError('max_features must select a positive bounded number of source features')
    wrapped_names={j:wrap_label(names[j],21) for j in range(len(names))}
    row_height=max(64,sum(1+.65*wrapped_names[j].count('\n') for j in range(len(names)))*3.8+24 if maximum==len(names) else maximum*4.8+24);height=nr*row_height+48+10*math.ceil(len(keys)/3)
    if height>480:raise ValueError('Class page exceeds 480 mm; select fewer outputs per page')
    width=o.get('width','double');W=WIDTH_MM[width];fig=plt.figure(figsize=(W/25.4,height/25.4),layout='constrained')
    outer=fig.add_gridspec(nr+1,nc,height_ratios=[row_height]*nr+[48],hspace=.20,wspace=.12);cmap=LinearSegmentedColormap.from_list('feature_value',PALETTES['blue-coral']);norm=Normalize(*d.get('feature_value_limits',[-2,2]));all_min=min(a.min() for a in matrices);all_max=max(a.max() for a in matrices);margin=max((all_max-all_min)*.04,.01);orders=[]
    for k,(c,a,v) in enumerate(zip(classes,matrices,features)):
        sub=outer[k//nc,k%nc].subgridspec(1,2,width_ratios=[1,.34],wspace=.04);ax=fig.add_subplot(sub[0,0]);rose=fig.add_subplot(sub[0,1]);order=np.argsort(-magnitudes[k],kind='stable')[:maximum];orders.append([names[j] for j in order])
        heights=np.array([1+.65*wrapped_names[j].count('\n') for j in order]);edges=np.r_[0,np.cumsum(heights)];centers=(edges[:-1]+edges[1:])/2
        for row,j in enumerate(order):
            x=a[:,j];bins=np.round((x-all_min)/max(all_max-all_min,1e-12)*60);offset=np.zeros(len(x));scale=.30/max(1,np.ceil(max(np.sum(bins==b) for b in np.unique(bins))/2))
            for b in np.unique(bins):
                ix=np.flatnonzero(bins==b);rank=np.arange(len(ix));offset[ix]=(rank//2+1)*np.where(rank%2,1,-1)*scale
            ax.scatter(x,centers[row]+offset,c=v[:,j],norm=norm,cmap=cmap,s=3.6,lw=0,alpha=.80)
        ax.axvline(0,c=MUTED,lw=.7);ax.set_yticks(centers,[wrapped_names[j] for j in order],fontsize=7);ax.set_ylim(edges[-1],0);ax.set_xlim(all_min-margin,all_max+margin);ax.grid(axis='y',ls=(0,(1,4)),color=GRID,lw=.4);ax.set_xlabel('SHAP contribution ('+unit+')',fontsize=8);ax.set_title(c['label']+f' · n = {len(a)}',loc='left',fontsize=9);ax.spines[['top','right','left']].set_visible(False);ax.tick_params(axis='y',length=0)
        vals=shown[k];radius_max=math.sqrt(shown.max());sector=360/len(keys)
        for j,(key,value) in enumerate(zip(keys,vals)):rose.add_patch(Wedge((0,0),math.sqrt(value),90-j*sector-sector,90-j*sector,facecolor=palette[key],edgecolor='white',lw=.55))
        reference=min(.20,float(shown.max()));rose.add_patch(Circle((0,0),math.sqrt(reference),fc='none',ec=MUTED,lw=.55,ls='--'));bound=radius_max*1.15;rose.set(xlim=(-bound,bound),ylim=(-bound,bound),aspect='equal');rose.axis('off');rose.set_title('Absolute shares',fontsize=7,pad=7);rose.text(.5,-.12,f'Area reference: {reference:.0%}',transform=rose.transAxes,ha='center',fontsize=6.4,color=MUTED)
    lower=outer[-1,:].subgridspec(1,2,width_ratios=[.52,1]);ring=fig.add_subplot(lower[0,0]);key=fig.add_subplot(lower[0,1]);ring.axis('off');ring.set_aspect('equal');key.axis('off')
    thickness=min(.18,.70/len(classes))
    for k,c in enumerate(classes):
        start=90;radius=1-k*(thickness+.035)
        for name,value in zip(keys,shown[k]):
            extent=360*value;ring.add_patch(Wedge((0,0),radius,start-extent,start,width=thickness,fc=palette[name],ec='white',lw=.55));start-=extent
    ring.set(xlim=(-1.15,1.15),ylim=(-1.15,1.15));ring.text(0,0,'100%\nper output',ha='center',va='center',fontsize=7);ring.set_title('Contribution shares',fontsize=8)
    key.legend(handles=[Patch(facecolor=palette[name],label=wrap_label(name,23)) for name in keys],loc='upper left',ncol=3,fontsize=6.8,handlelength=1,columnspacing=1.4)
    key.text(0,-.05,wrap_label('Rings outer to inner: '+', '.join(labels),70),fontsize=7,va='top',color=MUTED)
    sm=mpl.cm.ScalarMappable(norm=norm,cmap=cmap);cb=fig.colorbar(sm,ax=fig.axes[:-2],location='top',shrink=.38,fraction=.025,pad=.035,aspect=30,extend='both');cb.set_label(d.get('feature_value_label','Standardized feature value'),fontsize=7);cb.ax.tick_params(labelsize=6.5);cb.outline.set_visible(False)
    fig.suptitle(o.get('title','SHAP · class distributions and contribution shares'),x=.01,ha='left',fontsize=10,fontweight='bold')
    return fig,{'variant':'reference_classic','preserved_design':'H36 / R11 swarms, calibrated roses and concentric share rings','source_class_order':labels,'n_per_output':[len(a) for a in matrices],'feature_orders':orders,'share_features':keys,'share_matrix':shown.tolist(),'share_denominator':'all supplied features, remainder explicitly included','rose':'equal angles; sector area proportional to supplied share; common area scale','ring':'angle proportional to supplied share; common feature colors','share_estimation':'none; frozen upstream share table required','model_fit':'none','unit':unit,'layout':{'rows':nr,'columns':nc},'displayed_feature_count':maximum,'source_feature_count':len(names)}

def single_output_page(d,o,a,v,names,magnitude,shares,keys,label,unit):
    maximum=o.get('max_features',len(names))
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1<=maximum<=len(names):raise ValueError('Invalid displayed feature count')
    order=np.argsort(-magnitude,kind='stable')[:maximum];texts=[wrap_label(names[j],23) for j in order];heights=np.array([1+.70*t.count('\n') for t in texts]);edges=np.r_[0,np.cumsum(heights)];centers=(edges[:-1]+edges[1:])/2
    width=WIDTH_MM[o.get('width','double')];narrow=width<=120;height=max(112,edges[-1]*4.2+32)+(27 if narrow else 0)
    fig=plt.figure(figsize=(width/25.4,height/25.4),layout='constrained');gs=fig.add_gridspec(2 if narrow else 1,2,width_ratios=[1,.42],height_ratios=[1,.29] if narrow else [1],wspace=.12,hspace=.12);ax=fig.add_subplot(gs[0,0]);right=gs[0,1].subgridspec(3 if narrow else 4,1,height_ratios=[.15,1,1] if narrow else [.15,1,1,1.30],hspace=.12);cax=fig.add_subplot(right[0,0]);rose=fig.add_subplot(right[1,0]);ring=fig.add_subplot(right[2,0]);key=fig.add_subplot(gs[1,:] if narrow else right[3,0]);key.axis('off')
    limits=d.get('feature_value_limits',[-2,2])
    if len(limits)!=2 or not np.isfinite(limits).all() or limits[0]>=limits[1]:raise ValueError('Finite increasing feature-value color limits required')
    norm=Normalize(*limits);cm=LinearSegmentedColormap.from_list('feature_value',PALETTES['blue-coral']);xmin,xmax=float(a.min()),float(a.max());span=max(xmax-xmin,1e-9)
    for row,j in enumerate(order):
        x=a[:,j];bins=np.round((x-xmin)/span*65);off=np.zeros(len(x));step=.30/max(1,np.ceil(max(np.sum(bins==b) for b in np.unique(bins))/2))
        for b in np.unique(bins):
            ids=np.flatnonzero(bins==b);rank=np.arange(len(ids));off[ids]=(rank//2+1)*np.where(rank%2,1,-1)*step
        ax.scatter(x,centers[row]+off,c=v[:,j],norm=norm,cmap=cm,s=3.7,lw=0,alpha=.8)
    ax.set_yticks(centers,texts,fontsize=7.2);ax.set_ylim(edges[-1],0);ax.set_xlim(xmin-.04*span,xmax+.04*span);ax.axvline(0,c=MUTED,lw=.65);ax.grid(axis='y',color=GRID,lw=.4,ls=(0,(1,4)));ax.spines[['top','right','left']].set_visible(False);ax.tick_params(axis='y',length=0);ax.set_xlabel('SHAP contribution ('+unit+')');ax.set_title(label+f' · n = {len(a)}',loc='left',fontsize=9,pad=10)
    colors=PALETTES[o.get('feature_palette','muted')][:min(8,len(names))]+(['#B5BEC5'] if len(names)>8 else []);palette=dict(zip(keys,colors));sector=360/len(keys);radius_max=math.sqrt(max(shares));ref=min(.2,float(max(shares)))
    for i,(name,value) in enumerate(zip(keys,shares)):rose.add_patch(Wedge((0,0),math.sqrt(value),90-(i+1)*sector,90-i*sector,fc=palette[name],ec='white',lw=.5))
    rose.add_patch(Circle((0,0),math.sqrt(ref),fc='none',ec=MUTED,ls='--',lw=.5));bound=radius_max*1.12;rose.set(xlim=(-bound,bound),ylim=(-bound,bound),aspect='equal');rose.axis('off');rose.set_title('Absolute shares · rose',fontsize=7.5);rose.text(.5,-.13,f'Area reference: {ref:.0%}',transform=rose.transAxes,ha='center',fontsize=6.5,color=MUTED)
    start=90
    for name,value in zip(keys,shares):ring.add_patch(Wedge((0,0),1,start-360*value,start,width=.22,fc=palette[name],ec='white',lw=.5));start-=360*value
    ring.set(xlim=(-1.1,1.1),ylim=(-1.1,1.1),aspect='equal');ring.axis('off');ring.text(0,0,'100%\nall features',ha='center',va='center',fontsize=7);ring.set_title('Same shares · ring',fontsize=7.5)
    for i,(name,value) in enumerate(zip(keys,shares)):
        col=i//5 if narrow else 0;row=i%5 if narrow else i;y=1-row*(.20 if narrow else .107);base=col*.54
        key.scatter([base+.015],[y-.015],s=18,c=[palette[name]],marker='s');key.text(base+.055,y,wrap_label(name,23),va='top',fontsize=6.6);key.text(base+.49 if narrow else 1.02,y,f'{value:.1%}',ha='right',va='top',fontsize=6.6)
    key.set(xlim=(0,1.04),ylim=(-.03,1.06));cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cm),cax=cax,orientation='horizontal',extend='both');cb.set_label(wrap_label(d.get('feature_value_label','Standardized feature value'),18 if narrow else 36),fontsize=6.5,labelpad=2);cb.ax.tick_params(labelsize=6);cb.outline.set_visible(False)
    fig.suptitle(wrap_label(o.get('title','SHAP · contributions and absolute shares'),48 if narrow else 75),x=.01,ha='left',fontsize=10,fontweight='bold')
    return fig,{'variant':'reference_classic','layout':'compact_single_output','preserved_design':'swarm, calibrated rose and contribution-share ring','n_per_output':[len(a)],'source_class_order':[label],'feature_orders':[[names[j] for j in order]],'displayed_feature_count':len(order),'source_feature_count':len(names),'share_features':keys,'share_matrix':[shares.tolist()],'share_denominator':'all supplied features; explicit remainder','share_estimation':'none; supplied shares audited against complete frozen contributions','unit':unit,'rose':'equal angles; area proportional to supplied share','ring':'angle proportional to supplied share','model_fit':'none'}


def inset_output_page(d,o,a,v,names,magnitude,label,unit):
    """Default swarm with a small rose in reserved space, never over data points."""
    width=journal_size(o.get('width','double'),1)[0]*25.4
    maximum=o.get('max_features',min(len(names),8 if width<=120 else 12))
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1<=maximum<=len(names):
        raise ValueError('max_features must select one to all supplied features')
    order=np.argsort(-magnitude,kind='stable')[:maximum]
    wrapped=[wrap_label(names[j],16 if width<=120 else 29) for j in order]
    heights=np.array([1+.65*t.count('\n') for t in wrapped]);edges=np.r_[0,np.cumsum(heights)];centers=(edges[:-1]+edges[1:])/2
    top,bottom,left,right=24.,28.,29. if width<=120 else 44.,4.
    height=max(100,edges[-1]*4.9+top+bottom)
    if 'aspect' in o:height=max(height,width*o['aspect'])
    if height>480:raise ValueError('Page exceeds 480 mm; select or paginate features explicitly')
    fig=plt.figure(figsize=(width/25.4,height/25.4))
    plot_width=width-left-right
    if plot_width<36:raise ValueError('Panel is too narrow for readable feature labels; use one column or a wider page')
    ax=fig.add_axes([left/width,bottom/height,plot_width/width,(height-top-bottom)/height])
    color_width=min(42.,plot_width*.47)
    cax=fig.add_axes([left/width,10/height,color_width/width,2.6/height])
    key=fig.add_axes([(left+color_width+4)/width,7.4/height,(plot_width-color_width-4)/width,6.5/height]);key.axis('off')
    limits=d['feature_value_limits'];norm=Normalize(*limits);cmap=LinearSegmentedColormap.from_list('shap_feature_value',PALETTES['blue-coral'])
    xmin,xmax=float(min(0,a.min())),float(max(0,a.max()));span=max(xmax-xmin,1e-9)
    for i,j in enumerate(order):
        x=a[:,j];bins=np.round((x-xmin)/span*65);off=np.zeros(len(x));step=.31/max(1,np.ceil(max(np.sum(bins==b) for b in np.unique(bins))/2))
        for b in np.unique(bins):
            ids=np.flatnonzero(bins==b);r=np.arange(len(ids));off[ids]=(r//2+1)*np.where(r%2,1,-1)*step
        ax.scatter(x,centers[i]+off,c=v[:,j],norm=norm,cmap=cmap,s=3.2 if width<=120 else 4.2,lw=0,alpha=.78)
    ax.set_yticks(centers,[f'{i+1:02d}  '+s for i,s in enumerate(wrapped)],fontsize=7)
    ax.set_ylim(edges[-1]+.25,-.25);ax.set_xlim(xmin-.04*span,xmax+.48*span)
    ax.axvline(0,color=MUTED,lw=.65);ax.grid(axis='y',ls=(0,(1,4)),color=GRID,lw=.4)
    ax.spines[['top','right','left']].set_visible(False);ax.tick_params(axis='y',length=0)
    ax.set_xlabel('SHAP contribution ('+unit+')',fontsize=8)
    ax.set_title(wrap_label(label+f' · n = {len(a)}',40 if width<=120 else 70),loc='left',fontsize=8.5,pad=8)
    # The inset is deliberately reserved beyond the maximum supplied contribution.
    # Point coordinates, axes units and the attribution range are not transformed.
    rose=ax.inset_axes([.755,.62,.235,.34]);rose.axis('off');rose.set_aspect('equal')
    shown=order[:min(8,len(order))];remaining=[j for j in range(len(names)) if j not in shown]
    full=np.asarray(d['share_table'],float)[0]
    vals=[full[j] for j in shown]+([full[remaining].sum()] if remaining else [])
    keys=[str(i+1) for i in range(len(shown))]+(['R'] if remaining else [])
    colors=PALETTES[o.get('feature_palette','muted')][:len(shown)]+(['#B5BEC5'] if remaining else [])
    sector=360/len(vals);radius=max(math.sqrt(max(vals)),1e-6)
    for i,(value,color) in enumerate(zip(vals,colors)):
        start=90-(i+1)*sector;stop=90-i*sector
        rose.add_patch(Wedge((0,0),math.sqrt(value),start,stop,fc=color,ec='white',lw=.5))
        angle=math.radians((start+stop)/2);rose.text(radius*1.24*math.cos(angle),radius*1.24*math.sin(angle),keys[i],ha='center',va='center',fontsize=6.3)
    bound=radius*1.58;rose.set(xlim=(-bound,bound),ylim=(-bound,bound))
    rose.set_title('Absolute shares',fontsize=7,pad=2)
    key.text(0,.88,wrap_label('Rose: all features',18 if width<=120 else 30),fontsize=6.5,color=MUTED,va='center')
    if remaining:key.text(0,.10,wrap_label(f'R: other {len(remaining)} ({vals[-1]:.1%})',19 if width<=120 else 34),fontsize=6.5,color=MUTED,va='center')
    cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax,orientation='horizontal')
    cb.set_label(d['feature_value_label'],fontsize=6.8,labelpad=2);cb.outline.set_visible(False);cb.ax.tick_params(labelsize=6.5,length=2)
    if d.get('feature_value_mode')=='within_feature_range':cb.set_ticks([0,1],labels=['Low','High'])
    else:cb.set_ticks([limits[0],sum(limits)/2,limits[1]])
    fig.suptitle(wrap_label(o.get('title','SHAP · contributions and global shares'),40 if width<=120 else 78),x=.01,ha='left',fontsize=10,fontweight='bold')
    return fig,{'variant':'reference_classic','layout':'small_rose_inset','preserved_design':'sample swarms with small calibrated rose inset; classic rings remain optional',
        'unit':unit,'n_per_output':[len(a)],'source_class_order':[label],'feature_orders':[[names[j] for j in order]],
        'source_feature_count':len(names),'displayed_feature_count':len(order),'share_features':[names[j] for j in shown]+([f'Other {len(remaining)} features'] if remaining else []),
        'share_matrix':[list(map(float,vals))],'share_denominator':'all supplied features; explicit remainder',
        'rose':'equal angles, sector area proportional to mean absolute SHAP share; square-root radii',
        'inset_reserved_beyond_data':True,'model_fit':'none'}
