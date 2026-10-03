"""Fixed local Zotero routes, bounded reads and previewed writes with conflict/unknown-outcome protection."""
import json
import re
import uuid
from pathlib import Path
from academic_common import HERE, artifact, digest, read_file, rows, text
from evidence import atomic_json


def _key(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z0-9]{8}',value):
        raise ValueError('Provide a Zotero item or collection key')
    return value


def _scope(library):
    if library == 'user': return 'users/0'
    if re.fullmatch(r'group:[1-9][0-9]{0,12}',library):return 'groups/'+library.split(':')[1]
    raise ValueError('Select user or an explicit group:number library')


class LocalZotero:
    def __init__(self,port):
        if type(port) is not int or not 1<=port<=65535:raise ValueError('Provide a local port')
        import requests
        self.session=requests.Session();self.session.trust_env=False
        self.base='http://localhost:'+str(port)+'/api/'

    def close(self):self.session.close()

    def call(self,method,route,params=None,payload=None,server_id=None,key=None):
        if '..' in route or not re.fullmatch(r'[A-Za-z0-9/]*',route):raise ValueError('Only fixed local API routes are supported')
        headers={'Zotero-API-Version':'3'}
        if server_id:headers['Zotero-Server-ID']=server_id
        if key:headers['Zotero-API-Key']=key
        response=self.session.request(method,self.base+route,params=params,json=payload,headers=headers,timeout=(5,40),allow_redirects=False,stream=True)
        try:
            if not 200<=response.status_code<300:
                # Never echo token, private request body, URLs, or response body in errors.
                raise ValueError('Local Zotero request refused; HTTP '+str(response.status_code))
            chunks=[];size=0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>5_000_000:raise ValueError('Local Zotero response exceeds bounded scope')
                chunks.append(chunk)
            raw=b''.join(chunks)
            # /api/ is a plain-text handshake in current Zotero, not a JSON object.
            content=json.loads(raw) if raw.strip() and route else None
            return content,dict(response.headers)
        finally:response.close()


def inspect_zotero_connection(port: int = 23119) -> dict:
    """Check a local Zotero API without scanning a library or requesting write authorization."""
    client=LocalZotero(port)
    try:
        _,headers=client.call('GET','')
        types,_=client.call('GET','itemTypes')
        if not isinstance(types,list):raise ValueError('Local endpoint did not return Zotero item types')
        return {'success':True,'state':'responding','api_version':headers.get('Zotero-API-Version'),
                'instance_identity_available':bool(headers.get('Zotero-Server-ID')),'local_only':True,
                'limitations':['An API response is not validation of Word integration, attachments, synchronization or writes.']}
    except Exception as exc:
        return {'success':False,'state':'unavailable_or_disabled','error_type':type(exc).__name__,
                'limitations':['Start Zotero and explicitly enable communication with local applications. No application is installed or launched.']}
    finally:client.close()


def read_zotero_library(library: str, collection_key: str = '', item_keys: list = None, query: str = '', include_children: bool = False, limit: int = 50, start: int = 0, port: int = 23119) -> dict:
    """Read one explicit collection or item set, including optional bounded notes/annotations; never scan an unspecified whole library."""
    scope=_scope(library)
    if type(limit) is not int or not 1<=limit<=100 or type(start) is not int or start<0 or type(include_children) is not bool:raise ValueError('Select a bounded page and explicit child flag')
    keys=item_keys or []
    if not isinstance(keys,list) or len(keys)>25 or len(set(keys))!=len(keys):raise ValueError('Select at most 25 distinct item keys')
    keys=[_key(k) for k in keys]
    if bool(collection_key)==bool(keys):raise ValueError('Select exactly one collection or item set')
    if query and (not isinstance(query,str) or len(query)>500):raise ValueError('Local query is too long')
    if collection_key:route=scope+'/collections/'+_key(collection_key)+'/items'
    else:route=scope+'/items'
    params={'format':'json','limit':limit,'start':start}
    if keys:params['itemKey']=','.join(keys)
    if query:params['q']=query
    client=LocalZotero(port)
    try:
        # Pin subsequent requests to the same database when supported.
        _,initial=client.call('GET','');identity=initial.get('Zotero-Server-ID')
        data,headers=client.call('GET',route,params=params,server_id=identity)
        records=rows(data,100);children=[]
        if include_children:
            if len(records)>25:raise ValueError('Child retrieval requires at most 25 parent items')
            for item in records:
                if item.get('data',{}).get('itemType') in {'attachment','note','annotation'}:continue
                found,h=client.call('GET',scope+'/items/'+_key(item['key'])+'/children',params={'limit':100,'format':'json'},server_id=identity)
                children.append({'parent_key':item['key'],'records':rows(found,100),'coverage_complete':int(h.get('Total-Results',len(found)))<=100})
        total=int(headers.get('Total-Results',len(records)))
        return artifact('zotero_read',{'library':library,'collection_key':collection_key,'records':records,'children':children,
            'total_results':total,'start':start,'next_start':start+len(records) if start+len(records)<total else None,
            'coverage_complete':start==0 and len(records)>=total,'source':'local_zotero','instance_bound':bool(identity),
            'limitations':['Notes, annotations and authors may be private. Do not send them to public services.','A partial page is not an exhaustive library search. No write or cloud request occurs.']})
    finally:client.close()


