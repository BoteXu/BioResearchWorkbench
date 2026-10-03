"""Local bibliographic exchange and explicit PDF inventory; no native database mutation."""
import json
import re
from pathlib import Path
from academic_common import artifact, canonical_doi, digest, normalized, read_file, rows, safe_xml, text, unique


def _bib_entries(value):
    # Balanced braces and quoted values; unsupported macros are preserved, never expanded.
    entries = []; i = 0
    while i < len(value):
        m = re.search(r'@([A-Za-z]+)\s*([{(])', value[i:])
        if not m: break
        kind = m.group(1).lower(); start = i+m.end(); endchar = '}' if m.group(2) == '{' else ')'
        depth = 0; quoted = False; escaped = False; end = None
        for j in range(start, len(value)):
            c = value[j]
            if escaped: escaped = False; continue
            if c == '\\': escaped = True; continue
            if c == '"' and depth == 0: quoted = not quoted; continue
            if quoted: continue
            if c == endchar and depth == 0: end = j; break
            if c == '{': depth += 1
            elif c == '}': depth -= 1
        if end is None: raise ValueError('Unterminated BibTeX entry')
        body = value[start:end]; i = end+1
        if kind in {'comment', 'preamble', 'string'}:
            entries.append({'unsupported_entry': kind, 'raw': body}); continue
        if ',' not in body: raise ValueError('BibTeX entry requires a key and fields')
        key, fields = body.split(',', 1); parsed = {}; position = 0; unresolved = []
        while position < len(fields):
            fm = re.match(r'\s*,?\s*([\w-]+)\s*=\s*', fields[position:])
            if not fm:
                if fields[position:].strip(' ,\r\n\t'): raise ValueError('Unsupported BibTeX field syntax')
                break
            name = fm.group(1).lower(); position += fm.end(); startfield = position
            depth = 0; quoted = False; escaped = False
            while position < len(fields):
                c = fields[position]
                if escaped: escaped = False
                elif c == '\\': escaped = True
                elif c == '"' and depth == 0: quoted = not quoted
                elif not quoted:
                    if c == '{': depth += 1
                    elif c == '}': depth -= 1
                    elif c == ',' and depth == 0: break
                position += 1
            raw = fields[startfield:position].strip(); position += 1
            if name in parsed: raise ValueError('Repeated BibTeX field')
            if raw.startswith('{') and raw.endswith('}') or raw.startswith('"') and raw.endswith('"'):
                parsed[name] = raw[1:-1]
            else:
                parsed[name] = raw
                if not re.fullmatch(r'\d+', raw): unresolved.append(name)
        entries.append({'id': key.strip(), 'type': kind, 'title': parsed.get('title',''), 'doi': parsed.get('doi',''),
                        'year': parsed.get('year',''), 'authors': parsed.get('author','').split(' and ') if parsed.get('author') else [],
                        'source_fields': parsed, 'issues': ['unexpanded_macro:'+n for n in unresolved]})
    return entries


def _ris(value):
    records = []; fields = {}; last = None
    for line in value.splitlines():
        m = re.match(r'^([A-Z0-9]{2})\s{2}-\s?(.*)$', line)
        if m:
            k, v = m.groups()
            if k == 'TY':
                if fields: raise ValueError('RIS entry lacks ER terminator')
                fields = {'TY':[v]}
            elif k == 'ER':
                if not fields: raise ValueError('RIS terminator without entry')
                records.append({'id': (fields.get('ID') or ['ref'+str(len(records)+1)])[0],
                                'type': fields.get('TY',['GEN'])[0], 'title': (fields.get('TI') or fields.get('T1') or [''])[0],
                                'doi': fields.get('DO',[''])[0], 'year': (fields.get('PY') or fields.get('Y1') or [''])[0],
                                'authors': fields.get('AU', fields.get('A1',[])), 'source_fields': fields, 'issues': []})
                fields = {}; last = None; continue
            elif not fields: raise ValueError('RIS field outside entry')
            else: fields.setdefault(k,[]).append(v)
            last = k
        elif line.strip():
            if not last or not fields: raise ValueError('Unrecognized RIS line')
            fields[last][-1] += '\n'+line
    if fields: raise ValueError('RIS entry lacks ER terminator')
    return records


