"""Domain-specific result views, adaptive to supplied axes and panel counts."""
import math
import numpy as np,pandas as pd,matplotlib as mpl,matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch,Rectangle,PathPatch
from matplotlib.path import Path
from design_system import *
from renderers_extra import axes,line_panel,scatter_panel,bars_panel,proportion_panel

def qc_panel(d,o,kind):
    if kind=='per_base_quality':
        q=d.get('per_base_quality',d);fig,ax=axes(o,.55)
        if 'curves' in q:
            plt.close(fig)
            fig,meta=line_panel(q,o)
            meta.update(band_semantics='source means only; no invented quantiles',threshold_is_configurable=True)
            return fig,meta
        x=np.array(q['x'])
        lo,hi=('q10','q90') if 'q10' in q else ('min','max')
        ax.fill_between(x,q[lo],q[hi],color='#BFD1DB',alpha=.45,label='10–90%' if lo=='q10' else 'Supplied min–max',lw=0)
        ax.fill_between(x,q['q25'],q['q75'],color='#59988A',alpha=.5,label='Interquartile range',lw=0);ax.plot(x,q['median'],c='#286B60',lw=1.4,label='Median')
        ref=float(o.get('quality_reference',d.get('thresholds',{}).get('quality_reference',20)));ax.axhline(ref,color='#BC785E',ls='--',lw=.9,label=f'Reference Q{ref:g}')
        ax.set(xlabel='Sequencing cycle',ylabel='Phred quality',title=o.get('title','Per-cycle quality distribution'));ax.legend(loc='lower left',ncol=2);ax.set_ylim(bottom=0);return fig,{'reference':ref,'band_semantics':lo+'–'+hi,'threshold_is_configurable':True}
    if kind=='dup_insert':
        fp=d['fastp'];hist=np.array(fp['insert_size']['histogram']);dup=np.array(fp['duplication']['histogram']);fig,aa=axes(o,.48,ncols=2)
        if hist.sum()>0:
            aa[0].plot(np.arange(len(hist)),hist,c='#3B6F91');aa[0].fill_between(np.arange(len(hist)),hist,color='#3B6F91',alpha=.15);aa[0].set(xlabel='Insert size (bp)',ylabel='Reported pair count',title='Insert-size distribution');aa[0].set_ylim(bottom=0)
        else:
            aa[0].axis('off');aa[0].set_title('Insert-size availability',loc='left');aa[0].text(.05,.65,'No estimable insert-size bins',transform=aa[0].transAxes,fontsize=9,fontweight='bold');aa[0].text(.05,.42,'All source histogram counts are zero.\nUnknown pairs: '+str(fp['insert_size'].get('unknown','not reported')),transform=aa[0].transAxes,fontsize=8,color=MUTED)
        aa[1].bar(np.arange(1,len(dup)+1),dup,color='#4C9685',width=.75);aa[1].set(xlabel='Duplication level',ylabel='Reported count',title='Duplication profile');aa[1].set_yscale('symlog',linthresh=1)
        return fig,{'normalization':'none; actual source counts','insert_histogram_status':'NONZERO_SOURCE_BINS' if hist.sum()>0 else 'SOURCE_HAS_NO_ESTIMABLE_BINS','unknown_insert_size':fp['insert_size'].get('unknown')}
    if kind=='qc_triplet':
        qc=d['qc'];groups=np.array(d['groups']);order=d['group_order'];fig,aa=axes(o,o.get('aspect',.88),nrows=3,sharey=True)
        specs=[('n_counts','Counts per cell'),('n_genes','Detected genes per cell'),('percent_mito','Mitochondrial fraction')]
        colors=identity_colors(o.setdefault('theme',{}),order)
        for ax,(key,label) in zip(aa,specs):
            for i,g in enumerate(order):
                v=np.asarray(qc[key])[groups==g];offset=((np.arange(len(v))*.61803398875)%1-.5)*.27;ax.scatter(v,i+offset,s=1.5,c=colors[g],alpha=.23,lw=0)
                q=np.quantile(v,[.25,.5,.75]);ax.plot(q[[0,2]],[i,i],c=colors[g],lw=4,solid_capstyle='butt');ax.scatter([q[1]],[i],marker='|',s=25,c=INK,zorder=3)
            ax.set(xlabel=label,yticks=range(len(order)),yticklabels=[wrap_label(x,19) for x in order]);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0,labelsize=6.8);ax.tick_params(axis='x',labelsize=7);ax.grid(axis='x',color=GRID,lw=.4)
            if key!='percent_mito':
                ax.set_xscale('log');ax.xaxis.set_minor_formatter(mpl.ticker.NullFormatter())
        return fig,{'raw_points':True,'summary':'median and IQR','independent_unit':'cell for descriptive QC only'}
    if kind=='rle_plot':
        m=d.get('rle',d);v=np.array(m['values']);labels=m['columns'];groups=m.get('groups',labels);colors=identity_colors(o.setdefault('theme',{}),list(dict.fromkeys(groups)))
        if v.shape[1]!=len(labels):raise ValueError('RLE sample axes mismatch')
        fig,ax=axes(o,.65)
        q=np.quantile(v,[.05,.25,.5,.75,.95],axis=0)
        for i,lab in enumerate(labels):
            ax.plot([i,i],q[[0,4],i],c=colors[groups[i]],lw=.8);ax.plot([i,i],q[[1,3],i],c=colors[groups[i]],lw=7,solid_capstyle='butt');ax.scatter([i],[q[2,i]],c='white',marker='_',s=28,zorder=3)
        display=m.get('display_columns',{})
        ax.axhline(0,c=MUTED,lw=.8,ls='--');ax.set_xticks(range(len(labels)),[wrap_label(display.get(x,x),14) for x in labels],rotation=55,ha='right',fontsize=6.5);ax.set_ylabel('Log expression − feature median');ax.legend(handles=[Patch(color=colors[g],label=g) for g in dict.fromkeys(groups)],loc='upper left',bbox_to_anchor=(1.01,1));ax.set_title(o.get('title','Relative log expression · robust ranges'),loc='left')
        return fig,{'display':'median, IQR, 5–95% ranges; no confidence intervals','sample_order':labels}
    if kind=='norm_density':
        stages=d['stages'];fig,aa=axes(o,.48,ncols=len(stages),sharex=True,sharey=True,squeeze=False)
        allnames=[c.get('color_id',c['label']) for stage in stages for c in stage['curves']];colors=identity_colors(o.setdefault('theme',{}),allnames)
        for ax,stage in zip(aa.flat,stages):
            for c in stage['curves']:ax.plot(c['x'],c['y'],color=colors[c.get('color_id',c['label'])],lw=1,alpha=.8,label=c['label'])
            ax.set_title(stage['label'],loc='left');ax.set_xlabel(d['xlabel']);ax.set_ylabel(d['ylabel'])
        aa.flat[-1].legend(loc='upper left',bbox_to_anchor=(1.01,1));return fig,{'stages':[s['label'] for s in stages],'shared_axes':True,'source_curves':'supplied'}
    if kind=='missing_pattern':
        m=d['matrix'];mat=matrix_input(m['values'],m.get('rows'),m.get('columns')) if isinstance(m,dict) else matrix_input(m)
        missing=mat.isna().to_numpy();rates=missing.mean(axis=1);order=np.argsort(-rates,kind='stable') if o.get('sort_missing',True) else np.arange(len(mat))
        nr,nc=missing.shape
        if nr>80:raise ValueError('More than 80 named missingness rows: select or paginate explicitly')
        fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',max(.55,.25+.023*nr))),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[.18,1],width_ratios=[1,.24],hspace=.03,wspace=.04);ax=fig.add_subplot(gs[1,0]);top=fig.add_subplot(gs[0,0],sharex=ax);side=fig.add_subplot(gs[1,1],sharey=ax)
        ax.imshow(missing[order],cmap=mpl.colors.ListedColormap(['#EDF2F4','#3B6F91']),vmin=0,vmax=1,aspect='auto',interpolation='none');ax.set_yticks(range(nr),[wrap_label(mat.index[i],25) for i in order],fontsize=6.6);ax.set_xticks(range(nc),[wrap_label(s,16) for s in mat.columns],rotation=90 if nc>8 else 45,ha='center' if nc>8 else 'right',fontsize=6.5);ax.tick_params(length=0);ax.spines[:].set_visible(False)
        top.bar(range(nc),missing.mean(axis=0)*100,color='#9EB7C7',width=.72);top.set_ylabel('Missing (%)',fontsize=7);top.tick_params(labelbottom=False,labelsize=6.5);top.spines[['top','right']].set_visible(False)
        side.barh(range(nr),rates[order]*100,color='#3B6F91',height=.7);side.set_xlabel('Missing (%)');side.tick_params(labelleft=False,length=0);side.spines[['top','right','left']].set_visible(False);side.set_xlim(0,max(10,rates.max()*115));ax.set_ylim(nr-.5,-.5)
        ref=o.get('missing_reference',o.get('drop_thr',d.get('thresholds',{}).get('missing_reference')))
        if ref is not None:
            ref=float(ref)
            if not 0<=ref<=1:raise ValueError('Missing reference must be a fraction in [0,1]')
            side.axvline(ref*100,c='#CA7354',ls='--',lw=.8);side.set_xlim(0,max(side.get_xlim()[1],ref*110));side.set_title(f'Ref. {ref:.0%}\n(configurable)',loc='left',fontsize=7)
        fig.legend(handles=[Patch(color='#EDF2F4',label='Observed (including zero)'),Patch(color='#3B6F91',label='Missing')],loc='outside lower center',ncols=2,fontsize=7);fig.suptitle(o.get('title','Observed data & missingness'),x=.01,ha='left',fontsize=11,fontweight='bold')
        return fig,{'zero_is_observed':True,'row_order':[str(mat.index[i]) for i in order],'column_order':list(map(str,mat.columns)),'missing_rates_by_row':{str(mat.index[i]):float(rates[i]) for i in range(nr)},'missing_reference':ref,'threshold_is_configurable':True,'samples_removed':False}
    if kind=='batch_umap':
        from renderers import draw_embedding
        stages=d.get('stages')
        if not stages:raise ValueError('Provide named before/after embeddings with aligned sample IDs')
        if any('sample_ids' not in stage for stage in stages):raise ValueError('Every embedding stage requires exact sample_ids')
        if any(stage['sample_ids']!=stages[0]['sample_ids'] for stage in stages[1:]):raise ValueError('Before/after identity order differs; align explicitly upstream')
        nr,nc=choose_grid(len(stages),o.get('ncols',2),o.get('nrows'));fig,aa=axes(o,.48*nr,nrows=nr,ncols=nc,squeeze=False,sharex=True,sharey=True);groups=d['group_order'];colors=identity_colors(o.setdefault('theme',{}),groups)
        for ax,stage in zip(aa.flat,stages):
            xy=np.array(stage['embedding']);g=np.array(stage['groups']);
            if len(xy)!=len(g):raise ValueError('Stage embedding/group mismatch')
            for k in groups:
                z=g==k;ax.scatter(xy[z,0],xy[z,1],s=3,c=colors[k],alpha=.6,lw=0,label=k)
            ax.set_title(stage['label'],loc='left');ax.set(xlabel=d.get('x_label','Embedding 1'),ylabel=d.get('y_label','Embedding 2'));ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([])
        for ax in aa.flat[len(stages):]:ax.remove()
        aa.flat[min(len(stages),nr*nc)-1].legend(loc='upper left',bbox_to_anchor=(1,1));return fig,{'stages':[s['label'] for s in stages],'mixing_is_QC_pass':False}
    raise NotImplementedError(kind)

