"""Generate client configuration privately; never overwrite existing client settings."""
import argparse
import json
import os
import re
from pathlib import Path


def generate(install_dir, output_dir, trust_dns_proxy=False, server_name="bioresearch", transport="stdio"):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}",server_name): raise ValueError("Invalid MCP server name")
    root = Path(install_dir).resolve(strict=True)
    python = root / '.venv_tools' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    server = root / '.local' / 'mcp_server.py'
    if not python.is_file() or not server.is_file():
        raise ValueError('Expected installed runtime and MCP server were not found')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    environment = {'PYTHONUTF8':'1'}
    if trust_dns_proxy:
        environment['BIOMNI_TRUST_DNS_PROXY'] = '1'
    if transport == 'shared':
        import importlib.util
        spec = importlib.util.spec_from_file_location('brw_shared_permissions', Path(__file__).resolve().parent/'bridge/shared_mcp.py')
        shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
        shared.private_directory(output)
        settings = json.loads((root/'.local/shared_mcp_private/settings.private.json').read_text(encoding='utf8'))
        if (settings.get('schema') != 1 or type(settings.get('port')) is not int
                or not 1024 <= settings['port'] <= 65535 or len(settings.get('token','')) < 40
                or settings.get('trust_dns_proxy', False) != bool(trust_dns_proxy)):
            raise ValueError('Initialize and review private shared settings first')
        url = 'http://localhost:'+str(settings['port'])+'/mcp'
        headers = {'Authorization':'Bearer '+settings['token']}
        entry = {'url':url, 'headers':headers}
        codex = '[mcp_servers.'+server_name+']\nenabled = true\nurl = '+json.dumps(url)+'\nhttp_headers = { Authorization = '+json.dumps(headers['Authorization'])+' }\nstartup_timeout_sec = 15\ntool_timeout_sec = 120\n'
        data = {'portable.mcp.json':json.dumps({'mcpServers':{server_name:entry}},indent=2),
                'vscode.mcp.json':json.dumps({'servers':{server_name:{'type':'http',**entry}}},indent=2),
                'codex.config.toml':codex}
    elif transport == 'stdio':
        entry = {'command':str(python), 'args':[str(server)], 'env':environment}
        codex = '[mcp_servers.'+server_name+']\ncommand = ' + json.dumps(str(python)) + '\nargs = ' + json.dumps([str(server)]) + '\n[mcp_servers.'+server_name+'.env]\n' + '\n'.join(k + ' = ' + json.dumps(v) for k,v in environment.items()) + '\n'
        data = {'portable.mcp.json':json.dumps({'mcpServers':{server_name:entry}},indent=2), 'claude-desktop.json':json.dumps({'mcpServers':{server_name:entry}},indent=2), 'vscode.mcp.json':json.dumps({'servers':{server_name:{'type':'stdio',**entry}}},indent=2), 'codex.config.toml':codex}
    else:
        raise ValueError('Select stdio or shared transport')
    if any((output/name).exists() for name in data):
        raise ValueError('Generated configuration already exists; choose a new output folder')
    for name, content in data.items():
        path = output/name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf8', newline='\n') as file:
            file.write(content+'\n')
    print('CLIENT_CONFIGS_GENERATED_LOCALLY')
    print('Merge the selected file into the client configuration. Client GUI integration still requires validation.')
    print('Generated files contain local paths or authentication headers; keep them private.')
    return data


def register_shared_codex(output_dir, server_name):
    """Register only a new name; preserve and back up all existing private settings."""
    import hashlib
    import secrets
    import tomllib
    output = Path(output_dir)
    config = Path.home()/'.codex/config.toml'
    snippet = (output/'codex.config.toml').read_text(encoding='utf8')
    entry = tomllib.loads(snippet)
    if set(entry.get('mcp_servers', {})) != {server_name} or 'command' in entry['mcp_servers'][server_name]:
        raise ValueError('A single reviewed shared registration is required')
    old = config.read_bytes() if config.exists() else b''
    before = tomllib.loads(old.decode('utf-8-sig'))
    if server_name in before.get('mcp_servers', {}):
        raise ValueError('Existing registration must be migrated manually after review')
    updated = old.decode('utf-8-sig')+('\n' if old and not old.endswith(b'\n') else '')+'\n'+snippet
    expected = tomllib.loads(updated)
    retained = json.loads(json.dumps(expected))
    del retained['mcp_servers'][server_name]
    if 'mcp_servers' not in before and not retained['mcp_servers']:
        retained.pop('mcp_servers')
    if retained != before:
        raise ValueError('Unrelated client settings changed')
    backup = output/('codex-before-'+secrets.token_hex(8)+'.private.toml')
    with os.fdopen(os.open(backup, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'wb') as file:
        file.write(old)
    if backup.read_bytes() != old or (config.read_bytes() if config.exists() else b'') != old:
        raise ValueError('Client configuration changed during registration')
    config.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.with_name(config.name+'.'+secrets.token_hex(8)+'.tmp')
    with os.fdopen(os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'w', encoding='utf8', newline='') as file:
        file.write(updated)
    os.replace(temporary, config)
    if tomllib.loads(config.read_text(encoding='utf-8-sig')) != expected:
        raise ValueError('Client registration readback failed; inspect the private backup')
    print('SHARED_CODEX_REGISTRATION_WRITTEN; EXISTING_CHATS_MAY_CACHE_OLD_SETTINGS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install-dir',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--trust-dns-proxy',action='store_true')
    parser.add_argument('--server-name',default='bioresearch')
    parser.add_argument('--transport',choices=['stdio','shared'],default='stdio')
    parser.add_argument('--register-shared-codex', action='store_true')
    args = parser.parse_args()
    generate(args.install_dir,args.output_dir,args.trust_dns_proxy,args.server_name,args.transport)
    if args.register_shared_codex:
        if args.transport != 'shared': parser.error('Shared transport required for this registration')
        register_shared_codex(args.output_dir,args.server_name)
