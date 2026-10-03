"""Bounded static skill review. Findings are candidates, never a safety certificate."""
import argparse
import json
import re
from pathlib import Path

RULES = {
    'instruction_override': r'(?i)ignore (?:all |previous |prior )*(?:instructions|rules)|忽略.{0,8}(?:指令|规则)',
    'dynamic_execution': r'\b(?:eval|exec)\s*\(|(?:shell\s*=\s*True)|Invoke-Expression|os\.system\s*\(',
    'process_execution': r'subprocess\.|Start-Process|\b(?:curl|wget|pip install|uv pip|npm install)\b',
    'network_or_upload': r'https?://|requests\.(?:post|put)|urlopen|fetch\s*\(',
    'credential_access': r'(?i)(?:api[_-]?key|access[_-]?token|password|\.ssh|\.env)',
    'destructive_operation': r'shutil\.rmtree|Remove-Item|\brm\s+-[rf]|\bunlink\s*\(',
}
ALLOWED = {'.md','.py','.sh','.ps1','.js','.ts','.json','.yaml','.yml','.toml','.txt','.R'}


def scan(root, max_files=250, max_bytes=2000000):
    root = Path(root)
    if root.is_symlink() or not root.is_dir(): raise ValueError('Regular folder required')
    root = root.resolve()
    if not (root/'SKILL.md').is_file(): raise ValueError('SKILL.md required')
    findings = []
    ignored = []
    files = 0
    total = 0
    pending = [root]
    visited = 0
    while pending:
        folder = pending.pop()
        for p in folder.iterdir():
            visited += 1
            if visited>max_files*4: raise ValueError('Directory entry budget exceeded; narrow scope')
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                findings.append({'file':rel,'rule':'symlink_not_followed'})
                continue
            if p.is_dir():
                pending.append(p)
                continue
            if not p.is_file(): continue
            files += 1
            if files>max_files: raise ValueError('File budget exceeded; narrow scope')
            if p.suffix not in ALLOWED:
                ignored.append(rel)
                continue
            size = p.stat().st_size
            total += size
            if total>max_bytes: raise ValueError('Text budget exceeded; narrow scope')
            with p.open('rb') as stream:
                raw = stream.read(size+1)
            if len(raw)>size: raise ValueError('Source changed during scan')
            try: text = raw.decode('utf8')
            except UnicodeDecodeError:
                findings.append({'file':rel,'rule':'non_utf8_not_reviewed'})
                continue
            for line_no,line in enumerate(text.splitlines(),1):
                for rule,pattern in RULES.items():
                    if re.search(pattern,line): findings.append({'file':rel,'line':line_no,'rule':rule})
    return {'files_seen':files,'text_bytes':total,'findings':findings,
            'unreviewed_files':ignored,'state':'manual_review_required',
            'limitations':['No target code executed; matching lines may be benign.',
                           'Dynamic behavior, non-text files and dependency contents are not analyzed.',
                           'Report file names are private; review before sharing.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder')
    args=parser.parse_args()
    print(json.dumps(scan(args.folder),ensure_ascii=False,indent=2))
