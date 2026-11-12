"""Actual native scientific calls. Imported only after the allocated-server guard."""
from pathlib import Path
import csv,json,os,re,subprocess,importlib.metadata,shutil,math,copy
from contracts import read,write,sha,selected

def table(f,rows,fields):
    with Path(f).open('x',encoding='utf8',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=fields,delimiter='\t',extrasaction='raise');writer.writeheader();writer.writerows(rows)

def execute(request,ids,root,out,seed):
    try:from .runtime import guard
    except ImportError:from runtime import guard
    guard(request)
    if request['method'] in ('paper_native_evaluation','prepare_generated_identities'):
        if request['method']=='paper_native_evaluation':
            from native_evaluation import run_native_evaluation
            return run_native_evaluation(request,ids,root,out,seed)
        from identity_preparation import run_identity_preparation
        return run_identity_preparation(request,ids,root,out,seed)
    from identity import verify
    p=request['parameters'];mode=request['method'];ctx=read(ids['context']);software=read(ids['software'])
    for package,expected in p['expected_versions'].items():
        if importlib.metadata.version(package)!=expected:raise ValueError('Existing dependency version differs from reviewed exact version: '+package)
    required=['shepherd-score']+(['shepherd2'] if mode=='shepherd2_generate' else []);identity=verify(software,required)
    import numpy as np,torch,open3d as o3d
    if p['device']=='cuda' and (not torch.cuda.is_available() or torch.cuda.device_count()<1):raise ValueError('Requested server CUDA backend is unavailable; no silent CPU fallback')
    from rdkit import Chem
    from shepherd_score.container import Molecule,MoleculePair
    from shepherd_score.score.constants import ALPHA
    import shepherd_score
    if Path(shepherd_score.__file__).resolve().parent!=Path(software['source_roots']['shepherd-score']).resolve():raise ValueError('Imported scientific module differs from reviewed source root')
    exe=shutil.which('xtb')
    if not exe or sha(exe)!=p['expected_xtb_sha256']:raise ValueError('Existing reviewed xTB binary required; no automatic install')
    version=subprocess.run([exe,'--version'],capture_output=True,text=True,check=True).stdout
    if p['expected_xtb_version'] not in version:raise ValueError('Existing xTB version differs from review')
    write(out/'software_identity.private.json',{'python_sources':identity,'versions':{k:importlib.metadata.version(k) for k in p['expected_versions']},'xtb_sha256':sha(exe),'xtb_version':version,'scientific_acceptance':'NOT_ESTABLISHED'})
    from material_contracts import context as review_context,material,numerical_QC,checkpoint as review_checkpoint
    review_context(ctx)
    np.random.seed(seed);torch.manual_seed(seed);o3d.utility.random.seed(seed)
    records=read(ids['structure_manifest'])['molecules'];names=[r['id'] for r in records]
    if len(names)!=len(set(names)) or not names:raise ValueError('Unique explicit molecular identities required')
    ledger=[];profiles={};molecules={};parents={};qrecords=[];eligible=[]
    def molecule_qc(mol):
        if mol is None or mol.GetNumConformers()!=1 or not mol.GetConformer().Is3D() or len(Chem.GetMolFrags(mol))!=1:raise ValueError('One connected sanitized molecule with one actual 3D conformer required')
        if mol.GetNumAtoms()>p['max_atoms'] or any(a.GetAtomicNum() not in (1,5,6,7,8,9,15,16,17,35,53) for a in mol.GetAtoms()):raise ValueError('Outside declared organic closed-shell scope; metals need a separate parameterization route')
        if any(a.GetNumImplicitHs()>0 or a.GetNumRadicalElectrons() for a in mol.GetAtoms()):raise ValueError('Explicit hydrogen atoms and nonradical chemical state required')
        coords=np.asarray(mol.GetConformer().GetPositions())
        if coords.shape!=(mol.GetNumAtoms(),3) or not np.isfinite(coords).all():raise ValueError('Nonfinite molecular coordinates')
        if (sum(a.GetAtomicNum() for a in mol.GetAtoms())-Chem.GetFormalCharge(mol))%2:raise ValueError('This v1 route requires a reviewed closed-shell singlet')
        for b in mol.GetBonds():
            distance=np.linalg.norm(coords[b.GetBeginAtomIdx()]-coords[b.GetEndAtomIdx()])
            if distance<.35 or distance>3.:raise ValueError('Grossly invalid bonded geometry; detailed pose/strain QC is still separate')
        stereo=Chem.FindMolChiralCenters(mol,includeUnassigned=True)
        if any(label=='?' for _,label in stereo):raise ValueError('Unassigned tetrahedral stereochemistry requires explicit review')
        if any(str(info.specified)=='Unspecified' for info in Chem.FindPotentialStereo(mol)):raise ValueError('Unassigned potential atom/bond stereochemistry requires explicit review')
        return coords
    def partial_charges(mol,tag):
        coords=molecule_qc(mol);folder=out/('xtb_'+tag);folder.mkdir()
        xyz=str(mol.GetNumAtoms())+'\nfixed input geometry, angstrom\n'+'\n'.join(a.GetSymbol()+' '+' '.join(format(v,'.12g') for v in coords[a.GetIdx()]) for a in mol.GetAtoms())+'\n';(folder/'input.xyz').write_text(xyz,encoding='ascii')
        argv=[exe,'input.xyz','--gfn','2','--scc','--alpb',p['solvent'],'--chrg',str(Chem.GetFormalCharge(mol)),'--uhf','0','--parallel',str(request['resource_budget']['cpus']),'--norestart']
        with (folder/'engine.log').open('xb') as log:result=subprocess.run(argv,cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=p['xtb_timeout'])
        text=(folder/'engine.log').read_text(errors='replace')
        if result.returncode!=0 or not re.search('converged',text,re.I) or re.search('not converged|failed to converge|abnormal termination',text,re.I):raise ValueError('Actual xTB SCC failed or convergence is unassessed')
        energy_match=re.search(r'TOTAL ENERGY\s+([+-]?[0-9.]+(?:[EeDd][+-]?[0-9]+)?)',text)
        if energy_match is None or not math.isfinite(float(energy_match[1].replace('D','E').replace('d','e'))):raise ValueError('Native xTB single-point energy is missing or nonfinite')
        charges=np.loadtxt(folder/'charges',ndmin=1)
        if charges.shape!=(mol.GetNumAtoms(),) or not np.isfinite(charges).all() or abs(charges.sum()-Chem.GetFormalCharge(mol))>p['charge_sum_tolerance'] or (folder/'xtbopt.xyz').exists():raise ValueError('Charge atom axis/sum or fixed-geometry single-point contract failed')
        write(folder/'charge_receipt.private.json',{'state':'COMPLETED','exit_code':0,'input_xyz_sha256':sha(folder/'input.xyz'),'charges_sha256':sha(folder/'charges'),'atoms':mol.GetNumAtoms(),'formal_charge':Chem.GetFormalCharge(mol),'partial_charge_sum':float(charges.sum()),'solvent':p['solvent'],'single_point_energy_hartree':float(energy_match[1].replace('D','E').replace('d','e')),'energy_scope':'isolated_molecule_not_binding_energy','method':'GFN2-xTB_ALPB_single_point','geometry_optimized':False,'xtb_sha256':sha(exe),'argv':argv})
        return charges
    def profile(mol,q):
        obj=Molecule(Chem.Mol(mol),num_surf_points=p['surface_points'],probe_radius=p['probe_radius'],partial_charges=np.asarray(q),pharm_multi_vector=False)
        if np.asarray(obj.surf_pos).shape!=(p['surface_points'],3) or not np.isfinite(obj.surf_pos).all() or np.asarray(obj.surf_esp).shape!=(p['surface_points'],) or not np.isfinite(obj.surf_esp).all():raise ValueError('Native surface/ESP extraction failed')
        if not np.allclose(np.asarray(obj.partial_charges),q):raise ValueError('Native profile changed the selected charge model; no silent MMFF fallback')
        if (np.linalg.norm(np.asarray(obj.surf_pos)[:,None,:]-mol.GetConformer().GetPositions()[None,:,:],axis=2)<1e-6).any():raise ValueError('Native surface includes an atomic potential singularity')
        return obj
    def score(ref,fit):
        mp=MoleculePair(copy.deepcopy(ref),copy.deepcopy(fit),num_surf_points=p['surface_points'],do_center=False,device=torch.device(p['device']))
        shape=float(np.asarray(mp.score_with_surf(ALPHA(p['surface_points']),use='np')).item());esp=float(np.asarray(mp.score_with_esp(ALPHA(p['surface_points']),lam=p['esp_lambda'],use='np')).item())
        pharm=float(np.asarray(mp.score_with_pharm(use='np')).item()) if len(ref.pharm_types) and len(fit.pharm_types) else None
        if any(not math.isfinite(x) or x< -1e-6 or x>1.000001 for x in (shape,esp,*([pharm] if pharm is not None else []))):raise ValueError('Native dimensionless similarity score outside valid range')
        return shape,esp,pharm
    for number,row in enumerate(records):
        material(row,ctx)
        sdf=selected(root,row['sdf']['path'])
        if sha(sdf)!=row['sdf']['sha256']:raise ValueError('Selected molecular structure changed')
        qc,receipt,numerical_review=numerical_QC(row,root,sdf)
        write(out/(row['id']+'.input_QC.private.json'),numerical_review)
        supplier=Chem.SDMolSupplier(str(sdf),removeHs=False,sanitize=True);loaded=list(supplier)
        if len(loaded)!=1:raise ValueError('Each selected SDF must contain exactly one explicit 3D chemical state')
        mol=loaded[0];molecule_qc(mol)
        if Chem.GetFormalCharge(mol)!=row['formal_charge']:raise ValueError('Actual formal charge differs from reviewed state')
        q=partial_charges(mol,'input_'+str(number));obj=profile(mol,q);profiles[row['id']]=obj;molecules[row['id']]=mol;parents[row['id']]=row['parent_id'];qrecords.append((sdf,sha(sdf),qc,sha(qc),receipt,sha(receipt)))
        from contracts import digest
        atom_axis=[{'atomic_number':a.GetAtomicNum(),'formal_charge':a.GetFormalCharge(),'isotope':a.GetIsotope()} for a in mol.GetAtoms()]
        point_axis=[{'type':int(t),'position_angstrom':[round(float(x),6) for x in pos],'direction':[round(float(x),6) for x in vec]} for t,pos,vec in zip(obj.pharm_types,obj.pharm_ancs,obj.pharm_vecs)]
        write(out/(row['id']+'.axes.private.json'),{'schema':'private-reference-axes/1','source_sdf_sha256':sha(sdf),'reference_id':row['id'],'atom_axis':atom_axis,'atom_axis_sha256':digest(atom_axis),'pharmacophore_axis':point_axis,'pharmacophore_axis_sha256':digest(point_axis),'coordinates_unit':'angstrom','frame_id':ctx['frame_id'],'preparation_domain_sha256':ctx['preparation_domain_sha256'],'scientific_acceptance':'NOT_ESTABLISHED'})
        np.savez_compressed(out/('profile_'+row['id']+'.npz'),surface=obj.surf_pos,esp=obj.surf_esp,charges=q,pharm_types=obj.pharm_types,pharm_positions=obj.pharm_ancs,pharm_vectors=obj.pharm_vecs)
    references=[r for r in records if r['role']=='reference'];candidates=[r for r in records if r['role']!='reference'];score_rows=[];denominator=[]
    if not references:raise ValueError('Explicit reference interaction profile required')
    control=score(profiles[references[0]['id']],profiles[references[0]['id']])
    if any(abs(x-1)>1e-5 for x in control if x is not None):raise ValueError('Actual native self-similarity reference control failed')
    if mode=='prepare_reference_profiles':
        if candidates:raise ValueError('Reference-axis preparation accepts only the explicitly selected reference set')
        denominator=[{'candidate_id':r['id'],'state':'REFERENCE_PROFILE_PREPARED','experimental_binding_established':False} for r in references]
    elif mode!='shepherd2_generate':
        if len(references)!=1 or not candidates:raise ValueError('One reference plus the complete selected candidate/control set required')
        ref=profiles[references[0]['id']]
        for row in candidates:
            fit=profiles[row['id']];original=np.asarray(molecules[row['id']].GetConformer().GetPositions()).copy();transform=np.eye(4)
            if mode=='align_profiles':
                ref_center=ref.atom_pos.mean(0);fit_center=fit.atom_pos.mean(0);pair=MoleculePair(copy.deepcopy(ref),copy.deepcopy(fit),num_surf_points=p['surface_points'],do_center=True,device=torch.device(p['device']))
                pair.align_with_esp(ALPHA(p['surface_points']),lam=p['esp_lambda'],num_repeats=p['alignment_restarts'],max_num_steps=p['alignment_steps'],use_jax=False,use_analytical=True)
                moved=pair.get_transformed_molecule(pair.transform_esp);moved.center_to(-ref_center);fit=moved;transform=np.asarray(pair.transform_esp).copy();transform[:3,3]+=ref_center-transform[:3,:3]@fit_center
                if not np.isfinite(transform).all() or not np.allclose(transform[:3,:3].T@transform[:3,:3],np.eye(3),atol=1e-4) or not np.isclose(np.linalg.det(transform[:3,:3]),1,atol=1e-4):raise ValueError('Native alignment returned an invalid rigid transform')
                write(out/(row['id']+'.transform.private.json'),{'SE3_original_to_saved':transform.tolist(),'objective':'ESP_surface_alignment','all_scores_same_transformed_pose':True,'new_docking_pose_QC_required':True})
            saved=np.asarray(fit.mol.GetConformer().GetPositions());expected=original@transform[:3,:3].T+transform[:3,3]
            if not np.allclose(saved,expected,atol=1e-4) or mode=='score_fixed_pose' and not np.array_equal(saved,original):raise ValueError('Molecular pose changed outside the declared transformation')
            scores=score(ref,fit);saved_sdf=out/(row['id']+'.scored.sdf');writer=Chem.SDWriter(str(saved_sdf));writer.write(fit.mol);writer.close();score_rows.append({'candidate_id':row['id'],'parent_id':row['parent_id'],'microstate_id':row['microstate_id'],'role':row['role'],'shape_similarity':scores[0],'esp_surface_similarity':scores[1],'pharmacophore_similarity':scores[2],'pharmacophore_assessed':scores[2] is not None,'coordinate_mode':mode,'protein_ligand_energy_estimated':False});denominator.append({'candidate_id':row['id'],'state':'SCORED','experimental_binding_established':False});eligible.append({'candidate_id':row['id'],'parent_id':row['parent_id'],'microstate_id':row['microstate_id'],'path':saved_sdf.name,'sha256':sha(saved_sdf),'bytes':saved_sdf.stat().st_size,'eligibility':'REQUIRES_NEW_DOWNSTREAM_QC'})
    else:
        if candidates:raise ValueError('Generation references and downstream candidate scoring are distinct runs')
        from generation import run_generation
        generated=run_generation(request,ids,root,out,seed,profiles,molecules,references,molecule_qc,partial_charges,profile,score)
        score_rows=generated['score_rows'];denominator=generated['denominator'];eligible=generated['eligible']
        constraint_fields=['candidate_id','state','actual_structure_QC','constraints_passed','report_path','report_sha256','generation_contract_sha256','generation_options_sha256']
        table(out/'constraint_results.tsv',generated['constraint_rows'],constraint_fields)
    for row in score_rows:
        if 'reference_id' not in row:
            if mode=='shepherd2_generate':raise ValueError('Generated pair lacks explicit reference identity')
            row['reference_id']=references[0]['id']
    fields=['candidate_id','reference_id','parent_id','microstate_id','role','shape_similarity','esp_surface_similarity','pharmacophore_similarity','pharmacophore_assessed','coordinate_mode','protein_ligand_energy_estimated'];table(out/'profile_scores.tsv',score_rows,fields)
    dfields=['candidate_id','state','reason','formal_charge','canonical_isomeric_smiles'] if mode=='shepherd2_generate' else ['candidate_id','state','experimental_binding_established'];table(out/'candidate_denominator.tsv',denominator,dfields)
    for f,h,q,qh,rc,rh in qrecords:
        if sha(f)!=h or sha(q)!=qh or sha(rc)!=rh:raise ValueError('Nested selected source changed during run')
    verify(software,required)
    if sha(exe)!=p['expected_xtb_sha256']:raise ValueError('Scientific software or checkpoint changed during run')
    metrics={'selected_input_molecules':len(records),'scored_profile_pairs':len(score_rows),'self_shape_similarity':control[0],'self_esp_similarity':control[1]}
    if mode=='shepherd2_generate':metrics.update(generated['metrics'])
    result={'metrics':metrics,'eligible_outputs':eligible,'potential_model':'GFN2_xTB_atomic_partial_charge_Coulomb_surface','native_fallback_to_MMFF_allowed':False,'biological_replication_established':False,'scientific_acceptance':'NOT_ESTABLISHED','minimum_valid_fraction_met':generated['metrics']['chemical_valid_fraction']>=p['min_valid_fraction'] if mode=='shepherd2_generate' else None}
    if mode=='shepherd2_generate':
        for key in ('generation_options_sha256','generation_contract_sha256','branch_ids','minimum_constraint_fraction_met','deprecated_scope','effective_conditioning','expected_alignment_steps','profile_fidelity_summary'):result[key]=generated[key]
    return result