def small_cell_panel(d,o,kind):
    ex=np.array(d['expression']);groups=np.array(d['groups']);order=d['group_order'];genes=d['markers']
    if kind in ('marker_heatmap','genescore'):
        from renderers import draw_heatmap
        mat=pd.DataFrame(np.asarray(d['dot_mean']).T,index=genes,columns=order)
        return draw_heatmap({'matrix':mat},{**o,'cluster':True,'title':o.get('title','Marker expression across cell identities'),'cmap':'teal-depth','color_label':'Mean supplied log1p expression'})
    if kind=='expr_density':
        gene=o.get('gene',genes[0]);curves=[]
        for g in order:
            den=d['densities'][g][gene]
            if den:curves.append({'label':g,**den})
        return line_panel({'curves':curves,'xlabel':gene+' · log1p expression','ylabel':'Supplied density','title':'Expression distributions by cell identity'},o)
    if kind=='butterfly':
        fraction=np.array(d['dot_fraction']);mean=np.array(d['dot_mean']);j=order.index(o.get('group',order[0]));ref=(mean.sum(axis=0)-mean[j])/(len(order)-1);ix=np.argsort(mean[j]-ref)[-min(12,len(genes)):]
        colors=identity_colors(o.setdefault('theme',{}),order)
        fig,ax=axes({**o,'width':o.get('width','onehalf')},max(.5,.037*len(ix)+.15));y=np.arange(len(ix));ax.barh(y,mean[j,ix],color=colors[order[j]],height=.58,label=order[j]);ax.barh(y,-ref[ix],color='#B7C4CC',height=.58,label='Other identities\n(equal-weight means)');ax.set_yticks(y,[genes[k] for k in ix]);ax.axvline(0,c=INK,lw=.8);ax.set_xlabel('Mirrored mean log1p expression');fig.legend(*ax.get_legend_handles_labels(),loc='outside lower center',ncols=2,fontsize=6.8);ax.set_title(o.get('title',order[j]+' · marker expression'),loc='left',fontsize=9);return fig,{'quantity':'descriptive identity means, no DE p-values','reference':'equal-weight identity means, explicitly not pooled cells','identity_colors':colors}
    if kind=='proportion_dots':
        vals=np.array(d['cluster_counts']);frac=vals/vals.sum();fig,ax=axes({**o,'width':o.get('width','onehalf')},.66);y=np.arange(len(order));colors=identity_colors(o.setdefault('theme',{}),order)
        if o.get('variant','count_bars')=='lollipop':
            ax.hlines(y,0,frac,color='#D5E1E7',lw=2);ax.scatter(frac,y,s=30,c=[colors[g] for g in order],edgecolors='white',lw=.5)
        else:
            ax.barh(y,frac,height=.56,color=[colors[g] for g in order],edgecolor='white',lw=.4)
            for i,(n,f) in enumerate(zip(vals,frac)):ax.text(f+frac.max()*.025,i,f'{n:,} | {f:.1%}',va='center',fontsize=6.8)
            ax.set_xlim(0,frac.max()*1.48)
        ax.set_yticks(y,[wrap_label(x,25) for x in order]);ax.set_xlabel('Fraction of observed cells');ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter(1));ax.invert_yaxis();ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
        return fig,{'denominator':int(vals.sum()),'variant':o.get('variant','count_bars'),'unit':'single donor cell composition, no between-donor CI','identity_colors':colors}
    if kind=='feature_overlay':
        xy=np.array(d['embedding']);features=o.get('features',genes[:2])
        if len(features)!=2:raise ValueError('Two nonnegative feature channels required')
        a=ex[:,genes.index(features[0])];b=ex[:,genes.index(features[1])];maximum=max(a.max(),b.max(),1e-12);gamma=float(o.get('color_gamma',.6))
        if (a<0).any() or (b<0).any() or not np.isfinite(np.r_[a,b]).all():raise ValueError('Finite nonnegative expression layers required; scaled negative values are not supported')
        def rgb(a,b):
            a=np.asarray(a)[...,None]**gamma;b=np.asarray(b)[...,None]**gamma
            return (1-a)*(1-b)*np.array([.965,.973,.978])+a*(1-b)*np.array([.19,.47,.67])+(1-a)*b*np.array([.79,.39,.34])+a*b*np.array([.47,.28,.56])
        mix=rgb(a/maximum,b/maximum);fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.65)),layout='constrained');gs=fig.add_gridspec(1,2,width_ratios=[1,.25]);ax=fig.add_subplot(gs[0]);key=fig.add_subplot(gs[1]);ix=np.argsort(a+b,kind='stable');ax.scatter(xy[ix,0],xy[ix,1],c=mix[ix],s=4,lw=0);ax.set(xlabel='UMAP 1',ylabel='UMAP 2',title=' × '.join(features));ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([]);ax.spines[:].set_visible(False)
        v=np.linspace(0,1,64);aa,bb=np.meshgrid(v,v);key.imshow(rgb(aa,bb),origin='lower',extent=[0,maximum,0,maximum],aspect='equal');key.set(xlabel=features[0],ylabel=features[1]);key.set_xticks([0,maximum]);key.set_yticks([0,maximum]);key.set_title('Log1p expression',fontsize=8)
        return fig,{'features':features,'scaling':'common supplied-channel max','color_gamma':gamma,'range':[0,maximum],'overlap_color':'bilinear white-ground bivariate mix, not a third biological class','bivariate_key':'exact same color transform as points; no hidden point alpha'}
    raise NotImplementedError(kind)

