import math
import numpy as np,pandas as pd,matplotlib as mpl,matplotlib.pyplot as plt
from matplotlib.patches import PathPatch,Patch,Rectangle
from matplotlib.path import Path
from matplotlib.colors import LinearSegmentedColormap
from design_system import *
from renderers_extra import axes,bars_panel

def enrichment_panel(d,o):
    t=pd.DataFrame(d['table'])
    if not {'term','ratio','count','fdr'}<=set(t):raise ValueError('Enrichment table requires term,ratio,count,fdr')
    if not t.fdr.between(0,1).all() or (t['count']<0).any():raise ValueError('Invalid enrichment values')
    if len(t)>35:raise ValueError('Paginate more than 35 enriched terms')
    row_labels=[wrap_label(x,32) for x in t.term]
    fig,ax=axes(o,max(.34,sum(s.count('\n')+1 for s in row_labels)*.05+.15));yy=np.arange(len(t));strength=-np.log10(np.maximum(t.fdr.to_numpy(),1e-300))
    effect='NES' if 'NES' in t and o.get('variant','evidence_bubble')!='ratio' else 'ratio'
    xx=t[effect].to_numpy(float)
    if not np.isfinite(xx).all():raise ValueError('Finite supplied enrichment effects required')
    if o.get('variant')=='lollipop':ax.hlines(yy,0,xx,color='#E2E8EC',lw=.9)
    if effect=='NES' and xx.min()<=0<=xx.max():ax.axvline(0,c=MUTED,lw=.6,ls='--')
    sc=ax.scatter(xx,yy,s=25+np.sqrt(t['count'].to_numpy())*10,c=strength,cmap=LinearSegmentedColormap.from_list('enrichment',PALETTES['teal-depth']),edgecolors=INK,lw=.25)
    ax.set_yticks(yy,row_labels);ax.invert_yaxis();ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.set_xlabel('Supplied normalized enrichment score' if effect=='NES' else d.get('ratio_label','Genes in set / eligible genes'));ax.set_title(o.get('title','Pathway effects, support & significance'),loc='left',pad=12)
    ax.grid(axis='x',color=GRID,lw=.4);ax.margins(y=.20)
    cb=fig.colorbar(sc,ax=ax,shrink=.65,pad=.03);cb.set_label('−log10 FDR');cb.outline.set_visible(False)
    sizes=sorted(set([int(np.min(t['count'])),int(np.median(t['count'])),int(np.max(t['count']))]));leg=ax.legend(handles=[ax.scatter([],[],s=25+np.sqrt(n)*10,facecolor='#A5C7BD',edgecolor=INK,lw=.25,label=str(n)) for n in sizes],title='Gene count',loc='upper left',bbox_to_anchor=(1.21,1),labelspacing=1.1)
    return fig,{'n_terms':len(t),'variant':o.get('variant','evidence_bubble'),'effect_channel':effect,'size':'area is transformed supplied count, legend explicit','color':'-log10 supplied FDR','refit':False}

