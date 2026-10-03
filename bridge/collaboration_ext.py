"""Private evidence-backed manuscript collaboration; no external messaging, model or automatic publication."""
import difflib
import html
import io
import json
import re
import zipfile
from datetime import datetime,timezone
from academic_common import W, artifact, digest, docx_parts, locate, manuscript, normalized, read_file, rows, text, unique
from library_ext import load_library


def plan_manuscript(study: dict, results: list, target_journal: str = '') -> dict:
    """Prepare a section/figure/evidence plan from explicit completed/planned results and statistical consultation; invent no results."""
    from statistics_ext import guide_study_statistics
    guidance=guide_study_statistics(study);results=rows(results,200);unique(results)
    for r in results:
        if r.get('state') not in {'completed','partial','planned','failed','negative'}:raise ValueError('Declare each result state explicitly')
        text(r.get('description'))
        if r['state'] in {'completed','partial','negative'} and not r.get('source_sha256'):raise ValueError('Reported results require a source fingerprint')
        if r.get('source_path'):
            _,raw=read_file(r['source_path'])
            if digest(raw)!=r.get('source_sha256'):raise ValueError('Result source fingerprint mismatch')
        r['source_verification']='verified_local_hash' if r.get('source_path') else 'declared_not_checked'
    outline=[{'section':'Introduction','purpose':'Define the question, evidence gap and intended estimand','required_evidence':['primary_studies','opposing_evidence']},
             {'section':'Methods','purpose':'Declare units, design, QC, outcomes, missingness and complete test family','required_evidence':['analysis_plan','source_provenance','software_versions']},
             {'section':'Results','purpose':'Report completed and negative outcomes with effects and uncertainty','result_ids':[r['id'] for r in results if r['state'] in {'completed','negative'}]},
             {'section':'Discussion','purpose':'Interpret within species/model/assay and causal limits; discuss competing explanations','required_evidence':['limitations','alternative_explanations']},
             {'section':'Declarations','purpose':'Confirm ethics, contributions, funding, conflicts and data/code availability','required_evidence':['author_confirmed_statements']}]
    return artifact('manuscript_plan',{'study':study,'target_journal':target_journal,'statistics_consultation':guidance,'outline':outline,'results':results,
        'figure_plan':[{'result_id':r['id'],'caption_requires':['independent_unit','contrast','effect','uncertainty','method','source']} for r in results if r['state'] in {'completed','negative'}],
        'limitations':['This is an organizational plan, not authored scientific evidence or a journal acceptance prediction.','Source hashes establish integrity only. Planned/failed work is excluded from completed Results.','No coauthor is contacted and no document is shared.']})


