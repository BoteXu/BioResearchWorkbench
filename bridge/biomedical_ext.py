"""Bounded biomedical evidence audits; calculations and interpretation remain explicit."""
import hashlib
import itertools
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

CONTEXT = ('species','model','tissue','assay','biological_unit','contrast')
EVIDENCE_TYPES = ('human_genetics','expression','perturbation','binding','clinical','structure','other')


def _rows(rows, maximum=10000):
    if not isinstance(rows,list) or not 1 <= len(rows) <= maximum or any(not isinstance(r,dict) for r in rows):
        raise ValueError('Supply a bounded nonempty list of objects')
    return rows


def _number(value):
    if isinstance(value,bool):
        raise ValueError('Boolean is not a measurement')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Measurement must be finite')
    return number


def _provenance(row):
    reference = row.get('source_reference')
    result = {'source_reference':reference,'assertion_verified':False,'receipt_integrity':'not_supplied'}
    if row.get('receipt_file'):
        path = Path(row['receipt_file']).resolve(strict=True)
        if path.stat().st_size > 2000000:
            raise ValueError('Receipt exceeds size limit')
        receipt = json.loads(path.read_text(encoding='utf8'))
        data = Path(receipt['result_file']).resolve(strict=True)
        if data.stat().st_size > 30000000:
            raise ValueError('Export a smaller result receipt')
        digest = hashlib.sha256(data.read_bytes()).hexdigest()
        if digest != receipt['sha256']:
            raise ValueError('Source receipt hash mismatch')
        result.update(receipt_integrity='verified',receipt_file=str(path),result_sha256=digest)
    result['source_present'] = bool(reference or row.get('receipt_file'))
    return result


def _report(**fields):
    return {**fields,'scientific_validity':'not_established',
            'limitations':['Rules audit caller-supplied fields; original methods and source assertions require review.',
                           'Passing format, context or integrity checks does not establish causality or clinical utility.']}


def audit_drug_target_records(records: list, target_id: str, species: str) -> dict:
    """Normalize small activity tables, retaining assay class, censored values, target confidence and duplicates."""
    _rows(records)
    if not target_id or not species:
        raise ValueError('Explicit target and species required')
    units = {'M':1e9,'mM':1e6,'uM':1e3,'µM':1e3,'μM':1e3,'nM':1,'pM':0.001}
    output, seen = [], set()
    for index,row in enumerate(records):
        issues, provenance = [], _provenance(row)
        for key in ('activity_id','molecule_id','assay_id','target_type','assay_type','standard_type','standard_relation'):
            if not row.get(key):
                issues.append('missing_'+key)
        if not provenance['source_present']:
            issues.append('missing_source')
        if row.get('target_id') != target_id:
            issues.append('target_mismatch')
        if row.get('species') != species:
            issues.append('species_missing_or_mismatch')
        identity = row.get('activity_id')
        if identity and identity in seen or row.get('potential_duplicate') in (True,1,'1','true'):
            issues.append('duplicate_or_source_flagged_duplicate')
        if identity:
            seen.add(identity)
        value_nm = None
        try:
            value = _number(row.get('standard_value'))
            if value <= 0 or row.get('standard_units') not in units:
                raise ValueError('Invalid concentration')
            value_nm = value * units[row['standard_units']]
            if not math.isfinite(value_nm):
                raise ValueError('Overflow')
        except (TypeError,ValueError):
            issues.append('invalid_value_or_nonconvertible_unit')
        relation = row.get('standard_relation')
        if relation not in {'=','<','>','<=','>='}:
            issues.append('invalid_relation')
        if row.get('standard_type') not in {'Ki','Kd','IC50','XC50','EC50','AC50','Potency','ED50'}:
            issues.append('unsupported_concentration_activity_type')
        if row.get('data_validity_comment') not in {None,'','Manually validated'}:
            issues.append('source_validity_warning')
        confidence = row.get('confidence_score')
        if isinstance(confidence,bool) or not isinstance(confidence,int) or not 0 <= confidence <= 9:
            issues.append('missing_or_invalid_confidence_score')
        context = {k:row.get(k) for k in ('assay_id','assay_type','standard_type','target_type','species','conditions')}
        binding_candidate = row.get('assay_type') == 'B' and row.get('target_type') == 'SINGLE PROTEIN' and confidence == 9
        usable = not issues
        output.append({'row':index,'original':row,'value_nM':value_nm,'relation':relation,
                       'negative_log_molar':9-math.log10(value_nm) if usable and value_nm and relation=='=' else None,
                       'binding_assay_candidate':usable and binding_candidate,
                       'comparable_group':context,'issues':issues,'record_check_pass':usable,'provenance':provenance})
    return _report(records=output,summary=dict(Counter('pass' if r['record_check_pass'] else 'review' for r in output)),
                   interpretation='Binding candidates require source review; functional potency and censored concentrations are retained separately. No affinity averaging is performed.')


