"""Shared controlled-layout design implementation. No scientific fitting."""
from pathlib import Path
import hashlib, json, math, os, re, textwrap, warnings
from contextlib import contextmanager
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, to_hex, to_rgb
from matplotlib.patches import Ellipse

WIDTH_MM={'single':89.,'onehalf':120.,'double':183.}
INK='#253442'; MUTED='#617281'; GRID='#E2E8EC'
PALETTES={
 'okabe-ito':['#0072B2','#D55E00','#009E73','#CC79A7','#E69F00','#56B4E9','#222222','#999999'],
 'muted':['#3B6F91','#CA7354','#4C9685','#9279AE','#BE9848','#6E91AD','#B17890','#879878'],
 'jewel':['#27668C','#AB5067','#4A8B76','#7B62A3','#AD7D2E','#3C8E9C','#8F6257','#6E7B9B'],
 'earth':['#607A69','#A7694E','#8D7B59','#537986','#A67C85','#8B9270','#755F75','#B19575'],
 'soft':['#8CAAC4','#D7988C','#8EB7A7','#B5A1C7','#CEB37E','#9AC2C8','#BAA59A','#A8B2CE'],
 'cool':['#286889','#47958F','#6C80AD','#778A67','#A58BB0','#629DAA','#8699B4','#536977'],
 'warm':['#B85F53','#CC8C49','#A97884','#B29466','#976666','#CB9B88','#9E8171','#D7B167'],
 'blue-orange':['#316C98','#CC7952','#83ADC4','#E4B491','#596F83','#B6C6D0','#9E6F57','#C6ACA0'],
 'blue-depth':['#F3F7FA','#A8C9DC','#5796BB','#1B537A'],
 'teal-depth':['#F0F7F5','#B1D3C8','#579B8B','#216453'],
 'purple-depth':['#F6F2F9','#C5B6D5','#9373AD','#583B75'],
 'amber-depth':['#FBF7ED','#E5CCA1','#BA9456','#775825'],
 'blue-coral':['#316C98','#8CB5CC','#FAFAF8','#E2AD99','#C16A54'],
 'teal-rose':['#287D73','#97C6BA','#FAFAF8','#DCA6B6','#AD526D'],
 'purple-gold':['#735A95','#BAACD0','#FAFAF8','#E4D0A0','#AC873C'],
 'slate-ochre':['#4E6A7B','#ADC0CB','#FAFAF8','#DCC4A3','#A77E4E']}
_STYLE_STATE={'theme':None}
_PANEL_WIDTH_MM=None

@contextmanager
def panel_viewport(width_mm):
    """Internal composite child canvas; preserve physical fonts at any column width."""
    global _PANEL_WIDTH_MM
    if not np.isfinite(width_mm) or width_mm<45 or width_mm>183:raise ValueError('Composite panels require 45 to 183 mm; paginate narrower views')
    previous=_PANEL_WIDTH_MM;_PANEL_WIDTH_MM=float(width_mm)
    try:yield
    finally:_PANEL_WIDTH_MM=previous

def use_style(theme='journal',font_scale=1.):
    if theme not in ('journal','poster','minimal','dark'): raise ValueError('Unknown theme')
    if not np.isfinite(font_scale) or font_scale<=0: raise ValueError('font_scale must be positive')
    # Explicit local font discovery, never silent downloading or installation.
    candidates=[Path(__file__).resolve().parents[1]/'assets/fonts/LiberationSans-Regular.ttf',Path(os.environ.get('BIOSTYLE_FONT',''))]
    if os.environ.get('PROGRAMFILES'):
        candidates.append(Path(os.environ['PROGRAMFILES'])/'LibreOffice/share/fonts/truetype/LiberationSans-Regular.ttf')
    for p in candidates:
        if p.is_file():
            for font in p.parent.glob('LiberationSans-*.ttf'): font_manager.fontManager.addfont(str(font))
    try: font_manager.findfont('Liberation Sans',fallback_to_default=False)
    except ValueError: warnings.warn('Liberation Sans unavailable; DejaVu Sans fallback is recorded by the caller',RuntimeWarning)
    base=(11 if theme=='poster' else 8.5)*font_scale
    bg,ink=('#17232C','#F7FAFC') if theme=='dark' else ('white',INK)
    mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Liberation Sans','DejaVu Sans'],
       'font.size':base,'axes.labelsize':base,'axes.titlesize':base+1,'axes.titleweight':'bold',
       'xtick.labelsize':base-1,'ytick.labelsize':base-1,'legend.fontsize':base-1,
       'legend.title_fontsize':base-1,'axes.labelcolor':ink,'text.color':ink,
       'axes.edgecolor':ink,'xtick.color':ink,'ytick.color':ink,'axes.linewidth':.65,
       'axes.spines.top':False,'axes.spines.right':False,'axes.grid':False,
       'figure.facecolor':bg,'axes.facecolor':bg,'savefig.facecolor':bg,
       'grid.color':GRID,'grid.linewidth':.45,'grid.alpha':.6,'axes.axisbelow':True,
       'lines.linewidth':1.3,'lines.markersize':4,'lines.markeredgewidth':.4,
       'xtick.major.size':2.8,'ytick.major.size':2.8,'xtick.major.width':.6,'ytick.major.width':.6,
       'legend.frameon':False,'legend.handlelength':1.35,'legend.handletextpad':.5,
       'figure.dpi':120,'savefig.dpi':300,'savefig.bbox':None,
       'svg.fonttype':'none','pdf.fonttype':42,'ps.fonttype':42,
       'axes.prop_cycle':mpl.cycler(color=PALETTES['muted'])})
    _STYLE_STATE['theme']=theme
    return theme

