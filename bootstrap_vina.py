"""Fetch an exact official Vina binary with fixed checksums; no scientific data download."""
import argparse
import hashlib
import os
import platform
import urllib.request
from pathlib import Path

ASSETS = {
    ('Windows','AMD64'):('vina_1.2.7_win.exe','e0c4b2715e0c1a74f6e92d0f3be0328ac97542eafbc111e6b1efad897a73cce5'),
    ('Linux','x86_64'):('vina_1.2.7_linux_x86_64','f31f774f723bba7bbe6e9d1c47577020eea9a8da16424284c043d22593570644'),
    ('Darwin','arm64'):('vina_1.2.7_mac_aarch64','823c2bbacf26d72183861322345f0a89736aca66c8e81054c66f93af5ad623f1'),
    ('Darwin','x86_64'):('vina_1.2.7_mac_x86_64','9f44ccbb163223613283a75d0be53235d9e63f4da08292cb7196144f9838b7f9'),
}


def fetch(destination):
    key=(platform.system(),platform.machine())
    if key not in ASSETS: raise ValueError('Vina binary platform not verified; configure an existing compatible Vina')
    name,digest=ASSETS[key]
    target=Path(destination)
    if target.exists(): raise ValueError('Refuse overwriting an existing Vina executable')
    request=urllib.request.Request('https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/'+name,headers={'User-Agent':'BiomniDirectToolsInstaller'})
    with urllib.request.urlopen(request,timeout=60) as response: raw=response.read(20000001)
    if len(raw)>20000000 or hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('Vina binary checksum/size mismatch')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    if os.name!='nt': target.chmod(0o700)
    print('PINNED_VINA_BINARY_READY')
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args();fetch(args.destination)
