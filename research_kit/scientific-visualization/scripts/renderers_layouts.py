import math
import numpy as np,pandas as pd,matplotlib as mpl,matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from design_system import *
from renderers_extra import axes

def paired_panel(d,o):
    t=pd.DataFrame(d['table']);unit=d.get('unit_id','unit');stage=d.get('stage_column','stage');value=d.get('value_column','value')
    if t.duplicated([unit,stage]).any():raise ValueError('Duplicate unit/stage values; aggregate upstream explicitly')
    order=d['stage_order'];wide=t.pivot(index=unit,columns=stage,values=value).reindex(columns=order)
    if wide.isna().any().any():raise ValueError('Complete explicit pairing required; missing pairs cannot be silently connected')
    fig,ax=axes(o,.55);color_map=identity_colors(o.setdefault('theme',{}),order);colors=[color_map[s] for s in order];x=np.arange(len(order))
    for _,row in wide.iterrows():ax.plot(x,row.to_numpy(),c='#B4C3CD',alpha=.45,lw=.7,zorder=0)
    for j,s in enumerate(order):
        v=wide[s].to_numpy();jitter=((np.arange(len(v))*.61803398875)%1-.5)*.08;ax.scatter(j+jitter,v,c=colors[j],s=13,lw=.3,edgecolor='white',zorder=3);q=np.quantile(v,[.25,.5,.75]);ax.plot([j,j],q[[0,2]],c=colors[j],lw=5);ax.scatter(j,q[1],s=36,marker='_',c=INK,zorder=4)
    ax.set_xticks(x,[wrap_label(s,22) for s in order]);ax.set_ylabel(d.get('quantity','Supplied value'));ax.set_title(o.get('title','Paired observations & within-unit paths'),loc='left');return fig,{'pair_units':len(wide),'unit':d.get('unit_description',unit),'complete_pairing':True}

def upset_panel(d,o):
    sets={k:set(v) for k,v in d['sets'].items()};names=list(sets);members=set.union(*sets.values()) if sets else set()
    if not members:raise ValueError('No set memberships')
    patterns={}
    for x in members:
        p=tuple(n in sets[k] for n,k in [(x,k) for k in names]);patterns[p]=patterns.get(p,0)+1
    allp=sorted(patterns.items(),key=lambda x:(-x[1],x[0]));maxshown=int(o.get('max_shown',20));pats=allp[:maxshown];fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.68)),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1,.66],width_ratios=[1,.26],hspace=.04,wspace=.1);bar=fig.add_subplot(gs[0,0]);mat=fig.add_subplot(gs[1,0],sharex=bar);side=fig.add_subplot(gs[1,1],sharey=mat)
    bar.bar(range(len(pats)),[c for p,c in pats],color='#5B7E94',width=.7);bar.set_ylabel('Exclusive intersection size');bar.tick_params(labelbottom=False);bar.set_title(o.get('title','Set overlap & marginal sizes'),loc='left',pad=14)
    for j,(p,c) in enumerate(pats):
        ys=np.flatnonzero(p);mat.scatter([j]*len(names),range(len(names)),c=['#4C9685' if z else '#E5EBEF' for z in p],s=22,lw=0)
        if len(ys)>1:mat.plot([j,j],[ys.min(),ys.max()],c='#4C9685',lw=1)
    mat.set_yticks(range(len(names)),[wrap_label(s,28) for s in names]);mat.invert_yaxis();mat.set_xticks([]);mat.tick_params(length=0);mat.spines[:].set_visible(False)
    side.barh(range(len(names)),[len(sets[s]) for s in names],height=.6,color='#A2B9C7');side.tick_params(labelleft=False,length=0);side.set_xlabel('Set size');side.spines['left'].set_visible(False)
    return fig,{'total_intersections':len(allp),'shown_intersections':len(pats),'omitted_intersections':len(allp)-len(pats),'omitted_members':sum(c for _,c in allp[maxshown:]),'universe_size':len(members)}

