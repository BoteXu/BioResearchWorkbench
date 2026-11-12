"""Distinct violin and ridge forms from actual observations and frozen KDEs."""
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib.patches import Patch
from design_system import *

def distribution_view(d,o,kind):
    t=pd.DataFrame(d['table']);genes=d['genes'];groups=d['group_order']
    if not {'gene','group','value'}<=set(t):raise ValueError('Long expression requires gene, group and value')
    if not np.isfinite(t.value).all():raise ValueError('Finite expression observations required')
    if len(genes)>12 or len(groups)>30:raise ValueError('Paginate more than 12 genes or 30 groups')
    densities={(r['gene'],r['group'],r.get('hue')):r for r in d['densities']}
    hues=d.get('hue_order',[]);split=kind=='split_violin'
    if split and (len(hues)!=2 or 'hue' not in t):raise ValueError('Split violins require exactly two genuine supplied hue categories')
    colors=identity_colors(o.setdefault('theme',{}),hues if split else groups)
    combined_gene_axis=split and d.get('gene_as_group',False)
    facets=[None] if combined_gene_axis else genes
    nr,nc=choose_grid(len(facets),o.get('ncols',1),o.get('nrows'))
    aspect=o.get('aspect',max(.55,.075*len(groups)+.12) if kind=='ridge_expr' else max(.45,.31*nr))
    fig,aa=plt.subplots(nr,nc,figsize=journal_size(o.get('width','onehalf' if kind=='ridge_expr' else 'double'),aspect),squeeze=False,layout='constrained')
    for ax,gene in zip(aa.flat,facets):
        for i,group in enumerate(groups):
            for h in hues if split else [None]:
                actual_gene=group if combined_gene_axis else gene
                z=t[(t.gene==actual_gene)&(t.group==group)]
                if h is not None:z=z[z.hue==h]
                if z.empty:continue
                key=(actual_gene,group,h);den=densities.get(key)
                if den is None:raise ValueError('Missing frozen density for '+str(key))
                x=np.asarray(den['x'],float);y=np.asarray(den['y'],float)
                if x.shape!=y.shape or x.ndim!=1 or not np.isfinite(np.r_[x,y]).all() or (y<0).any():raise ValueError('Invalid frozen density grid')
                color=colors[h if split else group];w=y/max(y.max(),1e-12)*.39
                q=np.quantile(z.value,[.25,.5,.75])
                if kind=='ridge_expr':
                    ax.fill_between(x,i,i+w*2.10,color=color,alpha=.45,lw=0);ax.plot(x,i+w*2.10,c=color,lw=.8)
                    ax.scatter(z.value,np.full(len(z),i-.035),s=1.2,c=color,alpha=.16,lw=0)
                    ax.plot([q[1],q[1]],[i,i+.15],c=INK,lw=.9)
                else:
                    left,right=(i-w,i+w) if not split else (i-w,np.full_like(w,i)) if h==hues[0] else (np.full_like(w,i),i+w)
                    ax.fill_betweenx(x,left,right,color=color,alpha=.55,lw=.6,edgecolor=color)
                    delta=0 if not split else -.10 if h==hues[0] else .10
                    ax.plot([i+delta,i+delta],q[[0,2]],c=INK,lw=1.1);ax.scatter([i+delta],[q[1]],c='white',edgecolors=INK,lw=.4,s=9,zorder=3)
                    if len(z)<=25:
                        offset=np.linspace(.07,.29,len(z))*(-1 if split and h==hues[0] else 1)
                        ax.scatter(i+offset,z.value,s=7,facecolors=color,edgecolors='white',lw=.35,zorder=4)
        if gene is not None and len(facets)>1:ax.set_title(wrap_label(gene,35),loc='left',fontsize=8.5)
        if kind=='ridge_expr':
            ax.set_yticks(range(len(groups)),[wrap_label(x,23) for x in groups]);ax.set_xlabel(d.get('unit','Supplied expression'));ax.set_ylim(-.3,len(groups)-.2);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
        else:
            ax.set_xticks(range(len(groups)),[wrap_label(x,18) for x in groups],rotation=35,ha='right',fontsize=6.5);ax.set_ylabel(d.get('unit','Supplied expression'));ax.grid(axis='y',color=GRID,lw=.4)
    for ax in aa.flat[len(facets):]:ax.remove()
    if split:fig.legend(handles=[Patch(color=colors[h],label=h) for h in hues],loc='outside lower center',ncols=2,title=d.get('hue_label','Supplied category'))
    fig.suptitle(o.get('title','Supplied expression distributions'),x=.01,ha='left',fontweight='bold')
    return fig,{'form':kind,'genes':genes,'groups':groups,'hue_order':hues,'density_fitting':'none; supplied frozen grids','density_width_normalization':'each supplied density divided by its own maximum; width/height is not cell abundance','observations':len(t),'summary':'median and IQR, not CI','identity_colors':colors}

__all__=['distribution_view']
