"""Bounded transient HTTP evidence and no automatic write/connection retry; entirely offline."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))

class ReadOnlyHTTPChecks(unittest.TestCase):
    def transport(self,statuses):
        calls=[];sources=[];responses=[]
        class Response:
            def __init__(self,status):self.status_code=status;self.url='https://example.invalid/query';self.headers={};self.closed=False
            def iter_content(self,size):yield b'{}'
            def close(self):self.closed=True
        class Session:
            def __init__(self):self.trust_env=True;self.closed=False
            def request(self,method,*args,**kwargs):
                calls.append(method)
                if isinstance(statuses[len(calls)-1],Exception):raise statuses[len(calls)-1]
                r=Response(statuses[len(calls)-1]);responses.append(r);return r
            def close(self):self.closed=True
        session=Session()
        with patch.dict(sys.modules,{'requests':SimpleNamespace(Session=lambda:session)}):
            spec=importlib.util.spec_from_file_location('readonly_http_fixture',ROOT/'bridge/http_client.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module._public_url=lambda url:SimpleNamespace(hostname='example.invalid')
        module.trace_response=lambda r,raw:sources.append(r.status_code)
        module.time=SimpleNamespace(sleep=lambda seconds:None)
        return module,session,calls,sources,responses

    def test_transient_get_retains_failure_and_success_sources(self):
        m,session,calls,sources,responses=self.transport([500,503,200])
        with patch('privacy_ext.enforce_outbound'):
            raw,_=m.request('https://example.invalid/query')
        self.assertEqual(raw,b'{}');self.assertEqual(sources,[500,503,200]);self.assertEqual(calls,['GET']*3)
        self.assertFalse(session.trust_env);self.assertTrue(session.closed);self.assertTrue(all(r.closed for r in responses))

    def test_persistent_get_failure_is_bounded_and_not_passed(self):
        m,session,calls,sources,_=self.transport([500,500,500])
        with patch('privacy_ext.enforce_outbound'),self.assertRaises(RuntimeError):m.request('https://example.invalid/query')
        self.assertEqual(len(calls),3);self.assertEqual(sources,[500]*3);self.assertTrue(session.closed)

    def test_post_and_unknown_connection_are_never_retried(self):
        for method,status in [('POST',500),('GET',ConnectionError('synthetic unknown connection'))]:
            m,session,calls,_,_=self.transport([status])
            with patch('privacy_ext.enforce_outbound'),self.assertRaises((RuntimeError,ConnectionError)):
                m.request('https://example.invalid/query',method)
            self.assertEqual(len(calls),1);self.assertTrue(session.closed)

if __name__=='__main__':unittest.main()
