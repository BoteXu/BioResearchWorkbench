"""Private path selection tests; no bridge, query or scientific engine is invoked."""
from pathlib import Path
import os,tempfile,unittest
from unittest.mock import patch
import workbench

class PortableConfig(unittest.TestCase):
    def test_missing_selection_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(workbench,'HERE',Path(tmp)),patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'Select an existing private bridge'):workbench._bridge_root()
    def test_selected_existing_root_resolves_without_importing(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'BIORESEARCH_BRIDGE_ROOT':tmp},clear=True):
            (Path(tmp)/'bridge.py').write_text("raise AssertionError('not imported')",encoding='utf8')
            self.assertEqual(workbench._bridge_root(),str(Path(tmp).resolve()))
    def test_missing_bridge_fails_without_fallback(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'BIORESEARCH_BRIDGE_ROOT':tmp},clear=True):
            with self.assertRaisesRegex(ValueError,'no installation or fallback'):workbench._bridge_root()

if __name__=='__main__':unittest.main()