def build_evidence_draft(title: str, sections: list, references_path: str, evidence_ids: list) -> dict:
    """Assemble supplied authored paragraphs into Markdown/LaTeX plus a citation map; require evidence IDs or explicit unresolved marking."""
    text(title,500);sections=rows(sections,30);refs,source=load_library(references_path);refids={r['id'] for r in refs}
    if not isinstance(evidence_ids,list) or len(evidence_ids)>1000 or any(not isinstance(e,str) for e in evidence_ids):raise ValueError('Provide explicit reviewed evidence IDs')
    evidence=set(evidence_ids);markdown=['# '+title];latex=[];mapping=[]
    def tex_escape(v):
        replacements={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
        return ''.join(replacements.get(c,c) for c in v)
    for section in sections:
        heading=text(section.get('heading'),200);markdown.extend(['','## '+heading]);latex.append(r'\section{'+tex_escape(heading)+'}')
        for index,p in enumerate(rows(section.get('paragraphs',[]),100),1):
            value=text(p.get('text'),20000);citations=p.get('reference_ids',[]);links=p.get('evidence_ids',[])
            if not isinstance(citations,list) or not isinstance(links,list) or not set(citations)<=refids or not set(links)<=evidence:raise ValueError('Paragraph cites an unknown reference/evidence ID')
            state=p.get('state','unresolved')
            if state not in {'reviewed','unresolved'}:raise ValueError('Paragraph state must be reviewed or unresolved')
            if state=='reviewed' and not links:raise ValueError('Reviewed paragraphs require evidence links, including methods/result evidence')
            marker='' if state=='reviewed' else '[待核验] '
            markdown.extend(['',marker+value+(' ['+'; '.join('@'+c for c in citations)+']' if citations else '')])
            if any(not re.fullmatch(r'[A-Za-z0-9_:.-]+',c) for c in citations):raise ValueError('LaTeX citations require safe reference keys')
            latex.append(tex_escape(marker+value)+(r' \cite{'+','.join(citations)+'}' if citations else '')+'\n')
            mapping.append({'section':heading,'paragraph':index,'reference_ids':citations,'evidence_ids':links,'state':state})
    return artifact('evidence_draft',{'citation_evidence_map':mapping,'bibliography_source':source,
        'limitations':['Paragraphs and reviewed labels are supplied by Codex/humans; this function does not invent or verify scientific prose.','LaTeX is a section fragment for an existing project, not a compiled standalone document.','Citation rendering needs the native reference plugin or a verified CSL/BibTeX workflow.']},
        {'manuscript.md':'\n'.join(markdown)+'\n','manuscript_sections.tex':'\n'.join(latex),'citation_map.json':json.dumps(mapping,ensure_ascii=False,indent=2)})


def _citations(doc):
    value='\n'.join(s['text'] for s in doc['segments'])
    textkeys=re.findall(r'\\(?:[A-Za-z]*cite[A-Za-z]*)(?:\[[^\]]*\]){0,2}\{[^}]+\}|(?<!\w)@[A-Za-z0-9_:.-]+',value)
    fields=[f['instruction'] for f in doc['fields_and_comments'] if f.get('instruction')]
    return textkeys,fields


def compare_manuscript_versions(before_path: str, after_path: str) -> dict:
    """Compare located current text and complete Word citation instructions between two explicit files; do not merge or decide scientific correctness."""
    before=manuscript(before_path);after=manuscript(after_path)
    a=[s['text'] for s in before['segments']];b=[s['text'] for s in after['segments']]
    changes=[]
    for op,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if op!='equal':changes.append({'operation':op,'before_locations':[s['location'] for s in before['segments'][i:j]],
                                       'after_locations':[s['location'] for s in after['segments'][k:l]],'before':a[i:j],'after':b[k:l]})
    ca,fa=_citations(before);cb,fb=_citations(after)
    patch='\n'.join(difflib.unified_diff(a,b,fromfile='before',tofile='after',lineterm=''))
    return artifact('manuscript_diff',{'before_sha256':before['source_sha256'],'after_sha256':after['source_sha256'],'changes':changes,
        'citation_text_sequence_unchanged':ca==cb,'word_field_instructions_unchanged':fa==fb,
        'removed_citation_candidates':sorted(set(ca)-set(cb)),'added_citation_candidates':sorted(set(cb)-set(ca)),
        'limitations':['Matching text/fields does not verify numbers, logic, rendering or Word plugin behavior.','Changes in paragraph indexes do not establish author attribution. No automatic merge or sharing.']},{'changes.diff':patch})


def prepare_manuscript_revision(manuscript_path: str, edits: list, expected_source_sha256: str) -> dict:
    """Produce a fresh Markdown/LaTeX/text revision or conservative Word tracked revision; protect all citation instructions and refuse complex/protected paragraphs."""
    p,raw=read_file(manuscript_path)
    if digest(raw)!=expected_source_sha256:raise ValueError('Manuscript changed since review')
    doc=manuscript(manuscript_path);edits=rows(edits,200)
    if not edits:raise ValueError('Provide explicit located edits')
    locations=set();instructions=[]
    for e in edits:
        location=e.get('location');old=text(e.get('old_text'),20000);new=text(e.get('new_text'),20000);segment=locate(doc,location)
        if location in locations:raise ValueError('Combine edits at the same location')
        locations.add(location)
        if segment.get('protected') or segment.get('existing_revisions'):raise ValueError('Citation fields or existing tracked revisions require native Word review')
        if segment['text']!=old:raise ValueError('Edit must match the complete reviewed paragraph/line exactly')
        # Citation command/key sequences cannot be silently inserted, removed or changed.
        ca=_citations({'segments':[{'text':old}],'fields_and_comments':[]})[0]
        cb=_citations({'segments':[{'text':new}],'fields_and_comments':[]})[0]
        if ca!=cb:raise ValueError('Citation changes require a separate reviewed reference workflow')
        instructions.append({'location':location,'old_text':old,'new_text':new,'reason':text(e.get('reason'))})
    if p.suffix.lower() in {'.md','.txt','.tex'}:
        value=raw.decode('utf-8-sig');lines=value.splitlines(keepends=True)
        for e in instructions:
            index=int(e['location'].split(':')[1])-1
            if '\n' in e['new_text'] or '\r' in e['new_text']:raise ValueError('Line edits cannot insert new lines')
            ending='\r\n' if lines[index].endswith('\r\n') else '\n' if lines[index].endswith('\n') else ''
            lines[index]=e['new_text']+ending
        revised=''.join(lines).encode('utf8');name='revised'+p.suffix.lower();mode='located_text_edits'
    elif p.suffix.lower()=='.docx':
        parts=docx_parts(raw);xml=parts['word/document.xml'].decode('utf8')
        if '<w:document' not in xml:raise ValueError('Unsupported Word namespace prefix; use native editor')
        matches=list(re.finditer(r'<w:p(?=[\s/>])(?:[^>]*?/>|[^>]*>.*?</w:p>)',xml,re.S))
        if len(matches)!=len(doc['segments']):raise ValueError('Unsupported nested paragraph structure')
        replacements=[];revision_ids=[int(v) for v in re.findall(r'<w:(?:ins|del)\b[^>]*w:id="(\d+)"',xml)]
        rid=max(revision_ids+[0])+1;when=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        from academic_common import safe_xml
        for e in instructions:
            index=int(e['location'].split(':')[1])-1;m=matches[index];paragraph=m.group()
            # Preserve original namespaces, paragraph properties and package bytes. Only simple text runs are supported.
            node=list(safe_xml(parts['word/document.xml']).iter('{'+W+'}p'))[index]
            if any(c.tag not in {'{'+W+'}pPr','{'+W+'}r'} for c in node):raise ValueError('Complex Word paragraph requires native editing')
            runs=[c for c in node if c.tag=='{'+W+'}r']
            if not runs or any(c.tag not in {'{'+W+'}rPr','{'+W+'}t'} for run in runs for c in run):raise ValueError('Non-text Word runs require native editing')
            import xml.etree.ElementTree as ET
            formats={ET.tostring(run.find('{'+W+'}rPr')) if run.find('{'+W+'}rPr') is not None else b'' for run in runs}
            if len(formats)>1:raise ValueError('Mixed inline formatting requires native editing')
            raw_runs=list(re.finditer(r'<w:r(?:\s[^>]*)?>.*?</w:r>',paragraph,re.S))
            if len(raw_runs)!=len(runs):raise ValueError('Unsupported Word run structure')
            oldruns=''.join(r.group() for r in raw_runs)
            deleted=re.sub(r'<(/?)w:t(?=[\s>])',r'<\1w:delText',oldruns)
            style=re.search(r'<w:rPr(?:\s[^>]*)?>.*?</w:rPr>',raw_runs[0].group(),re.S)
            style=style.group() if style else ''
            replacement='<w:del w:id="'+str(rid)+'" w:author="Academic Reviewer" w:date="'+when+'">'+deleted+'</w:del>'
            replacement+='<w:ins w:id="'+str(rid+1)+'" w:author="Academic Reviewer" w:date="'+when+'"><w:r>'+style+'<w:t xml:space="preserve">'+html.escape(e['new_text'])+'</w:t></w:r></w:ins>';rid+=2
            start,end=raw_runs[0].start(),raw_runs[-1].end()
            updated=paragraph[:start]+replacement+paragraph[end:]
            replacements.append((m.start(),m.end(),updated))
        for start,end,value in sorted(replacements,reverse=True):xml=xml[:start]+value+xml[end:]
        safe_xml(xml.encode('utf8'));parts['word/document.xml']=xml.encode('utf8')
        buffer=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as original,zipfile.ZipFile(buffer,'w') as dest:
            for info in original.infolist():dest.writestr(info,parts[info.filename])
        revised=buffer.getvalue();name='revised.docx';mode='tracked_changes_simple_paragraphs'
    else:raise ValueError('PDF is read-only. Revise Markdown, text, LaTeX or simple DOCX paragraphs')
    return artifact('manuscript_revision',{'source_sha256':digest(raw),'revised_sha256':digest(revised),'mode':mode,'edits':instructions,
        'limitations':['The original file is preserved. Native Word/Zotero refresh and rendered review are required before submission.','Word field-bearing, mixed-format, complex and already-revised paragraphs are refused instead of flattened.','This function preserves package parts and creates tracked changes; it does not verify layout or plugin execution.']},{name:revised})


def manage_collaboration_review(manuscript_path: str, comments: list) -> dict:
    """Prepare a located comment/action ledger with dependencies and source hashes; never send messages or change author attribution."""
    doc=manuscript(manuscript_path);comments=rows(comments,1000);ids=set(unique(comments));ledger=[]
    for c in comments:
        locate(doc,c.get('location'));text(c.get('comment'));state=c.get('state','open')
        if state not in {'open','in_progress','resolved','deferred','disagreed'}:raise ValueError('Invalid comment state')
        dependencies=c.get('depends_on',[])
        if not isinstance(dependencies,list) or not set(dependencies)<=ids or c['id'] in dependencies:raise ValueError('Invalid comment dependencies')
        if state in {'resolved','deferred','disagreed'} and not str(c.get('resolution','')).strip():raise ValueError('Closed/deferred/disagreed comments require reasons')
        ledger.append({**c,'state':state,'source_sha256':doc['source_sha256']})
    graph={c['id']:c.get('depends_on',[]) for c in ledger};visiting=set();done=set()
    def visit(k):
        if k in visiting:raise ValueError('Comment dependency cycle')
        if k in done:return
        visiting.add(k)
        for dep in graph[k]:visit(dep)
        visiting.remove(k);done.add(k)
    for k in graph:visit(k)
    for c in ledger:
        c['dependency_blocked']=any(next(r for r in ledger if r['id']==d)['state']!='resolved' for d in c.get('depends_on',[]))
        if c['state']=='resolved' and c['dependency_blocked']:raise ValueError('A resolved comment has unresolved dependencies')
    return artifact('collaboration_ledger',{'source_sha256':doc['source_sha256'],'comments':ledger,
        'limitations':['The ledger is a private sidecar, not a live multiuser editor or automatic Word comment writeback.','Owners and resolutions are declared by the caller, not inferred from document versions. No messages or files are shared.']})


def prepare_reviewer_response(manuscript_path: str, responses: list) -> dict:
    """Generate an editable point-by-point response with exact revised locations and explicit completed/planned/declined states."""
    doc=manuscript(manuscript_path);responses=rows(responses,500);unique(responses);output=[];markdown=['# Response to reviewers']
    for r in responses:
        text(r.get('comment'));answer=text(r.get('response'));state=r.get('state')
        if state not in {'completed','planned','declined','clarification'}:raise ValueError('Declare the response action state')
        locations=r.get('locations',[])
        if not isinstance(locations,list) or len(locations)>50:raise ValueError('Provide bounded revision locations')
        quotes=[]
        for loc in locations:quotes.append({'location':loc,'text':locate(doc,loc)['text']})
        if state=='completed' and not quotes:raise ValueError('Completed revisions require actual revised locations')
        if state in {'declined','planned'} and not str(r.get('rationale','')).strip():raise ValueError('Explain declined or planned work')
        if r.get('result_path'):
            _,raw=read_file(r['result_path'])
            if digest(raw)!=r.get('result_sha256'):raise ValueError('Response analysis source hash mismatch')
        output.append({**r,'located_revisions':quotes})
        markdown.extend(['','## '+r['id'],'','**Comment:** '+r['comment'],'','**Response ('+state+'):** '+answer])
        for q in quotes:markdown.extend(['','**Revision — '+q['location']+':** '+q['text']])
    return artifact('reviewer_response',{'source_sha256':doc['source_sha256'],'responses':output,
        'limitations':['Responses are supplied and require scientific/author review. Located revisions do not prove an analysis was executed.','Result hashes establish source integrity only. Planned work is never labeled completed. No response is sent.']},{'response.md':'\n'.join(markdown)+'\n'})
