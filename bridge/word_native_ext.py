"""Reviewed native Word adapter. Fixed COM operations; no generic macros or source overwrite."""
import json
import os
import shutil
import subprocess
import base64
from pathlib import Path
from academic_common import artifact, read_file, digest, rows, text, docx_parts, safe_xml
from evidence import atomic_json

HERE=Path(__file__).resolve().parent


def _document(raw):
    parts=docx_parts(raw)
    if any('vba' in name.lower() or name.startswith(('word/embeddings/','word/activeX/')) for name in parts):
        raise ValueError('Macros, embedded executables and ActiveX are forbidden')
    for name,data in parts.items():
        if name.endswith('.rels'):
            for relation in safe_xml(data):
                if relation.get('TargetMode')=='External' and not relation.get('Type','').endswith('/hyperlink'):
                    raise ValueError('External templates, images and linked objects require removal before native automation')


def _native(config,folder):
    if os.name!='nt':raise ValueError('Native COM adapter requires installed Windows Word; portable document tools remain available')
    executable=shutil.which('powershell.exe')
    if not executable:raise ValueError('Native PowerShell is unavailable')
    atomic_json(folder/'native_request.json',config)
    # Execute our fixed reviewed code as a native command; no execution-policy
    # changes, interpolated paths, user scripts or document macros.
    script=(HERE/'word_native.ps1').read_text(encoding='utf8').split('\n',1)[1]
    code='$RequestFile=$env:BRW_WORD_REQUEST\n'+script
    try:
        process=subprocess.run([executable,'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(code.encode('utf-16le')).decode('ascii')],
            env={**os.environ,'BRW_WORD_REQUEST':str(folder/'native_request.json')},capture_output=True,text=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.TimeoutExpired:
        atomic_json(folder/'native_failure.json',{'state':'unknown','reason':'native_timeout','automatic_retry_allowed':False})
        raise RuntimeError('Native Word operation timed out; inspect private progress and the owned document before recovery') from None
    receipt=folder/'native_receipt.json'
    (folder/'native.stderr.txt').write_text(process.stderr[:20000],encoding='utf8')
    if process.returncode or not receipt.is_file():raise RuntimeError('Native Word operation failed or is unknown; inspect its private output before recovery')
    return json.loads(receipt.read_text(encoding='utf-8-sig'))


def inspect_native_word(manuscript_path: str) -> dict:
    """Read Word native UTF-16 ranges, comments, fields and page positions for one explicit document; no edits or citation refresh."""
    p,raw=read_file(manuscript_path)
    if p.suffix.lower()!='.docx':raise ValueError('Select a macro-free DOCX document')
    _document(raw)
    result=artifact('native_word_inspection',{'source_sha256':digest(raw),'state':'native_read_requested'})
    folder=Path(result['output_directory']);receipt=_native({'operation':'inspect','source':str(p),'source_sha256':digest(raw),'folder':str(folder)},folder)
    return {**result,'native':receipt,'limitations':['Native offsets are UTF-16 character positions, not Python string indices. A page position depends on the installed Word/fonts/printer layout. No citation plugin refresh occurs.']}


def prepare_native_word_revision(manuscript_path: str, expected_source_sha256: str, edits: list = None,
                                 comments: list = None, refresh_fields: bool = False) -> dict:
    """Preview range-based tracked edits and native comments against an explicit source hash; field-intersecting changes are forbidden."""
    p,raw=read_file(manuscript_path)
    if p.suffix.lower()!='.docx' or digest(raw)!=expected_source_sha256:raise ValueError('Unchanged macro-free DOCX required')
    _document(raw)
    edits=rows(edits or [],100);comments=rows(comments or [],100);ranges=[]
    for e in edits+comments:
        if type(e.get('start')) is not int or type(e.get('end')) is not int or not 0<=e['start']<e['end']:raise ValueError('Use reviewed native Word offsets')
        text(e.get('old_text'),20000)
    for e in edits:
        text(e.get('new_text'),20000);text(e.get('reason'),3000)
        if any(e['start']<b and e['end']>a for a,b in ranges):raise ValueError('Overlapping edits')
        ranges.append((e['start'],e['end']))
    for c in comments:text(c.get('comment'),10000)
    if type(refresh_fields) is not bool or not (edits or comments or refresh_fields):raise ValueError('Select explicit operations')
    return artifact('native_word_revision_plan',{'schema':1,'source':str(p),'source_sha256':digest(raw),'edits':edits,'comments':comments,'refresh_fields':refresh_fields,
        'limitations':['Native replacement tracks text changes and preserves surrounding Word structures. Replacement-run formatting and complex layout require visual review. Zotero plugin refresh is a separate operation.']})


def apply_native_word_revision(plan_file: str, expected_sha256: str, dispatch: bool = False) -> dict:
    """Execute one reviewed native Word plan on a fresh copy; preserve source, create real comments/tracked edits and export a PDF for final rendering review."""
    p,raw=read_file(plan_file)
    if dispatch is not True or digest(raw)!=expected_sha256 or not p.is_relative_to((HERE/'outputs').resolve()) or not p.parent.name.startswith('native_word_revision_plan_'):raise ValueError('Explicit unchanged generated Word plan required')
    plan=json.loads(raw);_,source=read_file(plan['source'])
    if digest(source)!=plan['source_sha256']:raise ValueError('Source changed after review')
    # A single-use marker survives timeout/unknown outcomes. Never retry writes.
    marker=p.parent/'dispatch.lock'
    with marker.open('x',encoding='utf8') as f:f.write('native operation dispatched; inspect receipt before recovery')
    result=artifact('native_word_revision',{'state':'dispatched','source_sha256':digest(source)})
    folder=Path(result['output_directory']);target=folder/'revised.docx';target.write_bytes(source)
    receipt=_native({**plan,'operation':'revise','source':str(target),'folder':str(folder)},folder)
    return {**result,'native':receipt,'state':'rendered_review_required','revised_file':str(target),'pdf_file':str(folder/'rendered.pdf')}


def request_native_citation_refresh(manuscript_path: str, expected_source_sha256: str,
                                    sync_acknowledged: bool = False, dispatch: bool = False) -> dict:
    """Invoke only the installed trusted ZoteroRefresh macro on a fresh document copy; keep an unknown/pending state until explicit native review, never retry."""
    if dispatch is not True or sync_acknowledged is not True:raise ValueError('Explicit citation refresh dispatch and Zotero synchronization acknowledgment required')
    p,raw=read_file(manuscript_path)
    if p.suffix.lower()!='.docx' or digest(raw)!=expected_source_sha256:raise ValueError('Unchanged DOCX required')
    _document(raw)
    result=artifact('native_citation_refresh',{'state':'requested','source_sha256':digest(raw)})
    folder=Path(result['output_directory']);target=folder/'refresh.docx';target.write_bytes(raw)
    receipt=_native({'operation':'zotero_refresh','source':str(target),'source_sha256':digest(raw),'folder':str(folder)},folder)
    return {**result,'native':receipt,'state':'pending_native_review','document':str(target),
        'limitations':['ZoteroRefresh can run asynchronously or display dialogs. Macro invocation does not establish citation completion. Review and save the open copy in Word, then inspect_native_word on that copy. Do not automatically retry an unknown refresh.']}
