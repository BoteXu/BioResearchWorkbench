"""Private clinical research QC and located medical evidence; no autonomous diagnosis or prescribing."""
import collections
import datetime
import json
import math
import re
import shutil
from pathlib import Path
from urllib.parse import quote
from academic_common import artifact, read_file, digest, rows, text, manuscript, locate, normalized
from code_common import table, number, report, sha, canon, relative

HERE=Path(__file__).resolve().parent


def audit_medical_guidelines(sources: list, recommendations: list, target_population: dict, review_date: str) -> dict:
    """Locate recommendations in selected documents and audit versions, region/population applicability and supersession declarations."""
    datetime.date.fromisoformat(review_date)
    if not {'population','region','question'}<=set(target_population):raise ValueError('Explicit target population/region/question required')
    docs={};records=[]
    for s in rows(sources,30):
        if not {'id','path','publisher','version','published_on','region','population','official_source','retrieved_on'}<=set(s):raise ValueError('Guideline version/source metadata required')
        datetime.date.fromisoformat(s['published_on']);datetime.date.fromisoformat(s['retrieved_on'])
        if s['id'] in docs:raise ValueError('Duplicate guideline source')
        docs[s['id']]=(s,manuscript(s['path']))
    for r in rows(recommendations,200):
        if r.get('source_id') not in docs:raise ValueError('Unknown selected guideline')
        s,doc=docs[r['source_id']];segment=locate(doc,r['location']);excerpt=text(r.get('excerpt'),2000)
        if normalized(excerpt) not in normalized(segment['text']):raise ValueError('Recommendation is not at supplied location')
        issues=[]
        if s['region']!=target_population['region']:issues.append('region_applicability_review')
        if s['population']!=target_population['population']:issues.append('population_applicability_review')
        if s.get('superseded_by'):issues.append('declared_superseded_source')
        if s['published_on']>review_date or s['retrieved_on']>review_date:issues.append('inconsistent_review_date')
        if not r.get('recommendation_strength') or not r.get('evidence_level'):issues.append('recommendation_grade_unspecified')
        records.append({**r,'source_sha256':doc['source_sha256'],'version':s['version'],'publisher':s['publisher'],'issues':issues,'decision':'professional_review_required'})
    conflicts=[]
    for i,a in enumerate(records):
        for b in records[i+1:]:
            if a.get('topic') and a.get('topic')==b.get('topic') and a.get('declared_action')!=b.get('declared_action'):
                conflicts.append({'sources':[a['source_id'],b['source_id']],'topic':a['topic'],'kind':'declared_recommendation_difference'})
    return report('guideline_audit',recommendations=records,conflicts=conflicts,review_date=review_date,
      limitations=['No automatic claim of the latest guideline or interpretation of recommendation semantics. Verify dates, official provenance, negation, grades and applicability. All documents remain private.'])


def query_drug_reference(public_query: str, source: str = 'rxnorm', approved_public_query: bool = False, maximum: int = 10) -> dict:
    """Retrieve an explicitly approved public drug name from fixed RxNorm/DailyMed endpoints; never send patient context."""
    if approved_public_query is not True:raise ValueError('Exact public drug query must be explicitly approved')
    query=text(public_query,150)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 +()./\-]{0,149}',query) or not 1<=maximum<=20:raise ValueError('Bounded public drug name required')
    from http_client import get_json
    if source=='rxnorm':
        data=get_json('https://rxnav.nlm.nih.gov/REST/drugs.json',{'name':query})
        groups=data.get('drugGroup',{}).get('conceptGroup',[]);concepts=[c for g in groups for c in g.get('conceptProperties',[])]
        result={'source':source,'concepts':concepts[:maximum],'candidate_count':len(concepts),'scope':'US_RxNorm_vocabulary','identity_match':'review_required'}
    elif source=='dailymed':
        data=get_json('https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json',{'drug_name':query,'pagesize':maximum,'page':1})
        result={'source':source,'labels':data.get('data',[]),'metadata':data.get('metadata',{}),'scope':'US_labeling','coverage':'one_page_not_exhaustive'}
    else:raise ValueError('Only fixed official drug sources supported')
    return report('drug_reference',**result,limitations=['Drug name matching and label retrieval do not validate drug interactions, prescribing, regional authorization or an individual treatment decision.'])


