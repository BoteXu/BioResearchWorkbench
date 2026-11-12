"""Existing local-database MSA acquisition/alignment, coordinate QC and explicit pairing on server."""
from pathlib import Path
import subprocess
import hashlib
from runtime import read,write,sha
from msa_format import parse,from_aligned_fasta

def fasta(path):
    from Bio import SeqIO
    records=list(SeqIO.parse(str(path),'fasta'))
    if not records or len({r.id for r in records})!=len(records):raise ValueError('Explicit unique selected sequences required')
    return [(r.id,str(r.seq).upper()) for r in records]

def qc(text,query,p,out):
    import numpy as np
    import pandas as pd
    entries=parse(text,query,p['kind']);seen=set();measurements=[]
    if not 0<p['neff_identity_threshold']<=1 or type(p['maximum_sequences_for_neff']) is not int or p['maximum_sequences_for_neff']<1:raise ValueError('Explicit valid Neff definition and compute scope required')
    for row in entries:
        sequence=row['match'];observed=sum(c!='-' for c in sequence);matches=sum(a==b for a,b in zip(sequence,query) if a!='-')
        measurements.append({'sequence_id':row['id'],'coverage':observed/len(query),'identity_on_observed_query_columns':matches/observed if observed else 0,
           'duplicate_match_sequence':sequence in seen,'source_sequence_sha256':row['sequence_sha256'],'ambiguous_match_residues':sum(c in ('XBZ' if p['kind']=='protein' else 'N') for c in sequence)})
        if not observed:raise ValueError('An entirely gapped row is not an observed homolog; explicitly filter and preserve its exclusion')
        seen.add(sequence)
    table=pd.DataFrame(measurements);table.to_csv(out/'msa_row_qc.tsv',sep='\t',index=False)
    neff=None;state='not_computed_budget';n=len(entries)
    if n<=p['maximum_sequences_for_neff']:
        matrix=np.array([list(r['match']) for r in entries]);weights=[]
        for i in range(n):
            joint=(matrix!='-')&(matrix[i]!='-');denom=joint.sum(axis=1)
            identity=np.divide(((matrix==matrix[i])&joint).sum(axis=1),denom,out=np.zeros(n,dtype=float),where=denom>0)
            neighbors=int((identity>=p['neff_identity_threshold']).sum())
            weights.append(1/max(neighbors,1))
        neff=float(sum(weights));state='exact_declared_identity_definition'
    summary={'query_sha256':hashlib.sha256(query.encode('ascii')).hexdigest(),'query_length':len(query),'sequences':n,
      'unique_match_sequences':len(seen),'duplicate_match_sequences':n-len(seen),'minimum_coverage':float(table.coverage.min()),
      'median_coverage':float(table.coverage.median()),'effective_sequence_count':neff,'neff_state':state,
      'neff_identity_threshold':p['neff_identity_threshold'],'neff_definition':'sum_i 1/count_j(identity on jointly nongap query columns >= threshold); not assumed equal to HHsuite/AF definitions',
      'query_unchanged':True,'format_coordinate_pass':True,'database_version':p['database_version'],
      'species_orthology_validated':False,'depth_implies_prediction_quality':False,'original_msa_modified':False}
    write(out/'msa_qc.json',summary)
    return [(out/'msa_row_qc.tsv','msa_row_qc'),(out/'msa_qc.json','msa_qc')]

def command(argv,log):
    with Path(log).open('xb') as f:proc=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=False)
    if proc.returncode:raise RuntimeError('Selected existing MSA tool failed; preserve exact command log')

