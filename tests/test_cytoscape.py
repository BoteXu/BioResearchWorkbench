import sys, types, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import software_ext

class CyRESTBoundary(unittest.TestCase):
    def fake(self,status=200,png=b'\x89PNG\r\n\x1a\nfixture'):
        calls=[]
        class Response:
            status_code=status
            def raise_for_status(self): pass
            def json(self): return {}
            def iter_content(self,n): yield png
            def close(self): pass
        class Session:
            trust_env=True
            def get(self,url,**kwargs):
                calls.append((url,kwargs,self.trust_env));return Response()
            def close(self): pass
        return types.SimpleNamespace(Session=Session,RequestException=RuntimeError),calls
    def test_local_redirect_stops_before_export(self):
        fake,calls=self.fake(307)
        with patch.dict(sys.modules,{'requests':fake}),self.assertRaises(ValueError):
            software_ext.cytoscape_render_network(123,'grid')
        self.assertEqual(len(calls),1)
        self.assertFalse(calls[0][1]['allow_redirects']);self.assertFalse(calls[0][2])
    def test_export_routes_and_png_gate(self):
        fake,calls=self.fake(png=b'not a PNG')
        with patch.dict(sys.modules,{'requests':fake}),self.assertRaises(ValueError):
            software_ext.cytoscape_render_network(123,'grid','Reviewed Style')
        self.assertEqual(len(calls),3)
        self.assertTrue(all(url.startswith('http://localhost:') and not kw['allow_redirects'] and not env for url,kw,env in calls))
        self.assertTrue(calls[-1][0].endswith('/networks/123/views/first.png'))
    def test_layout_path_injection_rejected(self):
        fake,calls=self.fake()
        with patch.dict(sys.modules,{'requests':fake}),self.assertRaises(ValueError):
            software_ext.cytoscape_render_network(123,'../networks')
        self.assertEqual(calls,[])
