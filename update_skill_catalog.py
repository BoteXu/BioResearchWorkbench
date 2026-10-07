"""Regenerate hashes for the maintained instruction pack without importing tools."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def update():
    exports = None
    tree=ast.parse((ROOT/'bridge'/'extensions.py').read_text(encoding='utf8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EXPORTS' for t in node.targets):
            exports=ast.literal_eval(node.value)
    if exports is None: raise ValueError('Tool exports missing')
    skills=[]
    for folder in sorted((ROOT/'skills').iterdir()):
        if not folder.is_dir(): continue
        text=(folder/'SKILL.md').read_text(encoding='utf8')
        routes=[]
        routing=(folder/'references'/'tool-routing.md').read_text(encoding='utf8')
        for line in routing.splitlines():
            if line.startswith('- `') and line.endswith('`'):
                route=line[3:-1]
                category,name=route.split('.',1)
                if category not in exports or name not in exports[category][1]: raise ValueError('Unknown tool route: '+route)
                routes.append(route)
        files={p.relative_to(ROOT/'skills').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
        skills.append({'name':folder.name,'description':text.split('\ndescription: ',1)[1].split('\n',1)[0].strip('"'),
                       'kind':'workflow_instructions','license':'Apache-2.0','tool_routes':routes,
                       'runtime_validation':'tool_routing_checked; backend validation remains task-specific','files':files})
    (ROOT/'skills'/'catalog.json').write_text(json.dumps({'version':'2.13.0','skills':skills},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('SKILL_CATALOG_UPDATED',len(skills))


if __name__=='__main__': update()
