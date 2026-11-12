"""Annotated embeddings and matched-stage views of supplied coordinates only."""
import hashlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
from design_system import *


def _input(d, o):
    xy = np.asarray(d['embedding'], float)
    groups = np.asarray(d['groups'], str)
    if len(groups)<1 or xy.shape != (len(groups), 2) or not np.isfinite(xy).all():
        raise ValueError('Finite, aligned two-dimensional stored coordinates required')
    order = list(map(str, d.get('group_order', dict.fromkeys(groups))))
    if set(order) != set(groups) or len(set(order)) != len(order):
        raise ValueError('group_order must name each observed identity exactly once')
    ids = list(map(str, d.get('sample_ids', range(len(xy)))))
    if len(ids) != len(xy) or len(set(ids)) != len(ids):
        raise ValueError('Unique sample_ids must align with coordinates')
    colors = identity_colors(o.setdefault('theme', {'palette': o.get('palette', 'muted')}), order)
    return xy, groups, order, ids, colors


def _frame(ax, xy, o):
    span = np.maximum(np.ptp(xy, axis=0), 1.e-6)
    pad = float(o.get('coordinate_padding', .14))
    ax.set_xlim(xy[:, 0].min()-span[0]*pad, xy[:, 0].max()+span[0]*pad)
    ax.set_ylim(xy[:, 1].min()-span[1]*pad, xy[:, 1].max()+span[1]*pad)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([]); ax.set_yticks([]); ax.spines[:].set_visible(False)
    # Coordinate arrows carry no invented physical scale or explained variance.
    if o.get('axis_arrows', True):
        for target in [(0.19, .055), (.055, .19)]:
            ax.annotate('', target, (.055, .055), xycoords='axes fraction',
                        arrowprops={'arrowstyle':'->', 'lw':.7, 'color':MUTED})
        coordinate = o.get('coordinate_type', 'UMAP')
        ax.text(.125, .007, coordinate+' 1', transform=ax.transAxes, fontsize=6.5, ha='center', color=MUTED)
        ax.text(.008, .125, coordinate+' 2', transform=ax.transAxes, fontsize=6.5, va='center', rotation=90, color=MUTED)


def _points(ax, xy, groups, order, colors, o, highlight=None):
    default_size=np.clip(16000/max(len(xy),1),2.5,9)*WIDTH_MM[o.get('width','double')]/183
    size = float(o.get('point_size', default_size))
    if highlight is not None:
        ax.scatter(*xy.T, s=size*.65, c='#E3E8EB', lw=0, alpha=.65, zorder=1)
    # Interleave identities in a fixed display order; do not privilege last group.
    ix = np.random.default_rng(0).permutation(len(xy))
    if highlight is None:
        ax.scatter(*xy[ix].T, s=size, c=[colors[g] for g in groups[ix]],
                   alpha=float(o.get('point_alpha', .86)), linewidths=0, zorder=2)
    else:
        m=groups == highlight
        ax.scatter(*xy[m].T, s=size, c=colors[highlight], alpha=.94, lw=0, zorder=3)


def _labels(fig, ax, xy, groups, order, colors, o):
    """Place readable labels in nearby whitespace without moving observations."""
    fig.canvas.draw(); renderer = fig.canvas.get_renderer()
    points = ax.transData.transform(xy)
    bounds = ax.get_window_extent(renderer).padded(-3)
    accepted = []; records = []
    counts = {g:int(sum(groups == g)) for g in order}
    offsets = o.get('label_offsets', {})
    # Small identities are placed first; labels must not conceal their few points.
    for g in sorted(order, key=lambda g:counts[g]):
        sub = xy[groups == g]
        center = np.median(sub, axis=0)
        anchor = sub[np.argmin(np.sum((sub-center)**2, axis=1))]
        anchor_px = ax.transData.transform(anchor)
        label = wrap_label(o.get('display_labels', {}).get(g, g), int(o.get('label_wrap', 20)))
        if o.get('label_counts', True): label += '\n'+f'n = {counts[g]:,}'
        probe = ax.text(*anchor, label, fontsize=o.get('label_size', 8), ha='center', va='center', alpha=0)
        bb = probe.get_window_extent(renderer); probe.remove()
        w,h = bb.width+8,bb.height+6
        candidates = [np.asarray(offsets[g],float)*fig.dpi/72] if g in offsets else [
            np.array([np.cos(a), np.sin(a)])*r*fig.dpi/72
            for r in (26,42,60,80,105) for a in np.linspace(0,2*np.pi,16,endpoint=False)]
        best=None
        for off in candidates:
            at=anchor_px+off
            box=Bbox.from_bounds(at[0]-w/2, at[1]-h/2,w,h)
            overflow=max(0,bounds.x0-box.x0)+max(0,box.x1-bounds.x1)+max(0,bounds.y0-box.y0)+max(0,box.y1-bounds.y1)
            collisions=sum(box.overlaps(old.padded(3)) for old in accepted)
            inside=((points[:,0]>=box.x0)&(points[:,0]<=box.x1)&(points[:,1]>=box.y0)&(points[:,1]<=box.y1)).sum()
            score=overflow*1000+collisions*100000+inside*35+np.linalg.norm(off)*.15
            if best is None or score<best[0]:best=(score,at,box)
        _,at,box=best;accepted.append(box)
        target=ax.transData.inverted().transform(at)
        annotation=ax.annotate(label, anchor, xytext=target, ha='center', va='center',
                    fontsize=o.get('label_size',8), color=INK, zorder=6,
                    path_effects=[pe.withStroke(linewidth=2.6,foreground='white')],
                    arrowprops={'arrowstyle':'-', 'color':colors[g], 'lw':.7,
                                'shrinkA':4,'shrinkB':4,'connectionstyle':'arc3,rad=0'})
        annotation.set_in_layout(False)
        records.append({'identity':g,'n':counts[g],'anchor':anchor.tolist(),'label_at':target.tolist()})
    return records


