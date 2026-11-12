"""Invented JSON/TSV receipt examples. No molecule parsing, generation or scientific calculation."""
from pathlib import Path
import copy,csv,json,sys,tempfile,unittest,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import read,write,sha,digest,prepare
from generation_contracts import branch_ids
from acceptance import inspect
from handoff import prepare_link
SUCCESS='CHEMICAL_QC_PASSED_REQUIRES_DOCKING'


class GenerationReturns(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.root=self.base/'returned';self.root.mkdir();self.selected=[]
        project=read(ROOT/'examples/branches/pharm_full.disabled.json');project['example_only']=False;p=project['parameters'];p['n_samples']=2;p['batch_size']=2
        g=p['generation_options'];s=g['reference_conditions'][0]
        atoms=[{'atomic_number':6,'formal_charge':0,'isotope':0}]*24
        points=[{'type':i,'position_angstrom':[float(i),0.,0.],'direction':[1.,0.,0.]} for i in range(4)]
        s.update(atom_axis_sha256=digest(atoms),pharmacophore_axis_sha256=digest(points))
        ctx={'frame_id':'FICTIONAL_FORMAT_FRAME','public_upload':False}
        manifest={'molecules':[{'id':'REFERENCE','role':'reference','sdf':{'sha256':'0'*64}}]}
        assets={'sha256':'f'*64,'scope':'FICTIONAL_ASSET_METADATA_NOT_A_CHECKPOINT'}
        inputs=self.base/'inputs';inputs.mkdir()
        for row in project['inputs']:
            value={'context':ctx,'structure_manifest':manifest,'software':{'scope':'FICTIONAL_FORMAT_ONLY'},'checkpoint_manifest':assets}[row['id']]
            f=inputs/(row['id']+'.json');write(f,value);row['sha256']=sha(f)
        self.prepared=self.base/'prepared';prepare(project,self.prepared);self.path=self.prepared/'request.private.json';self.request=read(self.path)
        for filename,value in [('source_context.private.json',ctx),('source_structures.private.json',manifest),('source_checkpoint_manifest.private.json',assets)]:write(self.root/filename,value);self.selected.append(filename)
        self.labels=['primary']+[x['label'] for x in project['sensitivity_variants']];proof=[];eligible=[];diagnostics=[];pins=read(ROOT/'upstream_code.json')
        seeds={'primary':p['seed'],**{x['label']:x['seed'] for x in project['sensitivity_variants']}}
        for label in self.labels:
            folder=self.root/label;folder.mkdir()
            identity={'versions':p['expected_versions'],'xtb_sha256':p['expected_xtb_sha256'],'python_sources':[{'package':k,'upstream_commit':v['commit'],'fingerprint':digest(v['python_blobs'])} for k,v in pins.items()],'test_fixture_not_scientific_execution':True}
            write(folder/'software_identity.private.json',identity);self.selected.append(label+'/software_identity.private.json')
            snapshot={'reference_id':'REFERENCE','source_sdf_sha256':'0'*64,'atom_axis':atoms,'atom_axis_sha256':digest(atoms),'pharmacophore_axis':points,'pharmacophore_axis_sha256':digest(points),'scaffold_mode':'none','pharm_mode':'pharm-full','resolved_priority_mask_on_full_reference_axis':[1,1,1,1]}
            contract={'plan_sha256':self.request['plan_sha256'],'generation_options_sha256':digest(g),'branch_ids':branch_ids(p),'seed':seeds[label],'reference_snapshots':[snapshot],'resolved_sample_counts':[{'candidate_id':'generated_'+str(i),'N_x1':24,'N_x4':4} for i in range(2)],'composition_mode':'single','profile_weights':[1.0],'checkpoint_sha256':'f'*64,'condition_frame':'origin','native_surface_points':75,'native_probe_radius_angstrom':.6,'threshold_basis':g['constraint_qc']['threshold_basis'],'scientific_acceptance':'NOT_ESTABLISHED','public_upload':False,'test_fixture_not_scientific_execution':True}
            contract_path=folder/'generation_contract.private.json';write(contract_path,contract);self.selected.append(label+'/generation_contract.private.json');ch=sha(contract_path)
            data={'profile_scores':[],'candidate_denominator':[],'constraint_results':[]}
            for i in range(2):
                name='generated_'+str(i);sdf=folder/(name+'.sdf');sdf.write_text('FICTIONAL_FORMAT_ONLY_NOT_A_REAL_MOLECULE_'+str(i),encoding='utf8')
                point_report={'required':4,'matched':4,'passed':True,'points':[{'source_point_index':j,'source_type':j,'matched_actual_point_index':j,'distance_angstrom':.01,'direction_cosine':1.0 if j!=3 else None,'passed':True} for j in range(4)]}
                state_id=project['run_id']+'__'+label+'__'+name
                report={'candidate_id':name,'generation_contract_sha256':ch,'generation_options_sha256':digest(g),'actual_structure_QC':True,'saved_SDF_readback_verified':True,'constraints_passed':True,'experimental_binding_established':False,'state':SUCCESS,'failure_reason':'','actual_sdf':{'path':sdf.name,'sha256':sha(sdf),'bytes':sdf.stat().st_size,'state_id':state_id,'parent_id':'UNASSESSED_GENERATED_PARENT','microstate_id':'FICTIONAL_STATE_'+str(i)},'reference_results':[{'reference_id':'REFERENCE','scaffold':{'required':0,'passed':True},'raw_generated_pharmacophore_head':copy.deepcopy(point_report),'reextracted_actual_molecular_pharmacophores':copy.deepcopy(point_report),'passed':True}],'test_fixture_not_scientific_execution':True}
                report_path=folder/(name+'.constraints.private.json');write(report_path,report);self.selected.append(report_path.relative_to(self.root).as_posix())
                data['profile_scores'].append({'candidate_id':name,'parent_id':'UNASSESSED_GENERATED_PARENT','microstate_id':'FICTIONAL_STATE_'+str(i),'role':'generated','shape_similarity':'.8','esp_surface_similarity':'.7','pharmacophore_similarity':'.9','pharmacophore_assessed':'True','coordinate_mode':'generated_source_frame_reference_REFERENCE','protein_ligand_energy_estimated':'False'})
                data['candidate_denominator'].append({'candidate_id':name,'state':SUCCESS})
                data['constraint_results'].append({'candidate_id':name,'state':SUCCESS,'actual_structure_QC':'True','constraints_passed':'True','report_path':report_path.name,'report_sha256':sha(report_path),'generation_contract_sha256':ch,'generation_options_sha256':digest(g)})
                eligible.append({'variant':label,'candidate_id':name,'state_id':state_id,'parent_id':'UNASSESSED_GENERATED_PARENT','microstate_id':'FICTIONAL_STATE_'+str(i),'path':sdf.relative_to(self.root).as_posix(),'sha256':sha(sdf),'bytes':sdf.stat().st_size,'eligibility':'REQUIRES_NEW_DOWNSTREAM_QC','constraints_passed':True,'constraint_report_path':report_path.relative_to(self.root).as_posix(),'constraint_report_sha256':sha(report_path),'generation_contract_sha256':ch,'generation_options_sha256':digest(g)})
            for role,rows in data.items():
                f=folder/(role+'.tsv');columns=list(rows[0])
                with f.open('w',encoding='utf8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=columns,delimiter='\t');w.writeheader();w.writerows(rows)
                preview=folder/(role+'.preview.private.json');write(preview,{'full_result_sha256':sha(f),'full_rows':2,'preview_rows':rows,'is_full_result':True});self.selected.append(preview.relative_to(self.root).as_posix())
                proof.append({'variant':label,'role':role,'path':f.relative_to(self.root).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size,'rows':2,'columns':columns,'preview_path':preview.relative_to(self.root).as_posix(),'preview_sha256':sha(preview),'candidate_row_counts':{'generated_0':1,'generated_1':1},'status_counts':{SUCCESS:2} if role!='profile_scores' else {},'scope':'full_server_stream_scan_not_independent_scientific_validation'})
            diagnostics.append({'variant':label,'seed':seeds[label],'metrics':{'self_shape_similarity':1.,'self_esp_similarity':1.,'requested_samples':2,'chemical_qc_passed':2,'valid_fraction':1.,'constraint_pass_fraction':1.},'native_fallback_to_MMFF_allowed':False,'biological_replication_established':False,'minimum_valid_fraction_met':True,'minimum_constraint_fraction_met':True,'generation_contract_sha256':ch,'generation_options_sha256':digest(g),'branch_ids':branch_ids(p),'test_fixture_not_scientific_execution':True})
        for filename,value in [('full_result_audit.private.json',proof),('variant_diagnostics.private.json',diagnostics),('eligible_candidate_outputs.private.json',eligible),('boundaries.private.json',{'score_semantics':'ligand_shape_ESP_pharmacophore_similarity_not_protein_ligand_binding_energy','potential_model':'GFN2_xTB_atomic_partial_charge_Coulomb_surface','not_DFT_density_ESP':True,'not_APBS_PB_energy':True,'generation_samples_are_biological_replicates':False,'experimental_binding_or_selectivity_established':False,'moved_or_generated_pose_requires_new_docking_and_pose_QC':True,'public_upload':False})]:write(self.root/filename,value);self.selected.append(filename)
        self.receipt={'state':'COMPLETED','exit_code':0,'method':'shepherd2_generate','run_id':project['run_id'],'host':project['expected_host'],'request_sha256':sha(self.path),'plan_sha256':self.request['plan_sha256'],'source_sha256':self.request['source_sha256'],'inputs':project['inputs'],'outputs':[],'public_upload':False,'test_fixture_not_scientific_execution':True};self.rebind()
        from test_return_integrity_v12 import upgrade_fixture_v12
        upgrade_fixture_v12(self)
    def tearDown(self):self.temp.cleanup()
    def rebind(self):
        self.receipt['outputs']=[{'path':f.relative_to(self.root).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in self.root.rglob('*') if f.is_file() and f.name!='receipt.private.json'];(self.root/'receipt.private.json').write_text(json.dumps(self.receipt),encoding='utf8')
    def mutate(self,name,fn):
        f=self.root/name;value=read(f);fn(value);f.write_text(json.dumps(value,allow_nan=False),encoding='utf8');self.rebind()
    def result(self):return inspect(self.path,self.root,self.selected)
    def test_complete_constraint_format_never_establishes_science(self):
        r=self.result();self.assertEqual(r['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW',r);self.assertEqual(r['scientific_acceptance'],'NOT_ESTABLISHED');self.assertFalse(r['current_server_environment_verified'])
    def test_every_requested_sample_needs_constraint_report(self):
        self.selected.remove('primary/generated_1.constraints.private.json')
        with self.assertRaises(ValueError):self.result()
    def test_raw_head_pass_does_not_replace_actual_molecular_recovery(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x['reference_results'][0]['reextracted_actual_molecular_pharmacophores'].update(passed=False,matched=3));self.assertEqual(self.result()['state'],'HOLD')
    def test_reextracted_distance_is_checked_even_if_pass_is_true(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x['reference_results'][0]['reextracted_actual_molecular_pharmacophores']['points'][0].update(distance_angstrom=3));self.assertEqual(self.result()['state'],'HOLD')
    def test_reextracted_direction_is_checked(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x['reference_results'][0]['reextracted_actual_molecular_pharmacophores']['points'][1].update(direction_cosine=-1));self.assertEqual(self.result()['state'],'HOLD')
    def test_actual_point_mapping_must_be_one_to_one(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x['reference_results'][0]['reextracted_actual_molecular_pharmacophores']['points'][1].update(matched_actual_point_index=0));self.assertEqual(self.result()['state'],'HOLD')
    def test_reference_point_axis_change_is_HOLD(self):
        self.mutate('primary/generation_contract.private.json',lambda x:x['reference_snapshots'][0]['pharmacophore_axis'][0].update(type=8));self.assertIn('actual_reference_atom_or_pharmacophore_axis_changed',self.result()['issues'])
    def test_native_generation_scale_change_is_HOLD(self):
        self.mutate('primary/generation_contract.private.json',lambda x:x.update(native_surface_points=400));self.assertIn('native_generation_scale_or_acceptance_scope_changed',self.result()['issues'])
    def test_invented_branch_claim_is_HOLD(self):
        self.mutate('primary/generation_contract.private.json',lambda x:x['branch_ids'].append('UNIMPLEMENTED'));self.assertIn('actual_generation_contract_changed',self.result()['issues'])
    def test_count_schedule_must_cover_all_samples(self):
        self.mutate('primary/generation_contract.private.json',lambda x:x['resolved_sample_counts'].pop());self.assertIn('resolved_generation_count_denominator_changed',self.result()['issues'])
    def test_priority_mask_must_match_approved_selection(self):
        self.mutate('primary/generation_contract.private.json',lambda x:x['reference_snapshots'][0].update(resolved_priority_mask_on_full_reference_axis=[0,0,0,0]));self.assertIn('actual_priority_mask_changed',self.result()['issues'])
    def test_accepted_SDF_cannot_be_swapped_to_another_sample(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x['actual_sdf'].update(path='generated_1.sdf'));self.assertIn('accepted_generation_SDF_path_not_canonical',self.result()['issues'])
    def test_all_reference_constraints_must_be_reported(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x.update(reference_results=[]));self.assertIn('candidate_reference_constraint_coverage_changed',self.result()['issues'])
    def test_constraint_report_requires_actual_structure_QC(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x.update(actual_structure_QC=False));self.assertIn('candidate_chemical_QC_alias_disagrees',self.result()['issues'])
    def test_in_memory_QC_does_not_replace_saved_SDF_readback(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x.update(saved_SDF_readback_verified=False));self.assertIn('accepted_generation_lacks_actual_structure_QC',self.result()['issues'])
    def test_saved_SDF_state_identity_cannot_be_reassigned(self):
        self.mutate('primary/generated_0.constraints.private.json',lambda x:x['actual_sdf'].update(state_id='OTHER_STATE'));self.assertIn('saved_SDF_state_or_parent_identity_changed',self.result()['issues'])
    def test_eligibility_does_not_override_constraint_failure(self):
        self.mutate('eligible_candidate_outputs.private.json',lambda x:x[0].update(constraints_passed=False));self.assertIn('eligible_candidate_constraint_receipt_binding_changed',self.result()['issues'])
    def test_eligible_SDF_cannot_be_relabelled_as_another_candidate(self):
        def swap(rows):
            rows[0].update(path=rows[1]['path'],sha256=rows[1]['sha256'],bytes=rows[1]['bytes'])
        self.mutate('eligible_candidate_outputs.private.json',swap);self.assertIn('eligible_candidate_constraint_receipt_binding_changed',self.result()['issues'])
    def test_false_constraint_fraction_is_not_accepted(self):
        self.mutate('variant_diagnostics.private.json',lambda x:x[0].update(minimum_constraint_fraction_met=False));self.assertIn('generation_constraint_gate_summary_disagrees',self.result()['issues'])
    def test_generation_handoff_requires_fresh_return_review(self):
        row={k:v for k,v in read(self.root/'eligible_candidate_outputs.private.json')[0].items() if k in ('candidate_id','parent_id','microstate_id','path','sha256','bytes')}
        selection={'candidates':[row],'target_workflow':'molecular_qc','experimental_validation':False,'public_upload':False,'scientific_context':{'receptor_sha256':'a'*64,'site_sha256':'b'*64,'protonation_basis':'FICTIONAL','chemical_state_review':'FICTIONAL','source_frame_id':'FICTIONAL_FORMAT_FRAME','limitations':['FORMAT_ONLY']}};selection['review_sha256']=digest(selection)
        args=[self.request,self.receipt,selection,self.root/'source_context.private.json',self.root/'eligible_candidate_outputs.private.json']
        with self.assertRaises(ValueError):prepare_link(*args)
        result=prepare_link(*args,generation_review={'request_path':self.path,'returned_root':self.root,'selected_return_files':self.selected})
        self.assertEqual(result['state'],'PREPARED_NOT_DISPATCHED');self.assertTrue(result['generation_constraint_return_reviewed']);self.assertFalse(result['automatic_submission'])
        self.assertEqual(result['existing_core_input_bindings'][0]['id_property'],'BRW_STATE_ID');self.assertEqual(result['existing_core_input_bindings'][0]['parent_property'],'BRW_PARENT_ID')
