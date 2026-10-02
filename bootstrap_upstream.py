"""Fetch a fixed official source revision using only the standard library."""
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

COMMIT = "400c1f366b96a35ca253e13c9b06c5076af41d65"
URL = "https://codeload.github.com/snap-stanford/Biomni/zip/" + COMMIT

def main(destination):
    root = Path(destination)
    if root.exists():
        raise ValueError("Choose a new install directory")
    req = urllib.request.Request(URL, headers={"User-Agent":"BiomniDirectToolsInstaller"})
    with urllib.request.urlopen(req,timeout=60) as response:
        content = response.read(25000001)
    if len(content) > 25000000:
        raise ValueError("Unexpected upstream archive size")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.infolist()
        if sum(x.file_size for x in members) > 100000000:
            raise ValueError("Unexpected expanded upstream size")
        prefix = members[0].filename.split('/')[0] + '/'
        for item in members:
            name = item.filename[len(prefix):] if item.filename.startswith(prefix) else None
            if name is None:
                raise ValueError("Unexpected archive root")
            if not name:
                continue
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError("Unsafe upstream archive path")
            target = root / relative
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.read(item))
    print("UPSTREAM_SOURCE_READY")

if __name__ == '__main__':
    main(sys.argv[1])
