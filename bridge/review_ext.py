"""Evidence-located academic audits; deterministic checks remain separate from human scientific judgments."""
import json
import re
from collections import Counter
from datetime import date
from academic_common import artifact, canonical_doi, digest, locate, manuscript, normalized, read_file, rows, text, unique
from library_ext import load_library


def inspect_manuscript(path: str) -> dict:
    """Extract bounded located text and Word field/comment inventory privately; no OCR, upload or scientific assessment."""
    return artifact('manuscript_inventory',manuscript(path))


def audit_claim_evidence(manuscript_path: str, claims: list, references_path: str) -> dict:
    """Verify claim locations, reference IDs and exact located source excerpts; support judgments must be explicitly supplied by a reviewer."""
    document=manuscript(manuscript_path);references,_=load_library(references_path)
    refids={r['id'] for r in references};claims=rows(claims,500);unique(claims)
    output=[]
    for c in claims:
        assertion=text(c.get('claim'));segment=locate(document,c.get('location'));issues=[]
        if normalized(assertion) not in normalized(segment['text']):issues.append('claim_not_found_at_location')
        evidence=rows(c.get('evidence',[]),30);checks=[]
        if not evidence:issues.append('no_evidence_supplied')
        for e in evidence:
            decision=e.get('decision','unassessed')
            if decision not in {'supports','contradicts','insufficient','unassessed','not_applicable'}:raise ValueError('Invalid reviewer decision')
            source=manuscript(e['source_path']);quote=text(e.get('quote'));located=locate(source,e.get('source_location'))
            verified=normalized(quote) in normalized(located['text'])
            if e.get('reference_id') not in refids:issues.append('unknown_reference_id')
            if not verified:issues.append('source_excerpt_not_found')
            if e.get('source_sha256')!=source['source_sha256']:issues.append('source_hash_missing_or_changed')
            required=('species','model','assay','independent_unit','contrast','limitations')
            missing=[k for k in required if not isinstance(e.get(k),str) or not e[k].strip()]
            if missing:issues.append('incomplete_evidence_context')
            if decision!='unassessed' and not str(e.get('rationale','')).strip():issues.append('reviewer_judgment_without_rationale')
            checks.append({'reference_id':e.get('reference_id'),'quote':quote,'source_location':e.get('source_location'),
                           'source_sha256':source['source_sha256'],'excerpt_located':verified,'missing_context':missing,
                           'reviewer_decision':decision,'rationale':e.get('rationale',''),'context':{k:e.get(k) for k in required}})
        if any(e['reviewer_decision']=='contradicts' for e in checks):issues.append('contradictory_evidence_requires_review')
        if not any(e['reviewer_decision']=='supports' for e in checks):issues.append('no_reviewer_confirmed_support')
        output.append({'id':c['id'],'claim':assertion,'location':c['location'],'evidence':checks,'issues':sorted(set(issues)),
                       'state':'review_required' if issues else 'located_with_reviewer_support'})
    return artifact('claim_audit',{'source_sha256':document['source_sha256'],'claims':output,
        'limitations':['An exact excerpt and hash establish location/integrity, not assertion truth.','Species, model, assay, causal language, negation and surrounding context require Codex/human review.','Evidence judgments are supplied by the reviewer; no semantic support is inferred automatically.']})


