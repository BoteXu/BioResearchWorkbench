"""Synthetic metadata integrity fixtures only; no molecular/scientific execution.

The lower-level fixtures deliberately isolate return consistency from request
authorization, which existing contract tests cover. They assert no scientific
validity and contain no real molecule, executable, user identity or server path.
"""
from pathlib import Path
from collections import Counter
import copy,csv,hashlib,json,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import digest,read,sha,write
from native_evaluation_reports import inspect_native_variant,TIMEOUT,SUCCESS,SCORE_FIELDS
from postanalysis_acceptance import inspect_postanalysis

def h(value):return hashlib.sha256(value.encode()).hexdigest()

def fixture(n=42,priority=False):
    """Match native runtime field names, including 41+ missing origin attempts."""
    v='primary';prefix=v+'/';cid='generated_0';ids=['generated_'+str(i) for i in range(n)]
    p={'seed':10,'device':'cpu','solvent':'water','xtb_timeout_seconds':10,'expected_xtb_sha256':h('FAKE_NONEXECUTABLE'),'expected_xtb_version':'METADATA_FIXTURE_ONLY','charge_sum_tolerance':.001,'condition':'all','priority_policy':'origin_full_profile_mask' if priority else 'none','minimum_evaluable_fraction':0,'workers':1,'xtb_cores':1,'max_native_npz_bytes':100000,'max_atoms':20,'expected_versions':{x:'METADATA_FIXTURE_ONLY' for x in ('numpy','pandas','scipy','torch','rdkit','open3d','shepherd-score')}}
    spec={'schema':'private-generation-lineage-job/1','origin_request':'inputs/source_request.private.json','origin_request_sha256':h('source_request'),'origin_return_root':'origin_return','origin_receipt_sha256':h('source_receipt'),'selected_return_files':['variant_diagnostics.private.json'],'origin_variant':'primary','reference_id':'REFERENCE','candidate_ids':[]}
    axis=[{'type':1,'position_angstrom':[0,0,0],'direction':[1,0,0]},{'type':2,'position_angstrom':[1,0,0],'direction':[0,1,0]}]
    snap={'reference_id':'REFERENCE','source_sdf_sha256':h('source_sdf'),'atom_axis_sha256':h('atom_axis'),'pharmacophore_axis_sha256':digest(axis),'pharmacophore_axis':axis,'resolved_priority_mask_on_full_reference_axis':[1,0],'conditioning_ESP_neutralized':False}
    contract={'reference_snapshots':[snap],'resolved_sample_counts':[{'candidate_id':x,'N_x1':1,'N_x4':2} for x in ids],'generation_options_sha256':h('generation_options')}
    outputs=[{'path':'primary/'+x+'.constraints.private.json','sha256':h('report_'+x),'bytes':20} for x in ids]
    outputs.extend({'path':path,'sha256':h(path),'bytes':20} for path in ('primary/generated_0.raw.npz','primary/profile_REFERENCE.npz','primary/REFERENCE.axes.private.json','primary/generation_contract.private.json'))
    index={x['path']:x for x in outputs};bound={}
    priority_indices=[0] if priority else None;scope='FULL_PHARM_ALIGNMENT_THEN_REFERENCE_TVERSKY_FOR_BOTH_SUBSETS' if priority else 'NOT_REQUESTED'
    scores=list(SCORE_FIELDS['all'])+(['sims_pharm_priority_target_relax_optimal','sims_pharm_nonpriority_target_relax_optimal'] if priority else [])
    records=[];callbacks=[]
    for number,name in enumerate(ids):
        active=number==0;state=SUCCESS if active else 'INPUT_UNAVAILABLE'
        row={'candidate_id':name,'state':state,'native_i':0 if active else None,'error':None if active else 'ORIGIN_ATTEMPT_HAS_NO_REGISTERED_RAW_NPZ','input_error':None if active else 'ORIGIN_ATTEMPT_HAS_NO_REGISTERED_RAW_NPZ','raw_path':'primary/'+name+'.raw.npz' if active else None,'raw_sha256':index['primary/generated_0.raw.npz']['sha256'] if active else None,'source_report_sha256':index['primary/'+name+'.constraints.private.json']['sha256'],'origin_generation_state':'SOURCE_FIXTURE','origin_reconstruction_formal_charge':0,'expected_raw_atom_slots':1,'native_is_valid':True if active else None,'native_is_valid_post_opt':True if active else None,'native_is_graph_consistent':True if active else None,'engine_calls':2 if active else 0,'engine_failures':0,'engine_evidence_complete':active,'native_reconstruction_charge_matches_origin_declared':True if active else None,'native_scoring_complete':active,'strain_energy':.1 if active else None,'rmsd':.2 if active else None,'smiles':'METADATA_ONLY' if active else None,'smiles_post_opt':'METADATA_ONLY' if active else None,'strain_energy_unit':'hartree','rmsd_unit':'angstrom','eligible_for_docking':False,'pipeline_failure':None}
        for field in scores:row[field]=.8 if active else None
        if active:row.update(raw_slots=1,dummy_atoms_removed=0,evaluated_atoms=1,coordinates_unit='angstrom',source_coordinate_state='generation_raw_source_frame')
        result={'i':0,'error':None,'is_valid':True,'is_valid_post_opt':True,'is_graph_consistent':True,'strain_energy':.1,'rmsd':.2,'smiles':'METADATA_ONLY','smiles_post_opt':'METADATA_ONLY'} if active else None
        if active:
            for field in scores:result['sim'+field[4:]]=.8
        artifacts={}
        if active:
            for field in ('molblock','molblock_post_opt'):
                path='native_molecules/'+name+'.'+field+'.mol';artifacts[field]={'path':path,'sha256':h(path),'bytes':20};bound[prefix+path]=artifacts[field]
        cb={k:row[k] for k in ('candidate_id','state','native_i','error','raw_sha256','source_report_sha256','origin_generation_state')}
        cb.update(native_result=result,native_artifacts=artifacts,native_large_fields_externalized=['molblock','molblock_post_opt'] if active else [],engine_call_indices=[0,1] if active else [],missing_scopes=[] if active else ['RAW_INPUT_UNAVAILABLE_OR_INVALID','ENGINE_EVIDENCE_INCOMPLETE','REQUESTED_NATIVE_SCORES_INCOMPLETE'])
        records.append(row);callbacks.append(cb)
    xtb={'executable':'/SYNTHETIC_OWNED_TOOL/xtb','sha256':p['expected_xtb_sha256'],'version_stdout':p['expected_xtb_version'],'version_stderr':'','version_exit_code':0,'reviewed_version_text':p['expected_xtb_version'],'version_matches':True,'method_cli_explicit':False,'paper_expected_method':'GFN2-xTB','native_method_selection':'installed_xtb_default_no_explicit_gfn_argument','default_method_independently_verified':False,'scientific_acceptance':'NOT_ESTABLISHED'}
    calls=[]
    for number,stage in enumerate(('single_point','relaxation')):
        files={}
        for filename in ('input_mol.xyz','charges','engine.log')+(('xtbopt.xyz',) if stage=='relaxation' else ()):
            path='call_'+format(number,'06d')+'/'+filename;files[filename]={'path':path,'sha256':h(path),'bytes':20};bound[prefix+'xtb_audit/'+path]=files[filename]
        argv=['xtb','input_mol.xyz','--scc' if stage=='single_point' else '--opt','--alpb','water','--parallel','1','--chrg','0']
        calls.append({'candidate_id':cid,'native_i':0,'call_index':number,'stage':stage,'operation':'check_output' if number==0 else 'check_call','native_argv':argv,'executed_argv':[xtb['executable']]+argv[1:],'cwd':'/SYNTHETIC_OWNED_RETURN/native_work/temp_'+str(number),'timeout_seconds':10,'timeout_scope':TIMEOUT,'energy_unit':'hartree','energy_scope':'isolated_conformer_not_binding_energy','xtb_sha256':p['expected_xtb_sha256'],'method_cli_explicit':False,'requested_formal_charge':0,'returncode':0,'exception_type':None,'timed_out':False,'binary_unchanged_after_call':True,'normal_termination_observed':True,'energy_hartree':-1.0,'partial_charge_sum':0.0,'partial_charge_count':1,'partial_charge_unit':'elementary_charge','atoms':1,'optimized_coordinate_axis_valid':True if number else None,'evidence_issues':[],'evidence_complete':True,'artifacts':files,'scientific_acceptance':'NOT_ESTABLISHED'})
    reference={'reference_id':'REFERENCE','source_sdf_sha256':snap['source_sdf_sha256'],'atom_axis_sha256':snap['atom_axis_sha256'],'pharmacophore_axis_sha256':snap['pharmacophore_axis_sha256'],'source_axes_sha256':index['primary/REFERENCE.axes.private.json']['sha256'],'source_profile_sha256':index['primary/profile_REFERENCE.npz']['sha256'],'full_pharmacophore_count':2,'partial_charges_from_exact_origin_profile':True,'coordinates_unit':'angstrom','surface_points':400,'probe_radius_angstrom':1.2,'evaluation_ESP':'raw_GFN2_xTB_atomic_charge_Coulomb_surface','scientific_acceptance':'NOT_ESTABLISHED'}
    bound[prefix+'reference_binding.private.json']={'sha256':digest(reference),'bytes':20}
    meta={'required_score_fields':scores,'condition':'all','priority_scope':scope,'expected_attempts':n,'reference_binding_sha256':digest(reference),'energy_unit':'hartree','timeout_scope':TIMEOUT,'scientific_acceptance':'NOT_ESTABLISHED','method_cli_explicit':False,'docking_eligibility_established':False,'fixed_pose_constraints_reassessed':False,'independently_aligned_modalities':True,'timeout_seconds':10,'surface_points':400,'probe_radius_angstrom':1.2,'pharm_multi_vector':False,'native_input_count':1,'native_callback_count':1,'pipeline_invoked':True,'pipeline_completed':True,'pipeline_failure':None,'native_dataframe_is_full_export':True,'seed':10,'origin_generation_contract_sha256':index['primary/generation_contract.private.json']['sha256']}
    pin=read(ROOT/'upstream_code.json')['shepherd-score']
    content={prefix+'native_records.private.json':records,prefix+'callback_results.private.json':callbacks,prefix+'engine_audit.private.json':{'calls':calls,'capture_errors':[],'xtb_identity':xtb,'single_worker':True,'energy_unit':'hartree','timeout_scope':TIMEOUT,'scientific_acceptance':'NOT_ESTABLISHED','method_cli_explicit':False},prefix+'evaluation_metadata.private.json':meta,prefix+'native_global_metrics.private.json':{'native_metrics':{},'native_denominator':1,'all_requested_denominator':n,'energy_unit':'hartree','timeout_scope':TIMEOUT,'scientific_acceptance':'NOT_ESTABLISHED','one_joint_docking_pose_established':False,'native_dataframe_complete':True},prefix+'origin_lineage.private.json':{'lineage_spec':spec,'source_review':{'state':'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW','issues':[]},'frame_id':'SYNTHETIC_FRAME','candidate_ids':ids,'expected_attempts':n,'reference_id':'REFERENCE','eligible_only_filter_used':False,'priority_indices_full_reference_axis':priority_indices,'priority_scope':scope,'native_i_to_candidate_id':{'0':cid}},prefix+'reference_binding.private.json':reference,prefix+'origin_generation_contract_snapshot.private.json':contract,prefix+'origin_receipt_snapshot.private.json':{'outputs':outputs},prefix+'origin_request_snapshot.private.json':{'parameters':{'n_samples':n,'generated_formal_charge':0,'solvent':'water'}},prefix+'software_identity.private.json':{'versions':p['expected_versions'],'xtb_identity':xtb,'generation_weights_loaded':False,'python_sources':[{'package':'shepherd-score','upstream_commit':pin['commit'],'fingerprint':digest(pin['python_blobs'])}]}}
    frame=[{field:records[0][field] for field in scores}]
    content[prefix+'native_dataframe.private.json']=frame
    bound[prefix+'native_dataframe.private.json']={'sha256':digest(frame),'bytes':20}
    meta.update(native_dataframe_artifact={'path':'native_dataframe.private.json','sha256':digest(frame)},native_pandas_rows=1)
    return content,bound,p,spec,n

