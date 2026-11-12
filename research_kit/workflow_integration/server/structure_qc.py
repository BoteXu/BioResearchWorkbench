"""Real PDB/mmCIF coordinate and selected residue-map checks on the server."""
from runtime import write,sha

def analyze(inputs,p,out,mode):
    import math
    import pandas as pd
    import gemmi
    structure=gemmi.read_structure(str(inputs['structure']))
    structure.setup_entities()
    if len(structure)!=1 and p.get('selected_model') is None:raise ValueError('Select an explicit model from a multi-model structure')
    model=structure[0 if p['selected_model'] is None else p['selected_model']];chains=set(p['selected_chains'])
    if not chains or not chains<={chain.name for chain in model}:raise ValueError('Actual selected chain not present')
    atoms=[];residues=[];res_lookup={};issues=[]
    for chain in model:
        if chain.name not in chains:continue
        for residue in chain:
            key=(chain.name,str(residue.seqid.num),residue.seqid.icode.strip())
            names=[a.name for a in residue];res_lookup[key]=residue.name
            missing=[a for a in p['required_backbone_atoms'] if a not in names] if residue.entity_type==gemmi.EntityType.Polymer else []
            if missing:issues.append('missing_required_backbone')
            residues.append({'chain':chain.name,'auth_residue':residue.seqid.num,'insertion_code':residue.seqid.icode.strip(),
                'residue_name':residue.name,'hetero_flag':residue.het_flag,'missing_required_backbone':';'.join(missing)})
            for atom in residue:
                position=[atom.pos.x,atom.pos.y,atom.pos.z]
                if not all(math.isfinite(v) for v in position):issues.append('nonfinite_coordinates')
                if not 0<=atom.occ<=1:issues.append('invalid_occupancy')
                if atom.altloc not in ('\x00',' '):issues.append('alternate_conformation_requires_selection')
                atoms.append({'chain':chain.name,'auth_residue':residue.seqid.num,'insertion_code':residue.seqid.icode.strip(),
                   'residue_name':residue.name,'atom_name':atom.name,'altloc':atom.altloc if atom.altloc!='\x00' else '',
                   'occupancy':atom.occ,'b_factor':atom.b_iso,'element':atom.element.name,'x':position[0],'y':position[1],'z':position[2]})
    if not atoms:raise ValueError('No selected atoms')
    frame=pd.DataFrame(atoms)
    if frame[['chain','auth_residue','insertion_code','atom_name','altloc']].duplicated().any():issues.append('duplicate_atom_identity')
    frame.to_csv(out/'atom_qc.tsv',sep='\t',index=False);pd.DataFrame(residues).to_csv(out/'residue_qc.tsv',sep='\t',index=False)
    mapping=pd.read_csv(inputs['residue_map'],sep='\t',dtype=str,keep_default_na=False);result=[]
    for row in mapping.to_dict('records'):
        key=(row['structure_chain'],row['structure_residue'],row['insertion_code']);observed=res_lookup.get(key)
        ok=observed is not None and observed==row['expected_residue_name']
        result.append({**row,'observed_residue_name':observed,'mapping_pass':ok})
        if row['required'].lower()=='true' and not ok:issues.append('required_residue_mapping_failed')
    pd.DataFrame(result).to_csv(out/'residue_mapping_qc.tsv',sep='\t',index=False)
    write(out/'structure_qc.json',{'structure_sha256':sha(inputs['structure']),'selected_chains':p['selected_chains'],
       'model_index':p['selected_model'],'atom_count':len(atoms),'residue_count':len(residues),'issues':sorted(set(issues)),
       'numerical_identity_qc_pass':not issues,'structure_repaired':False,'hydrogens_or_protonation_assigned':False,
       'confidence_source':p['confidence_source'],'b_factor_used_as_plddt':False,
       'limits':'Actual identity/coordinate checks only. Missing sequence, protonation, metals/cofactors, assembly and pocket confidence still require source/model review.'})
    return [(out/'atom_qc.tsv','atom_qc'),(out/'residue_qc.tsv','residue_qc'),(out/'residue_mapping_qc.tsv','residue_mapping_qc'),(out/'structure_qc.json','structure_qc')]
