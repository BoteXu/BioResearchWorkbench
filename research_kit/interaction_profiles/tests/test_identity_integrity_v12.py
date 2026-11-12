"""Metadata rejection fixtures only; no molecules, RDKit, numerical stack or server run."""
from pathlib import Path
import ast,copy,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'server')]
from contracts import read,digest
from postanalysis_contracts import identity_policy,ISOTOPE_SCOPE,validate_parameters
from identity_reports import inspect_identity_variant,PREPARED,CONSISTENT,SUCCESS


class Fixture:
    def __init__(self,count=1,policy='state_graph'):
        self.p=read(ROOT/'examples/prepare_generated_identities.project.example.json')['parameters']
        self.p['parent_policy']=policy;self.p['minimum_prepared_fraction']=1.
        self.spec={'origin_variant':'primary','candidate_ids':['generated_'+str(i) for i in range(count)]}
        self.content={};self.bound={};self.v='primary';self.prefix='primary/'
        pol=identity_policy(self.p);ps=digest(pol)
        self.content['primary/identity_policy.private.json']=pol
        self.content['primary/origin_lineage.private.json']={'source_review':{'state':CONSISTENT,'issues':[]}}
        request=read(ROOT/'examples/branches/unconditional_control.disabled.json')
        request['run_id']='IDENTITY_METADATA_FIXTURE';g=request['parameters']['generation_options']
        self.content['primary/origin_request_snapshot.private.json']=request
        contract={'generation_options_sha256':digest(g),'reference_snapshots':[]}
        self.content['primary/origin_generation_contract_snapshot.private.json']=contract
        source_outputs=[];source_elig=[];records=[];eligible=[];groups={}
        def source_file(path,obj):
            rec={'path':path,**self.file(obj)};source_outputs.append(rec);return rec
        cfile=source_file('primary/generation_contract.private.json',contract)
        for cid in self.spec['candidate_ids']:
            smi='C';state=request['run_id']+'__primary__'+cid
            srcfile=source_file('primary/'+cid+'.sdf',{'fictional_SDF_not_molecular_evidence':cid})
            source_sdf={'path':cid+'.sdf','sha256':srcfile['sha256'],'bytes':srcfile['bytes'],'state_id':state,'parent_id':'UNASSESSED_GENERATED_PARENT','microstate_id':smi}
            profile=[{'reference_id':r['reference_id'],'guidance_weight':w,'guidance_direction':'positive' if w>0 else 'negative' if w<0 else 'zero','scoring_state':'SCORED','shape_similarity':.8,'esp_surface_similarity':.7,'pharmacophore_similarity':None,'scope':'raw_GFN2_xTB_ligand_profile_similarity_not_binding_energy_or_selectivity'} for r,w in zip(g['reference_conditions'],request['parameters']['profile_weights'])]
            source_report={'candidate_id':cid,'state':SUCCESS,'failure_reason':'','chemical_valid':True,'actual_structure_QC':True,'saved_SDF_readback_verified':True,'constraints_passed':True,'hard_constraints_assessed':True,'eligible':True,'actual_sdf':source_sdf,'generation_contract_sha256':cfile['sha256'],'generation_options_sha256':digest(g),'experimental_binding_established':False,'native_output_to_source_translation_angstrom':[0.,0.,0.],'profile_fidelity_scores':profile,'reference_results':[]}
            cr=source_file('primary/'+cid+'.constraints.private.json',source_report)
            self.content['primary/'+cid+'.source_constraints.private.json']=source_report
            self.bound['primary/'+cid+'.source_constraints.private.json']={**cr,'path':'primary/'+cid+'.source_constraints.private.json'}
            old={**source_sdf,'candidate_id':cid,'variant':'primary','path':srcfile['path'],'constraint_report_path':cr['path'],'constraint_report_sha256':cr['sha256'],'generation_contract_sha256':cfile['sha256'],'generation_options_sha256':digest(g),'constraints_passed':True,'eligibility':'REQUIRES_NEW_DOWNSTREAM_QC'}
            source_elig.append(old)
            parent_smiles='[H]C([H])([H])[H]';parent='COMPUTED_GROUP_'+digest({'policy_sha256':ps,'canonical_parent_smiles':parent_smiles})
            fingerprint=digest({'fictional_graph_or_coordinate_fixture':cid})
            prepared_file=self.file({'fictional_prepared_SDF_not_molecular_evidence':cid})
            self.bound['primary/'+cid+'.identity.sdf']=prepared_file
            row={'candidate_id':cid,'state':PREPARED,'parent_id':parent,'source_parent_id':old['parent_id'],'microstate_id':smi,'state_id':state,'source_sdf_path':old['path'],'source_sdf_sha256':old['sha256'],'source_sdf_bytes':old['bytes'],'identity_policy_sha256':ps,'scientific_acceptance':'NOT_ESTABLISHED','original_graph_sha256':fingerprint,'original_coordinates_sha256':fingerprint,'prepared_graph_sha256':fingerprint,'prepared_coordinates_sha256':fingerprint,'original_formal_charge':0,'parent_formal_charge':0,'original_canonical_isomeric_smiles':parent_smiles,'canonical_parent_smiles':parent_smiles,'original_microstate_smiles':smi,'enumeration_status':'NOT_REQUESTED_STATE_GRAPH' if policy=='state_graph' else 'Completed','enumerated_tautomers':1,'original_graph_preserved':True,'original_atom_order_preserved':True,'original_coordinates_preserved':True,'prepared_sdf_readback_verified':True,'original_isotope_inventory':[],'parent_isotope_inventory':[],'isotope_policy_scope':ISOTOPE_SCOPE,'prepared_sdf_path':cid+'.identity.sdf','prepared_sdf_sha256':prepared_file['sha256'],'prepared_sdf_bytes':prepared_file['bytes'],'source_constraint_report_path':cid+'.source_constraints.private.json','source_constraint_report_sha256':cr['sha256'],'source_generation_contract_sha256':cfile['sha256'],'source_constraints_passed':True,'grouping_is_physiological_state_prediction':False,'no_candidates_dropped':True}
            records.append(row);groups.setdefault(parent,[]).append(cid)
            eligible.append({'candidate_id':cid,'variant':'primary','state_id':state,'parent_id':parent,'microstate_id':smi,'path':'primary/'+cid+'.identity.sdf',**prepared_file,'eligibility':'REQUIRES_NEW_DOWNSTREAM_QC','identity_report_path':'primary/'+cid+'.identity.private.json','identity_policy_sha256':ps,'source_sdf_sha256':old['sha256'],'constraints_preserved_by_exact_graph_atom_order_and_coordinate_invariance':True,'source_constraint_report_path':'primary/'+cid+'.source_constraints.private.json','source_constraint_report_sha256':cr['sha256']})
        for row,e in zip(records,eligible):
            members=groups[row['parent_id']];row.update(parent_group_size=len(members),group_representative_for_display_only=row['candidate_id']==members[0])
            report='primary/'+row['candidate_id']+'.identity.private.json'
            self.content[report]=row;self.bound[report]=self.file(row);e['identity_report_sha256']=self.bound[report]['sha256']
        snap=source_file('eligible_candidate_outputs.private.json',source_elig)
        self.bound['primary/origin_eligibility_snapshot.private.json']=snap
        self.content['primary/origin_eligibility_snapshot.private.json']=source_elig
        self.content['primary/origin_receipt_snapshot.private.json']={'outputs':source_outputs}
        self.content['primary/identity_records.private.json']=records
        self.content['primary/parent_groups.private.json']={'policy_sha256':ps,'groups':groups,'duplicates_retained':True,'identity_scope':'computed_grouping_not_independent_biological_or_experimental_entities'}
        self.eligible=eligible
    @staticmethod
    def file(obj):return {'sha256':digest(obj),'bytes':len(json.dumps(obj).encode('utf8'))}
    def result(self):return inspect_identity_variant(self.v,self.content,self.bound,self.p,self.spec,self.eligible)
    def row(self,index=0):return self.content['primary/identity_records.private.json'][index]
    def old(self,index=0):return self.content['primary/origin_eligibility_snapshot.private.json'][index]
    def source_report(self,index=0):return self.content['primary/'+self.spec['candidate_ids'][index]+'.source_constraints.private.json']
    def issues(self):return self.result()[0]


