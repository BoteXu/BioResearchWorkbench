"""Generate client configuration privately; never overwrite existing client settings."""
import argparse
import json
import os
from pathlib import Path


def generate(install_dir, output_dir, trust_dns_proxy=False):
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
    entry = {'command':str(python), 'args':[str(server)], 'env':environment}
    codex = '[mcp_servers.biomni]\ncommand = ' + json.dumps(str(python)) + '\nargs = ' + json.dumps([str(server)]) + '\n[mcp_servers.biomni.env]\n' + '\n'.join(k + ' = ' + json.dumps(v) for k,v in environment.items()) + '\n'
    data = {'portable.mcp.json':json.dumps({'mcpServers':{'biomni':entry}},indent=2), 'claude-desktop.json':json.dumps({'mcpServers':{'biomni':entry}},indent=2), 'vscode.mcp.json':json.dumps({'servers':{'biomni':{'type':'stdio',**entry}}},indent=2), 'codex.config.toml':codex}
    if any((output/name).exists() for name in data):
        raise ValueError('Generated configuration already exists; choose a new output folder')
    for name, content in data.items():
        (output/name).write_text(content+'\n',encoding='utf8',newline='\n')
    print('CLIENT_CONFIGS_GENERATED_LOCALLY')
    print('Merge the selected file into the client configuration. Client GUI integration still requires validation.')
    print('Generated files contain local paths; keep them private.')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install-dir',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--trust-dns-proxy',action='store_true')
    args = parser.parse_args()
    generate(args.install_dir,args.output_dir,args.trust_dns_proxy)