def read_zotero_attachment(library: str, attachment_key: str, allowed_folder: str, port: int = 23119) -> dict:
    """Resolve a local Zotero attachment to an explicitly permitted folder; refuse network/remote file URLs and symlink escape."""
    from urllib.parse import urlsplit,unquote
    import os
    scope=_scope(library);key=_key(attachment_key);root=Path(allowed_folder).resolve(strict=True)
    if not root.is_dir():raise ValueError('Provide an explicit permitted attachment folder')
    client=LocalZotero(port)
    try:
        # Use JSON item metadata, not the /file redirect which can contain an arbitrary URI.
        item,_=client.call('GET',scope+'/items/'+key)
        data=item.get('data',{});mode=data.get('linkMode')
        if data.get('itemType')!='attachment':raise ValueError('Select an attachment item')
        if mode=='linked_file':
            value=data.get('path','')
            if value.startswith('attachments:'):raise ValueError('Resolve a relative linked attachment through Zotero before selecting it')
            if value.startswith(('\\\\','//')):raise ValueError('UNC/network attachments are forbidden')
            p=Path(value)
        elif mode in {'imported_file','imported_url'}:
            # Controlled no-redirect request; only the Location is parsed locally.
            response=client.session.get(client.base+scope+'/items/'+key+'/file',timeout=(5,20),allow_redirects=False)
            try:
                if response.status_code!=302:raise ValueError('Stored attachment did not resolve to a local file')
                url=urlsplit(response.headers.get('Location',''))
                if url.scheme!='file' or url.netloc not in {'','localhost'}:raise ValueError('Remote attachment URLs are forbidden')
                path=unquote(url.path)
                if os.name=='nt' and re.match(r'^/[A-Za-z]:/',path):path=path[1:]
                p=Path(path)
            finally:response.close()
        else:raise ValueError('Attachment is not locally stored')
        p=p.resolve(strict=True)
        if not p.is_relative_to(root):raise ValueError('Attachment is outside the explicitly permitted folder')
        _,raw=read_file(p,30_000_000)
        return {'success':True,'attachment_key':key,'local_file':str(p),'sha256':digest(raw),'bytes':len(raw),
                'limitations':['Only the selected local file is resolved. No automatic upload or full-library scan occurs.']}
    finally:client.close()


