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
    parser.add_argument('--install-dir',default=str(Path.home()/'BiomniTools'))
    parser.add_argument('--profile',choices=['core','omics','full'],default='core')
    parser.add_argument('--client',choices=['codex','claude-desktop','vscode','portable'],default='codex')
    parser.add_argument('--skip-registration',action='store_true')
    parser.add_argument('--trust-dns-proxy',action='store_true')
    parser.add_argument('--validate-only',action='store_true')
    args = parser.parse_args()
    validate_package()
    if args.validate_only:
        return
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
        if subprocess.run([codex,'mcp','get','biomni'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
            raise ValueError('Existing biomni registration; inspect it first or use --skip-registration')
    target = Path(args.install_dir).expanduser().resolve()
    if target.exists():
        raise ValueError('Choose a new installation directory')
    target.parent.mkdir(parents=True,exist_ok=True)
    fetch_upstream(target)
    local = target/'.local'
    local.mkdir()
    for file in (ROOT/'bridge').iterdir():
        if file.is_file() and file.suffix=='.py':
            shutil.copy2(file,local/file.name)
    checked([uv,'venv','--python','3.11',target/'.venv_tools'])
    python = runtime_python(target)
    requirements = {'core':'requirements-core.lock.txt','omics':'requirements-omics.txt','full':'requirements-full.lock.txt'}[args.profile]
    checked([uv,'pip','install','--python',python,'-r',ROOT/requirements])
    checked([uv,'pip','install','--python',python,'--no-deps','-e',target])
    env = {**os.environ,'PYTHONUTF8':'1'}
    if args.trust_dns_proxy:
        env['BIOMNI_TRUST_DNS_PROXY']='1'
    checked([python,local/'bridge.py','--status'],env)
    checked([python,local/'smoke_mcp.py','--network'],env)
    text = (ROOT/'AGENTS.template.md').read_text(encoding='utf8').replace('{{INSTALL_DIR}}',target.as_posix()).replace('{{PYTHON}}',python.as_posix())
    (target/'AGENTS.generated.md').write_text(text,encoding='utf8',newline='\n')
    generate(target,target/'client_configs',args.trust_dns_proxy)
    if codex:
        command = [codex,'mcp','add','biomni','--env','PYTHONUTF8=1']
        if args.trust_dns_proxy:
            command.extend(['--env','BIOMNI_TRUST_DNS_PROXY=1'])
        checked(command+['--',python,local/'mcp_server.py'])
    print('INSTALLATION_AND_SMOKE_CHECKS_OK')
    print('Merge private client settings and AGENTS.generated.md, then open a fresh client session.')


if __name__=='__main__':
    main()
