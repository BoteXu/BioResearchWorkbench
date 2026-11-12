"""Run an existing licensed AlphaFold3 installation, preserve every seed/sample and source."""
from pathlib import Path
import subprocess
import json
import math
import hashlib
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    import pandas as pd
    from af3_input import audit_af3_input,audit_chain_provenance
    data_only=mode=='af3_data_pipeline'
    af_input=read(inputs['af3_input']);contract=audit_af3_input(af_input,True if data_only else p['run_data_pipeline'])
    provenance=audit_chain_provenance(contract,read(inputs['sequence_manifest']))
    engine=Path(p['run_alphafold_script']);python=Path(p['af3_python'])
    if not engine.is_file() or not engine.is_absolute() or engine.name!='run_alphafold.py' or sha(engine)!=p['engine_script_sha256']:raise ValueError('Select exact existing reviewed AF3 engine source')
    if not python.is_file() or not python.is_absolute():raise ValueError('Existing AF3 environment required')
    if not p['engine_revision'] or p['engine_revision'] in {'latest','main','unknown'} or p['input_schema_version']!=af_input['version']:raise ValueError('Pinned engine/schema revision required')
    if data_only:
        database=Path(p['database_directory']);manifest=read(inputs['database_manifest'])
        if not database.is_absolute() or not database.is_dir() or manifest.get('database_directory')!=str(database) or not manifest.get('releases'):
            raise ValueError('Pin existing local AF3 database collection and source releases')
        from database_identity import verify
        db_identity=verify(database,manifest,p['database_integrity_mode'])
        output=out/'af3_data';output.mkdir()
        argv=[str(python),str(engine),'--json_path='+str(inputs['af3_input']),'--db_dir='+str(database),'--output_dir='+str(output),'--run_data_pipeline=true','--run_inference=false']
        with (out/'af3_data.log').open('xb') as f:proc=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=False)
        if proc.returncode:raise RuntimeError('AF3 local MSA/template data pipeline failed')
        data_files=list(output.rglob('*_data.json'))
        if len(data_files)!=1:raise ValueError('Expected one exact completed AF3 data JSON')
        prepared=read(data_files[0]);prepared_contract=audit_af3_input(prepared,False)
        audit_chain_provenance(prepared_contract,read(inputs['sequence_manifest']))
        if prepared_contract['chain_ids']!=contract['chain_ids'] or prepared_contract['model_seeds']!=contract['model_seeds']:raise ValueError('Data pipeline changed chain identity/seed specification')
        from msa_format import parse
        registry=[];outputs=[(data_files[0],'af3_data_json')]
        for entity in prepared['sequences']:
            kind=next(iter(entity));body=entity[kind];ids=body['id'] if isinstance(body['id'],list) else [body['id']]
            for chain in ids:
                for field,role in [('unpairedMsa','unpaired_msa'),('pairedMsa','paired_msa')]:
                    text=body.get(field)
                    if text is None:continue
                    record={'chain':chain,'kind':kind,'role':role,'state':'empty_explicit' if not text else 'present','query_sha256':hashlib.sha256(body['sequence'].encode('ascii')).hexdigest()}
                    if text:
                        rows=parse(text,body['sequence'],kind);path=out/(chain+'_'+field+'.a3m');path.write_text(text,encoding='utf8',newline='\n')
                        record.update(rows=len(rows),sha256=sha(path));outputs.append((path,role))
                    registry.append(record)
                for index,template in enumerate(body.get('templates',[])):
                    path=out/('template_'+chain+'_'+str(index)+'.cif');path.write_text(template['mmcif'],encoding='utf8',newline='\n');outputs.append((path,'template_structure'))
        write(out/'msa_registry.json',registry)
        write(out/'data_diagnostics.json',{'query_chain_ids':contract['chain_ids'],'sequence_provenance':provenance,
            'database_integrity':db_identity,
            'database_manifest_sha256':sha(inputs['database_manifest']),'inference_executed':False,'query_sequences_uploaded':False,
            'source':'existing AF3 local data pipeline; no external MSA web service','pairing_interpretation':'Native pipeline association, not proof of physical interaction'})
        return outputs+[(out/'msa_registry.json','msa_registry'),(out/'data_diagnostics.json','diagnostics'),(out/'af3_data.log','backend_log')]
    import gemmi
    model_dir=Path(p['model_directory'])
    if not model_dir.is_dir():raise ValueError('Existing authorized AF3 weights required; never download here')
    if p['weights_access_confirmed'] is not True or not p['engine_revision'] or p['engine_revision'] in {'latest','main','unknown'} or p['input_schema_version']!=af_input['version']:raise ValueError('Pinned engine/schema and legitimate model access review required')
    if type(p['samples_per_seed']) is not int or p['samples_per_seed']<1:raise ValueError('Explicit positive diffusion-sample budget')
    if p['selected_pair'] and (len(p['selected_pair'])!=2 or len(set(p['selected_pair']))!=2 or not set(p['selected_pair'])<=set(contract['chain_ids'])):raise ValueError('Selected interface chain pair is ambiguous')
    output=out/'af3_output';output.mkdir()
    argv=[str(python),str(engine),'--json_path='+str(inputs['af3_input']),'--model_dir='+str(model_dir),'--output_dir='+str(output),
      '--run_data_pipeline='+str(p['run_data_pipeline']).lower(),'--run_inference=true','--num_diffusion_samples='+str(p['samples_per_seed']),
      '--num_recycles='+str(p['num_recycles'])]
    if p['msa_pairing_mode']=='manual_rows':
        if p['resolve_msa_overlaps'] is not False or p['run_data_pipeline'] is not False:raise ValueError('Preserve manually aligned rows: no data-pipeline rerun or MSA overlap resolution')
        receipt=read(inputs['manual_msa_receipt'])
        protein_ids={chain for entity in contract['entities'] if entity['kind']=='protein' for chain in entity['ids']}
        if receipt.get('af3_input_sha256')!=sha(inputs['af3_input']) or set(receipt.get('chain_ids',[]))!=protein_ids:raise ValueError('Manual paired rows are bound to another AF3 input')
        from msa_format import parse
        row_axes=[]
        for entity in af_input['sequences']:
            if 'protein' in entity:
                body=entity['protein']
                if body.get('pairedMsa')!='':raise ValueError('Manual pairing must go into unpairedMsa; pairedMsa must be empty')
                row_axes.append([r['id'] for r in parse(body['unpairedMsa'],body['sequence'])])
        if any(axis!=row_axes[0] for axis in row_axes[1:]):raise ValueError('Manual multi-chain MSA row order differs')
    elif p['msa_pairing_mode']!='native_heuristic':raise ValueError('Choose explicit native or manual-row pairing route')
    argv+=['--resolve_msa_overlaps='+str(p['resolve_msa_overlaps']).lower()]
    if p['run_data_pipeline']:
        db=Path(p['database_directory'])
        if not db.is_dir() or not db.is_absolute():raise ValueError('Use existing local server AF3 databases only')
        argv+=['--db_dir='+str(db)]
    with (out/'af3.log').open('xb') as f:proc=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=False)
    if proc.returncode:raise RuntimeError('AF3 engine failed; preserve af3.log and partial outputs, do not automatically retry')
    directories=list(output.glob(af_input['name'].lower()+'/seed-*_sample-*'))
    if not directories:directories=[q for q in output.rglob('seed-*_sample-*') if q.is_dir()]
    records=[];outputs=[];seen=set()
    for folder in sorted(directories):
        import re
        match=re.fullmatch('seed-([0-9]+)_sample-([0-9]+)',folder.name)
        if not match:continue
        seed,sample=map(int,match.groups());key=(seed,sample)
        if key in seen:raise ValueError('Duplicate AF3 seed/sample output')
        seen.add(key)
        structures=[q for q in folder.glob('*.cif') if q.name=='model.cif' or q.name.endswith('_model.cif')]
        summaries=[q for q in folder.glob('*confidences.json') if q.name.endswith('summary_confidences.json')]
        confidence=[q for q in folder.glob('*confidences.json') if not q.name.endswith('summary_confidences.json')]
        if len(structures)!=1 or len(summaries)!=1 or len(confidence)!=1:raise ValueError('AF3 sample missing unique coordinates/full confidence/summary files')
        structure=gemmi.read_structure(str(structures[0]));summary=read(summaries[0]);full=read(confidence[0])
        if len(structure)!=1:raise ValueError('AF3 output model axis unexpected')
        actual=[c.name for c in structure[0]]
        if set(actual)!=set(contract['chain_ids']):raise ValueError('Predicted chain identities differ from requested stoichiometry')
        token_ids=full.get('token_chain_ids');ordered=list(dict.fromkeys(token_ids)) if isinstance(token_ids,list) else None
        if ordered is None or set(ordered)!=set(actual):raise ValueError('Full token-chain mapping missing; never infer chain-pair axes from file order')
        chain_pair=summary.get('chain_pair_iptm');pae=summary.get('chain_pair_pae_min')
        if not isinstance(chain_pair,list) or len(chain_pair)!=len(ordered) or any(len(r)!=len(ordered) for r in chain_pair):raise ValueError('Chain-pair confidence axis mismatch')
        values=[v for row in chain_pair for v in row]
        if any(v is not None and (not isinstance(v,(float,int)) or not math.isfinite(v) or not 0<=v<=1) for v in values):raise ValueError('Invalid chain-pair confidence')
        row={'seed':seed,'sample':sample,'structure_sha256':sha(structures[0]),'summary_sha256':sha(summaries[0]),
             'ordered_chain_ids':';'.join(ordered),'ranking_score':summary.get('ranking_score'),'ptm':summary.get('ptm'),'iptm':summary.get('iptm'),
             'has_clash':summary.get('has_clash'),'selected_pair_iptm':None,'selected_pair_min_pae':None}
        if p['selected_pair']:
            i,j=[ordered.index(x) for x in p['selected_pair']];row['selected_pair_iptm']=chain_pair[i][j]
            if isinstance(pae,list) and len(pae)==len(ordered):row['selected_pair_min_pae']=pae[i][j]
        records.append(row)
        outputs.extend([(structures[0],'predicted_structure'),(summaries[0],'af3_summary'),(confidence[0],'af3_full_confidence')])
    expected={(seed,sample) for seed in contract['model_seeds'] for sample in range(p['samples_per_seed'])}
    if seen!=expected:raise ValueError('Missing/unexpected AF3 seed/sample outputs; preserve full campaign denominator')
    pd.DataFrame(records).to_csv(out/'af3_samples.tsv',sep='\t',index=False)
    write(out/'af3_diagnostics.json',{'expected_predictions':len(expected),'returned_predictions':len(records),'input_contract':contract,
       'sequence_provenance':provenance,
       'engine_revision':p['engine_revision'],'engine_script_sha256':p['engine_script_sha256'],'all_seed_samples_preserved':True,
       'confidence_is_affinity':False,'equilibrium_conformer_population_established':False,'biological_replication_count':0,
       'next':'Actual structure QC, interface/pose checks and explicitly reviewed simulation preparation'})
    return outputs+[(out/'af3_samples.tsv','af3_sample_table'),(out/'af3_diagnostics.json','diagnostics'),(out/'af3.log','backend_log')]