def read_drug_label(set_id: str, approved_public_identifier: bool = False) -> dict:
    """Retrieve one approved public DailyMed label and its history with XML safety checks and located sections."""
    if approved_public_identifier is not True or not re.fullmatch(r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}',set_id):raise ValueError('Approved public label Set ID required')
    from http_client import get_json, request
    from academic_common import safe_xml
    raw,_=request('https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/'+set_id+'.xml')
    history=get_json('https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/'+set_id+'/history.json')
    root=safe_xml(raw);sections=[]
    for i,section in enumerate(root.iter('{urn:hl7-org:v3}section'),1):
        title_node=section.find('{urn:hl7-org:v3}title');body=section.find('{urn:hl7-org:v3}text')
        sections.append({'location':'section:'+str(i),'title':''.join(title_node.itertext()) if title_node is not None else '',
             'text':''.join(body.itertext()) if body is not None else ''})
    return artifact('drug_label',{'schema':1,'set_id':set_id,'source_sha256':digest(raw),'history':history,'sections':sections,
      'limitations':['US source label. Section extraction needs professional review and is not a prescription or exhaustive interaction database.']}, {'label.xml':raw})


def compare_drug_labels(before_path: str, after_path: str) -> dict:
    """Compare located extracted label sections and retain version hashes; do not infer safety from changed text."""
    _,a=read_file(before_path);_,b=read_file(after_path);old=json.loads(a);new=json.loads(b)
    if old.get('set_id')!=new.get('set_id') or not old.get('set_id'):raise ValueError('Compare versions of the same label Set ID')
    def index(d):
        out={}
        for s in d['sections']:
            key=(s['title'],s['location'])
            if key in out:raise ValueError('Duplicate label section locator')
            out[key]=s['text']
        return out
    ai,bi=index(old),index(new)
    changed=[{'title':k[0],'location':k[1],'before':ai.get(k),'after':bi.get(k)} for k in sorted(set(ai)|set(bi)) if ai.get(k)!=bi.get(k)]
    return report('label_diff',input_hashes=[digest(a),digest(b)],changed_sections=changed,review_required=bool(changed))


def audit_clinical_dataset(table_path: str, specification: dict) -> dict:
    """Audit clinical IDs, repeated visits, units, measurement limits, event timing and censoring without excluding records."""
    header,data,h=table(table_path);unit=specification.get('unit_column');visit=specification.get('visit_column');issues=[]
    if unit not in header or not specification.get('independent_unit') or not specification.get('design'):raise ValueError('Clinical independent unit and design required')
    if visit and visit not in header:raise ValueError('Visit column missing')
    seen=set();counts=collections.Counter()
    for i,r in enumerate(data,2):
        counts[r[unit]]+=1;key=(r[unit],r[visit] if visit else '')
        if not r[unit] or (key in seen and visit):issues.append({'row':i,'kind':'missing_unit_or_duplicate_visit'})
        seen.add(key)
        for check in specification.get('measurements',[]):
            value,uc=check['value_column'],check['unit_column']
            if value not in header or uc not in header or not check.get('unit') or not check.get('reference_source'):raise ValueError('Measurement units/reference provenance required')
            if r[uc]!=check['unit']:issues.append({'row':i,'column':value,'kind':'unit_mismatch'})
            if r[value]:
                try:
                    x=number(r[value])
                    if 'plausible_min' in check and x<number(check['plausible_min']) or 'plausible_max' in check and x>number(check['plausible_max']):issues.append({'row':i,'column':value,'kind':'plausibility_review'})
                except ValueError:issues.append({'row':i,'column':value,'kind':'invalid_measurement'})
        for order in specification.get('time_order',[]):
            if len(order)!=2 or not set(order)<=set(header):raise ValueError('Time-order columns missing')
            if r[order[0]] and r[order[1]]:
                try:
                    a=datetime.datetime.fromisoformat(r[order[0]]);b=datetime.datetime.fromisoformat(r[order[1]])
                    if a>b:issues.append({'row':i,'kind':'event_order_violation','columns':order})
                except (ValueError,TypeError):issues.append({'row':i,'kind':'invalid_or_mixed_timezone'})
        status=specification.get('status_column')
        if status:
            if status not in header:raise ValueError('Status column missing')
            if r[status] not in specification.get('status_values',[]):issues.append({'row':i,'kind':'unknown_event_or_censor_status'})
    repeated=sum(n>1 for n in counts.values())
    if repeated and not specification.get('repeated_measure_strategy'):issues.append({'kind':'repeated_units_without_analysis_strategy'})
    return report('clinical_qc',input_sha256=h,specification_sha256=sha(specification),row_count=len(data),independent_unit_count=len([k for k in counts if k]),
      repeated_unit_count=repeated,issues=issues,qc_pass=not issues,
      limitations=['Plausibility thresholds are supplied review rules, not diagnostic reference intervals. No automatic deletion, imputation or public upload.'])


