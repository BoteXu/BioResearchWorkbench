import hashlib
import re

def audit_af3_input(value,run_data_pipeline=False):
    if not isinstance(value,dict) or value.get('dialect')!='alphafold3' or value.get('version') not in {1,2,3,4}:raise ValueError('Use a pinned engine-compatible native AlphaFold3 input dialect/version')
    if not isinstance(value.get('name'),str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,80}',value['name']):raise ValueError('Use a private safe job alias, not a personal name')
    seeds=value.get('modelSeeds')
    if not isinstance(seeds,list) or not seeds or len(set(seeds))!=len(seeds) or any(type(s) is not int or s<0 for s in seeds):raise ValueError('Explicit distinct nonnegative integer seeds required')
    chains=[];entities=[];lengths={};smiles_chains=set()
    for row in value.get('sequences',[]):
        if len(row)!=1 or next(iter(row)) not in {'protein','rna','dna','ligand'}:raise ValueError('Explicit molecule entity type required')
        kind=next(iter(row));entity=row[kind];ids=entity.get('id');ids=ids if isinstance(ids,list) else [ids]
        if 'description' in entity and value['version']<4:raise ValueError('Description fields require a compatible version-4 input schema')
        if not ids or any(not isinstance(i,str) or not re.fullmatch('[A-Z]+',i) for i in ids):raise ValueError('Unique uppercase chain IDs required')
        chains+=ids
        if kind!='ligand':
            sequence=entity.get('sequence','');alphabet={'protein':set('ACDEFGHIKLMNPQRSTVWY'),'rna':set('ACGU'),'dna':set('ACGT')}[kind]
            if not sequence or not set(sequence)<=alphabet:raise ValueError('Resolve unknown/nonstandard sequence with explicit supported modification/CCD mapping')
            if not run_data_pipeline and kind=='protein' and any(k not in entity for k in ('unpairedMsa','pairedMsa','templates')):
                raise ValueError('Offline inference requires explicit supplied MSA/template fields; empty is a deliberate no-MSA/no-template choice')
            if not run_data_pipeline and kind in {'protein','rna'}:
                msa_fields=('unpairedMsa','pairedMsa') if kind=='protein' else ('unpairedMsa',)
                if any(not isinstance(entity.get(k),str) for k in msa_fields):raise ValueError('Offline MSA must be explicit A3M text or deliberate empty string, not absent/null')
                if kind=='protein' and not isinstance(entity.get('templates'),list):raise ValueError('Offline templates must be an explicit list')
            for template in entity.get('templates',[]):
                q=template.get('queryIndices');t=template.get('templateIndices')
                if not isinstance(template.get('mmcif'),str) or not template['mmcif'] or not isinstance(q,list) or not isinstance(t,list) or len(q)!=len(t) or not q:
                    raise ValueError('Template must bind inline coordinates and equal nonempty mapping axes')
                if any(type(i) is not int or i<0 or i>=len(sequence) for i in q) or any(type(i) is not int or i<0 for i in t):raise ValueError('Template residue mapping is outside sequence or invalid')
            entities.append({'kind':kind,'ids':ids,'length':len(sequence),'sequence_sha256':hashlib.sha256(sequence.encode('ascii')).hexdigest()})
            lengths.update({chain:len(sequence) for chain in ids})
            for modification in entity.get('modifications',[]):
                position_key='ptmPosition' if kind=='protein' else 'basePosition'
                chemical_key='ptmType' if kind=='protein' else 'modificationType'
                if type(modification.get(position_key)) is not int or not 1<=modification[position_key]<=len(sequence) or not modification.get(chemical_key):
                    raise ValueError('Modification must identify a valid sequence position and explicit chemical component')
        elif ('ccdCodes' in entity)==('smiles' in entity):raise ValueError('Ligand must choose CCD codes or SMILES, not both/neither')
        elif 'smiles' in entity:smiles_chains.update(ids)
    if not chains or len(set(chains))!=len(chains):raise ValueError('Missing or repeated chain ID')
    # The local server process must not resolve paths embedded in third-party input to private locations.
    def check_paths(obj):
        if isinstance(obj,dict):
            for key,v in obj.items():
                if key.endswith('Path'):raise ValueError('Inline or explicitly materialize/bind MSA/template/CCD data; embedded filesystem paths are not accepted')
                check_paths(v)
        elif isinstance(obj,list):
            for item in obj:check_paths(item)
    check_paths(value)
    for pair in value.get('bondedAtomPairs',[]):
        if len(pair)!=2 or any(not isinstance(atom,list) or len(atom)!=3 or atom[0] not in chains or type(atom[1]) is not int or atom[1]<1 or not atom[2] for atom in pair):
            raise ValueError('Covalent atom mapping must refer to explicit chain/residue/atom identities')
        if any(atom[0] in lengths and atom[1]>lengths[atom[0]] for atom in pair):raise ValueError('Covalent mapping extends beyond actual sequence')
        if any(atom[0] in smiles_chains for atom in pair):raise ValueError('Covalent ligand atom names require explicit CCD, not SMILES-only input')
        if all(atom[0] in lengths for atom in pair):raise ValueError('Explicit polymer-polymer bond specification is not supported by this AF3 input adapter')
    return {'chain_ids':chains,'entities':entities,'model_seeds':seeds,'schema_version':value['version'],
      'sample_interpretation':'stochastic predicted candidates, not equilibrium populations or independent biological replicates',
      'inference_executed':False,'private_upload':False}

def audit_chain_provenance(contract,manifest):
    records=manifest.get('chains',[]);ids=[r.get('chain_id') for r in records]
    if len(ids)!=len(set(ids)) or set(ids)!=set(contract['chain_ids']):raise ValueError('Every physical chain must have one source mapping')
    lookup={r['chain_id']:r for r in records}
    for entity in contract['entities']:
        for chain in entity['ids']:
            row=lookup[chain]
            for field in ('source_accession','species','sequence_version','isoform_or_construct','source_receipt_sha256'):
                if not row.get(field) or str(row[field]).lower() in {'unknown','latest','na'}:raise ValueError('Unresolved sequence provenance: '+field)
            if row.get('sequence_sha256')!=entity['sequence_sha256']:raise ValueError('AF3 sequence differs from selected isoform/construct source')
            if not re.fullmatch('[a-f0-9]{64}',row['source_receipt_sha256']):raise ValueError('Source sequence receipt needs exact hash')
    return {'sequence_sources_bound':True,'chain_ids':ids,'sequence_homology_implies_function':False}
