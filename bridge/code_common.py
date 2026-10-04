"""Bounded, source-scoped private code review primitives. Never execute source."""
import csv
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from academic_common import artifact, digest, read_file, rows

LIMITS = ['Static checks are incomplete and do not establish scientific correctness.',
          'Private source, paths, data and reports are never uploaded by these tools.']


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def sha(value):
    return digest(canon(value).encode())


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or any(ord(c)<32 for c in value):
        raise ValueError('Use a relative POSIX filename')
    p=PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or ':' in value or value != p.as_posix():
        raise ValueError('Traversal, absolute and noncanonical paths are refused')
    return value


def scoped_sources(root_path, files):
    original=Path(root_path).expanduser()
    if original.is_symlink(): raise ValueError('Linked roots are refused')
    root=original.resolve(strict=True)
    if not root.is_dir() or not isinstance(files,list) or not 0<len(files)<=200:
        raise ValueError('Explicit scope of 1 to 200 source files required')
    if len(set(files))!=len(files): raise ValueError('Duplicate source selection')
    result=[]; total=0
    for name in files:
        relative(name); path=root/name
        if any(p.is_symlink() for p in [path,*path.parents] if p.is_relative_to(root)):
            raise ValueError('Linked source files and directories are refused')
        path=path.resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size>2_000_000:
            raise ValueError('Source exceeds scope or size limit')
        if path.name.startswith('.env') or path.suffix.lower() in {'.key','.pem','.pfx','.p12','.sqlite3'}:
            raise ValueError('Credential and runtime files are outside code review scope')
        raw=path.read_bytes();total+=len(raw)
        if total>12_000_000: raise ValueError('Source scope exceeds 12 MB')
        result.append({'path':name,'sha256':digest(raw),'bytes':len(raw),'text':raw.decode('utf-8-sig')})
    return root,result


def table(path, maximum=20000):
    p,raw=read_file(path,12_000_000)
    with p.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream,delimiter='\t' if p.suffix=='.tsv' else ',')
        header=reader.fieldnames
        if not header or len(set(header))!=len(header) or any(not h for h in header):
            raise ValueError('Distinct nonempty table columns required')
        data=[]
        for row in reader:
            if len(data)>=maximum: raise ValueError('Export a bounded server summary')
            if None in row or any(v is None for v in row.values()): raise ValueError('Inconsistent row width')
            data.append(row)
    return header,data,digest(raw)


def number(value):
    if isinstance(value,bool): raise ValueError('Boolean is not a numeric measurement')
    v=float(value)
    if not math.isfinite(v): raise ValueError('Finite numeric values required')
    return v


def report(kind, **data):
    return artifact(kind, {'schema':1, **data, 'limitations':data.get('limitations',[])+LIMITS})


def binding(inputs, design, references):
    if not isinstance(design,dict) or not design or not isinstance(references,dict) or not references:
        raise ValueError('Explicit design and reference versions required')
    out=[]
    for item in rows(inputs,200):
        if not item.get('id') or len(item['id'])>200: raise ValueError('Input identity required')
        _,raw=read_file(item['path'],30_000_000)
        out.append({'id':item['id'],'sha256':digest(raw)})
    if not out or len({x['id'] for x in out})!=len(out):raise ValueError('Distinct explicit inputs required')
    return {'inputs':sorted(out,key=lambda x:x['id']),'design':design,'references':references}
