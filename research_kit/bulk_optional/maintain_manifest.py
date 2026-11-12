"""Rebuild the source-only private add-on manifest after reviewed edits."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def update():
    files=[]
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(x in {'.git','__pycache__','runtime','results','data','logs','backups'} for x in p.relative_to(ROOT).parts) or p.name=='manifest.json':continue
        if p.is_symlink() or p.name.endswith(('.private.json','.private.txt')) or p.suffix.lower() in {'.zip','.docx','.log','.pyc'}:raise ValueError('Unexpected private runtime artifact in source tree')
        data=p.read_bytes();files.append({'path':p.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    value={'schema':'private-addon-source-manifest-v1','addon_version':'0.1.0-private','public_base':'2.12.0','visibility_required':'private','files':files}
    (ROOT/'manifest.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    return {'files':len(files),'addon_version':value['addon_version']}
if __name__=='__main__':print(json.dumps(update()))
