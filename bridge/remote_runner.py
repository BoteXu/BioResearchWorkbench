"""Portable server runner. Standard library only; execute on the chosen server."""
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf8')
    os.replace(temporary, path)


def main(request_path):
    request_path = Path(request_path).resolve(strict=True)
    task = json.loads(request_path.read_text(encoding='utf8'))
    folder = request_path.parent
    state_path = folder / 'remote_receipt.json'
    # One writer per task bundle, including across hosts sharing a filesystem.
    lock_path = folder / 'runner.lock'
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    state = {'task_id': task['task_id'], 'request_sha256': digest(request_path), 'host': socket.gethostname(), 'started_at_unix': time.time(), 'state': 'running', 'outputs': [], 'pid': os.getpid()}
    save(state_path, state)
    try:
        workdir = Path(task['remote_workdir']).resolve(strict=True)
        if state['host'] != task['expected_host']:
            raise ValueError('Server hostname does not match the explicitly selected host')
        for relative in task['expected_outputs']:
            candidate = (workdir / relative).resolve()
            candidate.relative_to(workdir)
            if candidate.exists():
                raise ValueError('Expected output already exists; select a fresh output path: ' + relative)
        for item in task.get('inputs', []):
            p = (workdir / item['path']).resolve(strict=True)
            p.relative_to(workdir)
            if digest(p) != item['sha256']:
                raise ValueError('Input checksum mismatch: ' + item['path'])
        with (folder / 'stdout.log').open('wb') as out, (folder / 'stderr.log').open('wb') as err:
            process = subprocess.Popen(task['argv'], cwd=str(workdir), stdout=out, stderr=err, shell=False)
            state['child_pid'] = process.pid
            save(state_path, state)
            state['exit_code'] = process.wait()
        for relative in task['expected_outputs']:
            p = (workdir / relative).resolve()
            p.relative_to(workdir)
            exists = p.is_file()
            state['outputs'].append({'path': relative, 'exists': exists, 'bytes': p.stat().st_size if exists else None, 'sha256': digest(p) if exists else None})
        state['state'] = 'succeeded' if state['exit_code'] == 0 and all(x['exists'] and x['bytes'] > 0 for x in state['outputs']) else 'failed'
    except Exception as exc:
        state['state'] = 'failed'
        state['error'] = str(exc)
    finally:
        state['finished_at_unix'] = time.time()
        save(state_path, state)
        lock_path.unlink()
    return 0 if state['state'] == 'succeeded' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