def audit_clinical_mapping(mapping: list, vocabulary_version: str, target_model: str = 'OMOP') -> dict:
    """Audit explicitly supplied terminology/table mappings, ambiguity and unresolved concepts; do not claim complete ETL compatibility."""
    if target_model!='OMOP' or not vocabulary_version:raise ValueError('Declared OMOP vocabulary version required')
    out=[];seen=set()
    for r in rows(mapping,2000):
        if not {'source_field','source_value','target_table','target_field','concept_id','domain','mapping_source'}<=set(r):raise ValueError('Complete mapping fields required')
        key=(r['source_field'],r['source_value']);issues=[]
        if key in seen:issues.append('ambiguous_duplicate_mapping')
        seen.add(key)
        if not r.get('concept_id') or r['concept_id'] in {0,'0'}:issues.append('unresolved_concept')
        if r.get('verified') is not True:issues.append('unverified_mapping')
        out.append({'source_field':r['source_field'],'row_sha256':sha(r),'issues':issues})
    return report('clinical_mapping',target_model=target_model,vocabulary_version=vocabulary_version,mappings=out,
      limitations=['No vocabulary is downloaded and no database is altered. Table/schema conformance, vocabulary licenses and concept meaning require separate verification.'])


def guide_clinical_study(design: dict) -> dict:
    """Produce design-specific clinical research checks after the statistical estimand/unit consultation; fit nothing."""
    from statistics_ext import guide_study_statistics
    # Use the existing consultation contract; explicit scientific context is supplied by the caller.
    required={'estimand','independent_unit','endpoints','exposure','eligibility','time_zero','follow_up','covariates','missingness','design_type'}
    if not required<=set(design) or any(design[k] in (None,'',[]) for k in required-{'covariates'}):raise ValueError('Complete clinical study design required')
    checks=['align eligibility, treatment assignment and follow-up time zero','audit repeated units and cohort overlap','document outcome adjudication and missingness','define population and estimand before modeling']
    checks += {'cohort':['audit immortal time and time-varying exposure','review confounding and exposure ascertainment'],
      'treatment_comparison':['check propensity overlap and weighted covariate balance','review unmeasured confounding sensitivity'],
      'survival':['justify censoring assumptions','check proportional hazards','specify competing-event handling'],
      'multicenter':['model center/patient dependence','validate across centers'],
      'target_trial':['prespecify treatment strategies and assignment','define grace period and adherence estimand']}.get(design['design_type'],[])
    if design['design_type'] not in {'cohort','treatment_comparison','survival','multicenter','target_trial'}:raise ValueError('Unsupported study design')
    consultation=None
    if 'statistics_study' in design:consultation=guide_study_statistics(design['statistics_study'])
    return report('clinical_study_guide',design=design,checks=checks,statistics_consultation=consultation,statistics_consultation_required='statistics.guide_study_statistics',
      limitations=['This located design checklist is not a fitted causal model. Observational estimates require identification assumptions and sensitivity review.'])