def audit_paper(manuscript_path: str, study: dict, reported_numbers: list = None) -> dict:
    """Combine statistical design consultation, explicit numeric consistency and located candidate reporting issues; never certify scientific quality."""
    from statistics_ext import guide_study_statistics
    document=manuscript(manuscript_path);guidance=guide_study_statistics(study);findings=[]
    patterns={'causal_language_candidate':r'\b(?:causes?|proves?|demonstrates causality|causal effect)\b|导致|证实.*因果',
              'computational_validation_candidate':r'\b(?:docking|molecular dynamics|prediction)\b.{0,100}\b(?:confirmed|validated|proved)\b|对接.{0,40}(?:证实|验证)',
              'significance_without_effect_candidate':r'\bp\s*[<=]\s*0\.0\d+\b|统计学显著',
              'novelty_claim_candidate':r'\b(?:first ever|for the first time|unprecedented)\b|首次|首个'}
    for segment in document['segments']:
        for rule,pattern in patterns.items():
            if re.search(pattern,segment['text'],re.I):findings.append({'rule':rule,'severity':'review','location':segment['location'],'excerpt':segment['text'][:1000],'state':'candidate_requires_context'})
    numerical=[]
    for r in rows(reported_numbers or [],500):
        label=text(r.get('label'),200);mentions=rows(r.get('mentions',[]),30)
        if len(mentions)<2:raise ValueError('Numeric comparison needs at least two explicit located mentions')
        verified=[]
        for m in mentions:
            value=str(m.get('value',''));unit=text(m.get('unit'),100)
            if not value.strip():raise ValueError('Provide exact reported values')
            present=bool(re.search(r'(?<![\d.])'+re.escape(value)+r'(?![\d.])',locate(document,m['location'])['text']))
            verified.append({'location':m['location'],'value':value,'unit':unit,'present':present})
        consistent=len({(m['value'],m['unit']) for m in verified})==1
        numerical.append({'label':label,'mentions':verified,'same_value_and_unit':consistent,'state':'consistent' if consistent and all(v['present'] for v in verified) else 'review_required'})
    return artifact('paper_audit',{'source_sha256':document['source_sha256'],'statistics_consultation':guidance,
        'candidate_findings':findings,'numeric_checks':numerical,'extraction_issues':document['extraction_issues'],
        'limitations':['Rules flag passages, including negations and quoted claims, for review; they do not decide causal validity.','Numeric checks compare supplied same-estimand mentions only; no automatic table/figure value extraction or statistical reanalysis.','No fabrication, image manipulation or overall scientific validity verdict is made.']})


REVIEW_TOPICS={
    'systematic':['question','protocol','search_strategy','search_dates','eligibility','selection','extraction','risk_of_bias','synthesis','heterogeneity','certainty','limitations'],
    'scoping':['question','protocol','search_strategy','search_dates','eligibility','selection','charting','evidence_map','limitations'],
    'narrative':['question','scope','source_selection','primary_sources','opposing_evidence','evidence_limits','limitations']}


