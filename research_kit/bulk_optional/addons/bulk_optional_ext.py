"""Private optional bulk workflow: contracts, routing and returned-file checks only."""
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

VERSION = '0.1.0-private'
STAGES = {
    'qc': {'routes': ['statistics.guide_study_statistics', 'qc.preflight_transcriptomics'], 'requirements': ['Exact input/design/context hashes', 'Reviewed sample QC and biological units'], 'source_status': 'replace_with_existing_gate'},
    'de': {'routes': ['transcriptomics.run_bulk_rnaseq', 'transcriptomics.run_normalized_expression', 'advanced.run_designed_expression', 'server.prepare_standard_pipeline'], 'requirements': ['Count or normalized model matches declared scale', 'Case minus control; full rank design; effect and uncertainty'], 'source_status': 'replace_with_existing_backend'},
    'enrich': {'routes': ['omics.local_gene_set_enrichment', 'omics.preranked_gsea', 'biomedical.audit_enrichment_results'], 'requirements': ['Explicit tested gene ID universe, species/namespace/version', 'Up/down ORA separately; unique signed full ranking'], 'source_status': 'replace_with_existing_backend'},
    'pathway': {'routes': ['systems.score_pathway_activity', 'advanced.summarize_pathway_overlap'], 'requirements': ['Gene-set ID mapping and coverage', 'Activity correlation is association; shared genes are not independent evidence', 'GSVA and correlation network require an independently validated server adapter'], 'source_status': 'partial_existing_routes'},
    'tf': {'routes': ['scientific_backend.prepare_scientific_backend'], 'requirements': ['Selected local signed regulator network', 'Explicit ULM/MLM server configuration and namespace', 'DoRothEA/VIPER require a validated adapter; source does not implement them'], 'source_status': 'partial_existing_routes'},
    'wgcna': {'routes': ['advanced.audit_network_stability', 'workflow.prepare_remote_task'], 'requirements': ['Enough independent units for the prespecified network question', 'Bootstrap/subsample preservation and confounder assessment', 'Validate PyWGCNA version, kME axes, eigengene output and module preservation on server', 'Fresh outputs; no recursive deletion'], 'source_status': 'review_only_engine'},
    'ppi': {'routes': ['systems.analyze_ppi_network', 'systems.query_string_network'], 'requirements': ['Selected local edges by default', 'Exact reviewed public gene list before any public STRING request', 'Retain isolates/all components and physical/functional edge distinction'], 'source_status': 'replace_with_existing_backend'},
    'cell': {'routes': ['advanced.analyze_cell_composition', 'systems.score_pathway_activity'], 'requirements': ['Tissue/species-specific curated marker or signature input', 'Namespace coverage; marker score is not an absolute cell fraction', 'Gene-score covariance is not cell of origin'], 'source_status': 'replace_with_existing_backend'},
    'key': {'routes': ['workflow.audit_result_table'], 'requirements': ['Retain nominations and missing sources, not fixed top lists as proof', 'No circular discovery/validation claim from same dataset', 'Server program clustering and per-program enrichment need a validated adapter'], 'source_status': 'review_only_engine'},
    'ml': {'routes': ['statistics.audit_prediction_split', 'code_execution.prepare_code_execution'], 'requirements': ['Split by independent biological unit', 'All learned preprocessing/selection/tuning inside nested train folds', 'Model selection assessed with outer folds; report calibration and uncertainty', 'SHAP on training fit is descriptive, not external validation'], 'source_status': 'review_only_engine'},
    'valid': {'routes': ['biomedical.assess_cohort_eligibility', 'reporting.audit_analysis_result'], 'requirements': ['No donor overlap', 'Freeze features, transformations, coefficients and thresholds once', 'No model refit per available external feature subset', 'Within-test-cohort standardization is transductive adaptation and must be declared'], 'source_status': 'review_only_engine'},
    'figs': {'routes': ['reporting.audit_analysis_result'], 'requirements': ['Receipt-bound selected figures only', 'Missing panels and failed/skipped stages explicitly labeled', 'Use existing scientific-figure skill for composition and visual review'], 'source_status': 'use_existing_delivery_workflow'},
    'report': {'routes': ['reporting.audit_analysis_result'], 'requirements': ['Actual stage receipts, versions, complete result tables and context', 'No fabricated sample removal, validation or significance', 'Use existing academic-delivery skill for actual editable report'], 'source_status': 'use_existing_delivery_workflow'},
}
REQUIRED = {'schema_version','project','expr_matrix','metadata','orientation','matrix_kind','sample_id_col','group_col','unit_col','case_label','control_label','covariates','paired','min_units','stages','context','study','reference'}
CONTEXT = {'species','model','assay','biological_unit','contrast','limitations','input_source','input_processing'}
STUDY = {'question','design','outcome_type','independent_unit','estimand','groups','repeated','clustered','primary_endpoints','missing_data','covariates'}

