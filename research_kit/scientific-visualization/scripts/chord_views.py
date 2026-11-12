"""Weighted ribbon chords, including self-links, from literal supplied links."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch,Wedge
from design_system import *

def ribbon_chord(d,o):
    t=pd.DataFrame(d['links'])
    if not {'source','target','value'}<=set(t):raise ValueError('Named source, target, value links required')
    if t.empty or not np.isfinite(t.value).all() or (t.value<0).any() or t.value.sum()<=0:raise ValueError('Positive total with finite nonnegative link weights required')
    nodes=list(d.get('nodes',dict.fromkeys(t.source.tolist()+t.target.tolist())))
    if len(nodes)>24:raise ValueError('Select at most 24 named chord nodes or facet')
    if set(t.source)|set(t.target)!=set(nodes):raise ValueError('Chord node names do not match supplied links')
    colors=d.get('colors') or identity_colors(o.setdefault('theme',{}),nodes)
    weight={n:float(t.loc[t.source==n,'value'].sum()+t.loc[t.target==n,'value'].sum()) for n in nodes}
    if any(v<=0 for v in weight.values()):raise ValueError('Chord nodes must participate in a positive link')
    gap=float(o.get('node_gap_degrees',4))
    if not 0<=gap<360/len(nodes):raise ValueError('Node gap exceeds circle capacity')
    scale=(2*np.pi-len(nodes)*np.deg2rad(gap))/sum(weight.values())
    start=np.pi/2;arcs={}
    for n in nodes:arcs[n]=(start,start+weight[n]*scale);start=arcs[n][1]+np.deg2rad(gap)
    cursor={n:a[0] for n,a in arcs.items()}
    fig,ax=plt.subplots(figsize=journal_size(o.get('width','double'),o.get('aspect',.86)),layout='constrained')
    def xy(angle,r=1):return np.array([np.cos(angle),np.sin(angle)])*r
    for row in t.itertuples():
        if row.value==0:continue
        a=cursor[row.source];b=a+row.value*scale;cursor[row.source]=b
        c=cursor[row.target];e=c+row.value*scale;cursor[row.target]=e
        src=[xy(z,.97) for z in np.linspace(a,b,14)]
        target=[xy(z,.97) for z in np.linspace(c,e,14)]
        vertices=src+[src[-1]*.18,target[0]*.18,target[0]]+target[1:]+[target[-1]*.18,src[0]*.18,src[0],src[0]]
        codes=[Path.MOVETO]+[Path.LINETO]*(len(src)-1)+[Path.CURVE4]*3+[Path.LINETO]*(len(target)-1)+[Path.CURVE4]*3+[Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(vertices,codes),facecolor=colors[row.source],alpha=.48,edgecolor='white',lw=.35))
    for n,(a,b) in arcs.items():
        ax.add_patch(Wedge((0,0),1,np.degrees(a),np.degrees(b),width=.035,facecolor=colors[n],edgecolor='white',lw=.5))
        p=xy((a+b)/2,1.09)
        name=d.get('display_nodes',{}).get(n,n)
        ax.text(*p,wrap_label(name,int(o.get('label_wrap',24))),ha='left' if p[0]>.12 else 'right' if p[0]<-.12 else 'center',va='center',fontsize=o.get('label_size',7.6))
    ax.set_aspect('equal');ax.set_xlim(-1.65,1.65);ax.set_ylim(-1.30,1.30);ax.axis('off')
    fig.suptitle(o.get('title','Supplied weighted relationships'),x=.02,ha='left',fontsize=10,fontweight='bold')
    if d.get('weight_label'):fig.supxlabel(wrap_label(d['weight_label'],38 if o.get('width')=='single' else 70),fontsize=7)
    return fig,{'variant':'weighted_ribbon_chord','nodes':nodes,'links':len(t),'self_links':int(sum(t.source==t.target)),
                'width_semantics':d.get('weight_label','literal supplied link weight'),'aggregation':'none in renderer','node_weights':weight}
