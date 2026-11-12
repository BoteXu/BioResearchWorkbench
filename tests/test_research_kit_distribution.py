"""Publication/upgrade boundaries only; do not import or run research engines."""
from pathlib import Path
import json,tempfile,unittest
import audit_release,upgrade

ROOT=Path(__file__).resolve().parents[1]
class ResearchSourceDistribution(unittest.TestCase):
    def test_upgrade_maps_public_sources_and_preserves_private_configuration(self):
        names=['research_kit/module/server/worker.py','research_kit/module/deployment.template.json','research_kit/module/deployment.local.json','research_kit/module/software_registry.json','research_kit/module/results/result.json']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'manifest.json').write_text(json.dumps({'files':[{'path':n,'sha256':'a'*64} for n in names]}),encoding='utf8')
            _,mapping=upgrade._mapping(root)
            self.assertEqual(set(mapping),set(names[:2]))
    def test_original_attachment_fingerprints_and_saved_skill_id_are_not_published(self):
        policy=json.loads((ROOT/'research_kit/workflow_integration/teaching_policy.json').read_text(encoding='utf8'))
        self.assertIsNone(policy['source_deck_sha256']);self.assertIsNone(policy['source_script_sha256'])
        text=(ROOT/'research_kit/scientific-visualization/SKILL.md').read_text(encoding='utf8')
        self.assertNotIn('\nid:',text);self.assertIn('name: "scientific-visualization"',text)
    def test_licensed_binary_scope_is_exact_and_does_not_weaken_text_privacy(self):
        assets=audit_release.licensed_fonts(ROOT)
        self.assertEqual(len(assets),4)
        self.assertTrue(all(name.endswith('.ttf') for name in assets))
        header='-----BEGIN '+'PRIVATE KEY-----'
        self.assertIn('private_key',audit_release.scan_text(header))
    def test_manifest_member_is_distinct_from_a_private_absolute_path(self):
        member='/'.join(['research_kit','example','project','input.template.json'])
        relative={'files':[{'path':member,'sha256':'a'*64}]}
        self.assertNotIn('home_or_server_path',audit_release.scan_text(json.dumps(relative)))
        relative['files'][0]['path']='/'+'home'+'/private-user/input.json'
        self.assertIn('home_or_server_path',audit_release.scan_text(json.dumps(relative)))

if __name__=='__main__':unittest.main()