def _endnote_xml(raw):
    root = safe_xml(raw); result = []
    for i, r in enumerate(root.findall('.//record'), 1):
        def value(path):
            node = r.find(path)
            return ''.join(node.itertext()).strip() if node is not None else ''
        refnode=r.find('ref-type');kind=refnode.get('name','') if refnode is not None else ''
        kind={'Book':'book','Thesis':'thesis','Journal Article':'article','Conference Paper':'paper-conference'}.get(kind,kind or value('ref-type') or 'article')
        result.append({'id': value('rec-number') or 'ref'+str(i), 'type': kind,
                       'title': value('titles/title'), 'doi': value('electronic-resource-num'), 'year': value('dates/year'),
                       'container_title':value('titles/secondary-title'),'volume':value('volume'),'issue':value('number'),'pages':value('pages'),'publisher':value('publisher'),
                       'authors': [''.join(a.itertext()) for a in r.findall('contributors/authors/author')],
                       'source_fields': {'endnote_record_xml': __import__('xml.etree.ElementTree',fromlist=['tostring']).tostring(r,encoding='unicode')},
                       'issues': []})
    return result


def load_library(path):
    p, raw = read_file(path, 20_000_000); suffix = p.suffix.lower(); unsupported = []
    if suffix == '.ris': records = _ris(raw.decode('utf-8-sig'))
    elif suffix in {'.bib', '.bibtex'}:
        parsed = _bib_entries(raw.decode('utf-8-sig')); unsupported = [r for r in parsed if 'unsupported_entry' in r]
        records = [r for r in parsed if 'unsupported_entry' not in r]
    elif suffix == '.xml': records = _endnote_xml(raw)
    elif suffix == '.json':
        data = json.loads(raw)
        if isinstance(data,dict) and 'records' in data:
            records = rows(data['records'], 5000)
            if any('data' in r and 'key' in r for r in records):
                parsed=[]
                for r in records:
                    value=r.get('data',{})
                    if value.get('itemType') in {'note','attachment','annotation'}:
                        unsupported.append({'unsupported_entry':value.get('itemType'),'key':r.get('key')});continue
                    date=value.get('date','');year=re.search(r'\b\d{4}\b',date)
                    parsed.append({'id':r['key'],'type':value.get('itemType','journalArticle'),'title':value.get('title',''),
                        'doi':value.get('DOI',''),'year':year.group() if year else '',
                        'authors':[a.get('name') or ' '.join([a.get('firstName',''),a.get('lastName','')]).strip() for a in value.get('creators',[]) if a.get('creatorType')=='author'],
                        'source_fields':r,'issues':[]})
                records=parsed
        else:
            records = []
            for i,r in enumerate(rows(data,5000),1):
                date = r.get('issued',{}).get('date-parts',[[]])[0]
                records.append({'id': str(r.get('id','ref'+str(i))), 'type':r.get('type','article-journal'), 'title':r.get('title',''),
                                'doi':r.get('DOI',''), 'year':str(date[0]) if date else '',
                                'authors':[' '.join([a.get('given',''),a.get('family',a.get('literal',''))]).strip() for a in r.get('author',[])],
                                'source_fields':r,'issues':[]})
    else: raise ValueError('Use RIS, BibTeX, CSL-JSON, normalized JSON or EndNote XML')
    rows(records,5000); unique(records)
    for r in records:
        r['doi'] = canonical_doi(r.get('doi','')); r.setdefault('authors',[]);r.setdefault('issues',[])
        if not r.get('title'): r['issues'].append('missing_title')
        fields=r.get('source_fields',{});z=fields.get('data',fields)
        aliases={'container_title':('publicationTitle','container-title','journal','JO','JF','T2'),
                 'volume':('volume','VL'),'issue':('issue','number','IS'),'pages':('pages','page','SP'),
                 'publisher':('publisher','PB'),'url':('url','URL','UR'),'isbn':('ISBN','isbn','SN')}
        for target,keys in aliases.items():
            for key in keys:
                if z.get(key):
                    value=z[key];r[target]=value[0] if isinstance(value,list) else value;break
        if fields.get('SP') and fields.get('EP'):r['pages']=str(fields['SP'][0])+'-'+str(fields['EP'][0])
    return records, {'source_sha256':digest(raw), 'format':suffix[1:], 'unsupported_entries':unsupported}


