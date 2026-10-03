"""Private outbound-data policy and exposure review. Never publishes settings or personal deny terms."""
import json
import os
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
CONFIG=HERE/'privacy_config.json'
PATTERNS={
    'absolute_local_path':r'(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:home|Users|scratch|mnt|workspace|projects?)/',
    'address_literal':r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',
    'email':r'[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
    'credential':r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|(?:ghp_|github_pat_|sk-)[A-Za-z0-9_]{20,}',
}


def policy():
    data=json.loads(CONFIG.read_text(encoding='utf8')) if CONFIG.exists() else {'mode':'public_data_only','allow_remote_gateway':False,'deny_terms':[]}
    if data.get('mode') not in {'offline','public_data_only'} or type(data.get('allow_remote_gateway',False)) is not bool or not isinstance(data.get('deny_terms',[]),list): raise ValueError('Invalid private privacy policy; refusing network operations')
    if any(not isinstance(x,str) or not x.strip() for x in data.get('deny_terms',[])): raise ValueError('Invalid private deny terms')
    return data


def audit_outbound_parameters(parameters: dict) -> dict:
    """Flag private paths, literal addresses, emails, credential formats and privately configured identifiers without echoing their values."""
    if not isinstance(parameters,dict): raise ValueError('Provide parameters as an object')
    text=json.dumps(parameters,ensure_ascii=False,default=str)
    findings=[key for key,pattern in PATTERNS.items() if re.search(pattern,text)]
    config=policy()
    if any(term.casefold() in text.casefold() for term in config.get('deny_terms',[])): findings.append('private_identifier')
    if parameters.get('sensitive_data') is True: findings.append('explicit_sensitive_data')
    return {'success':True,'outbound_gate_pass':not findings and config['mode']!='offline','issues':findings+(['offline_policy'] if config['mode']=='offline' else []),'limitations':['Pattern checks cannot recognize every patient identifier, personal name or sensitive scientific datum.','Public retrieval must contain only authorized public query information.','The function reports categories only and does not transmit parameters.']}


def enforce_outbound(parameters):
    result=audit_outbound_parameters(parameters or {})
    if not result['outbound_gate_pass']: raise ValueError('Privacy policy blocked outbound request; review the private data locally')


def inspect_privacy_policy() -> dict:
    """Report privacy mode and exposure boundaries without disclosing private identifiers or file paths."""
    data=policy()
    return {'success':True,'mode':data['mode'],'remote_gateway_allowed':data.get('allow_remote_gateway',False),'private_deny_terms_configured':bool(data.get('deny_terms')),'external_model_required':False,'automatic_result_upload':False,'automatic_ssh_connection':False,'limitations':['This is a configured policy review, not proof of complete anonymity.','Existing account ownership and previously published material must be reviewed separately.','Generated client settings, software registries, receipts and outputs must stay private.']}
