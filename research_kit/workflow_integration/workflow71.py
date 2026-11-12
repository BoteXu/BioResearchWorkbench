"""Private DAG review and current acceptance invalidation. This module submits nothing."""
from pathlib import Path
import json,re,hashlib
from acceptance import load,sha,selected

def audit_plan(root,plan):
    if plan.get('public_upload') is not False or plan.get('automatic_dispatch') is not False:raise ValueError('Private reviewed preparation only')
    nodes=plan.get('nodes',[]);seen={};lineage=[]
    if not nodes:raise ValueError('No explicitly selected workflow stages')
    for node in nodes:
        name=node['node_id']
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,60}',name) or name in seen:raise ValueError('Unique safe stage identifiers required')
        source=selected(root,node['project_path'])
        if sha(source)!=node['project_sha256']:raise ValueError('Scientific stage source changed')
        project=load(source)
        if project.get('public_upload') is not False or project.get('server_execution_authorized') is not False:raise ValueError('Prepared disabled stage required')
        for key in ('independent_unit','estimand'):
            if not project.get('statistical_plan',{}).get(key):raise ValueError('Missing biological unit/estimand')
        dependencies=node.get('depends_on',[])
        if any(d not in seen for d in dependencies):raise ValueError('DAG must be topological; missing/cyclic dependency')
        for edge in node.get('input_links',[]):
            if edge['from_node'] not in dependencies or edge['to_input'] not in {r['id'] for r in project['inputs']}:raise ValueError('Undeclared upstream stage or target input')
            parent=seen[edge['from_node']]
            if parent['statistical_plan']['independent_unit']!=project['statistical_plan']['independent_unit']:raise ValueError('Cross-flow independent units cannot silently change')
            if not edge.get('transform') or not edge.get('semantic_review'):raise ValueError('Explicit data conversion and scientific meaning review required')
            if not edge.get('source_role') or not edge.get('target_required_columns') or not re.fullmatch('[a-f0-9]{64}',edge.get('handoff_spec_sha256','')):raise ValueError('Bind exact source role, target schema and reviewed materialization specification')
            if edge['transform'] not in {'identity','liana_to_donor_lr','scirpy_to_clone_cells','fgsea_leading_members','stable_one_to_one_identifiers'}:raise ValueError('No executable fixed transform for this link; provide a reviewed exact matching input instead')
            lineage.append({'from':edge['from_node'],'to':name,'input':edge['to_input'],'transform':edge['transform'],'state':'WAITING_FOR_REAL_ACCEPTED_OUTPUT'})
        seen[name]=project
    return {'state':'PREPARED_NOT_SUBMITTED','node_count':len(nodes),'edges':lineage,'scientific_runtime':'NOT_RUN_THIS_UPGRADE',
      'unknown_submission':'inspect_receipts_never_retry','public_upload':False}

def current_acceptance(package_root,receipt,request):
    """Source/dependency/reference edits expire current acceptance without erasing history."""
    issues=[];current={p.name:sha(p) for p in (Path(package_root)/'server').glob('*') if p.is_file() and p.suffix in {'.py','.R','.json'}}
    if current!=receipt.get('source_sha256'):issues.append('source_changed')
    if receipt.get('state')!='COMPLETED':issues.append('last_attempt_not_completed')
    if request.get('plan_sha256')!=receipt.get('plan_sha256'):issues.append('parameters_or_inputs_changed')
    if not receipt.get('versions'):issues.append('runtime_versions_absent')
    issues.append('no_fresh_live_dependency_and_environment_observation')
    return {'historical_success':receipt.get('state')=='COMPLETED','current_environment_verified':False,
      'expiry_reasons':issues,'scientific_validity':'not_established','live_server_observed':False}
