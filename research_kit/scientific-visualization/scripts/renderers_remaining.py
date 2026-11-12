"""Specialist views from supplied scientific channels; no implicit fitting."""
import numpy as np,pandas as pd,matplotlib as mpl,matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap
from design_system import *
from renderers_extra import axes

def bubble_panel(d,o):
    t=pd.DataFrame(d['table']);required={'pair','interaction','score'}
    if not required<=set(t):raise ValueError('Communication bubbles require pair, interaction and supplied score')
    if t.duplicated(['pair','interaction']).any():raise ValueError('Duplicate communication axes; select one method/contrast explicitly')
    rows=list(dict.fromkeys(t.interaction));cols=list(dict.fromkeys(t.pair))
    if len(rows)>30:raise ValueError('Paginate more than 30 interaction names')
    if not np.isfinite(t.score).all():raise ValueError('Finite scores required')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',max(.55,.030*len(rows)+.22))),layout='constrained')
    gs=fig.add_gridspec(1,2,width_ratios=[1,.24],wspace=.07);ax=fig.add_subplot(gs[0,0]);guide=fig.add_subplot(gs[0,1]);guide.axis('off');sizes=np.full(len(t),45.)
    if 'pvalue' in t:
        if not t.pvalue.between(0,1).all():raise ValueError('Invalid supplied interaction p-values')
        sizes=15+np.minimum(-np.log10(t.pvalue.clip(lower=1e-6)),6)*12
    sc=ax.scatter([cols.index(x) for x in t.pair],[rows.index(x) for x in t.interaction],c=t.score,s=sizes,cmap=LinearSegmentedColormap.from_list('score',PALETTES['purple-depth']),edgecolors='white',lw=.5)
    ax.set_xticks(range(len(cols)),[d.get('display_pairs',{}).get(x,wrap_label(x,20)) for x in cols],rotation=55,ha='right',fontsize=6.5);ax.set_yticks(range(len(rows)),[wrap_label(x,32) for x in rows]);ax.set_xlim(-.6,len(cols)-.4);ax.set_ylim(len(rows)-.4,-.6);ax.spines[:].set_visible(False);ax.grid(color=GRID,lw=.4);ax.set_axisbelow(True);ax.tick_params(length=0)
    fig.suptitle(o.get('title','Ligand–receptor evidence across cell pairs'),x=.02,ha='left',fontsize=10,fontweight='bold')
    cb=fig.colorbar(sc,cax=guide.inset_axes([.1,.08,.12,.58]));cb.set_label(wrap_label(d.get('score_label','Supplied communication score'),24),fontsize=7)
    if 'pvalue' in t:
        vals=[.05,.01,0]
        guide.legend(handles=[ax.scatter([],[],s=15+min(-np.log10(max(p,1e-6)),6)*12,facecolor='#BAA6CD',edgecolor='white',label=f'{p:g}' if p else 'Reported 0') for p in vals],title='Source p-value',loc='upper left',fontsize=6.5)
    return fig,{'rows':rows,'columns':cols,'pvalue_size_channel':'supplied' if 'pvalue' in t else 'absent; fixed dot area'}

def genescore_panel(d,o):
    xy=np.asarray(d['embedding']);values=np.asarray(d['scores']);names=d['score_names']
    if values.shape!=(len(xy),len(names)):raise ValueError('Per-cell score matrix/embedding mismatch')
    nr,nc=choose_grid(len(names),o.get('ncols'),o.get('nrows'));fig,aa=axes(o,.6*nr,nrows=nr,ncols=nc,squeeze=False)
    lo,hi=float(values.min()),float(values.max())
    for j,(ax,name) in enumerate(zip(aa.flat,names)):
        ix=np.argsort(values[:,j],kind='stable');sc=ax.scatter(xy[ix,0],xy[ix,1],c=values[ix,j],vmin=lo,vmax=hi,cmap=LinearSegmentedColormap.from_list('score',PALETTES['purple-depth']),s=4,lw=0);ax.set_title(wrap_label(name,24));ax.set_aspect('equal');ax.axis('off')
    for ax in aa.flat[len(names):]:ax.remove()
    fig.colorbar(sc,ax=list(aa.flat[:len(names)]),shrink=.5,label=d['unit']);return fig,{'score_fitting':'none; supplied per-cell values','shared_scale':[lo,hi]}