def audit_clinical_prediction(predictions_path: str, specification: dict) -> dict:
    """Evaluate held-out binary probabilities: Brier, tie-aware AUC, calibration bins, threshold net benefit and subgroup coverage."""
    header,data,h=table(predictions_path)
    required={'unit_column','outcome_column','probability_column','validation_type','thresholds','training_unit_tokens','preprocessing_fitted_on_training','tuning_separate'}
    if not required<=set(specification) or not {specification[k] for k in ('unit_column','outcome_column','probability_column')}<=set(header):raise ValueError('Complete held-out prediction contract required')
    if specification['validation_type'] not in {'held_out','temporal_external','center_external'}:raise ValueError('Explicit validation design required')
    units=[r[specification['unit_column']] for r in data]
    if not units or any(not u for u in units) or len(set(units))!=len(units):raise ValueError('One independent prediction per nonmissing unit required')
    overlap=set(units)&set(specification['training_unit_tokens']);issues=[]
    if overlap:issues.append('training_validation_unit_overlap')
    if specification['preprocessing_fitted_on_training'] is not True or specification['tuning_separate'] is not True:issues.append('preprocessing_or_tuning_leakage')
    y=[number(r[specification['outcome_column']]) for r in data];p=[number(r[specification['probability_column']]) for r in data]
    if any(v not in {0,1} for v in y) or any(not 0<=v<=1 for v in p) or len(set(y))!=2:raise ValueError('Both binary outcomes and valid probabilities required')
    def metrics(ids):
        yy=[y[i] for i in ids];pp=[p[i] for i in ids];positives=sum(yy);negatives=len(ids)-positives
        groups=collections.defaultdict(lambda:[0,0])
        for outcome,pred in zip(yy,pp):groups[pred][int(outcome)]+=1
        wins=0;seen_neg=0
        for value in sorted(groups):
            neg,pos=groups[value];wins+=pos*seen_neg+.5*pos*neg;seen_neg+=neg
        return {'n':len(ids),'events':int(positives),'auc':wins/(positives*negatives) if positives and negatives else None,'brier':sum((a-b)**2 for a,b in zip(yy,pp))/len(ids)}
    calibration=[]
    for b in range(10):
        ids=[i for i,v in enumerate(p) if min(int(v*10),9)==b]
        if ids:calibration.append({'bin':b,'n':len(ids),'mean_prediction':sum(p[i] for i in ids)/len(ids),'event_fraction':sum(y[i] for i in ids)/len(ids)})
    net=[]
    for threshold in specification['thresholds']:
        t=number(threshold)
        if not 0<t<1:raise ValueError('Decision thresholds must be between zero and one')
        tp=sum(a==1 and b>=t for a,b in zip(y,p));fp=sum(a==0 and b>=t for a,b in zip(y,p));n=len(y)
        net.append({'threshold':t,'model':tp/n-fp/n*t/(1-t),'treat_all':sum(y)/n-(n-sum(y))/n*t/(1-t),'treat_none':0})
    subgroups=[]
    for c in specification.get('subgroup_columns',[]):
        if c not in header:raise ValueError('Subgroup column missing')
        for label in sorted({r[c] for r in data}):
            ids=[i for i,r in enumerate(data) if r[c]==label];subgroups.append({'column':c,'label':label,**metrics(ids)})
    return report('clinical_prediction',source_sha256=h,issues=issues,validation_gate_pass=not issues,overall=metrics(range(len(y))),calibration=calibration,decision_curve=net,subgroups=subgroups,
      limitations=['Descriptive held-out estimates have no uncertainty intervals here. Cluster/time-dependent outcomes need dedicated server validation. Small subgroup performance does not establish fairness or clinical utility.'])


def audit_medical_reporting(document_path: str, checklist: dict, assessments: list) -> dict:
    """Audit versioned medical reporting items using actual located source excerpts and reviewer judgments; no bundled proprietary checklist."""
    doc=manuscript(document_path)
    if not {'name','version','official_source','items'}<=set(checklist) or not checklist['official_source'].startswith('https://'):raise ValueError('Versioned official checklist metadata required')
    items=rows(checklist['items'],300);ids={r['id'] for r in items}
    if len(ids)!=len(items):raise ValueError('Duplicate checklist items')
    out=[];seen=set()
    for a in rows(assessments,300):
        if a.get('item_id') not in ids or a['item_id'] in seen or a.get('decision') not in {'reported','partial','missing','not_applicable'} or not a.get('reviewer'):raise ValueError('Distinct real reviewer decisions required')
        seen.add(a['item_id'])
        if a['decision'] in {'reported','partial'}:
            segment=locate(doc,a['location'])
            if normalized(text(a['excerpt'],2000)) not in normalized(segment['text']):raise ValueError('Reporting excerpt is not at declared location')
        elif not a.get('reason'):raise ValueError('Missing/not-applicable judgment needs a reason')
        out.append(a)
    return report('medical_reporting',source_sha256=doc['source_sha256'],checklist={k:v for k,v in checklist.items() if k!='items'},assessments=out,unassessed=sorted(ids-seen),
      limitations=['Supports caller-supplied TRIPOD+AI/TRIPOD-LLM and other permitted checklists. Items and grading rules are not redistributed; interpretation and licensing require review.'])


