"""Consume the existing FigureHandoff v1 contract; display stored channels only."""
from pathlib import Path
import json
from figure_handoff_contract import validate_handoff


def handoff_plan(handoff_path):
    p=Path(handoff_path)
    if p.stat().st_size>2*1024**2:raise ValueError('Narrow the selected handoff')
    value=json.loads(p.read_text(encoding='utf-8-sig'))
    check=validate_handoff(value,p.parent)
    return value,check


def render_handoff_pca(handoff_path,**options):
    """Render declared original PC axes, identities and explained variance."""
    import pandas as pd
    from native_figures import _tsv
    from renderers import render_template
    value,check=handoff_plan(handoff_path);spec=value['figure_spec']
    if spec.get('type')!='pca_samples':raise ValueError('This entry consumes an actual stored-PCA FigureSpec only')
    fields=spec.get('channels',{})
    if set(fields)!={'id','group','x','y'} or len(set(fields.values()))!=4:raise ValueError('Explicit unique stored PCA identity/group/coordinate channels required')
    path=Path(value['table']['path']);path=path if path.is_absolute() else Path(handoff_path).parent/path
    table=_tsv(path)
    if not set(fields.values())<=set(table) or table[fields['id']].duplicated().any() or (table[[fields['id'],fields['group']]]=='').any().any():raise ValueError('Actual complete literal sample/group channels required')
    coordinates=table[[fields['x'],fields['y']]].astype(float).to_numpy()
    order=spec.get('group_order',list(dict.fromkeys(table[fields['group']])))
    data={'sample_ids':table[fields['id']].tolist(),'groups':table[fields['group']].tolist(),'pca':coordinates,
          'pca_variance':spec.get('pca_variance'),'group_order':order,'biological_unit':value['context']['independent_unit']}
    fig,meta=render_template('pca_samples',data,**options)
    meta.update(handoff=check,context=value['context'],upstream_values_recomputed=False,source_binding=value['binding_sha256'])
    return fig,meta