def assess_cohort_eligibility(studies: list, criteria: dict) -> dict:
    """Apply explicit study criteria, separating exclusions from missing metadata and cohort overlap."""
    _rows(studies,500)
    required = ('species','tissue','model','assay','contrast')
    if not isinstance(criteria,dict) or any(not criteria.get(k) for k in required):
        raise ValueError('Criteria require species, tissue, model, assay and contrast')
    minimum = criteria.get('min_units_per_group',2)
    if type(minimum) is not int or minimum < 2:
        raise ValueError('Use at least two biological units per group')
    output, cohorts = [], defaultdict(list)
    for row in studies:
        excluded, missing, warnings = [], [], []
        provenance = _provenance(row)
        for key in required + tuple(k for k in ('platform','matrix_type','dose','time') if k in criteria):
            if not row.get(key):
                missing.append(key)
            elif row[key] != criteria[key]:
                excluded.append(key+'_mismatch')
        counts = row.get('group_unit_counts')
        if not isinstance(counts,dict) or len(counts)<2:
            missing.append('group_unit_counts')
        elif any(type(n) is not int or n < minimum for n in counts.values()):
            excluded.append('insufficient_or_invalid_biological_units')
        if not row.get('biological_unit'):
            missing.append('biological_unit')
        elif row['biological_unit'] in {'cell','spot','frame','spectrum','technical_replicate'}:
            excluded.append('independence_not_established_for_this_unit')
        for key in ('study_id','sample_metadata_reference','matrix_type'):
            if not row.get(key):
                missing.append(key)
        if not provenance['source_present']:
            missing.append('source')
        for key in ('paired','batch','dose','time'):
            if key not in row:
                warnings.append('unreported_'+key)
        if row.get('cohort_id'):
            cohorts[row['cohort_id']].append(row.get('study_id'))
        output.append({'study_id':row.get('study_id'),'decision':'exclude' if excluded else 'needs_review' if missing else 'eligible_under_supplied_criteria',
                       'exclusion_reasons':excluded,'missing':missing,'warnings':warnings,'provenance':provenance})
    return _report(studies=output,overlapping_cohort_ids={k:v for k,v in cohorts.items() if len(v)>1},
                   submitted_for_analysis=False,interpretation='Eligibility is conditional on documented criteria and independent-unit assertions; cohort overlap is not replication.')


