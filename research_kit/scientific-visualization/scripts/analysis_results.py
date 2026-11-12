"""Receipt-bound result consumers for 71 reviewed methods and completion routes.

Only frozen columns are displayed. There is no inference, embedding, clustering,
aggregation, interval reconstruction, identifier repair or new analysis here.
"""
from pathlib import Path
import json
from native_figures import plan_native_figures,_one,_tsv,digest

def plan_result_figures(request,receipt,root,acceptance,selection,expected_source_sha256):
    p=plan_native_figures(request,receipt,root,acceptance,selection,expected_source_sha256)
    if p['backend']=='omics71':
        policy=json.loads((Path(__file__).resolve().parents[1]/'assets/analysis71_routes.json').read_text(encoding='utf8'))
        key=p['request']['parameters']['analysis_id']
        if key not in policy['methods']:raise ValueError('No reviewed scientific result policy for this method')
        p['route']={**policy['methods'][key],'kind':'method_specific_frozen_result'}
        if not set(selection)<=set(p['route']['actual_roles']):raise ValueError('Only explicit method scientific roles may be selected for plotting')
        p['analysis_id']=key
    else:
        if 'preferred_views' not in p['route']:raise ValueError('Use the existing dedicated native consumer for this older backend')
        if not set(selection)<=set(p['route']['result_roles']):raise ValueError('Select actual scientific result roles, not an arbitrary log or status table')
    from native_figures import _binding
    p['binding_sha256']=_binding({k:v for k,v in p.items() if k!='binding_sha256'})
    return p

def _channels(table,mapping,expected):
    if set(mapping)!=set(expected) or any(not isinstance(v,str) for v in mapping.values()) or len(set(mapping.values()))!=len(mapping) or not set(mapping.values())<=set(table):raise ValueError('Exact distinct stored columns required for this selected view')

def _number(table,columns,missing=False):
    import numpy as np
    a=table[columns].replace({'NA':np.nan,'NaN':np.nan,'':np.nan}).astype(float)
    if np.isinf(a.to_numpy()).any() or not missing and a.isna().any().any():raise ValueError('Actual plot channel is nonfinite/unassessed; select an explicit assessed display set rather than impute or hide rows')
    return a

