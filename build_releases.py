"""Build two source-only editions from one audited Git tree."""
import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path


def build(destination):
    output=Path(destination).resolve();output.mkdir(parents=True,exist_ok=True)
    source=subprocess.check_output(['git','archive','--format=zip','HEAD'])
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        files={entry.filename:archive.read(entry.filename) for entry in archive.infolist() if not entry.is_dir()}
    original=json.loads(files['manifest.json'])
    assert set(files)=={e['path'] for e in original['files']}|{'manifest.json'}
    for entry in original['files']: assert hashlib.sha256(files[entry['path']]).hexdigest()==entry['sha256']
    for edition,profile in [('server','core'),('local','local')]:
        payload=dict(files)
        payload['edition.json']=(json.dumps({'edition':edition,'default_profile':profile})+'\n').encode()
        entries=[{'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in sorted(payload.items()) if name!='manifest.json']
        payload['manifest.json']=(json.dumps({'project':'BioResearchWorkbench','bridge_version':'2.8','package_version':'2.8.2','edition':edition,'files':entries},indent=2)+'\n').encode()
        target=output/('bioresearch-workbench-v2.8.2-'+edition+'.zip')
        if target.exists(): raise ValueError('Choose a fresh release output directory')
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,raw in sorted(payload.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,raw)
        print('EDITION_SOURCE_ARCHIVE_BUILT',edition,hashlib.sha256(target.read_bytes()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');build(parser.parse_args().destination)
