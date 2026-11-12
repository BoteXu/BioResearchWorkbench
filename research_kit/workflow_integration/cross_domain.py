"""Read only selected evidence tables; validate identity and claim transfers, fit nothing."""
from acceptance import load,rows,selected,sha

def audit(root,request):
    files={}
    for row in request['files']:
        path=selected(root,row['path'])
        if sha(path)!=row['sha256'] or path.stat().st_size!=row['bytes']:raise ValueError('Cross-domain evidence bytes changed')
        if row['id'] in files:raise ValueError('Duplicate selected evidence file')
        files[row['id']]=path
    _,entities=rows(files[request['entity_file_id']]);_,links=rows(files[request['mapping_file_id']])
    identifiers={};issues=[]
    for entity in entities:
        if entity['entity_id'] in identifiers:raise ValueError('Duplicate canonical entity ID')
        if not all(entity.get(k) for k in ('entity_type','species','namespace','version','source_id')):issues.append('incomplete_entity_context:'+entity['entity_id'])
        identifiers[entity['entity_id']]=entity
    adjacency={}
    for link in links:
        a=identifiers.get(link['from_id']);b=identifiers.get(link['to_id'])
        if a is None or b is None:issues.append('unresolved_mapping_endpoint');continue
        if link.get('evidence_file_id') not in files:issues.append('mapping_evidence_not_selected')
        if link.get('mapping_status') not in {'unique','ambiguous','unmapped'}:issues.append('mapping_status_missing')
        if a['species']!=b['species'] and link.get('relation')!='reviewed_orthology':issues.append('cross_species_mapping_unqualified')
        adjacency.setdefault(link['from_id'],[]).append(link)
    _,candidates=rows(files[request['candidate_file_id']]);handoffs=[]
    for row in candidates:
        chain=[row.get(k) for k in ('gene_id','transcript_id','protein_id','structure_id')];problems=[]
        if any(k not in identifiers for k in chain):problems.append('incomplete_canonical_chain')
        else:
            for entity,kind in zip(chain,('gene','transcript','protein_isoform','structure')):
                if identifiers[entity]['entity_type']!=kind:problems.append('entity_type_mismatch:'+kind)
            for a,b in zip(chain,chain[1:]):
                edges=[r for r in adjacency.get(a,[]) if r['to_id']==b]
                if len(edges)!=1 or edges[0]['mapping_status']!='unique':problems.append('ambiguous_or_missing_isoform_structure_mapping')
            if len({identifiers[x]['species'] for x in chain})!=1:problems.append('cross_species_chain_requires_separate_transfer_review')
            if identifiers[chain[2]]['entity_type']!='protein_isoform':problems.append('gene_level_to_unspecified_protein_transfer')
        for name in ('tissue','cell_context','contrast','effect_scale','source_cohort_id','evidence_file_id'):
            if not row.get(name):problems.append('candidate_context_missing:'+name)
        if row.get('evidence_file_id') not in files:problems.append('candidate_source_not_selected')
        if row.get('measurement_state') not in {'observed','predicted','imputed'}:problems.append('measurement_state_missing')
        if row.get('measurement_state')!='observed':problems.append('prediction_or_imputation_is_not_measured_target_support')
        if row.get('effect_direction') not in {'up','down','uncertain','not_estimable'}:problems.append('invalid_effect_direction')
        if row.get('effect_direction') in {'uncertain','not_estimable'}:problems.append('direction_not_established')
        handoffs.append({**row,'state':'HOLD' if problems else 'IDENTITY_READY_FOR_STRUCTURAL_REVIEW','issues':sorted(set(problems)),
                         'binding_activity_established':False,'protein_activity_direction':'not_inferred_from_expression',
                         'causal_mechanism_established':False})
    groups={}
    for row in candidates:groups.setdefault(row.get('source_cohort_id'),[]).append(row.get('candidate_id'))
    return {'issues':sorted(set(issues)),'handoffs':handoffs,'shared_cohort_evidence_groups':groups,
      'shared_cohort_counts_as_independent_replication':False,'automatic_docking_dispatch':False,
      'scientific_validity':'Identity consistency only; inspect original assay, model, direction and uncertainty',
      'public_upload':False}