class NativeReturnIntegrity(unittest.TestCase):
    def review(self,data):return inspect_native_variant('primary',*data)
    def test_actual_runtime_field_pattern_keeps_all_42_attempts(self):
        content,bound,p,spec,n=fixture();issues,records,metrics=self.review((content,bound,p,spec,n));self.assertEqual(issues,[]);self.assertEqual(len(records),42);self.assertEqual(metrics['native_valid_fraction_all_requested'],1/42)
    def test_runtime_input_invalid_is_a_retained_failure_not_schema_failure(self):
        content,bound,p,spec,n=fixture();content['primary/native_records.private.json'][41]['state']='INPUT_INVALID';content['primary/callback_results.private.json'][41]['state']='INPUT_INVALID'
        issues,_,_=self.review((content,bound,p,spec,n));self.assertNotIn('missing_native_input_not_explicitly_unavailable',issues)
    def test_engine_success_requires_all_actual_artifact_bindings(self):
        data=fixture();data[0]['primary/engine_audit.private.json']['calls'][0]['artifacts']={}
        issues,_,_=self.review(data);self.assertTrue(issues,'Missing input/charges/log must not pass native engine evidence')
    def test_optimized_coordinate_audit_cannot_be_false_when_success_is_true(self):
        data=fixture();data[0]['primary/engine_audit.private.json']['calls'][1]['optimized_coordinate_axis_valid']=False
        issues,_,_=self.review(data);self.assertTrue(issues,'Relaxation requires its actual optimized atom/coordinate axis')
    def test_exact_reference_charge_profile_hash_is_not_self_declared(self):
        content,bound,p,spec,n=fixture();ref=content['primary/reference_binding.private.json'];ref['source_profile_sha256']=h('WRONG_PROFILE');bound['primary/reference_binding.private.json']['sha256']=digest(ref);content['primary/evaluation_metadata.private.json']['reference_binding_sha256']=digest(ref)
        issues,_,_=self.review((content,bound,p,spec,n));self.assertTrue(issues,'Reference charges must bind the exact origin profile NPZ')
    def test_native_pipeline_failure_cannot_be_silently_accepted(self):
        data=fixture();meta=data[0]['primary/evaluation_metadata.private.json'];meta['pipeline_failure']='SYNTHETIC_EXPORT_FAILURE';meta['pipeline_completed']=False;meta['native_dataframe_is_full_export']=False;data[0]['primary/native_global_metrics.private.json']['native_dataframe_complete']=False
        issues,_,_=self.review(data);self.assertTrue(issues,'Failed native execution/export must remain explicit HOLD')
    def test_native_error_cannot_disappear_from_callback_ledger(self):
        data=fixture();data[0]['primary/callback_results.private.json'][0]['native_result']['error']='SYNTHETIC_NATIVE_ERROR'
        issues,_,_=self.review(data);self.assertTrue(issues,'Original native error must agree with the persisted ledger')
    def test_boolean_priority_mask_is_not_exact_integer_full_axis_mask(self):
        data=fixture(priority=True);data[0]['primary/origin_generation_contract_snapshot.private.json']['reference_snapshots'][0]['resolved_priority_mask_on_full_reference_axis'][0]=True
        with self.assertRaises(ValueError):self.review(data)
    def test_per_candidate_units_cannot_override_global_hartree_scope(self):
        for field,value in (('strain_energy_unit','kcal/mol'),('rmsd_unit','nm'),('eligible_for_docking',True)):
            with self.subTest(field=field):
                data=fixture();data[0]['primary/native_records.private.json'][0][field]=value
                issues,_,_=self.review(data);self.assertIn('native_candidate_units_or_docking_scope_changed',issues)
    def test_native_validity_requires_its_actual_molblock_artifacts(self):
        data=fixture();data[0]['primary/callback_results.private.json'][0]['native_artifacts']={}
        issues,_,_=self.review(data);self.assertIn('native_valid_structure_missing_bound_molblock',issues)
    def test_native_engine_cannot_be_replaced_by_another_program(self):
        for field in ('program','operation','solvent','executed_program'):
            with self.subTest(field=field):
                data=fixture();call=data[0]['primary/engine_audit.private.json']['calls'][0]
                if field=='program':call['native_argv'][0]='OTHER_PROGRAM'
                elif field=='operation':call['operation']='check_call'
                elif field=='solvent':call['native_argv'][4]='dmso'
                else:call['executed_argv'][0]='/OTHER/EXECUTABLE'
                issues,_,_=self.review(data);self.assertIn('native_engine_program_operation_or_solvent_changed',issues)

    def bundle_review(self,tamper_row_42=False,tamper_scope=False):
        """Real file/hash return checks; isolate request authorization with stubs."""
        content,bound,p,spec,n=fixture();prefix='primary/';records=content[prefix+'native_records.private.json']
        _,_,metrics=self.review((content,bound,p,spec,n));constant_sources={'SYNTHETIC_METADATA_ONLY':h('source')}
        metrics['pipeline_completed']=True
        content.update({'source_context.private.json':{'frame_id':'SYNTHETIC_FRAME'},'source_structures.private.json':spec,'eligible_candidate_outputs.private.json':[],'boundaries.private.json':{'scientific_acceptance':'NOT_ESTABLISHED'},'variant_diagnostics.private.json':[{'variant':'primary','seed':10,'metrics':metrics,'expected_attempts':n,'pipeline_failure':None}]})
        content['boundaries.private.json'].update(method='paper_native_evaluation',postanalysis_of_exact_generation_origin=True,paper_evaluation_scores_do_not_grant_docking_eligibility=True,computed_parent_is_not_physiological_state_prediction=True,technical_rechecks_are_not_independent_molecules=True,identity_grouping_preserves_original_chemical_state_and_pose=False,public_upload=False)
        content['variant_diagnostics.private.json'][0].update(scientific_acceptance='NOT_ESTABLISHED',biological_replication_established=False)
        if tamper_scope:content['boundaries.private.json']['technical_rechecks_are_not_independent_molecules']=False
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'primary').mkdir()
            def save(name,obj):
                f=root/name;f.parent.mkdir(parents=True,exist_ok=True);write(f,obj)
                return {'path':name,'sha256':sha(f),'bytes':f.stat().st_size}
            prewritten={}
            for short in ('reference_binding.private.json','native_dataframe.private.json'):
                name=prefix+short;prewritten[name]=save(name,content[name])
            meta=content[prefix+'evaluation_metadata.private.json'];meta['reference_binding_sha256']=prewritten[prefix+'reference_binding.private.json']['sha256'];meta['native_dataframe_artifact']['sha256']=prewritten[prefix+'native_dataframe.private.json']['sha256']
            columns=['candidate_id','state','strain_energy','sims_surf_target_relax_optimal'];full_rows=[{k:str(x.get(k) if x.get(k) is not None else '') for k in columns} for x in records]
            table=root/'primary/native_evaluation.tsv'
            with table.open('x',encoding='utf8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=columns,delimiter='\t');writer.writeheader();writer.writerows(full_rows)
            preview={'full_result_sha256':sha(table),'full_rows':n,'preview_rows':full_rows[:40],'is_full_result':False};preview_rec=save(prefix+'native_evaluation.preview.private.json',preview)
            proof_rows=copy.deepcopy(full_rows)
            if tamper_row_42:proof_rows[41]['strain_energy']='999.0'
            states={x['candidate_id']:x['state'] for x in records}
            proof={'variant':'primary','role':'native_evaluation','path':prefix+'native_evaluation.tsv','sha256':sha(table),'bytes':table.stat().st_size,'rows':n,'columns':columns,'preview_path':preview_rec['path'],'preview_sha256':preview_rec['sha256'],'candidate_row_counts':{x:1 for x in states},'candidate_states':states,'status_counts':dict(Counter(states.values())),'row_values_binding_sha256':digest(proof_rows),'scope':'full_server_stream_scan_not_independent_scientific_validation'}
            content['full_result_audit.private.json']=[proof];outputs=[]
            for name,obj in content.items():outputs.append(prewritten[name] if name in prewritten else save(name,obj))
            outputs.extend([preview_rec,{'path':proof['path'],'sha256':proof['sha256'],'bytes':proof['bytes']}])
            outputs.extend({'path':name,'sha256':x['sha256'],'bytes':x['bytes']} for name,x in bound.items() if name not in content)
            inputs=[{'id':'context','path':'inputs/context.private.json','sha256':sha(root/'source_context.private.json')},{'id':'structure_manifest','path':'inputs/lineage.private.json','sha256':sha(root/'source_structures.private.json')},{'id':'software','path':'inputs/software.private.json','sha256':h('software_input')}]
            req={'method':'paper_native_evaluation','run_id':'SYNTHETIC_METADATA_ONLY','expected_host':'SYNTHETIC_HOST','parameters':p,'sensitivity_variants':[],'source_sha256':constant_sources,'inputs':inputs,'acceptance_rules':[{'metric':'requested_attempts','operator':'eq','bound':n}],'server_execution_authorized':False};req['plan_sha256']=digest(req)
            path=root/'request.private.json';write(path,req)
            write(root/'receipt.private.json',{'request_sha256':sha(path),'plan_sha256':req['plan_sha256'],'source_sha256':constant_sources,'state':'COMPLETED','exit_code':0,'method':req['method'],'run_id':req['run_id'],'host':req['expected_host'],'public_upload':False,'inputs':inputs,'outputs':outputs})
            # Existing tests cover authorization/source signatures separately.
            # Here all selected return files, proof and complete rows are real.
            with patch('postanalysis_acceptance.validate',return_value=req),patch('postanalysis_acceptance.sources',return_value=constant_sources),patch('postanalysis_acceptance._origin',return_value=([],n)):
                return inspect_postanalysis(path,root,list(content)+[preview_rec['path']])
    def test_full_return_fixture_is_consistent_but_not_scientifically_accepted(self):
        result=self.bundle_review();self.assertEqual(result['issues'],[]);self.assertEqual(result['scientific_acceptance'],'NOT_ESTABLISHED');self.assertFalse(result['current_server_environment_verified'])
    def test_row_42_value_binding_cannot_hide_behind_first_40_preview(self):
        result=self.bundle_review(True);self.assertEqual(result['state'],'HOLD');self.assertIn('complete_postanalysis_table_values_disagree_with_full_records',result['issues'])
    def test_technical_seed_rechecks_cannot_be_promoted_to_independent_entities(self):
        result=self.bundle_review(tamper_scope=True);self.assertEqual(result['state'],'HOLD');self.assertIn('postanalysis_scope_or_replication_boundary_changed',result['issues'])

if __name__=='__main__':unittest.main()