def chord_panel(d,o):
    if o.get('variant','ribbon')=='ribbon':
        from chord_views import ribbon_chord
        return ribbon_chord(d,o)
    t=pd.DataFrame(d['links'])
    if not {'source','target','value'}<=set(t):raise ValueError('Links require source,target,value')
    if (t.value<0).any() or not np.isfinite(t.value).all():raise ValueError('Nonnegative finite link weights required')
    nodes=d.get('nodes',list(dict.fromkeys(t.source.tolist()+t.target.tolist())))
    if len(nodes)>24:raise ValueError('More than24 nodes: facet/filter with explicit scope')
    # Explicit labels eliminate reliance on cycling colors for many nodes.
    given=d.get('colors');colors=given or identity_colors(o.setdefault('theme',{}),nodes)
    theta=np.linspace(0,2*np.pi,len(nodes),endpoint=False);pos={n:np.array([np.cos(a),np.sin(a)]) for n,a in zip(nodes,theta)}
    fig,ax=axes(o,.85);maxw=max(t.value.max(),1e-12)
    for r in t.itertuples():
        p1=pos[r.source];p2=pos[r.target];path=Path([p1,p1*.25,p2*.25,p2],[Path.MOVETO,Path.CURVE4,Path.CURVE4,Path.CURVE4]);ax.add_patch(PathPatch(path,fill=False,color=colors[r.source],lw=.4+4*r.value/maxw,alpha=.30,zorder=1))
    for n,a in zip(nodes,theta):
        p=pos[n];ax.scatter(*p,s=40,c=colors[n],edgecolors='white',lw=.8,zorder=3);r=1.10;ax.text(r*p[0],r*p[1],wrap_label(n,18),ha='left' if p[0]>.1 else 'right' if p[0]<-.1 else 'center',va='center',fontsize=7.3)
    ax.set_aspect('equal');ax.set_xlim(-1.6,1.6);ax.set_ylim(-1.4,1.4);ax.axis('off');ax.set_title(o.get('title','Weighted relationships'),loc='left');return fig,{'edges':len(t),'node_order':nodes,'weight':'supplied, line width proportional','variant':'legible sparse arc network'}

def alluvial_panel(d,o):
    t=pd.DataFrame(d['links']);left=list(dict.fromkeys(t.source));right=list(dict.fromkeys(t.target));total=t.value.sum()
    if total<=0 or (t.value<0).any():raise ValueError('Nonnegative links with positive total required')
    colors=identity_colors(o.setdefault('theme',{}),left);L={};R={}
    gap=float(o.get('node_gap',.016));scale=1-gap*(max(len(left),len(right))-1)
    if scale<=0:raise ValueError('Alluvial gaps exceed available height')
    for names,side,col in [(left,L,'source'),(right,R,'target')]:
        cursor=(1-(scale+gap*(len(names)-1)))/2
        for g in names:side[g]=[cursor,cursor+t.loc[t[col]==g,'value'].sum()/total*scale];cursor=side[g][1]+gap
    lpos={g:a[0] for g,a in L.items()};rpos={g:a[0] for g,a in R.items()};fig,ax=axes(o,.7)
    for row in t.itertuples():
        h=row.value/total*scale;y0=lpos[row.source];y1=rpos[row.target];lpos[row.source]+=h;rpos[row.target]+=h
        vertices=[(.15,y0),(.45,y0),(.55,y1),(.85,y1),(.85,y1+h),(.55,y1+h),(.45,y0+h),(.15,y0+h),(.15,y0)];codes=[Path.MOVETO,Path.CURVE4,Path.CURVE4,Path.CURVE4,Path.LINETO,Path.CURVE4,Path.CURVE4,Path.CURVE4,Path.CLOSEPOLY];ax.add_patch(PathPatch(Path(vertices,codes),facecolor=colors[row.source],edgecolor='white',alpha=.45,lw=.3))
    for side,x,tx,align in [(L,.12,.09,'right'),(R,.85,.91,'left')]:
        names=sorted(side,key=lambda g:sum(side[g])/2);ys=np.array([sum(side[g])/2 for g in names]);separation=.038
        for i in range(1,len(ys)):ys[i]=max(ys[i],ys[i-1]+separation)
        if ys[-1]>1:ys-=ys[-1]-1
        for g,y in zip(names,ys):
            a,b=side[g];ax.add_patch(Rectangle((x,a),.03,b-a,fc=colors.get(g,'#6B8293')))
            ax.plot([x if align=='right' else x+.03,tx],[sum(side[g])/2,y],c=MUTED,lw=.4)
            ax.text(tx,y,wrap_label(g,24),ha=align,va='center',fontsize=7.3)
    ax.set(xlim=(-.24,1.30),ylim=(-.03,1.03));ax.axis('off');ax.set_title(o.get('title','Aligned annotation flows'),loc='left');return fig,{'total':float(total),'flow_semantics':d.get('flow_semantics','supplied links'),'no_temporal_inference':True}