def audit_genetic_alignment(rows: list, reference_assembly: str, max_frequency_difference: float = 0.15) -> dict:
    """Align paired small genetic summaries by explicit alleles; reject palindromes, build/ancestry/tissue gaps and unknown directions."""
    _rows(rows)
    threshold = _number(max_frequency_difference)
    if not reference_assembly or not 0 <= threshold <= 1:
        raise ValueError('Explicit assembly and frequency threshold required')
    output, seen = [], set()
    complement = str.maketrans('ACGT','TGCA')
    for index,row in enumerate(rows):
        issues, actions = [], []
        for field in ('variant_id','left','right'):
            if not row.get(field):
                issues.append('missing_'+field)
        if row.get('variant_id') in seen:
            issues.append('duplicate_variant')
        seen.add(row.get('variant_id'))
        left, right = row.get('left',{}), row.get('right',{})
        if not isinstance(left,dict) or not isinstance(right,dict):
            raise ValueError('left and right must be objects')
        provenance = [_provenance(x) for x in (left,right)]
        for side in (left,right):
            if side.get('assembly') != reference_assembly:
                issues.append('build_missing_or_mismatch')
            if not side.get('ancestry'):
                issues.append('missing_ancestry')
        if left.get('ancestry') != right.get('ancestry'):
            issues.append('ancestry_mismatch')
        for field in ('species','chromosome','position'):
            if not left.get(field) or left.get(field)!=right.get(field):
                issues.append(field+'_missing_or_mismatch')
        if type(left.get('position')) is not int or left.get('position',0)<1:
            issues.append('invalid_coordinate')
        if row.get('requires_same_tissue') is True and (not left.get('tissue') or left.get('tissue') != right.get('tissue')):
            issues.append('tissue_missing_or_mismatch')
        if not all(p['source_present'] for p in provenance):
            issues.append('missing_source')
        a,b,c,d = [str(s.get(k,'')).upper() for s,k in ((left,'effect_allele'),(left,'other_allele'),(right,'effect_allele'),(right,'other_allele'))]
        flip = None
        if any(x not in {'A','C','G','T'} for x in (a,b,c,d)) or a==b or c==d:
            issues.append('non_snp_or_invalid_alleles_require_reference_normalization')
        elif {a,b} in ({'A','T'},{'C','G'}):
            issues.append('palindromic_variant_requires_explicit_reference_review')
        elif (a,b)==(c,d):
            flip = False
        elif (a,b)==(d,c):
            flip = True
            actions.append('swap_effect_alleles')
        elif (a,b)==(c.translate(complement),d.translate(complement)):
            flip = False
            actions.append('complement_strand')
        elif (a,b)==(d.translate(complement),c.translate(complement)):
            flip = True
            actions.extend(['complement_strand','swap_effect_alleles'])
        else:
            issues.append('allele_mismatch')
        aligned = dict(right)
        try:
            for side in (left,right):
                effect = _number(side['effect'])
                if side.get('effect_type') not in {'beta','OR'} or side.get('effect_type')=='OR' and effect<=0:
                    raise ValueError('Invalid effect type')
                if not 0 <= _number(side['effect_allele_frequency']) <= 1:
                    raise ValueError('Invalid frequency')
            if flip is not None:
                aligned['effect'] = (1/_number(right['effect']) if right['effect_type']=='OR' else -_number(right['effect'])) if flip else _number(right['effect'])
                aligned['effect_allele_frequency'] = 1-_number(right['effect_allele_frequency']) if flip else _number(right['effect_allele_frequency'])
                aligned['effect_allele'],aligned['other_allele'] = a,b
                if abs(_number(left['effect_allele_frequency'])-aligned['effect_allele_frequency'])>threshold:
                    issues.append('frequency_disagreement')
                ci = right.get('confidence_interval')
                if ci is not None:
                    low,high = map(_number,ci)
                    if low>high or right['effect_type']=='OR' and low<=0:
                        raise ValueError('Invalid confidence interval')
                    aligned['confidence_interval'] = ([1/high,1/low] if right['effect_type']=='OR' else [-high,-low]) if flip else [low,high]
        except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError):
            issues.append('missing_or_invalid_effect_frequency_or_interval')
        output.append({'row':index,'variant_id':row.get('variant_id'),'original':row,'aligned_right':aligned if not issues else None,
                       'actions':actions,'issues':sorted(set(issues)),'alignment_pass':not issues,'provenance':provenance})
    return _report(rows=output,liftover_performed=False,interpretation='SNP direction checks only; no LD clumping, MR, colocalization or genome build conversion is performed.')


