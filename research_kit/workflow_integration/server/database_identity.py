from pathlib import Path
from runtime import sha

def verify(root,manifest,mode):
    root=Path(root).resolve(strict=True)
    if mode not in {'full_sha256','verified_snapshot_stat'}:raise ValueError('Select explicit database integrity verification level')
    entries=manifest.get('files',[])
    if not entries or len({r.get('path') for r in entries})!=len(entries):raise ValueError('Nonempty selected database file manifest required')
    for row in entries:
        name=row['path']
        if not isinstance(name,str) or name.startswith('/') or '\\' in name or any(p in ('','..','.') for p in name.split('/')):raise ValueError('Database file escapes selected database root')
        path=(root/name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size!=row['bytes']:raise ValueError('Database component unavailable or changed')
        if mode=='full_sha256':
            if sha(path)!=row.get('sha256'):raise ValueError('Database SHA256 changed')
        elif path.stat().st_mtime_ns!=row.get('mtime_ns') or not manifest.get('previous_verified_receipt_sha256'):
            raise ValueError('Database snapshot changed or lacks prior verification provenance')
    return {'integrity_level':mode,'listed_components_checked':len(entries),'full_bytes_rehashed':mode=='full_sha256',
            'coverage_limit':'Only declared engine-used components; audit engine database-path configuration separately'}
