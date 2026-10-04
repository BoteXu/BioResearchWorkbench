"""Synthetic project, recovery, private sync, review and native refusal checks."""
import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import academic_common as common
import workbench_ext as work
import academic_workspace_ext as academic
import personal_library_ext as personal
import workflow_ext as workflow
import scientific_backend_ext as scientific
import word_native_ext as word

CONTEXT=dict(species='synthetic',model='fixture',assay='fixture',biological_unit='study',contrast='fixture',limitations=['Synthetic verification only'])


class WorkbenchChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve());self.root=Path(self.tmp.name)
        self.patches=[patch.object(m,'HERE',self.root) for m in (common,work,academic,personal,workflow,scientific,word)]
        for p in self.patches:p.start()
        self.project=work.create_research_project('Synthetic project','What changes?','Independent studies',CONTEXT,{'estimand':'mean difference'})['project_id']
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def save(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value),encoding='utf8');return str(p)
    def sha(self,path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def plan(self,changes,rev=0):
        r=work.prepare_project_revision(self.project,rev,changes);p=str(Path(r['output_directory'])/'review.json')
        return p,self.sha(p)
    def apply(self,changes,rev=0):
        p,h=self.plan(changes,rev);return work.apply_project_revision(p,h,True)
    def stage(self,identity='qc',kind='qc',deps=None):return {'id':identity,'kind':kind,'placement':'server','depends_on':deps or []}
    def event(self,event,rev,data,stage='qc',assessment=None):
        return work.advance_workflow_stage(self.project,stage,rev,event,self.save('receipt.json',data),assessment)
    def test_project_revision_conflict(self):
        p,h=self.plan({'title':'Changed'});self.apply({'title':'Other'})
        with self.assertRaises(ValueError):work.apply_project_revision(p,h,True)
        self.assertEqual(work.inspect_research_project(self.project)['project']['title'],'Other')
    def test_reviewed_plan_hash(self):
        p,h=self.plan({'title':'Changed'});Path(p).write_text('{}')
        with self.assertRaises(ValueError):work.apply_project_revision(p,h,True)
    def test_analysis_requires_qc_dependency(self):
        with self.assertRaises(ValueError):self.plan({'stages':[self.stage('a','analysis')]})
    def test_cycle_refused(self):
        with self.assertRaises(ValueError):self.plan({'stages':[self.stage('a','qc',['b']),self.stage('b','qc',['a'])]})
    def test_unknown_not_resubmitted(self):
        self.apply({'stages':[self.stage()]});self.event('prepare',1,{'request_sha256':'a'*64})
        self.event('submit',2,{'job_id':'123'});self.event('observe_unknown',3,{'state':'unknown'})
        with self.assertRaises(ValueError):self.event('submit',4,{'job_id':'456'})
    def test_unmet_qc_blocks_analysis(self):
        self.apply({'stages':[self.stage(),self.stage('a','analysis',['qc'])]})
        with self.assertRaises(ValueError):self.event('prepare',1,{},'a')
    def test_complete_accept_then_dependency_ready(self):
        self.apply({'stages':[self.stage(),self.stage('a','analysis',['qc'])]})
        self.event('prepare',1,{'request_sha256':'a'*64})
        self.event('observe_completion',2,{'request_sha256':'a'*64,'state':'succeeded','exit_code':0,'outputs':[{'exists':True,'bytes':3,'sha256':'b'*64}]})
        with self.assertRaises(ValueError):self.event('accept',3,{},assessment={'decision':'pass'})
        self.event('accept',3,{},assessment={'decision':'pass','checks':['input/unit review'],'limitations':['synthetic']})
        self.assertTrue(work.inspect_research_project(self.project)['stages'][1]['ready'])
    def test_false_completion_refused(self):
        self.apply({'stages':[self.stage()]});self.event('prepare',1,{'request_sha256':'a'*64})
        with self.assertRaises(ValueError):self.event('observe_completion',2,{'state':'succeeded','exit_code':0,'outputs':[{'exists':False}]})
    def test_wrong_task_receipt_refused(self):
        self.apply({'stages':[self.stage()]});self.event('prepare',1,{'request_sha256':'a'*64})
        with self.assertRaises(ValueError):self.event('observe_completion',2,{'state':'succeeded','request_sha256':'c'*64,'exit_code':0,'outputs':[{'exists':True,'bytes':3,'sha256':'b'*64}]})
    def test_executed_stage_cannot_be_deleted(self):
        self.apply({'stages':[self.stage()]});self.event('prepare',1,{})
        with self.assertRaises(ValueError):self.plan({'stages':[]},2)
    def test_lineage_and_source_change_propagation(self):
        self.apply({'datasets':[{'id':'d1','cohort_ids':['c'],'subject_tokens':['p']},{'id':'d2','cohort_ids':['c'],'subject_tokens':['p']}],
            'claims':[{'id':'claim'}],'figures':[{'id':'fig'}],'edges':[{'source':'d1','target':'claim','relation':'supports'},{'source':'claim','target':'fig','relation':'shown_in'}]})
        r=work.audit_project_lineage(self.project,['d1']);self.assertEqual(r['overlaps'][0]['shared_subject_count'],1);self.assertIn('fig',r['affected_ids'])
    def test_dashboard_escapes_private_text(self):
        self.apply({'title':'<script>alert(1)</script>'});r=work.build_project_dashboard(self.project)
        raw=Path(r['output_directory'],'dashboard.html').read_text();self.assertNotIn('<script>',raw);self.assertIn('&lt;script&gt;',raw)
    def test_freeze_hashes_selected_files(self):
        p=self.save('result.json',{'value':1});r=work.freeze_reproduction_package(self.project,[{'name':'result.json','path':p}],{'software':'synthetic-v1'},[['tool','input']])
        self.assertEqual(r['files'][0]['sha256'],self.sha(p))
    def test_backup_restore_fresh_staging(self):
        r=work.create_private_backup([self.project]);archive=str(Path(r['output_directory'])/'backup.zip')
        plan=work.prepare_private_restore(archive,str(self.root/'restore'));p=str(Path(plan['output_directory'])/'review.json')
        result=work.apply_private_restore(p,self.sha(p),True);self.assertFalse(result['active_installation_modified'])
        with self.assertRaises(ValueError):work.apply_private_restore(p,self.sha(p),True)
    def test_backup_archive_unlisted_member_refused(self):
        p=self.root/'bad.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('backup_manifest.json',json.dumps({'schema':1,'files':[]}));z.writestr('../escape','bad')
        with self.assertRaises(ValueError):work.prepare_private_restore(str(p),str(self.root/'restore'))
    def test_adapter_contract_does_not_execute(self):
        c={'schema':1,'id':'fixture','version':'1','license':'test','source':'synthetic','placement':'server',
            'inputs':[{'name':'input','format':'csv','required':True}],'outputs':[{'name':'output','format':'json','required':True}],
            'resources':{'cpus':1,'memory_mb':512,'walltime_minutes':2},'invocation':['Rscript','fixed.R'],'parser':'json_v1','runtime_state':'unverified'}
        self.assertEqual(work.validate_adapter_contract(c)['decision'],'pass')
        c['placement']='arbitrary';self.assertEqual(work.validate_adapter_contract(c)['decision'],'fail')
    def test_scientific_adapter_missing_qc_contract(self):
        with self.assertRaises(ValueError):scientific.prepare_scientific_backend('coloc_susie',{},'/work','server.invalid','out',CONTEXT,[])
    def test_annotation_located_search(self):
        p=self.save('snapshot.json',{'records':[{'key':'ABCDEFGH','data':{'itemType':'annotation','parentItem':'PDFKEY01','annotationText':'The result was not causal.','annotationPageLabel':'iv'}}]})
        r=academic.index_selected_fulltext([],p);found=academic.search_selected_fulltext(r['index_id'],'not causal')
        self.assertIn('page_label:iv',found['records'][0]['location']);self.assertIn('not causal',found['records'][0]['excerpt'])
    def test_low_text_pdf_qc(self):
        p=self.root/'x.pdf';p.write_bytes(b'fixture')
        fake=types.SimpleNamespace(PdfReader=lambda stream:types.SimpleNamespace(is_encrypted=False,pages=[types.SimpleNamespace(extract_text=lambda:'')]))
        with patch.dict(sys.modules,{'pypdf':fake}):r=academic.index_selected_fulltext([{'path':str(p),'reference_id':'paper'}])
        self.assertEqual(r['qc'][0]['state'],'ocr_or_manual_review_required')
    def test_sync_preserves_private_annotations_and_missing_records(self):
        identity=personal.create_personal_library('Fixture','Synthetic')['library_id']
        p=self.save('z.json',{'source':'local_zotero','library':'user','collection_key':'ABCDEFGH','records':[{'key':'PAPER001','version':1,'data':{'itemType':'journalArticle','title':'First'}}],'coverage_complete':True})
        r=academic.prepare_zotero_incremental_sync(identity,p,'zotero_fixture',{'library':'user','collection_key':'ABCDEFGH'});plan=str(Path(r['output_directory'])/'review.json')
        academic.apply_zotero_incremental_sync(plan,self.sha(plan),True)
        r=academic.prepare_zotero_incremental_sync(identity,self.save('empty.json',{'source':'local_zotero','library':'user','collection_key':'ABCDEFGH','records':[]}), 'zotero_fixture',{'library':'user','collection_key':'ABCDEFGH'})
        plan=str(Path(r['output_directory'])/'review.json');academic.apply_zotero_incremental_sync(plan,self.sha(plan),True)
        self.assertEqual(sum(personal.inspect_personal_library(identity)['reading_state_counts'].values()),1)
    def search(self):
        with patch('privacy_ext.enforce_outbound'):return academic.create_review_search(['synthetic query'],True)['search_id']
    def page(self,identity):
        response={'success':True,'result':{'hitCount':2,'nextCursorMark':'next','resultList':{'result':[{'source':'MED','id':'1'}]}}}
        with patch('privacy_ext.enforce_outbound'),patch.dict(sys.modules,{'literature_ext':types.SimpleNamespace(query_europepmc=Mock(return_value=response))}):return academic.retrieve_review_search_page(identity,0,0,50,True)
    def test_resumable_search_cursor_and_coverage(self):
        identity=self.search();r=self.page(identity);self.assertFalse(r['query_coverage'][0]['complete']);self.assertEqual(r['query_coverage'][0]['cursor'],'next')
        response={'success':True,'result':{'hitCount':2,'resultList':{'result':[{'source':'MED','id':'2'}]}}}
        with patch('privacy_ext.enforce_outbound'),patch.dict(sys.modules,{'literature_ext':types.SimpleNamespace(query_europepmc=Mock(return_value=response))}):r=academic.retrieve_review_search_page(identity,0,1,50,True)
        self.assertTrue(r['query_coverage'][0]['complete']);self.assertEqual(r['unique_records'],2)
    def test_failed_search_page_retains_revision_cursor(self):
        identity=self.search()
        with patch('privacy_ext.enforce_outbound'),patch.dict(sys.modules,{'literature_ext':types.SimpleNamespace(query_europepmc=Mock(side_effect=RuntimeError('failed')))}):
            with self.assertRaises(RuntimeError):academic.retrieve_review_search_page(identity,0,0,50,True)
        state=academic.inspect_review_search(identity)['search'];self.assertEqual(state['revision'],0);self.assertEqual(state['queries'][0]['cursor'],'*')
    def test_real_second_reviewer_conflict_required(self):
        identity=self.search();self.page(identity)
        academic.record_independent_screening(identity,1,'MED:1','reviewer_a','include','Eligible',True)
        with self.assertRaises(ValueError):academic.resolve_screening_conflict(identity,2,'MED:1','resolver','include','Reviewed')
        academic.record_independent_screening(identity,2,'MED:1','reviewer_b','exclude','Model mismatch',True)
        self.assertEqual(academic.inspect_review_search(identity)['unresolved_conflicts'],['MED:1'])
        academic.resolve_screening_conflict(identity,3,'MED:1','resolver','exclude','Fulltext confirms mismatch')
        self.assertEqual(academic.inspect_review_search(identity)['unresolved_conflicts'],[])
    def test_native_external_template_refused(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('word/_rels/settings.xml.rels','<Relationships><Relationship Type="x/attachedTemplate" TargetMode="External" Target="remote"/></Relationships>')
        with self.assertRaises(ValueError):word._document(buf.getvalue())
    def test_native_macro_refused(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('word/vbaProject.bin',b'macro')
        with self.assertRaises(ValueError):word._document(buf.getvalue())


if __name__=='__main__':unittest.main()
