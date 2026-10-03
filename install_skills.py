"""Install only audited workflow instructions; never execute bundled skill code."""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def default_destination():
    return Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'skills'


def validate_pack(source=ROOT/'skills'):
    source = Path(source)
    if source.is_symlink():
        raise ValueError('Symlink skill pack refused')
    catalog = json.loads((source/'catalog.json').read_text(encoding='utf8'))
    names = [s['name'] for s in catalog['skills']]
    if len(names) != len(set(names)) or not names:
        raise ValueError('Duplicate or empty skill catalog')
    expected = {'catalog.json'}
    for skill in catalog['skills']:
        name = skill['name']
        if not re.fullmatch(r'biomni-[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name)>64:
            raise ValueError('Invalid namespaced skill name')
        for rel, checksum in skill['files'].items():
            path = source/rel
            if not rel.startswith(name+'/') or not path.resolve().is_relative_to(source.resolve()):
                raise ValueError('Invalid skill file path')
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=source.parent) or not path.is_file():
                raise ValueError('Nonregular skill file refused')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=checksum:
                raise ValueError('Skill checksum mismatch')
            expected.add(rel)
        text = (source/name/'SKILL.md').read_text(encoding='utf8')
        if not text.startswith('---\n') or '\nname: '+name+'\n' not in text or '\ndescription: ' not in text:
            raise ValueError('Invalid skill frontmatter')
    actual = set()
    for p in source.rglob('*'):
        if p.is_symlink():
            raise ValueError('Symlink in skill pack')
        if p.is_file():
            actual.add(p.relative_to(source).as_posix())
    if actual != expected:
        raise ValueError('Skill file set mismatch')
    return catalog


def install(destination=None, source=ROOT/'skills', selected=None, dry_run=False):
    catalog = validate_pack(source)
    source = Path(source)
    destination = Path(destination or default_destination()).expanduser()
    if destination.is_symlink() or any(p.is_symlink() for p in destination.parents):
        raise ValueError('Symlink destination refused')
    destination = destination.resolve()
    names = {s['name'] for s in catalog['skills']}
    selected = list(selected) if selected else sorted(names)
    if len(selected)!=len(set(selected)) or not set(selected)<=names:
        raise ValueError('Unknown or repeated skill selection')
    actions = []
    for name in selected:
        target = destination/name
        if target.is_symlink():
            raise ValueError('Existing symlink refused')
        if target.exists():
            expected = next(s['files'] for s in catalog['skills'] if s['name']==name)
            actual = {}
            for p in target.rglob('*'):
                if p.is_symlink(): raise ValueError('Existing symlink refused')
                if p.is_file(): actual[name+'/'+p.relative_to(target).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
            if actual!=expected:
                raise ValueError('Existing skill differs; preserve it and choose another destination')
            actions.append({'name':name,'state':'already_identical'})
        else:
            actions.append({'name':name,'state':'planned' if dry_run else 'installed'})
    if dry_run:
        return {'pack_version':catalog['version'],'actions':actions,'dry_run':True}
    destination.mkdir(parents=True, exist_ok=True)
    # Serialize pack installers; an interrupted lock needs inspection, never automatic recovery.
    lock = destination/'.biomni-skills-install.lock'
    with lock.open('x', encoding='utf8'):
        pass
    created = []
    try:
        with tempfile.TemporaryDirectory(prefix='.biomni-skills-stage-', dir=destination) as staging:
            staged = Path(staging)
            for action in actions:
                if action['state']=='installed': shutil.copytree(source/action['name'], staged/action['name'])
            for action in actions:
                if action['state']=='installed':
                    target = destination/action['name']
                    target.mkdir()  # exclusive creation; no overwrite even after preflight
                    created.append(target)
                    for p in (staged/action['name']).iterdir():
                        if p.is_dir(): shutil.copytree(p, target/p.name)
                        else: shutil.copy2(p, target/p.name)
    except BaseException:
        for target in reversed(created):
            if target.parent==destination and target.name in selected and not target.is_symlink():
                shutil.rmtree(target)
        raise
    finally:
        lock.unlink()
    return {'pack_version':catalog['version'],'actions':actions,'dry_run':False}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination')
    parser.add_argument('--skill', action='append')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    result = {'valid':True,'skills':len(validate_pack()['skills'])} if args.validate_only else install(args.destination, selected=args.skill, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