def embedding_atlas(d, o, kind='umap_clusters'):
    xy,groups,order,ids,colors=_input(d,o)
    variant=o.get('variant','atlas')
    meta={'embedding_refit':False,'coordinate_source':'supplied','point_order':'fixed display permutation, coordinates unchanged',
          'n_observations':len(xy),'identity_counts':{g:int(sum(groups==g)) for g in order},
          'identity_colors':colors,'coordinate_sha256':hashlib.sha256(xy.tobytes()).hexdigest(),'variant':variant}
    indexed=variant=='indexed' or (variant=='atlas' and o.get('label_style','auto')=='auto' and WIDTH_MM[o.get('width','double')]<105 and o.get('show_labels',True))
    if indexed:
        nr=int(np.ceil(len(order)/2));fig=plt.figure(figsize=journal_size(o.get('width','single'),o.get('aspect',1.12+.11*nr)),layout='constrained');gs=fig.add_gridspec(2,1,height_ratios=[1,.11*nr],hspace=.01);ax=fig.add_subplot(gs[0]);key=fig.add_subplot(gs[1]);key.axis('off')
        _points(ax,xy,groups,order,colors,o);_frame(ax,xy,o)
        for i,g in enumerate(order):
            sub=xy[groups==g];center=np.median(sub,axis=0);p=sub[np.argmin(np.sum((sub-center)**2,axis=1))]
            ax.annotate(str(i+1),p,xytext=(8,4) if len(sub)<40 else (0,0),textcoords='offset points',ha='center',va='center',fontsize=8,fontweight='bold',color=INK,path_effects=[pe.withStroke(linewidth=2.5,foreground='white')])
            x=(i%2)/2;y=1-(i//2+.15)/nr
            key.text(x+.01,y,str(i+1),transform=key.transAxes,color=colors[g],fontsize=8,fontweight='bold',va='top')
            label=wrap_label(g,20)+'\n'+f'n = {len(sub):,}'
            key.text(x+.06,y,label,transform=key.transAxes,fontsize=6.8,va='top')
        fig.suptitle(o.get('title','Annotated cell atlas'),x=.02,ha='left',fontsize=10,fontweight='bold');meta.update(variant='indexed_atlas',index_to_identity={str(i+1):g for i,g in enumerate(order)})
        return fig,meta
    if variant in ('highlight','facets') or kind in ('dim_facet','dim_highlight','onevsrest_grid'):
        selected=list(o.get('identities',order))
        if not selected or any(g not in order for g in selected):raise ValueError('Select observed identities')
        nr,nc=choose_grid(len(selected),o.get('ncols'),o.get('nrows'))
        aspect=o.get('aspect', max(.40, nr/nc*.90+.10))
        fig,axes=plt.subplots(nr,nc,figsize=journal_size(o.get('width','double'),aspect),
                              layout='constrained',squeeze=False,sharex=True,sharey=True)
        for ax,g in zip(axes.flat,selected):
            _points(ax,xy,groups,order,colors,{**o,'point_size':o.get('point_size',2.4)},highlight=g);_frame(ax,xy,{**o,'axis_arrows':False})
            n=meta['identity_counts'][g]
            ax.set_title(wrap_label(o.get('display_labels',{}).get(g,g),21),loc='left',fontsize=8.2,color=colors[g])
            ax.text(.99,.99,f'{n:,}  |  {n/len(xy):.1%}',transform=ax.transAxes,ha='right',va='top',fontsize=6.5,color=MUTED)
        for ax in axes.flat[len(selected):]:ax.remove()
        fig.suptitle(o.get('title','Cell identities · matched-coordinate highlights'),x=.02,ha='left',fontsize=10)
        meta.update(nrows=nr,ncols=nc,shared_limits=True,highlight_context='all supplied observations')
        return fig,meta
    profile=variant=='profile'
    if variant not in ('atlas','profile','classic'):raise ValueError('Embedding variants: atlas, indexed, profile, highlight, classic')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.76)),layout='constrained')
    if profile:
        gs=fig.add_gridspec(1,2,width_ratios=[1,.52],wspace=.10)
        ax=fig.add_subplot(gs[0,0]);counts_ax=fig.add_subplot(gs[0,1])
        counts=np.array([meta['identity_counts'][g] for g in order]);y=np.arange(len(order))
        counts_ax.barh(y,counts,color=[colors[g] for g in order],height=.46)
        for i,n in enumerate(counts):counts_ax.text(n+counts.max()*.025,i,f'{n:,}  ({n/len(xy):.1%})',va='center',fontsize=6.5)
        counts_ax.set_yticks(y,[wrap_label(g,19) for g in order],fontsize=7)
        counts_ax.set_xlim(0,counts.max()*1.44);counts_ax.invert_yaxis();counts_ax.set_xlabel('Observed cells')
        counts_ax.set_title('Identity abundance',loc='left',fontsize=9);counts_ax.spines[:].set_visible(False)
        counts_ax.tick_params(axis='y',length=0);counts_ax.grid(axis='x',lw=.4,color=GRID)
    else:ax=fig.add_subplot(111)
    _points(ax,xy,groups,order,colors,o);_frame(ax,xy,o)
    title=o.get('title','Annotated cell atlas')
    fig.suptitle(title,x=.02,ha='left',fontsize=11,fontweight='bold')
    if variant=='classic':
        ax.legend(handles=[Line2D([],[],marker='o',ls='',color=colors[g],label=wrap_label(g,20)) for g in order],loc='upper left',bbox_to_anchor=(1,1))
    elif o.get('show_labels',True):meta['labels']=_labels(fig,ax,xy,groups,order,colors,o)
    return fig,meta