def import_reference_library(path: str) -> dict:
    """Normalize an explicit exported library and retain source fields; do not merge or access a native database."""
    records, source = load_library(path)
    return artifact('library_import', {'records':records, **source, 'record_count':len(records),
        'limitations':['Exchange formats can lose notes, attachments, collections and native IDs. Source fields are retained privately.',
                       'BibTeX macros/TeX accents are not evaluated; unresolved values require review.','No cloud access or native library modification occurs.']})


def audit_reference_duplicates(path: str) -> dict:
    """Flag equal DOI, equal title/year and missing metadata; never delete or automatically merge records."""
    records, source = load_library(path); buckets = {}; candidates = []
    for r in records:
        if r['doi']: buckets.setdefault(('doi',r['doi']),[]).append(r['id'])
        if r.get('title'): buckets.setdefault(('title_year',normalized(r['title']),str(r.get('year',''))),[]).append(r['id'])
    for key, ids in buckets.items():
        if len(ids)>1: candidates.append({'basis':key[0],'ids':ids,'state':'review_required'})
    return artifact('library_duplicates', {'source':source,'candidates':candidates,'metadata_issues':[{'id':r['id'],'issues':r['issues']} for r in records if r['issues']],
        'limitations':['Identical titles may represent distinct versions. Equal DOI may still hide contradictory metadata. No merge is automatic.']})