def analyze(inputs,p,out,mode):
    if mode=='msa_pair':
        import pandas as pd
        if p['kind']!='protein':raise ValueError('This manual AF3 row-pairing adapter is for protein chains, not a generic RNA co-evolution model')
        specs=p['chains'];chains={};ledger=pd.read_csv(inputs['pairing_ledger'],sep='\t',dtype=str,keep_default_na=False)
        if len({r['chain_id'] for r in specs})!=len(specs):raise ValueError('Duplicate pairing chain identity')
        for spec in specs:
            import re
            if not re.fullmatch('[A-Z]+',spec['chain_id']):raise ValueError('Safe exact chain identifiers required')
            query=fasta(inputs[spec['query_input_id']])
            if len(query)!=1:raise ValueError('One selected query per chain')
            rows=parse(inputs[spec['msa_input_id']].read_text(encoding='utf8'),query[0][1],p['kind'])
            chains[spec['chain_id']]={'query':query[0][1],'rows':{r['id']:r for r in rows}}
        if ledger[['pair_id','chain_id']].duplicated().any() or set(ledger.chain_id)!=set(chains):raise ValueError('Pairing ledger must have one row per exact chain for each pair')
        outputs=[];a3m={c:'>query\n'+r['query']+'\n' for c,r in chains.items()}
        for pair_id,group in ledger.groupby('pair_id',sort=False):
            if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]*',pair_id):raise ValueError('Safe explicit paired-row identity required')
            if set(group.chain_id)!=set(chains) or len(group)!=len(chains):raise ValueError('Incomplete pair; never fill other-chain gaps to fabricate a paired row')
            observed=group[group.get('measurement_state',pd.Series('observed',index=group.index))!='structural_padding']
            if set(observed.orthology_status)!={'reviewed_unique'}:raise ValueError('Paralog/orthology ambiguity unresolved; use unpaired route or curated evidence')
            if p['pairing_policy']=='same_taxon_unique_ortholog':
                if group.taxon_id.nunique()!=1 or not group.taxon_id.iloc[0]:raise ValueError('Taxon mismatch or missing taxonomic provenance')
            elif p['pairing_policy']!='reviewed_cross_species':raise ValueError('Explicit supported pairing policy required')
            for row in group.to_dict('records'):
                if row.get('measurement_state')=='structural_padding':
                    if p.get('allow_explicit_padding') is not True or row['sequence_id'] or row['source_sequence_sha256']:raise ValueError('Explicit padding must be authorized and must not claim an observed homolog')
                    a3m[row['chain_id']]+='>'+pair_id+'\n'+'-'*len(chains[row['chain_id']]['query'])+'\n';continue
                source=chains[row['chain_id']]['rows'].get(row['sequence_id'])
                if source is None or row['source_sequence_sha256']!=source['sequence_sha256']:raise ValueError('Paired homolog identity/hash differs from actual source MSA')
                a3m[row['chain_id']]+='>'+pair_id+'\n'+source['a3m']+'\n'
        for chain,text in a3m.items():
            path=out/('paired_'+chain+'.a3m');path.write_text(text,encoding='utf8',newline='\n');outputs.append((path,'paired_msa'))
        write(out/'pairing_qc.json',{'pair_count':int(ledger.pair_id.nunique()),'chain_ids':list(chains),'policy':p['pairing_policy'],
           'paired_rows_correspond':True,'orthology_from_high_identity_alone':False,'interaction_established':False,
           'target_af3_field':'unpairedMsa','pairedMsa_must_be_empty':True,'resolve_msa_overlaps':False,'padding_counts_as_observed_homolog':False})
        if 'af3_input' in inputs:
            import copy
            from af3_input import audit_af3_input
            prepared=copy.deepcopy(read(inputs['af3_input']));entities=[]
            for entity in prepared['sequences']:
                if 'protein' not in entity:entities.append(entity);continue
                body=entity['protein'];ids=body['id'] if isinstance(body['id'],list) else [body['id']]
                for chain in ids:
                    if chain not in a3m or body['sequence']!=chains[chain]['query']:raise ValueError('Manual MSA is bound to other AF3 chains/query')
                    new=copy.deepcopy(body);new['id']=chain;new['unpairedMsa']=a3m[chain];new['pairedMsa']='';entities.append({'protein':new})
            prepared['sequences']=entities;audit_af3_input(prepared,False)
            write(out/'af3_manual_msa_input.json',prepared)
            write(out/'manual_msa_receipt.json',{'af3_input_sha256':sha(out/'af3_manual_msa_input.json'),'chain_ids':list(chains),
                 'resolve_msa_overlaps':False,'source_pairing_ledger_sha256':sha(inputs['pairing_ledger']),'padding_is_observed_homolog':False})
            outputs.extend([(out/'af3_manual_msa_input.json','af3_data_json'),(out/'manual_msa_receipt.json','manual_msa_receipt')])
        return outputs+[(out/'pairing_qc.json','pairing_qc')]
    query_records=fasta(inputs['query'])
    if len(query_records)!=1:raise ValueError('Select one query; multi-query binary MSA databases must not be treated as one A3M')
    query_id,query=query_records[0]
    if mode=='msa_qc':return qc(inputs['msa'].read_text(encoding='utf8'),query,p,out)
    if mode=='msa_filter':
        import pandas as pd
        original=parse(inputs['msa'].read_text(encoding='utf8'),query,p['kind']);kept=[];seen=set();decisions=[]
        for i,row in enumerate(original):
            coverage=sum(c!='-' for c in row['match'])/len(query);ambiguity=sum(c in ('XBZ' if p['kind']=='protein' else 'N') for c in row['match'])/len(query)
            reason=[]
            if i:
                if coverage<p['minimum_row_coverage']:reason.append('low_coverage')
                if ambiguity>p['maximum_ambiguity_fraction']:reason.append('ambiguous_residues')
                if p['deduplicate_exact_matches'] and row['match'] in seen:reason.append('duplicate_match_sequence')
            if not reason:kept.append(row);seen.add(row['match'])
            decisions.append({'sequence_id':row['id'],'retained':not reason,'reason':';'.join(reason),'coverage':coverage,'ambiguity_fraction':ambiguity})
        text=''.join('>'+r['id']+'\n'+r['a3m']+'\n' for r in kept)
        (out/'filtered_unpaired.a3m').write_text(text,encoding='utf8',newline='\n');pd.DataFrame(decisions).to_csv(out/'msa_filter_decisions.tsv',sep='\t',index=False)
        return [(out/'filtered_unpaired.a3m','unpaired_msa'),(out/'msa_filter_decisions.tsv','msa_filter_decisions')]+qc(text,query,p,out)
    if mode=='msa_align':
        exe=Path(p['aligner_executable'])
        if not exe.is_absolute() or not exe.is_file() or sha(exe)!=p['aligner_sha256']:raise ValueError('Select exact existing alignment executable')
        records=fasta(inputs['selected_sequences'])
        if query_id not in {r[0] for r in records}:raise ValueError('The actual query must be retained in the selected homolog FASTA')
        aligned=out/'aligned.fasta'
        if p['aligner']=='mafft':
            with aligned.open('xb') as stream,(out/'aligner.log').open('xb') as err:
                proc=subprocess.run([str(exe),'--amino' if p['kind']=='protein' else '--nuc','--auto','--thread',str(p['threads']),str(inputs['selected_sequences'])],stdout=stream,stderr=err,check=False)
            if proc.returncode:raise RuntimeError('MAFFT failed')
        elif p['aligner']=='clustalo':command([str(exe),'--seqtype='+{'protein':'Protein','rna':'RNA','dna':'DNA'}[p['kind']],'--infile='+str(inputs['selected_sequences']),'--outfile='+str(aligned),'--outfmt=fa','--threads='+str(p['threads'])],out/'aligner.log')
        elif p['aligner']=='muscle5':command([str(exe),'-align',str(inputs['selected_sequences']),'-output',str(aligned)],out/'aligner.log')
        else:raise ValueError('Select MAFFT, Clustal Omega or pinned MUSCLE5; no implicit CLI-version conversion')
        from Bio import SeqIO
        alignments=[(r.id,str(r.seq)) for r in SeqIO.parse(str(aligned),'fasta')]
        if {r[0] for r in alignments}!={r[0] for r in records}:raise ValueError('Aligner changed/removed sequence identities')
        text=from_aligned_fasta(alignments,query_id,query)
        (out/'unpaired.a3m').write_text(text,encoding='utf8',newline='\n')
        return [(aligned,'aligned_fasta'),(out/'unpaired.a3m','unpaired_msa')]+qc(text,query,p,out)
    if mode=='msa_search':
        if p['kind']!='protein':raise ValueError('Protein search is not an RNA/DNA MSA pipeline; use appropriate local AF3/HMMER nucleotide route')
        exe=Path(p['mmseqs_executable']);database=Path(p['database_prefix']);manifest=read(inputs['database_manifest'])
        if not exe.is_absolute() or not exe.is_file() or sha(exe)!=p['mmseqs_sha256'] or not Path(str(database)+'.dbtype').is_file():raise ValueError('Existing pinned MMseqs2 and target database required')
        if manifest.get('database_prefix')!=str(database) or manifest.get('release')!=p['database_version'] or manifest.get('release') in {'unknown','latest','main'}:raise ValueError('Database release/path not pinned')
        if manifest.get('dbtype_sha256')!=sha(Path(str(database)+'.dbtype')):raise ValueError('Database identity marker changed')
        from database_identity import verify
        database_identity=verify(database.parent,manifest,p['database_integrity_mode'])
        write(out/'database_verification.json',database_identity)
        qdb=out/'querydb';res=out/'resultdb';tmp=out/'tmp'
        command([str(exe),'createdb',str(inputs['query']),str(qdb),'--dbtype','1'],out/'createdb.log')
        command([str(exe),'search',str(qdb),str(database),str(res),str(tmp),'--threads',str(p['threads']),'-e',str(p['evalue']),
          '--max-seqs',str(p['maximum_hits']),'-s',str(p['sensitivity']),'-c',str(p['minimum_coverage']),'--cov-mode',str(p['coverage_mode'])],out/'search.log')
        command([str(exe),'convertalis',str(qdb),str(database),str(res),str(out/'hits.tsv'),'--format-output','query,target,evalue,bits,pident,qcov,tcov','--threads',str(p['threads'])],out/'convertalis.log')
        command([str(exe),'result2msa',str(qdb),str(database),str(res),str(out/'unpaired.a3m'),'--msa-format-mode','5','--filter-msa','0','--threads',str(p['threads'])],out/'result2msa.log')
        text=(out/'unpaired.a3m').read_text(encoding='utf8');outputs=[(out/'unpaired.a3m','unpaired_msa')]
        if (out/'hits.tsv').stat().st_size:outputs.append((out/'hits.tsv','homology_hits'))
        return outputs+[(out/'database_verification.json','database_verification')]+qc(text,query,p,out)
    raise ValueError('Unknown MSA route')