def render_result(plan,role,view,channels,*,path=None,unit=None,xunit=None,interval_label=None,probability_meaning=None,thresholds=None,annotations=None,transpose=False,**options):
    """Draw actual supplied result columns in a caller-selected allowed form.

    options are the existing physical width, layout, palette, facets and export
    controls. Their defaults preserve the current design system and SHAP forms.
    """
    import numpy as np
    import pandas as pd
    from renderers import render_template
    allowed=plan['route'].get('allowed_views',plan['route'].get('preferred_views',[]))
    if view not in allowed:raise ValueError('This scientific result route does not declare that display form')
    if not isinstance(unit,str) or not unit:raise ValueError('Declare the actual producer quantity and units; do not guess from a filename')
    source=_one(plan,role,path);table=_tsv(source)
    if table.empty or len(table)>20000:raise ValueError('Select a bounded nonempty frozen display export, not a raw matrix or empty placeholder')
    if options.get('cluster',False) or options.get('normalize',False):raise ValueError('Use a separately reviewed upstream hierarchy/normalization; this consumer does not refit results')
    options.setdefault('title',plan.get('analysis_id',plan['backend']).replace('_',' ')+' · '+role.replace('_',' '))
    if view=='matrix':
        if set(channels)!={'index','values'} or not isinstance(channels['values'],list) or not channels['values'] or len(set(channels['values']))!=len(channels['values']) or channels['index'] in channels['values']:raise ValueError('Exact actual matrix index and numeric column list required')
        cols=[channels['index']]+channels['values']
        if not set(cols)<=set(table) or table[channels['index']].duplicated().any() or table[channels['index']].eq('').any() or len(table)>2000 or len(channels['values'])>200:raise ValueError('Select/paginate unique actual frozen matrix axes within a readable display scope')
        value=_number(table,channels['values'],missing=True);value.index=table[channels['index']]
        if type(transpose) is not bool:raise ValueError('Explicit display transpose boolean required')
        if transpose:value=value.T
        data={'matrix':value};identifier='deg_heatmap';options={**options,'cluster':False,'color_label':unit}
        if annotations:
            if set(annotations)!={'role','path','id','group'}:raise ValueError('Exact stored annotation role/path/id/group required')
            annotation_source=_one(plan,annotations['role'],annotations['path']);ann=_tsv(annotation_source)
            if not {annotations['id'],annotations['group']}<=set(ann) or ann[annotations['id']].duplicated().any() or ann[annotations['id']].eq('').any() or ann[annotations['group']].eq('').any():raise ValueError('Complete unique source condition annotation identities required')
            lookup=ann.set_index(annotations['id'])[annotations['group']]
            if not set(value.columns)<=set(lookup.index):raise ValueError('Source metadata does not cover the exact displayed column identities')
            data['groups']=lookup.loc[list(value.columns)].tolist();data['group_order']=list(dict.fromkeys(data['groups']))
    elif annotations or transpose:
        raise ValueError('Source column annotations and display transpose are matrix-view options only')
    elif view=='scatter':
        _channels(table,channels,['id','x','y']);a=_number(table,[channels['x'],channels['y']])
        if not xunit:raise ValueError('Actual producer X quantity and units required; a technical column name is insufficient')
        if table[channels['id']].duplicated().any():raise ValueError('Select unique point identities or a single explicit contrast/unit facet')
        data={'x':a.iloc[:,0].to_numpy(),'y':a.iloc[:,1].to_numpy(),'xlabel':xunit,'ylabel':unit};identifier='validation_scatter'
        if options.get('width')=='single':
            from design_system import wrap_label
            data['xlabel']=wrap_label(xunit,35);data['ylabel']=wrap_label(unit,30)
        if len(table)<=12:
            data['point_labels']=table[channels['id']].tolist();options.setdefault('point_size',26);options.setdefault('aspect',.48)
    elif view=='interval':
        _channels(table,channels,['id','estimate','lo','hi'])
        if not interval_label:raise ValueError('Actual interval definition/coverage is required; no default 95% CI')
        a=_number(table,[channels['estimate'],channels['lo'],channels['hi']]);data={'table':pd.DataFrame({'label':table[channels['id']],'estimate':a.iloc[:,0],'lo':a.iloc[:,1],'hi':a.iloc[:,2]}),'unit':unit,'interval_label':interval_label};identifier='forest'
    elif view=='rank':
        _channels(table,channels,['id','value']);a=_number(table,[channels['value']]);data={'table':pd.DataFrame({'label':table[channels['id']],'value':a.iloc[:,0]}),'unit':unit};identifier='contact_freq'
        if options.get('width')=='single':
            from design_system import wrap_label
            data['unit']=wrap_label(unit,35)
    elif view=='curve':
        _channels(table,channels,['series','x','y']);a=_number(table,[channels['x'],channels['y']]);curves=[]
        if not xunit:raise ValueError('Actual producer time/rank/distance quantity and units required')
        for name,indices in table.groupby(channels['series'],sort=False).groups.items():
            x=a.loc[indices].iloc[:,0].to_numpy();y=a.loc[indices].iloc[:,1].to_numpy()
            if len(x)<2 or (np.diff(x)<=0).any():raise ValueError('Actual stored curve order must be strictly increasing; repeated X values need an explicit scatter/unit facet, not a joined population curve')
            curves.append({'label':name,'x':x,'y':y})
        data={'curves':curves,'xlabel':xunit,'ylabel':unit};identifier='convergence'
    elif view=='edges':
        _channels(table,channels,['source','target','weight']);a=_number(table,[channels['weight']])
        if len(table)>200:raise ValueError('Select an explicit frozen network display scope; retain the full denominator in source results')
        if (a.iloc[:,0]<0).any():raise ValueError('Chord width requires nonnegative native weights; use a signed matrix for negative associations, never silently take absolute values')
        data={'links':pd.DataFrame({'source':table[channels['source']],'target':table[channels['target']],'value':a.iloc[:,0]}),'weight_label':unit};identifier='chord_go'
    elif view=='volcano':
        _channels(table,channels,['id','effect','q'])
        if probability_meaning!='adjusted_pvalue' or not isinstance(thresholds,dict) or set(thresholds)!={'effect','q','basis'} or not thresholds['basis']:raise ValueError('Actual adjusted P-value plus prespecified effect/FDR thresholds and their basis required')
        a=_number(table,[channels['effect'],channels['q']])
        if ((a.iloc[:,1]<0)|(a.iloc[:,1]>1)).any() or not 0<thresholds['q']<1 or thresholds['effect']<0:raise ValueError('Invalid adjusted P values or source analysis thresholds')
        data={'de':pd.DataFrame({'gene':table[channels['id']],'log2FC':a.iloc[:,0],'padj':a.iloc[:,1]}),'effect_unit':unit,'classification_label':'Effect direction'};identifier='volcano';options={**options,'log2fc':thresholds['effect'],'fdr':thresholds['q']}
    elif view=='proportions':
        if set(channels)!={'index','values'} or not isinstance(channels['values'],list) or not channels['values']:raise ValueError('Actual probability/proportion matrix required')
        if not set([channels['index']]+channels['values'])<=set(table):raise ValueError('Missing actual proportion axes')
        a=_number(table,channels['values'])
        if (a<0).any().any() or (a>1).any().any() or not np.allclose(a.sum(axis=1),1,atol=1e-6,rtol=0):raise ValueError('Actual proportions must already sum to one; abundance is not silently normalized')
        data={'values':a.to_numpy(),'labels':table[channels['index']].tolist(),'categories':channels['values'],'unit':unit,'already_proportions':True};identifier='proportion_stack'
    else:raise ValueError('Use the explicit five-channel image consumer for generated morphology')
    fig,meta=render_template(identifier,data,**options)
    meta.update(source_role=role,source_path=str(source),source_sha256=digest(source),request_sha256=plan['request_sha256'],receipt_sha256=plan['receipt_sha256'],analysis_id=plan.get('analysis_id'),data_kind=plan['route']['kind'],actual_stored_columns=channels,units=unit,xunit=xunit,interval_label=interval_label,analysis_recomputed=False,scientific_acceptance='NOT_ESTABLISHED',interpretation_boundary=plan['route']['interpretation_boundary'])
    return fig,meta

