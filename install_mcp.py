"""Install optional upstream MCP processes separately; do not overwrite existing client or library settings."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def install(root,components,python_version='3.13',npm_cli='',node=''):
    manifest=json.loads((ROOT/'mcp_components.json').read_text())
    specs={c['id']:c for c in manifest['components']}
    if not components or len(set(components))!=len(components) or not set(components)<={'serena','duckdb','qdrant','context7','playwright'}:raise ValueError('Choose installable external components explicitly')
    uv=shutil.which('uv')
    if not uv:raise ValueError('Install uv from its official distribution first')
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);states=[]
    for name in components:
        spec=specs[name];target=root/name
        if name in ['serena','duckdb','qdrant']:
            if target.exists():raise ValueError('Existing component environment refused; reuse it or choose a fresh runtime folder')
            subprocess.run([uv,'venv','--python',python_version,str(target)],check=True)
            py=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            subprocess.run([uv,'pip','install','--python',str(py),'-r',str(ROOT/('requirements-mcp-'+name+'.txt'))],check=True)
            freeze=subprocess.run([uv,'pip','freeze','--python',str(py)],capture_output=True,text=True,check=True)
            (root/(name+'.installed.lock.txt')).write_text(freeze.stdout,encoding='utf8')
        else:
            if target.exists():raise ValueError('Existing component directory refused')
            npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
            if npm_cli:
                if not Path(npm_cli).is_file() or not Path(node).is_file():raise ValueError('Provide existing Node and npm CLI')
                command=[node,npm_cli]
            elif npm:command=[npm]
            else:raise ValueError('Install the official Node distribution including npm, or supply an existing npm CLI')
            target.mkdir();user=target/'npm-user.conf';global_file=target/'npm-global.conf';user.write_text('');global_file.write_text('')
            # Separate empty npm files prevent inherited registry credentials/settings.
            subprocess.run(command+['--userconfig',str(user),'--globalconfig',str(global_file),'--prefix',str(target),'--registry','https://registry.npmjs.org','install','--ignore-scripts','--save-exact','--no-audit','--no-fund',spec['package']+'@'+spec['version']],check=True)
        states.append({'component':name,'version':spec['version'],'state':'installed_unprobed'})
        (root/'installation-receipt.json').write_text(json.dumps({'schema':1,'private':True,'states':states},indent=2),encoding='utf8')
    return states


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime-root',required=True);p.add_argument('--components',nargs='+',required=True);p.add_argument('--python-version',default='3.13');p.add_argument('--npm-cli',default='');p.add_argument('--node',default='');a=p.parse_args()
    install(a.runtime_root,a.components,a.python_version,a.npm_cli,a.node);print('OPTIONAL_COMPONENTS_INSTALLED; CONNECTION_AND_SCOPE_ACCEPTANCE_REQUIRED')
