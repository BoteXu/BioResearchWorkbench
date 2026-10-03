"""Synthetic academic workflows and local Zotero protocol/refusal tests; no personal library or cloud writes."""
import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import academic_common as common
import library_ext as library
import review_ext as review
import collaboration_ext as collaboration
import zotero_ext as zotero
import evidence


class AcademicChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.home=patch.object(common,'HERE',self.root);self.home.start()
        self.zhome=patch.object(zotero,'HERE',self.root);self.zhome.start()
        self.refs=self.root/'refs.ris';self.refs.write_text('TY  - JOUR\nID  - alpha\nTI  - Example study\nDO  - 10.1234/example\nAU  - Doe, J\nPY  - 2024\nER  -\n',encoding='utf8')
        self.doc=self.root/'draft.md';self.doc.write_text('# Study\n## Results\nThe effect was uncertain [@alpha].\n## Discussion\nTODO explain limits.\n',encoding='utf8')
    def tearDown(self):
        self.home.stop();self.zhome.stop();self.temp.cleanup()
    def write(self,name,value):
        p=self.root/name;p.write_text(value,encoding='utf8');return str(p)
    def test_ris_fields_and_ids(self):
        r=library.import_reference_library(str(self.refs));self.assertEqual(r['records'][0]['id'],'alpha');self.assertEqual(r['records'][0]['doi'],'10.1234/example')
    def test_ncbi_throttle_bootstrap_transaction(self):
        with patch.object(evidence,'HERE',self.root):
            evidence.throttle('synthetic_service',0);evidence.throttle('synthetic_service',0)
            with evidence.connection() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM throttle').fetchone()[0],1)
    def test_ris_incomplete_entry_rejected(self):
        with self.assertRaises(ValueError):library.import_reference_library(self.write('bad.ris','TY  - JOUR\nTI  - unclosed'))
    def test_bibtex_nested_title_and_comma(self):
        r=library.import_reference_library(self.write('refs.bib','@article{a, title={A {nested}, title}, author={Doe, J and Roe, K}, year=2024}'))
        self.assertEqual(r['records'][0]['title'],'A {nested}, title');self.assertEqual(len(r['records'][0]['authors']),2)
    def test_bibtex_macro_not_invented(self):
        r=library.import_reference_library(self.write('refs.bib','@string{j={Journal}}\n@article{a,title={Title},journal=j}'))
        self.assertEqual(len(r['unsupported_entries']),1);self.assertIn('unexpanded_macro:journal',r['records'][0]['issues'])
    def test_csl_author_literal_and_year(self):
        r=library.import_reference_library(self.write('refs.json',json.dumps([{'id':'a','title':'Title','type':'article-journal','author':[{'literal':'Study Group'}],'issued':{'date-parts':[[2024]]}}])))
        self.assertEqual(r['records'][0]['authors'],['Study Group']);self.assertEqual(r['records'][0]['year'],'2024')
    def test_endnote_xml_record_ids(self):
        r=library.import_reference_library(self.write('refs.xml','<xml><records><record><rec-number>17</rec-number><titles><title>Study</title></titles><contributors><authors><author>Doe</author></authors></contributors></record></records></xml>'))
        self.assertEqual(r['records'][0]['id'],'17')
    def test_xml_entity_refusal(self):
        with self.assertRaises(ValueError):library.import_reference_library(self.write('bad.xml','<!DOCTYPE x [<!ENTITY e SYSTEM "file:///private">]><xml>&e;</xml>'))
    def test_duplicate_doi_not_merged(self):
        path=self.write('dup.ris',self.refs.read_text()+self.refs.read_text().replace('ID  - alpha','ID  - beta'))
        r=library.audit_reference_duplicates(path);self.assertEqual(r['candidates'][0]['basis'],'doi');self.assertEqual(len(library.load_library(path)[0]),2)
    def test_ris_export_roundtrip(self):
        r=library.export_reference_library(str(self.refs),'ris');after=library.load_library(str(Path(r['output_directory'])/'references.ris'))[0]
        self.assertEqual(after[0]['id'],'alpha');self.assertEqual(after[0]['doi'],'10.1234/example')
    def test_csl_export_roundtrip(self):
        r=library.export_reference_library(str(self.refs),'csl-json');after=library.load_library(str(Path(r['output_directory'])/'references.json'))[0]
        self.assertEqual(after[0]['authors'],['Doe, J'])
    def test_bibtex_export_roundtrip(self):
        r=library.export_reference_library(str(self.refs),'bibtex');after=library.load_library(str(Path(r['output_directory'])/'references.bib'))[0]
        self.assertEqual(after[0]['title'],'Example study')
    def test_zotero_snapshot_can_feed_library_export(self):
        snapshot={'records':[{'key':'ABCDEFGH','data':{'itemType':'journalArticle','title':'Local study','DOI':'10.1234/example','date':'2024-01-01','publicationTitle':'Journal','volume':'3','creators':[{'creatorType':'author','firstName':'J','lastName':'Doe'}]}}]}
        path=self.write('zotero.json',json.dumps(snapshot));r=library.export_reference_library(path,'csl-json')
        records=json.loads(Path(r['output_directory'],'references.json').read_text(encoding='utf8'))
        self.assertEqual(records[0]['id'],'ABCDEFGH');self.assertEqual(records[0]['container-title'],'Journal')
    def test_unresolved_macro_export_refused(self):
        with self.assertRaises(ValueError):library.export_reference_library(self.write('macro.bib','@article{a,title={Title},journal=macro}'),'bibtex')
    def test_manuscript_locations(self):
        r=review.inspect_manuscript(str(self.doc));self.assertEqual(r['segments'][2]['location'],'line:3')
    def test_claim_quote_hash_and_context(self):
        source=self.write('source.md','A descriptive association was observed.\n')
        e={'reference_id':'alpha','source_path':source,'source_location':'line:1','quote':'association was observed','source_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),
           'decision':'insufficient','rationale':'Different estimand','species':'human','model':'observational cohort','assay':'expression','independent_unit':'donor','contrast':'case/control','limitations':'noncausal'}
        c={'id':'c1','claim':'The effect was uncertain','location':'line:3','evidence':[e]}
        r=review.audit_claim_evidence(str(self.doc),[c],str(self.refs));self.assertTrue(r['claims'][0]['evidence'][0]['excerpt_located']);self.assertIn('no_reviewer_confirmed_support',r['claims'][0]['issues'])
    def test_claim_wrong_quote_blocks_support(self):
        e={'reference_id':'alpha','source_path':str(self.doc),'source_location':'line:3','quote':'A strong causal effect','decision':'supports','source_sha256':'wrong'}
        r=review.audit_claim_evidence(str(self.doc),[{'id':'c','claim':'The effect was uncertain','location':'line:3','evidence':[e]}],str(self.refs))
        self.assertIn('source_excerpt_not_found',r['claims'][0]['issues']);self.assertIn('source_hash_missing_or_changed',r['claims'][0]['issues'])
    def test_format_unknown_citation(self):
        r=review.audit_manuscript_format(self.write('bad.md','Study [@absent].\n'),str(self.refs));self.assertEqual(r['findings'][0]['rule'],'unknown_citation_key')
    def test_format_supplied_journal_rules(self):
        r=review.audit_manuscript_format(str(self.doc),str(self.refs),{'journal':'Example','source_url':'https://example.org/author-guide','checked_on':'2026-01-01','version':'reviewed','max_words':1,'required_sections':['Results']})
        self.assertFalse(r['journal_rule_checks'][0]['pass']);self.assertEqual(r['scope'],'supplied_journal_rules')
    def test_review_cohort_overlap_and_screening(self):
        r=review.audit_review(str(self.doc),'systematic',[],[],[{'id':'a','decision':'included'},{'id':'b','decision':'included'}],[{'id':'a','cohort_id':'same'},{'id':'b','cohort_id':'same'}])
        self.assertEqual(r['overlap_candidates'][0]['records'],['a','b']);self.assertFalse(r['search_coverage_declared'])
    def test_review_missing_exclusion_reason(self):
        r=review.audit_review(str(self.doc),'narrative',[],[],[{'id':'a','decision':'fulltext_excluded'}],[])
        self.assertEqual(r['screening_issues'][0]['issue'],'missing_exclusion_reason')
    def test_reporting_checklist_preserves_unassessed_items(self):
        profile={'name':'Reviewed checklist','version':'1','source_url':'https://example.org/checklist','checked_on':'2026-01-01','items':[{'id':'a','requirement':'Report outcome'},{'id':'b','requirement':'Report limitations'}]}
        r=review.audit_reporting_checklist(str(self.doc),profile,[{'id':'a','state':'reported','rationale':'Located','excerpts':[{'location':'line:3','quote':'effect was uncertain'}]}])
        self.assertEqual(r['assessments'][1]['reviewer_state'],'not_assessed');self.assertFalse(r['assessments'][0]['issues'])
    def test_terminology_first_use_before_definition(self):
        path=self.write('abbr.md','AUC was reported.\nArea under curve (AUC) was defined later.\n')
        r=review.audit_terminology_units(path,[{'abbreviation':'AUC','expansion':'Area under curve'}],[])
        self.assertFalse(r['checks'][0]['definition_before_first_use'])
    def test_unit_mismatch_is_retained(self):
        path=self.write('units.md','The concentration was 5 mg.\n')
        r=review.audit_terminology_units(path,[],[{'quantity':'concentration','expected_unit':'mg/L','mentions':[{'location':'line:1','literal':'5 mg','unit':'mg'}]}])
        self.assertFalse(r['checks'][0]['checks'][0]['unit_matches_declared_rule'])
    def test_metadata_transmits_only_doi(self):
        result={'result':{'message':{'title':['Example study'],'issued':{'date-parts':[[2024]]}}}}
        call=Mock(return_value=result)
        with patch.dict(sys.modules,{'literature_ext':types.SimpleNamespace(doi_metadata=call)}):r=review.audit_reference_metadata(str(self.refs),True)
        call.assert_called_once_with('10.1234/example');self.assertEqual(r['records'][0]['state'],'queried_metadata_fields_match')
    def test_similar_search_requires_exact_authorization(self):
        with self.assertRaises(ValueError):review.find_similar_studies(['public query'],{})
    def test_similar_facets_stay_local(self):
        response={'success':True,'result':{'hitCount':2,'resultList':{'result':[{'id':'1','source':'MED','title':'Human cardiac study','abstractText':'donor analysis'}]},'nextCursorMark':'next'}}
        search=Mock(return_value=response)
        with patch.dict(sys.modules,{'literature_ext':types.SimpleNamespace(query_europepmc=search)}):
            r=review.find_similar_studies(['cardiac research'],{'species':['human'],'tissue':['cardiac'],'question_terms':['private comparison phrase']},True,5)
        search.assert_called_once_with('cardiac research',5);self.assertEqual(r['candidates'][0]['matched_facets']['species'],['human']);self.assertFalse(r['searches'][0]['coverage_complete'])
    def test_update_failure_not_clean_bill(self):
        with patch.dict(sys.modules,{'literature_ext':types.SimpleNamespace(doi_metadata=Mock(side_effect=RuntimeError()))}):r=review.check_publication_updates(['10.1234/example'],True)
        self.assertEqual(r['records'][0]['state'],'query_failed')
    def test_text_revision_preserves_citation(self):
        r=collaboration.prepare_manuscript_revision(str(self.doc),[{'location':'line:3','old_text':'The effect was uncertain [@alpha].','new_text':'The estimated effect remained uncertain [@alpha].','reason':'clarify uncertainty'}],hashlib.sha256(self.doc.read_bytes()).hexdigest())
        self.assertIn('estimated',Path(r['output_directory'],'revised.md').read_text());self.assertNotIn('estimated',self.doc.read_text())
    def test_text_revision_citation_change_refused(self):
        with self.assertRaises(ValueError):collaboration.prepare_manuscript_revision(str(self.doc),[{'location':'line:3','old_text':'The effect was uncertain [@alpha].','new_text':'The effect was uncertain [@beta].','reason':'change'}],hashlib.sha256(self.doc.read_bytes()).hexdigest())
    def test_revision_stale_source_refused(self):
        with self.assertRaises(ValueError):collaboration.prepare_manuscript_revision(str(self.doc),[], '0'*64)
    def test_version_diff_citation_loss(self):
        after=self.write('after.md',self.doc.read_text().replace('[@alpha]',''))
        r=collaboration.compare_manuscript_versions(str(self.doc),after);self.assertFalse(r['citation_text_sequence_unchanged'])
    def make_docx(self,field=False):
        xml='<w:document xmlns:w="'+common.W+'"><w:body><w:p><w:r><w:t>Simple text</w:t></w:r></w:p>'
        if field:xml+='<w:p><w:r><w:instrText>ADDIN ZOTERO_ITEM CSL_CITATION {"citationItems":[]}</w:instrText></w:r><w:r><w:t>[1]</w:t></w:r></w:p>'
        xml+='</w:body></w:document>';p=self.root/'word.docx'
        with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml',xml);z.writestr('word/comments.xml','<w:comments xmlns:w="'+common.W+'"/>');z.writestr('customXml/item1.xml','<keep/>')
        return p
    def test_word_tracked_revision_preserves_other_parts_and_fields(self):
        p=self.make_docx(True);r=collaboration.prepare_manuscript_revision(str(p),[{'location':'paragraph:1','old_text':'Simple text','new_text':'Reviewed text','reason':'clarify'}],hashlib.sha256(p.read_bytes()).hexdigest())
        with zipfile.ZipFile(Path(r['output_directory'])/'revised.docx') as z:
            xml=z.read('word/document.xml');self.assertIn(b'<w:del ',xml);self.assertIn(b'<w:ins ',xml);self.assertIn(b'ADDIN ZOTERO_ITEM',xml);self.assertEqual(z.read('customXml/item1.xml'),b'<keep/>')
        self.assertEqual(common.manuscript(str(Path(r['output_directory'])/'revised.docx'))['segments'][0]['text'],'Reviewed text')
    def test_word_field_paragraph_refused(self):
        p=self.make_docx(True)
        with self.assertRaises(ValueError):collaboration.prepare_manuscript_revision(str(p),[{'location':'paragraph:2','old_text':'[1]','new_text':'[2]','reason':'edit'}],hashlib.sha256(p.read_bytes()).hexdigest())
    def test_word_field_spanning_paragraphs_protected(self):
        p=self.make_docx();parts=common.docx_parts(p.read_bytes())
        parts['word/document.xml']=('<w:document xmlns:w="'+common.W+'"><w:body><w:p><w:r><w:fldChar w:fldCharType="begin"/><w:instrText>ADDIN ZOTERO_BIBL</w:instrText><w:fldChar w:fldCharType="separate"/></w:r></w:p><w:p><w:r><w:t>Bibliography</w:t></w:r></w:p><w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:body></w:document>').encode()
        with zipfile.ZipFile(p,'w') as z:
            for name,raw in parts.items():z.writestr(name,raw)
        doc=common.manuscript(str(p));self.assertTrue(doc['segments'][1]['protected'])
    def test_word_split_citation_instruction_joined(self):
        p=self.make_docx();parts=common.docx_parts(p.read_bytes());xml=parts['word/document.xml'].decode().replace('<w:t>Simple text</w:t>','<w:fldChar w:fldCharType="begin"/><w:instrText>ADDIN ZOTERO_ITEM CSL_</w:instrText><w:instrText>CITATION {"citationItems":[]}</w:instrText><w:fldChar w:fldCharType="separate"/><w:t>[1]</w:t><w:fldChar w:fldCharType="end"/>')
        with zipfile.ZipFile(p,'w') as z:
            for name,raw in parts.items():z.writestr(name,xml.encode() if name=='word/document.xml' else raw)
        doc=common.manuscript(str(p));self.assertIn('CSL_CITATION',doc['fields_and_comments'][0]['instruction'])
    def test_draft_reviewed_without_evidence_refused(self):
        with self.assertRaises(ValueError):collaboration.build_evidence_draft('Title',[{'heading':'Results','paragraphs':[{'text':'Claim','state':'reviewed','reference_ids':['alpha']}]}],str(self.refs),[])
    def test_draft_unresolved_marker_and_map(self):
        r=collaboration.build_evidence_draft('Title',[{'heading':'Results','paragraphs':[{'text':'Claim','state':'unresolved','reference_ids':['alpha']}]}],str(self.refs),[])
        self.assertIn('待核验',Path(r['output_directory'],'manuscript.md').read_text(encoding='utf8'))
    def test_comment_cycle_refused(self):
        c=[{'id':'a','location':'line:3','comment':'a','depends_on':['b']},{'id':'b','location':'line:3','comment':'b','depends_on':['a']}]
        with self.assertRaises(ValueError):collaboration.manage_collaboration_review(str(self.doc),c)
    def test_completed_response_needs_real_location(self):
        with self.assertRaises(ValueError):collaboration.prepare_reviewer_response(str(self.doc),[{'id':'a','comment':'Please revise','response':'Done','state':'completed'}])
    def test_response_planned_is_labeled(self):
        r=collaboration.prepare_reviewer_response(str(self.doc),[{'id':'a','comment':'Analyze more','response':'Analysis planned','state':'planned','rationale':'Requires new allocation'}]);self.assertEqual(r['responses'][0]['state'],'planned')


