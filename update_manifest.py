"""Refresh allowlisted release hashes, including new source files not ignored by Git."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
result = subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root,capture_output=True,text=True,encoding='utf8',check=True)
names = sorted({name for name in result.stdout.split('\0') if name and name != 'manifest.json'})
entries = [{'path':name,'bytes':(root/name).stat().st_size,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()} for name in names]
(root/'manifest.json').write_text(json.dumps({'project':'BioResearchWorkbench','bridge_version':'2.13','package_version':'2.13.0','files':entries},indent=2)+'\n',encoding='utf8',newline='\n')
print('RELEASE_MANIFEST_UPDATED')
