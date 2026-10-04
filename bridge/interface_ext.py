"""Scoped scientific software state, hash-bound plans and reproducible private exports."""
import json
import re
from pathlib import Path
from academic_common import artifact, digest, read_file
from evidence import atomic_json
from software_ext import inspect_cytoscape_health
from zotero_ext import inspect_zotero_connection, read_zotero_library


def _get(route,port):
    import requests
    if type(port) is not int or not 1<=port<=65535 or not re.fullmatch(r'[A-Za-z0-9/]+',route):raise ValueError('Fixed local CyREST route required')
    session=requests.Session();session.trust_env=False
    try:
        r=session.get('http://localhost:'+str(port)+'/v1/'+route,timeout=(5,30),allow_redirects=False,stream=True)
        try:
            if not 200<=r.status_code<300:raise ValueError('Local CyREST operation refused')
            raw=bytearray()
            for chunk in r.iter_content(65536):
                raw.extend(chunk)
                if len(raw)>5_000_000:raise ValueError('CyREST response exceeds scope')
            return bytes(raw)
        finally:r.close()
    finally:session.close()


def inspect_scientific_interfaces(zotero_port: int = 23119, cytoscape_port: int = 1234) -> dict:
    """Check local Zotero handshake and Cytoscape version/layouts; never list library contents or import a network."""
    return {'success':True,'zotero':inspect_zotero_connection(zotero_port),'cytoscape':inspect_cytoscape_health(cytoscape_port),
            'limitations':['Connection responses, GUI validation, exports and writes have distinct receipts.','Private library reads require an explicitly selected item or collection scope.']}


def export_zotero_snapshot(library: str, item_keys: list, port: int = 23119) -> dict:
    """Export an explicitly authorized item set with original Zotero fields/versions and provenance; never write or cloud-sync."""
    snapshot=read_zotero_library(library,item_keys=item_keys,port=port,limit=25)
    raw=json.dumps(snapshot['records'],ensure_ascii=False,indent=2)
    return artifact('zotero_export',{'source':'local_zotero','requested_item_keys':item_keys,'records':len(snapshot['records']),
            'source_versions':[{'key':r.get('key'),'version':r.get('version')} for r in snapshot['records']],
            'content_sha256':digest(raw.encode()),'coverage_complete':snapshot['coverage_complete'],
            'limitations':['This request must be authorized for the selected private items.','Original citation fields are retained in JSON; Word citation rendering and whole-library coverage are not verified.']},
            {'zotero_items.json':raw})


def export_cytoscape_snapshot(network_id: int, port: int = 1234) -> dict:
    """Read one selected running Cytoscape network with version metadata and source hash; no layout or library mutation."""
    if type(network_id) is not int or network_id<0:raise ValueError('Explicit numeric network ID required')
    version=_get('version',port);raw=_get('networks/'+str(network_id),port);json.loads(raw)
    return artifact('cytoscape_snapshot',{'network_id':network_id,'network_sha256':digest(raw),'version':json.loads(version),
            'limitations':['Private network JSON is an export receipt, not rendered or scientifically validated PPI evidence.','Restoring into Cytoscape remains an explicit import operation.']},
            {'network.json':raw,'version.json':version})


def prepare_cytoscape_revision(network_id: int, layout: str, port: int = 1234) -> dict:
    """Preview a single layout operation tied to the exact selected network and running version; do not invoke it."""
    if type(network_id) is not int or network_id<0 or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',layout):raise ValueError('Select a numeric network and named layout')
    layouts=json.loads(_get('apply/layouts',port))
    if layout not in layouts:raise ValueError('Selected layout is unavailable')
    network=_get('networks/'+str(network_id),port);version=_get('version',port)
    plan={'schema':1,'network_id':network_id,'layout':layout,'port':port,'network_sha256':digest(network),'version_sha256':digest(version)}
    raw=json.dumps(plan,sort_keys=True,separators=(',',':'))
    return artifact('cytoscape_plan',{'state':'prepared','plan_sha256':digest(raw.encode()),'operation':'layout',
            'limitations':['Review this exact private plan before dispatch.','No selected network is modified during preparation.']},{'plan.json':raw})


def apply_cytoscape_revision(plan_path: str, reviewed_sha256: str) -> dict:
    """Dispatch one explicitly reviewed local layout plan; block changed networks/versions and repeated unknown outcomes."""
    path,raw=read_file(plan_path,100_000)
    if not re.fullmatch(r'[a-f0-9]{64}',reviewed_sha256) or digest(raw)!=reviewed_sha256:raise ValueError('Reviewed exact plan hash required')
    plan=json.loads(raw)
    if set(plan)!={'schema','network_id','layout','port','network_sha256','version_sha256'} or plan['schema']!=1:raise ValueError('Unsupported plan')
    if type(plan['network_id']) is not int or plan['network_id']<0 or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',plan['layout']):raise ValueError('Invalid network or layout')
    route='networks/'+str(plan['network_id'])
    if digest(_get(route,plan['port']))!=plan['network_sha256'] or digest(_get('version',plan['port']))!=plan['version_sha256']:raise ValueError('Network or version changed; prepare a new plan')
    ledger=path.with_name('dispatch_receipt.json')
    # Create exclusively before invoking a mutating GET endpoint. Unknown results are never retried.
    with ledger.open('x',encoding='utf8') as f:json.dump({'state':'dispatch_outcome_unknown','plan_sha256':reviewed_sha256},f)
    response=_get('apply/layouts/'+plan['layout']+'/'+str(plan['network_id']),plan['port'])
    after=_get(route,plan['port'])
    receipt={'state':'operation_response_received','plan_sha256':reviewed_sha256,'response_sha256':digest(response),'after_network_sha256':digest(after),'visual_validation':False}
    atomic_json(ledger,receipt)
    return artifact('cytoscape_revision',{'success':True,**receipt,'limitations':['A successful API response is not human visual inspection or scientific validation.','A failed/unknown dispatch is preserved and must be investigated before any new plan.']},{'after_network.json':after})
