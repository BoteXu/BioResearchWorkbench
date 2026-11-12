"""Shared-ranking multi-pathway GSEA tracks from supplied result arrays."""
import numpy as np
import matplotlib.pyplot as plt
from design_system import *

def gsea_overlay(d,o):
    paths=d['pathways'];n=len(paths)
    if n<1 or n>8:raise ValueError('Overlay 1 to 8 pathways, or explicitly facet/page larger collections')
    rank=np.asarray(paths[0]['rank']);metric=np.asarray(paths[0]['metric']);colors=identity_colors(o.setdefault('theme',{}),[p['name'] for p in paths])
    if any(not np.array_equal(p['rank'],rank) or not np.array_equal(p['metric'],metric) for p in paths):raise ValueError('Shared GSEA tracks require identical supplied ranks and ranking metric; use separate facets for different universes')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',max(.54,.35+.085*n))),layout='constrained');gs=fig.add_gridspec(n+2,2,width_ratios=[1,.38],height_ratios=[1]+[.10]*n+[.28],hspace=.015,wspace=.06)
    ax=fig.add_subplot(gs[0,0]);guide=fig.add_subplot(gs[:,1]);guide.axis('off')
    for i,p in enumerate(paths):
        es=np.asarray(p['es']);hits=np.asarray(p['hits'],int)
        if es.shape!=rank.shape or (hits<0).any() or (hits>=len(rank)).any():raise ValueError('GSEA ES and hit indices must align with supplied rank universe')
        c=colors[p['name']];ax.plot(rank,es,c=c,lw=1.5)
        peak=int(np.argmax(np.abs(es)));ax.scatter([rank[peak]],[es[peak]],s=15,c=c,edgecolors='white',lw=.4,zorder=4)
        hit=fig.add_subplot(gs[1+i,0],sharex=ax);hit.vlines(rank[hits],0,1,color=c,lw=.55);hit.set_ylim(0,1);hit.axis('off');hit.text(-.015,.5,str(i+1),transform=hit.transAxes,ha='right',va='center',fontsize=6.5,color=c)
        y=1-(i+.15)/n;guide.text(.01,y,str(i+1)+'. '+wrap_label(p['name'],26),transform=guide.transAxes,fontsize=7.3,fontweight='bold',color=c,va='top')
        lines=wrap_label(p['name'],26).count('\n')+1
        stats=f'NES {p["NES"]:.2f}  |  FDR {p["fdr"]:.3g}\n{len(hits)} ranked set members' if p.get('NES') is not None else f'{len(hits)} ranked set members'
        guide.annotate(stats,(.01,y),xytext=(0,-(lines*8.5+7)),xycoords='axes fraction',textcoords='offset points',fontsize=6.6,va='top')
    ax.axhline(0,c=GRID,lw=.6);ax.tick_params(labelbottom=False);ax.set_ylabel('Running enrichment score');ax.set_xlim(rank.min(),rank.max());ax.grid(axis='y',color=GRID,lw=.35)
    bottom=fig.add_subplot(gs[-1,0],sharex=ax);bottom.fill_between(rank,metric,0,where=metric>=0,color='#CA7354',alpha=.55,lw=0);bottom.fill_between(rank,metric,0,where=metric<0,color='#3B6F91',alpha=.55,lw=0);bottom.axhline(0,c=GRID,lw=.5);bottom.set(xlabel='Rank in the common supplied gene universe',ylabel='Rank metric')
    fig.suptitle(o.get('title','GSEA · pathways on a shared ranking'),x=.02,ha='left',fontsize=10,fontweight='bold')
    return fig,{'variant':'shared_ES_and_pathway_hit_tracks','shared_rank_universe':True,'ES_refit':False,'rank_metric_repeated':False,'pathways':[p['name'] for p in paths],'identity_colors':colors,'statistics':'supplied NES and FDR, no recomputation'}