def build_evidence_matrix(records: list, question: str) -> dict:
    """Group source-linked evidence by candidate and evidence class, retaining context and missing evidence without a total score."""
    _rows(records,2000)
    if not question:
        raise ValueError('Explicit research question required')
    matrix = {}
    for index,row in enumerate(records):
        candidate = row.get('candidate')
        if not candidate or row.get('evidence_type') not in EVIDENCE_TYPES:
            raise ValueError('Each record needs a candidate and supported evidence_type')
        group = matrix.setdefault(candidate,{key:[] for key in EVIDENCE_TYPES})
        group[row['evidence_type']].append({'row':index,'record':row,'missing_context':[k for k in CONTEXT if not row.get(k)],'provenance':_provenance(row)})
    return _report(question=question,candidates=[{'candidate':c,'evidence':e,'absent_classes':[k for k in EVIDENCE_TYPES[:-1] if not e[k]]} for c,e in matrix.items()],
                   interpretation='Absent classes mean not supplied, not evidence of biological absence. Records are not independent replications merely because they come from different databases.')


def compare_evidence(records: list) -> dict:
    """Compare source assertions only after matching question, endpoint, context, dose, time and units; retain nulls separately."""
    _rows(records,100)
    comparisons = []
    fields = ('question','endpoint','species','model','tissue','assay','biological_unit','contrast','dose','time','effect_unit')
    provenances = [_provenance(r) for r in records]
    for (i,left),(j,right) in itertools.combinations(enumerate(records),2):
        reasons = [k+'_missing_or_different' for k in fields if left.get(k) is None or right.get(k) is None or left[k]!=right[k]]
        if not provenances[i]['source_present'] or not provenances[j]['source_present']:
            reasons.append('missing_source')
        outcomes = (left.get('outcome'),right.get('outcome'))
        if any(x not in {'positive','negative','null','inconclusive'} for x in outcomes):
            reasons.append('invalid_or_missing_outcome')
        if left.get('source_reference') and left.get('source_reference') == right.get('source_reference'):
            reasons.append('shared_source_not_independent')
        label = 'not_comparable' if reasons else 'inconclusive' if 'inconclusive' in outcomes else 'null_or_detection_difference' if 'null' in outcomes else 'direction_conflict' if outcomes[0]!=outcomes[1] else 'direction_agreement'
        comparisons.append({'rows':[i,j],'classification':label,'reasons':reasons})
    return _report(comparisons=comparisons,provenance=provenances,
                   interpretation='Null means the source reports no detected effect; it is not proof of zero effect. Direction labels must be curated against the stated contrast.')


def audit_structure_context(records: list, protein_id: str, species: str, required_regions: list = None) -> dict:
    """Check chain-specific canonical residue mappings, missing residues, isoforms and mutations for a stated protein."""
    _rows(records,100)
    if not protein_id or not species:
        raise ValueError('Explicit protein and species required')
    output = []
    for index,row in enumerate(records):
        issues, provenance = [], _provenance(row)
        for key,value in (('protein_id',protein_id),('species',species)):
            if row.get(key)!=value:
                issues.append(key+'_missing_or_mismatch')
        for key in ('structure_id','chain_id','method','mapping_reference'):
            if not row.get(key):
                issues.append('missing_'+key)
        if not provenance['source_present']:
            issues.append('missing_source')
        length = row.get('reference_length')
        if type(length) is not int or not 1<=length<=100000:
            raise ValueError('Reference length must be 1-100000 residues')
        mapped = set()
        for interval in row.get('mapped_intervals',[]):
            if not isinstance(interval,list) or len(interval)!=2 or any(type(x) is not int for x in interval) or not 1<=interval[0]<=interval[1]<=length:
                raise ValueError('Use canonical one-based mapped intervals within reference length')
            mapped.update(range(interval[0],interval[1]+1))
        missing = row.get('missing_residues')
        if not isinstance(missing,list) or any(type(x) is not int or not 1<=x<=length for x in missing):
            issues.append('missing_or_invalid_missing_residue_annotation')
        else:
            mapped.difference_update(missing)
        gaps = []
        for interval in required_regions or []:
            if not isinstance(interval,list) or len(interval)!=2 or any(type(x) is not int for x in interval) or not 1<=interval[0]<=interval[1]<=length:
                raise ValueError('Invalid required region')
            absent = sorted(set(range(interval[0],interval[1]+1))-mapped)
            if absent:
                gaps.append({'region':interval,'missing_count':len(absent),'first_missing':absent[:20]})
        if gaps or not mapped:
            issues.append('required_region_or_mapping_missing')
        for key in ('mutations','isoform','ligands'):
            if key not in row:
                issues.append('unreported_'+key)
        if row.get('mutations'):
            issues.append('mutations_require_review')
        if row.get('isoform') != 'canonical':
            issues.append('isoform_requires_review')
        output.append({'row':index,'chain_id':row.get('chain_id'),'mapped_fraction':len(mapped)/length,
                       'required_region_gaps':gaps,'issues':issues,'context_check_pass':not issues,'provenance':provenance})
    return _report(structures=output,interpretation='Mappings are caller supplied. Coverage does not establish folding quality, domain function or ligand binding; inspect the actual structure and mapping source.')


