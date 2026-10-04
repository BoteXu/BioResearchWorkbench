"""Private browser access for devices without a native Python/MCP client."""
import argparse
import hmac
import hashlib
import ipaddress
import json
import os
import secrets
import ssl
import sys
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

LOCK = threading.RLock()
MAX_BODY = 1000000
RESULTS = Path(__file__).resolve().parent / 'results'
HTML = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BioResearchWorkbench 工具连接</title><style>body{font:16px system-ui;margin:auto;padding:24px;max-width:900px;background:#f4f7fa;color:#203040}h1{overflow-wrap:anywhere}section{background:white;border-radius:12px;padding:20px;margin:16px 0}input,select,textarea,button{font:inherit;padding:10px;margin:6px 0;box-sizing:border-box;width:100%;border:1px solid #bccbd4;border-radius:6px}button{background:#146b72;color:white;cursor:pointer}textarea{min-height:100px}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#536774}</style><h1>BioResearchWorkbench 工具连接</h1><p>连接你自己的工具宿主，查询资料、检查结果。大计算继续在服务器完成。</p><section><label>连接口令<input id="token" type="password" autocomplete="off"></label><button id="connect">连接并加载工具</button><button id="status">查看工具状态</button><small>口令只保存在当前页面内存中，不写入地址或浏览器存储。</small></section><section><label>工具类别<select id="category"><option>code_review</option><option>code_execution</option><option>clinical_research</option><option>workbench</option><option>academic_workspace</option><option>scientific_backend</option><option>word_native</option><option>biomedical</option><option>qc</option><option>systems</option><option>software</option><option>statistics</option><option>advanced</option><option>server</option><option>reporting</option><option>library</option><option>zotero</option><option>review</option><option>collaboration</option><option>personal_library</option><option>transcriptomics</option><option>molecular</option><option>research</option><option>atlas</option><option>literature</option><option>workflow</option><option>omics</option><option>database</option></select></label><label>选择工具<select id="tool"></select></label><div id="description"></div><div id="fields"></div><button id="run">运行检查或查询</button><small>公开数据库参数仅填写公开检索信息；敏感资料需获得具体授权。文件路径指向工具宿主上的文件。</small></section><section><h2>结果</h2><pre id="result">等待连接</pre><button id="download">保存当前结果</button></section><script src="/client.js"></script></html>'''
JS = '''let entries=[],last=null; const el=id=>document.getElementById(id);
async function call(data){const response=await fetch('/api',{method:'POST',headers:{'Authorization':'Bearer '+el('token').value,'Content-Type':'application/json'},body:JSON.stringify(data)});const value=await response.json();if(!response.ok)throw new Error(value.error||'连接失败');return value;}
function show(value){last=value;el('result').textContent=JSON.stringify(value,null,2);}
async function perform(fn){try{el('result').textContent='正在处理…';show(await fn());}catch(e){el('result').textContent=e.message;}}
function fields(){const entry=entries[Number(el('tool').value)];el('fields').replaceChildren();el('description').textContent=entry?.description||'';if(!entry)return;for(const spec of [...(entry.required_parameters||[]),...(entry.optional_parameters||[])]){const label=document.createElement('label');label.textContent=spec.name+(entry.required_parameters?.includes(spec)?'（必填）':'（可选）');const input=document.createElement(['dict','list'].includes(spec.type.split('[')[0])?'textarea':'input');input.dataset.name=spec.name;input.dataset.kind=spec.type.split('[')[0];input.placeholder=['dict','list'].includes(spec.type.split('[')[0])?'填写 JSON 对象或数组':'填写参数';if(spec.default!==undefined&&spec.default!==null)input.value=typeof spec.default==='object'?JSON.stringify(spec.default):String(spec.default);label.append(input);el('fields').append(label);}}
async function catalog(){const result=await call({operation:'catalog',category:el('category').value});entries=result.tools;el('tool').replaceChildren();entries.forEach((entry,index)=>{const option=document.createElement('option');option.value=index;option.textContent=entry.name;el('tool').append(option);});fields();return {message:'工具已加载',count:entries.length};}
el('connect').onclick=()=>perform(catalog);el('category').onchange=()=>perform(catalog);el('tool').onchange=fields;el('status').onclick=()=>perform(()=>call({operation:'status'}));
el('run').onclick=()=>perform(()=>{const entry=entries[Number(el('tool').value)];if(!entry)throw new Error('请先连接并选择工具');const parameters={};for(const input of el('fields').querySelectorAll('[data-name]')){if(!input.value.trim())continue;const kind=input.dataset.kind;parameters[input.dataset.name]=['dict','list','int','float','bool'].includes(kind)?JSON.parse(input.value):input.value;}return call(entry.direct_name?{operation:'query',name:entry.direct_name,parameters}:{operation:'tool',category:entry.category,name:entry.name,parameters});});
el('download').onclick=()=>{if(!last)return;const blob=new Blob([JSON.stringify(last,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='biomni-result.json';link.click();URL.revokeObjectURL(url);};'''


def create_token(path):
    file = Path(path)
    file.parent.mkdir(parents=True,exist_ok=True)
    descriptor = os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream:
        stream.write(secrets.token_urlsafe(48)+'\n')
    print('PRIVATE_TOKEN_FILE_CREATED')


def load_token(path):
    file = Path(path).resolve(strict=True)
    if os.name!='nt' and file.stat().st_mode & 0o077:
        raise ValueError('Restrict token file permissions to its owner')
    token = file.read_text(encoding='utf8').strip()
    if len(token)<32 or len(token)>256 or any(c.isspace() for c in token):
        raise ValueError('Use a long private token without spaces')
    return token


def require_tls(host,cert,key):
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host=='localhost'
    if bool(cert)!=bool(key) or not loopback and not (cert and key):
        raise ValueError('Non-loopback browser access requires a TLS certificate and key')


def returned_result(receipt):
    """Return bounded tool data to the browser together with its original receipt."""
    result = {'receipt':receipt,'result_state':'unavailable'}
    if receipt.get('result_file'):
        file = Path(receipt['result_file'])
        if file.is_symlink() or file.resolve().parent != RESULTS.resolve():
            raise ValueError('Browser results must belong to the bridge results directory')
        file = file.resolve(strict=True)
        if file.stat().st_size>2000000:
            result['result_state'] = 'review_large_result_on_host'
        else:
            raw = file.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=receipt['sha256']:
                raise ValueError('Result receipt integrity mismatch')
            result.update(result=json.loads(raw),result_state='included')
    return result


def execute(operation):
    import bridge
    from extensions import registry
    kind = operation.get('operation')
    if kind=='status':
        return bridge.readiness()
    if kind=='catalog':
        category = operation.get('category','biomedical')
        if category=='database':
            entries = []
            for direct,(name,allowed) in bridge.DATABASE_TOOLS.items():
                matched = bridge.tool_catalog(category='database',search=name,limit=100)['tools']
                entry = next((r for r in matched if r['name']==name),None)
                if entry:
                    entries.append({**entry,'direct_name':direct})
            return {'tools':entries}
        if category not in {c for c,_ in registry()}:
            raise ValueError('Unknown extension category')
        entries = bridge.tool_catalog(category=category,limit=100)['tools']
        return {'tools':[e for e in entries if (category,e['name']) in registry()]}
    if kind=='query':
        return returned_result(bridge.query_database(operation['name'],operation.get('parameters',{})))
    if kind=='tool':
        if (operation.get('category'),operation.get('name')) not in registry():
            raise ValueError('Only explicit bridge extensions are exposed to the browser')
        return returned_result(bridge.run_tool(operation['category'],operation['name'],operation.get('parameters',{})))
    raise ValueError('Unsupported operation')


def handler(token,dispatch=execute):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def reply(self,status,payload,content_type='application/json'):
            raw = payload.encode('utf8') if isinstance(payload,str) else json.dumps(payload,ensure_ascii=False).encode('utf8')
            self.send_response(status)
            self.send_header('Content-Type',content_type+'; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path=='/':
                self.reply(200,HTML,'text/html')
            elif self.path=='/client.js':
                self.reply(200,JS,'application/javascript')
            else:
                self.reply(404,{'error':'Not found'})

        def do_POST(self):
            if self.path!='/api':
                self.reply(404,{'error':'Not found'})
                return
            auth = self.headers.get('Authorization','')
            if not auth.startswith('Bearer ') or not hmac.compare_digest(auth[7:].encode('utf8'),token.encode('utf8')):
                self.reply(401,{'error':'连接口令无效'})
                return
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                self.reply(403,{'error':'跨来源访问被拒绝'})
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_BODY or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    self.reply(413,{'error':'请提交大小受限的 JSON 参数'})
                    return
                request = json.loads(self.rfile.read(length))
                if not isinstance(request,dict):
                    raise ValueError('Expected an object')
                with LOCK,redirect_stdout(sys.stderr):
                    result = dispatch(request)
                self.reply(200,result)
            except Exception as exc:
                self.reply(400,{'error':'请求未完成，请核对参数和宿主回执','error_type':type(exc).__name__})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--create-token-file')
    parser.add_argument('--token-file')
    parser.add_argument('--host',default='localhost')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--tls-cert')
    parser.add_argument('--tls-key')
    args = parser.parse_args()
    if args.create_token_file:
        create_token(args.create_token_file)
        return
    if not args.token_file or not 1<=args.port<=65535:
        parser.error('Provide --token-file and a valid port')
    require_tls(args.host,args.tls_cert,args.tls_key)
    from privacy_ext import policy
    try:
        loopback=ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        loopback=args.host=='localhost'
    if not loopback and not policy().get('allow_remote_gateway',False):
        parser.error('Remote gateway exposure is disabled by private policy; use the local tool connection')
    import socket
    class Server(ThreadingHTTPServer):
        address_family = socket.AF_INET6 if ':' in args.host else socket.AF_INET
    server = Server((args.host,args.port),handler(load_token(args.token_file)))
    if args.tls_cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.tls_cert,args.tls_key)
        server.socket = context.wrap_socket(server.socket,server_side=True)
    print('PRIVATE_BROWSER_GATEWAY_READY',flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__=='__main__':
    main()
