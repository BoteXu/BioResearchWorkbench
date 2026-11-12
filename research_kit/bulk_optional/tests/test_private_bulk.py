"""Synthetic contract/security checks, not biological or engine validation."""
import argparse
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addons'))
sys.path.insert(0,str(ROOT))
import bulk_optional_ext as addon
import install_private_addon as installer

def config():return json.loads((ROOT/'examples/config.template.json').read_text(encoding='utf8'))
def fixture(root,c=None,n=6,counts=False):
    c=c or config();samples=['sample'+str(i) for i in range(n)]
    lines=['gene_id,'+','.join(samples)]
    for g in range(30):
        v=[str(10+g%7+s+(g*s)%5) if counts else str(5+g*.01+s*.2+((g*s)%7)*.03) for s in range(n)]
        lines.append('gene'+str(g)+','+','.join(v))
    (root/'expression.csv').write_text('\n'.join(lines)+'\n',encoding='utf8')
    cols=['sample_id','condition','donor_id']+[v['name'] for v in c['covariates']]
    rows=[]
    for i,s in enumerate(samples):
        row=[s,c['control_label'] if i<n//2 else c['case_label'],'donor'+str(i%(n//2) if c['paired'] else i)]
        for v in c['covariates']:row.append(str(30+i%3*4+i//3) if v['type']=='numeric' else 'A' if i<n//2 else 'B')
        rows.append(row)
    (root/'metadata.csv').write_text(','.join(cols)+'\n'+'\n'.join(','.join(r) for r in rows)+'\n',encoding='utf8')
    return c

class Contracts(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.c=fixture(self.root)
    def tearDown(self):self.t.cleanup()
    def audit(self,c=None):return addon.audit_optional_bulk_inputs(c or self.c,str(self.root))
    def test_valid_normalized(self):
        r=self.audit();self.assertTrue(r['input_contract_pass']);self.assertEqual(r['residual_df'],4);self.assertFalse(r['formal_analysis_allowed']);self.assertEqual(r['genes'],30)
    def test_valid_raw_counts(self):
        self.c['matrix_kind']='raw_counts';fixture(self.root,self.c,counts=True);self.assertTrue(self.audit()['input_contract_pass'])
    def test_count_fraction_rejected(self):
        self.c['matrix_kind']='raw_counts'
        with self.assertRaises(ValueError):self.audit()
    def test_nonfinite_rejected(self):
        p=self.root/'expression.csv';p.write_text(p.read_text().replace('5.0,','nan,',1))
        with self.assertRaises(ValueError):self.audit()
    def test_duplicate_gene_rejected(self):
        p=self.root/'expression.csv';p.write_text(p.read_text().replace('gene1,','gene0,',1))
        with self.assertRaises(ValueError):self.audit()
    def test_duplicate_sample_rejected(self):
        p=self.root/'expression.csv';p.write_text(p.read_text().replace('sample1','sample0',1))
        with self.assertRaises(ValueError):self.audit()
    def test_exact_sample_sets(self):
        p=self.root/'metadata.csv';p.write_text(p.read_text().replace('sample5','other_sample',1))
        with self.assertRaises(ValueError):self.audit()
    def test_missing_covariate(self):
        self.c['covariates']=[{'name':'age','type':'numeric'}];self.c['study']['covariates']=['age']
        with self.assertRaises(ValueError):self.audit()
    def test_valid_numeric_design(self):
        self.c['covariates']=[{'name':'age','type':'numeric'}];self.c['study']['covariates']=['age'];fixture(self.root,self.c)
        self.assertTrue(self.audit()['input_contract_pass'])
    def test_confounded_design(self):
        self.c['covariates']=[{'name':'batch','type':'categorical'}];self.c['study']['covariates']=['batch'];fixture(self.root,self.c)
        with self.assertRaises(ValueError):self.audit()
    def test_technical_replicates_rejected(self):
        p=self.root/'metadata.csv';p.write_text(p.read_text().replace('donor1','donor0'))
        with self.assertRaises(ValueError):self.audit()
    def test_three_units_not_rows(self):
        fixture(self.root,self.c,n=4)
        with self.assertRaises(ValueError):self.audit()
    def test_complete_pairing(self):
        self.c['paired']=True;self.c['study']['repeated']=True;fixture(self.root,self.c,n=8)
        r=self.audit();self.assertTrue(r['input_contract_pass']);self.assertEqual(r['residual_df'],3)
    def test_incomplete_pairing(self):
        self.c['paired']=True;self.c['study']['repeated']=True;fixture(self.root,self.c,n=8)
        p=self.root/'metadata.csv';p.write_text(p.read_text().replace('sample7,Disease,donor3','sample7,Disease,other_donor'))
        with self.assertRaises(ValueError):self.audit()
    def test_unknown_stage_and_scale(self):
        for key,value in [('stages',['all']),('matrix_kind','TPM'),('orientation','auto')]:
            c=copy.deepcopy(self.c);c[key]=value;self.assertFalse(addon.audit_optional_bulk_configuration(c)['configuration_pass'])
    def test_missing_unit_declaration(self):
        del self.c['unit_col'];self.assertFalse(addon.audit_optional_bulk_configuration(self.c)['configuration_pass'])
    def test_unsafe_path(self):
        self.c['expr_matrix']='../expression.csv';self.assertFalse(addon.audit_optional_bulk_configuration(self.c)['configuration_pass'])
    def test_extra_defaults_rejected(self):
        for key,value in [('is_log2',False),('drop_samples',['sample1']),('shell_command','echo')]:
            c=copy.deepcopy(self.c);c[key]=value;self.assertFalse(addon.audit_optional_bulk_configuration(c)['configuration_pass'])
    def test_no_implicit_other_groups(self):
        p=self.root/'metadata.csv';p.write_text(p.read_text().replace('sample1,Control','sample1,Other'))
        with self.assertRaises(ValueError):self.audit()
    def test_input_bytes_bound(self):
        a=self.audit();p=self.root/'expression.csv';p.write_text(p.read_text().replace('5.0,','6.0,',1));b=self.audit()
        self.assertNotEqual(a['input_hashes']['matrix'],b['input_hashes']['matrix'])
    def test_plan_does_not_execute(self):
        c=copy.deepcopy(self.c);c['stages']=list(addon.STAGES)
        r=addon.plan_optional_bulk_workflow(c);self.assertEqual(len(r['steps']),13)
        for k in ['submission_performed','engine_execution_performed','network_requests_performed','formal_analysis_allowed']:self.assertFalse(r[k])
    def test_count_and_log_routes(self):
        for kind,route in [('raw_counts','transcriptomics.run_bulk_rnaseq'),('log2_normalized','transcriptomics.run_normalized_expression')]:
            c=copy.deepcopy(self.c);c['matrix_kind']=kind;r=addon.plan_optional_bulk_workflow(c);de=next(x for x in r['steps'] if x['stage']=='de');self.assertEqual(de['recommended_route'],route)
    def test_bounded_file_read(self):
        p=self.root/'expression.csv';p.write_text('a,b\n'+'x'*1000001)
        with self.assertRaises(ValueError):addon.audit_optional_bulk_inputs(self.c,str(self.root),1)
    def test_symlink_escape(self):
        link=self.root/'linked.csv'
        try:link.symlink_to(self.root/'expression.csv')
        except OSError:self.skipTest('Host does not allow symlink creation')
        self.c['expr_matrix']='linked.csv'
        with self.assertRaises(ValueError):self.audit()

class Returned(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.c=config();self.c['stages']=['qc'];self.h={'matrix':'a'*64,'metadata':'b'*64}
        (self.root/'result.csv').write_text('gene,effect\ngeneA,1\n');data=(self.root/'result.csv').read_bytes()
        self.r={'schema':'bulk-returned-v1','configuration_sha256':addon._object_hash(self.c),'input_hashes':self.h,'backend_versions':{'backend':'synthetic-contract-only'},'stages':{'qc':'succeeded'},'outputs':[{'path':'result.csv','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'stage':'qc'}]}
    def tearDown(self):self.t.cleanup()
    def audit(self):
        (self.root/'receipt.json').write_text(json.dumps(self.r));return addon.audit_optional_bulk_outputs(self.c,str(self.root),'receipt.json',self.h)
    def test_bound_returned_snapshot(self):
        r=self.audit();self.assertTrue(r['receipt_consistent']);self.assertFalse(r['scientific_validity_established']);self.assertFalse(r['live_server_observed'])
    def test_stale_configuration(self):self.r['configuration_sha256']='c'*64;self.assertFalse(self.audit()['receipt_consistent'])
    def test_stale_input(self):self.r['input_hashes']={'matrix':'c'*64,'metadata':'b'*64};self.assertFalse(self.audit()['receipt_consistent'])
    def test_tampered_output(self):
        (self.root/'result.csv').write_text('gene,effect\ngeneA,2\n');self.assertFalse(self.audit()['receipt_consistent'])
    def test_skipped_is_not_completed(self):self.r['stages']['qc']='skipped';self.assertFalse(self.audit()['receipt_consistent'])
    def test_missing_versions(self):self.r['backend_versions']={};self.assertFalse(self.audit()['receipt_consistent'])
    def test_output_traversal(self):self.r['outputs'][0]['path']='../result.csv';self.assertFalse(self.audit()['receipt_consistent'])
    def test_original_receipt_inadequate(self):self.r={'step':'qc','timestamp':'synthetic'};self.assertFalse(self.audit()['receipt_consistent'])
    def test_missing_output(self):self.r['outputs'][0]['path']='missing.csv';self.assertFalse(self.audit()['receipt_consistent'])

class Installer(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();r=Path(self.t.name);self.bridge=r/'bridge';self.skills=r/'skills';self.bridge.mkdir();self.skills.mkdir()
        (self.bridge/'extensions.py').write_text('EXPORTS = {\n}\n')
        (self.bridge/'bridge.py').write_text('def _source_manifest():\n    for name in ("cadd_ext.py"):\n        pass\n')
    def tearDown(self):self.t.cleanup()
    def test_dry_run_and_idempotent(self):
        r=installer.install(self.bridge,self.skills,True);self.assertEqual(r['state'],'dry_run');self.assertFalse((self.bridge/'bulk_optional_ext.py').exists())
        self.assertEqual(installer.install(self.bridge,self.skills)['state'],'installed');self.assertEqual(installer.install(self.bridge,self.skills)['state'],'already_current')
    def test_preserve_customization(self):
        installer.install(self.bridge,self.skills);p=self.skills/installer.SKILL/'SKILL.md';p.write_text('customized')
        old=(self.bridge/'extensions.py').read_bytes()
        with self.assertRaises(ValueError):installer.install(self.bridge,self.skills)
        self.assertEqual(p.read_text(),'customized');self.assertEqual(old,(self.bridge/'extensions.py').read_bytes())
    def test_unknown_lock_not_retried(self):
        lock=self.bridge/'.private-bulk-addon-install.lock';lock.write_text('unknown')
        with self.assertRaises(FileExistsError):installer.install(self.bridge,self.skills)
        self.assertEqual(lock.read_text(),'unknown')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--bridge-dir',required=True);a,rest=ap.parse_known_args();sys.path.insert(0,str(Path(a.bridge_dir).resolve()));unittest.main(argv=[sys.argv[0],*rest])
