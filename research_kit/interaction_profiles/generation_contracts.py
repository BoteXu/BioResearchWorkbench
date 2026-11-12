"""Explicit ShEPhERD-2 inference choices; standard-library validation only."""
import math
import re

PHARM_MODES = ('inpaint', 'pharm-full', 'pharm-priority', 'pharm-priority-only')
SCAFFOLD_MODES = ('none', 'fixed', 'released', 'inpaint')
BOOL_OPTIONS = {'inpaint_x1_pos', 'inpaint_x1_x', 'inpaint_x1_bonds', 'inpaint_x1_formal_charge',
                'inpaint_x3_pos', 'inpaint_x3_x', 'inpaint_x4_pos', 'inpaint_x4_direction', 'inpaint_x4_type'}
STOP_OPTIONS = {'stop_inpainting_at_time_x1_pos', 'stop_inpainting_at_time_x1_x',
                'stop_inpainting_at_time_x1_bonds', 'stop_inpainting_at_time_x3', 'stop_inpainting_at_time_x4'}
NOISE_OPTIONS = {'add_noise_to_inpainted_x3_pos', 'add_noise_to_inpainted_x3_x',
                 'add_noise_to_inpainted_x4_pos', 'add_noise_to_inpainted_x4_direction', 'add_noise_to_inpainted_x4_type'}
BRANCHES = {
    'joint_profile': 'all native interaction modalities',
    'modality_subset': 'shape / shape+ESP / pharmacophores / explicit combinations',
    'scaffold_fixed': 'native scaffold conditioning; independent chemical-subgraph audit',
    'scaffold_only': 'condition atoms without interaction-profile conditioning',
    'scaffold_release': 'native timed scaffold release; no fixed-position guarantee',
    'atom_bond_inpainting': 'native atom/position/bond/formal-charge inpainting',
    'pharm_full': 'all pharmacophores fixed',
    'pharm_priority': 'selected points fixed; remaining points inpainted',
    'pharm_priority_only': 'only selected points retained as pharmacophore conditions',
    'profile_composition': 'native default or conditional signed-weight composition',
    'frame_control': 'origin / native auto / explicit translation restored by adapter',
    'variable_counts': 'explicit per-sample or inclusive offset ranges',
    'advanced_inpainting': 'explicit time/noise/representation controls',
    'stochastic_sampling': 'native stochastic EDM sampling parameters',
    'unconditional_control': 'native unconditional generation as a declared control',
    'neutralized_esp': 'native neutralized conditioning with distinct evaluation semantics',
}


def finite(v, minimum=None, maximum=None, positive=False):
    return type(v) in (int, float) and math.isfinite(v) and (not positive or v > 0) and (minimum is None or v >= minimum) and (maximum is None or v <= maximum)


def indices(values, bound, name, allow_empty=False):
    if (not isinstance(values, list) or (not values and not allow_empty)
            or any(type(x) is not int or not 0 <= x < bound for x in values)
            or len(values) != len(set(values))):
        raise ValueError('Exact unique zero-based ' + name + ' required; bool is not an index')


def completed_steps(value, total):
    if type(value) is int:
        if value == -1:
            return total
        if 1 <= value <= total:
            return value
    elif type(value) is float and math.isfinite(value) and 0 < value <= 1 and int(value * total) > 0:
        return int(value * total)
    raise ValueError('early_stop_edm must be -1, an absolute positive step count, or a finite fraction')