def map_disease_terms(terms: list, mappings: list = None, ontology: str = 'mondo', sensitive_data: bool = False) -> dict:
    """Review explicit ontology relations locally, or retrieve bounded public OLS candidates without asserting equivalence."""
    if not isinstance(terms,list) or not 1<=len(terms)<=20 or any(not isinstance(t,str) or not t.strip() or len(t)>200 for t in terms):
        raise ValueError('Supply 1-20 short disease or phenotype terms')
    if ontology not in {'mondo','efo','hp'} or type(sensitive_data) is not bool:
        raise ValueError('Supported ontologies: mondo, efo, hp')
    if mappings is None:
        if sensitive_data:
            raise ValueError('Public ontology retrieval requires specific authorization for sensitive terms')
        from http_client import get_json
        results = []
        for term in terms:
            data = get_json('https://www.ebi.ac.uk/ols4/api/search',{'q':term,'ontology':ontology,'rows':10})
            candidates = [{'id':r.get('obo_id') or r.get('short_form'),'label':r.get('label'),'iri':r.get('iri'),
                           'relation':'candidate_not_equivalence'} for r in data.get('response',{}).get('docs',[])]
            results.append({'term':term,'candidates':candidates,'source_data':data,'automatic_merge_allowed':False})
        return _report(terms=results,public_queries_performed=True,interpretation='Search similarity and synonyms do not establish exact ontology equivalence.')
    _rows(mappings,500)
    output = []
    for row in mappings:
        provenance = _provenance(row)
        relation = row.get('relation')
        issues = []
        if row.get('term') not in terms or not row.get('target_id'):
            issues.append('term_or_target_missing')
        if relation not in {'exact','broad','narrow','related','unknown'}:
            issues.append('invalid_mapping_relation')
        if not provenance['source_present']:
            issues.append('missing_mapping_source')
        if not row.get('ontology_version'):
            issues.append('missing_ontology_version')
        output.append({'mapping':row,'issues':issues,'asserted_exact':relation=='exact' and not issues,
                       'automatic_merge_allowed':False,'provenance':provenance})
    return _report(mappings=output,public_queries_performed=False,interpretation='Exact is a caller-supplied mapping assertion; review versioned ontology semantics before merging.')


