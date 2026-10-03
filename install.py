"""One audited installer for Windows, macOS and compatible Linux environments."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from bootstrap_upstream import main as fetch_upstream
from client_config import generate

ROOT = Path(__file__).resolve().parent


def runtime_python(root, windows=None):
    windows = os.name == 'nt' if windows is None else windows
    return Path(root)/'.venv_tools'/('Scripts/python.exe' if windows else 'bin/python')


def validate_package(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf8'))
    for entry in manifest['files']:
        path = (root/entry['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Invalid distribution file path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Distribution checksum mismatch: '+entry['path'])
    print('PACKAGE_CHECKSUMS_OK')


def checked(argv, env=None):
    subprocess.run([str(x) for x in argv],check=True,env=env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install-dir')
    parser.add_argument('--mcp-name')
    default_profile = json.loads((ROOT/'edition.json').read_text(encoding='utf8'))['default_profile']
    parser.add_argument('--profile',choices=['core','local','omics','full'],default=default_profile)
    parser.add_argument('--client',choices=['codex','claude-desktop','vscode','portable'],default='codex')
    parser.add_argument('--skip-registration',action='store_true')
    parser.add_argument('--trust-dns-proxy',action='store_true')
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--install-vina',action='store_true',help='Download the fixed official Vina binary for this host')
    parser.add_argument('--install-skills',action='store_true',help='Copy the optional audited workflow pack into client discovery')
    parser.add_argument('--skills-dir',help='Private skill discovery directory; requires --install-skills')
    args = parser.parse_args()
    validate_package()
    mcp_name = args.mcp_name or ('bioresearch-local' if args.profile=='local' else 'bioresearch')
    if args.validate_only:
        return
    if args.skills_dir and not args.install_skills:
        parser.error('--skills-dir requires --install-skills')
    from install_skills import install as install_skill_pack, validate_pack
    validate_pack()
    if args.install_skills:
        install_skill_pack(args.skills_dir,dry_run=True)
    if platform.system() not in {'Windows','Darwin','Linux'}:
        raise ValueError('Native platform unverified; use browser access or a compatible Linux environment')
    uv = shutil.which('uv')
    if not uv:
        raise ValueError('Install uv using its official platform instructions first')
    codex = None
    if args.client=='codex' and not args.skip_registration:
        codex = shutil.which('codex')
        if not codex:
            raise ValueError('Codex CLI missing; choose --client portable or --skip-registration')
        if subprocess.run([codex,'mcp','get',mcp_name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
            raise ValueError('Existing registration for the selected MCP name; inspect it first or use --skip-registration')
    target = Path(args.install_dir or Path.home()/('BioResearchWorkbenchLocal' if args.profile=='local' else 'BioResearchWorkbench')).expanduser().resolve()
    if target.exists():
        raise ValueError('Choose a new installation directory')
    target.parent.mkdir(parents=True,exist_ok=True)
    fetch_upstream(target)
    local = target/'.local'
    local.mkdir()
    for file in (ROOT/'bridge').iterdir():
        if file.is_file() and file.suffix in {'.py','.R'}:
            shutil.copy2(file,local/file.name)
    for guide in ROOT.glob('*.md'):
        shutil.copy2(guide,local/guide.name)
    for provenance in ('LICENSE','NOTICE','third_party_components.json'):
        shutil.copy2(ROOT/provenance,local/provenance)
    shutil.copytree(ROOT/'skills',target/'skills',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(ROOT/'install_skills.py',target/'install_skills.py')
    (local/'compute_config.json').write_text(json.dumps({'edition':'local' if args.profile=='local' else 'server','profile':args.profile})+'\n',encoding='utf8')
    checked([uv,'venv','--python','3.11',target/'.venv_tools'])
    python = runtime_python(target)
    requirements = {'core':'requirements-core.lock.txt','local':'requirements-local.txt','omics':'requirements-omics.txt','full':'requirements-full.lock.txt'}[args.profile]
    checked([uv,'pip','install','--python',python,'-r',ROOT/requirements])
    checked([uv,'pip','install','--python',python,'--no-deps','-e',target])
    env = {**os.environ,'PYTHONUTF8':'1'}
    if args.trust_dns_proxy:
        env['BIOMNI_TRUST_DNS_PROXY']='1'
    if args.install_vina:
        if args.profile!='local': raise ValueError('Vina installation is for the optional local edition')
        from bootstrap_vina import fetch
        fetch(local/'bin'/('vina.exe' if os.name=='nt' else 'vina'))
    checked([python,local/'bridge.py','--status'],env)
    checked([python,local/'smoke_mcp.py','--network'],env)
    placement = 'server' if args.profile!='local' else 'local'
    text = (ROOT/'AGENTS.template.md').read_text(encoding='utf8').replace('{{INSTALL_DIR}}',target.as_posix()).replace('{{PYTHON}}',python.as_posix())
    if placement=='local':
        text+='\nThis is the optional local analysis edition. Explicit bounded transcriptomics and single-ligand docking workflows may run locally after input/design/resource checks. Large computations still belong on the server. Use real local-job completion receipts.\n'
    (target/'AGENTS.generated.md').write_text(text,encoding='utf8',newline='\n')
    generate(target,target/'client_configs',args.trust_dns_proxy,mcp_name)
    if codex:
        command = [codex,'mcp','add',mcp_name,'--env','PYTHONUTF8=1']
        if args.trust_dns_proxy:
            command.extend(['--env','BIOMNI_TRUST_DNS_PROXY=1'])
        checked(command+['--',python,local/'mcp_server.py'])
    if args.install_skills:
        install_skill_pack(args.skills_dir)
    print('INSTALLATION_AND_SMOKE_CHECKS_OK')
    print('Merge private client settings and AGENTS.generated.md, then open a fresh client session.')


if __name__=='__main__':
    main()
