"""Explicit opt-in for bounded local scientific computation."""
import json
import os
from pathlib import Path


def edition():
    configured = os.environ.get('BIOMNI_COMPUTE_EDITION')
    if configured is None:
        path = Path(__file__).resolve().parent/'compute_config.json'
        configured = json.loads(path.read_text(encoding='utf8')).get('edition','server') if path.exists() else 'server'
    if configured not in {'server','local'}:
        raise ValueError('Unknown compute edition')
    return configured


def require_local():
    if edition()!='local':
        raise ValueError('Local scientific execution requires the local edition; use server task preparation in the server edition')
