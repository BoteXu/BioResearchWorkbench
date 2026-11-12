"""Specialist single-cell displays of frozen program and density channels."""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from design_system import *

def program_butterfly(d,o):
    scores=np.asarray(d['program_scores'],float);groups=np.asarray(d['groups'],str);names=d['program_names'];order=d['group_order']
    if scores.shape!=(len(groups),2) or len(names)!=2 or not np.isfinite(scores).all():raise ValueError('Two finite aligned supplied program scores per observation required')
    x=scores[:,0]-scores[:,1];y=scores[:,0]+scores[:,1];colors=identity_colors(o.setdefault('theme',{}),order)
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.63)),layout='constrained');gs=fig.add_gridspec(2,2,width_ratios=[1,.34],height_ratios=[.20,1],wspace=.06,hspace=.02)
    ax=fig.add_subplot(gs[1,0]);top=fig.add_subplot(gs[0,0],sharex=ax);guide=fig.add_subplot(gs[:,1]);guide.axis('off')
    ix=np.random.default_rng(0).permutation(len(x));ax.scatter(x[ix],y[ix],c=[colors[g] for g in groups[ix]],s=o.get('point_size',4),alpha=.75,lw=0)
    bins=np.linspace(min(x.min(),-.01),max(x.max(),.01),50)
    top.hist([x[groups==g] for g in order],bins=bins,stacked=True,color=[colors[g] for g in order],lw=0,alpha=.8);top.axis('off')
    ax.axvline(0,c=MUTED,lw=.7,ls='--');ax.set_xlabel('A − B · marker-program dominance');ax.set_ylabel('A + B · total supplied score');ax.grid(color=GRID,lw=.35)
    guide.legend(handles=[Line2D([],[],marker='o',ls='',c=colors[g],label=wrap_label(g,21)) for g in order],title='Cell identity',loc='upper left',fontsize=7)
    guide.text(0,.32,'A: '+wrap_label(names[0],23)+'\n\nB: '+wrap_label(names[1],23),transform=guide.transAxes,fontsize=6.7,va='top')
    fig.suptitle(o.get('title','Two supplied programs · dominance and total'),x=.02,ha='left',fontsize=10,fontweight='bold')
    return fig,{'variant':'two_program_butterfly','coordinate_transform':'x = supplied A - B; y = supplied A + B','program_names':names,'scores_refit':False,'observations':len(x),'identity_colors':colors}

def weighted_density_view(d,o):
    grids=d['density_grids'];xy=np.asarray(d['embedding']);nr,nc=choose_grid(len(grids),o.get('ncols'),o.get('nrows'))
    fig,axes=plt.subplots(nr,nc,figsize=journal_size(o.get('width','double'),o.get('aspect',.88*nr/nc+.12)),layout='constrained',squeeze=False,sharex=True,sharey=True)
    maximum=max(float(np.nanmax(g['z'])) for g in grids);cm=LinearSegmentedColormap.from_list('weighted_density',PALETTES['teal-depth'])
    for ax,g in zip(axes.flat,grids):
        x=np.asarray(g['x']);y=np.asarray(g['y']);z=np.asarray(g['z'])
        if z.shape!=(len(y),len(x)) or (z<0).any() or not np.isfinite(z).all():raise ValueError('Frozen nonnegative density grid must have shape y by x')
        ax.pcolormesh(x,y,z,cmap=cm,norm=mpl.colors.PowerNorm(o.get('color_gamma',.6),vmin=0,vmax=maximum),shading='auto',rasterized=False)
        ax.contour(x,y,z,levels=np.linspace(0,maximum,7)[1:],colors=INK,alpha=.25,linewidths=.35)
        ax.scatter(*xy.T,s=.25,c='white',alpha=.22,lw=0);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([]);ax.spines[:].set_visible(False);ax.set_title(g['label'],fontsize=8.5)
    for ax in axes.flat[len(grids):]:ax.remove()
    m=mpl.cm.ScalarMappable(norm=mpl.colors.PowerNorm(o.get('color_gamma',.6),0,maximum),cmap=cm)
    fig.colorbar(m,ax=list(axes.flat[:len(grids)]),shrink=.55,label=d.get('unit','Relative weighted density'))
    fig.suptitle(o.get('title','Expression-weighted embedding densities'),x=.02,ha='left',fontsize=10,fontweight='bold')
    return fig,{'method':d.get('method'),'KDE_fitted_in_renderer':False,'shared_scale':[0,maximum],'color_gamma':o.get('color_gamma',.6),'genes':[g['label'] for g in grids],'original_coordinates':True,'grid_sizes':[[len(g['y']),len(g['x'])] for g in grids]}