def render_generated_channels(plan,*,image_path=None,identity_path=None,summary_path=None,query_ids,channel_names,width='double',ncols=None,nrows=None,outdir=None,formats=('png','svg'),stem='generated_channels',overwrite=False,cmap='gray'):
    import numpy as np
    import matplotlib.pyplot as plt
    from design_system import journal_size,wrap_label,finish_figure,choose_grid,safe_save
    if not plan['backend'].startswith('morphdiff_'):raise ValueError('Generated morphology consumer requires the actual MorphDiff route')
    paths={r:_one(plan,r,x) for r,x in [('predicted_images',image_path),('prediction_identity',identity_path),('channel_summary',summary_path)]}
    identity=_tsv(paths['prediction_identity']);summary=_tsv(paths['channel_summary'])
    if len(set(query_ids))!=len(query_ids) or not set(query_ids)<=set(identity.query_id) or len(query_ids)>8 or not query_ids:raise ValueError('Select 1–8 exact generated queries for a legible page')
    if channel_names!=list(dict.fromkeys(summary.channel)) or len(channel_names)!=5:raise ValueError('Five literal native image-channel names required; no guessed RGB substitute')
    a=np.load(paths['predicted_images'],allow_pickle=False,mmap_mode='r')
    if a.ndim!=4 or a.shape[:2]!=(len(identity),5):raise ValueError('Generated image/identity/channel dimensions differ')
    n=len(query_ids);standard=ncols is None and nrows is None
    nr,nc=(n,5) if standard else choose_grid(n*5,ncols,nrows,max_cols=5)
    size=journal_size(width,max(.32,nr/nc+.12))
    if size[1]*25.4>480:raise ValueError('Requested image panel layout needs explicit pagination; fonts will not be shrunk to fit')
    fig,axes=plt.subplots(nr,nc,figsize=size,layout='constrained',squeeze=False)
    for i,name in enumerate(query_ids):
        k=identity.query_id.tolist().index(name)
        for j,ch in enumerate(channel_names):
            ax=axes.flat[i*5+j]
            img=np.asarray(a[k,j])
            if not np.isfinite(img).all() or img.min()<0 or img.max()>1:raise ValueError('Expected actual native generated [0,1] channels')
            ax.imshow(img,cmap=cmap,vmin=0,vmax=1);ax.set_xticks([]);ax.set_yticks([])
            if not standard:ax.set_title(wrap_label(name+' · '+ch,24),fontsize=7)
            elif i==0:ax.set_title(wrap_label(ch,18),fontsize=8)
            if standard and j==0:ax.set_ylabel(wrap_label(name,22),fontsize=7)
    for ax in axes.flat[n*5:]:ax.remove()
    fig.suptitle('Model-generated morphology',x=.01,ha='left',fontsize=11);finish_figure(fig)
    meta={'status':'RENDERED_UNREVIEWED','data_kind':plan['route']['kind'],'actual_query_ids':query_ids,'channel_names':channel_names,'nrows':nr,'ncols':nc,'shared_display_scale':[0,1],'source_sha256':{k:digest(v) for k,v in paths.items()},'scientific_acceptance':'NOT_ESTABLISHED','not_experimental_microscopy':True}
    if outdir is not None:meta['outputs']=safe_save(fig,stem,outdir,formats,overwrite=overwrite)
    return fig,meta
