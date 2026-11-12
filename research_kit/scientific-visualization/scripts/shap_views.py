"""Alternative SHAP summaries from frozen contributions, never refit explanations."""
import numpy as np,matplotlib as mpl,matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from design_system import journal_size,wrap_label,INK,MUTED,GRID,PALETTES

def shap_summary_view(d,o):
    from shap_channels import contribution_unit
    unit=contribution_unit(d)
    sh=np.asarray(d['explanation']['shap'],float);values=np.asarray(d['explanation']['feature_values'],float);names=d['features']
    if sh.ndim!=2 or values.shape!=sh.shape or sh.shape[1]!=len(names) or not np.isfinite(sh).all() or not np.isfinite(values).all():raise ValueError('Finite aligned samples by features SHAP and feature-value matrices required')
    variant=o.get('variant','rose');top=o.get('top_n',8 if variant=='beeswarm_rose' else 12)
    if isinstance(top,bool) or not isinstance(top,int) or not 1<=top<=12:raise ValueError('Rose views support 1 to 12 displayed features; use a linear summary or paginate more')
    importance=np.mean(np.abs(sh),axis=0);ix=np.argsort(-importance,kind='stable')[:min(top,len(names))];imp=importance[ix]
    if not np.any(imp>0):raise ValueError('All mean absolute contributions are zero; use a zero-value table rather than an empty rose')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.85 if variant=='beeswarm_rose' else .58)),layout='constrained')
    gs=fig.add_gridspec(2,2,width_ratios=[1.15,1] if variant=='beeswarm_rose' else [1,.95],height_ratios=[1,.12],wspace=.14,hspace=.05)
    if variant=='beeswarm_rose':
        sub=gs[0,0].subgridspec(1,2,width_ratios=[1,.035],wspace=.04);ax=fig.add_subplot(sub[0,0]);cax=fig.add_subplot(sub[0,1]);norm=mpl.colors.Normalize(*d['feature_value_limits']);cmap=LinearSegmentedColormap.from_list('feature_value',PALETTES['blue-coral'])
        for row,j in enumerate(ix):
            s=sh[:,j];offset=np.zeros(len(s));bins=np.round((s-s.min())/max(np.ptp(s),1e-12)*40);step=.30/max(1,np.ceil(max(np.sum(bins==b) for b in np.unique(bins))/2))
            for b in np.unique(bins):
                ids=np.flatnonzero(bins==b);rank=np.arange(len(ids));offset[ids]=(rank//2+1)*np.where(rank%2,1,-1)*step
            ax.scatter(s,row+offset,s=3.8,c=values[:,j],norm=norm,cmap=cmap,alpha=.7,lw=0)
        ax.axvline(0,c=MUTED,lw=.6);ax.set_yticks(range(len(ix)),[f'{i+1}. '+wrap_label(names[j],20) for i,j in enumerate(ix)],fontsize=7);ax.set_ylim(len(ix)-.5,-.5);ax.set_xlabel('Contribution ('+unit+')');ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',c=GRID,lw=.4);ax.set_title('Sample contributions',loc='left',fontsize=9)
        cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax,extend='both');cb.set_label(d['feature_value_label'],fontsize=7);cb.outline.set_visible(False)
        if d.get('feature_value_mode')=='within_feature_range':cb.set_ticks([0,1],labels=['Low','High'])
        polar=fig.add_subplot(gs[0,1],projection='polar');key=fig.add_subplot(gs[1,1]);key.axis('off')
    else:
        polar=fig.add_subplot(gs[:,0],projection='polar');key=fig.add_subplot(gs[:,1]);key.axis('off')
    n=len(ix);angle=2*np.pi/n;theta=np.arange(n)*angle;bottom=.34;outer=np.sqrt(bottom**2+(1-bottom**2)*imp/imp.max());width=angle*.82
    # Sector area = angle * (outer^2 - inner^2)/2: exactly proportional to mean |SHAP|.
    cmap=LinearSegmentedColormap.from_list('magnitude',PALETTES['blue-depth']);rose_colors=cmap(.32+.58*imp/imp.max())
    polar.set_theta_offset(np.pi/2);polar.set_theta_direction(-1);polar.bar(theta,outer-bottom,bottom=bottom,width=width,color=rose_colors,edgecolor='white',lw=.7)
    polar.set_ylim(0,1.18);polar.set_xticks(theta,[str(i+1) for i in range(n)],fontsize=7.5);polar.tick_params(axis='x',pad=-2);polar.set_yticks([]);polar.spines['polar'].set_visible(False);polar.grid(False)
    polar.text(.5,.51,'Mean |SHAP|',transform=polar.transAxes,ha='center',va='center',fontsize=8,fontweight='bold');polar.text(.5,.45,unit,transform=polar.transAxes,ha='center',va='center',fontsize=6.8,color=MUTED)
    if variant=='beeswarm_rose':
        polar.set_title('Global magnitude',loc='center',fontsize=9,pad=18)
        for i,j in enumerate(ix):polar.text(theta[i],outer[i]+.055,f'{imp[i]:.2f}',ha='center',va='center',fontsize=6.5,color=INK)
        key.text(0,1,'Sector area proportional to mean |SHAP|.\nFeature numbers match the left panel.',va='top',fontsize=6.8,color=MUTED)
    else:
        key.text(0,1,'Feature',va='top',fontsize=8,fontweight='bold');key.text(1,1,'Mean |SHAP|',ha='right',va='top',fontsize=8,fontweight='bold')
        for i,j in enumerate(ix):
            y=.92-i*.075;key.text(0,y,f'{i+1:02d}  '+wrap_label(names[j],27),va='top',fontsize=7.3);key.text(1,y,f'{imp[i]:.3f}',ha='right',va='top',fontsize=7.3)
        key.set_xlim(0,1);key.text(0,-.01,'Sector area proportional to mean |SHAP|',fontsize=7,color=MUTED)
    fig.suptitle(o.get('title','SHAP · distribution and global magnitude' if variant=='beeswarm_rose' else 'SHAP · ranked magnitude rose'),x=.01,ha='left',fontsize=10,fontweight='bold')
    return fig,{'variant':variant,'explainer':d['explanation'].get('scope'),'n_samples':sh.shape[0],'selected_features':[names[j] for j in ix],'mean_abs_shap':imp.tolist(),'mean_abs_all_features':importance.tolist(),'unit':unit,'rose_encoding':'sector area proportional to mean absolute SHAP; radius square-root transformed','bar_order':'descending magnitude; numbered exact feature key','no_refit':True,'direction':'rose is unsigned magnitude, not effect direction or causality','feature_value_color_limits':d['feature_value_limits'] if variant=='beeswarm_rose' else None}