class ZoteroProtocol(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patches=[patch.object(common,'HERE',self.root),patch.object(zotero,'HERE',self.root)]
        for p in self.patches:p.start()
        self.item={'key':'ABCDEFGH','version':2,'data':{'itemType':'journalArticle','title':'Study','tags':[]}}
    def tearDown(self):
        for p in self.patches:p.stop()
        self.temp.cleanup()
    def fake(self,status=200,changed=False,write_timeout=False):
        calls=[];outer=self;created={}
        class Response:
            status_code=status
            headers={'Zotero-Server-ID':'synthetic-instance','Zotero-API-Version':'3','Total-Results':'1'}
            def __init__(self,data,plain=False):self.data=data;self.plain=plain
            def iter_content(self,size):yield b'Zotero is running' if self.plain else json.dumps(self.data).encode()
            def close(self):pass
        class Session:
            trust_env=True
            def request(self,method,url,**kw):
                calls.append((method,url,kw,self.trust_env))
                if method=='PATCH':
                    if write_timeout:raise TimeoutError('synthetic timeout')
                    outer.item['data']['tags']=kw['json']['tags'];outer.item['version']+=1;return Response(None)
                if url.endswith('/local/authorize'):return Response({'key':'x'*32,'remember':False})
                if url.endswith('/items') and method=='POST':
                    created['NEWITEM1']={'key':'NEWITEM1','version':1,'data':kw['json'][0]}
                    return Response({'successful':{'0':{'key':'NEWITEM1'}},'failed':{}})
                if url.endswith('/items/NEWITEM1'):return Response(created['NEWITEM1'])
                if url.endswith('/items/ABCDEFGH'):
                    item=json.loads(json.dumps(outer.item))
                    if changed:item['version']+=1
                    return Response(item)
                if '/collections/' in url:return Response([outer.item])
                if url.endswith('/itemTypes'):return Response([{'itemType':'journalArticle'}])
                if url.endswith('/children'):return Response([])
                return Response({},plain=url.endswith('/api/'))
            def close(self):pass
        return types.SimpleNamespace(Session=Session),calls
    def test_read_requires_explicit_scope(self):
        with self.assertRaises(ValueError):zotero.read_zotero_library('user')
    def test_current_plain_text_handshake(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):r=zotero.inspect_zotero_connection()
        self.assertTrue(r['success']);self.assertTrue(r['instance_identity_available'])
    def test_local_read_no_redirect_or_environment_credentials(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):r=zotero.read_zotero_library('user',collection_key='COLLECT1')
        self.assertEqual(len(r['records']),1);self.assertTrue(all(url.startswith('http://localhost:') and not kw['allow_redirects'] and not env for _,url,kw,env in calls))
    def test_redirect_refused(self):
        fake,calls=self.fake(307)
        with patch.dict(sys.modules,{'requests':fake}):r=zotero.inspect_zotero_connection()
        self.assertFalse(r['success']);self.assertEqual(len(calls),1)
    def test_write_preview_needs_sync_ack(self):
        with self.assertRaises(ValueError):zotero.prepare_zotero_write('user',[])
    def plan(self):
        return zotero.prepare_zotero_write('user',[{'action':'add_tags','item_key':'ABCDEFGH','tags':['reviewed']}],True)
    def test_write_preview_does_not_authorize_or_mutate(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):r=self.plan()
        self.assertTrue(all(method=='GET' for method,*_ in calls));self.assertTrue(r['sync_acknowledged'])
    def test_fixed_payload_rejects_attachment_creation(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):
            plan=self.plan();p=Path(plan['output_directory'])/'review.json';d=json.loads(p.read_text());d['changes'][0]['payload']['url']='https://example.org/private';p.write_text(json.dumps(d))
            with self.assertRaises(ValueError):zotero.apply_zotero_write(str(p),hashlib.sha256(p.read_bytes()).hexdigest(),True)
        self.assertFalse(any(method=='PATCH' for method,*_ in calls))
    def test_write_auth_and_verified_tags_no_token_artifact(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):
            plan=self.plan();p=Path(plan['output_directory'])/'review.json';r=zotero.apply_zotero_write(str(p),hashlib.sha256(p.read_bytes()).hexdigest(),True)
        self.assertEqual(r['state'],'completed');self.assertEqual(self.item['data']['tags'],[{'tag':'reviewed'}])
        self.assertNotIn('x'*32,Path(r['dispatch_receipt']).read_text())
    def test_note_creation_escape_and_verified_readback(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):
            plan=zotero.prepare_zotero_write('user',[{'action':'add_note','item_key':'ABCDEFGH','text':'Reviewed <script>literal</script>\nNext line'}],True)
            p=Path(plan['output_directory'])/'review.json';r=zotero.apply_zotero_write(str(p),hashlib.sha256(p.read_bytes()).hexdigest(),True)
        self.assertEqual(r['state'],'completed');self.assertIn('&lt;script&gt;',r['outcomes'][0]['after']['data']['note'])
    def test_new_reference_creation_fixed_schema(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):
            plan=zotero.prepare_zotero_write('user',[{'action':'create_reference','reference':{'title':'Reviewed reference','doi':'10.1234/example','year':'2024','authors':['Study Group']}}],True)
            p=Path(plan['output_directory'])/'review.json';r=zotero.apply_zotero_write(str(p),hashlib.sha256(p.read_bytes()).hexdigest(),True)
        self.assertEqual(r['state'],'completed');self.assertEqual(r['outcomes'][0]['after']['data']['itemType'],'journalArticle')
    def test_changed_item_blocks_before_authorization(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}):plan=self.plan()
        p=Path(plan['output_directory'])/'review.json';fake,calls=self.fake(changed=True)
        with patch.dict(sys.modules,{'requests':fake}),self.assertRaises(ValueError):zotero.apply_zotero_write(str(p),hashlib.sha256(p.read_bytes()).hexdigest(),True)
        self.assertFalse(any('/authorize' in url for _,url,*_ in calls))
    def test_unknown_write_never_retried(self):
        fake,calls=self.fake(write_timeout=True)
        with patch.dict(sys.modules,{'requests':fake}):
            plan=self.plan();p=Path(plan['output_directory'])/'review.json';sha=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaises(TimeoutError):zotero.apply_zotero_write(str(p),sha,True)
            self.assertEqual(json.loads((p.parent/'dispatch_state.json').read_text())['state'],'write_outcome_unknown')
            with self.assertRaises(ValueError):zotero.apply_zotero_write(str(p),sha,True)
        self.assertEqual(sum(method=='PATCH' for method,*_ in calls),1)
    def test_remote_group_route_refused(self):
        with self.assertRaises(ValueError):zotero.read_zotero_library('https://remote.example',collection_key='COLLECT1')