def export_reference_library(path: str, output_format: str) -> dict:
    """Export normalized records to CSL-JSON, RIS or BibTeX with explicit field-loss warnings and source provenance."""
    records, source = load_library(path)
    if output_format == 'csl-json':
        data = []
        for r in records:
            if source['format']=='json' and r.get('source_fields',{}).get('type') and isinstance(r['source_fields'].get('author',[]),list): item=dict(r['source_fields'])
            else: item={'type':{'BOOK':'book','book':'book','THES':'thesis','thesis':'thesis','CONFERENCE':'paper-conference','conferencePaper':'paper-conference'}.get(r.get('type'),'article-journal'),'author':[{'literal':a} for a in r['authors']]}
            item.update(id=r['id'],title=r.get('title',''),DOI=r['doi'])
            for field,key in [('container_title','container-title'),('volume','volume'),('issue','issue'),('pages','page'),('publisher','publisher'),('url','URL'),('isbn','ISBN')]:
                if r.get(field):item[key]=r[field]
            year=re.match(r'\d{4}',str(r.get('year','')))
            if year:item['issued']={'date-parts':[[int(year.group())]]}
            data.append(item)
        name='references.json'; content=json.dumps(data,ensure_ascii=False,indent=2)
    elif output_format == 'ris':
        blocks=[]
        for r in records:
            kind={'book':'BOOK','thesis':'THES','paper-conference':'CONF','conferencePaper':'CONF'}.get(r.get('type'),'JOUR')
            fields={'TY':[kind],'ID':[r['id']],'TI':[r.get('title','')],'DO':[r['doi']],'PY':[str(r.get('year',''))],'AU':r['authors']}
            for field,key in [('container_title','JO'),('volume','VL'),('issue','IS'),('pages','SP'),('publisher','PB'),('url','UR'),('isbn','SN')]:
                if r.get(field):fields[key]=[r[field]]
            if source['format']=='ris':fields={**r['source_fields'],**{k:v for k,v in fields.items() if k not in r['source_fields']}}
            for values in fields.values():
                if any('\n' in str(v) or '\r' in str(v) for v in values): raise ValueError('Multiline RIS fields require manual export review')
            blocks.append('\n'.join(k+'  - '+str(v) for k,vs in fields.items() for v in vs)+'\nER  -\n')
        name='references.ris';content='\n'.join(blocks)
    elif output_format == 'bibtex':
        blocks=[]
        for r in records:
            if not re.fullmatch(r'[A-Za-z0-9_:.-]+',r['id']): raise ValueError('BibTeX keys require an explicit safe key mapping')
            if any(v.startswith('unexpanded_macro:') for v in r.get('issues',[])):raise ValueError('Resolve BibTeX macros before exporting to avoid changing their meaning')
            fields={'title':r.get('title',''),'doi':r['doi'],'year':str(r.get('year','')),'author':' and '.join(r['authors'])}
            for field,key in [('container_title','journal'),('volume','volume'),('issue','number'),('pages','pages'),('publisher','publisher'),('url','url'),('isbn','isbn')]:
                if r.get(field):fields[key]=r[field]
            if source['format'] in {'bib','bibtex'}: fields={**r['source_fields'],**fields}
            for value in fields.values():
                if str(value).count('{')!=str(value).count('}'):raise ValueError('Unbalanced braces require manual BibTeX review')
            kind={'BOOK':'book','book':'book','thesis':'phdthesis','THES':'phdthesis','conferencePaper':'inproceedings','paper-conference':'inproceedings'}.get(r.get('type'),'article')
            blocks.append('@'+kind+'{'+r['id']+',\n'+',\n'.join('  '+k+' = {'+str(v)+'}' for k,v in fields.items() if v)+'\n}')
        name='references.bib';content='\n\n'.join(blocks)
    else: raise ValueError('Choose csl-json, ris or bibtex')
    return artifact('library_export',{'source':source,'output_format':output_format,'record_count':len(records),
        'limitations':['Exchange is not lossless synchronization. Normalized author strings do not infer family names.','Review type, keys, TeX macros and software-specific fields before import.']}, {name:content})


def index_pdf_folder(folder: str, max_files: int = 100) -> dict:
    """Hash and extract DOI candidates from one explicit nonrecursive local PDF folder; no upload or automatic DOI assignment."""
    if type(max_files) is not int or not 1<=max_files<=100:raise ValueError('Select 1 to 100 PDFs')
    directory=Path(folder).resolve(strict=True)
    if not directory.is_dir():raise ValueError('Provide a PDF folder')
    from pypdf import PdfReader
    files=sorted(directory.glob('*.pdf')); output=[]
    for p in files[:max_files]:
        try:
            source,raw=read_file(p,10_000_000);reader=PdfReader(__import__('io').BytesIO(raw))
            value='\n'.join(page.extract_text() or '' for page in list(reader.pages)[:3])
            output.append({'file':str(source),'sha256':digest(raw),'pages':len(reader.pages),'doi_candidates':sorted(set(re.findall(r'10\.\d{4,9}/[^\s<>]+',value)))[:20],
                           'state':'metadata_candidates_only','ocr_required':not value.strip()})
        except Exception as exc:output.append({'file':str(p),'state':'failed','error_type':type(exc).__name__})
    return artifact('pdf_inventory',{'records':output,'coverage_complete':len(files)<=max_files,
        'limitations':['Only the first three pages provide DOI candidates; references can contain unrelated DOIs.','Hashes detect equal bytes, not identical studies. No OCR, recursive scan or full-library upload occurs.']})
