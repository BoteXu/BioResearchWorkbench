"""Exact source-context/host/input metadata checks; no scientific data or engines."""
from pathlib import Path
import sys,tempfile,unittest,copy,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import read,write,sha,digest,sources
from postanalysis_acceptance import _origin,CONSISTENT

class OriginLineage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'primary').mkdir();self.prefix='primary/'
        context={'frame_id':'SYNTHETIC_FRAME','private_only':True};write(self.root/'source_context.private.json',context)
        r=read(ROOT/'examples/shepherd2_generate.project.example.json');r.update(example_only=False,source_sha256=sources())
        for x in r['inputs']:
            if x['id']=='context':x['sha256']=sha(self.root/'source_context.private.json')
        r['plan_sha256']=digest(r);path=self.root/'primary/origin_request_snapshot.private.json';write(path,r)
        contract=self.root/'primary/origin_generation_contract_snapshot.private.json';write(contract,{'scope':'FORMAT_FIXTURE_ONLY'})
        rc={'plan_sha256':r['plan_sha256'],'request_sha256':sha(path),'state':'COMPLETED','exit_code':0,'method':r['method'],'run_id':r['run_id'],'host':r['expected_host'],'source_sha256':r['source_sha256'],'inputs':copy.deepcopy(r['inputs']),'public_upload':False,'outputs':[{'path':'primary/generation_contract.private.json','sha256':sha(contract),'bytes':contract.stat().st_size}]}
        write(self.root/'primary/origin_receipt_snapshot.private.json',rc)
        self.spec={'origin_request_sha256':sha(path),'origin_receipt_sha256':sha(self.root/'primary/origin_receipt_snapshot.private.json'),'origin_variant':'primary'}
        self.content={self.prefix+'origin_request_snapshot.private.json':r,self.prefix+'origin_receipt_snapshot.private.json':rc,self.prefix+'origin_lineage.private.json':{'lineage_spec':self.spec,'source_review':{'state':CONSISTENT,'issues':[]},'frame_id':'SYNTHETIC_FRAME'},'source_context.private.json':context}
    def tearDown(self):self.temp.cleanup()
    def review(self):return _origin('primary',self.content,self.root,self.spec)[0]
    def test_exact_source_metadata_does_not_establish_scientific_validity(self):self.assertEqual(self.review(),[])
    def test_same_frame_label_cannot_hide_changed_protonation_context(self):
        f=self.root/'source_context.private.json';value=read(f);value['pH']=2.0;f.write_text(json.dumps(value),encoding='utf8')
        self.assertIn('postanalysis_context_does_not_match_exact_origin_context',self.review())
    def test_historical_or_other_host_receipt_cannot_replace_origin(self):
        self.content[self.prefix+'origin_receipt_snapshot.private.json']['host']='OTHER_SYNTHETIC_HOST'
        self.assertIn('origin_run_host_or_source_identity_changed',self.review())
    def test_actual_origin_inputs_require_full_denominator(self):
        self.content[self.prefix+'origin_receipt_snapshot.private.json']['inputs'].pop()
        self.assertIn('origin_actual_input_denominator_changed',self.review())
    def test_origin_source_inventory_must_match_exact_generation_request(self):
        self.content[self.prefix+'origin_receipt_snapshot.private.json']['source_sha256']={}
        self.assertIn('origin_run_host_or_source_identity_changed',self.review())