def molecule_panel(d,o):
    if d.get('charges') is not None and o.get('variant','charge_profile')=='charge_profile':
        mol=d.get('molecule_2d',d);xy=np.asarray(mol['xy'],float);charges=np.asarray(d['charges'],float);elements=mol['elements']
        if xy.shape!=(len(charges),2) or len(elements)!=len(charges) or not np.isfinite(charges).all():raise ValueError('Literal aligned atom projection and charges required')
        fig,aa=plt.subplots(1,2,figsize=journal_size(o.get('width','onehalf'),o.get('aspect',1.0)),layout='constrained',gridspec_kw={'width_ratios':[1,.88]})
        ax,bar=aa;lim=max(abs(charges).max(),1e-8);cmap=LinearSegmentedColormap.from_list('charge',PALETTES['blue-coral'])
        for i,j,order in mol['bonds']:ax.plot(xy[[i,j],0],xy[[i,j],1],c=GRID,lw=.7,zorder=0)
        sc=ax.scatter(*xy.T,c=charges,cmap=cmap,vmin=-lim,vmax=lim,s=55,edgecolors='#708390',lw=.4)
        for i,(p,el) in enumerate(zip(xy,elements)):ax.annotate(el+str(i+1),p,xytext=(4,2),textcoords='offset points',fontsize=6.5,va='center')
        ax.set_aspect('equal');ax.margins(.25);ax.axis('off');ax.set_title('Supplied XY projection',fontsize=8)
        y=np.arange(len(charges));bar.hlines(y,0,charges,color=INK,lw=.6,alpha=.6);bar.scatter(charges,y,c=charges,cmap=cmap,vmin=-lim,vmax=lim,s=15,edgecolors='white',lw=.3,zorder=3)
        bar.set_yticks(y,[el+str(i+1) for i,el in enumerate(elements)],fontsize=6.4);bar.set_ylim(len(y)-.5,-.5);bar.axvline(0,c=MUTED,lw=.6,ls='--');bar.set_xlabel('Mulliken charge (e)');bar.spines[['left','right','top']].set_visible(False);bar.tick_params(axis='y',length=0);bar.grid(axis='x',color=GRID,lw=.4);bar.set_title('Indexed atomic charges',fontsize=8)
        fig.suptitle(wrap_label(o.get('title','Mulliken charge profile'),55),x=.02,ha='left',fontsize=9,fontweight='bold')
        return fig,{'atoms':len(xy),'bonds':len(mol['bonds']),'coordinates':'literal supplied XY, not refitted','connectivity_inferred':False,'variant':'projection_and_indexed_charges'}
    mol=d.get('molecule_2d',d);xy=np.asarray(mol['xy']);elements=mol['elements'];fig,ax=axes(o,.65)
    for i,j,order in mol['bonds']:
        v=xy[j]-xy[i];n=np.array([-v[1],v[0]])/max(np.linalg.norm(v),1e-9)*.055
        for k in range(min(order,3)):
            shift=(k-(min(order,3)-1)/2)*n;p=xy[i]+shift;q=xy[j]+shift;ax.plot([p[0],q[0]],[p[1],q[1]],c=INK,lw=.85)
    atomcolors={'N':'#39789E','O':'#BF625C','S':'#A78B41','P':'#A378A5','H':'#6D7E88'}
    charges=d.get('charges')
    if charges is not None:
        if len(charges)!=len(xy):raise ValueError('Charges must align to exact atom indices')
        lim=max(abs(np.asarray(charges)).max(),1e-8);sc=ax.scatter(xy[:,0],xy[:,1],c=charges,cmap=LinearSegmentedColormap.from_list('charge',PALETTES['blue-coral']),vmin=-lim,vmax=lim,s=120,alpha=.7,edgecolors='white',linewidths=.4,zorder=0);fig.colorbar(sc,ax=ax,shrink=.6,label='Supplied Mulliken charge (e)')
    for i,(p,el) in enumerate(zip(xy,elements)):
        if el!='C' or charges is not None:ax.text(*p,el+(str(i+1) if charges is not None else ''),ha='center',va='center',color=atomcolors.get(el,INK),fontsize=6.5 if charges is not None else 9,bbox={'facecolor':'white','edgecolor':'none','pad':.6},zorder=3)
    ax.set_aspect('equal');ax.margins(.15);ax.axis('off');ax.set_title(o.get('title','Molecular depiction · supplied connectivity'),loc='left');return fig,{'atoms':len(xy),'bonds':len(mol['bonds']),'bond_orders':'supplied, never guessed from xyz','contacts':'not fabricated'}

