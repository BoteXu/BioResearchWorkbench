"""Load fixed upstream database definitions without importing a model stack."""
import ast
import importlib
import types
from pathlib import Path
from functools import lru_cache


class LazyModule:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, name):
        return getattr(importlib.import_module(self.name), name)


class LazyAttribute:
    def __init__(self, module, attribute):
        self.module, self.attribute = module, attribute

    def __call__(self, *args, **kwargs):
        return getattr(importlib.import_module(self.module), self.attribute)(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(getattr(importlib.import_module(self.module), self.attribute), name)


def blocked_model(*args, **kwargs):
    raise ValueError('Separate model inference is disabled; use explicit API parameters')


@lru_cache(maxsize=1)
def load():
    import biomni
    path = Path(biomni.__file__).parent / 'tool' / 'database.py'
    tree = ast.parse(path.read_text(encoding='utf8'), filename=str(path))
    namespace = {'__name__': 'biomni.tool.database', '__file__': str(path), 'get_llm': blocked_model}
    body = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'biomni.llm':
            continue
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split('.')[0] in {'Bio', 'langchain_core', 'biomni'}:
            for alias in node.names:
                namespace[alias.asname or alias.name] = LazyAttribute(node.module, alias.name)
        elif isinstance(node, ast.Import) and any(a.name.split('.')[0] in {'Bio', 'langchain_core'} for a in node.names):
            for alias in node.names:
                namespace[alias.asname or alias.name.split('.')[0]] = LazyModule(alias.name)
        else:
            body.append(node)
    tree.body = body
    exec(compile(tree, str(path), 'exec'), namespace)
    module = types.ModuleType('biomni.tool.database')
    module.__dict__.update(namespace)
    return module