def extract_review_effects(sources: list, extractions: list) -> dict:
    """Validate actual independently extracted study effects against located source text and detect repeated study/cohort/outcome rows."""
    docs={s['id']:manuscript(s['path']) for s in rows(sources,100)};out=[];identities=collections.defaultdict(list)
    for r in rows(extractions,500):
        if not {'source_id','location','excerpt','study_id','cohort_id','outcome','timepoint','scale','effect','variance','reviewer','independent_review'}<=set(r) or r['source_id'] not in docs:raise ValueError('Complete effect extraction contract required')
        segment=locate(docs[r['source_id']],r['location'])
        if normalized(text(r['excerpt'],2000)) not in normalized(segment['text']):raise ValueError('Effect excerpt not found at location')
        effect=number(r['effect']);variance=number(r['variance'])
        if variance<=0 or r['independent_review'] is not True:raise ValueError('Positive sampling variance and actual independent review required')
        key=(r['study_id'],r['cohort_id'],r['outcome'],r['timepoint']);identities[key].append(r)
        out.append({**r,'effect':effect,'variance':variance,'source_sha256':docs[r['source_id']]['source_sha256']})
    conflicts=[];pending=[]
    for key,group in identities.items():
        reviewers={r['reviewer'] for r in group}
        if len(reviewers)<2:pending.append(sha(key))
        if len(group)!=len(reviewers):conflicts.append({'identity_sha256':sha(key),'kind':'duplicate_reviewer_or_extraction'})
        if len({(r['effect'],r['variance'],r['scale']) for r in group})>1:conflicts.append({'identity_sha256':sha(key),'kind':'effect_disagreement'})
    return report('review_effect_extraction',extractions=out,pending_second_review=pending,conflicts=conflicts,
      limitations=['Excerpt containment does not prove the numeric extraction or effect-scale transformation. Two actual human reviews are recorded; no second reviewer is fabricated. Shared cohorts/controls need covariance review before pooling.'])


def record_bias_assessment(tool: dict, assessments: list) -> dict:
    """Record versioned outcome-specific bias/evidence-certainty judgments with source locators and actual reviewers."""
    if not {'name','version','official_source','license','design'}<=set(tool):raise ValueError('Bias tool identity/design/license required')
    out=[]
    for a in rows(assessments,500):
        if not {'study_id','outcome','domain','judgment','reason','reviewer','source_path','location','excerpt'}<=set(a):raise ValueError('Located reviewer judgments required')
        doc=manuscript(a['source_path']);segment=locate(doc,a['location'])
        if normalized(text(a['excerpt'],2000)) not in normalized(segment['text']):raise ValueError('Bias evidence is not at declared location')
        out.append({k:v for k,v in a.items() if k!='source_path'}|{'source_sha256':doc['source_sha256']})
    return report('bias_assessment',tool=tool,assessments=out,
      limitations=['No automatic RoB/GRADE score or redistributed grading rules. Verify tool version, design applicability, licensing and judgments professionally.'])