def audit_review(manuscript_path: str, review_type: str, checklist: list, search_log: list, screening_records: list, evidence_records: list) -> dict:
    """Audit supplied review reporting, search logs, screening accounting and cohort overlap with original operational checks, not an official checklist certification."""
    if review_type not in REVIEW_TOPICS:raise ValueError('Select systematic, scoping or narrative review')
    document=manuscript(manuscript_path);checklist=rows(checklist,100);seen=set();checks=[]
    for item in checklist:
        topic=item.get('topic');state=item.get('state')
        if topic not in REVIEW_TOPICS[review_type] or topic in seen:raise ValueError('Choose distinct review topics')
        seen.add(topic)
        if state not in {'reported','not_reported','unclear','not_applicable'}:raise ValueError('Invalid checklist state')
        if state=='reported':
            quote=text(item.get('quote'));found=normalized(quote) in normalized(locate(document,item.get('location'))['text'])
        else:found=None
        if state=='not_applicable' and not str(item.get('rationale','')).strip():raise ValueError('Explain nonapplicability')
        checks.append({**item,'excerpt_located':found,'state':state if found is not False else 'unclear'})
    checks += [{'topic':t,'state':'not_assessed'} for t in REVIEW_TOPICS[review_type] if t not in seen]
    searches=rows(search_log,100);search_issues=[]
    for i,entry in enumerate(searches):
        missing=[k for k in ('database','query','searched_on','coverage_until','result_count','receipt_sha256') if entry.get(k) in (None,'')]
        if missing:search_issues.append({'search_index':i,'missing':missing})
        for k in ('searched_on','coverage_until'):
            if entry.get(k):date.fromisoformat(entry[k])
        if 'result_count' in entry and (type(entry['result_count']) is not int or entry['result_count']<0):raise ValueError('Search result counts must be nonnegative integers')
    screening=rows(screening_records,10000);unique(screening)
    decisions=Counter();screen_issues=[]
    for r in screening:
        if r.get('decision') not in {'duplicate','title_excluded','fulltext_excluded','included','pending','not_retrieved'}:raise ValueError('Invalid screening decision')
        decisions[r['decision']]+=1
        if r['decision'].endswith('excluded') and not str(r.get('reason','')).strip():screen_issues.append({'id':r['id'],'issue':'missing_exclusion_reason'})
    evidence=rows(evidence_records,5000);unique(evidence);cohorts={};datasets={}
    for r in evidence:
        for key,bucket in [('cohort_id',cohorts),('dataset_id',datasets)]:
            if r.get(key):bucket.setdefault(str(r[key]),[]).append(r['id'])
    overlaps=[{'basis':kind,'identifier':k,'records':v} for kind,bucket in [('cohort',cohorts),('dataset',datasets)] for k,v in bucket.items() if len(v)>1]
    included={r['id'] for r in screening if r['decision']=='included'};evidence_ids={r['id'] for r in evidence}
    return artifact('review_audit',{'source_sha256':document['source_sha256'],'review_type':review_type,'checklist':checks,
        'search_log_issues':search_issues,'screening_counts':dict(decisions),'screening_issues':screen_issues,
        'screening_total':len(screening),'unmapped_included_records':sorted(included-evidence_ids),'evidence_not_included':sorted(evidence_ids-included),
        'overlap_candidates':overlaps,'search_coverage_declared':bool(searches),
        'limitations':['This operational checklist is not the complete official PRISMA/PRISMA-ScR checklist or a risk-of-bias instrument.','Counts describe supplied records only, not verified exhaustive database coverage.','Cohort/dataset IDs require source verification; absent IDs cannot establish independent studies.']})