def selection_mask(selection, n_atoms, n_pharms):
    """Return explicit mask or None for native atom-to-pharmacophore resolution."""
    if not isinstance(selection, dict) or set(selection) != {'kind', 'values', 'min_ring_atoms'}:
        raise ValueError('Explicit mutually exclusive pharmacophore selector required')
    kind, values, ring = selection['kind'], selection['values'], selection['min_ring_atoms']
    if type(ring) is not int or ring < 1:
        raise ValueError('A positive min_ring_atoms count is required')
    if kind == 'none':
        if values != []:
            raise ValueError('No-selection requires an empty value list')
        return None
    if kind == 'mask':
        if not isinstance(values, list) or len(values) != n_pharms or any(type(v) is not int or v not in (0, 1) for v in values):
            raise ValueError('Mask must match the complete pinned pharmacophore axis exactly')
        return list(values)
    if kind in ('indices', 'atoms'):
        indices(values, n_pharms if kind == 'indices' else n_atoms, 'pharmacophore/atom selector')
        return [int(i in values) for i in range(n_pharms)] if kind == 'indices' else None
    raise ValueError('Unknown pharmacophore selection mode')


def validate_options(p):
    g = p['generation_options']
    fields = {'schema', 'task', 'condition_modalities', 'condition_frame', 'reference_conditions',
              'atom_condition_reference_id', 'sizes', 'sampler', 'advanced_inpaint',
              'composition_alignment', 'neutralize_esp', 'constraint_qc'}
    if not isinstance(g, dict) or set(g) != fields or g['schema'] != 'private-shepherd2-generation/2':
        raise ValueError('Exact versioned generation options required; old plans expire')
    if g['task'] not in ('profile', 'scaffold_only', 'unconditional'):
        raise ValueError('Unknown native generation task')
    mods = g['condition_modalities']
    if not isinstance(mods, list) or len(mods) != len(set(mods)) or not set(mods) <= {'shape', 'esp', 'pharm','pharm_positions','pharm_directions','pharm_type'}:
        raise ValueError('Explicit unique supported condition modalities required')
    if 'pharm' in mods and set(mods)&{'pharm_positions','pharm_directions','pharm_type'}:raise ValueError('Use full pharmacophores or explicit subfields, without redundant aliases')
    if 'esp' in mods and 'shape' not in mods:
        raise ValueError('Native ESP conditioning includes shape; do not silently add it')
    if (g['task'] == 'profile') != bool(mods):
        raise ValueError('Profile task needs modalities; scaffold-only/unconditional do not')
    frame = g['condition_frame']
    if not (isinstance(frame, str) and frame in ('origin', 'auto')):
        if not isinstance(frame, list) or len(frame) != 3 or not all(finite(v) for v in frame):
            raise ValueError('Explicit finite Angstrom translation or origin/auto required')
    if type(g['neutralize_esp']) is not bool or g['neutralize_esp'] and 'esp' not in mods:
        raise ValueError('Neutralized ESP must be an explicit active conditioning choice')
    selections = g['reference_conditions']
    if not isinstance(selections, list) or not selections:
        raise ValueError('All evaluation references need exact source/axis bindings')
    names = []
    for r in selections:
        required = {'reference_id', 'source_sdf_sha256', 'atom_axis_sha256', 'pharmacophore_axis_sha256',
                    'expected_atom_count', 'expected_pharmacophore_count', 'scaffold_mode',
                    'scaffold_atom_indices', 'exit_vector_atom_indices', 'pharm_mode', 'pharm_selection'}
        if not isinstance(r, dict) or set(r) != required:
            raise ValueError('Exact reference-specific scientific conditioning fields required')
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,70}', r['reference_id']):
            raise ValueError('Explicit safe reference identity required')
        names.append(r['reference_id'])
        if any(not re.fullmatch('[a-f0-9]{64}', r[k]) for k in ('source_sdf_sha256', 'atom_axis_sha256', 'pharmacophore_axis_sha256')):
            raise ValueError('SDF, atom axis and pharmacophore axis must all be source-bound')
        na, np_ = r['expected_atom_count'], r['expected_pharmacophore_count']
        if type(na) is not int or not 1 <= na <= p['max_atoms'] or type(np_) is not int or np_ < 0:
            raise ValueError('Exact finite reference axis denominators required')
        if set(mods)&{'pharm','pharm_positions','pharm_directions','pharm_type'} and np_==0:raise ValueError('Requested pharmacophore conditioning has no actual reference points; choose modalities explicitly')
        if r['scaffold_mode'] not in SCAFFOLD_MODES or r['pharm_mode'] not in PHARM_MODES:
            raise ValueError('Unknown scaffold or pharmacophore branch')
        indices(r['scaffold_atom_indices'], na, 'scaffold atom indices', allow_empty=r['scaffold_mode'] == 'none')
        if r['scaffold_mode'] == 'none' and r['scaffold_atom_indices']:
            raise ValueError('No scaffold mode cannot silently carry a scaffold selection')
        indices(r['exit_vector_atom_indices'], na, 'exit-vector indices', allow_empty=True)
        if not set(r['exit_vector_atom_indices']) <= set(r['scaffold_atom_indices']) or r['exit_vector_atom_indices'] and r['scaffold_mode'] != 'inpaint':
            raise ValueError('Exit-vector atoms are only a subset of an atom-inpainting selection')
        mask = selection_mask(r['pharm_selection'], na, np_)
        if r['pharm_mode'] in ('pharm-priority', 'pharm-priority-only'):
            if r['pharm_selection']['kind'] == 'none' or np_ == 0 or mask is not None and not any(mask):
                raise ValueError('Priority needs a nonempty exact selection; no all-zero fallback')
        elif r['pharm_selection']['kind'] != 'none':
            raise ValueError('Only priority modes accept a point/atom/mask selector')
        if r['pharm_mode'] != 'inpaint' and ('pharm' not in mods or not np_):
            raise ValueError('Fixed pharmacophores require active nonempty pharmacophore conditioning')
    if len(names) != len(set(names)) or len(names) != len(p['profile_weights']):
        raise ValueError('Exactly one weight and selector per unique reference, in declared order')
    if p['composition_mode'] == 'single' and len(names) != 1:
        raise ValueError('Single-profile generation has exactly one reference')
    composition = p['composition_mode'] != 'single'
    atom_id = g['atom_condition_reference_id']
    active = [r for r in selections if r['scaffold_mode'] != 'none']
    if active and (len(active) != 1 or atom_id != active[0]['reference_id']):
        raise ValueError('A single explicit atom-condition source is required; never select the first implicitly')
    if not active and atom_id is not None:
        raise ValueError('Atom-condition identity has no active scaffold')
    if active and p['profile_weights'][names.index(atom_id)] <= 0:
        raise ValueError('A negative guidance reference cannot provide a fixed scaffold')
    if g['task'] == 'scaffold_only' and not active:
        raise ValueError('Scaffold-only task requires an actual atom condition')
    if g['task'] == 'unconditional' and (active or g['neutralize_esp'] or frame != 'origin'):
        raise ValueError('Unconditional controls do not carry hidden conditions or frame offsets')
    for i, r in enumerate(selections):
        if p['profile_weights'][i] <= 0 and r['pharm_mode'] != 'inpaint':
            raise ValueError('Negative/zero guidance does not define fixed pharmacophore constraints')
    if composition:
        if g['task'] != 'profile':
            raise ValueError('Native composition is a profile task')
        modes = {r['pharm_mode'] for r in selections}
        if 'pharm-priority' in modes or len({m == 'inpaint' for m in modes}) > 1:
            raise ValueError('Native composition has one pharmacophore flag and no per-profile priority vector; do not emulate silently')
        if any(r['scaffold_mode'] == 'released' for r in active):
            raise ValueError('Timed scaffold release belongs to the single sampler, not composition')
        if frame != 'origin' and not active:
            raise ValueError('Native composition ignores COM without atom_condition; reject ignored settings')
        if active and active[0]['exit_vector_atom_indices']:
            raise ValueError('Native composition does not forward exit-vector-aware bond inpainting')
    sizes = g['sizes']
    if not isinstance(sizes, dict) or set(sizes) != {'mode', 'atoms', 'pharms'} or sizes['mode'] not in ('offset', 'offset_range', 'per_sample', 'absolute'):
        raise ValueError('Explicit generation count branch required')
    if sizes['mode'] == 'offset':
        if sizes['atoms'] is not None or sizes['pharms'] is not None:
            raise ValueError('Offset counts use the existing explicit add_atoms/add_pharms')
    elif sizes['mode'] == 'offset_range':
        for k in ('atoms', 'pharms'):
            v = sizes[k]
            if not isinstance(v, list) or len(v) != 2 or any(type(x) is not int for x in v) or v[0] > v[1]:
                raise ValueError('Inclusive signed offset ranges require ordered integer endpoints')
    elif sizes['mode'] == 'per_sample':
        for k in ('atoms', 'pharms'):
            if not isinstance(sizes[k], list) or len(sizes[k]) != p['n_samples'] or any(type(v) is not int or v < 1 for v in sizes[k]):
                raise ValueError('Per-sample atom/pharmacophore counts must cover the complete sample denominator')
    else:
        if any(type(sizes[k]) is not int or sizes[k] < 1 for k in ('atoms', 'pharms')):
            raise ValueError('Absolute positive integer counts required')
    if g['task'] == 'unconditional' and sizes['mode'] != 'absolute':
        raise ValueError('Unconditional counts cannot be inferred from an evaluation reference')
    sampler = g['sampler']
    if not isinstance(sampler, dict) or set(sampler) != {'early_stop_edm', 'sigma_max', 'sigma_min', 'rho', 'use_stochastic', 'S_churn', 'S_noise', 'use_2nd_order_correction'}:
        raise ValueError('Explicit supported native EDM settings required')
    steps = completed_steps(sampler['early_stop_edm'], p['denoise_steps'])
    if (not all(finite(sampler[k], positive=True) for k in ('sigma_max', 'sigma_min', 'rho', 'S_noise'))
            or sampler['sigma_max'] <= sampler['sigma_min'] or not finite(sampler['S_churn'], minimum=0)
            or any(type(sampler[k]) is not bool for k in ('use_stochastic', 'use_2nd_order_correction'))):
        raise ValueError('Invalid EDM schedule/noise settings')
    if composition and sampler['use_2nd_order_correction']:
        raise ValueError('Native composition has no second-order-correction argument')
    adv = g['advanced_inpaint']
    if not isinstance(adv, dict) or not set(adv) <= BOOL_OPTIONS | STOP_OPTIONS | NOISE_OPTIONS:
        raise ValueError('Unknown native inpainting option')
    if g['task'] == 'unconditional' and adv:
        raise ValueError('Unconditional controls cannot carry ignored inpainting settings')
    if g['task']=='scaffold_only' and any('x1' not in k for k in adv):raise ValueError('Scaffold-only profiles have no surface/pharmacophore fields for advanced overrides')
    hard_modes={r['pharm_mode'] for r in selections}
    if hard_modes&{'pharm-full','pharm-priority-only'} and any('x4' in k for k in adv):raise ValueError('Fixed pharmacophore branches do not consume x4 inpainting overrides')
    if 'pharm-priority' in hard_modes and any(k in BOOL_OPTIONS and 'x4' in k for k in adv):raise ValueError('Native mixed-priority mode controls x4 flags internally; only time/noise overrides remain explicit')
    for k, v in adv.items():
        if k in BOOL_OPTIONS and type(v) is not bool or k in STOP_OPTIONS and not finite(v, minimum=0, maximum=1) or k in NOISE_OPTIONS and not finite(v, minimum=0):
            raise ValueError('Invalid exact inpainting option type/range')
    if any(adv.get(k) is True for k in BOOL_OPTIONS if k.startswith('inpaint_x1')) and (not active or active[0]['scaffold_mode'] != 'inpaint'):
        raise ValueError('Atom/bond inpainting requires its own explicit branch; fixed scaffolds disable it natively')
    if active and active[0]['scaffold_mode'] == 'inpaint' and not any(adv.get(k) is True for k in BOOL_OPTIONS if k.startswith('inpaint_x1')):
        raise ValueError('Atom-inpainting branch needs an actual enabled atom/bond modality')
    if active and active[0]['scaffold_mode'] == 'fixed' and any(adv.get(k, 1) < 1 for k in ('stop_inpainting_at_time_x1_pos', 'stop_inpainting_at_time_x1_x', 'stop_inpainting_at_time_x1_bonds')):
        raise ValueError('Fixed scaffolds cannot carry release settings')
    if active and active[0]['scaffold_mode'] == 'released':
        fraction = min(adv.get(k, 1) for k in ('stop_inpainting_at_time_x1_pos', 'stop_inpainting_at_time_x1_x', 'stop_inpainting_at_time_x1_bonds'))
        if not 0 < fraction < 1 or not 1<=int(fraction * p['denoise_steps'])<steps:
            raise ValueError('Timed release must actually occur before the configured sampler finishes')
    alignment = g['composition_alignment']
    if (not isinstance(alignment, dict) or set(alignment) != {'mode', 'start_fraction', 'interval', 'ema_alpha'}
            or alignment['mode'] not in ('none', 'so3', 'se3') or not finite(alignment['start_fraction'], minimum=0, maximum=1)
            or type(alignment['interval']) is not int or alignment['interval'] < 1 or not finite(alignment['ema_alpha'], positive=True, maximum=1)):
        raise ValueError('Explicit supported native composition alignment settings required')
    if not composition and alignment['mode'] != 'none':
        raise ValueError('Composition alignment cannot silently affect a single condition')
    if alignment['mode'] == 'none' and alignment['start_fraction'] != 0:
        raise ValueError('No composition alignment maps to the native zero-length alignment window')
    if composition and alignment['mode'] != 'none' and ('esp' not in mods or alignment['start_fraction'] == 0):
        raise ValueError('Native composition aligns ESP only and requires an actual nonzero alignment window')
    effective=effective_conditioning(p)
    if g['task']=='profile' and not effective['profile_condition_present']:
        raise ValueError('Profile task has no effective image condition after overrides/stop times; declare an unconditional or scaffold-only task explicitly')
    if any(effective['effective_inpainting_flags'][k] for k in ('inpaint_x4_pos','inpaint_x4_direction','inpaint_x4_type')) and any(r['expected_pharmacophore_count']==0 for r in selections):
        raise ValueError('An enabled pharmacophore override needs actual nonempty source points, even when its raw modality label was omitted')
    if active and active[0]['scaffold_mode']=='inpaint' and not any(effective['effective_inpainting_flags'][k] for k in BOOL_OPTIONS if k.startswith('inpaint_x1')):
        raise ValueError('Atom-inpainting branch has no positive-duration effective atom or bond channel')
    if g['neutralize_esp'] and not effective['effective_inpainting_flags']['inpaint_x3_x']:
        raise ValueError('Neutralized ESP was requested but its actual conditioning channel is disabled')
    if composition and alignment['mode']!='none' and (not effective['effective_inpainting_flags']['inpaint_x3_pos'] or not effective['effective_inpainting_flags']['inpaint_x3_x'] or not expected_alignment_steps(p,effective)):
        raise ValueError('Requested composition alignment lacks effective ESP conditioning or an available native invocation under early stop and interval')
    qc = g['constraint_qc']
    qfields = {'max_scaffold_displacement_angstrom', 'max_priority_distance_angstrom', 'min_direction_cosine',
               'min_constraint_pass_fraction', 'require_scaffold_bonds', 'require_scaffold_stereochemistry',
               'require_actual_pharmacophore_recovery', 'threshold_basis'}
    if (not isinstance(qc, dict) or set(qc) != qfields
            or not all(finite(qc[k], positive=True) for k in ('max_scaffold_displacement_angstrom', 'max_priority_distance_angstrom'))
            or not finite(qc['min_direction_cosine'], minimum=0, maximum=1)
            or not finite(qc['min_constraint_pass_fraction'], positive=True, maximum=1)
            or any(qc[k] is not True for k in ('require_scaffold_bonds', 'require_scaffold_stereochemistry', 'require_actual_pharmacophore_recovery'))
            or not isinstance(qc['threshold_basis'], str) or not qc['threshold_basis'].strip()):
        raise ValueError('Prespecified interpretable actual-structure constraint QC required')
    return g