def surface_panel(d,o,kind):
    if d.get('sample_path'):
        from renderers_extra import scatter_panel
        fig,meta=scatter_panel(d,o);ax=fig.axes[0];ax.plot(d['x'],d['y'],lw=.7,c='#AFBAC3',zorder=0);meta.update(variant='actual sampled path, not an interpolated surface',interpolation=False)
        return fig,meta
    x=np.asarray(d['x']);y=np.asarray(d['y']);z=np.asarray(d['z']);
    if z.shape!=(len(y),len(x)) or not np.isfinite(z).any():raise ValueError('Regular grid z must be y×x')
    fig,ax=axes(o,.7);cm=LinearSegmentedColormap.from_list('field',PALETTES[o.get('cmap','teal-depth')]);cont=ax.contourf(x,y,np.ma.masked_invalid(z),levels=o.get('levels',15),cmap=cm);ax.contour(x,y,np.ma.masked_invalid(z),levels=8,colors='white',linewidths=.35,alpha=.5);fig.colorbar(cont,ax=ax,shrink=.75,label=d['unit']);ax.set(xlabel=d.get('xlabel','Coordinate 1'),ylabel=d.get('ylabel','Coordinate 2'),title=o.get('title',d.get('title','')))
    if 'sample_coordinates' in d:
        p=np.asarray(d['sample_coordinates']);ax.scatter(p[:,0],p[:,1],s=18,facecolors='white',edgecolors=INK,lw=.65,zorder=4)
    return fig,{'grid_shape':z.shape,'grid_interpolation':'none; supplied values','unit':d['unit'],'observed_coordinates_overlay':'sample_coordinates' in d}