def audit_manuscript_format(manuscript_path: str, references_path: str, journal_rules: dict = None, citation_mapping: dict = None) -> dict:
    """Check located citations, headings, figure/table mentions and explicit versioned journal rules; no automatic formatting or live guideline assumption."""
    document=manuscript(manuscript_path);refs,_=load_library(references_path);ids={r['id'] for r in refs};findings=[];citations=[];heads=[]
    for s in document['segments']:
        v=s['text']
        for m in re.finditer(r'\\(?:[A-Za-z]*cite[A-Za-z]*)(?:\[[^\]]*\]){0,2}\{([^}]+)\}',v):
            citations.extend({'id':x.strip(),'location':s['location']} for x in m.group(1).split(','))
        citations.extend({'id':m.group(1),'location':s['location']} for m in re.finditer(r'(?<![\w\\])@([A-Za-z0-9_:.-]+)',v))
        if re.match(r'^#{1,6}\s',v):heads.append({'title':v.lstrip('# ').strip(),'location':s['location']})
        for m in re.finditer(r'\\(?:sub)*section\*?\{([^}]+)\}',v):heads.append({'title':m.group(1),'location':s['location']})
        if re.search(r'\b(?:TODO|TBD|FIXME)\b|待补充|待核验',v):findings.append({'rule':'unresolved_placeholder','location':s['location'],'severity':'review'})
    embedded=[]
    for f in document['fields_and_comments']:
        instruction=f.get('instruction','')
        if 'ZOTERO_ITEM CSL_CITATION' in instruction:
            try:
                value=json.loads(instruction[instruction.index('{'):]);embedded.extend({'id':str(c.get('id','')),'location':f['location'],'uris':c.get('uris',[])} for c in value.get('citationItems',[]))
            except (ValueError,TypeError):findings.append({'rule':'unparsed_zotero_field','location':f['location'],'severity':'review'})
        elif 'EN.CITE' in instruction:findings.append({'rule':'endnote_field_requires_native_refresh','location':f['location'],'severity':'review'})
    mapping=citation_mapping or {}
    if not isinstance(mapping,dict) or len(mapping)>5000 or any(not isinstance(k,str) or not isinstance(v,str) or v not in ids for k,v in mapping.items()):raise ValueError('Citation mapping must point to known bibliography IDs')
    mapped_word=[]
    for c in embedded:
        possible=[mapping[c['id']]] if c['id'] in mapping else []
        for uri in c['uris']:
            key=str(uri).rstrip('/').rsplit('/',1)[-1]
            if key in ids:possible.append(key)
        possible=sorted(set(possible))
        mapped_word.append({**c,'reference_ids':possible,'state':'mapped' if len(possible)==1 else 'ambiguous_or_unmapped'})
        if len(possible)==1:citations.append({'id':possible[0],'location':c['location']})
        else:findings.append({'rule':'word_citation_mapping_required','location':c['location'],'severity':'review'})
    unknown=[c for c in citations if c['id'] not in ids]
    for c in unknown:findings.append({'rule':'unknown_citation_key',**c,'severity':'error'})
    # Numeric citations are detected but require a supplied numbered bibliography mapping.
    numeric=[{'location':s['location'],'text':m.group(0)} for s in document['segments'] for m in re.finditer(r'\[(?:\d+[,-]?\s*)+\]',s['text'])]
    full='\n'.join(s['text'] for s in document['segments']);words=len(re.findall(r'\b\w+\b|[\u4e00-\u9fff]',full))
    rules=journal_rules or {};rule_results=[]
    if rules:
        for key in ('journal','source_url','checked_on','version'):
            text(rules.get(key),2000)
        if not rules['source_url'].startswith('https://'):raise ValueError('Journal rules need an official HTTPS source URL')
        date.fromisoformat(rules['checked_on'])
        if rules.get('max_words') is not None:
            if type(rules['max_words']) is not int or rules['max_words']<1:raise ValueError('Invalid word limit')
            rule_results.append({'rule':'max_words','pass':words<=rules['max_words'],'actual':words,'limit':rules['max_words']})
        for heading in rules.get('required_sections',[]):
            text(heading,200);present=any(normalized(heading) in normalized(s['text']) for s in document['segments'])
            rule_results.append({'rule':'required_section','section':heading,'candidate_present':present,'state':'review_required' if present else 'not_found'})
        for label in rules.get('required_statements',[]):
            text(label,200);present=normalized(label) in normalized(full)
            rule_results.append({'rule':'required_statement','label':label,'candidate_present':present,'state':'review_required' if present else 'not_found'})
        for rule in rows(rules.get('exact_patterns',[]),50):
            # Literal text checks, not arbitrary regular expressions from external documents.
            value=text(rule.get('literal'),500);rule_results.append({'rule':text(rule.get('id'),100),'literal':value,'present':value in full})
    mentions={kind:sorted({int(m.group(1)) for m in re.finditer(pattern,full,re.I)}) for kind,pattern in {
        'figure':r'(?:\bFig(?:ure)?\.?\s*|图\s*)(\d+)','table':r'(?:\bTable\s*|表\s*)(\d+)'}.items()}
    for kind,numbers in mentions.items():
        if numbers and set(range(1,max(numbers)+1))-set(numbers):findings.append({'rule':'numbering_gap_candidate','kind':kind,'numbers':numbers,'severity':'review'})
    return artifact('format_audit',{'source_sha256':document['source_sha256'],'findings':findings,'citation_keys':citations,'embedded_zotero_citations':embedded,
        'mapped_word_citations':mapped_word,'numeric_citations_requiring_mapping':numeric,'uncited_reference_keys':sorted(ids-{c['id'] for c in citations}),
        'headings':heads,'figure_table_mentions':mentions,'word_count_approximate':words,'journal_rules':rules,'journal_rule_checks':rule_results,
        'scope':'supplied_journal_rules' if rules else 'generic_checks_only','extraction_issues':document['extraction_issues'],
        'limitations':['Word counts, headings and numbering are text candidates; captions and journal-specific exclusions require review.','Embedded Word item IDs need a Zotero URI/key mapping; they are not assumed to equal exported bibliography IDs.','No rendered typography, citation-style compliance or complete abbreviation/unit check is claimed.','Official journal rules must be verified by Codex at the stated source/date before supplying them.']})


