"""Bounded returned-result views for private native workflows; no scientific engine.

Only selected completed artifacts are read. Caller-declared QC, receipt hashes
and table checks do not establish scheduler authenticity or scientific validity.
"""
from pathlib import Path, PurePosixPath
import csv, hashlib, json
from contextlib import contextmanager


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):h.update(block)
    return h.hexdigest()


def _json(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>2*1024**2:raise ValueError('Select a bounded real JSON file, not a link or remote URL')
    return json.loads(p.read_text(encoding='utf-8-sig'))


def _binding(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _inside(root,name):
    # Output receipt paths are portable POSIX relative paths, never hosts or URLs.
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or name.startswith('/') or '..' in Path(name).parts or PurePosixPath(name).as_posix()!=name:raise ValueError('Select an exact relative output receipt path')
    p=root/name
    if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise ValueError('Selected output is missing, linked or outside its owned result directory')
    return p


def plan_native_figures(request_path,receipt_path,output_root,acceptance_path,selection,expected_source_sha256):
    """Check current code, exact receipts/QC and every explicitly selected file.

    selection maps a role to a list of exact receipt paths; repeated roles are
    never overwritten or resolved by choosing the last file.
    """
    request,receipt,acceptance=map(_json,[request_path,receipt_path,acceptance_path])
    policy=_json(Path(__file__).resolve().parents[1]/'assets/workflow_channels.json')
    backend=request['backend']
    if backend not in policy['routes'] and backend!='ml':raise ValueError('No reviewed native result policy for this backend')
    if receipt.get('state')!='COMPLETED' or receipt.get('exit_code')!=0 or receipt.get('request_sha256')!=digest(request_path):raise ValueError('Exact completed producer receipt required; submitted/unknown/historical is not completed')
    if not expected_source_sha256 or request.get('source_sha256')!=expected_source_sha256 or receipt.get('source_sha256')!=expected_source_sha256:raise ValueError('Source changed or source binding incomplete: old acceptance is expired')
    if acceptance.get('state')!='RETURN_CHECKS_PASS' or acceptance.get('issues') or acceptance.get('receipt_sha256')!=digest(receipt_path) or acceptance.get('request_sha256')!=digest(request_path) or acceptance.get('plan_sha256')!=request.get('plan_sha256'):raise ValueError('Returned QC must pass for this exact request, source and receipt; HOLD cannot be hidden by a figure')
    if not isinstance(selection,dict) or not selection:raise ValueError('Explicit nonempty result-role/path selection required')
    root=Path(output_root).resolve();outputs=receipt.get('outputs',[]);by_path={};selected={};total=0
    for row in outputs:
        if row.get('path') in by_path:raise ValueError('Ambiguous repeated output path in producer receipt')
        by_path[row.get('path')]=row
    if not set(request.get('required_roles',[]))<={r.get('role') for r in outputs}:raise ValueError('Producer is missing mandatory output roles')
    for role,names in selection.items():
        if not isinstance(names,list) or not names or len(set(names))!=len(names):raise ValueError('Each role requires explicitly selected unique output paths')
        selected[role]=[]
        for name in names:
            row=by_path.get(name)
            if row is None or row.get('role')!=role:raise ValueError('Selected path/role does not match the completed producer')
            p=_inside(root,name);total+=p.stat().st_size
            if p.stat().st_size>20*1024**2 or total>100*1024**2:raise ValueError('Prepare a smaller frozen display export on the server; no automatic large local load')
            if digest(p)!=row.get('sha256') or p.stat().st_size!=row.get('bytes'):raise ValueError('Returned artifact changed after completion')
            selected[role].append({'path':name,'sha256':row['sha256'],'bytes':row['bytes']})
    route=policy['routes'].get(backend,{'kind':'model_attribution','preferred_figures':['shap_summary','roc_multi','pr_curve','calibration','confusion'],'interpretation_boundary':'Explain a fitted output on the declared scale; validation partitions and background units remain explicit.'})
    plan={'schema':'native-figure-plan/1','state':'READY_FOR_DISPLAY_REVIEW','backend':backend,'route':route,
          'output_root':str(root),'request':request,'receipt_sha256':digest(receipt_path),'request_sha256':digest(request_path),
          'acceptance_sha256':digest(acceptance_path),'selected':selected,'bytes_verified':total,
          'analysis_performed':False,'scientific_validity_established':False,'server_live_observed':False,'private_only':True}
    plan['binding_sha256']=_binding(plan)
    return plan


def _one(plan,role,path=None):
    if plan.get('state')!='READY_FOR_DISPLAY_REVIEW' or plan.get('binding_sha256')!=_binding({k:v for k,v in plan.items() if k!='binding_sha256'}):raise ValueError('Figure plan changed; prepare a new reviewed plan')
    rows=plan['selected'].get(role,[])
    if path is not None:rows=[r for r in rows if r['path']==path]
    if len(rows)!=1:raise ValueError('Select the exact output path: missing or repeated result role '+role)
    p=_inside(Path(plan['output_root']),rows[0]['path'])
    if p.stat().st_size!=rows[0]['bytes'] or digest(p)!=rows[0]['sha256']:raise ValueError('Selected bytes changed after figure planning')
    return p


def _tsv(path,index=False):
    import pandas as pd
    with path.open(encoding='utf-8-sig',newline='') as f:
        header=next(csv.reader(f,delimiter='\t'))
    if len(header)!=len(set(header)) or any(not k for k in (header[1:] if index else header)):raise ValueError('Duplicate or missing literal table columns; no pandas header mangling')
    d=pd.read_csv(path,sep='\t',dtype=str,keep_default_na=False,index_col=0 if index else None)
    if index and (not d.index.is_unique or any(not x for x in d.index)):raise ValueError('Unique literal nonempty source row identities required')
    return d


@contextmanager
def _npz(path):
    import zipfile, numpy as np
    with zipfile.ZipFile(path) as z:
        members=z.infolist()
        if len(members)>20 or sum(m.file_size for m in members)>100*1024**2:raise ValueError('Prepare a bounded uncompressed display array export on the server')
    with np.load(path,allow_pickle=False) as value:yield value


def native_shap_data(plan,model,paths=None):
    """Read the actual native NPZ/diagnostic/summary/identity four-file output."""
    import numpy as np
    paths=paths or {};files={role:_one(plan,role,paths.get(role)) for role in ['shap_values','shap_diagnostics','shap_summary','shap_identity']}
    diag=_json(files['shap_diagnostics']);cfg=plan['request']['parameters'].get('shap',{})
    if model!=diag.get('model') or diag.get('output')!=cfg.get('output') or diag.get('background_units')!=cfg.get('background_units') or diag.get('explained_units')!=cfg.get('explain_units') or diag.get('additivity_pass') is not True:raise ValueError('SHAP model/output/background/test-unit or actual additivity QC differs from producer')
    unit=diag.get('contribution_unit')
    if not unit or 'unspecified' in unit.lower() or diag.get('link')!='identity':raise ValueError('Explicit native contribution unit and actual link required; no guessed log-odds or response units')
    with _npz(files['shap_values']) as z:
        a=np.array(z['values']);raw=np.array(z['original_feature_values']);base=np.array(z['base_values']);prediction=np.array(z['model_output']);features=z['feature_names'].astype(str).tolist();ids=z['unit_ids'].astype(str).tolist()
    if a.ndim!=2 or raw.shape!=a.shape or a.shape!=(len(ids),len(features)) or base.shape!=(len(ids),) or prediction.shape!=(len(ids),) or not np.isfinite(a).all() or not np.isfinite(raw).all() or not np.isfinite(base).all() or not np.isfinite(prediction).all() or len(set(ids))!=len(ids) or len(set(features))!=len(features):raise ValueError('Native attribution array, feature/unit identity or finite-value contract failed')
    if ids!=diag['explained_units'] or features!=diag['feature_axis']:raise ValueError('Native array identities differ from exact diagnostics')
    tolerance=float(diag['additivity_tolerance'])
    if tolerance!=cfg.get('additivity_tolerance') or not np.isfinite(tolerance) or tolerance<=0 or (np.abs(base+a.sum(axis=1)-prediction)>tolerance).any():raise ValueError('Actual output-scale SHAP additivity failed; no relabeling or refit')
    if cfg['output']=='probability' and (((prediction<0)|(prediction>1)).any() or unit!='probability'):raise ValueError('Probability explanation channel/unit mismatch')
    summary=_tsv(files['shap_summary']);identity=_tsv(files['shap_identity'])
    if summary.feature_id.tolist()!=features or not np.allclose(summary.mean_abs_shap.astype(float),abs(a).mean(axis=0),rtol=1e-6,atol=1e-9) or not np.allclose(summary.mean_shap.astype(float),a.mean(axis=0),rtol=1e-6,atol=1e-9):raise ValueError('Native full-feature summary differs from frozen contributions')
    if identity.unit_id.tolist()!=ids or not np.allclose(identity.model_output.astype(float),prediction) or not np.allclose(identity.base_value.astype(float),base) or not np.allclose(identity.sum_shap.astype(float),a.sum(axis=1)):raise ValueError('Native sample/output identity side table differs')
    total=summary.mean_abs_shap.astype(float).sum()
    if total<=0:raise ValueError('Zero contribution magnitude requires an explicit zero table')
    return {'features':features,'sample_ids':ids,'positive_class':diag.get('output_name',model),
            'feature_value_mode':'within_feature_range','share_table':[(summary.mean_abs_shap.astype(float)/total).tolist()],
            'explanation':{'shap':a,'feature_values':raw,'unit':unit,'output':cfg['output'],'link':'identity','algorithm':diag['algorithm'],
                           'scope':'locked producer test units; training-only background; not causal or external clinical validation'},
            'native_provenance':{'receipt_sha256':plan['receipt_sha256'],'request_sha256':plan['request_sha256'],'artifact_sha256':{k:digest(v) for k,v in files.items()}}}


def render_native_shap(plan,model,*,paths=None,**options):
    from renderers import render_template
    data=native_shap_data(plan,model,paths)
    fig,meta=render_template('shap_summary',data,**options)
    meta.update(native_provenance=data['native_provenance'],scientific_validity_established=False)
    return fig,meta


MATRIX_UNITS={
    'celltype_proportions':'Estimated cell-type proportion',
    'celltype_abundance':'Estimated cell abundance',
    'reference_signatures':'Reference signature (producer scale)',
    'spatial_coupling':'Transport mass', 'modality_attention':'Model attention weight',
    'program_gene_projection':'Model decoder projection', 'fused_similarity':'Fused similarity',
    'module_eigengenes':'Module eigengene', 'pathway_activity':'PROGENy footprint activity',
}


def render_native_matrix(plan,role,*,path=None,unit=None,**options):
    """Read actual numeric TSV axes, preserve missingness and avoid new clustering."""
    import numpy as np
    from renderers import render_template
    allowed=set(MATRIX_UNITS)|{'unit_expression_profiles','integrated_representation','attribute_representation'}
    if role not in allowed:raise ValueError('Prepare an explicit frozen display export for this role; no implicit model/H5AD/RDS decoding')
    p=_one(plan,role,path)
    if p.suffix.lower()!='.tsv':raise ValueError('Matrix view requires a bounded frozen TSV, not an executable/pickled scientific object')
    raw=_tsv(p,index=True);matrix=raw.replace({'NA':np.nan,'NaN':np.nan,'':np.nan}).astype(float)
    if matrix.shape[0]>2000 or matrix.shape[1]>200 or matrix.empty or np.isinf(matrix.to_numpy()).any():raise ValueError('Narrow a nonempty finite-or-missing matrix on the server before local display')
    if role in {'celltype_proportions','celltype_abundance','reference_signatures','spatial_coupling'}:
        values=matrix.to_numpy()
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('This channel requires actual finite nonnegative values; no replacement of missingness with zero')
    if role=='celltype_proportions' and not np.allclose(matrix.sum(axis=1),1,atol=1e-5,rtol=0):raise ValueError('Actual normalized proportions must sum to one; abundance is not silently renormalized')
    label=MATRIX_UNITS.get(role,unit)
    if not label:raise ValueError('Declare the producer scale of this matrix')
    if unit is not None and role in MATRIX_UNITS and unit!=label:raise ValueError('Do not relabel model abundance, attention, coupling or projections as another quantity')
    if options.get('cluster',False):raise ValueError('Native matrices retain the source order; provide a separate reviewed upstream hierarchy export for a clustered view')
    fig,meta=render_template('deg_heatmap',{'matrix':matrix},cluster=False,color_label=label,**{k:v for k,v in options.items() if k!='cluster'})
    meta.update(native_role=role,native_kind=plan['route']['kind'],source_sha256=digest(p),receipt_sha256=plan['receipt_sha256'],unit=label,
                interpretation_boundary=plan['route']['interpretation_boundary'],scientific_validity_established=False)
    return fig,meta


def render_batchie_intervals(plan,*,path=None,row_ids=None,**options):
    """Actual conditional-mean viability and Q05/Q95: 90% CrI, never 95% CI."""
    import numpy as np
    from renderers import render_template
    if plan['backend']!='batchie_posterior':raise ValueError('BATCHIE interval view requires its actual producer')
    p=_one(plan,'combination_predictions',path);table=_tsv(p)
    required=['row_id','observed','posterior_mean_viability','posterior_q05_viability','posterior_q95_viability']
    if not set(required)<=set(table) or table.row_id.duplicated().any():raise ValueError('Exact row identities and native posterior channels required')
    if row_ids is not None:
        if len(set(row_ids))!=len(row_ids) or not set(row_ids)<=set(table.row_id):raise ValueError('Select actual unique combination row IDs')
        table=table.set_index('row_id').loc[row_ids].reset_index()
    if len(table)>30:raise ValueError('Select/paginate at most 30 actual combinations per interval page')
    values=table[required[2:]].astype(float).to_numpy()
    if not np.isfinite(values).all() or ((values<0)|(values>1)).any():raise ValueError('Actual posterior viability must be finite in [0,1]')
    rows=[{'label':str(r.row_id),'estimate':float(r.posterior_mean_viability),'lo':float(r.posterior_q05_viability),'hi':float(r.posterior_q95_viability)} for r in table.itertuples()]
    fig,meta=render_template('forest',{'table':rows,'unit':'Model conditional-mean viability','null':0,'interval_label':'Mean [90% credible interval]','allow_estimate_outside_interval':True},**options)
    meta.update(interval_kind='posterior_credible_conditional_mean',interval_mass=.90,observations_not_replicated=True,source_sha256=digest(p),scientific_validity_established=False)
    return fig,meta


def render_proteintalks_checkpoints(plan,feature_ids,*,path=None,ncols=None,**options):
    """Discrete native predictions; no invented continuous physical-hour curve."""
    import numpy as np
    import matplotlib.pyplot as plt
    from design_system import use_style,WIDTH_MM,choose_grid,identity_colors,wrap_label,safe_save,finish_figure
    if plan['backend']!='proteintalks_predict':raise ValueError('Requires the exact ProteinTalks checkpoint producer')
    p=_one(plan,'proteome_predictions',path)
    with _npz(p) as z:
        values=np.array(z['protein_expression']);features=z['protein_ids'].astype(str).tolist();cases=z['case_ids'].astype(str).tolist();ticks=np.array(z['native_internal_ticks']);labels=np.array(z['physical_timepoint_labels_hours'])
    if values.shape!=(len(cases),3,len(features)) or len(set(features))!=len(features) or len(set(cases))!=len(cases) or not np.isfinite(values).all() or not np.array_equal(ticks,[1,2,3]) or not np.array_equal(labels,[6,24,48]):raise ValueError('Native checkpoint time/protein/case axis mismatch')
    if not feature_ids or len(feature_ids)>12 or len(set(feature_ids))!=len(feature_ids) or not set(feature_ids)<=set(features):raise ValueError('Select one to 12 actual protein identities per page')
    if len(cases)>8:raise ValueError('Prepare explicit case facets/pages with at most eight literal case identities')
    width=WIDTH_MM[options.get('width','double')];columns=ncols or min(len(feature_ids),max(1,int(width//55)))
    if width/columns<50:raise ValueError('Requested panel columns are too narrow; use fewer columns or a wider page')
    nr,nc=choose_grid(len(feature_ids),ncols=columns);use_style()
    fig,axes=plt.subplots(nr,nc,squeeze=False,figsize=(width/25.4,(nr*50+15)/25.4),layout='constrained')
    colors=identity_colors(options.get('theme',{'palette':'muted'}),cases)
    for ax,feature in zip(axes.flat,feature_ids):
        for i,case in enumerate(cases):ax.scatter(ticks,values[i,:,features.index(feature)],c=colors[case],s=15,label=case,edgecolors='white',linewidth=.4)
        ax.set_xticks(ticks,['6 h','24 h','48 h']);ax.set_xlabel('Trained checkpoint labels');ax.set_ylabel(plan['request']['parameters']['expression_scale']);ax.set_title(wrap_label(feature,22),loc='left',fontsize=8.5)
    for ax in axes.flat[len(feature_ids):]:ax.set_visible(False)
    axes.flat[0].legend(fontsize=6.5);finish_figure(fig)
    meta={'status':'RENDERED_UNREVIEWED','view':'discrete_native_proteintalks','internal_ticks':ticks.tolist(),'trained_labels_hours':labels.tolist(),'continuous_physical_time_model':False,'feature_ids':feature_ids,'case_ids':cases,'layout':{'rows':nr,'columns':nc},'source_sha256':digest(p),'scientific_validity_established':False}
    if options.get('outdir') is not None:meta['outputs']=safe_save(fig,options.get('stem','proteintalks_checkpoints'),options['outdir'],options.get('formats',('png','svg')),overwrite=options.get('overwrite',False))
    return fig,meta
