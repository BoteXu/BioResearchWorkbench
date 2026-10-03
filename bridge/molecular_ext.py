"""Bounded molecular descriptors and rigid-receptor single-ligand Vina docking."""
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from transcriptomics_ext import _context,_folder,_finish,_workflow
from compute_policy import require_local


def molecular_descriptors(smiles: list) -> dict:
    """RDKit descriptors for at most 100 explicit SMILES; no property is an experimental ADMET measurement."""
    require_local()
    if not isinstance(smiles,list) or not 1<=len(smiles)<=100 or any(not isinstance(s,str) or len(s)>2000 for s in smiles):
        raise ValueError('Provide 1..100 bounded SMILES strings')
    from rdkit import Chem
    from rdkit.Chem import Descriptors,Lipinski
    from rdkit import rdBase
    rows = []
    for text in smiles:
        molecule = Chem.MolFromSmiles(text)
        if molecule is None:
            rows.append({'smiles':text,'state':'invalid'})
            continue
        rows.append({'smiles':text,'canonical_smiles':Chem.MolToSmiles(molecule),'state':'computed','molecular_weight':Descriptors.MolWt(molecule),'logP_estimate':Descriptors.MolLogP(molecule),'tpsa':Descriptors.TPSA(molecule),'h_bond_donors':Lipinski.NumHDonors(molecule),'h_bond_acceptors':Lipinski.NumHAcceptors(molecule),'rotatable_bonds':Lipinski.NumRotatableBonds(molecule),'formal_charge':Chem.GetFormalCharge(molecule)})
    return {'success':True,'backend':'RDKit','backend_version':rdBase.rdkitVersion,'rows':rows,'limitations':['Descriptor calculations do not establish absorption, toxicity, target binding or clinical activity.','No protonation-state, tautomer, stereochemistry or salt standardization is silently performed.']}


def _atoms(path):
    file = Path(path).resolve(strict=True)
    if file.suffix.lower()!='.pdbqt' or not 0<file.stat().st_size<=10000000:
        raise ValueError('Provide a prepared PDBQT no larger than 10 MB')
    raw = file.read_bytes()
    text = raw.decode('utf8')
    atoms = []
    for line in text.splitlines():
        if line.startswith(('ATOM  ','HETATM')):
            try:
                xyz = [float(line[i:i+8]) for i in (30,38,46)]
                charge = float(line[70:76]); atom_type = line[77:].strip()
            except ValueError:
                raise ValueError('Malformed PDBQT coordinates or partial charge')
            if len(line)<78 or not atom_type or not all(math.isfinite(v) for v in xyz+[charge]):
                raise ValueError('PDBQT requires finite coordinates, partial charge and atom type')
            atoms.append({'xyz':xyz,'type':atom_type})
    if not atoms:
        raise ValueError('PDBQT has no atoms')
    return text,atoms,hashlib.sha256(raw).hexdigest()


def audit_docking_inputs(receptor_path: str, ligand_path: str, center: list, box_size: list, context: dict) -> dict:
    """Validate prepared PDBQT and explicit bounded search geometry; preparation chemistry remains unverified."""
    _context(context)
    if any(not isinstance(v,list) or len(v)!=3 for v in (center,box_size)):
        raise ValueError('Center and box size require three finite numeric coordinates')
    if any(type(x) not in {int,float} or not math.isfinite(x) for x in center+box_size) or any(not 1<=x<=40 for x in box_size):
        raise ValueError('Use finite coordinates and local box edges 1..40 Angstrom')
    receptor,ra,rh = _atoms(receptor_path)
    ligand,la,lh = _atoms(ligand_path)
    if len(ra)>100000 or len(la)>300: raise ValueError('Atom count exceeds single-ligand local limit')
    if any(line.startswith(('ROOT','BRANCH','TORSDOF')) for line in receptor.splitlines()): raise ValueError('Provide a rigid receptor PDBQT')
    if 'ROOT' not in ligand.splitlines() or 'ENDROOT' not in ligand.splitlines() or not re.search(r'^TORSDOF\s+\d+\s*$',ligand,re.M):
        raise ValueError('Prepared ligand requires ROOT/ENDROOT/TORSDOF records')
    nearby = sum(all(abs(atom['xyz'][i]-center[i])<=box_size[i]/2+4 for i in range(3)) for atom in ra)
    if not nearby: raise ValueError('Search box does not overlap receptor atoms')
    return {'input_gate_pass':True,'receptor_atoms':len(ra),'ligand_atoms':len(la),'receptor_sha256':rh,'ligand_sha256':lh,'center_angstrom':center,'box_edges_angstrom':box_size,'context':context,'limitations':['Syntax and geometry checks do not verify protonation, atom typing, cofactors, binding-site relevance or preparation quality.','Receptor is rigid; this does not model induced fit.']}