def audit_terminology_units(manuscript_path: str, glossary: list, quantity_rules: list) -> dict:
    """Check explicit abbreviation definitions, first-use order and declared quantity/unit mentions; do not invent expansions or convert units."""
    document=manuscript(manuscript_path);glossary=rows(glossary,200);quantity_rules=rows(quantity_rules,200);findings=[]
    full='\n'.join(s['text'] for s in document['segments'])
    for g in glossary:
        abbreviation=text(g.get('abbreviation'),50);expansion=text(g.get('expansion'),300)
        pattern=re.compile(r'(?<!\w)'+re.escape(abbreviation)+r'(?!\w)')
        occurrences=[{'location':s['location'],'text':s['text']} for s in document['segments'] if pattern.search(s['text'])]
        definitions=[expansion+' ('+abbreviation+')',abbreviation+' ('+expansion+')',expansion+'（'+abbreviation+'）']
        first=pattern.search(full);definition_positions=[full.find(v) for v in definitions if v in full]
        findings.append({'kind':'abbreviation','abbreviation':abbreviation,'expansion':expansion,'occurrences':occurrences,
                         'definition_found':bool(definition_positions),'definition_before_first_use':bool(first and definition_positions and min(definition_positions)<=first.start()),
                         'state':'not_used' if not occurrences else 'review_required' if not definition_positions else 'definition_located'})
    for q in quantity_rules:
        label=text(q.get('quantity'),100);unit=text(q.get('expected_unit'),100)
        mentions=rows(q.get('mentions',[]),100);checks=[]
        for m in mentions:
            value=text(m.get('literal'),200);segment=locate(document,m.get('location'))
            checks.append({'location':m['location'],'literal':value,'located':value in segment['text'],
                           'expected_unit_present':unit in value,'declared_unit':m.get('unit'),
                           'unit_matches_declared_rule':m.get('unit')==unit})
        findings.append({'kind':'quantity_unit','quantity':label,'expected_unit':unit,'checks':checks,
                         'state':'checked_supplied_mentions_only' if checks else 'not_assessed'})
    return artifact('terminology_audit',{'source_sha256':document['source_sha256'],'checks':findings,
        'limitations':['Definitions and units come from a reviewed caller-supplied glossary. No domain expansion or dimensional conversion is guessed.','Case-sensitive literal checks flag locations for review; references and table headings may need exclusions.','Only supplied quantities/mentions are checked; this does not certify all manuscript terminology or SI compliance.']})