def prepare_zotero_write(library: str, changes: list, sync_acknowledged: bool = False, port: int = 23119) -> dict:
    """Preview additive tags, plain-text notes or new references with private before snapshots; no authorization dialog or write."""
    scope=_scope(library);changes=rows(changes,25)
    if not changes or sync_acknowledged is not True:raise ValueError('Explicitly acknowledge that library writes can synchronize to a configured cloud account')
    client=LocalZotero(port)
    try:
        _,headers=client.call('GET','');identity=headers.get('Zotero-Server-ID')
        if not identity:raise ValueError('Safe write plans require instance-bound local API support')
        plan=[];targets=set()
        for change in changes:
            action=change.get('action')
            if action in {'add_tags','add_note'}:
                key=_key(change.get('item_key'));target=(action,key)
                if target in targets:raise ValueError('Combine changes for the same action/item in one plan')
                targets.add(target);before,_=client.call('GET',scope+'/items/'+key,server_id=identity)
                if type(before.get('version')) is not int:raise ValueError('Item has no version for conflict checking')
                if action=='add_tags':
                    tags=change.get('tags')
                    if not isinstance(tags,list) or not 1<=len(tags)<=30:raise ValueError('Provide 1 to 30 tags')
                    tags=[text(t,100) for t in tags];existing=before['data'].get('tags',[])
                    payload={'version':before['version'],'tags':existing+[{'tag':t} for t in sorted(set(tags)-{v['tag'] for v in existing})]}
                else:
                    import html
                    payload={'itemType':'note','parentItem':key,'note':'<p>'+html.escape(text(change.get('text'),20000)).replace('\n','<br/>')+'</p>'}
                plan.append({'action':action,'item_key':key,'before':before,'before_sha256':digest(json.dumps(before,sort_keys=True).encode()),'payload':payload})
            elif action=='create_reference':
                ref=change.get('reference',{});title=text(ref.get('title'),2000)
                authors=ref.get('authors',[])
                if not isinstance(authors,list) or len(authors)>100:raise ValueError('Provide bounded author names')
                from academic_common import canonical_doi
                payload={'itemType':'journalArticle','title':title,'DOI':canonical_doi(ref.get('doi','')),
                         'date':str(ref.get('year',''))[:50],'creators':[{'creatorType':'author','name':text(a,300)} for a in authors]}
                plan.append({'action':action,'payload':payload,'possible_duplicate_review_required':True})
            else:raise ValueError('Supported writes: add_tags, add_note, create_reference. Deletion and arbitrary field overwrite are forbidden')
        return artifact('zotero_write_plan',{'schema':1,'library':library,'port':port,'server_id':identity,'changes':plan,'sync_acknowledged':True,
            'limitations':['No change has been applied. Preview duplicates and notes before dispatch.','Local writes may synchronize. Before snapshots are private; notes/new references are not automatically deleted during recovery.']})
    finally:client.close()