def rank_matrix_panel(d,o):
    m=d['matrix'];t=matrix_input(m['values'],m.get('rows'),m.get('columns')) if isinstance(m,dict) else matrix_input(m);a=t.to_numpy()
    if not np.isfinite(a).all() or (a<1).any():raise ValueError('Positive finite supplied ranks required, not a score vector')
    rows=list(map(str,t.index));cols=list(map(str,t.columns));fig,ax=axes({**o,'width':o.get('width','onehalf' if len(rows)<=8 else 'double')},max(.35,.045*len(rows)+.15));y=np.arange(len(rows));colors=identity_colors(o.setdefault('theme',{}),cols)
    for i in range(len(rows)):
        ax.plot(a[i],y[i]+.15*(np.arange(len(cols))-(len(cols)-1)/2),c='#C3CED5',lw=.8,zorder=0)
    for j,c in enumerate(cols):ax.scatter(a[:,j],y+.15*(j-(len(cols)-1)/2),s=25,c=colors[c],label=c,edgecolors='white',lw=.5)
    ax.set_yticks(y,[wrap_label(x,25) for x in rows]);ax.invert_yaxis();ax.set_xlabel('Supplied rank (1 = best)');ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(integer=True));ax.grid(axis='x',color=GRID,lw=.4);fig.legend(*ax.get_legend_handles_labels(),loc='outside lower center',ncols=min(3,len(cols)),fontsize=6.5);ax.set_title(o.get('title','Rank agreement across criteria'),loc='left');return fig,{'criteria':cols,'rows':rows,'aggregation':'none; no fabricated consensus score'}

def trajectory_pca_panel(d,o):
    pcs=np.asarray(d['pca']);time=np.asarray(d.get('time_ns',np.arange(len(pcs))));var=d.get('pca_variance');fig,ax=axes(o,.65)
    if pcs.ndim!=2 or pcs.shape[1]<2 or len(time)!=len(pcs):raise ValueError('Aligned trajectory PCA/time required')
    ax.plot(pcs[:,0],pcs[:,1],c='#C5CFD5',lw=.8,zorder=1)
    sc=ax.scatter(pcs[:,0],pcs[:,1],c=time,cmap=LinearSegmentedColormap.from_list('time',PALETTES['purple-depth']),s=28,edgecolors='white',lw=.5,zorder=3)
    for i,label in [(0,'Start'),(len(pcs)-1,'End')]:ax.annotate(label,pcs[i,:2],xytext=(5,4),textcoords='offset points',fontsize=7)
    ax.set(xlabel='PC1'+(f' ({100*var[0]:.1f}%)' if var is not None else ''),ylabel='PC2'+(f' ({100*var[1]:.1f}%)' if var is not None else ''));ax.set_title(o.get('title','Trajectory in principal-component space'),loc='left');fig.colorbar(sc,ax=ax,shrink=.6,label='Time (ns)' if 'time_ns' in d else 'Source frame index')
    return fig,{'coordinates':'supplied','order':'source temporal order','ellipse':'none; serially correlated frames are not independent sample groups'}

def stages_panel(d,o):
    stages=d['stages'];nr,nc=choose_grid(len(stages),o.get('ncols',2),o.get('nrows'));fig,aa=axes(o,.42*nr,nrows=nr,ncols=nc,squeeze=False,sharex=True,sharey=True)
    names=list(dict.fromkeys(c.get('color_id',c['label']) for stage in stages for c in stage['curves']));colors=identity_colors(o.setdefault('theme',{}),names)
    for ax,stage in zip(aa.flat,stages):
        for c in stage['curves']:
            x=np.asarray(c['x']);y=np.asarray(c['y'])
            if x.shape!=y.shape:raise ValueError('Stage curve axes mismatch')
            ax.plot(x,y,color=colors[c.get('color_id',c['label'])],ls=c.get('linestyle','-'),lw=1.1)
        for line in d.get('reference_lines',[]):ax.axhline(line['value'],color=MUTED,lw=.7,ls='--')
        ax.set(title=stage['label'],xlabel=d['xlabel'],ylabel=d['ylabel']);ax.grid(axis='y',color=GRID,lw=.4)
    for ax in aa.flat[len(stages):]:ax.remove()
    fig.legend(handles=[Line2D([],[],c=colors[n],label=n) for n in names],loc='outside lower center',ncols=min(4,len(names)),frameon=False)
    fig.suptitle(o.get('title','Aligned source stages'),x=.01,ha='left',fontweight='bold');return fig,{'stages':[s['label'] for s in stages],'shared_axes':True,'color_map':colors,'references':d.get('reference_lines',[])}