def find_similar_studies(public_queries: list, comparison: dict, public_query_authorized: bool = False, max_results_per_query: int = 25) -> dict:
    """Search explicitly approved public queries in Europe PMC and rerank returned metadata with transparent lexical/facet overlap; never transmit a draft."""
    if public_query_authorized is not True:raise ValueError('Approve the exact public query strings before retrieval')
    if not isinstance(public_queries,list) or not 1<=len(public_queries)<=5:raise ValueError('Select 1 to 5 public queries')
    if type(max_results_per_query) is not int or not 1<=max_results_per_query<=100:raise ValueError('Select a bounded public search page')
    from literature_ext import query_europepmc
    from privacy_ext import enforce_outbound
    queries=[text(q,1000) for q in public_queries];enforce_outbound({'queries':queries})
    # Comparison fields are used locally and are never attached to network calls.
    facets={k:comparison.get(k,[]) for k in ('question_terms','species','tissue','intervention','methods','endpoints','dataset_ids')}
    for vals in facets.values():
        if not isinstance(vals,list) or len(vals)>50 or any(not isinstance(v,str) or not v.strip() or len(v)>200 for v in vals):raise ValueError('Facets must be bounded lists of terms')
    retrieved={};searches=[]
    for query in queries:
        response=query_europepmc(query,max_results_per_query);r=response.get('result',{})
        if not response.get('success'):raise RuntimeError('Public metadata search failed; no exhaustive search claim is possible')
        found=r.get('resultList',{}).get('result',[])
        searches.append({'database':'Europe PMC','query':query,'hit_count':r.get('hitCount'),'returned':len(found),'next_cursor':r.get('nextCursorMark'),'coverage_complete':int(r.get('hitCount',0))<=len(found)})
        for item in found:
            key=canonical_doi(item.get('doi','')) or str(item.get('source',''))+':'+str(item.get('id',''))
            retrieved[key]=item
    candidates=[]
    for key,item in retrieved.items():
        body=normalized(item.get('title','')+' '+item.get('abstractText','')+' '+json.dumps(item.get('keywordList',{})))
        matched={k:[term for term in vals if normalized(term) in body] for k,vals in facets.items()}
        total=sum(len(v) for v in facets.values());score=sum(len(v) for v in matched.values())/total if total else 0
        candidates.append({'identifier':key,'title':item.get('title'),'year':item.get('pubYear'),'doi':item.get('doi'),
            'pmid':item.get('id') if item.get('source')=='MED' else None,'pmcid':item.get('pmcid'),'matched_facets':matched,
            'metadata_overlap_score':score,'dataset_overlap_candidates':matched['dataset_ids'],'metadata':item,'state':'source_review_required'})
    candidates.sort(key=lambda r:(-r['metadata_overlap_score'],r['identifier']))
    return artifact('similar_studies',{'searches':searches,'candidates':candidates,'local_comparison':facets,
        'limitations':['Metadata overlap is a transparent retrieval aid, not semantic equivalence, study eligibility, plagiarism or novelty assessment.','Only bounded first pages are retrieved. No absent-hit guarantee, exhaustive review or global-first claim is possible.','Species, tissue, direction, cohort overlap and independent units must be verified from original studies.','Only approved queries leave the device; private comparison fields are used locally.']})


def check_publication_updates(dois: list, public_query_authorized: bool = False) -> dict:
    """Query Crossref deposited update/retraction relationships for explicit public DOIs; absence of records is not proof of publication integrity."""
    if public_query_authorized is not True or not isinstance(dois,list) or not 1<=len(dois)<=25:raise ValueError('Approve 1 to 25 public DOI queries')
    from literature_ext import doi_metadata
    results=[]
    for value in dois:
        doi=canonical_doi(value)
        if not doi:raise ValueError('Invalid public DOI')
        try:
            data=doi_metadata(doi)['result']['message']
            updates=data.get('update-to',[]);relation=data.get('relation',{})
            results.append({'doi':doi,'update_to':updates,'relations':relation,'has_deposited_update':bool(updates or relation),
                            'state':'metadata_requires_review','source':'Crossref','deposited':data.get('deposited')})
        except Exception as exc:results.append({'doi':doi,'state':'query_failed','error_type':type(exc).__name__})
    return artifact('publication_updates',{'records':results,'limitations':['Crossref integrates deposited updates and Retraction Watch data, but coverage and relationship direction need review.','Query failure or no update metadata must never be reported as not retracted or scientifically reliable.']})


