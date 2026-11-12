"""Explicit source-only private add-on installer, preserving existing client settings."""
import argparse
import ast
import hashlib
import json
import os
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MODULE='bulk_optional_ext.py'
NAMES=['guide_optional_bulk_pipeline','audit_optional_bulk_configuration','audit_optional_bulk_inputs','plan_optional_bulk_workflow','audit_optional_bulk_outputs']
SKILL='biomni-bulk-rnaseq-optional'

def _hash(data):return hashlib.sha256(data).hexdigest()
def validate():
    m=json.loads((ROOT/'manifest.json').read_text(encoding='utf8'))
    files=m['files'];seen=set()
    for item in files:
        rel=item['path'];p=ROOT/rel
        if not isinstance(rel,str) or rel in seen or p.is_symlink() or not p.resolve().is_relative_to(ROOT) or not p.is_file():raise ValueError('Invalid add-on manifest path')
        seen.add(rel)
        if _hash(p.read_bytes())!=item['sha256']:raise ValueError('Add-on source hash mismatch')
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.name!='manifest.json'}
    if actual!=seen:raise ValueError('Unexpected source file or incomplete manifest')
    for p in [ROOT/'addons'/MODULE,ROOT/'install_private_addon.py']:ast.parse(p.read_text(encoding='utf8'))
    return m

def install(bridge_dir,skills_dir,dry_run=False):
    validate();bridge=Path(bridge_dir);skills=Path(skills_dir)
    if bridge.is_symlink() or not bridge.is_dir() or skills.is_symlink() or not skills.is_dir():raise ValueError('Choose existing regular private bridge and client-skill directories')
    bridge=bridge.resolve();skills=skills.resolve()
    source=(ROOT/'addons'/MODULE).read_bytes();skill=(ROOT/'skills'/SKILL/'SKILL.md').read_bytes()
    targets={bridge/MODULE:source,skills/SKILL/'SKILL.md':skill}
    extension=bridge/'extensions.py';entry=bridge/'bridge.py'
    oldext=extension.read_bytes();oldentry=entry.read_bytes()
    e=oldext.decode('utf8').replace('\r\n','\n');b=oldentry.decode('utf8').replace('\r\n','\n')
    line='    "bulk_optional": ("bulk_optional_ext", '+repr(NAMES)+'),\n'
    if '"bulk_optional"' in e:
        if line not in e:raise ValueError('Existing optional registry differs; review update before overwriting')
    else:
        if e.count('EXPORTS = {')!=1:raise ValueError('Unsupported bridge registry')
        e=e.replace('EXPORTS = {','EXPORTS = {\n'+line,1)
    if '"bulk_optional_ext.py"' not in b:
        if b.count('"cadd_ext.py"):\n')!=1:raise ValueError('Require a reviewed bridge 2.12 source manifest')
        b=b.replace('"cadd_ext.py"):\n','"cadd_ext.py", "bulk_optional_ext.py"):\n',1)
    ast.parse(e);ast.parse(b)
    targets[extension]=e.encode('utf8');targets[entry]=b.encode('utf8')
    before={p:p.read_bytes() if p.exists() else None for p in targets}
    for p in [bridge/MODULE,skills/SKILL/'SKILL.md']:
        if before[p] is not None and before[p]!=targets[p]:raise ValueError('Existing optional source differs; preserve it for reviewed update')
    skilldir=skills/SKILL
    if skilldir.exists() and (skilldir.is_symlink() or {p.name for p in skilldir.iterdir()}!={'SKILL.md'}):raise ValueError('Existing skill has unexpected contents; preserve customization')
    changed={p:data for p,data in targets.items() if before[p]!=data}
    if dry_run or not changed:return {'success':True,'state':'dry_run' if dry_run else 'already_current','changed_files':len(changed)}
    lock=bridge/'.private-bulk-addon-install.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    backup=bridge/'private_addon_backups'/('bulk_'+uuid.uuid4().hex);applied=[]
    try:
        os.close(fd)
        if any((p.read_bytes() if p.exists() else None)!=before[p] for p in targets):raise ValueError('Selected sources changed; stop and review')
        backup.mkdir(parents=True,exist_ok=False)
        for p in changed:
            if before[p] is not None:(backup/p.name).write_bytes(before[p])
        for p,data in changed.items():
            p.parent.mkdir(parents=True,exist_ok=True)
            temp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');temp.write_bytes(data);os.replace(temp,p);applied.append(p)
        receipt={'schema':'private-bulk-install-v1','state':'installed','addon_version':'0.1.0-private','changed_files':[{'name':p.name,'before_sha256':_hash(before[p]) if before[p] is not None else None,'after_sha256':_hash(targets[p])} for p in changed], 'configuration_changed':False,'dependencies_installed':False}
        (backup/'install-receipt.private.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        return {'success':True,'state':'installed','changed_files':len(changed),'configuration_changed':False,'dependencies_installed':False}
    except BaseException:
        for p in reversed(applied):
            if before[p] is None:p.unlink(missing_ok=True)
            else:p.write_bytes(before[p])
        raise
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bridge-dir',required=True);ap.add_argument('--skills-dir',required=True);ap.add_argument('--dry-run',action='store_true');a=ap.parse_args()
    print(json.dumps(install(a.bridge_dir,a.skills_dir,a.dry_run)))
