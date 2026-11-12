"""Bind explicit user-selected constraints to actual returned reference axes; preparation only."""
import copy
from pathlib import Path
from contracts import read, sha, selected
from acceptance import inspect
from generation_contracts import validate_options


def bind_selections(reference_request_path, returned_root, returned_names, project, variant):
    reference = read(reference_request_path)
    if reference['method'] != 'prepare_reference_profiles':
        raise ValueError('A real reference-axis preparation request is required')
    result = inspect(reference_request_path, returned_root, returned_names)
    if result['state'] != 'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW':
        raise ValueError('Reference profiles or complete returned axes are on HOLD')
    variants = {'primary'} | {x['label'] for x in reference['sensitivity_variants']}
    if variant not in variants:
        raise ValueError('Select an actual reviewed reference preparation variant')
    axes_path = selected(returned_root, variant + '/reference_axis_index.private.json')
    axes = {x['reference_id']: x for x in read(axes_path)}
    draft = copy.deepcopy(project)
    if draft.get('method') != 'shepherd2_generate' or draft.get('server_execution_authorized') is not False or draft.get('public_upload') is not False:
        raise ValueError('Only a private disabled generation draft can be bound')
    source_manifest=read(selected(returned_root,'source_structures.private.json'))
    actual_order=[x['id'] for x in source_manifest['molecules'] if x['role']=='reference']
    requested_order=[x['reference_id'] for x in draft['parameters']['generation_options']['reference_conditions']]
    if requested_order!=actual_order:raise ValueError('Reference subset/reordering requires a separately reviewed derived source manifest; do not bind it to the unchanged full manifest')
    # Explicit atom and point choices stay exactly as supplied; no automatic scaffold/point selection.
    for row in draft['parameters']['generation_options']['reference_conditions']:
        actual = axes.get(row['reference_id'])
        if actual is None:
            raise ValueError('Requested reference does not exist in the actual prepared profile set')
        for field in ('source_sdf_sha256', 'atom_axis_sha256', 'pharmacophore_axis_sha256'):
            row[field] = actual[field]
        row['expected_atom_count'] = len(actual['atom_axis'])
        row['expected_pharmacophore_count'] = len(actual['pharmacophore_axis'])
    bound_inputs = {x['id']: x for x in reference['inputs']}
    for row in draft['inputs']:
        if row['id'] in ('structure_manifest', 'context'):
            row['sha256'] = bound_inputs[row['id']]['sha256']
    validate_options(draft['parameters'])
    draft['example_only'] = True
    draft['reference_selection_provenance'] = {
        'source_request_sha256': sha(reference_request_path),
        'source_receipt_sha256': sha(Path(returned_root) / 'receipt.private.json'),
        'source_reference_axes_sha256': sha(axes_path), 'source_variant': variant,
        'source_frame_id': read(selected(returned_root,'source_context.private.json'))['frame_id'],
        'source_preparation_domain_sha256': read(selected(returned_root,'source_context.private.json'))['preparation_domain_sha256'],
        'state': 'BOUND_TO_ACTUAL_REFERENCE_AXES_REQUIRES_REVIEW',
        'scientific_acceptance': 'NOT_ESTABLISHED', 'automatic_execution': False}
    return draft