def audit_reporting_checklist(manuscript_path: str, checklist_profile: dict, assessments: list) -> dict:
    """Apply a supplied versioned PRISMA/CONSORT/STROBE/ARRIVE or journal checklist with located reviewer assessments, preserving unassessed items."""
    document=manuscript(manuscript_path);profile=checklist_profile
    for k in ('name','version','source_url','checked_on'):text(profile.get(k),2000)
    if not profile['source_url'].startswith('https://'):raise ValueError('Provide an official HTTPS checklist source')
    date.fromisoformat(profile['checked_on']);items=rows(profile.get('items',[]),200);ids=set(unique(items))
    if not items:raise ValueError('Provide complete intended checklist items')
    for item in items:text(item.get('requirement'),2000)
    assessments=rows(assessments,200);unique(assessments);byid={a['id']:a for a in assessments}
    if not set(byid)<=ids:raise ValueError('Assessment references an unknown checklist item')
    output=[]
    for item in items:
        a=byid.get(item['id'],{'id':item['id'],'state':'not_assessed'});state=a.get('state')
        if state not in {'reported','not_reported','unclear','not_applicable','not_assessed'}:raise ValueError('Invalid checklist assessment')
        evidence=[]
        for excerpt in rows(a.get('excerpts',[]),20):
            quote=text(excerpt.get('quote'));segment=locate(document,excerpt.get('location'))
            evidence.append({**excerpt,'located':normalized(quote) in normalized(segment['text'])})
        issues=[]
        if state=='reported' and (not evidence or not all(e['located'] for e in evidence)):issues.append('reported_without_located_evidence')
        if state in {'reported','unclear','not_applicable'} and not str(a.get('rationale','')).strip():issues.append('missing_review_rationale')
        output.append({'id':item['id'],'requirement':item['requirement'],'reviewer_state':state,'excerpts':evidence,'rationale':a.get('rationale',''),'issues':issues})
    return artifact('reporting_checklist',{'source_sha256':document['source_sha256'],'profile':profile,'assessments':output,
        'limitations':['Checklist text/version/completeness and applicability must be verified at the official source before use.','Located text is not proof that a reported method was performed correctly.','No numeric quality score, risk-of-bias certification or automatic scientific judgment is produced.']})


def audit_reference_metadata(references_path: str, public_query_authorized: bool = False) -> dict:
    """Compare at most 25 explicitly selected DOI records to Crossref metadata; send DOIs only, never a private library or authors list."""
    if public_query_authorized is not True:raise ValueError('Approve the selected public DOI queries before metadata checks')
    records,source=load_library(references_path)
    if not 1<=len(records)<=25:raise ValueError('Select a reference subset of 1 to 25 records')
    from literature_ext import doi_metadata
    results=[]
    for r in records:
        if not r['doi']:results.append({'id':r['id'],'state':'no_valid_doi'});continue
        try:
            data=doi_metadata(r['doi'])['result']['message'];official_titles=data.get('title',[])
            candidates=[]
            if official_titles and normalized(r.get('title','')) not in {normalized(t) for t in official_titles}:candidates.append('title_differs')
            dates={str(data[k]['date-parts'][0][0]) for k in ('published','published-print','published-online','issued') if data.get(k,{}).get('date-parts',[[]])[0]}
            if r.get('year') and dates and str(r['year']) not in dates:candidates.append('year_differs')
            results.append({'id':r['id'],'doi':r['doi'],'state':'review_required' if candidates else 'queried_metadata_fields_match',
                'difference_candidates':candidates,'official_title':official_titles,'official_years':sorted(dates),'official_author_metadata':data.get('author',[]),
                'updates':data.get('update-to',[]),'relations':data.get('relation',{})})
        except Exception as exc:results.append({'id':r['id'],'state':'query_failed','error_type':type(exc).__name__})
    return artifact('reference_metadata',{'library_source':source,'records':results,
        'limitations':['Only DOI strings are sent; source records remain local.','Title/year normalization is a candidate check. Online/print dates, translations, authors and versions require review.','A matching DOI record does not establish citation support, publication integrity or absence of retraction.']})