class IdentityIntegrity(unittest.TestCase):
    def test_complete_consistent_metadata_is_accepted_with_science_unestablished(self):
        f=Fixture();issues,records,metrics=f.result();self.assertEqual(issues,[]);self.assertEqual(metrics['prepared_fraction'],1.);self.assertEqual(records[0]['scientific_acceptance'],'NOT_ESTABLISHED')
    def test_eligible_cannot_swap_to_another_registered_SDF(self):
        f=Fixture();other=f.file({'other':'not_the_reported_candidate'});f.bound['primary/different.sdf']=other;f.eligible[0].update(path='primary/different.sdf',**other)
        self.assertIn('identity_eligibility_points_to_different_prepared_SDF',f.issues())
    def test_eligible_hash_must_match_same_candidate_prepared_report(self):
        f=Fixture();f.eligible[0]['sha256']='a'*64;self.assertIn('identity_eligibility_points_to_different_prepared_SDF',f.issues())
    def test_original_eligibility_snapshot_must_match_source_receipt_bytes(self):
        f=Fixture();f.bound['primary/origin_eligibility_snapshot.private.json']={**f.bound['primary/origin_eligibility_snapshot.private.json'],'bytes':5};self.assertIn('origin_eligibility_snapshot_not_bound_to_original_receipt',f.issues())
    def test_original_eligibility_snapshot_must_match_source_receipt_hash(self):
        f=Fixture();f.bound['primary/origin_eligibility_snapshot.private.json']={**f.bound['primary/origin_eligibility_snapshot.private.json'],'sha256':'0'*64};self.assertIn('origin_eligibility_snapshot_not_bound_to_original_receipt',f.issues())
    def test_identity_cannot_inherit_a_quality_HOLD_source(self):
        f=Fixture();f.content['primary/origin_lineage.private.json']['source_review']={'state':'HOLD','issues':['prespecified_chemical_valid_fraction_failed']};self.assertIn('identity_origin_complete_source_review_not_accepted',f.issues())
    def test_consistent_source_label_cannot_hide_nonempty_issues(self):
        f=Fixture();f.content['primary/origin_lineage.private.json']['source_review']['issues']=['source_changed'];self.assertIn('identity_origin_complete_source_review_not_accepted',f.issues())
    def test_source_candidate_must_belong_to_selected_original_variant(self):
        f=Fixture();f.old()['variant']='other';self.assertIn('selected_identity_source_not_qualified_or_original_receipt_bound',f.issues())
    def test_source_eligible_candidates_are_unique_in_each_variant(self):
        f=Fixture();f.content['primary/origin_eligibility_snapshot.private.json'].append(copy.deepcopy(f.old()));self.assertIn('origin_eligibility_snapshot_candidate_axis_invalid',f.issues())
    def test_source_SDF_sha_is_bound_to_original_receipt(self):
        f=Fixture();f.old()['sha256']='1'*64;self.assertIn('selected_identity_source_not_qualified_or_original_receipt_bound',f.issues())
    def test_source_eligibility_must_still_have_constraints_passed(self):
        f=Fixture();f.old()['constraints_passed']=False;self.assertIn('selected_identity_source_not_qualified_or_original_receipt_bound',f.issues())
    def test_source_microstate_cannot_be_relabelled_in_new_report(self):
        f=Fixture();f.row()['microstate_id']='N';self.assertIn('identity_record_does_not_preserve_original_source_identity',f.issues())
    def test_original_parent_and_source_bytes_remain_explicit(self):
        f=Fixture();del f.row()['source_parent_id'];f.row()['source_sdf_bytes']=True;self.assertIn('identity_record_does_not_preserve_original_source_identity',f.issues())
    def test_success_requires_selected_complete_source_constraint_report(self):
        f=Fixture();del f.content['primary/generated_0.source_constraints.private.json'];self.assertIn('original_constraint_report_missing_or_not_original_receipt_bound',f.issues())
    def test_source_constraint_copy_is_bound_to_original_receipt(self):
        f=Fixture();f.bound['primary/generated_0.source_constraints.private.json']={'sha256':'2'*64,'bytes':15};self.assertIn('original_constraint_report_missing_or_not_original_receipt_bound',f.issues())
    def test_source_constraint_saved_SDF_identity_cannot_change(self):
        f=Fixture();f.source_report()['actual_sdf']['state_id']='OTHER';self.assertIn('original_candidate_constraint_or_saved_state_identity_changed',f.issues())
    def test_source_constraint_flags_are_rechecked_not_only_inherited(self):
        f=Fixture();f.source_report()['eligible']=False;self.assertIn('original_candidate_constraint_or_saved_state_identity_changed',f.issues())
    def test_source_actual_constraint_reference_denominator_is_rechecked(self):
        f=Fixture();f.source_report()['reference_results']=[{'reference_id':'unrequested'}];self.assertTrue(any(x.startswith('source_') for x in f.issues()))
    def test_eligible_constraint_copy_cannot_be_replaced(self):
        f=Fixture();f.eligible[0]['source_constraint_report_path']='primary/other.json';self.assertIn('identity_eligibility_report_or_chemical_identity_changed',f.issues())
    def test_graph_fingerprints_are_required_even_when_preservation_flags_are_true(self):
        f=Fixture();del f.row()['original_graph_sha256'];self.assertIn('original_and_prepared_graph_or_coordinate_fingerprints_disagree',f.issues())
    def test_prepared_coordinate_fingerprint_must_equal_original(self):
        f=Fixture();f.row()['prepared_coordinates_sha256']='3'*64;self.assertIn('original_and_prepared_graph_or_coordinate_fingerprints_disagree',f.issues())
    def test_state_graph_parent_must_be_original_canonical_state(self):
        f=Fixture();f.row()['canonical_parent_smiles']='arbitrary';self.assertIn('state_graph_parent_differs_from_original_state',f.issues())
    def test_state_graph_denominator_cannot_be_negative_or_boolean(self):
        for value in (-5,True,2):
            f=Fixture();f.row()['enumerated_tautomers']=value;self.assertIn('state_graph_parent_differs_from_original_state',f.issues())
    def test_tautomer_completed_status_and_positive_bounded_count_are_required(self):
        for status,count in [('MaxTautomersReached',2),('Completed',0),('Completed',True),('Completed',1000000)]:
            f=Fixture(policy='charge_preserving_tautomer');f.row().update(enumeration_status=status,enumerated_tautomers=count);self.assertIn('tautomer_enumeration_not_complete_or_bounded',f.issues())
    def test_charge_preserving_tautomer_cannot_change_formal_charge(self):
        f=Fixture(policy='charge_preserving_tautomer');f.row()['parent_formal_charge']=1;self.assertIn('charge_preserving_parent_changed_charge',f.issues())
    def test_original_and_parent_charge_fields_are_exact_integers(self):
        f=Fixture();f.row()['original_formal_charge']=False;self.assertIn('original_or_parent_chemical_state_fields_invalid',f.issues())
    def test_isotope_inventory_loss_is_rejected(self):
        f=Fixture();f.row()['original_isotope_inventory']=[{'atomic_number':1,'isotope':2,'count':1}];self.assertIn('isotope_inventory_or_preservation_policy_changed',f.issues())
    def test_isotope_inventory_count_is_not_boolean(self):
        f=Fixture();bad=[{'atomic_number':1,'isotope':2,'count':True}];f.row()['original_isotope_inventory']=bad;f.row()['parent_isotope_inventory']=copy.deepcopy(bad);self.assertIn('isotope_inventory_or_preservation_policy_changed',f.issues())
    def test_fixed_isotope_policy_cannot_be_silently_replaced(self):
        f=Fixture();f.content['primary/identity_policy.private.json']['tautomer_remove_isotopic_hs']=True;self.assertIn('actual_identity_policy_or_software_changed',f.issues())
    def test_fixed_isotope_policy_boolean_is_not_the_integer_zero(self):
        f=Fixture();f.content['primary/identity_policy.private.json']['tautomer_remove_isotopic_hs']=0;self.assertIn('actual_identity_policy_or_software_changed',f.issues())
    def test_all_requested_failures_remain_in_denominator_and_do_not_gain_eligibility(self):
        f=Fixture();row=f.row();row.update(state='PREPARATION_FAILED',parent_id=None,parent_group_size=0,group_representative_for_display_only=False,error='ENUMERATION_NOT_COMPLETED');f.eligible=[];f.content['primary/parent_groups.private.json']['groups']={}
        issues,_,metrics=f.result();self.assertEqual(metrics['requested_count'],1);self.assertEqual(metrics['prepared_count'],0);self.assertEqual(metrics['prepared_fraction'],0.);self.assertIn('prespecified_prepared_fraction_failed',issues)
    def test_complete_request_denominator_cannot_drop_a_candidate(self):
        f=Fixture(count=2);f.content['primary/identity_records.private.json'].pop()
        with self.assertRaises(ValueError):f.result()
    def test_duplicate_eligible_identity_cannot_expand_or_replace_denominator(self):
        f=Fixture();f.eligible.append(copy.deepcopy(f.eligible[0]));self.assertIn('identity_eligibility_denominator_changed',f.issues())
    def test_multiple_group_members_are_retained_without_selecting_only_representative(self):
        f=Fixture(count=2);issues,records,metrics=f.result();self.assertEqual(issues,[]);self.assertEqual(metrics['prepared_count'],2);self.assertEqual(metrics['computed_parent_groups'],1);self.assertEqual(sum(r['group_representative_for_display_only'] for r in records),1)
    def test_success_with_failure_reason_is_rejected(self):
        f=Fixture();f.row()['error']='previous_error';self.assertIn('prepared_identity_carries_failure_reason',f.issues())


class FixedIsotopeAPI(unittest.TestCase):
    def test_fixed_isotope_control_uses_public_cleanup_constructor_API(self):
        path=ROOT/'server/identity_preparation.py';source=path.read_text(encoding='utf8');ast.parse(source)
        self.assertIn('cleanup.tautomerRemoveIsotopicHs=False',source);self.assertIn('TautomerEnumerator(cleanup)',source);self.assertNotIn('SetRemoveIsotopicHs(',source)
    def test_unsigned_native_enumeration_limit_cannot_overflow(self):
        for key in ('max_tautomers','max_transforms'):
            r=read(ROOT/'examples/prepare_generated_identities.project.example.json');r['parameters'][key]=4294967296
            with self.assertRaises(ValueError):validate_parameters(r)
    def test_metadata_suite_does_not_import_scientific_stack(self):
        self.assertFalse(any(name in sys.modules for name in ('numpy','rdkit','torch','scipy','open3d')))


if __name__=='__main__':unittest.main()
