"""Review release candidates without printing matching sensitive values."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PATTERNS = {
    'absolute_windows_path': r'(?<![A-Za-z])[A-Za-z]:[\\/][^\s"\']+',
    'home_or_server_path': r'/(?:home|Users|public|mnt|scratch|workspace|projects?)/[^\s"\']+',
    'address_literal': r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',
    'private_key': r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',
    'credential_token': r'(?:ghp_|github_pat_|sk-)[A-Za-z0-9_]{20,}',
    'personal_email': r'[A-Za-z0-9_.+\-]+@(?!(?:example\.(?:invalid|com)|users\.noreply\.github\.com)\b)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',
}
RUNTIME = {'results','jobs','outputs','sources','source_snapshots','evidence','data','downloads','articles','supplements','client_configs','.venv_tools','__pycache__','node_modules','embedding-cache','serena-private','browser-private','.serena','shared_mcp_private'}


def scan_text(text, deny_terms=()):
    # The optional Open Babel distribution uses a four-component public package version.
    # Exempt only its complete requirements line; all other address text remains scanned.
    address_text = re.sub(r'(?m)^openbabel-wheel==[0-9]+(?:\.[0-9]+){3}\r?$', 'PUBLIC_PACKAGE_VERSION', text)
    findings = [category for category,pattern in PATTERNS.items() if re.search(pattern,address_text if category=='address_literal' else text)]
    if any(term.casefold() in text.casefold() for term in deny_terms if term):
        findings.append('private_deny_term')
    return findings


def git(root, *args):
    result = subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,encoding='utf8',errors='replace',check=True)
    return result.stdout


def review(root, manifest=False, history=False, deny_terms=()):
    root = Path(root).resolve()
    if (root/'.git').exists():
        names = git(root,'ls-files','--cached','--others','--exclude-standard','-z').split('\0')
        paths = sorted({root/name for name in names if name})
    else:
        paths = sorted(p for p in root.rglob('*') if p.is_file() and not any(part in {'__pycache__','.git'} for part in p.relative_to(root).parts))
    findings = []
    for path in paths:
        name = path.relative_to(root).as_posix()
        if any(part in RUNTIME for part in path.relative_to(root).parts) or path.name.startswith('.env') or path.name.endswith(('.private.json','.private.txt','.private.toml','.private.lock')) or path.suffix.lower() in {'.env','.pem','.key','.sqlite3','.sqlite','.duckdb','.onnx','.log','.pfx','.p12','.zip'}:
            findings.append({'file':name,'category':'runtime_or_sensitive_file'})
            continue
        for category in scan_text(path.read_text(encoding='utf8',errors='replace'),deny_terms):
            findings.append({'file':name,'category':category})
    if manifest:
        entries = json.loads((root/'manifest.json').read_text(encoding='utf8'))['files']
        expected = {entry['path']:entry for entry in entries}
        actual = {path.relative_to(root).as_posix() for path in paths}
        if actual != set(expected) | {'manifest.json'}:
            findings.append({'category':'distribution_file_set_mismatch'})
        for name, entry in expected.items():
            path = (root/name).resolve()
            if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                findings.append({'file':name,'category':'distribution_checksum_mismatch'})
    if history:
        for line in git(root,'log','--format=%an|%ae|%cn|%ce','HEAD').splitlines():
            fields = line.split('|')
            if fields != ['Project Contributors','contributors@example.invalid']*2:
                findings.append({'category':'non_generic_commit_identity'})
        for line in git(root,'log','--format=%ai|%ci','HEAD').splitlines():
            if any(not stamp.endswith(' +0000') for stamp in line.split('|')):
                findings.append({'category':'non_normalized_commit_timezone'})
        # Review historical blob content as well as current files and metadata.
        objects = git(root,'rev-list','--objects','HEAD').splitlines()
        blobs = set()
        for line in objects:
            object_id = line.split(' ',1)[0]
            if object_id not in blobs and git(root,'cat-file','-t',object_id).strip() == 'blob':
                blobs.add(object_id)
                categories = scan_text(git(root,'cat-file','-p',object_id),deny_terms)
                findings.extend({'category':'historical_'+category} for category in categories)
    return {'files_reviewed':len(paths),'privacy_findings':findings,'pass':not findings,'limitations':['Pattern scanning is not proof of anonymity; manually review names, research context and account association.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',default=str(Path(__file__).resolve().parent))
    parser.add_argument('--manifest',action='store_true')
    parser.add_argument('--history',action='store_true')
    parser.add_argument('--deny-file')
    args = parser.parse_args()
    terms = Path(args.deny_file).read_text(encoding='utf8').splitlines() if args.deny_file else []
    result = review(args.root,args.manifest,args.history,terms)
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['pass'] else 1)
