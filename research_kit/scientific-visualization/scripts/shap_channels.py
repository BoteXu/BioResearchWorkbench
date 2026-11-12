"""Validate frozen attributions and prepare display-only colors and shares.

No explainer, predictor, model fitting or scientific resampling is imported.
Units follow the explained output/link, never the example dataset or algorithm.
"""
import numpy as np


def contribution_unit(data):
    explanation = data.get('explanation', {})
    unit = explanation.get('unit', data.get('unit'))
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError('Declare the actual SHAP contribution unit; probability, decision score and log-odds are not interchangeable')
    output = explanation.get('output')
    if output == 'probability' and explanation.get('link', 'identity') == 'identity' and unit not in {'probability', 'probability units'}:
        raise ValueError('Identity-link probability explanations must retain probability units; no implicit logit or percentage conversion')
    return unit


def prepare_shap_display(data):
    """Return a private copy plus auditable display metadata, preserving raw values."""
    d = dict(data)
    e = dict(d.get('explanation', {}))
    d['explanation'] = e
    unit = contribution_unit(d)
    names = list(d.get('features', []))
    if not names or any(not isinstance(s, str) or not s for s in names) or len(set(names)) != len(names):
        raise ValueError('Literal nonempty unique feature identities required')
    classes = d.get('class_contributions')
    if classes is None:
        classes = [{'label': d.get('positive_class', e.get('output_name', 'Supplied output')),
                    'shap': e.get('shap'), 'feature_values': e.get('feature_values'),
                    'original_feature_values': e.get('original_feature_values',e.get('feature_values'))}]
    prepared, magnitudes, color_bounds = [], [], []
    mode = d.get('feature_value_mode', 'declared' if 'feature_value_limits' in d else 'within_feature_range')
    if mode not in {'declared', 'within_feature_range'}:
        raise ValueError('feature_value_mode must be declared or within_feature_range')
    for c in classes:
        a, v = np.asarray(c.get('shap'), float), np.asarray(c.get('feature_values'), float)
        if a.ndim != 2 or a.shape != v.shape or not len(a) or a.shape[1] != len(names) or not np.isfinite(a).all() or not np.isfinite(v).all():
            raise ValueError('Finite nonempty aligned observations × features required for each actual explained output')
        if c.get('unit', unit) != unit:
            raise ValueError('Different contribution units require separate pages')
        raw = np.asarray(c.get('original_feature_values', v), float)
        if raw.shape != v.shape or not np.isfinite(raw).all():
            raise ValueError('Original feature values must preserve the literal contribution axes')
        if mode == 'within_feature_range':
            lo, hi = raw.min(axis=0), raw.max(axis=0)
            span = hi - lo
            colors = np.divide(raw-lo, span, out=np.full_like(raw, .5), where=span > 0)
            color_bounds.append({'min': lo.tolist(), 'max': hi.tolist(), 'constant_features': [names[j] for j in np.flatnonzero(span == 0)]})
        else:
            limits = np.asarray(d.get('feature_value_limits'), float)
            if limits.shape != (2,) or not np.isfinite(limits).all() or limits[0] >= limits[1] or not d.get('feature_value_label'):
                raise ValueError('A declared color channel requires finite increasing limits and its actual feature-value label')
            colors = v
        prepared.append({**c, 'shap': a, 'feature_values': colors, 'original_feature_values': raw})
        magnitudes.append(np.abs(a).mean(axis=0))
    magnitude = np.stack(magnitudes)
    totals = magnitude.sum(axis=1)
    if (totals <= 0).any():
        raise ValueError('Zero total attribution magnitude: use a zero table, not an empty rose')
    # This is an exact presentation summary of supplied contributions, not a new
    # scientific estimate or a replacement explanation. The full denominator is retained.
    expected = magnitude / totals[:, None]
    supplied = d.get('share_table')
    if supplied is not None:
        supplied = np.asarray(supplied, float)
        if supplied.shape != expected.shape or not np.isfinite(supplied).all() or not np.allclose(supplied, expected, rtol=1e-6, atol=1e-9):
            raise ValueError('Supplied full-denominator shares disagree with frozen contributions')
        shares, share_source = supplied, 'supplied_full_denominator_table_verified'
    else:
        shares, share_source = expected, 'display_only_mean_absolute_summary_of_all_supplied_contributions'
    d['share_table'] = shares
    if 'class_contributions' in d:
        d['class_contributions'] = prepared
    else:
        e.update(shap=prepared[0]['shap'], feature_values=prepared[0]['feature_values'],
                 original_feature_values=prepared[0]['original_feature_values'])
    if mode == 'within_feature_range':
        d.update(feature_value_limits=[0, 1], feature_value_label='Within-feature value', feature_value_mode=mode)
    e['unit'] = unit
    meta = {'unit': unit, 'explainer': e.get('algorithm', 'supplied upstream explanation'),
            'explanation_scope': e.get('scope', 'UNSPECIFIED_NOT_VALIDATED'),
            'output': e.get('output', 'unspecified'), 'link': e.get('link', 'unspecified'),
            'share_source': share_source, 'full_feature_magnitude': magnitude.tolist(),
            'full_feature_shares': shares.tolist(), 'feature_value_mode': mode,
            'color_bounds_per_output': color_bounds,
            'feature_colors_are_display_only': True, 'refit': False}
    return d, meta
