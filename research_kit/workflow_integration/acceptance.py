"""Bounded returned-result verification. Does not fit models or process raw scientific data."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re

MAX=8_000_000
def load(path):
    p=Path(path)
    if not 0<p.stat().st_size<=MAX:raise ValueError('Return selected bounded summaries')
    return json.loads(p.read_text(encoding='utf-8-sig'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def sha(path):
    p=Path(path)
    if not 0<p.stat().st_size<=MAX:raise ValueError('Only bounded selected summaries may be hashed here')
    return hashlib.sha256(p.read_bytes()).hexdigest()
def selected(root,name):
    if not isinstance(name,str) or not name or ':' in name or '\\' in name or name.startswith('/') or any(s in ('','..','.') for s in name.split('/')):raise ValueError('Unsafe returned path')
    path=(Path(root)/name).resolve(strict=True)
    if not path.is_relative_to(Path(root).resolve()) or not path.is_file():raise ValueError('Returned file escapes scope')
    return path
def rows(path):
    if Path(path).stat().st_size>MAX:raise ValueError('Select smaller summary')
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter='\t');header=reader.fieldnames
        if not header or len(set(header))!=len(header):raise ValueError('Missing or duplicate result columns')
        result=[]
        for row in reader:
            if len(result)>=20000 or None in row or any(v is None for v in row.values()):raise ValueError('Unbounded or malformed returned table')
            result.append(row)
    return header,result
def number(value):
    if isinstance(value,bool):raise ValueError('Boolean is not numeric observation')
    x=float(value)
    if not math.isfinite(x):raise ValueError('Nonfinite observation')
    return x

def inspect_result(request_file,receipt_file,returned_root,backend_root,selection):
    request=load(request_file);receipt=load(receipt_file);issues=[]
    if sha(request_file)!=receipt.get('request_sha256') or request.get('plan_sha256')!=receipt.get('plan_sha256'):issues.append('request_or_plan_binding_changed')
    if receipt.get('state')!='COMPLETED' or type(receipt.get('exit_code')) is not int or receipt['exit_code']!=0:issues.append('server_run_not_completed')
    if request.get('expected_host')!=receipt.get('host') or request.get('node_role')!='compute':issues.append('compute_host_mismatch')
    if request.get('source_sha256')!=receipt.get('source_sha256'):issues.append('request_backend_source_binding_changed')
    expected_inputs={r['id']:r['sha256'] for r in request['inputs']};received_inputs={r['id']:r['sha256'] for r in receipt.get('inputs',[])}
    if len(received_inputs)!=len(receipt.get('inputs',[])) or expected_inputs!=received_inputs:issues.append('actual_scientific_input_set_changed')
    for name,digest in receipt.get('source_sha256',{}).items():
        source=selected(backend_root,name)
        if sha(source)!=digest:issues.append('server_source_changed:'+name)
    expected_source={p.name for p in Path(backend_root).glob('*') if p.suffix in {'.py','.R','.json'}}
    if set(receipt.get('source_sha256',{}))!=expected_source:issues.append('incomplete_backend_source_binding')
    output_rows=receipt.get('outputs',[])
    output_paths=[r['path'] for r in output_rows]
    if len(set(output_paths))!=len(output_paths):issues.append('duplicate_output_paths')
    for row in output_rows:
        if not re.fullmatch('[a-f0-9]{64}',str(row.get('sha256',''))) or type(row.get('bytes')) is not int or row['bytes']<=0:issues.append('invalid_output_identity')
    required=set(request['required_roles']);actual={r['role'] for r in output_rows}
    for missing in sorted(required-actual):issues.append('required_role_missing:'+missing)
    bound={r['path']:r for r in output_rows};local={'_by_path':{},'_by_role':{}};total=0
    if len(bound)!=len(output_rows):issues.append('duplicate_output_receipt_path')
    for name in selection:
        if name not in bound:issues.append('unregistered_selected_result:'+name);continue
        path=selected(returned_root,name);total+=path.stat().st_size
        if total>64_000_000:raise ValueError('Return fewer summaries per review')
        if sha(path)!=bound[name]['sha256'] or path.stat().st_size!=bound[name]['bytes']:issues.append('returned_file_changed:'+name)
        local[bound[name]['role']]=path
        local['_by_role'].setdefault(bound[name]['role'],[]).append(path)
        local['_by_path'][name]=path
    if request['backend']=='omics71':
        for role,path in list(local.items()):
            if role.startswith('preview_primary_') and role[len('preview_primary_'):] not in local:local[role[len('preview_primary_'):]]=path
    # A few status strings cannot substitute for the actual analytical outputs.
    needs={
      'ml':{'predictions','model_metrics','split_provenance','feature_contract'},
      'survival':{'predictions','model_metrics','split_provenance','feature_contract'},
      'graph_training':{'predictions','model_metrics','training_history','feature_contract'},
      'singlecell':{'cell_qc','attrition','descriptive_markers','diagnostics'},
      'scvi':{'cell_qc','attrition','training_history','diagnostics'},
      'pseudobulk':{'pseudobulk_eligibility','diagnostics'},
      'multiomics_concordance':{'cross_modal_association','diagnostics'},
      'molecular_qc':{'chemical_qc','diagnostics'},'pose_qc':{'chemical_qc','pose_physical_checks','diagnostics'},
      'md_analysis':{'trajectory_observables','rmsf','contacts','diagnostics'},
      'free_energy':{'thermodynamic_ledger','free_energy_uncertainty'},'kinetics':{'kinetics_uncertainty'}}
    needs['vina_docking']={'docking_campaign','diagnostics'}
    if request['backend']=='ml' and request['parameters'].get('shap') is not None:
        needs['ml'].update({'shap_summary','shap_identity','shap_diagnostics'})
        for role_path,row in bound.items():
            if row['role']=='shap_diagnostics' and role_path not in selection:issues.append('model_shap_diagnostic_not_selected:'+role_path)
        for name,path in local['_by_path'].items():
            if bound[name]['role']=='shap_diagnostics' and load(path).get('additivity_pass') is not True:issues.append('shap_additivity_failed_or_missing:'+name)
    needs['matrix_qc']={'matrix_qc','sample_qc','design_matrix','pca_scores','correlation'}
    needs['structure_qc']={'atom_qc','residue_qc','residue_mapping_qc','structure_qc'}
    needs['af3']={'af3_sample_table','diagnostics'}
    needs.update({'msa_qc':{'msa_qc','msa_row_qc'},'msa_filter':{'msa_qc','msa_row_qc','msa_filter_decisions'},
                  'msa_search':{'msa_qc','msa_row_qc'},'msa_align':{'msa_qc','msa_row_qc'},'msa_pair':{'pairing_qc'},
                  'af3_data_pipeline':{'msa_registry','diagnostics'}})
    from native_acceptance import SUMMARY_ROLES,inspect_native
    from server.completion_contracts import ROUTES as COMPLETION,COMMON_ROLES
    if request['backend'] in COMPLETION:
        from completion_acceptance import inspect_completion
        needs[request['backend']]=set(COMMON_ROLES)
        issues.extend(inspect_completion(request,receipt,local,load,rows))
    needs.update({k:set(v)|{'runtime_warnings'} for k,v in SUMMARY_ROLES.items()})
    if request['backend'] in SUMMARY_ROLES:
        for name,row in bound.items():
            if row['role'] in SUMMARY_ROLES[request['backend']] and name not in selection:issues.append('native_summary_member_not_selected:'+name)
        issues.extend(inspect_native(request,local,load,rows))
    if request['backend']=='omics71':
        from branch71_acceptance import inspect_branch
        registry=load(Path(backend_root)/'branches71.json')
        branch=registry[request['parameters']['analysis_id']]
        needs['omics71']=set(branch['required_roles'])|set(branch.get('required_proof_roles',[]))|{'analysis_qc','analysis_diagnostics','analysis_sensitivity','implementation_record'}
        issues.extend(inspect_branch(request,receipt,local,branch))
    needs[request['backend']].add('runtime_warnings') if request['backend'] in needs else None
    if request['backend']=='r_omics':
        method=request['parameters']['method'];needs['r_omics']={
         'DESeq2':{'sample_qc','design_matrix','differential','diagnostics','feature_filter'},
         'limma':{'sample_qc','design_matrix','differential','diagnostics','feature_filter'},
         'edgeR_QL':{'sample_qc','design_matrix','differential','diagnostics','feature_filter'},
         'limma_voom':{'sample_qc','design_matrix','differential','diagnostics','feature_filter'},
         'ORA':{'enrichment','diagnostics'},'fgsea':{'enrichment','diagnostics'},
         'WGCNA':{'network_qc','soft_threshold','modules','module_eigengenes','module_membership','diagnostics'},
         'MOFA2':{'factor_scores','factor_loadings','view_variance','diagnostics'}}[method]
        needs['r_omics'].add('runtime_warnings')
        if method=='MOFA2':
            for view in request['parameters']['view_ids']:
                if 'weights_'+view+'.tsv' not in selection:issues.append('modality_loading_not_returned:'+view)
        if method=='WGCNA' and any(x['id']=='reference_matrix' for x in request['inputs']):
            needs['r_omics'].add('module_preservation')
    if request['backend'] not in needs:issues.append('backend_return_inspector_not_implemented')
    for role in sorted(needs.get(request['backend'],set())-set(local)):issues.append('actual_diagnostic_not_selected:'+role)
    if 'runtime_warnings' in local:
        for row in load(local['runtime_warnings']):
            if row.get('category') in {'ConvergenceWarning','FitFailedWarning'}:issues.append('model_convergence_or_fit_warning')
    if 'predictions' in local:
        header,data=rows(local['predictions'])
        if not data:issues.append('empty_prediction_table')
        for row in data:
            for key,value in row.items():
                if key.startswith('probability_') and value and not 0<=number(value)<=1:issues.append('invalid_predicted_probability')
            probability=[number(value) for key,value in row.items() if key.startswith('probability_') and value]
            if probability and abs(sum(probability)-1)>1e-5:issues.append('probabilities_do_not_sum_to_one')
    if 'split_provenance' in local:
        for row in load(local['split_provenance']):
            if set(row['train_units'])&set(row['validation_units']):issues.append('actual_fold_unit_leakage')
    if 'differential' in local:
        header,data=rows(local['differential'])
        fields={'feature_id'}
        if not fields<=set(header) or not data:issues.append('differential_table_missing_identity_or_rows')
        ids=[r.get('feature_id') for r in data]
        if len(set(ids))!=len(ids):issues.append('duplicate_tested_feature')
        for row in data:
            for key in ('pvalue','padj','P.Value','adj.P.Val'):
                if key in row and row[key] not in ('NA','NaN','') and not 0<=number(row[key])<=1:issues.append('invalid_pvalue')
        if not any(k in header for k in ('log2FoldChange','logFC')) or not any(k in header for k in ('lfcSE','t')):issues.append('effect_or_uncertainty_statistic_missing')
    if 'pose_physical_checks' in local:
        header,data=rows(local['pose_physical_checks']);checks=request['parameters']['mandatory_pose_checks']
        for key in checks:
            if key not in header:issues.append('physical_pose_check_missing:'+key)
            elif any(row[key].strip().lower() not in {'true','1'} for row in data):issues.append('physical_pose_check_failed_or_unassessed:'+key)
        if not data:issues.append('no_pose_checks')
    if 'trajectory_observables' in local:
        _,data=rows(local['trajectory_observables']);last=None
        for row in data:
            t=number(row['time_ps'])
            if last is not None and t<=last:issues.append('nonmonotonic_trajectory_time')
            last=t
            if number(row['rmsd_angstrom'])<0 or number(row['radius_gyration_angstrom'])<=0:issues.append('invalid_trajectory_observation')
    if 'af3_sample_table' in local:
        header,data=rows(local['af3_sample_table']);sample_keys=[(r['seed'],r['sample']) for r in data]
        if len(set(sample_keys))!=len(sample_keys):issues.append('duplicate_af3_seed_sample')
        for row in data:
            for field in ('ptm','iptm','selected_pair_iptm'):
                if row.get(field) not in (None,'','NA') and not 0<=number(row[field])<=1:issues.append('invalid_af3_confidence')
        if request['parameters'].get('selected_pair') and any(row.get('selected_pair_iptm') in ('','NA',None) for row in data):issues.append('selected_interface_confidence_missing')
    # Evaluate prespecified observations directly from selected generated diagnostics, never caller pass flags.
    for gate in request.get('acceptance_rules',[]):
        role=gate['role'];name=gate['field'];op=gate['operator']
        if role not in local:issues.append('gate_source_not_returned:'+gate['id']);continue
        if not gate.get('definition') or not gate.get('unit') or not gate.get('threshold_basis'):raise ValueError('A numerical cutoff requires definition, unit and scientific basis')
        explicit=gate.get('source_path')
        if explicit is not None:
            if explicit not in local['_by_path'] or bound[explicit]['role']!=role:issues.append('gate_explicit_source_not_selected:'+gate['id']);continue
            gate_path=local['_by_path'][explicit]
        else:
            if len(local['_by_role'].get(role,[]))>1:issues.append('ambiguous_gate_source_role:'+gate['id']);continue
            gate_path=local[role]
        value=load(gate_path)
        for part in name.split('.'):
            if isinstance(value,list) and part.isdigit() and int(part)<len(value):value=value[int(part)]
            elif isinstance(value,dict) and part in value:value=value[part]
            else:value=None;break
        if value is None:issues.append('required_observation_missing:'+gate['id']);continue
        if op=='eq':passed=type(value)==type(gate['bound']) and value==gate['bound']
        elif op=='ge':passed=number(value)>=number(gate['bound'])
        elif op=='le':passed=number(value)<=number(gate['bound'])
        else:raise ValueError('Unsupported acceptance operator')
        if not passed:issues.append('observed_diagnostic_failed:'+gate['id'])
    if not request.get('acceptance_rules'):issues.append('no_prespecified_scientific_acceptance_rules')
    return {'state':'RETURN_CHECKS_PASS' if not issues else 'HOLD','issues':sorted(set(issues)),
       'receipt_sha256':sha(receipt_file),'request_sha256':sha(request_file),'plan_sha256':request['plan_sha256'],
       'selected_summary_bytes_verified':not any('changed' in i for i in issues),'selected_roles':sorted(k for k in local if not k.startswith('_')),
       'server_live_process_observed':False,'unselected_large_outputs':'server-declared hashes only, not locally downloaded/verified',
       'scientific_validity':'requires source/design/physical-model review; not established by engineering acceptance',
       'private_only':True,'automatic_resubmission':False}