def barcode_panel(d,o):
    m=d['matrix'];t=matrix_input(m['values'],m.get('rows'),m.get('columns'));a=t.to_numpy()
    if not np.isin(a,[0,1]).all():raise ValueError('Interaction barcode requires actual binary presence values')
    fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',max(.5,.029*len(t)+.25))),layout='constrained');gs=fig.add_gridspec(1,2,width_ratios=[1,.24],wspace=.08);ax=fig.add_subplot(gs[0]);side=fig.add_subplot(gs[1],sharey=ax)
    ax.imshow(a,cmap=mpl.colors.ListedColormap(['#F0F3F5','#347F79']),vmin=0,vmax=1,aspect='auto',interpolation='none');ax.set_yticks(range(len(t)),[wrap_label(x,27) for x in t.index],fontsize=7);ax.set_xticks(range(t.shape[1]),t.columns,rotation=45,ha='right');ax.set_xlabel('Source time (ns)');ax.tick_params(length=0);ax.spines[:].set_visible(False)
    ax.set_xticks(np.arange(t.shape[1]+1)-.5,minor=True);ax.set_yticks(np.arange(len(t)+1)-.5,minor=True);ax.grid(which='minor',color='white',lw=.55);ax.tick_params(which='minor',length=0)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color='#347F79',label='Present'),Patch(color='#F0F3F5',ec='#CAD4DA',label='Absent')],loc='outside lower center',ncols=2,fontsize=7)
    side.barh(range(len(t)),a.mean(axis=1),color='#347F79',height=.55);side.set_xlim(0,1);side.xaxis.set_major_formatter(mpl.ticker.PercentFormatter(1));side.set_xlabel('Occupancy');side.tick_params(axis='y',labelleft=False,length=0);side.spines['left'].set_visible(False);fig.suptitle(wrap_label(o.get('title','Geometric interaction timeline & occupancy'),70),x=.01,ha='left',fontweight='bold')
    return fig,{'definition':d.get('definition'),'frames':a.shape[1],'presence_values':'supplied binary','occupancy_denominator':a.shape[1],'equilibrium_claim':False}

def frontier_gap_panel(d,o):
    systems=d['systems'];n=len(systems);fig,ax=axes({**o,'width':o.get('width','single' if n==1 else 'onehalf')},max(.65,.17*n+.3))
    endpoints=[]
    for i,s in enumerate(systems):
        occupied=np.asarray(s['occupied_eV'],float);virtual=np.asarray(s['virtual_eV'],float)
        if not occupied.size or not virtual.size or not np.isfinite(np.r_[occupied,virtual]).all():raise ValueError('Finite occupied and virtual orbital energies are both required')
        homo,lumo=float(occupied.max()),float(virtual.min());gap=lumo-homo
        if gap<0:raise ValueError('Declared occupied/virtual frontier ordering is inconsistent')
        ax.plot([homo,lumo],[i,i],c='#AABAC4',lw=2,zorder=0);ax.scatter([homo,lumo],[i,i],c=['#3B6F91','#CA7354'],s=42,edgecolors='white',lw=.7,zorder=3)
        ax.annotate(f'HOMO\n{homo:.2f}',(homo,i),xytext=(0,10),textcoords='offset points',ha='center',fontsize=7);ax.annotate(f'LUMO\n{lumo:.2f}',(lumo,i),xytext=(0,10),textcoords='offset points',ha='center',fontsize=7)
        ax.text((homo+lumo)/2,i-.20,f'ΔE = {gap:.2f} eV',ha='center',va='top',fontsize=8,fontweight='bold');endpoints.append({'label':s['label'],'HOMO_eV':homo,'LUMO_eV':lumo,'gap_eV':gap})
    ax.set_yticks(range(n),[wrap_label(s['label'],20) for s in systems]);ax.set_ylim(-.6,n-.25);ax.set_xlabel('Supplied orbital energy (eV)');ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',color=GRID,lw=.4);ax.margins(x=.2);ax.set_title(o.get('title','Frontier-orbital separation'),loc='left');return fig,{'frontiers':endpoints,'gap':'supplied orbital endpoint difference, not an experimental optical gap'}

def gene_profile_panels(d,o):
    curves=d['curves'];nr,nc=choose_grid(len(curves),o.get('ncols'),o.get('nrows'));fig,aa=axes(o,.38*nr,nrows=nr,ncols=nc,squeeze=False,sharex=True,sharey=True);colors=identity_colors(o.setdefault('theme',{}),[c['label'] for c in curves])
    for ax,c in zip(aa.flat,curves):
        x=np.asarray(c['x'],float);y=np.asarray(c['y'],float)
        if x.shape!=y.shape or not np.isfinite(np.r_[x,y]).all():raise ValueError('Finite aligned ordered gene observations required')
        ax.scatter(x,y,c=colors[c['label']],s=6,alpha=.55,lw=0)
        if 'trend' in c:
            trend=c['trend'];ax.plot(trend['x'],trend['y'],c=colors[c['label']],lw=1.3)
        ax.set_title(wrap_label(c['label'],25),loc='left');ax.set(xlabel=d['xlabel'],ylabel=d['ylabel']);ax.grid(axis='y',color=GRID,lw=.4)
    for ax in aa.flat[len(curves):]:ax.remove()
    fig.suptitle(o.get('title','Gene profiles along supplied ordering'),x=.01,ha='left',fontweight='bold');return fig,{'genes':[c['label'] for c in curves],'trend_fitting':'none; only optional supplied trend channels','observations_connected':False,'shared_axes':True,'nrows':nr,'ncols':nc}

__all__=['bubble_panel','genescore_panel','rank_matrix_panel','trajectory_pca_panel','stages_panel','barcode_panel','frontier_gap_panel','gene_profile_panels']