def poses_panel(d,o):
    poses=d['pose_coordinates_A'];nr,nc=choose_grid(len(poses),o.get('ncols'),o.get('nrows'),max_cols=3);fig=plt.figure(figsize=journal_size(o.get('width','double'),o.get('aspect',.37*nr)),layout='constrained')
    allxyz=np.concatenate([np.array(p) for p in poses]);center=allxyz.mean(axis=0);span=np.ptp(allxyz,axis=0).max()/2*1.1
    for i,p in enumerate(poses):
        ax=fig.add_subplot(nr,nc,i+1,projection='3d');p=np.asarray(p);atomcolors={'C':'#79919F','N':'#39789E','O':'#C16A54','S':'#B08C3F'};cs=[atomcolors.get(e,'#8D7C98') for e in d.get('elements',['C']*len(p))];ax.scatter(p[:,0],p[:,1],p[:,2],s=13,c=cs,edgecolors='white',lw=.3)
        # Only supplied pose atoms are shown; bond connectivity must be supplied
        # to draw bonds. The offline molecular viewer is the interactive entry.
        for bond in d.get('bonds',[]):
            a,b=bond[:2];ax.plot(p[[a,b],0],p[[a,b],1],p[[a,b],2],c='#597E99',lw=1.35)
        ax.set(xlim=(center[0]-span,center[0]+span),ylim=(center[1]-span,center[1]+span),zlim=(center[2]-span,center[2]+span));ax.set_proj_type('ortho');ax.set_box_aspect([1,1,1],zoom=o.get('camera_zoom',1.35));ax.view_init(elev=o.get('elev',20),azim=o.get('azim',35));ax.set_axis_off();ax.set_title(d['pose_ids'][i]+f' · {d["scores"][i]:.2f} kcal/mol',fontsize=8)
    return fig,{'poses':len(poses),'camera_shared':True,'coordinate_unit':'Angstrom','scoring':'Vina, not measured affinity'}

