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
    path_text=text
    try:
        source_index=json.loads(text)
        if isinstance(source_index,dict) and isinstance(source_index.get('files'),list):
            source_index=dict(source_index);rows=[]
            for entry in source_index['files']:
                row=dict(entry) if isinstance(entry,dict) else entry
                if isinstance(row,dict):
                    name=row.get('path')
                    if isinstance(name,str) and name and not name.startswith('/') and '\\' not in name and ':' not in name and all(p not in {'','.','..'} for p in name.split('/')) and re.fullmatch('[a-f0-9]{64}',str(row.get('sha256',''))):
                        row['path']='CANONICAL_SOURCE_MEMBER'
                rows.append(row)
            source_index['files']=rows;path_text=json.dumps(source_index,ensure_ascii=False)
    except (ValueError,TypeError):
        pass
    findings = [category for category,pattern in PATTERNS.items() if re.search(pattern,address_text if category=='address_literal' else path_text if category=='home_or_server_path' else text)]
    if any(term.casefold() in text.casefold() for term in deny_terms if term):
        findings.append('private_deny_term')
    return findings


def git(root, *args):
    result = subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,encoding='utf8',errors='replace',check=True)
    return result.stdout


def licensed_fonts(root):
    """Only exact, metadata-reviewed OFL font bytes may bypass text decoding."""
    path=root/'PUBLIC_ASSETS.json'
    if not path.exists():return {}
    data=json.loads(path.read_text(encoding='utf8'));result={}
    for name,row in data['files'].items():
        if not name.startswith('research_kit/scientific-visualization/assets/fonts/') or not name.endswith('.ttf') or row.get('license')!='OFL-1.1':raise ValueError('Unsupported binary publication scope')
        license_path=root/row['license_file']
        if not license_path.is_file() or hashlib.sha256(license_path.read_bytes()).hexdigest()!=row['license_sha256']:raise ValueError('Bundled font license changed')
        result[name]=row['sha256']
    return result


def historical_blobs(root):
    """Read all reachable HEAD objects without one process per historical blob."""
    objects=list(dict.fromkeys(line.split(' ',1)[0] for line in git(root,'rev-list','--objects','HEAD').splitlines()))
    proc=subprocess.Popen(['git','cat-file','--batch'],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for oid in objects:
            proc.stdin.write((oid+'\n').encode());proc.stdin.flush()
            header=proc.stdout.readline().decode('ascii').split()
            if len(header)!=3:raise ValueError('Unresolved history object')
            size=int(header[2]);raw=proc.stdout.read(size)
            if len(raw)!=size or proc.stdout.read(1)!=b'\n':raise ValueError('Incomplete history object')
            if header[1]=='blob':yield raw
    finally:
        proc.stdin.close();proc.stdout.close();proc.wait()


def review(root, manifest=False, history=False, deny_terms=()):
    root = Path(root).resolve()
    fonts=licensed_fonts(root);font_hashes=set(fonts.values())
    if (root/'.git').exists():
        names = git(root,'ls-files','--cached','--others','--exclude-standard','-z').split('\0')
        paths = sorted({root/name for name in names if name})
    else:
        paths = sorted(p for p in root.rglob('*') if p.is_file() and not any(part in {'__pycache__','.git'} for part in p.relative_to(root).parts))
    findings = []
    for path in paths:
        name = path.relative_to(root).as_posix()
        if any(part in RUNTIME for part in path.relative_to(root).parts) or path.name.startswith('.env') or path.name.endswith(('.private.json','.private.txt','.private.toml','.private.lock','.local.json')) or ('research_kit' in path.parts and 'qa' in path.parts) or path.suffix.lower() in {'.env','.pem','.key','.sqlite3','.sqlite','.duckdb','.onnx','.log','.pfx','.p12','.zip'}:
            findings.append({'file':name,'category':'runtime_or_sensitive_file'})
            continue
        if name in fonts:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=fonts[name]:findings.append({'file':name,'category':'licensed_binary_checksum_mismatch'})
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
        for raw in historical_blobs(root):
            if hashlib.sha256(raw).hexdigest() in font_hashes:continue
            categories=scan_text(raw.decode('utf8',errors='replace'),deny_terms)
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