def journal_size(width='single',aspect=.75):
    if width not in WIDTH_MM: raise ValueError('width: single, onehalf, double')
    if not np.isfinite(aspect) or aspect<=0: raise ValueError('aspect must be positive')
    w=(_PANEL_WIDTH_MM if _PANEL_WIDTH_MM is not None else WIDTH_MM[width])/25.4
    return w,w*aspect

def cat_palette(n,style='muted'):
    aliases={'okabe':'okabe-ito','phylo':'jewel'}; style=aliases.get(style,style)
    if style not in list(PALETTES)[:8]: raise ValueError('Categorical palette required')
    if n<0 or n>len(PALETTES[style]): raise ValueError('Too many categories for unique colors; facet or supply explicit mapping/markers')
    return PALETTES[style][:n]

def identity_colors(theme,labels):
    labels=list(dict.fromkeys(map(str,labels)))
    fixed=dict(theme.get('identity_colors',{}))
    missing=[s for s in sorted(labels) if s not in fixed]
    # A project can contain identities from unrelated domains. Reserve colors
    # only for fixed identities actually present in this view; inactive mappings
    # must not exhaust the palette for a new, independent figure.
    active_colors={fixed[s] for s in labels if s in fixed}
    available=[c for c in PALETTES[theme.get('palette','muted')] if c not in active_colors]
    if len(missing)>len(available): raise ValueError('Provide explicit identity colors and facets/markers for high-cardinality data')
    fixed.update(zip(missing,available))
    for c in fixed.values(): to_rgb(c)
    theme['identity_colors']=fixed  # caller persists this mapping at project creation
    return {s:fixed[s] for s in labels}

def wrap_label(s,width=24):
    return '\n'.join(textwrap.wrap(str(s),width=width,break_long_words=True,break_on_hyphens=False))

def choose_grid(n,ncols=None,nrows=None,max_cols=3):
    for value in (n,ncols,nrows):
        if value is not None and (isinstance(value,bool) or not np.isfinite(value) or int(value)!=value):raise ValueError('Panel counts and layout rows/columns must be finite integers')
        if value is not None and value<1:raise ValueError('Panel counts and rows/columns must be positive')
    if n<1: raise ValueError('At least one panel required')
    if ncols is None and nrows is None: ncols=min(max_cols,max(1,math.ceil(math.sqrt(n))))
    if ncols is None: ncols=math.ceil(n/nrows)
    if nrows is None: nrows=math.ceil(n/ncols)
    if ncols<1 or nrows<1 or ncols*nrows<n: raise ValueError('Requested layout cannot fit panels; increase rows/columns or paginate')
    return int(nrows),int(ncols)

def add_ellipse(ax,x,y,color,level=.95,records=None,label=''):
    from scipy.stats import chi2
    xy=np.column_stack([x,y]).astype(float); xy=xy[np.isfinite(xy).all(axis=1)]
    reason=None
    if len(xy)<3: reason='fewer_than_three_finite_samples'
    else:
        vals,vecs=np.linalg.eigh(np.cov(xy,rowvar=False)); order=np.argsort(vals)[::-1]
        vals,vecs=vals[order],vecs[:,order]
        if vals[-1]<=max(vals[0],1.)*1e-12: reason='singular_covariance'
    if reason:
        if records is not None: records.append({'group':label,'ellipse':'omitted','reason':reason})
        return None
    radii=2*np.sqrt(vals*chi2.ppf(level,2))
    angle=np.degrees(np.arctan2(vecs[1,0],vecs[0,0]))
    e=Ellipse(xy.mean(axis=0),*radii,angle=angle,edgecolor=color,facecolor=mpl.colors.to_rgba(color,.10),linewidth=.9,zorder=1)
    ax.add_patch(e)
    if records is not None: records.append({'group':label,'ellipse':'data_dispersion','level':level,'n':len(xy)})
    return e