def apply_zotero_write(plan_file: str, expected_sha256: str, dispatch: bool = False) -> dict:
    """Explicitly dispatch an unchanged preview through Zotero's own authorization dialog; block conflicts and never retry an unknown write."""
    if dispatch is not True:raise ValueError('Dispatch must be explicitly enabled for a reviewed plan')
    p,raw=read_file(plan_file,5_000_000)
    if not re.fullmatch(r'[0-9a-f]{64}',expected_sha256) or digest(raw)!=expected_sha256:raise ValueError('Reviewed write plan hash mismatch')
    # Only a private generated plan, not a user-supplied arbitrary HTTP request.
    if not p.is_relative_to((HERE/'outputs').resolve()) or p.name!='review.json' or not p.parent.name.startswith('zotero_write_plan_'):raise ValueError('Use a generated private Zotero write plan')
    plan=json.loads(raw)
    if plan.get('schema')!=1 or plan.get('sync_acknowledged') is not True:raise ValueError('Invalid write plan')
    state=p.parent/'dispatch_state.json';lock=p.parent/'dispatch.lock'
    if state.exists() or lock.exists():raise ValueError('This plan has already been attempted; inspect its private receipt before preparing a new plan')
    client=LocalZotero(plan['port']);scope=_scope(plan['library']);outcomes=[]
    try:
        # Lock across processes; preserve it after interrupted/unknown dispatch.
        with lock.open('x',encoding='utf8') as f:f.write(expected_sha256)
        atomic_json(state,{'state':'checking','outcomes':[]})
        _,headers=client.call('GET','')
        if headers.get('Zotero-Server-ID')!=plan['server_id']:raise ValueError('Zotero database identity changed; prepare a new plan')
        changes=rows(plan['changes'],25)
        if not changes:raise ValueError('Empty write plan')
        for c in changes:
            if c['action'] not in {'add_tags','add_note','create_reference'}:raise ValueError('Unsupported write action')
            payload=c.get('payload',{})
            if not isinstance(payload,dict):raise ValueError('Invalid fixed write payload')
            if c['action']=='add_tags':
                if set(payload)!={'version','tags'} or type(payload['version']) is not int or not isinstance(payload['tags'],list) or len(payload['tags'])>500:raise ValueError('Invalid tag patch')
                for tag in payload['tags']:
                    if not isinstance(tag,dict) or not set(tag)<={'tag','type'}:raise ValueError('Invalid tag fields')
                    text(tag.get('tag'),100)
            elif c['action']=='add_note':
                import html
                if set(payload)!={'itemType','parentItem','note'} or payload['itemType']!='note' or payload['parentItem']!=c.get('item_key'):raise ValueError('Invalid note creation')
                value=payload['note']
                if not isinstance(value,str) or not value.startswith('<p>') or not value.endswith('</p>'):raise ValueError('Invalid escaped note')
                inner=html.unescape(value[3:-4].replace('<br/>','\n'))
                if '<p>'+html.escape(text(inner,20000)).replace('\n','<br/>')+'</p>'!=value:raise ValueError('Only escaped plain-text notes are allowed')
            else:
                if set(payload)!={'itemType','title','DOI','date','creators'} or payload['itemType']!='journalArticle':raise ValueError('Only fixed bibliographic creation is allowed')
                text(payload['title'],2000)
                from academic_common import canonical_doi
                if not isinstance(payload['DOI'],str) or payload['DOI'] and canonical_doi(payload['DOI'])!=payload['DOI']:raise ValueError('Invalid bibliographic DOI')
                if not isinstance(payload['date'],str) or len(payload['date'])>50:raise ValueError('Invalid bibliographic date')
                if not isinstance(payload['creators'],list) or len(payload['creators'])>100:raise ValueError('Invalid author list')
                for author in payload['creators']:
                    if set(author)!={'creatorType','name'} or author['creatorType']!='author':raise ValueError('Invalid author fields')
                    text(author['name'],300)
            if 'item_key' in c:
                current,_=client.call('GET',scope+'/items/'+_key(c['item_key']),server_id=plan['server_id'])
                if digest(json.dumps(current,sort_keys=True).encode())!=c['before_sha256']:raise ValueError('Item changed since preview; prepare a new plan')
                if c['action']=='add_tags' and payload['version']!=current.get('version'):raise ValueError('Tag patch version does not match reviewed item')
        for c in changes:
            auth,_=client.call('POST','local/authorize',payload={'appName':'Biomni local academic tools'},server_id=plan['server_id'])
            token=auth.get('key')
            if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9]{32}',token):raise ValueError('Local write authorization was not granted')
            # The token stays in memory; it is never an argument, artifact or receipt field.
            atomic_json(state,{'state':'write_outcome_unknown','outcomes':outcomes,'next_action':c['action']})
            if c['action']=='add_tags':
                data,_=client.call('PATCH',scope+'/items/'+_key(c['item_key']),payload=c['payload'],server_id=plan['server_id'],key=token)
                after,_=client.call('GET',scope+'/items/'+c['item_key'],server_id=plan['server_id'])
                if after.get('data',{}).get('tags')!=c['payload']['tags']:raise ValueError('Write response did not verify expected tags; inspect the private receipt')
                outcomes.append({'action':c['action'],'item_key':c['item_key'],'state':'verified','after':after})
            else:
                data,_=client.call('POST',scope+'/items',payload=[c['payload']],server_id=plan['server_id'],key=token)
                successful=(data or {}).get('successful',{})
                if (data or {}).get('failed') or '0' not in successful:raise ValueError('Create response did not confirm a successful item')
                created=_key(successful['0']['key']);after,_=client.call('GET',scope+'/items/'+created,server_id=plan['server_id'])
                for k,v in c['payload'].items():
                    actual=after.get('data',{}).get(k)
                    if k=='note':
                        import html
                        def visible(value):
                            value=re.sub(r'<br\s*/?>','\n',value or '',flags=re.I)
                            return html.unescape(re.sub(r'<[^>]+>','',value))
                        if visible(actual)!=visible(v):raise ValueError('Created note differs from preview')
                    elif actual!=v:raise ValueError('Created item differs from preview; inspect before further dispatch')
                outcomes.append({'action':c['action'],'item_key':created,'state':'verified','after':after})
            token=None
            atomic_json(state,{'state':'partial_completed','outcomes':outcomes})
        atomic_json(state,{'state':'completed','outcomes':outcomes})
        return {'success':True,'state':'completed','outcomes':outcomes,'dispatch_receipt':str(state),
            'limitations':['Before/after snapshots support manual recovery, not an atomic transaction or automatic rollback.','No unknown or interrupted write is automatically retried. The library may synchronize according to Zotero settings.']}
    except Exception as exc:
        # Do not overwrite a write_outcome_unknown receipt with a misleading failed state.
        if state.exists():
            d=json.loads(state.read_text());d['error_type']=type(exc).__name__;atomic_json(state,d)
        raise
    finally:client.close()
