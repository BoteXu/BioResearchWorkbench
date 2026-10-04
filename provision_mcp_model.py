"""Provision only the public fixed embedding files; private texts are never sent to a model service."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def provision(cache):
    from huggingface_hub import hf_hub_download
    root=Path(__file__).resolve().parent;spec=json.loads((root/'mcp_embedding_model.json').read_text())
    folder=None
    for name,sha in spec['files'].items():
        path=Path(hf_hub_download(spec['repository'],name,revision=spec['revision'],cache_dir=str(cache),token=False))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Embedding model source checksum mismatch')
        folder=path.parent
    return folder


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache-dir',required=True);a=p.parse_args();provision(Path(a.cache_dir))
    print('PINNED_PUBLIC_EMBEDDING_FILES_VERIFIED')