def audit_adverse_event_reports(table_path: str, specification: dict) -> dict:
    """Deduplicate declared case/version reports and calculate descriptive drug-event reporting odds with explicit continuity correction."""
    header,data,h=table(table_path);required={'case_column','version_column','drug_column','event_column','target_drug','target_event','source','retrieved_on','continuity_correction'}
    if not required<=set(specification) or not {specification[k] for k in ('case_column','version_column','drug_column','event_column')}<=set(header):raise ValueError('Explicit case/version/drug/event definition required')
    correction=number(specification['continuity_correction'])
    if correction<0:raise ValueError('Continuity correction cannot be negative')
    by=collections.defaultdict(list)
    for r in data:
        case=r[specification['case_column']]
        if not case:raise ValueError('Missing case identity')
        version=number(r[specification['version_column']])
        if version<0 or version!=int(version):raise ValueError('Integer report version required')
        by[case].append((version,r))
    counts=[0,0,0,0];duplicates=0
    for case,records in by.items():
        newest=max(v for v,r in records);selected=[r for v,r in records if v==newest]
        pairs={(r[specification['drug_column']],r[specification['event_column']]) for r in selected};duplicates+=len(selected)-len(pairs)
        has_drug=any(d==specification['target_drug'] for d,e in pairs);has_event=any(e==specification['target_event'] for d,e in pairs)
        counts[0 if has_drug and has_event else 1 if has_drug else 2 if has_event else 3]+=1
    values=[v+correction for v in counts];result=None
    if min(values)>0:
        a,b,c,d=values;logror=math.log(a*d/(b*c));se=math.sqrt(sum(1/x for x in values));result={'ror':math.exp(logror),'lower95':math.exp(logror-1.96*se),'upper95':math.exp(logror+1.96*se)}
    return report('adverse_event_review',input_sha256=h,source=specification['source'],retrieved_on=specification['retrieved_on'],case_counts=dict(zip(('drug_event','drug_other','other_event','other_other'),counts)),
      duplicate_latest_pairs=duplicates,continuity_correction=correction,reporting_odds=result,
      limitations=['Spontaneous reports cannot establish incidence, causation or individual drug safety. Case-level co-occurrence is a declared signal definition, not a verified drug-event attribution. Other report versions are excluded explicitly; no patient data is transmitted.'])


def audit_imaging_metadata(records: list, specification: dict) -> dict:
    """Audit supplied private imaging metadata for patient/series allocation, acquisition differences and label-review provenance; no image inference."""
    data=rows(records,2000);issues=[];split={};settings=collections.defaultdict(set)
    for i,r in enumerate(data):
        if not {'patient_token','series_token','split','modality','acquisition','label_review'}<=set(r) or not r['patient_token'] or not r['series_token']:raise ValueError('Pseudonymous patient/series and acquisition contract required')
        if r['split'] not in {'train','validation','test'}:raise ValueError('Explicit image split required')
        if r['patient_token'] in split and split[r['patient_token']]!=r['split']:issues.append({'row':i,'kind':'patient_split_leakage'})
        split[r['patient_token']]=r['split'];settings[r['split']].add(sha(r['acquisition']))
        if r['label_review'] not in {'independent_reviewed','unreviewed','not_applicable'}:raise ValueError('Explicit label review state required')
        if r['label_review']=='unreviewed':issues.append({'row':i,'kind':'label_unreviewed'})
        for field in specification.get('required_acquisition_fields',[]):
            if field not in r['acquisition']:issues.append({'row':i,'kind':'missing_acquisition_field','field':field})
    if len(set(frozenset(v) for v in settings.values()))>1:issues.append({'kind':'acquisition_distribution_difference_review'})
    return report('imaging_qc',issues=issues,patient_count=len(split),qc_pass=not issues,
      limitations=['Tokens remain sensitive pseudonymous data. Metadata QC does not validate pixels, segmentation, diagnosis or label correctness. Large image analysis stays on the server.'])


def prepare_medical_teaching(title: str, sources: list, claims: list, case_data: dict = None) -> dict:
    """Create a private source-located teaching document from explicitly reviewed claims and approved synthetic/deidentified case material."""
    docs={s['id']:manuscript(s['path']) for s in rows(sources,50)};lines=['# '+text(title,300),'','Private teaching draft; professional review required.',''];verified=[]
    if case_data:
        if case_data.get('approved_use') is not True or case_data.get('kind') not in {'synthetic','reviewed_deidentified'}:raise ValueError('Approved synthetic/deidentified teaching case required')
        lines+=['## Case material','',json.dumps(case_data.get('content',{}),ensure_ascii=False),'']
    for c in rows(claims,100):
        if c.get('source_id') not in docs or c.get('reviewed') is not True or not c.get('limitations'):raise ValueError('Reviewed located claims and limits required')
        segment=locate(docs[c['source_id']],c['location'])
        if normalized(text(c['excerpt'],2000)) not in normalized(segment['text']):raise ValueError('Teaching claim excerpt not at supplied location')
        claim=text(c['claim'],2000);verified.append({**c,'source_sha256':docs[c['source_id']]['source_sha256']})
        lines+=['## '+claim,'','Source: '+c['source_id']+'; '+c['location'],'','Limitations: '+str(c['limitations']),'']
    return artifact('medical_teaching',{'schema':1,'claims':verified,'state':'private_review_draft','limitations':['Reviewer-approved claims are supplied input, not independently established truth. No patient data is uploaded or automatically published.']}, {'teaching.md':'\n'.join(lines)})


