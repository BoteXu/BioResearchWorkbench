"""Server-only independent audits of saved chemistry and point constraints."""


def mapping_search_status(match_count,qualified_count,passed,cap=10000):
    """Scalar status helper; an incomplete search cannot establish a negative."""
    if (type(match_count) is not int or type(qualified_count) is not int or type(cap) is not int
            or cap<1 or not 0<=qualified_count<=match_count<=cap or type(passed) is not bool):
        raise ValueError('Exact matching-search denominator/status required')
    if passed and qualified_count==0:raise ValueError('A passed mapping needs an actual qualified witness')
    reached=match_count==cap
    complete=passed or not reached
    return {'match_enumeration_count':match_count,'qualified_mapping_count':qualified_count,
            'match_enumeration_cap':cap,'match_cap_reached':reached,'match_enumeration_complete':not reached,
            'assessment_complete':complete,'assessment_state':'PASSED' if passed else 'FAILED' if complete else 'SEARCH_INCOMPLETE'}


class ConstraintAuditor:
    def __init__(self, request):
        try:
            from .runtime import guard
        except ImportError:
            from runtime import guard
        guard(request)
        import numpy as np
        from rdkit import Chem
        from scipy.optimize import linear_sum_assignment
        from shepherd_score.score.constants import P_TYPES, DIRECTIONAL_PTYPES
        self.np, self.Chem, self.assignment = np, Chem, linear_sum_assignment
        self.types = tuple(P_TYPES)
        self.directional = set(DIRECTIONAL_PTYPES)
        self.limits = request['parameters']['generation_options']['constraint_qc']

    def points(self, target, actual_types, actual_positions, actual_vectors, selected):
        """Type-aware, directional, one-to-one maximum-valid matching; no shared nearest point."""
        np = self.np
        types = np.asarray(actual_types)
        pos, vec = np.asarray(actual_positions), np.asarray(actual_vectors)
        if types.size==0 and pos.size==0 and vec.size==0:
            types=np.asarray([],dtype=int);pos=np.zeros((0,3));vec=np.zeros((0,3))
        if types.ndim != 1 or not np.issubdtype(types.dtype,np.integer) or pos.shape != (len(types), 3) or vec.shape != pos.shape or not np.isfinite(pos).all() or not np.isfinite(vec).all():
            raise ValueError('Pharmacophore type/position/direction axes or finite values are invalid')
        targets = list(selected)
        if not targets:
            return {'required': 0, 'matched': 0, 'passed': True, 'points': []}
        cost = np.full((len(targets), len(types)), 1e9)
        measurements = {}
        for i, source_index in enumerate(targets):
            pt = int(target.pharm_types[source_index])
            if not 0 <= pt < len(self.types):
                raise ValueError('Unknown reference pharmacophore type')
            name = self.types[pt].lower()
            anchor = np.asarray(target.pharm_positions[source_index])
            direction = np.asarray(target.pharm_directions[source_index])
            for j, actual_type in enumerate(types):
                distance = float(np.linalg.norm(pos[j] - anchor))
                cosine = None
                direction_ok = True
                if name in self.directional:
                    denominator = float(np.linalg.norm(direction) * np.linalg.norm(vec[j]))
                    cosine = float(np.dot(direction, vec[j]) / denominator) if denominator > 1e-12 else None
                    # Ring-plane normals have equivalent opposite signs; H-bond/halogen vectors do not.
                    if cosine is not None and name == 'aromatic': cosine = abs(cosine)
                    direction_ok = cosine is not None and cosine >= self.limits['min_direction_cosine']
                valid = int(actual_type) == pt and distance <= self.limits['max_priority_distance_angstrom'] and direction_ok
                measurements[(i, j)] = (distance, cosine, valid)
                if valid:
                    cost[i, j] = distance / self.limits['max_priority_distance_angstrom']
        assigned = dict(zip(*self.assignment(cost))) if len(types) else {}
        rows = []
        for i, source_index in enumerate(targets):
            j = assigned.get(i)
            distance, cosine, passed = measurements[(i, j)] if j is not None else (None, None, False)
            rows.append({'source_point_index': source_index, 'source_type': int(target.pharm_types[source_index]),
                         'source_type_name': self.types[int(target.pharm_types[source_index])],
                         'matched_actual_point_index': int(j) if j is not None and passed else None,
                         'distance_angstrom': distance, 'direction_cosine': cosine, 'passed': bool(passed)})
        matched = sum(x['passed'] for x in rows)
        return {'required': len(rows), 'matched': matched, 'passed': matched == len(rows), 'points': rows,
                'matching': 'one_to_one_type_position_direction; aromatic_normal_sign_equivalent'}

    def scaffold(self, source_mol, actual_mol, selection):
        np, Chem = self.np, self.Chem
        inds = selection['scaffold_atom_indices']
        mode = selection['scaffold_mode']
        if mode == 'none':
            return {'required': 0, 'passed': True, 'scope': 'no_scaffold_constraint','assessment_complete':True,'assessment_state':'NOT_REQUESTED'}
        # Preserve the requested atom order. Only stereocentres fully defined by the selected subgraph
        # can be independently tested for relative stereochemistry at this stage.
        rw = Chem.RWMol()
        mapping = {original: rw.AddAtom(Chem.Atom(source_mol.GetAtomWithIdx(original))) for original in inds}
        stereo_centres = 0
        for original in inds:
            atom = source_mol.GetAtomWithIdx(original)
            defined = {x.GetIdx() for x in atom.GetNeighbors()} <= set(inds)
            if not defined:
                rw.GetAtomWithIdx(mapping[original]).SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
            elif atom.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED:
                stereo_centres += 1
        for bond in source_mol.GetBonds():
            a, b = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
            if a in mapping and b in mapping:
                rw.AddBond(mapping[a], mapping[b], bond.GetBondType())
                copied = rw.GetBondBetweenAtoms(mapping[a], mapping[b])
                copied.SetIsAromatic(bond.GetIsAromatic())
        for bond in source_mol.GetBonds():
            a, b = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
            if a in mapping and b in mapping:
                copied = rw.GetBondBetweenAtoms(mapping[a], mapping[b])
                stereo_atoms = list(bond.GetStereoAtoms())
                if len(stereo_atoms) == 2 and set(stereo_atoms) <= set(inds):
                    copied.SetStereoAtoms(mapping[stereo_atoms[0]], mapping[stereo_atoms[1]])
                    copied.SetStereo(bond.GetStereo())
        query = rw.GetMol()
        query.UpdatePropertyCache(strict=False)
        Chem.GetSymmSSSR(query)
        matches = actual_mol.GetSubstructMatches(query, useChirality=True, uniquify=False, maxMatches=10000)
        source_pos = np.asarray(source_mol.GetConformer().GetPositions())[inds]
        actual_pos = np.asarray(actual_mol.GetConformer().GetPositions())
        qualified = []
        for match in matches:
            if any((source_mol.GetAtomWithIdx(inds[i]).GetAtomicNum(), source_mol.GetAtomWithIdx(inds[i]).GetFormalCharge(), source_mol.GetAtomWithIdx(inds[i]).GetIsotope()) !=
                   (actual_mol.GetAtomWithIdx(match[i]).GetAtomicNum(), actual_mol.GetAtomWithIdx(match[i]).GetFormalCharge(), actual_mol.GetAtomWithIdx(match[i]).GetIsotope())
                   for i in range(len(inds))):
                continue
            # An induced subgraph audit also rejects extra internal scaffold bonds, beyond a
            # normal substructure query's positive-bond checks.
            if any((source_mol.GetBondBetweenAtoms(inds[i], inds[j]) is None) !=
                   (actual_mol.GetBondBetweenAtoms(match[i], match[j]) is None)
                   for i in range(len(inds)) for j in range(i)):
                continue
            delta = np.linalg.norm(actual_pos[list(match)] - source_pos, axis=1)
            qualified.append((float(delta.max()), tuple(match), float(np.sqrt(np.mean(delta ** 2)))))
        if not qualified:
            search=mapping_search_status(len(matches),0,False)
            return {'required': len(inds), 'passed': False, 'chemical_subgraph_retained':False if search['assessment_complete'] else None,
                    'scope': mode, 'fully_defined_stereocentres_audited': stereo_centres,
                    'failure': 'no_element_charge_bond_stereochemistry_preserving_induced_subgraph' if search['assessment_complete'] else 'search_cap_reached_without_qualified_mapping',**search}
        displacement, match, rms = min(qualified)
        fixed = mode == 'fixed'
        passed = not fixed or displacement <= self.limits['max_scaffold_displacement_angstrom']
        search=mapping_search_status(len(matches),len(qualified),bool(passed))
        return {'required': len(inds), 'passed': bool(passed), 'chemical_subgraph_retained': True,
                'source_atom_indices': inds, 'actual_atom_indices': list(match), 'scope': mode,
                'fixed_position_required': fixed, 'max_displacement_angstrom': displacement,
                'unfitted_RMSD_angstrom': rms, 'fully_defined_stereocentres_audited': stereo_centres,
                **search,'displacement_scope':'best_observed_mapping; truncated_search_does_not_establish_global_minimum',
                'release_or_inpainting_does_not_guarantee_fixed_coordinates': not fixed}

    def evaluate(self, source_mol, actual_mol, target, actual_profile, sample, selection, required_points):
        scaffold = self.scaffold(source_mol, actual_mol, selection)
        raw = self.points(target, sample.pharm_types, sample.pharm_positions, sample.pharm_directions, required_points)
        actual = self.points(target, actual_profile.pharm_types, actual_profile.pharm_ancs, actual_profile.pharm_vecs, required_points)
        return {'reference_id': selection['reference_id'], 'scaffold': scaffold,
                'raw_generated_pharmacophore_head': raw, 'reextracted_actual_molecular_pharmacophores': actual,
                'passed': scaffold['passed'] and raw['passed'] and actual['passed'],
                'assessment_complete':scaffold['assessment_complete'],
                'excluded_low_priority_points_are_not_forbidden': selection['pharm_mode'] == 'pharm-priority-only',
                'scientific_acceptance': 'NOT_ESTABLISHED'}
