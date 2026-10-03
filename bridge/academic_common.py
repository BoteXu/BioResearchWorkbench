"""Bounded private manuscript/library artifacts; no external model or upload."""
import hashlib
import json
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from evidence import atomic_json

HERE = Path(__file__).resolve().parent
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_file(path, limit=30_000_000):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file() or p.stat().st_size > limit:
        raise ValueError('Provide a bounded local file')
    return p, p.read_bytes()


def rows(value, maximum=1000):
    if not isinstance(value, list) or len(value) > maximum or any(not isinstance(r, dict) for r in value):
        raise ValueError('Provide a bounded list of objects')
    return value


def text(value, maximum=10000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Provide nonempty bounded text')
    return value.strip()


def unique(records, key='id'):
    ids = [text(r.get(key), 200) for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Record identifiers must be unique')
    return ids


def artifact(kind, data, files=None):
    folder = HERE/'outputs'/(kind+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    for name, raw in (files or {}).items():
        if Path(name).name != name:
            raise ValueError('Artifact names must be basenames')
        (folder/name).write_bytes(raw.encode('utf8') if isinstance(raw, str) else raw)
    atomic_json(folder/'review.json', data)
    from reporting_ext import render_report
    summary = {'workflow': kind, **data, 'outputs': []}
    for p in sorted(folder.iterdir()):
        summary['outputs'].append({'name': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())})
    render_report(folder, summary)
    manifest = [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())} for p in sorted(folder.iterdir())]
    atomic_json(folder/'manifest.json', {'files': manifest})
    return {'success': True, **data, 'output_directory': str(folder), 'manifest_file': str(folder/'manifest.json')}


def safe_xml(raw):
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', raw, re.I):
        raise ValueError('XML entity declarations are not accepted')
    return ET.fromstring(raw)


def docx_parts(raw):
    with zipfile.ZipFile(__import__('io').BytesIO(raw)) as z:
        if len(z.infolist()) > 1000 or sum(e.file_size for e in z.infolist()) > 60_000_000:
            raise ValueError('DOCX expanded size exceeds review limit')
        if len(set(z.namelist())) != len(z.namelist()):
            raise ValueError('Duplicate DOCX parts are not accepted')
        return {n: z.read(n) for n in z.namelist()}


def manuscript(path):
    p, raw = read_file(path)
    suffix = p.suffix.lower(); segments = []; fields = []
    if suffix == '.docx':
        parts = docx_parts(raw); root = safe_xml(parts['word/document.xml'])
        depth=0;buffer=[];field_location=None
        for i, paragraph in enumerate(root.iter('{'+W+'}p'), 1):
            # Current displayed text includes insertions and excludes deleted text.
            value = ''.join(n.text or '' for n in paragraph.iter('{'+W+'}t'))
            instr = [n.text or '' for n in paragraph.iter('{'+W+'}instrText')]
            instr += [n.get('{'+W+'}instr', '') for n in paragraph.iter('{'+W+'}fldSimple')]
            active=depth>0;had_markers=False
            for node in paragraph.iter():
                if node.tag=='{'+W+'}fldChar':
                    had_markers=True;kind=node.get('{'+W+'}fldCharType')
                    if kind=='begin':
                        depth+=1
                        if depth==1:buffer=[];field_location='paragraph:'+str(i)
                    elif kind in {'separate','end'}:
                        if buffer:fields.append({'location':field_location or 'paragraph:'+str(i),'instruction':''.join(buffer)});buffer=[]
                        if kind=='end':depth=max(0,depth-1)
                elif node.tag=='{'+W+'}instrText' and depth:buffer.append(node.text or '')
                elif node.tag=='{'+W+'}fldSimple':fields.append({'location':'paragraph:'+str(i),'instruction':node.get('{'+W+'}instr','')})
            if not had_markers and not depth and instr:
                standalone=[n.text or '' for n in paragraph.iter('{'+W+'}instrText')]
                if standalone:fields.append({'location':'paragraph:'+str(i),'instruction':''.join(standalone)})
            segments.append({'location': 'paragraph:'+str(i), 'text': value,
                             'protected': bool(active or depth or instr or list(paragraph.iter('{'+W+'}fldChar'))),
                             'existing_revisions': bool(list(paragraph.iter('{'+W+'}ins')) or list(paragraph.iter('{'+W+'}del')))})
        for name in parts:
            if re.fullmatch(r'word/comments\d*\.xml', name):
                comments = safe_xml(parts[name])
                for c in comments.iter('{'+W+'}comment'):
                    fields.append({'location': 'comment:'+str(c.get('{'+W+'}id')), 'comment': ''.join(n.text or '' for n in c.iter('{'+W+'}t'))})
    elif suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(__import__('io').BytesIO(raw))
        if len(reader.pages) > 500:
            raise ValueError('PDF exceeds bounded review page limit')
        segments = [{'location': 'page:'+str(i+1), 'text': page.extract_text() or '', 'protected': False} for i, page in enumerate(reader.pages)]
    elif suffix in {'.md', '.txt', '.tex'}:
        segments = [{'location': 'line:'+str(i), 'text': v, 'protected': False} for i, v in enumerate(raw.decode('utf-8-sig').splitlines(), 1)]
    else:
        raise ValueError('Supported manuscripts: DOCX, PDF, Markdown, UTF-8 text, LaTeX')
    if sum(len(s['text']) for s in segments) > 2_000_000:
        raise ValueError('Extracted manuscript exceeds bounded text limit')
    return {'source_sha256': digest(raw), 'format': suffix[1:], 'segments': segments, 'fields_and_comments': fields,
            'extraction_issues': ['empty_text_requires_OCR'] if suffix == '.pdf' and any(not s['text'].strip() for s in segments) else [],
            'limitations': ['Text extraction does not establish layout quality or semantic correctness.', 'PDF locations are pages; DOCX locations are paragraph indexes, not rendered page numbers.', 'All source text and identifiers remain private; this tool makes no network request.']}


def locate(document, location):
    found = [s for s in document['segments'] if s['location'] == location]
    if len(found) != 1:
        raise ValueError('Location must match exactly one extracted segment')
    return found[0]


def normalized(value):
    return re.sub(r'\s+', ' ', value).strip().casefold()


def canonical_doi(value):
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', str(value).strip(), flags=re.I).lower()
    return value if re.fullmatch(r'10\.\d{4,9}/\S+', value) else ''