def orbital_panel(d,o):
    systems=d['systems'];o={**o,'width':o.get('width','single' if len(systems)==1 else 'double')};fig,ax=axes(o,.95 if len(systems)==1 else .65)
    for i,s in enumerate(systems):
        occ=np.array(s['occupied_eV']);vir=np.array(s['virtual_eV']);occ=occ[-o.get('occupied_levels',6):];vir=vir[:o.get('virtual_levels',6)]
        for e in occ:ax.plot([i-.28,i+.28],[e,e],c='#3B6F91',lw=1.6)
        for e in vir:ax.plot([i-.28,i+.28],[e,e],c='#CA7354',lw=1.4)
        ax.annotate('',(i+.39,vir.min()),(i+.39,occ.max()),arrowprops={'arrowstyle':'<->','color':MUTED,'lw':.8});ax.text(i+.45,(vir.min()+occ.max())/2,f'{vir.min()-occ.max():.2f} eV',fontsize=7,va='center')
    ax.set_xticks(range(len(systems)),[wrap_label(s['label'],23) for s in systems]);ax.set(xlim=(-.6,len(systems)-.15),ylabel='Orbital energy (eV)',title=o.get('title','Frontier orbitals & gap'));fig.legend(handles=[Line2D([],[],c='#3B6F91',label='Occupied'),Line2D([],[],c='#CA7354',label='Virtual')],loc='outside lower center',ncols=2);return fig,{'energies':'supplied eV','gaps':'LUMO − HOMO, no experimental assignment'}

