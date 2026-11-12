"""Frozen-table contract fixtures, never real backend completion evidence."""
from pathlib import Path
import os,sys,json,tempfile,unittest,hashlib
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'scientific-visualization'
os.environ['MPLBACKEND']='Agg';sys.dont_write_bytecode=True;sys.path.insert(0,str(S/'scripts'))
from native_figures import _binding
from analysis_results import render_result

def fixture(root,content,views=None):
    p=root/'frozen.tsv';p.write_text(content,encoding='utf8')
    plan={'test_fixture':'NOT_A_NATIVE_RUN','schema':'frozen-display-consumer-fixture/1','state':'READY_FOR_DISPLAY_REVIEW','backend':'contract_fixture','route':{'allowed_views':views or ['matrix','scatter','interval','rank','curve','edges','volcano','proportions'],'kind':'contract_fixture_only','interpretation_boundary':'no scientific result is claimed'},'output_root':str(root),'request_sha256':'NOT_A_REQUEST','receipt_sha256':'NOT_A_RECEIPT','selected':{'result':[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}]}}
    plan['binding_sha256']=_binding(plan);return plan

class ResultConsumerContracts(unittest.TestCase):
    def test_71_policies_match_exact_analysis_ids(self):
        p=json.loads((S/'assets/analysis71_routes.json').read_text(encoding='utf8'));r=json.loads((ROOT/'workflow_integration/server/branches71.json').read_text(encoding='utf8'));self.assertEqual(set(p['methods']),set(r));self.assertEqual(len(p['methods']),71)
    def test_no_new_template_duplicates(self):
        d=json.loads((S/'assets/figure_catalog.json').read_text(encoding='utf8'));self.assertEqual(d['counts'],{'figures':140,'modules':22,'composites':7});self.assertEqual(len({r['id'] for r in d['figures']}),140)
    def test_actual_x_units_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'id\tx\ty\na\t1\t2\n')
            with self.assertRaises(ValueError):render_result(p,'result','scatter',{'id':'id','x':'x','y':'y'},unit='y quantity')
    def test_incomplete_intervals_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'id\te\tlo\na\t1\t0\n')
            with self.assertRaises(ValueError):render_result(p,'result','interval',{'id':'id','estimate':'e','lo':'lo'},unit='effect')
    def test_interval_coverage_never_invented(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'id\te\tlo\thi\na\t1\t0\t2\n')
            with self.assertRaises(ValueError):render_result(p,'result','interval',{'id':'id','estimate':'e','lo':'lo','hi':'hi'},unit='effect')
    def test_probabilities_not_silently_renormalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'id\ta\tb\nrow\t.2\t.7\n')
            with self.assertRaises(ValueError):render_result(p,'result','proportions',{'index':'id','values':['a','b']},unit='probability')
    def test_duplicate_curve_x_not_joined_into_a_trajectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'trace\tt\ty\na\t1\t2\na\t1\t3\n')
            with self.assertRaises(ValueError):render_result(p,'result','curve',{'series':'trace','x':'t','y':'y'},unit='actual y',xunit='actual t')
    def test_source_hash_change_invalidates_display(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=fixture(root,'id\tx\ty\na\t1\t2\n');(root/'frozen.tsv').write_text('id\tx\ty\na\t1\t3\n')
            with self.assertRaises(ValueError):render_result(p,'result','scatter',{'id':'id','x':'x','y':'y'},unit='y',xunit='x')
    def test_raw_posterior_cannot_be_called_FDR(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'id\tx\tq\na\t1\t.7\n')
            with self.assertRaises(ValueError):render_result(p,'result','volcano',{'id':'id','effect':'x','q':'q'},unit='effect',probability_meaning='posterior_probability',thresholds={'effect':1,'q':.05,'basis':'fixture'})
    def test_matrix_does_not_refit_clustering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'id\tx\ty\na\t1\t2\n')
            with self.assertRaises(ValueError):render_result(p,'result','matrix',{'index':'id','values':['x','y']},unit='frozen units',cluster=True)
    def test_signed_edges_never_absolute_value_chord(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(Path(tmp),'s\tt\tw\na\tb\t-.5\n')
            with self.assertRaises(ValueError):render_result(p,'result','edges',{'source':'s','target':'t','weight':'w'},unit='signed association')
    def test_identity_annotation_aligns_by_id_not_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=fixture(root,'set\tS01\tS02\nA\t1\t2\n');ann=root/'meta.tsv';ann.write_text('sample\tcondition\nS02\tTreated\nS01\tControl\n')
            p['selected']['metadata']=[{'path':ann.name,'sha256':hashlib.sha256(ann.read_bytes()).hexdigest(),'bytes':ann.stat().st_size}];p['binding_sha256']=_binding({k:v for k,v in p.items() if k!='binding_sha256'})
            with patch('renderers.render_template',return_value=(object(),{})) as render:
                render_result(p,'result','matrix',{'index':'set','values':['S01','S02']},unit='frozen scores',annotations={'role':'metadata','path':ann.name,'id':'sample','group':'condition'})
                self.assertEqual(render.call_args.args[1]['groups'],['Control','Treated'])
    def test_missing_annotation_is_not_inferred_from_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=fixture(root,'set\tS01_Treat\nA\t1\n');ann=root/'meta.tsv';ann.write_text('sample\tcondition\nS01\tControl\n');p['selected']['metadata']=[{'path':ann.name,'sha256':hashlib.sha256(ann.read_bytes()).hexdigest(),'bytes':ann.stat().st_size}];p['binding_sha256']=_binding({k:v for k,v in p.items() if k!='binding_sha256'})
            with self.assertRaises(ValueError):render_result(p,'result','matrix',{'index':'set','values':['S01_Treat']},unit='score',annotations={'role':'metadata','path':ann.name,'id':'sample','group':'condition'})
    def test_row_z_label_is_caller_explicit_and_values_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=fixture(root,'id\tS01\tS02\nA\t-1\t1\n')
            with patch('renderers.render_template',return_value=(object(),{})) as render:
                _,meta=render_result(p,'result','matrix',{'index':'id','values':['S01','S02']},unit='Row Z of frozen ssGSEA scores')
                self.assertEqual(render.call_args.args[1]['matrix'].to_numpy().tolist(),[[-1,1]]);self.assertEqual(meta['units'],'Row Z of frozen ssGSEA scores')

if __name__=='__main__':unittest.main()
