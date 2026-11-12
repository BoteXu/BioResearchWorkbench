"""Native conditional inference, reached only on an explicitly approved compute host."""
from pathlib import Path
import copy,math
from contracts import read, write, sha, digest
from generation_contracts import validate_options, selection_mask, branch_ids, completed_steps, effective_conditioning, expected_alignment_steps


def run_generation(request, ids, root, out, seed, profiles, molecules, references,
                   molecule_qc, partial_charges, make_profile, score):
    try:
        from .runtime import guard
        from .constraint_qc import ConstraintAuditor
    except ImportError:
        from runtime import guard
        from constraint_qc import ConstraintAuditor
    guard(request)
    import numpy as np
    import shepherd
    from rdkit import Chem
    from shepherd import load_model
    from shepherd.interaction_profile import extract_interaction_profile, InteractionProfile, InpaintAdvancedOptions
    from shepherd.extract import create_rdkit_molecule
    from material_contracts import checkpoint as review_checkpoint

    p = request['parameters']
    g = validate_options(p)
    software = read(ids['software'])
    if Path(shepherd.__file__).resolve().parent != Path(software['source_roots']['shepherd2']).resolve():
        raise ValueError('Imported native model differs from reviewed source root')
    assets = read(ids['checkpoint_manifest'])
    checkpoint, license_file = review_checkpoint(assets, root)
    selected = g['reference_conditions']
    if [r['id'] for r in references] != [r['reference_id'] for r in selected]:
        raise ValueError('Reference input order/identity differs from complete conditioning denominator')
    has_fixed = any(r['scaffold_mode'] in ('fixed', 'released') or r['pharm_mode'] != 'inpaint' for r in selected)
    auditor = ConstraintAuditor(request)
    conditions, targets, masks, snapshots = [], [], [], []
    for row, selection in zip(references, selected):
        mol, evaluated = molecules[row['id']], profiles[row['id']]
        if selection['source_sdf_sha256'] != row['sdf']['sha256']:
            raise ValueError('Scaffold/pharmacophore selection refers to a different source SDF')
        atom_axis = [{'atomic_number': a.GetAtomicNum(), 'formal_charge': a.GetFormalCharge(), 'isotope': a.GetIsotope()} for a in mol.GetAtoms()]
        # Stable chemically defined point ordering; stochastic surface sampling is separate.
        point_axis = [{'type': int(t), 'position_angstrom': [round(float(x), 6) for x in pos],
                       'direction': [round(float(x), 6) for x in vec]}
                      for t, pos, vec in zip(evaluated.pharm_types, evaluated.pharm_ancs, evaluated.pharm_vecs)]
        if (len(atom_axis) != selection['expected_atom_count'] or len(point_axis) != selection['expected_pharmacophore_count']
                or digest(atom_axis) != selection['atom_axis_sha256'] or digest(point_axis) != selection['pharmacophore_axis_sha256']):
            raise ValueError('Actual reference atom/pharmacophore axis changed after selection review')
        target = extract_interaction_profile(Chem.Mol(mol), xtb_optimize=False,
                    partial_charges=np.asarray(evaluated.partial_charges), center=False,
                    solvent=p['solvent'], num_surf_points=75, probe_radius=.6,
                    neutralize_esp=g['neutralize_esp'])
        if (target is None or np.asarray(target.surface).shape != (75, 3)
                or not np.isfinite(target.surface).all() or not np.isfinite(target.electrostatics).all()
                or not np.allclose(target.partial_charges, evaluated.partial_charges)
                or not np.array_equal(target.pharm_types, evaluated.pharm_types)
                or not np.allclose(target.pharm_positions, evaluated.pharm_ancs)
                or not np.allclose(target.pharm_directions, evaluated.pharm_vecs)):
            raise ValueError('Native conditioning profile changed the charge or selected point axis')
        condition = target
        if selection['scaffold_mode'] != 'none':
            condition = condition.with_condition_atoms(selection['scaffold_atom_indices'],
                         exit_vector_inds=selection['exit_vector_atom_indices'] or None)
        mask = selection_mask(selection['pharm_selection'], mol.GetNumAtoms(), target.n_pharms)
        if selection['pharm_selection']['kind'] == 'atoms':
            labels = target.pharm_prioritization_labels(selection['pharm_selection']['values'],
                        min_ring_priority_atoms=selection['pharm_selection']['min_ring_atoms'])
            mask = [int(v) for v in labels]
        mode = selection['pharm_mode']
        if mode in ('pharm-priority', 'pharm-priority-only'):
            if len(mask) != target.n_pharms or any(type(v) is not int or v not in (0, 1) for v in mask) or not any(mask):
                raise ValueError('Atom-to-point priority selected no actual points or changed the reviewed axis')
        if mode == 'pharm-full': mask = [1] * target.n_pharms
        if mode == 'inpaint': mask = [0] * target.n_pharms
        if mode == 'pharm-priority-only':
            condition = condition.subselection_pharm(pharm_prioritization_labels=mask)
            if condition.n_pharms != sum(mask):
                raise ValueError('Priority-only point subset did not preserve the exact requested denominator')
        if g['task'] == 'scaffold_only':
            condition = InteractionProfile.from_condition_atoms(mol, inds=selection['scaffold_atom_indices'],
                          exit_vector_inds=selection['exit_vector_atom_indices'] or None)
        targets.append(copy.deepcopy(target))
        conditions.append(condition)
        masks.append(mask)
        snapshots.append({'reference_id': row['id'], 'source_sdf_sha256': row['sdf']['sha256'],
                          'atom_axis': atom_axis, 'atom_axis_sha256': digest(atom_axis),
                          'pharmacophore_axis': point_axis, 'pharmacophore_axis_sha256': digest(point_axis),
                          'scaffold_mode': selection['scaffold_mode'], 'scaffold_atom_indices': selection['scaffold_atom_indices'],
                          'pharm_mode': mode, 'resolved_priority_mask_on_full_reference_axis': mask,
                          'conditioned_pharmacophore_count': condition.n_pharms,
                          'conditioning_ESP_neutralized': g['neutralize_esp'],
                          'evaluation_ESP': 'raw_GFN2_xTB_Coulomb_surface'})
    atom_index = next((i for i, x in enumerate(selected) if x['reference_id'] == g['atom_condition_reference_id']), None)
    actual_conditioning=effective_conditioning(p,masks)
    alignment_schedule=expected_alignment_steps(p,actual_conditioning)
    scaffold = selected[atom_index]['scaffold_mode'] in ('fixed', 'released') if atom_index is not None else False
    pharm = any(r['pharm_mode'] != 'inpaint' for r in selected)
    # Counts are resolved once per technical variant. Equal (N_x1,N_x4) cases are batched
    # through native scalar-count calls, including the composition API which has no lists.
    sizes = g['sizes']
    rng = np.random.default_rng(seed)
    base_atoms, base_pharms = selected[0]['expected_atom_count'], selected[0]['expected_pharmacophore_count']
    count_rows = []
    floor_atoms = max(1, len(selected[atom_index]['scaffold_atom_indices']) if atom_index is not None else 0)
    floor_pharms = max([1] + [c.n_pharms for c in conditions if set(g['condition_modalities'])&{'pharm','pharm_positions','pharm_directions','pharm_type'}])
    for i in range(p['n_samples']):
        if sizes['mode'] == 'offset':
            na, nf = base_atoms + p['add_atoms'], base_pharms + p['add_pharms']
        elif sizes['mode'] == 'offset_range':
            na = base_atoms + int(rng.integers(sizes['atoms'][0], sizes['atoms'][1] + 1))
            nf = base_pharms + int(rng.integers(sizes['pharms'][0], sizes['pharms'][1] + 1))
        elif sizes['mode'] == 'per_sample': na, nf = sizes['atoms'][i], sizes['pharms'][i]
        else: na, nf = sizes['atoms'], sizes['pharms']
        if not floor_atoms <= na <= p['max_atoms'] or not floor_pharms <= nf <= p['max_atoms']:
            raise ValueError('Requested per-sample sizes violate the actual active condition floors or reviewed atom/point budget')
        count_rows.append({'candidate_id': 'generated_' + str(i), 'N_x1': na, 'N_x4': nf})
    model = load_model(local_checkpoint_path=str(checkpoint), force_download=False, inference_only=True, device=p['device'])
    if str(model.device).split(':')[0]!=p['device']:raise ValueError('Native checkpoint loading silently selected a different compute device')
    if has_fixed and model.params.get('scaffold_conditioning') is not True:
        raise ValueError('Actual checkpoint lacks the native trained fixed-condition feature flag')
    if model.params['dataset']['x3']['num_points'] != 75:
        raise ValueError('Actual checkpoint surface axis is incompatible with reviewed conditioning')
    contract = {'schema': 'private-native-generation-contract/2', 'plan_sha256': request['plan_sha256'],
                'generation_options_sha256': digest(g), 'branch_ids': branch_ids(p), 'seed': seed,
                'reference_snapshots': snapshots, 'resolved_sample_counts': count_rows,
                'composition_mode': p['composition_mode'], 'profile_weights': p['profile_weights'],
                'implicit_unconditional_weight': 1 - sum(p['profile_weights']) if p['composition_mode'] == 'default' else None,
                'checkpoint_sha256': sha(checkpoint), 'checkpoint_fixed_condition_feature': model.params.get('scaffold_conditioning'),
                'condition_frame': g['condition_frame'], 'threshold_basis': g['constraint_qc']['threshold_basis'],
                'native_surface_points': 75, 'native_probe_radius_angstrom': .6,
                'count_batching': 'equal_count_scalar_native_calls; grouping_changes_RNG_stream_not_biological_replication',
                'native_early_stop_steps': completed_steps(g['sampler']['early_stop_edm'], p['denoise_steps']),
                'effective_conditioning':actual_conditioning,'expected_alignment_steps':alignment_schedule,
                'alignment_execution_scope':'expected_native_call_schedule_not_observed_execution',
                'moved_pose_requires_new_QC': True, 'scientific_acceptance': 'NOT_ESTABLISHED', 'public_upload': False}
    write(out / 'generation_contract.private.json', contract)
    contract_sha = sha(out / 'generation_contract.private.json')
    score_rows, denominator, eligible, constraints, success_smiles = [], [], [], [], set()
    chemical_success = 0
    candidate_summaries=[]
    frame = np.asarray(g['condition_frame'], dtype=float) if isinstance(g['condition_frame'], list) else g['condition_frame']
    modalities = set(g['condition_modalities']) if g['condition_modalities'] else set()
    # Native explicit COM subtracts the supplied translation without auto-restoration.
    restore = np.asarray(g['condition_frame'], dtype=float) if isinstance(g['condition_frame'], list) else np.zeros(3)
    adv = InpaintAdvancedOptions(**g['advanced_inpaint']) if g['advanced_inpaint'] else None
    for start in range(0, p['n_samples'], p['batch_size']):
        groups = {}
        for index in range(start, min(start + p['batch_size'], p['n_samples'])):
            count = count_rows[index]
            groups.setdefault((count['N_x1'], count['N_x4']), []).append(index)
        for (na, nf), indices in groups.items():
            sampler = dict(g['sampler'])
            kwargs = dict(batch_size=len(indices), N_x1=na, N_x4=nf,
                          condition_modalities=modalities, condition_center_of_mass=frame,
                          inpaint=adv, scaffold_conditioning=scaffold, pharmacophore_conditioning=pharm,
                          num_steps=p['denoise_steps'], shepherd_pred=True, verbose=False, **sampler)
            # Sampling errors are recorded for the entire requested group; no hidden retry.
            batch_error = None
            try:
                if p['composition_mode'] == 'single':
                    priority = masks[0] if selected[0]['pharm_mode'] == 'pharm-priority' else None
                    samples = model.generate(condition=None if g['task'] == 'unconditional' else conditions[0],
                              pharmacophore_prioritization=priority, **kwargs)
                else:
                    kwargs.pop('use_2nd_order_correction')
                    align = g['composition_alignment']
                    # No alignment uses a zero-length native window and its valid SO(3) enum.
                    samples = model.generate_composition(profiles=conditions, weights_conditions=np.asarray(p['profile_weights']),
                              composition_mode=p['composition_mode'], atom_condition=conditions[atom_index] if atom_index is not None else None,
                              alignment_start_frac=align['start_fraction'], alignment_interval=align['interval'],
                              alignment_mode='so3' if align['mode'] == 'none' else align['mode'], alignment_ema_alpha=align['ema_alpha'], **kwargs)
                if len(samples) != len(indices): raise ValueError('Native sampling denominator differs from requested group')
            except Exception as error:
                samples = [None] * len(indices)
                batch_error = str(error)
            for index, original_sample in zip(indices, samples):
                identity = 'generated_' + str(index)
                row = {'candidate_id': identity, 'state': 'FAILED_CHEMISTRY_OR_CONSTRAINT_QC', 'reason': '',
                       'formal_charge': p['generated_formal_charge'], 'canonical_isomeric_smiles': ''}
                report = {'schema': 'private-candidate-constraint-QC/2', 'candidate_id': identity,
                          'generation_contract_sha256': contract_sha, 'generation_options_sha256': digest(g),
                          'native_output_to_source_translation_angstrom': restore.tolist(),
                          'actual_structure_QC': False, 'chemical_valid':False,'constraints_passed': False,
                          'hard_constraints_assessed':False,'eligible':False,
                          'profile_fidelity_scores':[{'reference_id':ref['id'],'guidance_weight':p['profile_weights'][j],
                              'guidance_direction':guidance_direction(p['profile_weights'][j]),'scoring_state':'NOT_ASSESSED',
                              'shape_similarity':None,'esp_surface_similarity':None,'pharmacophore_similarity':None,
                              'scope':'raw_GFN2_xTB_ligand_profile_similarity_not_binding_energy_or_selectivity'} for j,ref in enumerate(references)],
                          'reference_results': [], 'experimental_binding_established': False}
                saved_sdf = None
                try:
                    if batch_error: raise ValueError('Native sampling group failed: ' + batch_error)
                    sample = copy.deepcopy(original_sample)
                    def save_raw(path, s):
                        np.savez_compressed(path, atoms=np.asarray(s.atoms), positions=np.asarray(s.positions),
                            formal_charges=np.asarray(s.formal_charges), bonds=np.asarray(s.bonds), surface=np.asarray(s.surface),
                            esp=np.asarray(s.electrostatics), pharm_types=np.asarray(s.pharm_types),
                            pharm_positions=np.asarray(s.pharm_positions), pharm_vectors=np.asarray(s.pharm_directions))
                    save_raw(out / (identity + '.native.npz'), sample)
                    for key in ('x1', 'x2', 'x3', 'x4'):
                        sample[key]['positions'] = np.asarray(sample[key]['positions']) + restore
                    save_raw(out / (identity + '.raw.npz'), sample)
                    atom, pos = np.asarray(sample.atoms), np.asarray(sample.positions)
                    if atom.ndim != 1 or len(atom) != na or pos.shape != (len(atom), 3) or not np.isfinite(pos).all():
                        raise ValueError('Native generated atom/count/coordinate axis differs from resolved schedule')
                    if np.asarray(sample.pharm_types).shape != (nf,):
                        raise ValueError('Native generated pharmacophore denominator differs from resolved schedule')
                    mol = create_rdkit_molecule(sample, charge=p['generated_formal_charge'])
                    converted = molecule_qc(mol)
                    kept, elements = pos[atom > 0], atom[atom > 0]
                    if len(converted) != len(kept) or list(elements) != [a.GetAtomicNum() for a in mol.GetAtoms()] or not np.allclose(converted, kept, atol=.000501, rtol=0):
                        raise ValueError('Native chemical conversion changed the atom axis or fixed geometry beyond XYZ rounding')
                    if Chem.GetFormalCharge(mol) != p['generated_formal_charge']:
                        raise ValueError('Generated formal charge differs from prespecified reconstruction state')
                    smiles = Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True)
                    state_id=request['run_id']+'__'+out.name+'__'+identity
                    mol.SetProp('BRW_STATE_ID',state_id)
                    mol.SetProp('BRW_PARENT_ID','UNASSESSED_GENERATED_PARENT')
                    mol.SetProp('BRW_MICROSTATE_ID',smiles)
                    mol.SetProp('BRW_GENERATION_PLAN_SHA256',request['plan_sha256'])
                    mol.SetProp('BRW_GENERATION_OPTIONS_SHA256',digest(g))
                    saved_sdf = out / (identity + '.sdf')
                    writer = Chem.SDWriter(str(saved_sdf)); writer.write(mol); writer.close()
                    saved=list(Chem.SDMolSupplier(str(saved_sdf),removeHs=False,sanitize=True))
                    if len(saved)!=1 or saved[0] is None:raise ValueError('Saved candidate SDF failed actual readback')
                    persisted=saved[0];saved_coordinates=molecule_qc(persisted)
                    if (not np.allclose(saved_coordinates,converted,atol=1e-7,rtol=0)
                            or [a.GetAtomicNum() for a in persisted.GetAtoms()]!=[a.GetAtomicNum() for a in mol.GetAtoms()]
                            or persisted.GetProp('BRW_STATE_ID')!=state_id
                            or persisted.GetProp('BRW_PARENT_ID')!='UNASSESSED_GENERATED_PARENT'
                            or persisted.GetProp('BRW_MICROSTATE_ID')!=smiles
                            or Chem.MolToSmiles(Chem.RemoveHs(persisted),isomericSmiles=True)!=smiles):
                        raise ValueError('Saved SDF changed coordinates, atom/state identity or stereochemical graph')
                    mol=persisted
                    report['actual_structure_QC'] = True
                    report['chemical_valid']=True
                    row['canonical_isomeric_smiles']=smiles
                    report['saved_SDF_readback_verified']=True
                    report['actual_sdf'] = {'path': saved_sdf.name, 'sha256': sha(saved_sdf), 'bytes': saved_sdf.stat().st_size,'state_id':state_id,'parent_id':'UNASSESSED_GENERATED_PARENT','microstate_id':smiles}
                    chemical_success += 1
                    q=partial_charges(mol,identity);obj=make_profile(mol,q)
                    report['quantum_charge_QC']=True
                    for ref,observed in zip(references,report['profile_fidelity_scores']):
                        try:
                            sc=score(profiles[ref['id']],obj)
                            observed.update(scoring_state='SCORED',shape_similarity=sc[0],esp_surface_similarity=sc[1],pharmacophore_similarity=sc[2])
                        except Exception as error:
                            observed.update(scoring_state='FAILED',error=str(error))
                    raw_formal_charges=np.asarray(sample.formal_charges)
                    if raw_formal_charges.shape!=(len(atom),) or not np.issubdtype(raw_formal_charges.dtype,np.integer):raise ValueError('Generated formal-charge head atom axis is invalid')
                    if np.asarray(sample.bonds).shape!=(len(atom)*(len(atom)-1)//2,):raise ValueError('Generated bond-head pair denominator is invalid')
                    report['native_XYZ_reconstruction_scope']={'fixed_reconstruction_formal_charge':p['generated_formal_charge'],'generated_formal_charge_head_sum':int(raw_formal_charges[atom>0].sum()),'native_bond_head_used_by_converter':False,'actual_bonds_inferred_from_XYZ_then_independently_audited':True}
                    raw_surface, raw_esp = np.asarray(sample.surface), np.asarray(sample.electrostatics)
                    if raw_surface.shape != (75, 3) or raw_esp.shape != (75,) or not np.isfinite(raw_surface).all() or not np.isfinite(raw_esp).all():
                        raise ValueError('Generated joint ESP head is incomplete/nonfinite')
                    distances = np.linalg.norm(raw_surface[:, None, :] - converted[None, :, :], axis=2)
                    if (distances < 1e-6).any(): raise ValueError('Generated surface contains an atomic potential singularity')
                    rmse = float(np.sqrt(np.mean((obj.get_electrostatic_potential(surf_pos=raw_surface) - raw_esp) ** 2)))
                    report['raw_ESP_head_vs_raw_recomputed_Coulomb_RMSE'] = rmse
                    report['ESP_consistency_scope'] = 'raw_partial_charge_joint_head_diagnostic; not_DFT_truth; neutralized_condition_separate'
                    for i, selection in enumerate(selected):
                        if g['task'] == 'unconditional' or p['profile_weights'][i] <= 0:
                            continue
                        result = auditor.evaluate(molecules[references[i]['id']], mol, targets[i], obj, sample,
                                                  selection, [j for j, bit in enumerate(masks[i]) if bit])
                        report['reference_results'].append(result)
                    report['constraints_passed'] = all(x['passed'] for x in report['reference_results'])
                    report['hard_constraints_assessed']=all(x.get('assessment_complete',True) for x in report['reference_results'])
                    row['canonical_isomeric_smiles'] = smiles
                    if not report['hard_constraints_assessed']:
                        row['state']='HOLD_SEARCH_INCOMPLETE'
                        raise ValueError('Scaffold mapping search reached its declared cap without establishing constraint recovery')
                    if not report['constraints_passed']:
                        raise ValueError('Saved chemistry or reextracted pharmacophores fail the prespecified constraints')
                    if any(x['scoring_state']!='SCORED' for x in report['profile_fidelity_scores']):raise ValueError('One or more requested reference profile scores failed; preserve hard-constraint assessment separately')
                    for ref,observed in zip(references,report['profile_fidelity_scores']):
                        sc=tuple(observed[k] for k in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity'))
                        score_rows.append({'candidate_id': identity, 'parent_id': 'UNASSESSED_GENERATED_PARENT', 'microstate_id': smiles,
                            'reference_id':ref['id'],
                            'role': 'generated', 'shape_similarity': sc[0], 'esp_surface_similarity': sc[1],
                            'pharmacophore_similarity': sc[2], 'pharmacophore_assessed': sc[2] is not None,
                            'coordinate_mode': 'generated_source_frame_reference_' + ref['id'], 'protein_ligand_energy_estimated': False})
                    row['state'] = 'CHEMICAL_QC_PASSED_REQUIRES_DOCKING'
                    success_smiles.add(smiles)
                except Exception as error:
                    row['reason'] = str(error)
                    # Partially computed scores from a failed candidate must not enter accepted results.
                    score_rows = [x for x in score_rows if x['candidate_id'] != identity]
                report['state'] = row['state']; report['failure_reason'] = row['reason']
                report['eligible']=row['state']=='CHEMICAL_QC_PASSED_REQUIRES_DOCKING'
                report_path = out / (identity + '.constraints.private.json')
                write(report_path, report)
                passed = row['state'] == 'CHEMICAL_QC_PASSED_REQUIRES_DOCKING'
                if passed:
                    eligible.append({'candidate_id': identity, 'parent_id': 'UNASSESSED_GENERATED_PARENT',
                        'state_id':state_id,
                        'microstate_id': row['canonical_isomeric_smiles'], 'path': saved_sdf.name,
                        'sha256': sha(saved_sdf), 'bytes': saved_sdf.stat().st_size, 'eligibility': 'REQUIRES_NEW_DOWNSTREAM_QC',
                        'constraints_passed': True, 'constraint_report_path': report_path.name,
                        'constraint_report_sha256': sha(report_path), 'generation_contract_sha256': contract_sha,
                        'generation_options_sha256': digest(g)})
                constraints.append({'candidate_id': identity, 'state': row['state'], 'actual_structure_QC': report['actual_structure_QC'],
                    'constraints_passed': report['constraints_passed'], 'report_path': report_path.name, 'report_sha256': sha(report_path),
                    'generation_contract_sha256': contract_sha, 'generation_options_sha256': digest(g)})
                denominator.append(row)
                candidate_summaries.append({k:report[k] for k in ('candidate_id','chemical_valid','constraints_passed','hard_constraints_assessed','eligible','profile_fidelity_scores')})
    if sha(checkpoint) != assets['sha256'] or sha(license_file) != assets['license_document']['sha256']:
        raise ValueError('Trusted checkpoint or license changed during generation')
    counts=summarize_generation_counts(candidate_summaries,p['n_samples'],len(success_smiles))
    if counts['metrics']['chemical_valid_count']!=chemical_success:raise ValueError('Chemical validity counter differs from complete persisted candidate reports')
    fidelity=summarize_profile_fidelity(references,p['profile_weights'],candidate_summaries,p['n_samples'])
    return {'score_rows': score_rows, 'denominator': denominator, 'eligible': eligible, 'constraint_rows': constraints,
            'metrics': counts['metrics'],'deprecated_scope':counts['deprecated_scope'],
            'effective_conditioning':actual_conditioning,'expected_alignment_steps':alignment_schedule,
            'profile_fidelity_summary':fidelity,
            'generation_options_sha256': digest(g), 'generation_contract_sha256': contract_sha,
            'branch_ids': branch_ids(p), 'minimum_constraint_fraction_met': counts['metrics']['constraint_pass_fraction'] >= g['constraint_qc']['min_constraint_pass_fraction']}


def guidance_direction(weight):
    return 'positive' if weight>0 else 'negative' if weight<0 else 'zero'


def summarize_generation_counts(reports,requested,unique_eligible):
    """Scalar-report checks only: chemistry, hard constraints, and eligibility stay distinct."""
    if type(requested) is not int or requested<1 or len(reports)!=requested:raise ValueError('Complete requested candidate denominator required')
    if len({r['candidate_id'] for r in reports})!=requested:raise ValueError('Duplicate candidate reports')
    for row in reports:
        if any(type(row.get(k)) is not bool for k in ('chemical_valid','constraints_passed','hard_constraints_assessed','eligible')):raise ValueError('Exact independent candidate outcome booleans required')
        if row['constraints_passed'] and not (row['chemical_valid'] and row['hard_constraints_assessed']):raise ValueError('Hard constraints cannot pass without actual chemistry and assessment')
        if row['eligible'] and not (row['chemical_valid'] and row['constraints_passed']):raise ValueError('Eligibility cannot replace failed chemistry or constraints')
    chemical=sum(r['chemical_valid'] for r in reports)
    constraint=sum(r['chemical_valid'] and r['constraints_passed'] for r in reports)
    eligible=sum(r['eligible'] for r in reports)
    if type(unique_eligible) is not int or not 0<=unique_eligible<=eligible:raise ValueError('Invalid unique eligible graph denominator')
    metrics={'requested_samples':requested,'chemical_valid_count':chemical,'chemical_valid_fraction':chemical/requested,
             'constraint_pass_count':constraint,'constraint_pass_fraction':constraint/requested,
             'eligible_count':eligible,'eligible_fraction':eligible/requested,
             'chemical_qc_completed':chemical,'chemical_qc_passed':chemical,'valid_fraction':eligible/requested,
             'unique_isomeric_graphs':unique_eligible,'unique_fraction_among_eligible':unique_eligible/eligible if eligible else 0,
             'unique_fraction_among_valid':unique_eligible/eligible if eligible else 0}
    return {'metrics':metrics,'deprecated_scope':{
        'chemical_qc_completed':'deprecated_alias_of_chemical_valid_count; persisted_chemical_structure_QC_only',
        'chemical_qc_passed':'deprecated_alias_of_chemical_valid_count; never_eligible_count',
        'valid_fraction':'deprecated_eligible_fraction; use_chemical_valid_fraction_for_chemical_validity',
        'unique_fraction_among_valid':'deprecated_unique_fraction_among_eligible; not_parent_novelty',
        'constraint_pass_fraction':'chemical_valid_and_hard_constraints_passed_over_all_requested; independent_of_score_success'}}


def summarize_profile_fidelity(references,weights,reports,requested):
    """Descriptive scores captured before hard rejection; complete missing denominators remain."""
    if type(requested) is not int or requested<1 or not references or len(references)!=len(weights) or len(reports)!=requested:raise ValueError('Complete reference and requested sample denominators required')
    identities=[x['id'] for x in references]
    if len(set(identities))!=len(identities) or len({x['candidate_id'] for x in reports})!=requested:raise ValueError('Unique complete candidate and reference denominators required')
    if any(type(w) not in (int,float) or not math.isfinite(w) for w in weights):raise ValueError('Finite explicit reference weights required')
    for report in reports:
        if type(report.get('chemical_valid')) is not bool:raise ValueError('Exact chemical outcome required for the fidelity denominator')
        if len(report['profile_fidelity_scores'])!=len(identities) or {x['reference_id'] for x in report['profile_fidelity_scores']}!=set(identities):raise ValueError('Every candidate needs the exact complete reference fidelity axis')
    result=[]
    for reference,weight in zip(references,weights):
        identity=reference['id'];observations=[]
        for report in reports:
            found=[x for x in report['profile_fidelity_scores'] if x['reference_id']==identity]
            if len(found)!=1:raise ValueError('Each requested candidate needs one fidelity status per reference')
            if found[0]['guidance_weight']!=weight or found[0]['guidance_direction']!=guidance_direction(weight):raise ValueError('Reference fidelity direction/weight differs from requested guidance')
            if found[0]['scoring_state']=='SCORED' and not report['chemical_valid']:raise ValueError('Unverified chemistry cannot carry an accepted actual-structure profile score')
            if found[0]['scoring_state']!='SCORED' and any(found[0][m] is not None for m in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity')):raise ValueError('Failed/unassessed fidelity values must remain missing rather than accepted partial scores')
            observations.append(found[0])
        row={'reference_id':identity,'guidance_weight':weight,'guidance_direction':guidance_direction(weight),
             'requested_count':requested,'chemical_valid_count':sum(x['chemical_valid'] for x in reports),
             'scored_count':sum(x['scoring_state']=='SCORED' for x in observations),
             'failed_scoring_count':sum(x['scoring_state']=='FAILED' for x in observations),
             'unassessed_count':sum(x['scoring_state']=='NOT_ASSESSED' for x in observations),'metrics':{},
             'scope':'descriptive_ligand_profile_fidelity; negative_guidance_not_selectivity_or_binding_energy'}
        if row['scored_count']+row['failed_scoring_count']+row['unassessed_count']!=requested:raise ValueError('Unknown fidelity status')
        for metric in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity'):
            if metric!='pharmacophore_similarity' and any(x['scoring_state']=='SCORED' and x[metric] is None for x in observations):raise ValueError('A scored reference must retain actual shape and ESP measurements')
            values=[x[metric] for x in observations if x['scoring_state']=='SCORED' and x[metric] is not None]
            if any(type(x) not in (int,float) or not math.isfinite(x) or not -1e-6<=x<=1.000001 for x in values):raise ValueError('Nonfinite/out-of-range observed similarity')
            values.sort();n=len(values)
            row['metrics'][metric]={'observed_count':n,'missing_count':requested-n,'minimum':values[0] if n else None,
                'median':(values[(n-1)//2]+values[n//2])/2 if n else None,'mean':sum(values)/n if n else None,
                'maximum':values[-1] if n else None,'summary_scope':'observed_only; missing_retained_in_requested_denominator'}
        result.append(row)
    return result
