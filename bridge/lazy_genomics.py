"""Load pinned Biomni genomics with optional imports deferred until used."""
import ast
import importlib
import types
from functools import lru_cache
from pathlib import Path
from importlib.util import find_spec


def requirements(name):
    import biomni
    path = Path(biomni.__file__).parent / "tool" / "genomics.py"
    tree = ast.parse(path.read_text(encoding="utf8"))
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            aliases.update({a.asname or a.name: a.name.split(".")[0] for a in node.names})
        elif isinstance(node, ast.ImportFrom) and node.module:
            aliases.update({a.asname or a.name: node.module.split(".")[0] for a in node.names})
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    packages = {aliases[n.id] for n in ast.walk(function) if isinstance(n, ast.Name) and n.id in aliases}
    for node in ast.walk(function):
        if isinstance(node, ast.Import):
            packages.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            packages.add(node.module.split(".")[0])
    return {package: find_spec(package) is not None for package in sorted(packages)}


class LazyModule:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, attribute):
        return getattr(importlib.import_module(self.name), attribute)


@lru_cache(maxsize=1)
def load():
    import biomni
    path = Path(biomni.__file__).parent / "tool" / "genomics.py"
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    deferred = {"esm", "gget", "gseapy", "scanpy", "torch", "pybiomart"}
    namespace = {"__name__": "biomni.tool.genomics", "__file__": str(path)}
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import) and any(alias.name in deferred for alias in node.names):
            for alias in node.names:
                namespace[alias.asname or alias.name] = LazyModule(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "pybiomart":
            def dataset(*args, **kwargs):
                return importlib.import_module("pybiomart").Dataset(*args, **kwargs)
            namespace["Dataset"] = dataset
        else:
            body.append(node)
    tree.body = body
    exec(compile(tree, str(path), "exec"), namespace)
    module = types.ModuleType("biomni.tool.genomics")
    module.__dict__.update(namespace)
    return module