def km_panel(d,o):
    t=pd.DataFrame(d['table']);groups=list(dict.fromkeys(t.stratum));colors=identity_colors(o.setdefault('theme',{}),groups);fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.77)),layout='constrained');gs=fig.add_gridspec(2,1,height_ratios=[1,.25],hspace=.05);ax=fig.add_subplot(gs[0]);risk=fig.add_subplot(gs[1],sharex=ax)
    ticks=np.linspace(0,t.time.max(),6)
    for j,g in enumerate(groups):
        sub=t[t.stratum==g];x=np.r_[0,sub.time];y=np.r_[1,sub.survival];ax.step(x,y,where='post',c=colors[g],lw=1.4,label=g)
        if 'lower' in sub:ax.fill_between(x,np.r_[1,sub.lower],np.r_[1,sub.upper],step='post',color=colors[g],alpha=.1,lw=0)
        cens=sub.ncensor>0
        if cens.any():ax.scatter(sub.time[cens],sub.survival[cens],c=colors[g],marker='|',s=18,lw=.7)
        for k in ticks:
            future=sub[sub.time>=k];n=int(future.nrisk.iloc[0]) if len(future) else 0;risk.text(k,j,str(n),ha='center',va='center',color=colors[g],fontsize=7.3)
    ax.set(ylim=(0,1.02),ylabel='Survival probability');ax.set_title(o.get('title','Survival curves, uncertainty & risk sets'),loc='left',pad=12);ax.legend();ax.tick_params(labelbottom=False);ax.grid(axis='y',color=GRID,lw=.4);risk.set_yticks(range(len(groups)),groups);risk.set_xticks(ticks);risk.set_xlabel(d.get('time_unit','Time (days)'));risk.set_ylim(len(groups)-.5,-.5);risk.spines[:].set_visible(False);risk.tick_params(axis='y',length=0)
    return fig,{'confidence_band':'provided','censors':'provided event table','risk_counts':'from supplied risk sets, no survival fitting'}

def scatter3d_panel(d,o):
    xyz=np.asarray(d.get('pca',d.get('xyz')));groups=np.asarray(d['groups']);order=d['group_order'];colors=identity_colors(o.setdefault('theme',{}),order)
    if xyz.ndim!=2 or xyz.shape[1]<3 or len(xyz)!=len(groups):raise ValueError('Three coordinates aligned to identity labels required')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.85)),layout='constrained');gs=fig.add_gridspec(2,2);ax=fig.add_subplot(gs[0,0],projection='3d')
    for g in order:
        p=xyz[groups==g];ax.scatter(p[:,0],p[:,1],p[:,2],s=2 if len(xyz)>500 else 15,c=colors[g],alpha=.6,lw=0,label=g)
    ax.set(xlabel='PC1',ylabel='PC2',zlabel='PC3');ax.view_init(elev=o.get('elev',25),azim=o.get('azim',40));ax.set_box_aspect([1,1,1]);ax.set_title('Three-dimensional geometry',fontsize=8)
    for ij,sp in zip([(0,1),(0,2),(1,2)],[gs[0,1],gs[1,0],gs[1,1]]):
        aa=fig.add_subplot(sp)
        for g in order:
            p=xyz[groups==g];aa.scatter(p[:,ij[0]],p[:,ij[1]],s=2 if len(xyz)>500 else 13,c=colors[g],alpha=.6,lw=0)
        aa.set(xlabel=f'PC{ij[0]+1}',ylabel=f'PC{ij[1]+1}');aa.grid(color=GRID,lw=.4)
    fig.legend(handles=[Line2D([],[],marker='o',ls='',color=colors[g],label=wrap_label(g,20)) for g in order],loc='outside lower center',ncol=min(4,len(order)),fontsize=6.7);return fig,{'orthogonal_projections':True,'coordinates_refit':False,'camera':{'elev':o.get('elev',25),'azim':o.get('azim',40)}}

