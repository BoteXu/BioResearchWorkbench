"""Fictional result-format cases only. No chemical structures are parsed or computed."""
from pathlib import Path
import json,sys,csv,tempfile,unittest,shutil,copy
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'server')]
from contracts import read,write,sha,digest,prepare,sources
from acceptance import inspect,RULES
from handoff import prepare_link
import test_contracts as fixture_module
class Returns(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);project=fixture_module.fixture();inp=self.base/'inputs';inp.mkdir();ctx={'frame_id':'FIXTURE_FRAME','public_upload':False};manifest={'molecules':[{'id':'REF','role':'reference'},{'id':'CAND','role':'candidate'}]}
        content={'context':ctx,'structure_manifest':manifest,'software':{'scope':'FICTIONAL_FORMAT_ONLY'}}
        for row in project['inputs']:
            f=inp/(row['id']+'.private.json');write(f,content[row['id']]);row['sha256']=sha(f)
        self.prepared=self.base/'prepared';prepare(project,self.prepared);self.request_path=self.prepared/'request.private.json';self.request=read(self.request_path);self.root=self.base/'returned';self.root.mkdir();self.selected=[]
        shutil.copy2(inp/'context.private.json',self.root/'source_context.private.json');shutil.copy2(inp/'structure_manifest.private.json',self.root/'source_structures.private.json')
        pins=read(ROOT/'upstream_code.json');proof=[];diagnostics=[];eligible=[]
        self.labels=['primary']+[x['label'] for x in project['sensitivity_variants']]
        for label in self.labels:
            folder=self.root/label;folder.mkdir();write(folder/'software_identity.private.json',{'versions':project['parameters']['expected_versions'],'xtb_sha256':project['parameters']['expected_xtb_sha256'],'python_sources':[{'package':'shepherd-score','upstream_commit':pins['shepherd-score']['commit'],'fingerprint':digest(pins['shepherd-score']['python_blobs'])}],'test_fixture_not_scientific_execution':True});self.selected.append(label+'/software_identity.private.json')
            data={'profile_scores':[{'candidate_id':'CAND','parent_id':'PARENT','microstate_id':'EXACT_STATE','shape_similarity':'0.8','esp_surface_similarity':'0.7','pharmacophore_similarity':'0.6','pharmacophore_assessed':'True','coordinate_mode':'score_fixed_pose','protein_ligand_energy_estimated':'False'}],'candidate_denominator':[{'candidate_id':'CAND','state':'SCORED'}]}
            for role,rows in data.items():
                f=folder/(role+'.tsv');columns=list(rows[0])
                with f.open('w',encoding='utf8',newline='') as out:w=csv.DictWriter(out,fieldnames=columns,delimiter='\t');w.writeheader();w.writerows(rows)
                preview=folder/(role+'.preview.private.json');write(preview,{'full_result_sha256':sha(f),'full_rows':1,'preview_rows':rows,'is_full_result':True});self.selected.append(preview.relative_to(self.root).as_posix())
                proof.append({'variant':label,'role':role,'path':f.relative_to(self.root).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size,'rows':1,'columns':columns,'preview_path':preview.relative_to(self.root).as_posix(),'preview_sha256':sha(preview),'candidate_row_counts':{'CAND':1},'status_counts':{'SCORED':1} if role=='candidate_denominator' else {},'scope':'full_server_stream_scan_not_independent_scientific_validation'})
            sdf=folder/'CAND.scored.sdf';sdf.write_text('FICTIONAL_EVIDENCE_FORMAT_ONLY_NOT_A_REAL_MOLECULE',encoding='utf8');eligible.append({'variant':label,'candidate_id':'CAND','parent_id':'PARENT','microstate_id':'EXACT_STATE','path':sdf.relative_to(self.root).as_posix(),'sha256':sha(sdf),'bytes':sdf.stat().st_size,'eligibility':'REQUIRES_NEW_DOWNSTREAM_QC'})
            diagnostics.append({'variant':label,'metrics':{'self_shape_similarity':1.,'self_esp_similarity':1.,'selected_input_molecules':2,'scored_profile_pairs':1},'native_fallback_to_MMFF_allowed':False,'biological_replication_established':False,'scientific_acceptance':'NOT_ESTABLISHED','test_fixture_not_scientific_execution':True})
        write(self.root/'full_result_audit.private.json',proof);write(self.root/'variant_diagnostics.private.json',diagnostics);write(self.root/'eligible_candidate_outputs.private.json',eligible)
        write(self.root/'boundaries.private.json',{'score_semantics':'ligand_shape_ESP_pharmacophore_similarity_not_protein_ligand_binding_energy','potential_model':'GFN2_xTB_atomic_partial_charge_Coulomb_surface','not_DFT_density_ESP':True,'not_APBS_PB_energy':True,'generation_samples_are_biological_replicates':False,'experimental_binding_or_selectivity_established':False,'moved_or_generated_pose_requires_new_docking_and_pose_QC':False,'public_upload':False})
        self.selected += ['full_result_audit.private.json','variant_diagnostics.private.json','eligible_candidate_outputs.private.json','boundaries.private.json','source_context.private.json','source_structures.private.json']
        self.receipt={'state':'COMPLETED','exit_code':0,'method':project['method'],'run_id':project['run_id'],'host':project['expected_host'],'request_sha256':sha(self.request_path),'plan_sha256':self.request['plan_sha256'],'source_sha256':self.request['source_sha256'],'inputs':project['inputs'],'public_upload':False,'outputs':[],'test_fixture_not_scientific_execution':True};self.rebind()
        from test_return_integrity_v12 import upgrade_fixture_v12
        upgrade_fixture_v12(self)
    def tearDown(self):self.temp.cleanup()
    def rebind(self):
        self.receipt['outputs']=[{'path':f.relative_to(self.root).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in self.root.rglob('*') if f.is_file() and f.name!='receipt.private.json'];(self.root/'receipt.private.json').write_text(json.dumps(self.receipt),encoding='utf8')
    def mutate(self,name,fn):
        f=self.root/name;x=read(f);fn(x);f.write_text(json.dumps(x,allow_nan=False),encoding='utf8');self.rebind()
    def result(self):return inspect(self.request_path,self.root,self.selected)
    def selection(self):
        row={k:v for k,v in read(self.root/'eligible_candidate_outputs.private.json')[0].items() if k not in ('variant','eligibility')};sel={'candidates':[row],'target_workflow':'molecular_qc','experimental_validation':False,'public_upload':False,'scientific_context':{'receptor_sha256':'a'*64,'site_sha256':'b'*64,'protonation_basis':'FIXTURE_ONLY','chemical_state_review':'FIXTURE_ONLY','source_frame_id':'FIXTURE_FRAME','limitations':['FORMAT_TEST_ONLY']}};sel['review_sha256']=digest(sel);return sel
    def handoff(self,selection):return prepare_link(self.request,self.receipt,selection,self.root/'source_context.private.json',self.root/'eligible_candidate_outputs.private.json',return_review={'request_path':self.request_path,'returned_root':self.root,'selected_return_files':self.selected})
    def test_consistent_format_never_establishes_scientific_acceptance(self):
        r=self.result();self.assertEqual(r['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW');self.assertEqual(r['scientific_acceptance'],'NOT_ESTABLISHED');self.assertFalse(r['current_server_environment_verified'])
    def test_nonempty_result_cannot_have_empty_preview(self):
        self.mutate('primary/profile_scores.preview.private.json',lambda x:x.update(preview_rows=[]));self.assertIn('preview_row_count_mismatch',self.result()['issues'])
    def test_invalid_similarity_is_HOLD(self):
        self.mutate('primary/profile_scores.preview.private.json',lambda x:x['preview_rows'][0].update(esp_surface_similarity='2'));self.assertIn('invalid_dimensionless_similarity',self.result()['issues'])
    def test_similarity_cannot_be_called_binding_energy(self):
        self.mutate('primary/profile_scores.preview.private.json',lambda x:x['preview_rows'][0].update(protein_ligand_energy_estimated='True'));self.assertIn('ligand_similarity_misrepresented_as_binding_energy',self.result()['issues'])
    def test_software_version_drift_is_HOLD(self):
        self.mutate('primary/software_identity.private.json',lambda x:x['versions'].update(torch='WRONG'));self.assertIn('actual_software_identity_changed',self.result()['issues'])
    def test_primary_result_cannot_point_to_alternate(self):
        self.mutate('full_result_audit.private.json',lambda x:x[0].update(path='seed_check_1/profile_scores.tsv'));self.assertIn('full_result_path_not_canonical_or_registered',self.result()['issues'])
    def test_every_seed_preview_is_required(self):
        self.selected.remove('seed_check_1/profile_scores.preview.private.json')
        with self.assertRaises(ValueError):self.result()
    def test_missing_eligible_scored_candidate_is_not_complete(self):
        self.mutate('eligible_candidate_outputs.private.json',lambda x:x.pop());self.assertIn('scored_candidate_eligibility_incomplete',self.result()['issues'])
    def test_QC_eligible_handoff_only_prepares_new_QC(self):
        r=self.handoff(self.selection());self.assertEqual(r['state'],'PREPARED_NOT_DISPATCHED');self.assertTrue(r['new_input_QC_required']);self.assertFalse(r['experimental_validation'])
    def test_handoff_cannot_change_source_frame(self):
        x=self.selection();x['scientific_context']['source_frame_id']='WRONG';x['review_sha256']=digest({k:v for k,v in x.items() if k!='review_sha256'})
        with self.assertRaises(ValueError):self.handoff(x)
    def test_handoff_cannot_change_chemical_state(self):
        x=self.selection();x['candidates'][0]['microstate_id']='OTHER_STATE';x['review_sha256']=digest({k:v for k,v in x.items() if k!='review_sha256'})
        with self.assertRaises(ValueError):self.handoff(x)
    def test_duplicate_source_eligibility_is_refused(self):
        self.mutate('eligible_candidate_outputs.private.json',lambda x:x.append(dict(x[0])))
        with self.assertRaises(ValueError):self.handoff(self.selection())
    def test_unknown_run_is_not_a_handoff_source(self):
        self.receipt['state']='UNKNOWN'
        with self.assertRaises(ValueError):self.handoff(self.selection())
    def test_generated_parent_must_be_standardized_before_docking(self):
        self.mutate('eligible_candidate_outputs.private.json',lambda x:x[0].update(parent_id='UNASSESSED_GENERATED_PARENT'));x=self.selection();x['target_workflow']='vina_docking';x['review_sha256']=digest({k:v for k,v in x.items() if k!='review_sha256'})
        with self.assertRaises(ValueError):self.handoff(x)