def trajectory_panel(d,o,kind):
    xy=np.array(d['embedding']);time=np.asarray(d['pseudotime']);fig,ax=axes({**o,'width':o.get('width','onehalf')},1.05)
    if len(time)!=len(xy):raise ValueError('Trajectory identities mismatch')
    sc=ax.scatter(xy[:,0],xy[:,1],c=time,cmap=LinearSegmentedColormap.from_list('time',PALETTES['teal-depth']),s=8,lw=.2,edgecolor='white');fig.colorbar(sc,ax=ax,label=d.get('time_label','Supplied pseudotime'),shrink=.7)
    for path in d.get('paths',[]):
        p=np.array(path);ax.plot(p[:,0],p[:,1],c=INK,lw=1.2,alpha=.7)
    if kind=='velocity_stream':
        vel=np.asarray(d['velocity_embedding'])
        if vel.shape!=xy.shape:raise ValueError('Aligned projected velocities required')
        if not np.isfinite(vel).all():raise ValueError('Finite projected velocity vectors required')
        magnitude=np.linalg.norm(vel,axis=1);span=max(np.linalg.norm(np.ptp(xy,axis=0)),1e-9);display_scale=float(o.get('velocity_scale',max(magnitude.max(),1e-12)/(.12*span)))
        if not np.isfinite(display_scale) or display_scale<=0:raise ValueError('Positive uniform velocity display scale required')
        sel=np.arange(0,len(xy),max(1,len(xy)//60));arrows=ax.quiver(xy[sel,0],xy[sel,1],vel[sel,0],vel[sel,1],angles='xy',scale_units='xy',scale=display_scale,color=INK,width=.0025,alpha=.68)
        ref=float(magnitude.max())*.5
        ax.quiverkey(arrows,.18,.03,ref,f'{ref:.2g} supplied velocity units',labelpos='E',coordinates='axes',fontproperties={'size':6})
    ax.set(xlabel=d.get('xlabel','Supplied embedding 1'),ylabel=d.get('ylabel','Supplied embedding 2'),title=o.get('title','Trajectory and ordered states'));ax.set_aspect('equal');ax.set_anchor('C');ax.set_xticks([]);ax.set_yticks([]);return fig,{'fitted_in_renderer':False,'time_label':d.get('time_label'),'vectors':kind=='velocity_stream','vector_display_scale':display_scale if kind=='velocity_stream' else None,'vector_rule':'one common scalar; supplied directions and relative lengths preserved; no invented streamline field' if kind=='velocity_stream' else None}

def phase_panel(d,o):
    t=pd.DataFrame(d['table']);fig,ax=axes(o,.65);sc=ax.scatter(t.spliced,t.unspliced,c=t[d.get('color_column','velocity')],cmap=LinearSegmentedColormap.from_list('velocity',PALETTES['blue-coral']),s=10,lw=.2,edgecolors='white',alpha=.8)
    if 'model_line' in d:
        line=d['model_line'];ax.plot(line['x'],line['y'],c=INK,ls='--',lw=1,label='Supplied model relation');ax.legend()
    ax.set(xlabel='Spliced moment (supplied scale)',ylabel='Unspliced moment (supplied scale)',title=d.get('gene','Phase portrait'));fig.colorbar(sc,ax=ax,label='Supplied velocity',shrink=.7);return fig,{'line_fitted_here':False,'gene':d.get('gene')}

def oncoprint_panel(d,o):
    # Explicit events + coverage matrix prevents empty mutation rows being used
    # as evidence that a sample was assayed and mutation-negative.
    samples=d['samples'];genes=d['genes'];assay=np.asarray(d['assayed'],bool)
    if assay.shape!=(len(genes),len(samples)):raise ValueError('Explicit assayed gene×sample mask required')
    events={tuple(k.split('|',1)):v for k,v in d['events'].items()};types=d['event_types'];colors=identity_colors(o.setdefault('theme',{}),types)
    fig,ax=axes(o,max(.6,.05*len(genes)+.25))
    for i,g in enumerate(genes):
        for j,s in enumerate(samples):
            ax.add_patch(Rectangle((j-.45,i-.4),.9,.8,fc='#F0F3F5' if assay[i,j] else '#D9CDBF',ec='white',lw=.3))
            ev=events.get((g,s),[])
            if ev and not assay[i,j]:raise ValueError('Events on declared unassayed cell')
            for k,typ in enumerate(ev):ax.add_patch(Rectangle((j-.43,i-.36+k*.72/max(len(ev),1)),.86,.72/max(len(ev),1),fc=colors[typ],lw=0))
    ax.set(xlim=(-.5,len(samples)-.5),ylim=(len(genes)-.5,-.5));ax.set_yticks(range(len(genes)),genes);step=max(1,math.ceil(len(samples)/25));ax.set_xticks(range(0,len(samples),step),[wrap_label(s,12) for s in samples[::step]],rotation=60,ha='right',fontsize=6.3);ax.tick_params(length=0);ax.spines[:].set_visible(False);ax.legend(handles=[Patch(color=colors[t],label=t) for t in types]+[Patch(color='#D9CDBF',label='Unassayed')],loc='upper left',bbox_to_anchor=(1,1));return fig,{'multi_event_cells_preserved':True,'samples':len(samples),'genes':len(genes),'empty_is_negative_only_if_assayed':True}

__all__=['qc_panel','small_cell_panel','surface_panel','orbital_panel','trajectory_panel','phase_panel','oncoprint_panel']
