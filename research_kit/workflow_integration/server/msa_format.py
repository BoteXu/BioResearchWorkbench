"""A3M coordinate parser shared by server workers and bounded format tests. No inference."""
import hashlib
import re

def parse(text,query,alphabet='protein'):
    allowed=set('ACDEFGHIKLMNPQRSTVWYXBZUO' if alphabet=='protein' else 'ACGUN' if alphabet=='rna' else 'ACGTN')
    entries=[];name=None;parts=[]
    for line in text.splitlines():
        if line.startswith('#') or not line.strip():continue
        if line.startswith('>'):
            if name is not None:entries.append((name,''.join(parts)))
            name=line[1:].split()[0];parts=[]
        else:
            if name is None:raise ValueError('MSA sequence before header')
            parts.append(line.strip())
    if name is not None:entries.append((name,''.join(parts)))
    if not entries or len({x[0] for x in entries})!=len(entries):raise ValueError('Empty MSA or duplicate sequence ID')
    rows=[]
    for name,sequence in entries:
        if not sequence or '\x00' in sequence or any(c!='-' and c!='.' and c.upper() not in allowed for c in sequence):raise ValueError('A3M contains invalid residue or binary database output')
        match=''.join(c for c in sequence if not c.islower() and c!='.')
        if len(match)!=len(query):raise ValueError('A3M match columns do not correspond to exact query length')
        rows.append({'id':name,'a3m':sequence,'match':match,'sequence_sha256':hashlib.sha256(sequence.replace('-','').replace('.','').upper().encode('ascii')).hexdigest()})
    if rows[0]['match']!=query or rows[0]['a3m']!=query:raise ValueError('First A3M row must be the exact ungapped query, not a homolog/isoform/truncation')
    return rows

def from_aligned_fasta(entries,query_id,query):
    if len({name for name,seq in entries})!=len(entries):raise ValueError('Duplicate alignment ID')
    matches=[seq for name,seq in entries if name==query_id]
    if len(matches)!=1 or matches[0].replace('-','').upper()!=query:raise ValueError('Aligned query identity changed')
    master=matches[0];out=[]
    for name,sequence in entries:
        if len(sequence)!=len(master):raise ValueError('Aligned FASTA column count mismatch')
        result=[]
        for q,residue in zip(master,sequence):
            if q=='-':
                if residue!='-':result.append(residue.lower())
            else:result.append(residue.upper())
        out.append((name,''.join(result)))
    out.sort(key=lambda item:item[0]!=query_id)
    text=''.join('>'+name+'\n'+sequence+'\n' for name,sequence in out)
    parse(text,query);return text