def audit_cell_annotations(clusters: list, marker_rules: dict, min_donors: int = 2) -> dict:
    """Review returned marker summaries and donor counts without loading a cell matrix or replacing annotation."""
    _rows(clusters,500)
    if not isinstance(marker_rules,dict) or not marker_rules or type(min_donors) is not int or min_donors<2:
        raise ValueError('Supply curated marker rules and at least two donors')
    output = []
    for row in clusters:
        label = row.get('label')
        rule = marker_rules.get(label)
        if not isinstance(rule,dict) or not isinstance(rule.get('positive'),list) or not rule['positive'] or not rule.get('source_reference'):
            raise ValueError('Each proposed label needs positive marker rules and a source')
        markers = row.get('markers')
        if not isinstance(markers,list) or any(not isinstance(g,str) for g in markers):
            raise ValueError('Markers must be a list of gene identifiers')
        observed = set(markers)
        supporting = sorted(observed & set(rule['positive']))
        conflicting = sorted(observed & set(rule.get('negative',[])))
        issues = []
        minimum = rule.get('min_positive',min(2,len(rule['positive'])))
        if type(minimum) is not int or not 1<=minimum<=len(rule['positive']):
            raise ValueError('Invalid minimum positive marker count')
        if len(supporting)<minimum:
            issues.append('insufficient_positive_rule_markers')
        if conflicting:
            issues.append('conflicting_markers')
        if type(row.get('donor_count')) is not int or row['donor_count']<min_donors:
            issues.append('insufficient_or_unknown_donors')
        for key in ('species','tissue','model'):
            if not rule.get(key) or row.get(key)!=rule[key]:
                issues.append(key+'_missing_or_rule_mismatch')
        if row.get('doublet_flag') is not False:
            issues.append('doublet_flag_or_screen_unknown')
        provenance = _provenance(row)
        if not provenance['source_present']:
            issues.append('missing_source')
        output.append({'cluster_id':row.get('cluster_id'),'proposed_label':label,'supporting':supporting,'conflicting':conflicting,
                       'issues':issues,'annotation_review_required':bool(issues),'rule_source':rule['source_reference'],'provenance':provenance})
    return _report(clusters=output,interpretation='Marker overlap is descriptive; it does not establish cell identity, independence or absence of doublets.')


def audit_enrichment_results(results: list, background_genes: list, mapping_summary: dict, max_driver_fraction: float = 0.5, max_mapping_loss: float = 0.2) -> dict:
    """Audit server enrichment summaries for background, ID loss, set versions, repeated terms and driver concentration."""
    _rows(results,2000)
    if not isinstance(background_genes,list) or not background_genes or any(not isinstance(g,str) or not g for g in background_genes):
        raise ValueError('Explicit background gene identifiers required')
    threshold = _number(max_driver_fraction)
    loss_threshold = _number(max_mapping_loss)
    if not 0<threshold<=1 or not 0<=loss_threshold<=1 or not isinstance(mapping_summary,dict):
        raise ValueError('Invalid driver threshold or mapping summary')
    total,mapped = mapping_summary.get('input_count'),mapping_summary.get('mapped_count')
    if type(total) is not int or type(mapped) is not int or not 0<=mapped<=total or total<1:
        raise ValueError('Mapping counts must satisfy 0<=mapped<=input_count')
    background, seen, output = set(background_genes), set(), []
    for row in results:
        issues, provenance = [], _provenance(row)
        key = (row.get('term_id'),row.get('database_version'),row.get('contrast'))
        if key in seen:
            issues.append('duplicate_term_version_contrast')
        seen.add(key)
        for field in ('term_id','database_version','contrast','method','direction','background_reference'):
            if not row.get(field):
                issues.append('missing_'+field)
        if row.get('direction') not in {'up','down','positive','negative','unsigned'}:
            issues.append('invalid_direction')
        if row.get('method')=='GSEA':
            try:
                score = _number(row['NES'])
                if score==0 or (score>0 and row.get('direction') not in {'up','positive'}) or (score<0 and row.get('direction') not in {'down','negative'}):
                    issues.append('nes_direction_mismatch')
            except (ValueError,TypeError,KeyError):
                issues.append('missing_or_invalid_nes')
        try:
            if not 0<=_number(row['q_value'])<=1:
                raise ValueError('Invalid q')
        except (ValueError,TypeError,KeyError):
            issues.append('invalid_q_value')
        genes = row.get('driver_genes')
        if not isinstance(genes,list) or not genes or any(not isinstance(g,str) for g in genes):
            issues.append('missing_or_invalid_driver_genes')
            genes = []
        if len(genes)!=len(set(genes)):
            issues.append('duplicate_driver_genes')
        if set(genes)-background:
            issues.append('drivers_outside_background')
        counts = row.get('driver_contributions')
        fraction = None
        if isinstance(counts,dict) and counts:
            try:
                values = [_number(v) for v in counts.values()]
                total_weight = _number(sum(values))
                if any(v<0 for v in values) or total_weight<=0 or set(counts)-set(genes):
                    raise ValueError('Invalid driver contributions')
                fraction = max(values)/total_weight
                if fraction>threshold:
                    issues.append('concentrated_driver_contribution')
            except (ValueError,TypeError):
                issues.append('invalid_driver_contributions')
        else:
            issues.append('driver_concentration_not_evaluated')
        if not provenance['source_present']:
            issues.append('missing_source')
        output.append({'term_id':row.get('term_id'),'issues':issues,'max_driver_fraction':fraction,'provenance':provenance})
    overlaps = []
    for (i,a),(j,b) in itertools.combinations(enumerate(results[:100]),2):
        left,right = set(a.get('driver_genes') or []),set(b.get('driver_genes') or [])
        if left and right and len(left&right)/len(left|right)>=0.8:
            overlaps.append({'rows':[i,j],'driver_jaccard':len(left&right)/len(left|right)})
    return _report(terms=output,mapping_loss_fraction=1-mapped/total,mapping_loss_warning=1-mapped/total>loss_threshold,
                   policy_thresholds={'max_mapping_loss':loss_threshold,'max_driver_fraction':threshold},duplicate_background_count=len(background_genes)-len(background),
                   similar_driver_sets=overlaps,overlap_comparisons_truncated=len(results)>100,
                   interpretation='Driver overlap is not ontology redundancy. Reported contributions and background appropriateness require source review; no enrichment is recomputed.')