def matrix_input(value,row_names=None,col_names=None,allow_sparse=False):
    from scipy import sparse
    import pandas as pd
    if sparse.issparse(value):
        if not allow_sparse: raise TypeError('Sparse input not supported by this template; supply a bounded dense matrix explicitly')
        if value.shape[0]*value.shape[1]>1_000_000: raise ValueError('Sparse-to-dense bound exceeded; select a smaller view upstream')
        value=value.toarray()
    if isinstance(value,pd.DataFrame):
        if not value.index.is_unique or not value.columns.is_unique: raise ValueError('Matrix labels must be unique')
        return value.astype(float)
    v=np.asarray(value,dtype=float)
    if v.ndim!=2 or 0 in v.shape: raise ValueError('Nonempty 2D matrix required')
    frame=pd.DataFrame(v,index=row_names if row_names is not None else [str(i+1) for i in range(v.shape[0])],columns=col_names if col_names is not None else [str(i+1) for i in range(v.shape[1])])
    if not frame.index.is_unique or not frame.columns.is_unique:raise ValueError('Matrix labels must be unique')
    return frame

def safe_save(fig,name,outdir,formats=('png','svg'),dpi=300,overwrite=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',name) or '..' in name: raise ValueError('Use a plain filename stem')
    out=Path(outdir).resolve(); out.mkdir(exist_ok=True,parents=True)
    exts=list(dict.fromkeys(str(x).lower() for x in formats))
    if any(e not in ('png','svg','pdf','tiff','tif') for e in exts): raise ValueError('Unsupported export format')
    paths=[out/(name+'.'+e) for e in exts]
    if not overwrite and any(p.exists() for p in paths): raise FileExistsError('Existing figure; choose a new version or explicitly allow overwrite')
    finish_figure(fig)
    fig.canvas.draw()
    for p in paths:
        tmp=p.with_name(p.stem+'.partial'+p.suffix)
        fig.savefig(tmp,dpi=dpi,bbox_inches=None,facecolor=fig.get_facecolor())
        tmp.replace(p)
    return list(map(str,paths))

def finish_figure(fig):
    """Wrap overlong titles within their physical lane, preserving font size."""
    from matplotlib.text import Text
    for label in fig.findobj(match=Text):
        text=label.get_text()
        if '⁻¹' in text:label.set_text(text.replace('⁻¹',r'$^{-1}$'))
    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    for ax in fig.axes:
        for label in (ax.title,ax._left_title,ax._right_title):
            text=label.get_text()
            if text and label.get_window_extent(renderer).width>ax.get_window_extent(renderer).width*1.02:
                width=max(10,int(ax.get_window_extent(renderer).width/(label.get_fontsize()*fig.dpi/72*.55)))
                label.set_text(wrap_label(text,width))
    if fig._suptitle is not None:
        title=fig._suptitle
        if title.get_window_extent(renderer).width>fig.bbox.width*.96:
            width=max(20,int(fig.bbox.width*.96/(title.get_fontsize()*fig.dpi/72*.52)));title.set_text(wrap_label(title.get_text(),width))

def sig_pairs(ax,positions,pairs,pvals,y_start,step,h=.02):
    if len(pairs)!=len(pvals): raise ValueError('pairs/pvals lengths differ')
    from biostyle import sig_bracket
    for i,((a,b),p) in enumerate(zip(pairs,pvals)):
        if not np.isfinite(p): text='NA'
        elif not 0<=p<=1: raise ValueError('p must be in [0,1]')
        else: text='****' if p<1e-4 else '***' if p<1e-3 else '**' if p<.01 else '*' if p<.05 else 'ns'
        sig_bracket(ax,positions[a],positions[b],y_start+i*step,h*np.ptp(ax.get_ylim()),text)

__all__=['WIDTH_MM','PALETTES','INK','MUTED','GRID','use_style','journal_size','cat_palette','identity_colors','wrap_label','choose_grid','add_ellipse','matrix_input','safe_save','finish_figure','sig_pairs','panel_viewport']
