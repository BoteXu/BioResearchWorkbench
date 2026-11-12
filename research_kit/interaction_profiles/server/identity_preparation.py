"""Existing-server RDKit identity grouping; original molecular graph/pose is preserved."""
from pathlib import Path
import importlib.metadata,math
from collections import Counter
from contracts import read,write,sha,digest
from lineage import load_origin,bound_output
from postanalysis_contracts import identity_policy,ISOTOPE_SCOPE

def _graph(mol,Chem):
    return {'canonical_isomeric_smiles':Chem.MolToSmiles(mol,canonical=True,isomericSmiles=True),
        'atoms':[(a.GetAtomicNum(),a.GetIsotope(),a.GetFormalCharge(),a.GetNumRadicalElectrons(),str(a.GetChiralTag()),a.GetNoImplicit(),a.GetNumExplicitHs()) for a in mol.GetAtoms()],
        'bonds':[(b.GetBeginAtomIdx(),b.GetEndAtomIdx(),str(b.GetBondType()),str(b.GetStereo()),list(b.GetStereoAtoms())) for b in mol.GetBonds()]}

def _coords(mol):
    if mol.GetNumConformers()!=1 or not mol.GetConformer().Is3D():raise ValueError('One original 3D conformer required')
    c=mol.GetConformer();xyz=[tuple(float(v) for v in c.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())]
    if any(not math.isfinite(v) for row in xyz for v in row):raise ValueError('Nonfinite original coordinates')
    return xyz

def _isotopes(mol):
    counts=Counter((a.GetAtomicNum(),a.GetIsotope()) for a in mol.GetAtoms() if a.GetIsotope())
    return [{'atomic_number':a,'isotope':i,'count':n} for (a,i),n in sorted(counts.items())]

