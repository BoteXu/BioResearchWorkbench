"""Fictional standard-library return contracts. No SDF chemistry or scientific engines run."""
from pathlib import Path
import copy,csv,json,math,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from contracts import read,sha,digest,sources
from generation_contracts import effective_conditioning,expected_alignment_steps,completed_steps,branch_ids
from handoff import prepare_link
from server.generation import summarize_profile_fidelity

SUCCESS='CHEMICAL_QC_PASSED_REQUIRES_DOCKING'


def _save(path,value):path.write_text(json.dumps(value,allow_nan=False),encoding='utf8')


def _fixture_profile_values(rows):
    return sorted([{'candidate_id':str(row['candidate_id']),'reference_id':str(row['reference_id']),'shape_similarity':float(row['shape_similarity']),'esp_surface_similarity':float(row['esp_surface_similarity']),'pharmacophore_similarity':None if row.get('pharmacophore_similarity') in ('',None) else float(row['pharmacophore_similarity']),'pharmacophore_assessed':str(row['pharmacophore_assessed']).lower()=='true','protein_ligand_energy_estimated':str(row['protein_ligand_energy_estimated']).lower()=='true'} for row in rows],key=lambda x:(x['candidate_id'],x['reference_id']))


def upgrade_fixture_v12(f):
    """Migrate only fictional test artifacts; never call this helper on research results.

    This intentionally constructs the new positive fixture fields so older regression
    modules can keep testing their original failure trigger after the schema upgrade.
    Apply once at the end of an old setUp, before the tested mutation, never afterwards.
    """
    root=f.root;request_path=getattr(f,'request_path',getattr(f,'path',None));r=f.request
    manifest=read(root/'source_structures.private.json');eligibility=read(root/'eligible_candidate_outputs.private.json')
    for row in manifest['molecules']:
        if row['role']!='reference':
            actual=next((x for x in eligibility if x['candidate_id']==row['id']),None)
            if actual:
                for key in ('parent_id','microstate_id'):row.setdefault(key,actual[key])
    _save(root/'source_structures.private.json',manifest)
    for row in r['inputs']:
        if row['id']=='structure_manifest':row['sha256']=sha(root/'source_structures.private.json')
        if row['id']=='context':row['sha256']=sha(root/'source_context.private.json')
    r['source_sha256']=sources();r.pop('plan_sha256',None);body={**r,'server_execution_authorized':False};r['plan_sha256']=digest(body);_save(request_path,r)
    f.request_path=request_path
    refs=[x['id'] for x in manifest['molecules'] if x['role']=='reference']
    proofs=read(root/'full_result_audit.private.json');diagnostics=read(root/'variant_diagnostics.private.json')
    labels={x['variant'] for x in diagnostics}
    for label in labels:
        folder=root/label;tables={};columns={}
        if r['method']=='prepare_reference_profiles':
            axes_path=folder/'reference_axis_index.private.json';axes=read(axes_path);context=read(root/'source_context.private.json')
            for axis in axes:axis.setdefault('coordinates_unit','angstrom');axis.setdefault('scientific_acceptance','NOT_ESTABLISHED');axis.setdefault('preparation_domain_sha256',context['preparation_domain_sha256'])
            _save(axes_path,axes)
        for proof in [x for x in proofs if x['variant']==label]:
            role=proof['role']
            with (folder/(role+'.tsv')).open(encoding='utf8',newline='') as stream:
                reader=csv.DictReader(stream,delimiter='\t');columns[role]=list(reader.fieldnames);tables[role]=list(reader)
        for row in tables['profile_scores']:
            if 'reference_id' not in row:
                row['reference_id']=row.get('coordinate_mode','').removeprefix('generated_source_frame_reference_') if r['method']=='shepherd2_generate' else refs[0]
        if 'reference_id' not in columns['profile_scores']:columns['profile_scores'].insert(1,'reference_id')
        if r['method']=='shepherd2_generate':
            p=r['parameters'];g=p['generation_options'];contract_path=folder/'generation_contract.private.json';contract=read(contract_path)
            masks=[x['resolved_priority_mask_on_full_reference_axis'] for x in contract['reference_snapshots']]
            effective=effective_conditioning(p,masks);align=expected_alignment_steps(p,effective)
            contract.update(plan_sha256=r['plan_sha256'],generation_options_sha256=digest(g),branch_ids=branch_ids(p),effective_conditioning=effective,expected_alignment_steps=align,native_early_stop_steps=completed_steps(g['sampler']['early_stop_edm'],p['denoise_steps']))
            _save(contract_path,contract);contract_sha=sha(contract_path);reports={}
            for i in range(p['n_samples']):
                name='generated_'+str(i);path=folder/(name+'.constraints.private.json');report=read(path)
                report.setdefault('chemical_valid',report['actual_structure_QC']);report.setdefault('eligible',report['state']==SUCCESS);report.setdefault('hard_constraints_assessed',report['chemical_valid'])
                restore=g['condition_frame'] if isinstance(g['condition_frame'],list) else [0.,0.,0.]
                report.setdefault('native_output_to_source_translation_angstrom',restore)
                for result in report.get('reference_results',[]):
                    result.setdefault('assessment_complete',True);result.get('scaffold',{}).setdefault('assessment_complete',True)
                report.update(generation_contract_sha256=contract_sha,generation_options_sha256=digest(g))
                score_rows=[x for x in tables['profile_scores'] if x['candidate_id']==name]
                if 'profile_fidelity_scores' not in report:
                    report['profile_fidelity_scores']=[]
                    for row in score_rows:
                        ref=row['reference_id'];weight=p['profile_weights'][refs.index(ref)]
                        scored={'reference_id':ref,'guidance_weight':weight,'guidance_direction':'positive' if weight>0 else 'negative' if weight<0 else 'zero','scoring_state':'SCORED','scope':'raw_GFN2_xTB_ligand_profile_similarity_not_binding_energy_or_selectivity'}
                        for field in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity'):scored[field]=None if row.get(field) in ('',None) else float(row[field])
                        report['profile_fidelity_scores'].append(scored)
                _save(path,report);reports[name]=report
                for row in eligibility:
                    if row['variant']==label and row['candidate_id']==name:
                        row.update(constraint_report_sha256=sha(path),generation_contract_sha256=contract_sha,generation_options_sha256=digest(g))
            for row in tables['constraint_results']:
                report=reports[row['candidate_id']];row.update(report_sha256=sha(folder/(row['candidate_id']+'.constraints.private.json')),generation_contract_sha256=contract_sha,generation_options_sha256=digest(g))
            summary=next(x for x in diagnostics if x['variant']==label);n=p['n_samples'];chemical=sum(x['chemical_valid'] is True for x in reports.values());constrained=sum(x['chemical_valid'] is True and x['constraints_passed'] is True for x in reports.values());eligible_count=sum(x['eligible'] is True for x in reports.values())
            summary['metrics'].update(chemical_valid_count=chemical,chemical_valid_fraction=chemical/n,constraint_pass_count=constrained,constraint_pass_fraction=constrained/n,eligible_count=eligible_count,eligible_fraction=eligible_count/n,chemical_qc_passed=chemical,valid_fraction=eligible_count/n)
            summary.update(generation_contract_sha256=contract_sha,generation_options_sha256=digest(g),branch_ids=branch_ids(p),effective_conditioning=effective,expected_alignment_steps=align,minimum_valid_fraction_met=chemical/n>=p['min_valid_fraction'],minimum_constraint_fraction_met=constrained/n>=g['constraint_qc']['min_constraint_pass_fraction'])
            summary['profile_fidelity_summary']=summarize_profile_fidelity([x for x in manifest['molecules'] if x['role']=='reference'],p['profile_weights'],list(reports.values()),n)
        for proof in [x for x in proofs if x['variant']==label]:
            role=proof['role'];data=tables[role];path=folder/(role+'.tsv')
            with path.open('w',encoding='utf8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=columns[role],delimiter='\t');writer.writeheader();writer.writerows(data)
            preview=folder/(role+'.preview.private.json');_save(preview,{'full_result_sha256':sha(path),'full_rows':len(data),'preview_rows':data[:40],'is_full_result':len(data)<=40})
            counts={};states={};state_counts={};pairs={}
            for row in data:
                name=row['candidate_id'];counts[name]=counts.get(name,0)+1
                if 'state' in row:states[name]=row['state'];state_counts[row['state']]=state_counts.get(row['state'],0)+1
                if role=='profile_scores':pairs.setdefault(name,{})[row['reference_id']]=pairs.setdefault(name,{}).get(row['reference_id'],0)+1
            proof.update(sha256=sha(path),bytes=path.stat().st_size,rows=len(data),columns=columns[role],preview_sha256=sha(preview),candidate_row_counts=counts,status_counts=state_counts)
            if role=='profile_scores':
                proof['candidate_reference_row_counts']=pairs
                proof['identity_binding_sha256']=digest(sorted([{k:str(row.get(k,'')) for k in ('candidate_id','reference_id','parent_id','microstate_id','coordinate_mode')} for row in data],key=lambda x:(x['candidate_id'],x['reference_id'])))
                proof['profile_values_binding_sha256']=digest(_fixture_profile_values(data))
                proof['full_value_audit_issues']=[]
            if role in ('candidate_denominator','constraint_results'):proof['candidate_states']=states
    _save(root/'full_result_audit.private.json',proofs);_save(root/'eligible_candidate_outputs.private.json',eligibility);_save(root/'variant_diagnostics.private.json',diagnostics)
    f.receipt.update(method=r['method'],run_id=r['run_id'],host=r['expected_host'],request_sha256=sha(request_path),plan_sha256=r['plan_sha256'],source_sha256=r['source_sha256'],inputs=r['inputs']);f.rebind()
    return f


def fresh_review(f):return {'request_path':getattr(f,'request_path',getattr(f,'path',None)),'returned_root':f.root,'selected_return_files':f.selected}


def _fixture_table(f,label,role,rows):
    """Change an invented full table and update all its format-only receipt bindings."""
    path=f.root/label/(role+'.tsv')
    with path.open(encoding='utf8',newline='') as stream:columns=list(csv.DictReader(stream,delimiter='\t').fieldnames)
    with path.open('w',encoding='utf8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,delimiter='\t');writer.writeheader();writer.writerows(rows)
    preview=f.root/label/(role+'.preview.private.json');_save(preview,{'full_result_sha256':sha(path),'full_rows':len(rows),'preview_rows':rows[:40],'is_full_result':len(rows)<=40})
    proof=read(f.root/'full_result_audit.private.json');entry=next(x for x in proof if x['variant']==label and x['role']==role)
    counts={};states={};statuses={};pairs={}
    for row in rows:
        name=row['candidate_id'];counts[name]=counts.get(name,0)+1
        if 'state' in row:states[name]=row['state'];statuses[row['state']]=statuses.get(row['state'],0)+1
        if role=='profile_scores':pairs.setdefault(name,{})[row['reference_id']]=pairs.setdefault(name,{}).get(row['reference_id'],0)+1
    entry.update(sha256=sha(path),bytes=path.stat().st_size,rows=len(rows),columns=columns,preview_sha256=sha(preview),candidate_row_counts=counts,status_counts=statuses)
    if role=='profile_scores':
        entry['candidate_reference_row_counts']=pairs
        entry['identity_binding_sha256']=digest(sorted([{k:str(row.get(k,'')) for k in ('candidate_id','reference_id','parent_id','microstate_id','coordinate_mode')} for row in rows],key=lambda x:(x['candidate_id'],x['reference_id'])))
        entry['profile_values_binding_sha256']=digest(_fixture_profile_values(rows))
        entry['full_value_audit_issues']=[]
    else:entry['candidate_states']=states
    _save(f.root/'full_result_audit.private.json',proof);f.rebind()


def _fixture_rows(f,label,role):
    with (f.root/label/(role+'.tsv')).open(encoding='utf8',newline='') as stream:return list(csv.DictReader(stream,delimiter='\t'))


def _fixture_report_binding(f,label,name):
    path=f.root/label/(name+'.constraints.private.json');checksum=sha(path)
    eligibility=read(f.root/'eligible_candidate_outputs.private.json')
    for row in eligibility:
        if row['variant']==label and row['candidate_id']==name:row['constraint_report_sha256']=checksum
    _save(f.root/'eligible_candidate_outputs.private.json',eligibility)
    rows=_fixture_rows(f,label,'constraint_results')
    for row in rows:
        if row['candidate_id']==name:row['report_sha256']=checksum
    _fixture_table(f,label,'constraint_results',rows)


class ReturnIntegrityV12(unittest.TestCase):
    def setUp(self):self.fixtures=[]
    def tearDown(self):
        for f in self.fixtures:f.tearDown()
    def scoring(self):
        import test_returns
        f=test_returns.Returns(methodName='test_consistent_format_never_establishes_scientific_acceptance');f.setUp();self.fixtures.append(f);return f
    def generation(self):
        import test_generation_returns
        f=test_generation_returns.GenerationReturns(methodName='test_complete_constraint_format_never_establishes_science');f.setUp();self.fixtures.append(f);return f
    def reference_pair(self):
        import test_reference_preparation
        fixture=test_reference_preparation.ReferencePreparation(methodName='test_reference_axis_return_is_bounded_consistency_only');fixture.setUp();self.fixtures.append(fixture);f=fixture.f
        manifest=read(f.root/'source_structures.private.json');manifest['molecules'].append({'id':'REF2','role':'reference','sdf':{'sha256':'1'*64}});_save(f.root/'source_structures.private.json',manifest)
        for label in f.labels:
            axes=read(f.root/label/'reference_axis_index.private.json');second=copy.deepcopy(axes[0]);second.update(reference_id='REF2',source_sdf_sha256='1'*64);axes.append(second);_save(f.root/label/'reference_axis_index.private.json',axes)
            _fixture_table(f,label,'candidate_denominator',[{'candidate_id':name,'state':'REFERENCE_PROFILE_PREPARED'} for name in ('REF','REF2')])
        upgrade_fixture_v12(f)
        project=fixture.draft();p=project['parameters'];p['composition_mode']='default';p['profile_weights']=[1.,1.];second=copy.deepcopy(p['generation_options']['reference_conditions'][0]);second['reference_id']='REF2';p['generation_options']['reference_conditions'].append(second)
        return fixture,project
    def failed_generation(self,chemical,constrained):
        f=self.generation();name='generated_0';label='primary';path=f.root/label/(name+'.constraints.private.json');report=read(path)
        report.update(chemical_valid=chemical,actual_structure_QC=chemical,hard_constraints_assessed=chemical,constraints_passed=constrained,eligible=False,state='FAILED_CHEMISTRY_OR_CONSTRAINT_QC',failure_reason='FICTIONAL_PRESPECIFIED_FAILURE')
        if not chemical:
            report.pop('actual_sdf',None);report['saved_SDF_readback_verified']=False
            report['reference_results']=[]
            for row in report['profile_fidelity_scores']:row.update(scoring_state='NOT_ASSESSED',shape_similarity=None,esp_surface_similarity=None,pharmacophore_similarity=None)
        elif constrained:
            report['profile_fidelity_scores'][0].update(scoring_state='FAILED',error='FICTIONAL_SCORE_FAILURE',shape_similarity=None,esp_surface_similarity=None,pharmacophore_similarity=None)
        else:
            result=report['reference_results'][0];result['passed']=False;points=result['reextracted_actual_molecular_pharmacophores'];points.update(matched=3,passed=False);points['points'][-1].update(passed=False,matched_actual_point_index=None,distance_angstrom=3.)
        _save(path,report)
        eligibility=read(f.root/'eligible_candidate_outputs.private.json');_save(f.root/'eligible_candidate_outputs.private.json',[x for x in eligibility if not(x['variant']==label and x['candidate_id']==name)])
        for role in ('profile_scores','candidate_denominator','constraint_results'):
            rows=_fixture_rows(f,label,role)
            if role=='profile_scores':rows=[x for x in rows if x['candidate_id']!=name]
            else:
                for row in rows:
                    if row['candidate_id']==name:
                        row['state']=report['state']
                        if role=='constraint_results':row.update(actual_structure_QC=str(chemical),constraints_passed=str(constrained),report_sha256=sha(path))
            _fixture_table(f,label,role,rows)
        # Build a new complete fictional campaign, before the test's corruption.
        upgrade_fixture_v12(f)
        return f
    def scoring_beyond_preview(self):
        f=self.scoring();manifest=read(f.root/'source_structures.private.json');references=[x for x in manifest['molecules'] if x['role']=='reference'];manifest['molecules']=references+[{'id':'C'+str(i).zfill(3),'role':'candidate','parent_id':'P'+str(i),'microstate_id':'M'+str(i)} for i in range(42)];_save(f.root/'source_structures.private.json',manifest);eligibility=[]
        for label in f.labels:
            prototype=_fixture_rows(f,label,'profile_scores')[0];scores=[];states=[]
            for row in manifest['molecules'][len(references):]:
                score={**prototype,'candidate_id':row['id'],'parent_id':row['parent_id'],'microstate_id':row['microstate_id']};scores.append(score);states.append({'candidate_id':row['id'],'state':'SCORED'})
                path=f.root/label/(row['id']+'.scored.sdf');path.write_text('FICTIONAL_FORMAT_ONLY_'+row['id'],encoding='utf8');eligibility.append({'variant':label,'candidate_id':row['id'],'parent_id':row['parent_id'],'microstate_id':row['microstate_id'],'path':path.relative_to(f.root).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,'eligibility':'REQUIRES_NEW_DOWNSTREAM_QC'})
            _fixture_table(f,label,'profile_scores',scores);_fixture_table(f,label,'candidate_denominator',states)
        _save(f.root/'eligible_candidate_outputs.private.json',eligibility);upgrade_fixture_v12(f);return f
    def assert_hold(self,f):self.assertEqual(f.result()['state'],'HOLD')
    def assert_issue(self,f,issue):
        result=f.result();self.assertEqual(result['state'],'HOLD');self.assertIn(issue,result['issues'],result)
    def test_scoring_positive_fixture_remains_consistency_only(self):
        f=self.scoring();self.assertEqual(f.result()['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW',f.result());self.assertEqual(f.result()['scientific_acceptance'],'NOT_ESTABLISHED')
    def test_generation_positive_fixture_has_distinct_stage_counts(self):
        f=self.generation();self.assertEqual(f.result()['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW',f.result())
    def test_scoring_handoff_requires_complete_fresh_review(self):
        f=self.scoring()
        with self.assertRaises(ValueError):prepare_link(f.request,f.receipt,f.selection(),f.root/'source_context.private.json',f.root/'eligible_candidate_outputs.private.json')
        result=prepare_link(f.request,f.receipt,f.selection(),f.root/'source_context.private.json',f.root/'eligible_candidate_outputs.private.json',return_review=fresh_review(f));self.assertTrue(result['complete_source_return_reviewed'])
    def test_scoring_HOLD_receipt_cannot_prepare_handoff(self):
        f=self.scoring();f.receipt.update(method='UNRELATED',host='WRONG',request_sha256='a'*64,public_upload=True);f.rebind()
        with self.assertRaises(ValueError):prepare_link(f.request,f.receipt,f.selection(),f.root/'source_context.private.json',f.root/'eligible_candidate_outputs.private.json',return_review=fresh_review(f))
    def test_boolean_exit_code_is_not_completed_zero(self):
        f=self.scoring();f.receipt['exit_code']=False;f.rebind()
        with self.assertRaises(ValueError):prepare_link(f.request,f.receipt,f.selection(),f.root/'source_context.private.json',f.root/'eligible_candidate_outputs.private.json',return_review=fresh_review(f))
    def test_scored_SDF_qualification_cannot_relabel_microstate(self):
        f=self.scoring();f.mutate('eligible_candidate_outputs.private.json',lambda x:x[0].update(microstate_id='OTHER'));self.assert_issue(f,'scored_candidate_source_chemical_identity_changed')
    def test_scored_SDF_qualification_cannot_relabel_parent(self):
        f=self.scoring();f.mutate('eligible_candidate_outputs.private.json',lambda x:x[0].update(parent_id='OTHER'));self.assert_issue(f,'scored_candidate_source_chemical_identity_changed')
    def test_score_preview_must_use_actual_microstate(self):
        f=self.generation();f.mutate('primary/profile_scores.preview.private.json',lambda x:x['preview_rows'][0].update(microstate_id='OTHER'));self.assert_issue(f,'profile_score_chemical_identity_changed')
    def test_score_preview_must_use_actual_reference(self):
        f=self.generation();f.mutate('primary/profile_scores.preview.private.json',lambda x:x['preview_rows'][0].update(reference_id='UNKNOWN'));self.assert_issue(f,'profile_score_candidate_or_reference_changed')
    def test_score_preview_coordinate_label_cannot_change_reference(self):
        f=self.generation();f.mutate('primary/profile_scores.preview.private.json',lambda x:x['preview_rows'][0].update(coordinate_mode='generated_source_frame_reference_UNKNOWN'));self.assert_issue(f,'profile_score_coordinate_reference_changed')
    def test_score_preview_value_must_match_complete_candidate_fidelity(self):
        f=self.generation();f.mutate('primary/profile_scores.preview.private.json',lambda x:x['preview_rows'][0].update(shape_similarity='.1'));self.assert_issue(f,'profile_preview_fidelity_value_changed')
    def test_constraint_preview_cannot_disagree_with_complete_candidate(self):
        f=self.generation();f.mutate('primary/constraint_results.preview.private.json',lambda x:x['preview_rows'][0].update(constraints_passed='False',state='FAILED'));self.assert_issue(f,'constraint_preview_disagrees_with_complete_candidate_report')
    def test_candidate_denominator_preview_cannot_disagree_with_complete_candidate(self):
        f=self.generation();f.mutate('primary/candidate_denominator.preview.private.json',lambda x:x['preview_rows'][0].update(state='FAILED'));self.assert_issue(f,'preview_candidate_state_disagrees_with_complete_report:candidate_denominator')
    def test_full_candidate_reference_matrix_is_required(self):
        f=self.generation();f.mutate('full_result_audit.private.json',lambda x:x[0].pop('candidate_reference_row_counts'));self.assert_issue(f,'complete_candidate_reference_coverage_changed')
    def test_full_candidate_status_map_is_required(self):
        f=self.generation();f.mutate('full_result_audit.private.json',lambda x:next(row for row in x if row['role']=='constraint_results' and row['variant']=='primary').pop('candidate_states'));self.assert_issue(f,'complete_candidate_state_binding_changed:constraint_results')
    def test_full_score_identity_digest_is_required_beyond_the_preview(self):
        f=self.scoring();f.mutate('full_result_audit.private.json',lambda x:x[0].update(identity_binding_sha256='0'*64));self.assert_issue(f,'complete_profile_score_chemical_identity_binding_changed')
    def test_full_score_value_scan_is_required_beyond_the_preview(self):
        f=self.scoring();f.mutate('full_result_audit.private.json',lambda x:x[0].update(full_value_audit_issues=['INVALID_ROW_41']));self.assert_issue(f,'complete_profile_score_value_audit_failed_or_missing')
    def test_missing_full_score_value_scan_cannot_pass(self):
        f=self.generation();f.mutate('full_result_audit.private.json',lambda x:x[0].pop('full_value_audit_issues'));self.assert_issue(f,'complete_profile_score_value_audit_failed_or_missing')
    def test_generated_full_score_values_are_bound_to_complete_fidelity(self):
        f=self.generation();f.mutate('full_result_audit.private.json',lambda x:x[0].update(profile_values_binding_sha256='0'*64));self.assert_issue(f,'complete_profile_values_disagree_with_candidate_fidelity')
    def test_complete_42_candidate_scoring_fixture_is_consistent_with_bounded_preview(self):
        f=self.scoring_beyond_preview();self.assertEqual(f.result()['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW',f.result());self.assertEqual(len(read(f.root/'primary/profile_scores.preview.private.json')['preview_rows']),40)
    def test_row_41_chemical_relabel_is_rejected_even_with_unchanged_preview(self):
        f=self.scoring_beyond_preview();preview=read(f.root/'primary/profile_scores.preview.private.json')['preview_rows'];rows=_fixture_rows(f,'primary','profile_scores');rows[40]['microstate_id']='WRONG_ROW_41_STATE';_fixture_table(f,'primary','profile_scores',rows);self.assertEqual(read(f.root/'primary/profile_scores.preview.private.json')['preview_rows'],preview);self.assert_issue(f,'complete_profile_score_chemical_identity_binding_changed')
    def test_frame_restore_must_match_explicit_contract_even_after_hash_rebinding(self):
        f=self.generation();f.mutate('primary/generated_0.constraints.private.json',lambda x:x.update(native_output_to_source_translation_angstrom=[999,0,0]));_fixture_report_binding(f,'primary','generated_0');self.assert_issue(f,'native_output_source_frame_restore_changed')
    def test_effective_conditioning_is_recomputed(self):
        f=self.generation();f.mutate('primary/generation_contract.private.json',lambda x:x['effective_conditioning'].update(effective_modalities=[]));self.assert_issue(f,'actual_native_conditioning_or_alignment_schedule_changed')
    def test_alignment_schedule_is_not_just_a_declared_label(self):
        f=self.generation();f.mutate('primary/generation_contract.private.json',lambda x:x.update(expected_alignment_steps=[1]));self.assert_issue(f,'actual_native_conditioning_or_alignment_schedule_changed')
    def test_stage_counts_cannot_relabel_chemical_validity_as_eligibility(self):
        f=self.generation();f.mutate('variant_diagnostics.private.json',lambda x:x[0]['metrics'].update(chemical_valid_count=1));self.assert_issue(f,'chemical_constraint_eligible_counts_disagree')
    def test_selected_actual_SDF_is_rehashed_before_handoff(self):
        f=self.scoring();(f.root/'primary/CAND.scored.sdf').write_text('CHANGED_AFTER_RETURN',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'Selected source SDF changed'):prepare_link(f.request,f.receipt,f.selection(),f.root/'source_context.private.json',f.root/'eligible_candidate_outputs.private.json',return_review=fresh_review(f))
    def test_reference_pair_exact_axis_can_bind(self):
        fixture,project=self.reference_pair();self.assertEqual(fixture.f.result()['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW',fixture.f.result());self.assertEqual([x['reference_id'] for x in fixture.bind(project)['parameters']['generation_options']['reference_conditions']],['REF','REF2'])
    def test_reference_subset_cannot_bind_full_source_manifest(self):
        fixture,project=self.reference_pair();project['parameters']['generation_options']['reference_conditions'].pop();project['parameters']['profile_weights']=[1.]
        with self.assertRaisesRegex(ValueError,'subset/reordering'):fixture.bind(project)
    def test_reference_reorder_cannot_bind_full_source_manifest(self):
        fixture,project=self.reference_pair();project['parameters']['generation_options']['reference_conditions'].reverse()
        with self.assertRaisesRegex(ValueError,'subset/reordering'):fixture.bind(project)
    def test_reference_preparation_domain_cannot_change_while_axes_stay_the_same(self):
        fixture,project=self.reference_pair();fixture.f.mutate('primary/reference_axis_index.private.json',lambda x:x[0].update(preparation_domain_sha256='b'*64));self.assert_issue(fixture.f,'prepared_reference_profile_domain_or_scope_changed')
    def test_failed_chemistry_retains_complete_unassessed_fidelity_and_numerical_HOLD_only(self):
        f=self.failed_generation(False,False);self.assertEqual(set(f.result()['issues']),{'prespecified_chemical_valid_fraction_failed','prespecified_constraint_pass_fraction_failed'},f.result())
    def test_constraint_rejection_does_not_erase_valid_chemistry_or_early_fidelity(self):
        f=self.failed_generation(True,False);self.assertEqual(f.result()['issues'],['prespecified_constraint_pass_fraction_failed'],f.result());report=read(f.root/'primary/generated_0.constraints.private.json');self.assertTrue(report['chemical_valid']);self.assertEqual(report['profile_fidelity_scores'][0]['scoring_state'],'SCORED')
    def test_score_failure_preserves_chemical_and_hard_constraint_counts(self):
        f=self.failed_generation(True,True);self.assertEqual(f.result()['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW',f.result());m=next(x for x in read(f.root/'variant_diagnostics.private.json') if x['variant']=='primary')['metrics'];self.assertEqual((m['chemical_valid_count'],m['constraint_pass_count'],m['eligible_count']),(2,2,1))
    def test_failed_candidate_still_needs_complete_fidelity_reference_axis(self):
        f=self.failed_generation(False,False);f.mutate('primary/generated_0.constraints.private.json',lambda x:x.update(profile_fidelity_scores=[]));self.assert_issue(f,'candidate_profile_fidelity_reference_changed')
    def test_failed_or_unassessed_fidelity_cannot_carry_accepted_values(self):
        f=self.failed_generation(False,False);f.mutate('primary/generated_0.constraints.private.json',lambda x:x['profile_fidelity_scores'][0].update(shape_similarity=.9));self.assert_issue(f,'unassessed_or_failed_profile_fidelity_contains_accepted_values')
    def test_fidelity_summary_is_recomputed_from_all_requested_candidates(self):
        f=self.generation();f.mutate('variant_diagnostics.private.json',lambda x:x[0]['profile_fidelity_summary'][0].update(requested_count=1));self.assert_issue(f,'profile_fidelity_summary_disagrees_with_complete_reports')
    def test_branch_binding_error_is_separate_from_numerical_QC_HOLD(self):
        f=self.generation();f.mutate('variant_diagnostics.private.json',lambda x:x[0].update(branch_ids=['OTHER']));self.assert_issue(f,'generation_branch_binding_changed');self.assertNotIn('prespecified_constraint_pass_fraction_failed',f.result()['issues'])
    def test_wrong_gate_flag_is_integrity_failure_not_low_numerical_QC(self):
        f=self.generation();f.mutate('variant_diagnostics.private.json',lambda x:x[0].update(minimum_valid_fraction_met=False));self.assert_issue(f,'generation_chemical_gate_summary_disagrees');self.assertNotIn('prespecified_chemical_valid_fraction_failed',f.result()['issues'])
    def test_failed_constraint_flag_must_match_complete_assessment_outcomes(self):
        f=self.failed_generation(True,False)
        def change(report):
            row=report['reference_results'][0];row['passed']=True;points=row['reextracted_actual_molecular_pharmacophores'];points.update(matched=4,passed=True);points['points'][-1].update(passed=True,matched_actual_point_index=3,distance_angstrom=.01)
        f.mutate('primary/generated_0.constraints.private.json',change);_fixture_report_binding(f,'primary','generated_0');self.assert_issue(f,'candidate_constraint_outcome_disagrees')
    def test_no_scientific_dependency_was_imported(self):
        self.assertFalse(any(x in sys.modules for x in ('numpy','rdkit','torch','scipy','open3d')))
