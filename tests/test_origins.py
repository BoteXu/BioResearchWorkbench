"""Distribution provenance and public compatibility contracts."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import client_config
import bootstrap_upstream


class OriginChecks(unittest.TestCase):
    def test_declared_foundation_matches_fetched_revision(self):
        data=json.loads((ROOT/'third_party_components.json').read_text(encoding='utf8'))
        upstream=next(c for c in data['components'] if c['name']=='Biomni')
        self.assertEqual(data['initial_foundation'],'Biomni')
        self.assertEqual(upstream['revision'],bootstrap_upstream.COMMIT)
        self.assertEqual(upstream['use'],'fetched_upstream_source')
        self.assertIn(bootstrap_upstream.COMMIT,upstream['license_reference'])

    def test_requirement_declarations_have_source_attribution(self):
        data=json.loads((ROOT/'third_party_components.json').read_text(encoding='utf8'))
        packages={c['name']:c for c in data['components'] if c['use']=='separately_installed_python_dependency'}
        for file in ROOT.glob('requirements*.txt'):
            for line in file.read_text(encoding='utf8').splitlines():
                match=re.match(r'([A-Za-z0-9_.-]+)==',line)
                if match:
                    self.assertIn(file.name,packages[match.group(1)]['version_references'])
        self.assertTrue(all('not relicensed' in c['license_status'] for c in packages.values()))

    def test_old_and_new_registration_names_remain_explicitly_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); runtime=root/'.venv_tools'/('Scripts' if sys.platform=='win32' else 'bin')
            runtime.mkdir(parents=True)
            (runtime/('python.exe' if sys.platform=='win32' else 'python')).touch()
            (root/'.local').mkdir();(root/'.local'/'mcp_server.py').touch()
            for name in ['biomni','biomni-local','bioresearch','bioresearch-local']:
                files=client_config.generate(root,root/name,server_name=name)
                self.assertEqual(set(json.loads(files['portable.mcp.json'])['mcpServers']),{name})
            files=client_config.generate(root,root/'default')
            self.assertEqual(set(json.loads(files['portable.mcp.json'])['mcpServers']),{'bioresearch'})


if __name__=='__main__':unittest.main()