def run_identity_preparation(request,ids,root,output,seed):
    try:from .runtime import guard
    except ImportError:from runtime import guard
    guard(request)
    origin=load_origin(request,ids,root);p=request['parameters'];output=Path(output)
    if importlib.metadata.version('rdkit')!=p['expected_versions']['rdkit']:raise ValueError('Existing RDKit version differs from review')
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    binaries={'rdchem':Path(Chem.rdchem.__file__).resolve(),'standardize':Path(rdMolStandardize.__file__).resolve()}
    for key,f in binaries.items():
        if sha(f)!=p['expected_'+key+'_sha256']:raise ValueError('Existing native RDKit binary differs: '+key)
    policy=identity_policy(p)
    policy_sha=digest(policy);write(output/'identity_policy.private.json',policy)
    (output/'origin_request_snapshot.private.json').write_bytes(origin['origin_path'].read_bytes())
    (output/'origin_receipt_snapshot.private.json').write_bytes((origin['returned']/'receipt.private.json').read_bytes())
    (output/'origin_generation_contract_snapshot.private.json').write_bytes(bound_output(origin,origin['variant']+'/generation_contract.private.json').read_bytes())
    (output/'origin_eligibility_snapshot.private.json').write_bytes(bound_output(origin,'eligible_candidate_outputs.private.json').read_bytes())
    write(output/'origin_lineage.private.json',{'schema':'postanalysis-origin/1','lineage_spec':origin['spec'],'source_plan_sha256':origin['origin']['plan_sha256'],'source_request_sha256':sha(origin['origin_path']),'source_receipt_sha256':origin['spec']['origin_receipt_sha256'],'source_review':origin['source_review'],'coordinates_unit':'angstrom','frame_id':origin['context']['frame_id'],'private_only':True})
    source={e['candidate_id']:e for e in origin['eligible']};records=[];eligible=[]
    for cid in origin['spec']['candidate_ids']:
        old=source[cid];row={'candidate_id':cid,'state':'PREPARATION_FAILED','parent_id':None,'source_parent_id':old['parent_id'],'microstate_id':old['microstate_id'],'state_id':old['state_id'],'source_sdf_path':old['path'],'source_sdf_sha256':old['sha256'],'source_sdf_bytes':old['bytes'],'identity_policy_sha256':policy_sha,'scientific_acceptance':'NOT_ESTABLISHED'}
        sdf=bound_output(origin,old['path']);report=bound_output(origin,old['constraint_report_path'])
        if sha(sdf)!=old['sha256'] or sha(report)!=old['constraint_report_sha256']:raise ValueError('Source eligibility/constraint bytes differ')
        try:
            loaded=list(Chem.SDMolSupplier(str(sdf),removeHs=False,sanitize=True))
            if len(loaded)!=1 or loaded[0] is None:raise ValueError('Exactly one sanitized original chemical state required')
            mol=loaded[0]
            if mol.GetNumAtoms()>p['max_atoms'] or len(Chem.GetMolFrags(mol))!=1:raise ValueError('Unsupported atom budget or disconnected source')
            for prop,key in (('BRW_STATE_ID','state_id'),('BRW_MICROSTATE_ID','microstate_id'),('BRW_PARENT_ID','parent_id')):
                if not mol.HasProp(prop) or mol.GetProp(prop)!=old[key]:raise ValueError('Actual source SDF property differs from generation eligibility')
            graph=_graph(mol,Chem);xyz=_coords(mol);identity_copy=Chem.Mol(mol);isotopes=_isotopes(mol)
            microstate_smiles=Chem.MolToSmiles(Chem.RemoveHs(mol),canonical=True,isomericSmiles=True)
            if microstate_smiles!=old['microstate_id']:raise ValueError('Original actual chemical microstate differs from its generation identity')
            row.update(original_graph_sha256=digest(graph),original_coordinates_sha256=digest(xyz),original_formal_charge=Chem.GetFormalCharge(mol),original_canonical_isomeric_smiles=graph['canonical_isomeric_smiles'],original_microstate_smiles=microstate_smiles,original_isotope_inventory=isotopes)
            if p['parent_policy']=='uncharged_tautomer':identity_copy=rdMolStandardize.Uncharger(canonicalOrder=True,force=False,protonationOnly=False).uncharge(identity_copy)
            status='NOT_REQUESTED_STATE_GRAPH';nt=1
            if p['parent_policy']!='state_graph':
                cleanup=rdMolStandardize.CleanupParameters()
                cleanup.tautomerRemoveIsotopicHs=False
                if cleanup.tautomerRemoveIsotopicHs is not False:raise ValueError('Installed RDKit did not retain the reviewed isotope policy')
                enumerator=rdMolStandardize.TautomerEnumerator(cleanup)
                enumerator.SetMaxTautomers(p['max_tautomers']);enumerator.SetMaxTransforms(p['max_transforms'])
                enumerator.SetRemoveSp3Stereo(p['tautomer_remove_sp3_stereo']);enumerator.SetRemoveBondStereo(p['tautomer_remove_bond_stereo']);enumerator.SetReassignStereo(p['tautomer_reassign_stereo'])
                enumerated=enumerator.Enumerate(identity_copy);status=str(enumerated.status);nt=len(enumerated)
                row.update(enumeration_status=status,enumerated_tautomers=nt)
                if enumerated.status!=rdMolStandardize.TautomerEnumeratorStatus.Completed or not 1<=nt<=p['max_tautomers']:raise ValueError('Tautomer enumeration incomplete or its denominator invalid; no accepted parent key')
                identity_copy=enumerator.PickCanonical(enumerated)
            parent_smiles=Chem.MolToSmiles(identity_copy,canonical=True,isomericSmiles=True)
            if not parent_smiles:raise ValueError('Computed grouping key is empty')
            parent_isotopes=_isotopes(identity_copy)
            if parent_isotopes!=isotopes:raise ValueError('Computational parent grouping changed isotope inventory')
            if p['parent_policy']!='uncharged_tautomer' and Chem.GetFormalCharge(identity_copy)!=Chem.GetFormalCharge(mol):raise ValueError('Charge-preserving grouping changed the original formal charge')
            parent_id='COMPUTED_GROUP_'+digest({'policy_sha256':policy_sha,'canonical_parent_smiles':parent_smiles})
            # Only metadata changes on the original state/coordinate copy, never the standardized copy.
            saved=Chem.Mol(mol);saved.SetProp('BRW_PARENT_ID',parent_id);saved.SetProp('BRW_PARENT_POLICY_SHA256',policy_sha);saved.SetProp('BRW_PARENT_ID_SCOPE','COMPUTATIONAL_GROUP_NOT_PHYSIOLOGICAL_PROTONATION_OR_EXPERIMENTAL_PARENT')
            target=output/(cid+'.identity.sdf');writer=Chem.SDWriter(str(target))
            try:writer.write(saved)
            finally:writer.close()
            reread=list(Chem.SDMolSupplier(str(target),removeHs=False,sanitize=True))
            if len(reread)!=1 or reread[0] is None:raise ValueError('Saved SDF did not round-trip')
            again=reread[0]
            if _graph(again,Chem)!=graph or _coords(again)!=xyz:raise ValueError('Identity preparation changed original graph, atom order or coordinates')
            if any(not again.HasProp(prop) or again.GetProp(prop)!=value for prop,value in (('BRW_PARENT_ID',parent_id),('BRW_STATE_ID',old['state_id']),('BRW_MICROSTATE_ID',old['microstate_id']),('BRW_PARENT_POLICY_SHA256',policy_sha))):raise ValueError('Saved molecular identity properties differ')
            constraints=output/(cid+'.source_constraints.private.json');constraints.write_bytes(report.read_bytes())
            row.update(state='IDENTITY_PREPARED_REQUIRES_NEW_QC',parent_id=parent_id,canonical_parent_smiles=parent_smiles,parent_formal_charge=Chem.GetFormalCharge(identity_copy),enumeration_status=status,enumerated_tautomers=nt,original_graph_preserved=True,original_atom_order_preserved=True,original_coordinates_preserved=True,prepared_graph_sha256=digest(_graph(again,Chem)),prepared_coordinates_sha256=digest(_coords(again)),prepared_sdf_readback_verified=True,parent_isotope_inventory=parent_isotopes,isotope_policy_scope=ISOTOPE_SCOPE,prepared_sdf_path=target.name,prepared_sdf_sha256=sha(target),prepared_sdf_bytes=target.stat().st_size,source_constraint_report_path=constraints.name,source_constraint_report_sha256=sha(constraints),source_generation_contract_sha256=old['generation_contract_sha256'],source_constraints_passed=old['constraints_passed'],grouping_is_physiological_state_prediction=False)
            eligible.append({'candidate_id':cid,'state_id':old['state_id'],'parent_id':parent_id,'microstate_id':old['microstate_id'],'path':target.name,'sha256':sha(target),'bytes':target.stat().st_size,'eligibility':'REQUIRES_NEW_DOWNSTREAM_QC','identity_report_path':cid+'.identity.private.json','identity_policy_sha256':policy_sha,'source_sdf_sha256':old['sha256'],'constraints_preserved_by_exact_graph_atom_order_and_coordinate_invariance':True,'source_constraint_report_path':constraints.name,'source_constraint_report_sha256':sha(constraints)})
        except Exception as exc:row['error']=type(exc).__name__+': '+str(exc)
        records.append(row)
    groups={}
    for row in records:
        if row['parent_id'] is not None and row['state']=='IDENTITY_PREPARED_REQUIRES_NEW_QC':groups.setdefault(row['parent_id'],[]).append(row['candidate_id'])
    for row in records:
        members=groups.get(row['parent_id'],[]);row.update(parent_group_size=len(members),group_representative_for_display_only=bool(members) and row['candidate_id']==members[0],no_candidates_dropped=True)
        write(output/(row['candidate_id']+'.identity.private.json'),row)
    for item in eligible:item['identity_report_sha256']=sha(output/item['identity_report_path'])
    write(output/'identity_records.private.json',records)
    write(output/'parent_groups.private.json',{'policy_sha256':policy_sha,'groups':groups,'duplicates_retained':True,'identity_scope':'computed_grouping_not_independent_biological_or_experimental_entities'})
    from worker import table
    fields=['candidate_id','state','parent_id','microstate_id','state_id','source_sdf_sha256','prepared_sdf_sha256','identity_policy_sha256','parent_group_size','group_representative_for_display_only']
    table(output/'identity_preparation.tsv',[{k:r.get(k,'') for k in fields} for r in records],fields)
    for key,f in binaries.items():
        if sha(f)!=p['expected_'+key+'_sha256']:raise ValueError('RDKit changed during identity preparation')
    for cid in origin['spec']['candidate_ids']:
        bound_output(origin,source[cid]['path']);bound_output(origin,source[cid]['constraint_report_path'])
    prepared=len(eligible);metrics={'requested_count':len(records),'prepared_count':prepared,'prepared_fraction':prepared/len(records),'computed_parent_groups':len(groups)}
    write(output/'postanalysis_boundaries.private.json',{'original_graph_and_pose_preserved_for_prepared_records':True,'parent_groups_are_computational':True,'pH_or_pKa_predicted':False,'canonical_tautomer_is_most_stable_asserted':False,'new_downstream_QC_required':True,'seeds_are_technical_rechecks_not_independent_molecules':True,'scientific_acceptance':'NOT_ESTABLISHED','public_upload':False})
    return {'metrics':metrics,'eligible_outputs':eligible,'expected_attempts':len(records),'minimum_prepared_fraction_met':metrics['prepared_fraction']>=p['minimum_prepared_fraction'],'scientific_acceptance':'NOT_ESTABLISHED','biological_replication_established':False,'identity_policy_sha256':policy_sha}