def _sha(data): return hashlib.sha256(data).hexdigest()
def _object_hash(value): return _sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8'))
def _label(value): return isinstance(value,str) and bool(value.strip()) and len(value)<=4000 and '\x00' not in value
def _relative(value):
    if not isinstance(value,str) or not value or '\\' in value or '\x00' in value or ':' in value:
        raise ValueError('Use a nonempty portable project-relative path')
    p=PurePosixPath(value)
    if p.is_absolute() or any(x in {'..','.'} for x in value.split('/')) or '' in value.split('/'):
        raise ValueError('Project-relative path cannot escape its selected root')
    return p
def _file(root,name):
    _relative(name)
    p=root.joinpath(*PurePosixPath(name).parts)
    for ancestor in [p,*p.parents]:
        if ancestor==root.parent: break
        if ancestor.is_symlink():raise ValueError('Symlink input is not allowed')
    p=p.resolve(strict=True)
    if not p.is_relative_to(root) or not p.is_file():raise ValueError('Select a contained regular file')
    return p

def guide_optional_bulk_pipeline() -> dict:
    """Describe the private 13-stage optional matrix workflow; launch/install/query nothing."""
    return {'success':True,'addon_version':VERSION,'placement':'server_compute_local_audit','optional':True,'stages':STAGES,
        'entrypoint':'Expression matrix plus metadata; FASTQ processing remains a separate existing server workflow',
        'legacy_scripts':'Non-executable review snapshots; never invoke original run.py',
        'network_default':'offline','formal_analysis_allowed':False,'engine_execution_performed':False,
        'limitations':['Routes identify existing tools, not proof of their installed runtime or scientific accuracy.','Individual analysis stages require input QC, design consultation, current environment and actual receipts.']}