def energy_panel(d,o):
    if o.get('variant','waterfall')=='waterfall':
        rows=[r for r in d['rows'] if r['component'] in ['VDWAALS','EEL','EGB','ESURF']]
        total=next(r for r in d['rows'] if r['component']=='TOTAL')
        if not np.isclose(sum(r['mean'] for r in rows),total['mean'],atol=.05,rtol=0):raise ValueError('Waterfall requires supplied additive components consistent with the reported total; select components/stacked for another contract')
        fig,ax=axes({**o,'width':o.get('width','onehalf')},.72);previous=0.;endpoints=[0.]
        for i,r in enumerate(rows):
            value=float(r['mean']);end=previous+value;color='#C56D56' if value>=0 else '#39789E'
            ax.bar(i,value,bottom=previous,width=.64,color=color,edgecolor='white',lw=.6)
            ax.plot([i+.32,i+.68],[end,end],c=MUTED,lw=.6,ls='--')
            ax.annotate(f'{value:+.2f}',(i,(previous+end)/2),ha='center',va='center',color='white' if abs(value)>4 else INK,fontsize=7)
            previous=end;endpoints.append(end)
        i=len(rows);ax.bar(i,total['mean'],width=.64,color=INK,edgecolor='white',lw=.6)
        ax.errorbar(i,total['mean'],yerr=total['reported_sem'],fmt='none',ecolor='#CA7354',capsize=3,lw=.9)
        ax.annotate(f'{total["mean"]:+.2f}',(i,total['mean']),xytext=(0,-12 if total['mean']<0 else 6),textcoords='offset points',ha='center',fontsize=7)
        ax.axhline(0,c=MUTED,lw=.7);ax.set_xticks(range(len(rows)+1),[r['component'] for r in rows]+['TOTAL'],rotation=35,ha='right');ax.set_ylabel('Reported MM/GBSA energy (kcal/mol)');ax.set_title(o.get('title','Energy balance and reported total'),loc='left');ax.grid(axis='y',c=GRID,lw=.4);ax.set_axisbelow(True);span=max(np.ptp(endpoints),1);ax.set_ylim(min(endpoints)-span*.14,max(endpoints)+span*.07)
        return fig,{'variant':'waterfall','components':[r['component'] for r in rows],'cumulative_display_endpoints':endpoints,'reported_total':total['mean'],'uncertainty':'source frame SEM on TOTAL; not a CI','legacy_forms':['components','stacked']}
    if o.get('variant','components')!='stacked':
        rows=[r for r in d['rows'] if r['component'] in ['VDWAALS','EEL','EGB','ESURF','TOTAL']]
        fig,ax=axes({**o,'width':o.get('width','onehalf')},.62)
        for i,r in enumerate(rows):
            v=r['mean'];color='#C56D56' if v>=0 else '#39789E'
            if r['component']=='TOTAL':
                ax.axhspan(i-.45,i+.45,color='#F1F5F7',lw=0);ax.errorbar(v,i,xerr=r['reported_sem'],fmt='D',color=INK,capsize=3,lw=1,ms=5,zorder=4)
            else:
                ax.plot([0,v],[i,i],c=color,lw=2,alpha=.6);ax.scatter(v,i,c=color,s=30,edgecolor='white',lw=.5,zorder=3)
            ax.annotate(f'{v:+.2f}',(v,i),xytext=(6 if v>=0 else -6,0),textcoords='offset points',ha='left' if v>=0 else 'right',va='center',fontsize=7)
        ax.axvline(0,c=MUTED,lw=.8);ax.set_yticks(range(len(rows)),[r['component'] for r in rows]);ax.invert_yaxis();ax.set_xlabel('Reported MM/GBSA component (kcal/mol)');ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',color=GRID,lw=.4);ax.margins(x=.15);ax.set_title(o.get('title','Components & total · source SEM on total'),loc='left')
        return fig,{'variant':'signed_component_lollipops','source_components':[r['component'] for r in rows],'uncertainty':'source reported frame SEM on TOTAL only; not independent-run CI','stacked_form_retained':True}
    rows=[r for r in d['rows'] if r['component'] in ['VDWAALS','EEL','EGB','ESURF']];fig,aa=axes(o,.50,ncols=2,gridspec_kw={'width_ratios':[1,.55]})
    positive=negative=0
    for i,r in enumerate(rows):
        value=r['mean'];bottom=positive if value>=0 else negative;aa[0].bar([0],[value],bottom=bottom,color=PALETTES['muted'][i],width=.50,label=r['component'],edgecolor='white',lw=.7)
        if value>=0:positive+=value
        else:negative+=value
    aa[0].axhline(0,c=INK,lw=.8);aa[0].set(xticks=[0],xticklabels=['Binding-energy components'],ylabel='Reported MM/GBSA energy (kcal/mol)',title='Signed component balance');aa[0].legend(loc='upper left',bbox_to_anchor=(-.02,-.12),ncol=2)
    tot=next(r for r in d['rows'] if r['component']=='TOTAL');aa[1].errorbar([0],[tot['mean']],yerr=[tot['reported_sem']],fmt='o',color='#3B6F91',capsize=4,lw=1.4,ms=7);aa[1].axhline(0,c=GRID,lw=.7);aa[1].set(xticks=[0],xticklabels=['Total'],ylabel='kcal/mol',title='Mean ± reported SEM')
    return fig,{'source_components':[r['component'] for r in rows],'sum':positive+negative,'reported_total':tot['mean'],'uncertainty':'supplied frame SEM, not independent-run CI'}

__all__=['enrichment_panel','chord_panel','alluvial_panel','molecule_panel','poses_panel','energy_panel']