def effective_conditioning(p,resolved_priority_masks=None):
    """Derive the flags consumed by the pinned native sampler, without importing it.

    Native flags and their positive-duration application are separate: a zero-length
    inpainting window does not establish that a requested profile was conditioned on.
    Atom-to-point priority masks may be unresolved during planning; execution must
    provide the source-bound resolved masks before saving its actual contract.
    """
    g=p['generation_options'];mods=set(g['condition_modalities']);adv=g['advanced_inpaint']
    flags={k:False for k in sorted(BOOL_OPTIONS)}
    flags.update(inpaint_x3_pos='shape' in mods,inpaint_x3_x='esp' in mods,
                 inpaint_x4_pos=bool(mods&{'pharm','pharm_positions'}),
                 inpaint_x4_direction=bool(mods&{'pharm','pharm_directions'}),
                 inpaint_x4_type=bool(mods&{'pharm','pharm_type'}))
    flags.update({k:v for k,v in adv.items() if k in BOOL_OPTIONS})
    selections=g['reference_conditions'];active=next((r for r in selections if r['scaffold_mode']!='none'),None)
    if resolved_priority_masks is not None:
        if not isinstance(resolved_priority_masks,list) or len(resolved_priority_masks)!=len(selections):raise ValueError('Complete source-bound resolved priority masks required')
        for r,mask in zip(selections,resolved_priority_masks):
            if not isinstance(mask,list) or len(mask)!=r['expected_pharmacophore_count'] or any(type(v) is not int or v not in (0,1) for v in mask):raise ValueError('Resolved mask does not match its exact pharmacophore axis')
    fixed_scaffold=active is not None and active['scaffold_mode'] in ('fixed','released')
    fixed_pharm=any(r['pharm_mode']!='inpaint' for r in selections)
    unresolved=[]
    if fixed_scaffold:
        for key in flags:
            if key.startswith('inpaint_x1'):flags[key]=False
    if fixed_pharm:
        mixed=False
        for i,r in enumerate(selections):
            if r['pharm_mode']!='pharm-priority':continue
            mask=resolved_priority_masks[i] if resolved_priority_masks is not None else selection_mask(r['pharm_selection'],r['expected_atom_count'],r['expected_pharmacophore_count'])
            if mask is None:
                unresolved.append(r['reference_id']);mixed=True
            else:mixed=any(v==0 for v in mask) and any(v==1 for v in mask)
        for key in ('inpaint_x4_pos','inpaint_x4_direction','inpaint_x4_type'):flags[key]=mixed
    if g['task']=='unconditional':flags={k:False for k in flags};fixed_scaffold=False;fixed_pharm=False
    duration={
        'inpaint_x1_pos':adv.get('stop_inpainting_at_time_x1_pos',1.),
        'inpaint_x1_x':adv.get('stop_inpainting_at_time_x1_x',1.),
        'inpaint_x1_formal_charge':adv.get('stop_inpainting_at_time_x1_x',1.),
        'inpaint_x1_bonds':adv.get('stop_inpainting_at_time_x1_bonds',1.),
        'inpaint_x3_pos':adv.get('stop_inpainting_at_time_x3',1.),
        'inpaint_x3_x':adv.get('stop_inpainting_at_time_x3',1.),
        'inpaint_x4_pos':adv.get('stop_inpainting_at_time_x4',1.),
        'inpaint_x4_direction':adv.get('stop_inpainting_at_time_x4',1.),
        'inpaint_x4_type':adv.get('stop_inpainting_at_time_x4',1.)}
    finished=completed_steps(g['sampler']['early_stop_edm'],p['denoise_steps'])
    application_steps={k:min(finished,int(duration[k]*p['denoise_steps'])) if v else 0 for k,v in flags.items()}
    effective={k:bool(v and application_steps[k]>0) for k,v in flags.items()}
    modalities=[]
    if effective['inpaint_x3_pos']:modalities.append('shape')
    if effective['inpaint_x3_x']:modalities.append('esp' if effective['inpaint_x3_pos'] else 'esp_values_on_diffusing_surface')
    pharm_channels=[fixed_pharm or effective[k] for k in ('inpaint_x4_pos','inpaint_x4_direction','inpaint_x4_type')]
    if all(pharm_channels):modalities.append('pharm')
    else:
        for enabled,label in zip(pharm_channels,('pharm_positions','pharm_directions','pharm_type')):
            if enabled:modalities.append(label)
    return {'native_inpainting_flags':flags,'effective_inpainting_flags':effective,
            'inpainting_application_steps':application_steps,'effective_modalities':modalities,
            'fixed_scaffold_conditioning':fixed_scaffold,'fixed_pharmacophore_conditioning':fixed_pharm,
            'profile_condition_present':bool(modalities),
            'atom_condition_present':fixed_scaffold or any(effective[k] for k in effective if k.startswith('inpaint_x1')),
            'runtime_priority_resolution_required':unresolved,
            'scope':'pinned_native_flag_and_time_semantics_not_observed_scientific_runtime'}


