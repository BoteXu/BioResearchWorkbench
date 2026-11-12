"""Behavioral acceptance of frozen graphics; no scientific fitting or optional engines."""
import unittest,sys,copy,tempfile,json,xml.etree.ElementTree as ET,ast
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import validate,digest,KINDS
from examples import example
from display import render_svg,color
from native_tracks import native_plan
from audits import palette_audit,inspect

class FrozenGraphics(unittest.TestCase):
    def test_all_sizes_preserve_values_and_identities(self):
        for kind in KINDS:
            for size in ('small','medium','large'):
                with self.subTest(kind=kind,size=size):
                    s=example(kind,size);before=digest(s);pages=render_svg(s,Path('.'))
                    self.assertEqual(before,digest(s));self.assertTrue(pages)
                    for p in pages:
                        root=ET.fromstring(p['svg']);self.assertEqual(root.attrib['role'],'img');self.assertGreater(p['height_mm'],30)
                    if kind=='heatmap':self.assertEqual([c for p in pages for q in p['panels'] for c in q['column_ids']],s['data']['columns'])
                    if kind=='oncoprint':self.assertEqual([c for p in pages for q in p['panels'] for c in q['object_ids']],s['data']['samples'])
    def test_multi_events_and_unassayed_remain_distinct(self):
        s=example('oncoprint');p=render_svg(s,Path('.'))[0]['svg']
        self.assertIn('Not assayed',p);self.assertIn('not TMB',p);self.assertNotIn('B_cell',p)
        self.assertTrue(any(len(r['events'])>1 for r in s['data']['cells']))
        self.assertNotIn('url(#missing)',p)
    def test_no_silent_clipping_missingness_or_partial_grid(self):
        for kind,mutate in [
            ('heatmap',lambda s:s['data']['values'][0].__setitem__(1,99)),
            ('markers',lambda s:s['data']['summaries'].pop()),
            ('markers',lambda s:s['data']['summaries'][0].__setitem__('n_objects',1)),
            ('oncoprint',lambda s:s['data']['cells'].pop()),
            ('heatmap',lambda s:s['data']['tree'].__setitem__('leaf_order',list(reversed(s['data']['rows'])))),
            ('markers',lambda s:s['data']['objects'][0].__setitem__('x',True)),
            ('genome',lambda s:s['data']['tracks'][3]['records'][0].__setitem__('lane',-1))]:
            with self.subTest(kind=kind):
                s=example(kind);mutate(s)
                with self.assertRaises(ValueError):validate(s)
        s=example('spatial');s['data']['sections'][0]['objects'][0]['radius']=100
        with self.assertRaises(ValueError):render_svg(s,Path('.'))
    def test_layout_width_height_capacity_and_long_labels(self):
        s=example('markers','large');s['layout'].update(columns=1,page_panels=2,width_mm=160)
        a=render_svg(s,Path('.'));self.assertGreater(len(a),3)
        s['layout']['height_mm']=30
        with self.assertRaises(ValueError):render_svg(s,Path('.'))
        s=example('heatmap');s['data']['row_labels']={r:'Long biological annotation '+r+' for wrapped labels' for r in s['data']['rows']}
        self.assertIn('biological',render_svg(s,Path('.'))[0]['svg'])
        s['layout']['panel_width_mm']=300
        with self.assertRaises(ValueError):render_svg(s,Path('.'))
        s=example('spatial');s['layout'].update(columns=2,rows=1,page_panels=3)
        with self.assertRaises(ValueError):render_svg(s,Path('.'))
    def test_custom_display_labels_and_adaptive_gene_lanes(self):
        s=example('oncoprint');s['data']['sample_labels']={r:'ID_'+r for r in s['data']['samples']}
        self.assertIn('ID_S01',render_svg(s,Path('.'))[0]['svg'])
        s=example('genome');s['data']['tracks'][3]['records'][1]['lane']=4
        self.assertIn('GENE_B',render_svg(s,Path('.'))[0]['svg'])
    def test_signed_scales_and_role_specific_failure(self):
        self.assertNotEqual(color(-1,[-2,2],0),color(1,[-2,2],0))
        s=example('circos');self.assertEqual(s['data']['tracks'][0]['center'],0)
        result=palette_audit(example('palette')['data']);self.assertEqual(next(r['decision'] for r in result['colors'] if r['name']=='Faint annotation'),'CONTRAST_REVIEW')
    def test_native_plans_real_code_and_coordinate_conversion(self):
        with tempfile.TemporaryDirectory() as td:
            s=example('genome');s['data']['tracks']=s['data']['tracks'][:4];r=native_plan(s,Path(td)/'gviz','Gviz')
            code=(Path(td)/'gviz/native_tracks.R').read_text()
            self.assertIn('GeneRegionTrack',code);self.assertIn('start=d$start+1',code)
            self.assertFalse(r['dispatch_authorized']);self.assertEqual(r['native_backend_runtime'],'NOT_RUN_SERVER_UNAVAILABLE')
            s=example('genome');types=['bigwig','bigwig','bed','gtf','links','hic_matrix'];assets=[{'track_id':t['id'],'path':f'assets/t{i}.dat','sha256':'1'*64,'file_type':types[i]} for i,t in enumerate(s['data']['tracks'])]
            r=native_plan(s,Path(td)/'pygt','pyGenomeTracks',assets);self.assertEqual(len(r['argv']),9)
            self.assertIn('[x-axis]',(Path(td)/'pygt/tracks.ini').read_text())
    def test_remote_guards_before_optional_imports(self):
        from server.anndata_snapshot import guard
        with self.assertRaises(RuntimeError):guard({'dispatch_authorized':False})
        source=(Path(__file__).resolve().parents[1]/'server/anndata_snapshot.py').read_text()
        self.assertLess(source.index('guard(p);'),source.index('    import anndata'))
    def test_native_config_injection_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            s=example('genome');s['data']['tracks'][0]['label']='bad\n[exec]'
            with self.assertRaises(ValueError):native_plan(s,Path(td)/'bad','Gviz')
    def test_interactive_exact_ids_and_offline_semantics(self):
        from interactive import viewer
        s=example('interactive');svg=render_svg(s,Path('.'))[0]['svg'];h=viewer(svg,s,digest(s))
        for value in ('connect-src','keydown','selected_ids','source_sha256','Cell_001','Blob','crypto.subtle'):
            self.assertIn(value,h)
        self.assertNotIn('https://',h)
    def test_svg_audit_and_entities(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'f.svg';f.write_text(render_svg(example('heatmap'),Path('.'))[0]['svg'],encoding='utf8')
            self.assertTrue(inspect(f)['has_description'])
            f.write_text('<!DOCTYPE x><svg/>')
            with self.assertRaises(ValueError):inspect(f)
    def test_no_local_science_imports(self):
        root=Path(__file__).resolve().parents[1]
        for f in root.glob('*.py'):
            names=[]
            for node in ast.walk(ast.parse(f.read_text(encoding='utf8'))):
                if isinstance(node,ast.Import):names.extend(n.name.split('.')[0] for n in node.names)
                elif isinstance(node,ast.ImportFrom):names.append((node.module or '').split('.')[0])
            self.assertFalse(set(names)&{'numpy','scipy','pandas','scanpy','anndata','sklearn','torch','seaborn','matplotlib'},str(f))

if __name__=='__main__':unittest.main(verbosity=2)
