"""Native source-scoped DiffDock/DiffSBDD/RFdiffusion/MACE, owned server only."""
from pathlib import Path
import subprocess,os,re
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    from native_genetics import reference_manifest,existing_file
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd
    outputs=[];diag={'mode':mode,'software_versions':p['software_versions'],'scientific_acceptance':'NOT_ESTABLISHED'}
    model_manifest,models=reference_manifest(inputs['model_manifest'])
    if model_manifest.get('trusted_source_reviewed') is not True or not model_manifest.get('source_url') or not model_manifest.get('license') or not model_manifest.get('intended_domain'):raise ValueError('Existing model bytes need reviewed trusted source, license and scientific domain; native pickle loaders must not load untrusted artifacts')
    def model(key):
        rel=model_manifest.get(key)
        if rel not in models:raise ValueError('Exact existing model/cache component missing from the selected hash-bound manifest: '+key)
        return models[rel]
    if mode=='mace_singlepoint':
        import ase.io,torch
        from mace.calculators import MACECalculator
        checkpoint=model('model_file');meta=read(inputs['structure_identity']);frames=list(ase.io.iread(str(inputs['structures']),format='extxyz',index=':'))
        if len(frames)!=len(meta) or not frames or len(frames)>p['maximum_structures'] or len({q.get('structure_id') for q in meta})!=len(meta) or any(not isinstance(q.get('structure_id'),str) or not q['structure_id'] for q in meta):raise ValueError('Exact native structure frame identities and explicit server budget required')
        if model_manifest.get('energy_unit')!=p['model_energy_unit'] or model_manifest.get('length_unit')!=p['model_length_unit'] or model_manifest.get('supported_elements')!=p['supported_elements']:raise ValueError('Actual force-field domain/elements/units differ from the reviewed task')
        if model_manifest.get('model_head')!=p['model_head']:raise ValueError('Actual model prediction head differs from the selected checkpoint manifest')
        calc=MACECalculator(model_paths=str(checkpoint),device='cuda' if p['accelerator']=='gpu' else 'cpu',default_dtype=p['dtype'],energy_units_to_eV=p['energy_units_to_ev'],length_units_to_A=p['length_units_to_angstrom'],model_type='MACE',head=p['model_head'])
        if p['model_head'] is None and len(getattr(calc,'available_heads',[]))>1:raise ValueError('Select an actual explicit head for a multi-head MACE model; do not silently select the first')
        rows=[];forces=[]
        for i,(atoms,ident) in enumerate(zip(frames,meta)):
            if ident.get('frame_index')!=i or len(atoms)>p['maximum_atoms'] or not len(atoms) or not set(atoms.get_chemical_symbols())<=set(p['supported_elements']) or not np.isfinite(atoms.positions).all() or atoms.pbc.any():raise ValueError('Selected finite nonperiodic molecular structure/domain differs; periodic/material branches require separate review')
            before=atoms.positions.copy();symbols=atoms.get_chemical_symbols();atoms.calc=calc;energy=float(atoms.get_potential_energy());force=np.asarray(atoms.get_forces())
            if not np.isfinite(energy) or force.shape!=(len(atoms),3) or not np.isfinite(force).all() or not np.array_equal(atoms.positions,before):raise ValueError('Native single-point energies/forces invalid or coordinates changed')
            rows.append({'structure_id':ident['structure_id'],'frame_index':i,'energy_ev':energy,'n_atoms':len(atoms),'maximum_force_ev_per_angstrom':float(np.linalg.norm(force,axis=1).max())})
            forces.extend({'structure_id':ident['structure_id'],'source_atom_index':j,'element':symbols[j],'fx_ev_per_angstrom':float(v[0]),'fy_ev_per_angstrom':float(v[1]),'fz_ev_per_angstrom':float(v[2])} for j,v in enumerate(force))
        pd.DataFrame(rows).to_csv(out/'mace_energies.tsv',sep='\t',index=False);pd.DataFrame(forces).to_csv(out/'mace_forces.tsv',sep='\t',index=False);outputs.extend([(out/'mace_energies.tsv','potential_energies'),(out/'mace_forces.tsv','atomic_forces')]);diag.update(n_structures=len(frames),source_coordinates_unchanged=True,interpretation='Actual MACE molecular single-point energy/force prediction within the declared model domain and unit conversion. Not docking affinity, quantum electronic potential, binding free energy or a validated dynamics trajectory.')
    else:
        if model_manifest.get('native_software_versions')!=p['native_software_versions']:raise ValueError('Exact child scientific environment must match the reviewed model environment; the orchestration interpreter is not proof')
        source,members=reference_manifest(inputs['source_manifest']);root=(inputs['source_manifest'].parent/source.get('repository_directory','')).resolve()
        if not root.is_dir() or not root.is_relative_to(inputs['source_manifest'].parent.resolve()) or not source.get('source_url') or not source.get('license'):raise ValueError('Selected existing native source tree with provenance/license required')
        entries={'diffdock_pose':('inference.py','d9a908b3f45672d3f45216070dfd4c1493f50c16882f03489c48f94262856e67'),'diffsbdd_generate':('generate_ligands.py','8884e63ddb7f0fa84bd89bfd956fbefa10db687fa0cfc3380b85d06837be4474'),'rfdiffusion_backbone':('scripts/run_inference.py','a22624d7d40d3d207d91e92163441da5a778c867ed6ea85aa546cc9fdbeb2105')}
        script,digest=entries[mode]
        if sha(root/script)!=digest:raise ValueError('Native entry differs from exact primary-source code reviewed for this adapter')
        actual={q.resolve() for q in root.rglob('*') if q.is_file() and q.suffix in {'.py','.yaml','.yml','.json'} and '.git' not in q.parts and '__pycache__' not in q.parts}
        if not actual<={q.resolve() for q in members.values()}:raise ValueError('All actual native source/config files must be immutable and bound before execution')
        if mode in {'diffdock_pose','diffsbdd_generate'}:
            from rdkit import Chem
            from Bio.PDB import PDBParser
            receptor=PDBParser(QUIET=True).get_structure('reviewed',str(inputs['receptor']));coords=np.asarray([atom.coord for atom in receptor.get_atoms()]);qc=read(inputs['structure_qc_receipt'])
            if coords.size==0 or not np.isfinite(coords).all() or qc.get('inputs',{}).get('receptor')!=sha(inputs['receptor']) or qc.get('decision')!='PASS':raise ValueError('Actual finite receptor and exact independently reviewed structure-QC receipt required')
        if mode=='diffdock_pose':
            ligand=list(Chem.SDMolSupplier(str(inputs['ligand']),removeHs=False))
            if len(ligand)!=1 or ligand[0] is None:raise ValueError('One actual chemically valid ligand SDF required')
            if qc.get('inputs',{}).get('ligand')!=sha(inputs['ligand']):raise ValueError('Input ligand preparation identity absent from the exact QC receipt')
            score=model('score_checkpoint');confidence=model('confidence_checkpoint')
            for file in [score.parent/'model_parameters.yml',confidence.parent/'model_parameters.yml']:
                if file.resolve() not in {q.resolve() for q in models.values()}:raise ValueError('Exact native score/confidence architecture files must be bound')
            cache=Path(p['torch_hub_directory']).resolve()
            for name in ['esm2_t33_650M_UR50D.pt','esm2_t33_650M_UR50D-contact-regression.pt']:
                if (cache/'checkpoints'/name).resolve() not in {q.resolve() for q in models.values()}:raise ValueError('Required actual ESM cache must already exist; no runtime downloads')
            config=out/'explicit_empty_inference_config.json';write(config,{})
            # Native YAML loading occurs after CLI parsing and overwrites CLI
            # values. Use an explicit empty config, never an inherited default.
            args=['--config',str(config),'--protein_path',str(inputs['receptor']),'--ligand_description',str(inputs['ligand']),'--complex_name','reviewed_complex','--out_dir',str(out/'native'),'--model_dir',str(score.parent),'--ckpt',score.name,'--confidence_model_dir',str(confidence.parent),'--confidence_ckpt',confidence.name,'--samples_per_complex',str(p['n_samples']),'--inference_steps',str(p['inference_steps']),'--batch_size',str(p['batch_size'])]
        elif mode=='diffsbdd_generate':
            checkpoint=model('model_file');residues=p['pocket_residues'];present={str(chain.id)+':'+str(res.id[1]) for chain in receptor.get_chains() for res in chain if res.id[2]==' '}
            if not set(residues)<=present:raise ValueError('Every native pocket residue must exist literally in the reviewed receptor; insertion-code pockets need a separate route')
            args=[str(checkpoint),'--pdbfile',str(inputs['receptor']),'--outfile',str(out/'generated.sdf'),'--n_samples',str(p['n_samples']),'--batch_size',str(p['batch_size']),'--num_nodes_lig',str(p['ligand_atoms']),'--timesteps',str(p['inference_steps']),'--all_frags','--resi_list']+residues
            # No sanitization/largest-fragment filtering in the sampler: retain
            # all returned raw molecules, then record validity separately.
        else:
            checkpoint=model('model_file');args=['inference.output_prefix='+str(out/'backbone'),'inference.model_directory_path='+str(checkpoint.parent),'inference.ckpt_override_path='+str(checkpoint),'inference.num_designs='+str(p['n_samples']),'inference.design_startnum='+str(p['seed']),'inference.deterministic=True','inference.write_trajectory=False','contigmap.contigs=['+str(p['backbone_length'])+'-'+str(p['backbone_length'])+']']
        launcher=Path(__file__).with_name('native_author_launcher.py');job={'mode':mode,'repository':str(root),'script':script,'arguments':args,'seed':p['seed'],'accelerator':p['accelerator'],'torch_hub_directory':str(cache) if mode=='diffdock_pose' else None,'native_software_versions':p['native_software_versions'],'version_receipt':str(out/'native_backend_versions.json')};write(out/'native_job.private.json',job);env=os.environ.copy()
        if mode=='diffdock_pose':env['TORCH_HOME']=str(Path(p['torch_hub_directory']).resolve().parent)
        interpreter=Path(p['python_executable'])
        if not interpreter.is_absolute() or not interpreter.is_file():raise ValueError('Reuse existing compatible native server interpreter only')
        with (out/'native.stdout.log').open('xb') as so,(out/'native.stderr.log').open('xb') as se:proc=subprocess.run([str(interpreter),str(launcher),str(out/'native_job.private.json')],cwd=root,env=env,stdout=so,stderr=se,check=False)
        outputs.append((out/'native_job.private.json','native_command'))
        if proc.returncode:raise RuntimeError('Actual native inference failed; inspect logs and do not automatically retry')
        outputs.append((out/'native_backend_versions.json','native_engine_versions'))
        if mode in {'diffdock_pose','diffsbdd_generate'}:
            files=sorted((out/'native/reviewed_complex').glob('rank*_confidence*.sdf')) if mode=='diffdock_pose' else [out/'generated.sdf'];rows=[]
            source_smiles=Chem.MolToSmiles(Chem.RemoveHs(ligand[0]),isomericSmiles=True) if mode=='diffdock_pose' else None
            for fn in files:
                outputs.append((fn,'docking_poses' if mode=='diffdock_pose' else 'generated_molecules'))
                for index,mol in enumerate(Chem.SDMolSupplier(str(fn),sanitize=False,removeHs=False)):
                    state='UNREADABLE';n_atoms=None
                    if mol is not None:
                        n_atoms=mol.GetNumAtoms();valid=Chem.Mol(mol);status=Chem.SanitizeMol(valid,catchErrors=True);state='CHEMICALLY_VALID' if int(status)==0 else 'SANITIZATION_FAILED'
                        if not mol.GetNumConformers() or not np.isfinite(mol.GetConformer().GetPositions()).all():state='INVALID_COORDINATES'
                        if source_smiles is not None and state=='CHEMICALLY_VALID' and Chem.MolToSmiles(Chem.RemoveHs(valid),isomericSmiles=True)!=source_smiles:raise ValueError('Native docking changed the literal input ligand molecular graph/stereochemistry')
                    match=re.fullmatch(r'rank(\d+)_confidence(-?\d+(?:\.\d+)?)\.sdf',fn.name);rows.append({'native_file':fn.relative_to(out).as_posix(),'record_index':index,'state':state,'n_atoms':n_atoms,'native_rank':int(match[1]) if match else None,'native_confidence':float(match[2]) if match else None})
            if not rows or len(rows)!=p['n_samples']:raise ValueError('Actual native sample count differs; retain raw failures/attrition and review, never silently resample or declare complete')
            pd.DataFrame(rows).to_csv(out/'molecule_qc.tsv',sep='\t',index=False);outputs.append((out/'molecule_qc.tsv','molecular_qc'));diag.update(n_returned=len(rows),n_chemically_valid=sum(r['state']=='CHEMICALLY_VALID' for r in rows),interpretation='Native DiffDock pose confidence is not affinity; DiffSBDD generates molecules conditional on a supplied pocket. All raw records retained with validity states; PoseBusters, receptor clashes/strain, controls and independent docking/MD acceptance remain required downstream. No activity claim.')
        else:
            from Bio.PDB import PDBParser
            files=sorted(out.glob('backbone_*.pdb'));rows=[]
            for fn in files:
                atoms=list(PDBParser(QUIET=True).get_structure(fn.stem,str(fn)).get_atoms());cas=[a for a in atoms if a.name=='CA'];positions=np.asarray([a.coord for a in atoms])
                if len(cas)!=p['backbone_length'] or not np.isfinite(positions).all():raise ValueError('Native RFdiffusion backbone length/coordinate QC failed')
                outputs.append((fn,'protein_backbones'));trb=fn.with_suffix('.trb')
                if not trb.is_file():raise ValueError('Native RFdiffusion provenance metadata absent')
                outputs.append((trb,'native_opaque_metadata'));rows.append({'native_file':fn.name,'n_residues':len(cas),'n_atoms':len(atoms),'scope':'unconditional_backbone_only'})
            if len(files)!=p['n_samples']:raise ValueError('Actual native RFdiffusion design count differs')
            pd.DataFrame(rows).to_csv(out/'backbone_qc.tsv',sep='\t',index=False);outputs.append((out/'backbone_qc.tsv','backbone_qc'));diag.update(n_backbones=len(files),interpretation='Original RFdiffusion unconditional fixed-length backbone sampling only. Poly-glycine sequence/backbone coordinates are not a designed functional protein or validated binder. Native TRB pickle is preserved opaque and never unpickled by acceptance. Sequence design, folding/structure and function require distinct downstream workflows.')
        for fn,role in [('native.stdout.log','backend_stdout'),('native.stderr.log','backend_stderr')]:
            if (out/fn).stat().st_size:outputs.append((out/fn,role))
    write(out/'diagnostics.json',diag);outputs.append((out/'diagnostics.json','diagnostics'));write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