def extract_study_elements(path: str, max_excerpts_per_field: int = 5) -> dict:
    """Extract located candidate passages for study design; leave values unfilled for Codex source review."""
    file = Path(path).resolve(strict=True)
    if file.stat().st_size>10000000 or type(max_excerpts_per_field) is not int or not 1<=max_excerpts_per_field<=10:
        raise ValueError('Use a local document under 10 MB and 1-10 excerpts per field')
    if file.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        reader = PdfReader(str(file))
        if len(reader.pages)>300:
            raise ValueError('Export the relevant methods pages')
        chunks = [('page',i+1,(page.extract_text() or '')) for i,page in enumerate(reader.pages)]
    elif file.suffix.lower() in {'.txt','.md'}:
        chunks = [('line',i+1,text) for i,text in enumerate(file.read_text(encoding='utf-8-sig').splitlines())]
    else:
        raise ValueError('Use local PDF, TXT or Markdown; convert other formats with the existing document helper')
    patterns = {
        'sample':r'\b(sample|participant|patient|animal|donor|replicate)s?\b|样本|患者|供者|重复',
        'randomization':r'randomi[sz]|随机', 'blinding':r'blind|盲法',
        'dose':r'\b(dose|dosage|concentration|mg/kg|µM|nM)\b|剂量|浓度',
        'time':r'\b(hour|day|week|month|minute|time point)s?\b|小时|天|时间',
        'endpoint':r'\b(endpoint|outcome|primary|secondary)\b|终点|主要指标',
        'statistical_unit':r'\b(unit|replicate|paired|donor|subject|independent)s?\b|统计单位|独立|配对',
        'statistics':r'\b(statistic|regression|ANOVA|t-test|adjusted|FDR|multiple testing)\b|统计|回归|校正',
    }
    fields = {}
    for field,pattern in patterns.items():
        excerpts = []
        for location,index,text in chunks:
            for match in re.finditer(pattern,text,re.I):
                excerpts.append({'location_type':location,'location':index,'character_offset':match.start(),
                                 'excerpt':text[max(0,match.start()-120):match.end()+220]})
                if len(excerpts)>=max_excerpts_per_field:
                    break
            if len(excerpts)>=max_excerpts_per_field:
                break
        fields[field] = {'value':None,'state':'candidate_passages_require_review' if excerpts else 'not_located_by_rules','excerpts':excerpts}
    return _report(source_file=str(file),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),fields=fields,
                   interpretation='Located passages are not extracted factual values. Negation and distinctions between biological and technical repeats require reading the original passage. PDF offsets refer to extracted page text.')
