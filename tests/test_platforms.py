"""Portable installation paths and authenticated browser API checks."""
import http.client
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'bridge'))
import install
import web_gateway


class PlatformChecks(unittest.TestCase):
    def test_returned_data_integrity_and_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'fixture.json'
            raw = b'{"fixture":"public"}'
            path.write_bytes(raw)
            receipt = {'result_file':str(path),'sha256':hashlib.sha256(raw).hexdigest()}
            self.assertEqual(web_gateway.returned_result(receipt)['result'],{'fixture':'public'})
            with self.assertRaises(ValueError):
                web_gateway.returned_result({**receipt,'sha256':'incorrect'})
            path.write_bytes(b'x'*2000001)
            self.assertEqual(web_gateway.returned_result(receipt)['result_state'],'review_large_result_on_host')

    def test_runtime_paths_for_both_platform_families(self):
        root = Path('synthetic_install')
        self.assertEqual(install.runtime_python(root,False),root/'.venv_tools'/'bin'/'python')
        self.assertEqual(install.runtime_python(root,True),root/'.venv_tools'/'Scripts'/'python.exe')

    def test_portable_locks_do_not_require_win32_on_posix(self):
        for file in ('requirements-core.lock.txt','requirements-full.lock.txt'):
            lines = (ROOT/file).read_text().splitlines()
            self.assertTrue(all('sys_platform' in line for line in lines if line.startswith('pywin32')))

    def test_distribution_traversal_and_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'manifest.json').write_text(json.dumps({'files':[{'path':'../escape','sha256':'bad'}]}))
            with self.assertRaises(ValueError):
                install.validate_package(root)
            (root/'fixture.txt').write_text('fixture')
            (root/'manifest.json').write_text(json.dumps({'files':[{'path':'fixture.txt','sha256':'bad'}]}))
            with self.assertRaises(ValueError):
                install.validate_package(root)

    def test_private_token_generation_refuses_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'browser-token.txt'
            web_gateway.create_token(path)
            self.assertGreaterEqual(len(web_gateway.load_token(path)),32)
            with self.assertRaises(FileExistsError):
                web_gateway.create_token(path)
            if os.name!='nt':
                path.chmod(0o644)
                with self.assertRaises(ValueError):
                    web_gateway.load_token(path)

    def test_external_binding_requires_tls(self):
        web_gateway.require_tls('localhost',None,None)
        with self.assertRaises(ValueError):
            web_gateway.require_tls('gateway.example.invalid',None,None)
        with self.assertRaises(ValueError):
            web_gateway.require_tls('localhost','fixture-cert',None)

    def test_browser_api_auth_origin_and_payload_limits(self):
        token = 'synthetic-browser-token-'+'x'*40
        calls = []
        def dispatch(data):
            calls.append(data)
            return {'state':'synthetic_pass'}
        server = ThreadingHTTPServer(('localhost',0),web_gateway.handler(token,dispatch))
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            def request(headers,body='{}'):
                connection = http.client.HTTPConnection(server.server_address[0],server.server_port,timeout=5)
                connection.request('POST','/api',body,{**{'Content-Type':'application/json'},**headers})
                response = connection.getresponse()
                status,data = response.status,json.loads(response.read())
                connection.close()
                return status,data
            self.assertEqual(request({})[0],401)
            self.assertEqual(request({'Authorization':'Bearer incorrect'})[0],401)
            auth = {'Authorization':'Bearer '+token}
            self.assertEqual(request({**auth,'Origin':'https://untrusted.example.invalid'})[0],403)
            self.assertEqual(request(auth,'[]')[0],400)
            self.assertEqual(request({**auth,'Content-Length':str(web_gateway.MAX_BODY+1)},'')[0],413)
            status,data = request(auth,json.dumps({'operation':'status'}))
            self.assertEqual(status,200)
            self.assertEqual(data['state'],'synthetic_pass')
            self.assertEqual(calls,[{'operation':'status'}])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__=='__main__':
    unittest.main()