def expected_alignment_steps(p,effective=None):
    """Exact loop step indices at which the pinned composition sampler can align.

    A previous D_theta prediction is required, so step zero cannot align. This is
    an expected invocation schedule, not an assertion that a server ran it.
    """
    g=p['generation_options'];alignment=g['composition_alignment']
    if p['composition_mode']=='single' or alignment['mode']=='none':return []
    effective=effective or effective_conditioning(p)
    # The pinned alignment loop checks native flags rather than replacement-window
    # stop indices. Validation separately refuses a requested ESP alignment whose
    # conditioning window is ineffective; preserve the literal call schedule here.
    flags=effective['native_inpainting_flags']
    if not flags['inpaint_x3_pos'] or not flags['inpaint_x3_x']:return []
    start=int((1.-alignment['start_fraction'])*p['denoise_steps'])
    finished=completed_steps(g['sampler']['early_stop_edm'],p['denoise_steps'])
    return [step for step in range(max(1,start),finished) if (step-start)%alignment['interval']==0]


def branch_ids(p):
    g = validate_options(p)
    ids = {'frame_control'}
    if g['task'] == 'unconditional':
        ids.add('unconditional_control')
    elif g['task'] == 'scaffold_only':
        ids.add('scaffold_only')
    else:
        ids.add('joint_profile' if set(effective_conditioning(p)['effective_modalities']) == {'shape', 'esp', 'pharm'} else 'modality_subset')
    for r in g['reference_conditions']:
        mode = r['scaffold_mode']
        if mode != 'none':
            ids.add({'fixed': 'scaffold_fixed', 'released': 'scaffold_release', 'inpaint': 'atom_bond_inpainting'}[mode])
        if r['pharm_mode'] != 'inpaint':
            ids.add({'pharm-full': 'pharm_full', 'pharm-priority': 'pharm_priority', 'pharm-priority-only': 'pharm_priority_only'}[r['pharm_mode']])
    if p['composition_mode'] != 'single': ids.add('profile_composition')
    if g['sizes']['mode'] in ('offset_range', 'per_sample'): ids.add('variable_counts')
    if g['advanced_inpaint']: ids.add('advanced_inpainting')
    if g['sampler']['use_stochastic']: ids.add('stochastic_sampling')
    if g['neutralize_esp']: ids.add('neutralized_esp')
    return sorted(ids)
