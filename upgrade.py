"""Previewed, hash-bound portable upgrades. Never install dependencies, edit client registrations or overwrite private configuration."""
import argparse
import hashlib
import json
import os
import shutil
import uuid
import copy
from pathlib import Path
from install import validate_package

ROOT = Path(__file__).resolve().parent


def digest(raw): return hashlib.sha256(raw).hexdigest()


def _json(path, value):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');tmp.replace(p)


def _root(path):
    original=Path(path).expanduser()
    if original.is_symlink(): raise ValueError('Linked installation roots are refused')
    resolved=original.resolve(strict=True)
    if not resolved.is_dir(): raise ValueError('Installation directory required')
    return resolved


def _target(root, name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or any(x in {'','..','.'} for x in name.split('/')):
        raise ValueError('Canonical relative upgrade path required')
    p=root/name
    if p.is_absolute() and not p.resolve().is_relative_to(root) or any(a.is_symlink() for a in [p,*p.parents] if a.is_relative_to(root)):
        raise ValueError('Upgrade path escapes or traverses a linked installation')
    return p


def _mapping(package):
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf8'));files={}
    for entry in manifest['files']:
        name=entry['path'];target=None
        if name.startswith('bridge/') and Path(name).suffix in {'.py','.R','.ps1'}:target='.local/'+name.split('/',1)[1]
        elif '/' not in name and (name.endswith('.md') or name in {'LICENSE','NOTICE','third_party_components.json','mcp_components.json','mcp_embedding_model.json','cadd_sources.json','molecular_resources.json','TOOL_CATALOG.json','benchmark_catalog.json'}):target='.local/'+name
        elif name.startswith('skills/'):target=name
        elif name=='install_skills.py':target=name
        if target: files[target]={'source':name,'sha256':entry['sha256']}
    return manifest,files


def initialize_installation(install_dir, package_root=ROOT):
    """Record installed stock hashes only after all selected files actually match; do not adopt customizations as stock."""
    root=_root(install_dir);package=_root(package_root);validate_package(package)
    state=root/'upgrade_state.json'
    if state.exists():raise ValueError('Existing upgrade baseline must be reviewed, not replaced')
    manifest,files=_mapping(package)
    mismatches=[name for name,spec in files.items() if not _target(root,name).is_file() or digest(_target(root,name).read_bytes())!=spec['sha256']]
    if mismatches:raise ValueError('Installed stock files differ from supplied baseline package')
    config=root/'.local/compute_config.json'
    profile=json.loads(config.read_text()).get('profile','core') if config.is_file() else 'core'
    req={'core':'requirements-core.lock.txt','local':'requirements-local.txt','omics':'requirements-omics.txt','full':'requirements-full.lock.txt'}
    if profile not in req:raise ValueError('Unknown installation profile')
    value={'schema':1,'version':manifest['package_version'],'managed':files,'profile':profile,
           'requirements_sha256':digest((package/req[profile]).read_bytes())}
    _json(state,value);return {'state':'baseline_recorded','version':value['version'],'managed_files':len(files)}


def preview_upgrade(install_dir, package_root=ROOT):
    root=_root(install_dir);package=_root(package_root);validate_package(package)
    previous=json.loads((root/'upgrade_state.json').read_text(encoding='utf8'))
    manifest,files=_mapping(package);changes=[];custom=[];blockers=[]
    config=root/'.local/compute_config.json'
    cfg=json.loads(config.read_text(encoding='utf8')) if config.exists() else {}
    if cfg.get('edition') not in {'server','local'}:blockers.append('unrecognized_compute_configuration')
    if cfg.get('profile',previous['profile'])!=previous['profile']:blockers.append('profile_changed_requires_environment_review')
    req={'core':'requirements-core.lock.txt','local':'requirements-local.txt','omics':'requirements-omics.txt','full':'requirements-full.lock.txt'}[previous['profile']]
    if digest((package/req).read_bytes())!=previous['requirements_sha256']:blockers.append('dependency_change_requires_separate_environment_migration')
    for name,spec in sorted(files.items()):
        p=_target(root,name);actual=digest(p.read_bytes()) if p.is_file() else None;old=previous['managed'].get(name)
        if actual==spec['sha256']:continue
        if actual is not None and (old is None or actual!=old['sha256']):
            custom.append(name)
            if name.startswith('.local/') and p.suffix=='.py':blockers.append('custom_source_requires_manual_merge:'+name)
            continue
        changes.append({'path':name,'before_sha256':actual,'after_sha256':spec['sha256'],'source':spec['source']})
    # Runtime configuration, unknown add-ons, user-customized skills and retired stock files remain private and untouched.
    plan={'schema':1,'install_dir':str(root),'package_root':str(package),'package_manifest_sha256':digest((package/'manifest.json').read_bytes()),
          'baseline_sha256':digest((root/'upgrade_state.json').read_bytes()),'from_version':previous['version'],'to_version':manifest['package_version'],
          'changes':changes,'preserved_customizations':custom,'blockers':sorted(set(blockers)),'can_apply':not blockers,
          'configuration_migration':'validated existing edition/profile; no implicit schema or credential migration',
          'dependencies_changed':any('dependency_change' in b for b in blockers),'state':'preview_only'}
    return {**plan,'plan_sha256':digest(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode())}


def _same_plan(expected, actual):
    if expected.get('plan_sha256')!=actual['plan_sha256'] or expected!=actual:raise ValueError('Upgrade source, baseline or destination changed since preview')


def _copy_atomic(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    shutil.copyfile(source,tmp);tmp.replace(target)


def apply_upgrade(plan, reviewed_sha256):
    if plan.get('plan_sha256')!=reviewed_sha256:raise ValueError('Exact reviewed plan hash required')
    current=preview_upgrade(plan['install_dir'],plan['package_root']);_same_plan(plan,current)
    if not plan['can_apply']:raise ValueError('Resolve compatibility/customization blockers before upgrading')
    root=_root(plan['install_dir']);package=_root(plan['package_root']);lock=root/'.upgrade.lock'
    descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
    folder=root/'.upgrades'/uuid.uuid4().hex;folder.mkdir(parents=True)
    journal={'schema':1,'state':'prepared','plan':plan,'written':[],'baseline':json.loads((root/'upgrade_state.json').read_text())}
    _json(folder/'journal.json',journal)
    try:
        _same_plan(plan,preview_upgrade(root,package))
        for change in plan['changes']:
            target=_target(root,change['path']);source=_target(package,change['source'])
            actual=digest(target.read_bytes()) if target.is_file() else None
            if actual!=change['before_sha256'] or digest(source.read_bytes())!=change['after_sha256']:raise ValueError('Concurrent upgrade input change')
            if target.exists():_copy_atomic(target,_target(folder/'before',change['path']))
            # Journal intent before the write permits recovery after a crash at either side of replacement.
            journal['written'].append(change);journal['state']='applying';_json(folder/'journal.json',journal)
            _copy_atomic(source,target)
        next_state={**copy.deepcopy(journal['baseline']),'version':plan['to_version']}
        for change in plan['changes']:next_state['managed'][change['path']]={'source':change['source'],'sha256':change['after_sha256']}
        _json(root/'upgrade_state.json',next_state)
        journal['state']='applied';_json(folder/'journal.json',journal)
        return {'state':'applied','version':plan['to_version'],'journal_file':str(folder/'journal.json'),'restart_required':True,
                'preserved_customizations':plan['preserved_customizations'],'runtime_acceptance':'required_after_restart'}
    except Exception:
        try:rollback_upgrade(folder/'journal.json',allow_in_progress=True)
        except Exception:
            journal['state']='rollback_requires_review';_json(folder/'journal.json',journal)
        raise
    finally:
        # Only remove our own regular lock; no recursive deletion or lock recovery is attempted.
        if lock.is_file() and not lock.is_symlink():lock.unlink()


def rollback_upgrade(journal_file, allow_in_progress=False):
    path=Path(journal_file).resolve(strict=True);journal=json.loads(path.read_text(encoding='utf8'))
    root=_root(journal['plan']['install_dir'])
    if not path.parent.is_relative_to(root/'.upgrades') or path.name!='journal.json':raise ValueError('Journal must belong to the selected installation')
    if journal['state']!='applied' and not allow_in_progress:raise ValueError('Inspect an interrupted upgrade before explicit recovery')
    if not allow_in_progress and (root/'.upgrade.lock').exists():raise ValueError('Active or stale upgrade lock requires inspection')
    for change in reversed(journal['written']):
        target=_target(root,change['path']);actual=digest(target.read_bytes()) if target.is_file() else None
        if actual==change['before_sha256']:continue
        if actual!=change['after_sha256']:raise ValueError('Post-upgrade customization blocks rollback')
        if change['before_sha256'] is None:target.unlink()
        else:
            backup=_target(path.parent/'before',change['path'])
            if digest(backup.read_bytes())!=change['before_sha256']:raise ValueError('Rollback backup integrity mismatch')
            _copy_atomic(backup,target)
    _json(root/'upgrade_state.json',journal['baseline']);journal['state']='rolled_back';_json(path,journal)
    return {'state':'rolled_back','version':journal['baseline']['version'],'restart_required':True}


def main():
    p=argparse.ArgumentParser();p.add_argument('--install-dir');p.add_argument('--package-root',default=str(ROOT));p.add_argument('--preview-file');p.add_argument('--apply-plan');p.add_argument('--reviewed-sha256');p.add_argument('--rollback-journal');p.add_argument('--initialize-baseline',action='store_true');args=p.parse_args()
    if args.rollback_journal:result=rollback_upgrade(args.rollback_journal)
    elif args.apply_plan:result=apply_upgrade(json.loads(Path(args.apply_plan).read_text(encoding='utf8')),args.reviewed_sha256)
    elif args.initialize_baseline:result=initialize_installation(args.install_dir,args.package_root)
    else:
        result=preview_upgrade(args.install_dir,args.package_root)
        if args.preview_file:
            if Path(args.preview_file).exists():raise ValueError('Choose a fresh private plan file')
            _json(args.preview_file,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