def multi_volcano_panel(d,o):
    from renderers import draw_volcano
    from composite import compose_panels
    contrasts=d['contrasts'];n=len(contrasts);nr,nc=choose_grid(n,o.get('ncols'),o.get('nrows'),max_cols=2)
    if n==1 and o.get('single_as_joint',True):
        fig,meta=draw_volcano({'de':contrasts[0]['de'],'contrast':contrasts[0]['label']},{**o,'title':contrasts[0]['label']})
        meta.update(single_contrast_joint=True,nrows=1,ncols=1)
        return fig,meta
    fc=float(o.get('log2fc',1.));q=float(o.get('fdr',.05))
    if not 0<q<1 or fc<0:raise ValueError('Invalid shared thresholds')
    tables=[pd.DataFrame(c['de']) for c in contrasts];allx=np.concatenate([t.log2FC.to_numpy() for t in tables]);allp=np.concatenate([t.padj.to_numpy() for t in tables])
    if not np.isfinite(allx).all() or not np.isfinite(allp).all() or ((allp<0)|(allp>1)).any():raise ValueError('Finite effects and adjusted P in[0,1] required')
    fin=-np.log10(allp[allp>0]);cap=float(fin.max()+max(1,fin.max()*.08)) if len(fin) else -np.log10(q)+1
    colors=['#CFD8DE','#3B6F91','#CA7354'];fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.58*nr)),layout='constrained');outer=fig.add_gridspec(nr,nc,hspace=.10,wspace=.10);panels=[];zero_counts=[]
    for i,(c,t) in enumerate(zip(contrasts,tables)):
        marginal=o.get('variant','marginal')!='classic'
        if marginal:
            sub=outer[i//nc,i%nc].subgridspec(2,2,height_ratios=[.20,1],width_ratios=[1,.19],hspace=.02,wspace=.02);ax=fig.add_subplot(sub[1,0]);top=fig.add_subplot(sub[0,0],sharex=ax);side=fig.add_subplot(sub[1,1],sharey=ax)
        else:ax=fig.add_subplot(outer[i//nc,i%nc])
        x=t.log2FC.to_numpy();p=t.padj.to_numpy();y=-np.log10(np.where(p==0,10**(-cap),p));sig=(p<q)&(abs(x)>fc);cls=np.where(sig&(x>0),2,np.where(sig&(x<0),1,0));zero_counts.append(int(sum(p==0)))
        for j,color in enumerate(colors):
            hit=(cls==j)&(p>0);ax.scatter(x[hit],y[hit],s=2.5 if j==0 else 4,c=color,lw=0,alpha=.35 if j==0 else .8)
            hit=(cls==j)&(p==0)
            if hit.any():ax.scatter(x[hit],y[hit],s=12,marker='^',c=color,edgecolors='white',lw=.3)
        if marginal:
            top.hist([x[cls==j] for j in range(3)],bins=np.linspace(allx.min(),allx.max(),40),stacked=True,color=colors,lw=0);side.hist([y[cls==j] for j in range(3)],bins=np.linspace(0,cap,30),stacked=True,color=colors,orientation='horizontal',lw=0);top.axis('off');side.axis('off');top.set_title(wrap_label(c['label'],35),loc='left',fontsize=8)
        else:ax.set_title(wrap_label(c['label'],35),loc='left',fontsize=8)
        ax.axvline(-fc,c=MUTED,ls='--',lw=.6);ax.axvline(fc,c=MUTED,ls='--',lw=.6);ax.axhline(-np.log10(q),c=MUTED,ls='--',lw=.6);ax.set(xlabel='log2 fold change',ylabel='−log10 adjusted P',xlim=(allx.min()-max(np.ptp(allx)*.05,.1),allx.max()+max(np.ptp(allx)*.05,.1)),ylim=(0,cap*1.15));panels.append(ax)
    fig.legend(handles=[Patch(color=colors[i],label=x) for i,x in enumerate(['Other','Down','Up'])],title=f'FDR < {q:g}; |log2FC| > {fc:g} · triangles denote source P=0',loc='outside lower center',ncols=3,frameon=False)
    return fig,{'shared_thresholds':{'fdr':q,'log2fc':fc},'shared_axes':True,'shared_zero_display_height':cap,'reported_zero_counts':zero_counts,'variant':o.get('variant','marginal'),'contrasts':[c['label'] for c in contrasts],'nrows':nr,'ncols':nc}

def funnel_panel(d,o):
    labels=d['stages'];counts=np.asarray(d['counts'],int)
    if len(labels)!=len(counts) or (counts<0).any() or (np.diff(counts)>0).any():raise ValueError('Monotone nonincreasing genuine stage counts required')
    fig,ax=axes(o,max(.45,.10*len(labels)+.2));maximum=max(counts.max(),1)
    for i,(label,n) in enumerate(zip(labels,counts)):
        ax.barh(i,n,left=-n/2,height=.64,color=PALETTES['muted'][i%8],edgecolor='white',lw=.8);ax.text(n/2+maximum*.03,i,f'{n:,}',va='center',fontsize=8);ax.text(-maximum*.58,i,wrap_label(label,24),ha='right',va='center',fontsize=8)
    ax.set_xlim(-maximum*1.2,maximum*.8);ax.set_ylim(len(labels)-.4,-.6);ax.axis('off');ax.set_title(o.get('title','Screening stages & retained candidates'),loc='left',pad=12);return fig,{'counts':counts.tolist(),'stages':labels,'no_fabricated_stages':True}

__all__=['paired_panel','upset_panel','km_panel','scatter3d_panel','multi_volcano_panel','funnel_panel']
