"""Generate public extension contracts and documentation from source AST; never read installation state."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = '2.13.2'


def assignment(tree, name):
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


def generate(root=ROOT):
    root = Path(root)
    exports = assignment(ast.parse((root/'bridge/extensions.py').read_text(encoding='utf8')), 'EXPORTS')
    intents = assignment(ast.parse((root/'bridge/research_ext.py').read_text(encoding='utf8')), 'INTENTS')
    types = {'str': 'string', 'int': 'integer', 'float': 'number', 'bool': 'boolean', 'dict': 'object', 'list': 'array'}
    entries = []; modules = {}
    for category, (module, names) in sorted(exports.items()):
        tree = ast.parse((root/'bridge'/(module+'.py')).read_text(encoding='utf8'))
        functions = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
        enums = {}
        if category == 'molecular_biology': enums['task'] = list(assignment(tree, 'ROUTES'))
        if category == 'research_quality': enums['analysis'] = list(assignment(tree, 'ANALYSES'))
        for name in names:
            node = functions[name]; properties = {}; required = []
            defaults = [None]*(len(node.args.args)-len(node.args.defaults)) + list(node.args.defaults)
            for p, d in zip(node.args.args, defaults):
                annotation = ast.unparse(p.annotation) if p.annotation else 'Any'
                spec = {'type': types.get(annotation, 'string'), 'description': p.arg.replace('_', ' ')}
                if spec['type'] == 'array': spec['items'] = {}
                if p.arg in enums: spec['enum'] = enums[p.arg]
                if d is None: required.append(p.arg)
                else:
                    default = ast.literal_eval(d); spec['default'] = default
                    if default is None: spec['type'] = [spec['type'], 'null']
                if p.arg == 'approved_public_data': spec['description'] = 'Explicit approval of these exact public identifiers; default false; never infer approval from installation.'
                properties[p.arg] = spec
            effect_units = ['delta_psi_fraction', 'delta_usage_fraction', 'log2_fold_change'] if name == 'audit_splicing_results' else []
            entries.append({'category': category, 'name': name, 'description': ast.get_docstring(node) or '',
                            'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': required},
                            'example_template': {'category': category, 'name': name, 'parameters': {p: '<'+p+'>' for p in required}},
                            'effect_units': effect_units, 'source_file': 'bridge/'+module+'.py',
                            'source_sha256': hashlib.sha256((root/'bridge'/(module+'.py')).read_bytes()).hexdigest()})
        optional = {'requests','pypdf','numpy','pandas','scipy','statsmodels','sklearn','scanpy','anndata','gseapy','networkx','rdkit','meeko','gemmi','igraph','leidenalg','pydeseq2','duckdb','psutil'}
        dependencies = set()
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom) and n.module: dependencies.add(n.module.split('.')[0])
            if isinstance(n,ast.Import): dependencies.update(x.name.split('.')[0] for x in n.names)
        modules[category] = {'source': module+'.py', 'function_count': len(names), 'load': 'deferred_until_call',
                             'referenced_optional_packages':sorted(dependencies&optional),
                             'version_constraints':'requirements-core.lock.txt and selected requirements-local/omics/full profile; external R/CLI versions need actual probes',
                             'compatibility': 'Python 3.11; task-specific optional dependencies require runtime checks',
                             'permission_review': 'public identifier authorization' if category in {'atlas', 'literature'} else
                             'explicit native write dispatch' if category in {'zotero', 'word_native'} else 'inspect the selected function contract'}
    summary = {'package_version': VERSION, 'extension_functions': len(entries), 'extension_categories': len(exports), 'routing_intents': len(intents)}
    baseline = json.loads((root/'catalog_baseline.json').read_text(encoding='utf8')) if (root/'catalog_baseline.json').exists() else {'tools':{}}
    current = {e['category']+'.'+e['name']: {'parameters':list(e['input_schema']['properties']), 'required':e['input_schema']['required']} for e in entries}
    changes = {'from_version':baseline.get('package_version'), 'to_version':VERSION,
               'added':sorted(set(current)-set(baseline['tools'])), 'removed':sorted(set(baseline['tools'])-set(current)),
               'parameter_changes':sorted(k for k in set(current)&set(baseline['tools']) if current[k]!=baseline['tools'][k])}
    document = {'schema': 1, **summary, 'tools': entries, 'modules': modules,
                'version_changes':changes,
                'limitations': ['Static signatures and templates are not backend or scientific acceptance.',
                                'Nested scientific contracts require their linked domain guide.',
                                'Pinned Biomni upstream tools and client plugins are discovered separately at runtime.']}
    markdown = '# 自动生成功能目录\n\n此目录由公开源码生成，不读取运行回执或私人配置。\n\n'
    markdown += '| 扩展函数 | 类别 | 任务路由 | 包版本 |\n|---|---|---|---|\n'
    markdown += f'| {len(entries)} | {len(exports)} | {len(intents)} | {VERSION} |\n\n'
    markdown += '参数 schema、默认值、枚举和调用模板见 [TOOL_CATALOG.json](TOOL_CATALOG.json)。模板中的占位符需要实际填写，模板不是可执行验收。\n\n'
    for category in sorted(exports):
        markdown += '## '+category+'\n\n| 函数 | 功能 | 必需参数 |\n|---|---|---|\n'
        for e in entries:
            if e['category'] == category:
                markdown += '| `'+e['name']+'` | '+e['description'].replace('|', '\\|').replace('\n', ' ')+' | '+', '.join(e['input_schema']['required'])+' |\n'
        markdown += '\n'
    return document, markdown


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    data, md = generate(); outputs={'TOOL_CATALOG.json': json.dumps(data, ensure_ascii=False, indent=2)+'\n', 'TOOL_CATALOG.md':md}
    begin='<!-- GENERATED:CATALOG:BEGIN -->';end='<!-- GENERATED:CATALOG:END -->'
    readme=(ROOT/'README.md').read_text(encoding='utf8')
    if readme.count(begin)!=1 or readme.count(end)!=1 or readme.index(begin)>readme.index(end):
        raise SystemExit('README requires one ordered generated catalog block')
    skills=len(json.loads((ROOT/'skills/catalog.json').read_text(encoding='utf8'))['skills'])
    summary=f"**公开目录（自动生成）**：{data['extension_functions']} 个扩展函数、{data['extension_categories']} 个类别、{data['routing_intents']} 个任务路由、{skills} 个原始工作流 skill。上游 Biomni 工具和客户端插件另行发现；这些数量不代表全部后端都已验收。\n"
    outputs['README.md']=readme[:readme.index(begin)+len(begin)]+'\n'+summary+readme[readme.index(end):]
    if args.check:
        if any(not (ROOT/name).exists() or (ROOT/name).read_text(encoding='utf8')!=value for name,value in outputs.items()):
            raise SystemExit('Generated tool catalog is stale; regenerate before release')
        print('CATALOG_CURRENT');return
    for name,value in outputs.items(): (ROOT/name).write_text(value,encoding='utf8',newline='\n')
    print(json.dumps({k:data[k] for k in ['extension_functions','extension_categories','routing_intents']}))


if __name__ == '__main__': main()