def prepare_clinical_backend(backend: str, configuration: dict, remote_workdir: str, expected_host: str, output_directory: str,
                             context: dict, inputs: list, rscript: str = 'Rscript') -> dict:
    """Prepare fixed existing-R clinical models with mandatory unit/design/QC gates; no local fitting or server submission."""
    from workflow_ext import prepare_remote_task
    from scientific_backend_ext import _bind_bundle
    required={'data','unit_column','estimand','covariates','missingness_policy','design','statistical_plan_reviewed'}
    required |= {'time_column','status_column'} if backend in {'cox_survival','competing_risks'} else {'treatment_column','outcome_column'} if backend=='propensity_iptw' else set()
    if backend not in {'cox_survival','competing_risks','propensity_iptw'} or not required<=set(configuration):raise ValueError('Complete fixed clinical model contract required')
    if configuration['statistical_plan_reviewed'] is not True or configuration['missingness_policy']!='reject':raise ValueError('Reviewed statistical plan and explicit reject-missing policy required')
    if backend=='propensity_iptw' and (type(configuration.get('bootstrap_replications')) is not int or not 100<=configuration['bootstrap_replications']<=2000 or type(configuration.get('seed')) is not int):raise ValueError('Prespecified bounded independent-unit bootstrap and seed required')
    consultation=configuration.get('statistics_study')
    if not isinstance(consultation,dict):raise ValueError('Run the statistical consultation before formal clinical modeling')
    from statistics_ext import guide_study_statistics
    guidance=guide_study_statistics(consultation)
    if consultation['estimand']!=configuration['estimand'] or consultation['independent_unit']!=context.get('biological_unit') or consultation['repeated'] or consultation['clustered']:
        raise ValueError('Initial clinical adapters require matching estimand and independent units without repeated/clustered rows')
    if not inputs or configuration['data'] not in {i['path'] for i in inputs}:raise ValueError('Checksummed clinical data manifest required')
    for key in ('unit_column','time_column','status_column','treatment_column','outcome_column'):
        if key in configuration and not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',configuration[key]):raise ValueError('Safe explicit column names required')
    if not isinstance(configuration['covariates'],list) or any(not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',c) for c in configuration['covariates']):raise ValueError('Safe explicit covariates required')
    relative(configuration['data']);relative(output_directory)
    if Path(rscript).stem.lower()!='rscript':raise ValueError('Existing Rscript required')
    config={**configuration,'backend':backend,'output_directory':output_directory,'context':context,'statistics_guidance':guidance}
    bundle=prepare_remote_task([rscript,'clinical_backend.R','clinical_config.json'],remote_workdir,expected_host,
      [output_directory+'/summary.json',output_directory+'/results.rds',output_directory+'/qc.json',output_directory+'/session.txt'],context,inputs)
    folder=Path(bundle['bundle']);(folder/'clinical_config.json').write_text(canon(config)+'\n',encoding='utf8');shutil.copyfile(HERE/'clinical_backend.R',folder/'clinical_backend.R')
    bundle=_bind_bundle(bundle,['clinical_config.json','clinical_backend.R'])
    return {**bundle,'backend':backend,'limitations':bundle['limitations']+['Existing jsonlite/survival/cmprsk packages only. Mandatory numeric/unit/design/missingness checks precede fitting. Binary numeric covariates only in the initial IPTW adapter; no implicit categorization, trimming or imputation. Clinical use requires professional review.']}