def matched_embeddings(d,o):
    stages=d.get('stages',[])
    if not stages:raise ValueError('Named embedding stages required')
    for stage in stages:
        if 'sample_ids' not in stage:raise ValueError('Every stage requires literal sample_ids')
        _input({**stage,'group_order':d['group_order']},o)
    if any(not np.array_equal(s['sample_ids'],stages[0]['sample_ids']) for s in stages[1:]):raise ValueError('Stage sample ID order differs; align explicitly upstream')
    exact=all(np.array_equal(s['embedding'],stages[0]['embedding']) and np.array_equal(s['groups'],stages[0]['groups']) for s in stages[1:])
    view=o.get('variant','auto')
    if exact and view!='stages':
        source={**stages[0],'group_order':d['group_order']}
        fig,meta=embedding_atlas(source,{**o,'variant':'atlas' if view=='auto' else view,'title':o.get('title','Stored cell atlas')})
        meta.update(stages=[s['label'] for s in stages],identical_coordinates=True,
                    duplicate_panels_collapsed=True,identity_test_only=d.get('identity_test_only',False),mixing_is_QC_pass=False)
        return fig,meta
    nr,nc=choose_grid(len(stages),o.get('ncols'),o.get('nrows'))
    fig,axes=plt.subplots(nr,nc,figsize=journal_size(o.get('width','double'),o.get('aspect',.53*nr)),
                         layout='constrained',squeeze=False,sharex=True,sharey=True)
    allxy=np.concatenate([s['embedding'] for s in stages]);colors=None
    for ax,s in zip(axes.flat,stages):
        xy,g,order,ids,colors=_input({**s,'group_order':d['group_order']},o)
        _points(ax,xy,g,order,colors,o);_frame(ax,allxy,o)
        ax.set_title(wrap_label(s['label'],30),loc='left',fontsize=9)
    for ax in axes.flat[len(stages):]:ax.remove()
    fig.legend(handles=[Line2D([],[],marker='o',ls='',color=colors[g],label=wrap_label(g,20)) for g in d['group_order']],
               loc='outside lower center',ncols=min(4,len(colors)),fontsize=7)
    return fig,{'stages':[s['label'] for s in stages],'identical_coordinates':exact,'shared_limits':True,
                'duplicate_panels_collapsed':False,'mixing_is_QC_pass':False}
