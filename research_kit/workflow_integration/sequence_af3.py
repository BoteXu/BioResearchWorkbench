"""Private sequence provenance and AlphaFold 3 input checking; no local inference or private upload."""
from pathlib import Path
import hashlib
import re
from acceptance import load,selected,sha

def sequence_plan(provider,identifier,sequence_type,approved_public_identifier=False):
    if approved_public_identifier is not True:raise ValueError('Only an explicitly approved public identifier may leave the device')
    if provider=='uniprot':
        if not re.fullmatch('[A-Z0-9]{6,10}(?:-[1-9][0-9]*)?',identifier):raise ValueError('Exact UniProt accession required, not a private name or sequence')
        if sequence_type!='protein':raise ValueError('UniProt route is protein sequence retrieval')
        endpoint='https://rest.uniprot.org/uniprotkb/'+identifier+'.fasta'
        return {'existing_bridge_query':'uniprot','parameters':{'endpoint':endpoint,'max_results':1},
                'sequence_type':'protein','identifier':identifier,'isoform_suffix_preserved':True,
                'required_companion':'UniProt metadata/sequence version and species; FASTA alone does not establish biological identity',
                'public_data_only':True,'private_sequence_uploaded':False}
    if provider=='ensembl':
        if not re.fullmatch(r'ENS[A-Z]*[GPT][0-9]+(?:\.[0-9]+)?',identifier):raise ValueError('Exact Ensembl stable/versioned identifier required')
        if sequence_type not in {'protein','cdna','cds','genomic'}:raise ValueError('Choose explicit sequence type')
        if '.' in identifier:raise ValueError('Resolve the requested version against an explicit archived release; do not silently query the current unversioned sequence')
        return {'existing_bridge_query':'ensembl','parameters':{'endpoint':'https://rest.ensembl.org/sequence/id/'+identifier+'?type='+sequence_type+';content-type=application/json','verbose':False},
                'sequence_type':sequence_type,'identifier':identifier,'required_companion':'lookup/id plus species, assembly and release audit',
                'public_data_only':True,'private_sequence_uploaded':False}
    raise ValueError('Use the installed NCBI sequence tool for RefSeq/GenBank; no duplicate client is added here')

def audit_fasta(path,kind,expected_ids):
    if Path(path).stat().st_size>8_000_000:raise ValueError('Select bounded sequences, not a sequence database')
    text=Path(path).read_text(encoding='utf-8-sig')
    entries=[];name=None;parts=[]
    for line in text.splitlines():
        if line.startswith('>'):
            if name is not None:entries.append((name,''.join(parts)))
            name=line[1:].strip().split()[0];parts=[]
        elif line.strip():
            if name is None:raise ValueError('Sequence without FASTA identifier')
            parts.append(line.strip())
    if name is not None:entries.append((name,''.join(parts)))
    entries=[(name.split('|')[1] if name.startswith(('sp|','tr|')) and len(name.split('|'))>=3 else name,seq) for name,seq in entries]
    ids=[name for name,seq in entries]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected_ids):raise ValueError('FASTA identity differs from selected canonical/isoform identifiers')
    alphabet={'protein':set('ACDEFGHIKLMNPQRSTVWYXBZUO'),'dna':set('ACGTN'),'rna':set('ACGUN')}[kind]
    records=[]
    for name,sequence in entries:
        if not sequence or not set(sequence)<=alphabet:raise ValueError('Invalid alphabet/gap/stop; resolve ambiguity explicitly')
        records.append({'id':name,'length':len(sequence),'sequence_sha256':hashlib.sha256(sequence.encode('ascii')).hexdigest(),
            'ambiguous_symbols':sum(c in ('XBZ' if kind=='protein' else 'N') for c in sequence),'source_file_sha256':sha(path),'sequence_identity_validity':'not_established_without_source/version context'})
    return {'kind':kind,'records':records,'private_sequence_uploaded':False}

from server.af3_input import audit_af3_input
