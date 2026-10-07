import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'bridge'))
import evidence as e
import extensions
import generate_catalog
import upgrade

class PlatformEvolutionTests(unittest.TestCase):
    def test_health_success_failure_and_source_config_expiration(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'HERE',Path(tmp)),patch.object(e,'distributions',return_value=[]):
            root=Path(tmp);(root/'fixture.py').write_text('v1');context=e.validation_context()
            with patch.object(e,'_PROCESS_SOURCE',context['source']),patch.object(e,'_PROCESS_DEPENDENCIES',context['dependencies']):
                e.observe('tool',True,'synthetic');self.assertTrue(e.health('tool')['current_environment_verified'])
                e.observe('tool',False,'synthetic','failure');r=e.health('tool');self.assertEqual(r['runtime_state'],'failed');self.assertTrue(r['historical_success']);self.assertFalse(r['last_attempt_success'])
                e.observe('tool',True,'synthetic');(root/'config.json').write_text('{}');r=e.health('tool');self.assertEqual(r['runtime_state'],'expired');self.assertIn('configuration',r['expired_dimensions'])
                (root/'fixture.py').write_text('v2');e.observe('tool',True,'synthetic');self.assertFalse(e.health('tool')['current_environment_verified'])
    def test_dependency_and_interpreter_changes_invalidate(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'HERE',Path(tmp)),patch.object(e,'distributions',return_value=[]):
            context=e.validation_context()
            with patch.object(e,'_PROCESS_SOURCE',context['source']),patch.object(e,'_PROCESS_DEPENDENCIES',context['dependencies']):e.observe('tool',True,'synthetic')
            for key in ['dependencies','executables','interpreter','routing']:
                changed={**context,key:'changed'}
                self.assertEqual(e.health('tool',changed)['runtime_state'],'expired')
    def test_legacy_pass_requires_revalidation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'HERE',Path(tmp)),patch.object(e,'distributions',return_value=[]):
            with e.connection() as conn:conn.execute('INSERT INTO observations VALUES(?,?,?,?,?)',('legacy',1,'fixture','fixture',None))
            r=e.health('legacy');self.assertTrue(r['historical_success']);self.assertEqual(r['runtime_state'],'expired')
    def test_lazy_scoped_modules_do_not_import_unselected_sources(self):
        with patch.dict(os.environ,{'BIOMNI_MODULES':'literature,molecular_biology'}),patch.object(extensions.importlib,'import_module',side_effect=AssertionError('eager import')):
            r=extensions.registry();self.assertIn(('molecular_biology','audit_splicing_results'),r);self.assertNotIn(('clinical_research','audit_clinical_dataset'),r)
        with patch.dict(os.environ,{'BIOMNI_MODULES':'unknown'}):
            with self.assertRaises(ValueError):extensions.registry()
    def package(self,root,version,code):
        root.mkdir();(root/'bridge').mkdir();(root/'bridge/fixture.py').write_text(code)
        (root/'skills/biomni-fixture').mkdir(parents=True);(root/'skills/biomni-fixture/SKILL.md').write_text('original workflow')
        (root/'requirements-core.lock.txt').write_text('example==1\n')
        names=['bridge/fixture.py','skills/biomni-fixture/SKILL.md','requirements-core.lock.txt']
        (root/'manifest.json').write_text(json.dumps({'package_version':version,'files':[{'path':n,'sha256':hashlib.sha256((root/n).read_bytes()).hexdigest()} for n in names]}))
    def installation(self,root,package):
        root.mkdir();(root/'.local').mkdir();shutil.copytree(package/'skills',root/'skills');shutil.copyfile(package/'bridge/fixture.py',root/'.local/fixture.py')
        (root/'.local/compute_config.json').write_text(json.dumps({'edition':'server','profile':'core'}));(root/'.local/private.json').write_text('private')
        upgrade.initialize_installation(root,package)
    def test_upgrade_rollback_and_private_configuration_protection(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);a=r/'a';b=r/'b';t=r/'install';self.package(a,'1.0.0','old');self.package(b,'2.0.0','new');self.installation(t,a)
            p=upgrade.preview_upgrade(t,b);result=upgrade.apply_upgrade(p,p['plan_sha256']);self.assertEqual((t/'.local/fixture.py').read_text(),'new');self.assertEqual((t/'.local/private.json').read_text(),'private')
            upgrade.rollback_upgrade(result['journal_file']);self.assertEqual((t/'.local/fixture.py').read_text(),'old');self.assertTrue(upgrade.preview_upgrade(t,b)['can_apply'])
    def test_custom_skill_preserved_and_custom_source_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);a=r/'a';b=r/'b';t=r/'install';self.package(a,'1','old');self.package(b,'2','new');self.installation(t,a)
            (t/'skills/biomni-fixture/SKILL.md').write_text('my instructions');p=upgrade.preview_upgrade(t,b);self.assertIn('skills/biomni-fixture/SKILL.md',p['preserved_customizations']);upgrade.apply_upgrade(p,p['plan_sha256']);self.assertEqual((t/'skills/biomni-fixture/SKILL.md').read_text(),'my instructions')
            (t/'.local/fixture.py').write_text('custom source');p=upgrade.preview_upgrade(t,b);self.assertFalse(p['can_apply'])
            (t/'.local/fixture.py').write_text('new')
            for suffix in ['.R','.ps1']:
                name='bridge/custom'+suffix;(b/name).write_text('stock');(t/('.local/custom'+suffix)).write_text('custom')
                manifest=json.loads((b/'manifest.json').read_text());manifest['files'].append({'path':name,'sha256':hashlib.sha256((b/name).read_bytes()).hexdigest()});(b/'manifest.json').write_text(json.dumps(manifest))
                p=upgrade.preview_upgrade(t,b);self.assertFalse(p['can_apply']);self.assertIn('custom_source_requires_manual_merge:.local/custom'+suffix,p['blockers'])
    def test_preview_race_and_post_upgrade_changes_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);a=r/'a';b=r/'b';t=r/'install';self.package(a,'1','old');self.package(b,'2','new');self.installation(t,a)
            p=upgrade.preview_upgrade(t,b);(t/'.local/fixture.py').write_text('concurrent edit')
            with self.assertRaises(ValueError):upgrade.apply_upgrade(p,p['plan_sha256'])
            (t/'.local/fixture.py').write_text('old');p=upgrade.preview_upgrade(t,b);v=upgrade.apply_upgrade(p,p['plan_sha256']);(t/'.local/fixture.py').write_text('custom after upgrade')
            with self.assertRaises(ValueError):upgrade.rollback_upgrade(v['journal_file'])
    def test_failure_rolls_back_written_files(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);a=r/'a';b=r/'b';t=r/'install';self.package(a,'1','old');self.package(b,'2','new');self.installation(t,a)
            p=upgrade.preview_upgrade(t,b);original=upgrade._copy_atomic;failed=[False]
            def fail_once(source,target):
                if target.resolve()==(t/'.local/fixture.py').resolve() and not failed[0]:
                    failed[0]=True;original(source,target);raise OSError('simulated failure after replacement')
                return original(source,target)
            with patch.object(upgrade,'_copy_atomic',side_effect=fail_once):
                with self.assertRaises(OSError):upgrade.apply_upgrade(p,p['plan_sha256'])
            self.assertEqual((t/'.local/fixture.py').read_text(),'old');self.assertFalse((t/'.upgrade.lock').exists())
    def test_catalog_has_real_signatures_enums_and_no_runtime_state(self):
        data,md=generate_catalog.generate();entry=next(t for t in data['tools'] if t['name']=='guide_molecular_drylab')
        self.assertEqual(set(entry['input_schema']['properties']['task']['enum']),set(__import__('molecular_biology_ext').ROUTES))
        self.assertNotIn('receipt_file',json.dumps(data));self.assertIn('splicing',md)

if __name__=='__main__':unittest.main()
