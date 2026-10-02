"""Synthetic checks only; no patient data, server account or model credentials."""
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'bridge'))
import audit_release
import client_config
from workflow_ext import audit_result_table, audit_sample_metadata, prepare_remote_task


class CoreChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_independent_units_and_duplicate_observations(self):
        file = self.root/'samples.csv'
        file.write_text('sample,unit,condition\na,1,case\nb,2,case\nc,3,case\nd,4,control\ne,5,control\nf,6,control\n',encoding='utf8')
        args = dict(path=str(file),sample_key='sample',unit_key='unit',condition_key='condition',case='case',control='control')
        self.assertTrue(audit_sample_metadata(**args)['input_gate_pass'])
        file.write_text(file.read_text()+'g,1,case\n',encoding='utf8')
        self.assertFalse(audit_sample_metadata(**args)['input_gate_pass'])

    def test_empty_unit_cannot_increase_replicate_count(self):
        file = self.root/'samples.csv'
        file.write_text('sample,unit,condition\na,1,case\nb,2,case\nc,,case\nd,4,control\ne,5,control\nf,6,control\n',encoding='utf8')
        result = audit_sample_metadata(str(file),'sample','unit','condition','case','control')
        self.assertEqual(result['independent_units']['case'],2)
        self.assertFalse(result['input_gate_pass'])

    def test_results_bounds_missing_and_duplicates(self):
        file = self.root/'result.csv'
        mapping = {'feature':'id','effect':'b','p':'p','q':'q'}
        file.write_text('id,b,p,q\nexample,0.2,0.05,0.1\n',encoding='utf8')
        result = audit_result_table(str(file),'differential',mapping,{})
        self.assertTrue(result['table_format_pass'])
        self.assertFalse(result['review_context_complete'])
        self.assertEqual(result['scientific_validity'],'not_established')
        file.write_text('id,b,p,q\nexample,inf,1.5,0.1\nexample,NA,0.2,NA\n',encoding='utf8')
        result = audit_result_table(str(file),'differential',mapping,{})
        self.assertFalse(result['table_format_pass'])
        self.assertTrue(result['warnings'])

    def test_all_result_schemas(self):
        file = self.root/'result.csv'
        file.write_text('id,b,se,p,pp,n,i2\nexample,0.2,0.1,0.05,0.8,3,20\n',encoding='utf8')
        schemas = {'mr':{'feature':'id','effect':'b','se':'se','p':'p'},'coloc':{'feature':'id','pp_h4':'pp'},'meta':{'feature':'id','effect':'b','se':'se','p':'p','studies':'n','i2':'i2'},'image':{'feature':'id','measurement':'b'}}
        for mode, mapping in schemas.items():
            with self.subTest(mode=mode):
                self.assertTrue(audit_result_table(str(file),mode,mapping,{})['table_format_pass'])

    def test_bad_csv_width_and_duplicate_headers(self):
        file = self.root/'bad.csv'
        for text in ['id,b,p,q\nx,1,2\n','id,b,p,p\nx,1,0.2,0.3\n']:
            file.write_text(text,encoding='utf8')
            with self.assertRaises(ValueError):
                audit_result_table(str(file),'differential',{'feature':'id','effect':'b','p':'p','q':'q'},{})

    def test_client_formats_and_no_overwrite(self):
        runtime = self.root/'.venv_tools'/('Scripts' if os.name=='nt' else 'bin')
        runtime.mkdir(parents=True)
        (runtime/('python.exe' if os.name=='nt' else 'python')).write_text('fixture')
        server = self.root/'.local'
        server.mkdir()
        (server/'mcp_server.py').write_text('fixture')
        configs = client_config.generate(self.root,self.root/'client_configs')
        portable = json.loads(configs['portable.mcp.json'])
        vscode = json.loads(configs['vscode.mcp.json'])
        codex = tomllib.loads(configs['codex.config.toml'])
        self.assertEqual(portable['mcpServers']['biomni']['command'],vscode['servers']['biomni']['command'])
        self.assertEqual(codex['mcp_servers']['biomni']['env'],{'PYTHONUTF8':'1'})
        with self.assertRaises(ValueError):
            client_config.generate(self.root,self.root/'client_configs')

    def test_privacy_patterns_do_not_echo_values(self):
        fake_key = 'ghp_' + 'a'*40
        fake_path = '/home/' + 'example/private'
        self.assertIn('credential_token',audit_release.scan_text(fake_key))
        self.assertIn('home_or_server_path',audit_release.scan_text(fake_path))
        self.assertIn('private_deny_term',audit_release.scan_text('synthetic individual',['synthetic individual']))
        self.assertFalse(audit_release.scan_text('Project Contributors <contributors@example.invalid>'))

    def test_private_runtime_files_rejected(self):
        folder = self.root/'client_configs'
        folder.mkdir()
        (folder/'config.json').write_text('{}')
        result = audit_release.review(self.root)
        self.assertFalse(result['pass'])
        self.assertEqual(result['privacy_findings'][0]['category'],'runtime_or_sensitive_file')

    def test_prepare_is_not_submission(self):
        result = prepare_remote_task(['python3','analysis.py'],'/work','server.invalid',['new-result.csv'],dict(species='synthetic',model='fixture',assay='fixture',biological_unit='fixture',contrast='fixture',limitations=['Synthetic fixture']))
        self.assertEqual(result['state'],'prepared_not_submitted')
        with self.assertRaises(ValueError):
            prepare_remote_task(['python3'],'/work','server.invalid',['../escape'],dict(species='synthetic',model='fixture',assay='fixture',biological_unit='fixture',contrast='fixture',limitations=['Synthetic fixture']))

    def test_portable_runner_rejects_stale_outputs(self):
        (self.root/'already.txt').write_text('old fixture')
        request = self.root/'task.json'
        request.write_text(json.dumps({'task_id':'fixture','expected_host':socket.gethostname(),'remote_workdir':str(self.root),'argv':[sys.executable,'-c','pass'],'expected_outputs':['already.txt']}),encoding='utf8')
        process = subprocess.run([sys.executable,str(ROOT/'bridge'/'remote_runner.py'),str(request)],capture_output=True,timeout=20)
        self.assertNotEqual(process.returncode,0)
        receipt = json.loads((self.root/'remote_receipt.json').read_text())
        self.assertIn('already exists',receipt['error'])


if __name__ == '__main__':
    unittest.main()
