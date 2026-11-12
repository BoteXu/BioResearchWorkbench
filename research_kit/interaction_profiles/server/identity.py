"""Read selected existing package source only; imports no scientific packages."""
from pathlib import Path
import json,sys,hashlib,importlib.metadata
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import read,digest
def verify(software,required):
    source=read(Path(__file__).resolve().parents[1]/'upstream_code.json');records=[]
    for name in required:
        spec=source[name];root=Path(software['source_roots'][name]).resolve(strict=True);expected=spec['python_blobs'];actual={f.relative_to(root).as_posix():f for f in root.rglob('*.py') if '__pycache__' not in f.parts}
        if set(actual)!=set(expected):raise ValueError('Installed source inventory differs from reviewed upstream: '+name)
        for rel,f in actual.items():
            b=f.read_bytes()
            if hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()!=expected[rel]:raise ValueError('Installed source file differs from reviewed pinned Git blob: '+name+'/'+rel)
        records.append({'package':name,'source_root':str(root),'upstream_commit':spec['commit'],'files':len(expected),'fingerprint':digest(expected),'scope':'exact_python_source_inventory_not_scientific_runtime_validation'})
    return records