def audit_optional_bulk_configuration(configuration: dict) -> dict:
    """Reject implicit scale/orientation, missing biological units and unsafe defaults; fit nothing."""
    c=configuration
    if not isinstance(c,dict):raise ValueError('Configuration must be an object')
    issues=[]
    absent=REQUIRED-set(c)
    if absent:issues.append('missing_fields:'+','.join(sorted(absent)))
    extra=set(c)-REQUIRED
    if extra:issues.append('unsupported_fields:'+','.join(sorted(extra)))
    if absent:return {'success':True,'configuration_pass':False,'issues':issues,'formal_analysis_allowed':False}
    if c['schema_version']!='1.1-private':issues.append('unsupported_schema')
    if not isinstance(c['project'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',c['project']):issues.append('invalid_project_label')
    for key in ['expr_matrix','metadata']:
        try:_relative(c[key])
        except ValueError:issues.append('unsafe_path:'+key)
    if c['expr_matrix']==c['metadata']:issues.append('input_role_collision')
    if c['orientation']!='genes_by_samples':issues.append('explicit_gene_by_sample_orientation_required')
    if c['matrix_kind'] not in {'raw_counts','log2_normalized'}:issues.append('explicit_supported_scale_required')
    for key in ['sample_id_col','group_col','unit_col']:
        if not isinstance(c[key],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',c[key]):issues.append('invalid_column:'+key)
    if len({c['sample_id_col'],c['group_col'],c['unit_col']})!=3:issues.append('column_role_collision')
    if not _label(c['case_label']) or not _label(c['control_label']) or c['case_label']==c['control_label']:issues.append('distinct_case_control_required')
    if type(c['paired']) is not bool:issues.append('explicit_pairing_boolean_required')
    if type(c['min_units']) is not int or not 3<=c['min_units']<=500:issues.append('minimum_three_units_required')
    cov=c['covariates'];names=[]
    if not isinstance(cov,list) or len(cov)>20:issues.append('invalid_covariates')
    else:
        for v in cov:
            if not isinstance(v,dict) or set(v)!={'name','type'} or v['type'] not in {'categorical','numeric'} or not isinstance(v['name'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',v['name']):issues.append('invalid_covariate_spec');continue
            names.append(v['name'])
        if len(names)!=len(set(names)) or set(names)&{c['group_col'],c['unit_col'],c['sample_id_col']}:issues.append('covariate_role_collision')
    stages=c['stages']
    if not isinstance(stages,list) or not stages or any(not isinstance(s,str) or s not in STAGES for s in stages) or len(stages)!=len(set(stages)):issues.append('explicit_known_unique_stages_required')
    ctx=c['context']
    if not isinstance(ctx,dict) or not CONTEXT<=set(ctx) or any(not ctx.get(k) for k in CONTEXT):issues.append('complete_source_and_biological_context_required')
    ref=c['reference']
    if not isinstance(ref,dict) or not {'assembly','annotation_version','gene_namespace'}<=set(ref) or any(not _label(ref[k]) for k in ['assembly','annotation_version','gene_namespace']):issues.append('explicit_reference_version_required')
    study=c['study']
    if not isinstance(study,dict) or not STUDY<=set(study):issues.append('statistics_consultation_inputs_required')
    else:
        try:
            from statistics_ext import guide_study_statistics
            guide_study_statistics(study)
        except ImportError:issues.append('existing_statistics_tool_unavailable')
        except (ValueError,TypeError):issues.append('invalid_statistics_consultation')
        if study.get('groups')!=2:issues.append('study_group_count_mismatch')
        if study.get('covariates')!=names:issues.append('study_covariates_mismatch')
        if study.get('repeated')!=c['paired']:issues.append('study_repetition_mismatch')
        if study.get('clustered') is not False:issues.append('clustered_design_requires_separate_server_model')
        if isinstance(ctx,dict) and study.get('independent_unit')!=ctx.get('biological_unit'):issues.append('study_unit_context_mismatch')
    return {'success':True,'configuration_pass':not issues,'issues':issues,'configuration_sha256':_object_hash(c),'formal_analysis_allowed':False,'limitations':['Configuration is caller-declared; source, estimand and unit identities need review.','No implicit log transform, sample intersection, missing-covariate omission, download or overwrite.']}

def _rank(columns):
    a=[[float(v) for v in row] for row in zip(*columns)];n=len(a);m=len(columns);r=0
    for j in range(m):
        scale=max(abs(a[i][j]) for i in range(n))
        if scale:
            for i in range(n):a[i][j]/=scale
    for j in range(m):
        pivot=max(range(r,n),key=lambda i:abs(a[i][j])) if r<n else None
        if pivot is None or abs(a[pivot][j])<1e-10:continue
        a[r],a[pivot]=a[pivot],a[r];v=a[r][j];a[r]=[x/v for x in a[r]]
        for i in range(r+1,n):
            v=a[i][j];a[i]=[x-v*y for x,y in zip(a[i],a[r])]
        r+=1
    return r

def _rows(path,limit_bytes):
    if path.stat().st_size>limit_bytes:raise ValueError('Selected file exceeds local audit budget; use server QC')
    data=path.read_bytes()
    if len(data)>limit_bytes:raise ValueError('Input changed or exceeded local audit budget')
    from io import StringIO
    reader=csv.reader(StringIO(data.decode('utf-8-sig')),delimiter='\t' if path.suffix.lower()=='.tsv' else ',')
    header=next(reader,[])
    if len(header)<2 or any(not s.strip() for s in header) or len(set(header))!=len(header):raise ValueError('Missing or duplicate header')
    return data,header,reader

def audit_optional_bulk_inputs(configuration: dict, project_directory: str, maximum_mb: int = 50) -> dict:
    """Bounded offline matrix/unit/design audit; formal inference still requires substantive sample QC."""
    check=audit_optional_bulk_configuration(configuration)
    if not check['configuration_pass']:return {**check,'input_contract_pass':False}
    if type(maximum_mb) is not int or not 1<=maximum_mb<=50:raise ValueError('Local audit budget must be 1..50 MB')
    root=Path(project_directory)
    if root.is_symlink() or not root.is_dir():raise ValueError('Select an existing regular project directory')
    root=root.resolve(strict=True);c=configuration
    matrix=_file(root,c['expr_matrix']);metadata=_file(root,c['metadata'])
    raw,header,reader=_rows(matrix,maximum_mb*1000000);samples=header[1:]
    if len(samples)>500:raise ValueError('More than 500 observations requires server QC')
    gids=set();lib=[0.]*len(samples);detected=[0]*len(samples);first=None;varying=0
    for row in reader:
        if len(row)!=len(header) or not row[0].strip() or row[0] in gids:raise ValueError('Malformed row or duplicate gene ID')
        gids.add(row[0])
        if len(gids)>60000 or len(gids)*len(samples)>2000000:raise ValueError('Matrix entry budget exceeded; use server QC')
        vals=[float(v) for v in row[1:]]
        if any(not math.isfinite(v) for v in vals):raise ValueError('Missing or nonfinite expression')
        if c['matrix_kind']=='raw_counts' and any(v<0 or v!=int(v) or v>2147483647 for v in vals):raise ValueError('Declared counts require bounded nonnegative integers; do not round normalized data')
        if first is None:first=vals
        varying+=len(set(vals))>1
        lib=[a+b for a,b in zip(lib,vals)];detected=[a+(b>0) for a,b in zip(detected,vals)]
    if not gids:raise ValueError('Empty matrix')
    mraw,mh,mreader=_rows(metadata,maximum_mb*1000000)
    needed=[c['sample_id_col'],c['group_col'],c['unit_col']]+[v['name'] for v in c['covariates']]
    if mh[0]!=c['sample_id_col'] or not set(needed)<=set(mh):raise ValueError('Metadata needs sample ID first and every declared unit/group/covariate')
    byid={}
    for row in mreader:
        if len(row)!=len(mh) or not row[0].strip() or row[0] in byid:raise ValueError('Malformed or duplicate metadata sample')
        if len(byid)>=500:raise ValueError('Metadata observation budget exceeded')
        record=dict(zip(mh,row))
        if any(not record[k].strip() for k in needed):raise ValueError('Missing unit, condition or covariate; no omission permitted')
        byid[row[0]]=record
    if set(samples)!=set(byid):raise ValueError('Matrix and metadata sample sets must match exactly; no silent intersection')
    rows=[byid[s] for s in samples];groups=[r[c['group_col']] for r in rows];units=[r[c['unit_col']] for r in rows]
    if set(groups)!={c['control_label'],c['case_label']}:raise ValueError('Prepare explicit two-group input files; do not silently discard other cohorts')
    pairs=Counter(zip(units,groups));pergroup={g:{u for u,v in pairs if v==g} for g in set(groups)}
    if max(pairs.values())>1:raise ValueError('Repeated unit/condition rows require reviewed aggregation or another model')
    if min(map(len,pergroup.values()))<c['min_units']:raise ValueError('Insufficient independent biological units')
    if c['paired']:
        if pergroup[c['case_label']]!=pergroup[c['control_label']]:raise ValueError('Pairing is incomplete')
    elif len(set(units))!=len(units):raise ValueError('Unpaired workflow cannot reuse biological units across groups')
    cols=[[1.]*len(rows),[float(g==c['case_label']) for g in groups]];names=['Intercept','case_minus_control']
    if c['paired']:
        for u in sorted(set(units))[1:]:cols.append([float(v==u) for v in units]);names.append('pair:'+u)
    for v in c['covariates']:
        vals=[r[v['name']] for r in rows]
        if v['type']=='numeric':
            vals=[float(x) for x in vals]
            if any(not math.isfinite(x) for x in vals):raise ValueError('Nonfinite numeric covariate')
            cols.append(vals);names.append(v['name'])
        else:
            levels=sorted(set(vals))
            if not 2<=len(levels)<=30:raise ValueError('Categorical covariate requires 2..30 explicitly observed levels')
            for level in levels[1:]:cols.append([float(x==level) for x in vals]);names.append(v['name']+':'+level)
    if len(cols)>50 or _rank(cols)!=len(cols) or len(rows)-len(cols)<3:raise ValueError('Confounded, oversized or saturated design')
    issues=[]
    if varying<20:issues.append('fewer_than_twenty_varying_features')
    if c['matrix_kind']=='raw_counts':
        if min(lib)<=0 or min(detected)<20:issues.append('empty_or_low_coverage_library')
        mid=sorted(lib);median=(mid[(len(mid)-1)//2]+mid[len(mid)//2])/2
        if median<=0 or any(x<median*.1 or x>median*10 for x in lib):issues.append('extreme_depth_requires_review')
    return {'success':True,'input_contract_pass':not issues,'issues':issues,'configuration_sha256':check['configuration_sha256'],
        'input_hashes':{'matrix':_sha(raw),'metadata':_sha(mraw)},'samples':len(samples),'genes':len(gids),'varying_genes':varying,
        'sample_order_sha256':_object_hash(samples),'independent_units':{g:len(v) for g,v in pergroup.items()},
        'design_columns':names,'residual_df':len(rows)-len(cols),'formal_analysis_allowed':False,
        'remaining_gates':['Existing statistical consultation reviewed against source design','Substantive sample QC: PCA, correlation, assay-specific quality and reviewed flags','Exact server runtime/package versions and fresh outputs'],
        'limitations':['This bounded structural audit is not full sample QC, formal inference, or verification of biological provenance.','Numeric rank uses a floating-point tolerance; inspect ill-conditioning in the actual model backend.','Normalized expression does not supply measured library depth; no 2^log proxy is labeled read depth.']}

def plan_optional_bulk_workflow(configuration: dict) -> dict:
    """Return an explicit optional 13-stage plan using existing tools; submit/execute/query nothing."""
    check=audit_optional_bulk_configuration(configuration)
    if not check['configuration_pass']:return {**check,'state':'blocked_configuration'}
    c=configuration;steps=[]
    for name in c['stages']:
        step={'stage':name,**STAGES[name],'execution_state':'not_run','placement':'server' if name not in {'qc','figs','report'} else 'local_review_or_server'}
        if name=='de':
            numeric=any(v['type']=='numeric' for v in c['covariates'])
            step['recommended_route']='advanced.run_designed_expression' if numeric and not c['paired'] else 'server.prepare_standard_pipeline' if numeric else 'transcriptomics.run_bulk_rnaseq' if c['matrix_kind']=='raw_counts' else 'transcriptomics.run_normalized_expression'
            step['method']='dream_explicit_design_required' if numeric and c['paired'] else 'limma_voom_or_edgeR_ql' if c['matrix_kind']=='raw_counts' else 'limma_ebayes_or_prespecified_treat'
        steps.append(step)
    return {'success':True,'state':'plan_only','addon_version':VERSION,'configuration_sha256':check['configuration_sha256'],'steps':steps,
        'mandatory_before_inference':['statistics.guide_study_statistics','audit_optional_bulk_inputs','qc.preflight_transcriptomics or exact-design server QC'],
        'formal_analysis_allowed':False,'submission_performed':False,'engine_execution_performed':False,'network_requests_performed':False,
        'limitations':['Review-only source scripts remain disabled; this plan does not create a working replacement engine.','Large computation uses an existing authorized server route and actual scheduler receipts.','Default core workflow pack and public release are unchanged.']}

def audit_optional_bulk_outputs(configuration: dict, output_directory: str, receipt_file: str, expected_input_hashes: dict) -> dict:
    """Check selected returned stage/output hashes and exact design binding; establish no scientific truth."""
    check=audit_optional_bulk_configuration(configuration)
    if not check['configuration_pass']:return {**check,'receipt_consistent':False}
    root=Path(output_directory)
    if root.is_symlink() or not root.is_dir():raise ValueError('Select a regular returned output directory')
    root=root.resolve();receipt=_file(root,receipt_file)
    if receipt.stat().st_size>1000000:raise ValueError('Receipt exceeds review budget')
    r=json.loads(receipt.read_text(encoding='utf8'));issues=[]
    if not isinstance(expected_input_hashes,dict) or set(expected_input_hashes)!={'matrix','metadata'} or any(not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) for h in expected_input_hashes.values()):raise ValueError('Provide independently checked exact matrix and metadata hashes')
    if r.get('schema')!='bulk-returned-v1':issues.append('unsupported_receipt_schema')
    if r.get('configuration_sha256')!=check['configuration_sha256']:issues.append('configuration_binding_mismatch')
    if r.get('input_hashes')!=expected_input_hashes:issues.append('input_binding_mismatch')
    if not isinstance(r.get('backend_versions'),dict) or not r['backend_versions'] or any(not _label(v) for v in r['backend_versions'].values()):issues.append('missing_backend_versions')
    stages=r.get('stages');files=r.get('outputs');checked=0
    if not isinstance(stages,dict) or set(stages)!=set(configuration['stages']):issues.append('stage_set_mismatch')
    elif any(v!='succeeded' for v in stages.values()):issues.append('incomplete_failed_or_skipped_stage')
    if not isinstance(files,list) or not 1<=len(files)<=500:issues.append('missing_or_oversized_output_manifest')
    else:
        seen=set();covered=set()
        for item in files:
            if not isinstance(item,dict) or set(item)!={'path','sha256','stage','bytes'} or item.get('stage') not in configuration['stages']:issues.append('invalid_output_entry');continue
            name=item['path']
            if name in seen or name==receipt_file:issues.append('duplicate_or_receipt_output');continue
            seen.add(name);covered.add(item['stage'])
            try:
                p=_file(root,name)
                if type(item['bytes']) is not int or p.stat().st_size!=item['bytes']:issues.append('output_size_mismatch');continue
                h=hashlib.sha256()
                with p.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
                if h.hexdigest()!=item['sha256']:issues.append('output_hash_mismatch')
                else:checked+=1
            except (ValueError,FileNotFoundError):issues.append('missing_or_unsafe_output')
        if covered!=set(configuration['stages']):issues.append('stage_missing_output')
    return {'success':True,'receipt_consistent':not issues,'completed_in_declared_snapshot':not issues,'checked_outputs':checked,'issues':issues,
        'scientific_validity_established':False,'live_server_observed':False,
        'limitations':['Caller-supplied snapshot and hashes need independent scheduler/QC/source review.','A succeeded label or matching bytes does not establish sample exclusion, statistical validity, activity or causality.','Unknown submissions must not be retried automatically.']}
