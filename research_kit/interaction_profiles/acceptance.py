"""Bounded result inspection, with no local molecular computation."""
from pathlib import Path
import math
from contracts import read,sha,digest,selected,sources,validate
from server.return_binding import receipt_index,proof_issues,preview_issues
MAX=8_000_000
RULES={'profile_scores':{'required':['candidate_id','reference_id','parent_id','microstate_id','shape_similarity','esp_surface_similarity','pharmacophore_similarity','pharmacophore_assessed','coordinate_mode','protein_ligand_energy_estimated'],'empty_valid':True},'candidate_denominator':{'required':['candidate_id','state'],'empty_valid':False}}
def small(f):
    if not 0<Path(f).stat().st_size<=MAX:raise ValueError('Select a bounded nonempty JSON summary <=8 MB')
    return read(f)

def _reported_bool(value):
    if type(value) is bool:return value
    if isinstance(value,str) and value.lower() in ('true','false'):return value.lower()=='true'
    return None

def _positive_counts(mapping):
    return isinstance(mapping,dict) and all(isinstance(k,str) and bool(k) and type(v) is int and v>0 for k,v in mapping.items())

def _identity_links(r,content,proof,bound,variants):
    """Cross-check full identity maps and bounded rows against source/complete candidate reports."""
    issues=[];rows=content['source_structures.private.json'].get('molecules')
    if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):return ['source_molecule_manifest_malformed']
    ids=[x.get('id') for x in rows]
    if any(not isinstance(x,str) or not x for x in ids) or len(ids)!=len(set(ids)):return ['source_molecule_identity_duplicated_or_missing']
    refs=[x['id'] for x in rows if x.get('role')=='reference'];inputs={x['id']:x for x in rows if x.get('role')!='reference'}
    if not refs or (r['method'] in ('score_fixed_pose','align_profiles') and len(refs)!=1):issues.append('source_reference_denominator_invalid')
    eligible=content['eligible_candidate_outputs.private.json'];by_variant={v:{} for v in variants}
    for x in eligible:
        v=x.get('variant');name=x.get('candidate_id')
        if v not in by_variant or not isinstance(name,str) or not name:issues.append('eligible_candidate_identity_invalid');continue
        if name in by_variant[v]:issues.append('duplicate_candidate_eligibility_identity')
        by_variant[v][name]=x
        if r['method']!='shepherd2_generate':
            source=inputs.get(name)
            if source is None or any(not isinstance(source.get(k),str) or not source[k] or x.get(k)!=source[k] for k in ('parent_id','microstate_id')):issues.append('scored_candidate_source_chemical_identity_changed')
            if x.get('path')!=v+'/'+name+'.scored.sdf':issues.append('scored_candidate_SDF_path_not_canonical')
    proofs={(x.get('variant'),x.get('role')):x for x in proof if isinstance(x,dict)}
    for v in variants:
        if r['method']=='shepherd2_generate':
            reports={name:content[v+'/'+name+'.constraints.private.json'] for name in ('generated_'+str(i) for i in range(r['parameters']['n_samples']))}
            states={name:x.get('state') for name,x in reports.items()}
            score_candidates=by_variant[v]
        else:
            reports={};states={name:('REFERENCE_PROFILE_PREPARED' if r['method']=='prepare_reference_profiles' else 'SCORED') for name in (refs if r['method']=='prepare_reference_profiles' else inputs)}
            score_candidates={} if r['method']=='prepare_reference_profiles' else inputs
        expected_pairs={name:{ref:1 for ref in refs} for name in score_candidates}
        score_proof=proofs.get((v,'profile_scores'),{})
        actual_pairs=score_proof.get('candidate_reference_row_counts')
        if not isinstance(actual_pairs,dict) or any(not _positive_counts(x) for x in actual_pairs.values()) or actual_pairs!=expected_pairs:issues.append('complete_candidate_reference_coverage_changed')
        expected_rows={name:len(refs) for name in score_candidates}
        if score_proof.get('candidate_row_counts')!=expected_rows or score_proof.get('rows')!=sum(expected_rows.values()):issues.append('complete_profile_score_identity_denominator_changed')
        full_identities=[{'candidate_id':str(name),'reference_id':str(ref),'parent_id':str(row.get('parent_id','')),'microstate_id':str(row.get('microstate_id','')),'coordinate_mode':'generated_source_frame_reference_'+ref if r['method']=='shepherd2_generate' else r['method']} for name,row in score_candidates.items() for ref in refs]
        full_identities.sort(key=lambda x:(x['candidate_id'],x['reference_id']))
        if score_proof.get('identity_binding_sha256')!=digest(full_identities):issues.append('complete_profile_score_chemical_identity_binding_changed')
        if type(score_proof.get('full_value_audit_issues')) is not list or score_proof['full_value_audit_issues']!=[]:issues.append('complete_profile_score_value_audit_failed_or_missing')
        if r['method']=='shepherd2_generate':
            try:
                complete_values=[]
                for name in score_candidates:
                    fidelity={x['reference_id']:x for x in reports[name]['profile_fidelity_scores']}
                    for ref in refs:
                        row=fidelity[ref];pharm=row['pharmacophore_similarity']
                        complete_values.append({'candidate_id':str(name),'reference_id':str(ref),'shape_similarity':float(row['shape_similarity']),'esp_surface_similarity':float(row['esp_surface_similarity']),'pharmacophore_similarity':None if pharm is None else float(pharm),'pharmacophore_assessed':pharm is not None,'protein_ligand_energy_estimated':False})
                complete_values.sort(key=lambda x:(x['candidate_id'],x['reference_id']))
                if score_proof.get('profile_values_binding_sha256')!=digest(complete_values):issues.append('complete_profile_values_disagree_with_candidate_fidelity')
            except (KeyError,TypeError,ValueError,OverflowError):issues.append('complete_profile_value_binding_unverifiable')
        for role in ('candidate_denominator','constraint_results'):
            if role=='constraint_results' and r['method']!='shepherd2_generate':continue
            full=proofs.get((v,role),{});counts=full.get('candidate_row_counts',{});actual_states=full.get('candidate_states')
            if (not isinstance(actual_states,dict) or any(not isinstance(k,str) or not isinstance(state,str) or not state for k,state in actual_states.items()) or actual_states!=states or counts!={name:1 for name in states}):issues.append('complete_candidate_state_binding_changed:'+role)
            status_counts={}
            for state in states.values():status_counts[state]=status_counts.get(state,0)+1
            if full.get('status_counts')!=status_counts:issues.append('complete_candidate_status_counts_changed:'+role)
        for role in ('profile_scores','candidate_denominator','constraint_results'):
            if role=='constraint_results' and r['method']!='shepherd2_generate':continue
            for values in content[v+'/'+role+'.preview.private.json']['preview_rows']:
                name=values.get('candidate_id')
                if role=='profile_scores':
                    ref=values.get('reference_id');identity=score_candidates.get(name)
                    if identity is None or ref not in refs:issues.append('profile_score_candidate_or_reference_changed');continue
                    if any(values.get(k)!=identity.get(k) for k in ('parent_id','microstate_id')):issues.append('profile_score_chemical_identity_changed')
                    coordinate='generated_source_frame_reference_'+ref if r['method']=='shepherd2_generate' else r['method']
                    if values.get('coordinate_mode')!=coordinate:issues.append('profile_score_coordinate_reference_changed')
                    if values.get('role') is not None and values['role']!=('generated' if r['method']=='shepherd2_generate' else identity.get('role')):issues.append('profile_score_source_role_changed')
                    if r['method']=='shepherd2_generate':
                        fidelity={x.get('reference_id'):x for x in reports[name].get('profile_fidelity_scores',[])}.get(ref)
                        if not isinstance(fidelity,dict) or fidelity.get('scoring_state')!='SCORED':issues.append('profile_score_has_no_complete_candidate_fidelity_record')
                        else:
                            for field in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity'):
                                value=fidelity.get(field);preview=values.get(field)
                                if field=='pharmacophore_similarity' and value is None:
                                    if preview not in ('',None) or _reported_bool(values.get('pharmacophore_assessed')) is not False:issues.append('profile_preview_fidelity_value_changed')
                                    continue
                                try:
                                    if type(value) not in (int,float) or type(preview) is bool or not math.isclose(float(preview),value,rel_tol=1e-12,abs_tol=1e-12):issues.append('profile_preview_fidelity_value_changed')
                                except (TypeError,ValueError,OverflowError):issues.append('profile_preview_fidelity_value_changed')
                else:
                    if name not in states or values.get('state')!=states.get(name):issues.append('preview_candidate_state_disagrees_with_complete_report:'+role)
                    if role=='constraint_results' and name in reports:
                        report=reports[name];report_path=v+'/'+name+'.constraints.private.json'
                        if (_reported_bool(values.get('actual_structure_QC')) is not report.get('actual_structure_QC') or _reported_bool(values.get('constraints_passed')) is not report.get('constraints_passed') or values.get('report_path')!=name+'.constraints.private.json' or values.get('report_sha256')!=bound.get(report_path,{}).get('sha256') or values.get('generation_contract_sha256')!=report.get('generation_contract_sha256') or values.get('generation_options_sha256')!=report.get('generation_options_sha256')):issues.append('constraint_preview_disagrees_with_complete_candidate_report')
    return issues
