"""Fictional prepared-axis receipts and draft binding only, never molecule processing."""
from pathlib import Path
import copy,csv,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import read,write,sha,digest,validate
from acceptance import inspect
from reference_selection import bind_selections
import test_returns as returns_fixture


class ReferencePreparation(unittest.TestCase):
    def setUp(self):
        self.f=returns_fixture.Returns(methodName='test_consistent_format_never_establishes_scientific_acceptance');self.f.setUp();f=self.f
        source={'molecules':[{'id':'REF','role':'reference','sdf':{'sha256':'0'*64}}]}
        context=read(f.root/'source_context.private.json');context['preparation_domain_sha256']='a'*64
        for name,value in [('structure_manifest',source),('context',context)]:
            sourcepath=f.base/'inputs'/(name+'.private.json');sourcepath.write_text(json.dumps(value),encoding='utf8')
            (f.root/('source_structures.private.json' if name=='structure_manifest' else 'source_context.private.json')).write_text(json.dumps(value),encoding='utf8')
            next(x for x in f.request['inputs'] if x['id']==name)['sha256']=sha(sourcepath)
        f.request['method']='prepare_reference_profiles';f.request.pop('plan_sha256');f.request['plan_sha256']=digest(f.request);f.request_path.write_text(json.dumps(f.request),encoding='utf8')
        f.receipt.update(method='prepare_reference_profiles',request_sha256=sha(f.request_path),plan_sha256=f.request['plan_sha256'],inputs=f.request['inputs'])
        proof=read(f.root/'full_result_audit.private.json')
        for row in proof:
            folder=f.root/row['variant'];role=row['role'];data=[] if role=='profile_scores' else [{'candidate_id':'REF','state':'REFERENCE_PROFILE_PREPARED'}]
            fpath=folder/(role+'.tsv');columns=row['columns'] if role=='profile_scores' else ['candidate_id','state']
            with fpath.open('w',encoding='utf8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=columns,delimiter='\t');w.writeheader();w.writerows(data)
            preview=folder/(role+'.preview.private.json');preview.write_text(json.dumps({'full_result_sha256':sha(fpath),'full_rows':len(data),'preview_rows':data,'is_full_result':True}),encoding='utf8')
            row.update(sha256=sha(fpath),bytes=fpath.stat().st_size,rows=len(data),columns=columns,preview_sha256=sha(preview),candidate_row_counts={'REF':1} if data else {},status_counts={'REFERENCE_PROFILE_PREPARED':1} if data else {})
        (f.root/'full_result_audit.private.json').write_text(json.dumps(proof),encoding='utf8');(f.root/'eligible_candidate_outputs.private.json').write_text('[]',encoding='utf8')
        atoms=[{'atomic_number':6,'formal_charge':0,'isotope':0}]*6
        points=[{'type':3,'position_angstrom':[0.,0.,0.],'direction':[0.,0.,0.]}]*2
        axes={'reference_id':'REF','source_sdf_sha256':'0'*64,'atom_axis':atoms,'atom_axis_sha256':digest(atoms),'pharmacophore_axis':points,'pharmacophore_axis_sha256':digest(points),'frame_id':context['frame_id'],'preparation_domain_sha256':'a'*64}
        for label in f.labels:
            write(f.root/label/'reference_axis_index.private.json',[axes]);f.selected.append(label+'/reference_axis_index.private.json')
        f.rebind()
        from test_return_integrity_v12 import upgrade_fixture_v12
        upgrade_fixture_v12(f)
    def tearDown(self):self.f.tearDown()
    def draft(self):
        project=read(ROOT/'examples/shepherd2_generate.project.example.json');project['parameters']['generation_options']['reference_conditions'][0]['reference_id']='REF';return project
    def bind(self,project=None):
        f=self.f;return bind_selections(f.request_path,f.root,f.selected,project or self.draft(),'primary')
    def test_reference_axis_return_is_bounded_consistency_only(self):
        self.assertEqual(self.f.result()['state'],'RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW',self.f.result())
    def test_changed_pharmacophore_axis_is_rejected(self):
        self.f.mutate('primary/reference_axis_index.private.json',lambda x:x[0]['pharmacophore_axis'].pop());self.assertIn('prepared_reference_axis_source_changed',self.f.result()['issues'])
    def test_axis_binding_retains_disabled_review_state(self):
        draft=self.bind();s=draft['parameters']['generation_options']['reference_conditions'][0]
        self.assertEqual(s['expected_atom_count'],6);self.assertEqual(s['expected_pharmacophore_count'],2);self.assertTrue(draft['example_only']);self.assertFalse(draft['server_execution_authorized'])
        with self.assertRaises(ValueError):validate(draft)
    def test_binding_does_not_choose_scaffold_or_priority_points(self):
        project=self.draft();s=project['parameters']['generation_options']['reference_conditions'][0];s.update(scaffold_mode='fixed',scaffold_atom_indices=[1,3]);project['parameters']['generation_options']['atom_condition_reference_id']='REF'
        draft=self.bind(project);self.assertEqual(draft['parameters']['generation_options']['reference_conditions'][0]['scaffold_atom_indices'],[1,3])
    def test_unknown_reference_is_not_replaced_by_first_profile(self):
        project=self.draft();project['parameters']['generation_options']['reference_conditions'][0]['reference_id']='UNKNOWN'
        with self.assertRaises(ValueError):self.bind(project)
    def test_HOLD_reference_profiles_cannot_bind_a_generation_draft(self):
        self.f.receipt['state']='UNKNOWN';self.f.rebind()
        with self.assertRaises(ValueError):self.bind()