def summarize_vina_poses(poses_path: str) -> dict:
    """Read all Vina result remarks, retaining affinities and reference-pose RMSD bounds."""
    file = Path(poses_path).resolve(strict=True)
    if file.stat().st_size>10000000: raise ValueError('Pose file exceeds local review limit')
    rows = []
    for line in file.read_text(encoding='utf8').splitlines():
        if line.startswith('REMARK VINA RESULT:'):
            parts = line.split(':',1)[1].split()
            if len(parts)!=3: raise ValueError('Malformed Vina result remark')
            values = [float(v) for v in parts]
            if not all(math.isfinite(v) for v in values): raise ValueError('Nonfinite docking score')
            rows.append({'pose':len(rows)+1,'affinity_kcal_mol':values[0],'rmsd_lower_bound_angstrom':values[1],'rmsd_upper_bound_angstrom':values[2]})
    if not rows: raise ValueError('No Vina result remarks found')
    return {'success':True,'poses':rows,'best_affinity_kcal_mol':min(r['affinity_kcal_mol'] for r in rows),'pose_file_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'limitations':['Vina scores are approximate rankings, not measured binding free energies.','Reported RMSD bounds compare predicted poses; they are not crystal-pose redocking validation.','Scores from different receptors, preparation protocols or force fields are not directly interchangeable.']}


@_workflow
def run_vina_docking(receptor_path: str, ligand_path: str, center: list, box_size: list, context: dict, vina: str = 'vina', exhaustiveness: int = 8, poses: int = 9, threads: int = 2, seed: int = 42, timeout_seconds: int = 600) -> dict:
    """Run one prepared ligand against a rigid receptor using installed Vina; preserve failed and partial files."""
    require_local()
    gate = audit_docking_inputs(receptor_path,ligand_path,center,box_size,context)
    if any(type(v) is not int for v in (exhaustiveness,poses,threads,seed,timeout_seconds)) or not 1<=exhaustiveness<=16 or not 1<=poses<=20 or not 1<=threads<=4 or not 1<=seed<=2147483647 or not 10<=timeout_seconds<=900:
        raise ValueError('Invalid bounded docking workload')
    from software_ext import resolve
    executable = resolve('vina',vina)
    if not executable or not re.fullmatch(r'vina(?:_\d[\w.-]*)?',Path(executable).stem.lower()): raise ValueError('Provide an installed AutoDock Vina executable')
    import os
    flags = getattr(subprocess,'CREATE_NO_WINDOW',0)
    checked = subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=15,creationflags=flags)
    if checked.returncode or 'vina' not in checked.stdout.lower(): raise ValueError('Vina version check failed')
    folder = _folder('vina_docking')
    shutil.copyfile(receptor_path,folder/'receptor.pdbqt');shutil.copyfile(ligand_path,folder/'ligand.pdbqt')
    config = {**{f'center_{axis}':value for axis,value in zip('xyz',center)},**{f'size_{axis}':value for axis,value in zip('xyz',box_size)},'exhaustiveness':exhaustiveness,'num_modes':poses,'cpu':threads,'seed':seed}
    (folder/'parameters.json').write_text(json.dumps(config,indent=2),encoding='utf8')
    command = [executable,'--receptor',str(folder/'receptor.pdbqt'),'--ligand',str(folder/'ligand.pdbqt'),'--out',str(folder/'poses.pdbqt')]
    for key,value in config.items(): command.extend(['--'+key,str(value)])
    try:
        with (folder/'backend.log').open('w',encoding='utf8') as log:
            completed = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=timeout_seconds,creationflags=flags,env={**os.environ,'OMP_NUM_THREADS':str(threads)})
        if completed.returncode: raise RuntimeError('Vina failed; inspect the preserved private backend.log')
        result = summarize_vina_poses(str(folder/'poses.pdbqt'))
    except Exception:
        (folder/'state.json').write_text('{"state":"failed_or_interrupted"}\n',encoding='utf8')
        raise
    return _finish(folder,{'workflow':'single_ligand_docking','backend':'AutoDock Vina','backend_version':checked.stdout.strip(),'parameters':config,'context':context,'input_audit':gate,'results':result,'limitations':result['limitations']+['Single run only; use protocol-matched repeats and experimental/reference controls before scientific interpretation.','Large libraries, flexible-receptor work and molecular dynamics belong on the server.']})