def inspect(request_path,root,names):
    r=small(request_path)
    if r['method'] in ('paper_native_evaluation','prepare_generated_identities'):
        from postanalysis_acceptance import inspect_postanalysis
        return inspect_postanalysis(request_path,root,names)
    validate({**r,'server_execution_authorized':False});rules=dict(RULES)
    if r['method']=='shepherd2_generate':rules['constraint_results']={'required':['candidate_id','state','actual_structure_QC','constraints_passed','report_path','report_sha256','generation_contract_sha256','generation_options_sha256'],'empty_valid':False}
    receipt=small(selected(root,'receipt.private.json'));issues=[];body={k:v for k,v in r.items() if k!='plan_sha256'};body['server_execution_authorized']=False
    if digest(body)!=r['plan_sha256'] or receipt.get('request_sha256')!=sha(request_path) or receipt.get('plan_sha256')!=r['plan_sha256']:issues.append('request_or_plan_changed')
    if receipt.get('source_sha256')!=r.get('source_sha256') or r.get('source_sha256')!=sources():issues.append('reviewed_source_expired')
    if receipt.get('state')!='COMPLETED' or type(receipt.get('exit_code')) is not int or receipt['exit_code']!=0:issues.append('scientific_run_not_completed')
    if receipt.get('method')!=r['method'] or receipt.get('run_id')!=r['run_id'] or receipt.get('host')!=r['expected_host'] or receipt.get('public_upload') is not False:issues.append('source_identity_or_privacy_changed')
    expected={x['id']:x['sha256'] for x in r['inputs']};actual={x['id']:x['sha256'] for x in receipt.get('inputs',[])}
    if expected!=actual or len(actual)!=len(receipt.get('inputs',[])):issues.append('actual_input_denominator_changed')
    bound,invalid=receipt_index(receipt.get('outputs',[]));issues.extend(invalid);variants={'primary'}|{v['label'] for v in r['sensitivity_variants']}
    required={'variant_diagnostics.private.json','full_result_audit.private.json','boundaries.private.json','source_context.private.json','source_structures.private.json','eligible_candidate_outputs.private.json'}|{v+'/'+t+'.preview.private.json' for v in variants for t in rules}|{v+'/software_identity.private.json' for v in variants}
    from generation_reports import generation_names,inspect_generation
    required|=generation_names(r,variants)
    if r['method']=='prepare_reference_profiles':
        # The exact reference identities are read from the source-bound copied manifest below.
        for v in variants:
            required.add(v+'/reference_axis_index.private.json')
    if len(names)!=len(set(names)) or not required<=set(names):raise ValueError('Return every bounded proof, variant preview and actual software identity; do not return whole molecular matrices')
    content={};total=0
    for name in names:
        f=selected(root,name);total+=f.stat().st_size
        if name not in bound or sha(f)!=bound[name]['sha256'] or f.stat().st_size!=bound[name]['bytes'] or total>32_000_000:raise ValueError('Unbound/changed/unbounded selected return')
        content[name]=small(f)
    if sha(selected(root,'source_context.private.json'))!=expected['context'] or sha(selected(root,'source_structures.private.json'))!=expected['structure_manifest']:issues.append('copied_source_context_or_manifest_changed')
    proof=content['full_result_audit.private.json'];issues.extend(proof_issues(proof,bound,variants,list(rules),'full_server_stream_scan_not_independent_scientific_validation',rules))
    for row in proof:
        canonical=row['variant']+'/'+row['role']+'.preview.private.json';preview=content[canonical];issues.extend(preview_issues(preview,row))
        counts=row.get('candidate_row_counts',{})
        if not isinstance(counts,dict) or any(not k or type(v) is not int or v<1 for k,v in counts.items()) or sum(counts.values())!=row['rows']:issues.append('candidate_denominator_inconsistent')
        elif r['method']!='shepherd2_generate':
            expected_candidates={x['id'] for x in content['source_structures.private.json']['molecules'] if (x['role']=='reference')==(r['method']=='prepare_reference_profiles')}
            if r['method']=='prepare_reference_profiles' and row['role']=='profile_scores':expected_candidates=set()
            if set(counts)!=expected_candidates or any(v!=1 for v in counts.values()):issues.append('selected_candidate_identity_coverage_changed')
        identities=set()
        for values in preview['preview_rows']:
            if not set(rules[row['role']]['required'])<=set(values):issues.append('preview_schema_incomplete');continue
            identity=(values['candidate_id'],values.get('coordinate_mode',''))
            if identity in identities:issues.append('duplicate_result_identity')
            identities.add(identity)
            if row['role']=='profile_scores':
                for field in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity'):
                    value=values[field]
                    if field=='pharmacophore_similarity' and value=='':
                        if str(values['pharmacophore_assessed']).lower()!='false':issues.append('unassessed_pharmacophore_was_claimed_assessed')
                        continue
                    try:
                        n=float(value)
                        if not math.isfinite(n) or not -1e-6<=n<=1.000001:raise ValueError()
                    except (ValueError,TypeError):issues.append('invalid_dimensionless_similarity')
                    if field=='pharmacophore_similarity' and str(values['pharmacophore_assessed']).lower()!='true':issues.append('pharmacophore_value_and_assessment_disagree')
                if str(values['protein_ligand_energy_estimated']).lower()!='false':issues.append('ligand_similarity_misrepresented_as_binding_energy')
                if r['method']!='shepherd2_generate' and values['coordinate_mode']!=r['method']:issues.append('fixed_pose_and_free_alignment_were_mixed')
        if row['role'] in ('candidate_denominator','constraint_results'):
            wanted=r['parameters']['n_samples'] if r['method']=='shepherd2_generate' else len([x for x in content['source_structures.private.json']['molecules'] if (x['role']=='reference')==(r['method']=='prepare_reference_profiles')])
            if row['rows']!=wanted or len(row['candidate_row_counts'])!=wanted:issues.append('requested_candidate_denominator_incomplete')
            if r['method']=='shepherd2_generate' and set(counts)!={'generated_'+str(i) for i in range(wanted)}:issues.append('requested_generation_identity_incomplete')
    eligibility=content['eligible_candidate_outputs.private.json'];eligible_paths=[x.get('path') for x in eligibility]
    if len(eligible_paths)!=len(set(eligible_paths)):issues.append('duplicate_candidate_eligibility_record')
    for x in eligibility:
        record=bound.get(x.get('path',''),{})
        if x.get('variant') not in variants or not x.get('path','').startswith(x.get('variant','')+'/') or x.get('eligibility')!='REQUIRES_NEW_DOWNSTREAM_QC' or any(x.get(k)!=record.get(k) for k in ('sha256','bytes')) or not record:issues.append('candidate_eligibility_not_bound_to_actual_SDF')
    if r['method']!='shepherd2_generate':
        expected_candidates={x['id'] for x in content['source_structures.private.json']['molecules'] if x['role']!='reference'}
        for v in variants:
            seen=[x.get('candidate_id') for x in eligibility if x.get('variant')==v]
            if set(seen)!=expected_candidates or len(seen)!=len(expected_candidates):issues.append('scored_candidate_eligibility_incomplete')
    source_pins=read(Path(__file__).parent/'upstream_code.json')
    for label in variants:
        identity=content[label+'/software_identity.private.json'];expected_packages={'shepherd-score'}|({'shepherd2'} if r['method']=='shepherd2_generate' else set());seen={x.get('package') for x in identity.get('python_sources',[])}
        if identity.get('versions')!=r['parameters']['expected_versions'] or identity.get('xtb_sha256')!=r['parameters']['expected_xtb_sha256'] or seen!=expected_packages:issues.append('actual_software_identity_changed')
        for item in identity.get('python_sources',[]):
            pin=source_pins.get(item.get('package'),{})
            if item.get('upstream_commit')!=pin.get('commit') or item.get('fingerprint')!=digest(pin.get('python_blobs',{})):issues.append('upstream_source_pin_changed')
    diagnostics=content['variant_diagnostics.private.json'];labels=[x.get('variant') for x in diagnostics]
    if len(labels)!=len(variants) or set(labels)!=variants:issues.append('actual_variant_diagnostics_incomplete')
    for variant in diagnostics:
        metrics=variant.get('metrics',{})
        if not metrics or any(type(v) not in (int,float) or not math.isfinite(v) for v in metrics.values()):issues.append('actual_numerical_diagnostics_missing')
        if variant.get('biological_replication_established') is not False or variant.get('native_fallback_to_MMFF_allowed') is not False:issues.append('scope_or_charge_model_changed')
        if r['method']=='shepherd2_generate':
            denominator=next((x for x in proof if x['variant']==variant['variant'] and x['role']=='candidate_denominator'),{});success=denominator.get('status_counts',{}).get('CHEMICAL_QC_PASSED_REQUIRES_DOCKING',0);eligible_count=len([x for x in eligibility if x.get('variant')==variant['variant']]);requested=r['parameters']['n_samples']
            if metrics.get('requested_samples')!=requested or metrics.get('eligible_count')!=success or eligible_count!=success or not math.isclose(metrics.get('valid_fraction',-1),success/requested,abs_tol=1e-12):issues.append('generation_validity_denominator_disagrees')
        for gate in r['acceptance_rules']:
            value=metrics.get(gate['metric']);b=gate['bound'];op=gate['operator']
            if type(value) not in (int,float) or op not in ('ge','le','eq') or not {'ge':value>=b,'le':value<=b,'eq':value==b}[op]:issues.append('prespecified_actual_QC_gate_failed:'+gate['metric'])
    issues.extend(_identity_links(r,content,proof,bound,variants))
    if r['method']=='shepherd2_generate':
        if sha(selected(root,'source_checkpoint_manifest.private.json'))!=expected['checkpoint_manifest']:issues.append('copied_checkpoint_manifest_changed')
        issues.extend(inspect_generation(r,content,proof,bound,eligibility,variants,diagnostics))
    if r['method']=='prepare_reference_profiles':
        expected_refs={x['id']:x for x in content['source_structures.private.json']['molecules'] if x['role']=='reference'}
        for v in variants:
            axes=content[v+'/reference_axis_index.private.json']
            if len(axes)!=len(expected_refs) or {x.get('reference_id') for x in axes}!=set(expected_refs):issues.append('prepared_reference_axis_coverage_changed');continue
            for x in axes:
                if x.get('source_sdf_sha256')!=expected_refs[x['reference_id']]['sdf']['sha256'] or x.get('atom_axis_sha256')!=digest(x.get('atom_axis')) or x.get('pharmacophore_axis_sha256')!=digest(x.get('pharmacophore_axis')) or not x.get('atom_axis') or x.get('frame_id')!=content['source_context.private.json']['frame_id']:issues.append('prepared_reference_axis_source_changed')
                if x.get('coordinates_unit')!='angstrom' or x.get('preparation_domain_sha256')!=content['source_context.private.json'].get('preparation_domain_sha256') or x.get('scientific_acceptance')!='NOT_ESTABLISHED':issues.append('prepared_reference_profile_domain_or_scope_changed')
    boundary=content['boundaries.private.json']
    if boundary.get('experimental_binding_or_selectivity_established') is not False or boundary.get('generation_samples_are_biological_replicates') is not False or boundary.get('score_semantics')!='ligand_shape_ESP_pharmacophore_similarity_not_protein_ligand_binding_energy':issues.append('scientific_boundary_overclaimed')
    if boundary.get('potential_model')!='GFN2_xTB_atomic_partial_charge_Coulomb_surface' or boundary.get('not_DFT_density_ESP') is not True or boundary.get('not_APBS_PB_energy') is not True or boundary.get('moved_or_generated_pose_requires_new_docking_and_pose_QC') is not (r['method'] in ('align_profiles','shepherd2_generate')):issues.append('potential_model_or_pose_scope_misrepresented')
    return {'state':'HOLD' if issues else 'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW','issues':sorted(set(issues)),'scientific_acceptance':'NOT_ESTABLISHED','current_server_environment_verified':False,'public_upload':False}
