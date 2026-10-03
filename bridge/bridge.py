"""Call selected Biomni biomedical tools directly, without a second LLM."""

import argparse
import ast
import hashlib
import importlib
import json
import math
import sys
import threading
import time
import uuid
import inspect
import copy
from contextlib import redirect_stdout
from importlib.metadata import version, PackageNotFoundError
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from database_ext import SPECS, adapted_query, validate as validate_database
from evidence import TRACE, atomic_json, health, observe, utc, trace_response
from extensions import registry as extension_registry


HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
_REQUEST_LOCK = threading.Lock()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATABASE_TOOLS = {
    "uniprot": ("query_uniprot", {"endpoint", "max_results"}),
    "geo": ("query_geo", {"search_term", "max_results"}),
    "alphafold": ("query_alphafold", {"uniprot_id", "endpoint"}),
    "ensembl": ("query_ensembl", {"endpoint", "verbose"}),
    "reactome": ("query_reactome", {"endpoint", "verbose"}),
    "clinicaltrials": ("query_clinicaltrials", {"endpoint", "max_results", "verbose"}),
}
DATABASE_TOOLS.update({key: (value[0], value[1]) for key, value in SPECS.items()})
EXCLUDED_MODULES = {"support_tools", "lab_automation"}
OFFICIAL_HOSTS = {
    "uniprot": {"rest.uniprot.org"},
    "ensembl": {"rest.ensembl.org"},
    "reactome": {"reactome.org", "www.reactome.org"},
    "clinicaltrials": {"clinicaltrials.gov", "www.clinicaltrials.gov"},
}


@lru_cache(maxsize=1)
def _registry() -> dict:
    import biomni
    folder = Path(biomni.__file__).parent / 'tool' / 'tool_description'
    entries = {}
    for path in sorted(folder.glob('*.py')):
        if path.name == '__init__.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf8'))
        assignment = next((n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'description' for t in n.targets)), None)
        if assignment is not None:
            entries['biomni.tool.' + path.stem] = ast.literal_eval(assignment.value)
    return entries


def _validate_parameters(parameters: dict) -> None:
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be a JSON object")
    if any(not isinstance(key, str) for key in parameters):
        raise ValueError("parameter names must be strings")


def _validate_endpoint(name: str, endpoint: str) -> None:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint must be a nonempty string")
    parsed = urlsplit(endpoint)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS[name] or parsed.username or parsed.password:
            raise ValueError(f"{name} endpoint must use its official HTTPS host")
    elif endpoint.lstrip().startswith(("//", "\\")):
        raise ValueError("endpoint must be an API path or official HTTPS URL")


def tool_catalog(category: str | None = None, search: str | None = None, limit: int = 30, check_imports: bool = False) -> dict:
    """Browse Biomni's registered tools and distinguish imports from actual execution."""
    matches = []
    extensions = extension_registry()
    observed = health()
    for module_name, schemas in _registry().items():
        short_name = module_name.rsplit(".", 1)[-1]
        if short_name in EXCLUDED_MODULES:
            continue
        if category and short_name != category:
            continue
        try:
            if short_name == "database":
                from lazy_database import load
                module = load()
            elif not check_imports:
                module = None
            elif short_name == "genomics":
                from lazy_genomics import load
                module = load()
            else:
                module = importlib.import_module(module_name)
            import_error = None
        except Exception as exc:
            module = None
            import_error = f"{type(exc).__name__}: {exc}"
        for schema in schemas:
            name = schema["name"]
            if (short_name, name) in extensions:
                continue
            description = schema.get("description", "")
            if search and search.casefold() not in f"{short_name} {name} {description}".casefold():
                continue
            item = {
                    "category": short_name,
                    "name": name,
                    "description": description,
                    "required": [p["name"] for p in schema.get("required_parameters", [])],
                    "required_parameters": schema.get("required_parameters", []),
                    "optional_parameters": schema.get("optional_parameters", []),
                    "import_ready": module is not None and hasattr(module, name) if check_imports or short_name == 'database' else None,
                    "import_check": 'checked' if check_imports or short_name == 'database' else 'deferred',
                    "import_error": import_error,
                    "implementation": "Biomni pinned source" + (" with deferred optional imports" if short_name == "genomics" else ""),
                    "callable_route": "biomni_run_tool",
                    **observed.get(f"{short_name}.{name}", {"runtime_state": "untested"}),
                }
            if short_name == "database":
                direct_name = next((key for key, value in DATABASE_TOOLS.items() if value[0] == name), None)
                item["callable_route"] = "biomni_database_query" if direct_name else "not_exposed"
                item["direct_name"] = direct_name
                if direct_name:
                    allowed = DATABASE_TOOLS[direct_name][1]
                    needed = SPECS[direct_name][2] if direct_name in SPECS else "search_term" if direct_name == "geo" else "uniprot_id" if direct_name == "alphafold" else "endpoint"
                    originals = {p["name"]: p for p in schema.get("required_parameters", []) + schema.get("optional_parameters", [])}
                    item["required"] = [needed] if needed else []
                    item["required_parameters"] = [{**originals.get(needed, {"name": needed, "type": "str"}), "default": None}] if needed else []
                    item["optional_parameters"] = [originals.get(key, {"name": key, "type": "dict" if key in {"params", "variables"} else "str"}) for key in sorted(allowed) if key != needed]
            if short_name == "genomics":
                from lazy_genomics import requirements
                item["dependency_check"] = requirements(name)
            if (short_name, name) in {("genomics", "annotate_celltype_scRNA"), ("literature", "advanced_web_search_claude")}:
                item["callable_route"] = "not_exposed_requires_separate_model"
            matches.append(item)
    for (short_name, name), entry in extensions.items():
        if category and short_name != category:
            continue
        if search and search.casefold() not in f"{short_name} {name} {entry['description']}".casefold():
            continue
        matches.append({"category": short_name, **{k: v for k, v in entry.items() if k != "function"}, "required": [p["name"] for p in entry["required_parameters"]], "import_ready": True, "import_error": None, "callable_route": "biomni_run_tool", **observed.get(f"{short_name}.{name}", {"runtime_state": "untested"})})
    registered = {item["name"] for item in matches if item["category"] == "database"}
    for direct_name, spec in SPECS.items():
        if spec[0] in registered or category and category != "database":
            continue
        if search and search.casefold() not in f"database {direct_name} {spec[0]}".casefold():
            continue
        matches.append({"category": "database", "name": spec[0], "direct_name": direct_name, "description": f"Explicit {direct_name} query adapter; use its official API parameters.", "required": [spec[2]] if spec[2] else [], "required_parameters": [{"name": spec[2], "type": "str"}] if spec[2] else [], "optional_parameters": [{"name": key, "type": "dict" if key in {"params", "variables"} else "str"} for key in sorted(spec[1]) if key != spec[2]], "implementation": "bridge adapter", "import_ready": True, "import_error": None, "callable_route": "biomni_database_query", **observed.get(f"database.{spec[0]}", {"runtime_state": "untested"})})
    return {
        "total_matches": len(matches),
        "import_ready_matches": sum(item["import_ready"] is True for item in matches),
        "runtime_passed_matches": sum(item["runtime_state"] == "passed" for item in matches),
        "tools": matches[: max(1, min(limit, 100))],
    }


def _clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def _input_files(parameters):
    files = []
    for key, value in parameters.items():
        if isinstance(value, str) and (key == "path" or key.endswith(("_path", "_file", "_filename"))):
            path = Path(value)
            if not path.is_file():
                continue
            stat = path.stat()
            item = {"parameter": key, "path": str(path.resolve()), "bytes": stat.st_size, "modified_ns": stat.st_mtime_ns, "hash_state": "not_computed_large_input"}
            if stat.st_size <= 256_000_000:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                item.update(sha256=digest.hexdigest(), hash_state="computed")
            files.append(item)
    return files


def _source_manifest():
    manifest = []
    folder = HERE / "source_snapshots"
    folder.mkdir(exist_ok=True)
    for name in ("bridge.py", "database_ext.py", "literature_ext.py", "omics_ext.py", "atlas_ext.py", "workflow_ext.py", "research_ext.py", "biomedical_ext.py", "remote_runner.py", "server_probe.py", "extensions.py", "evidence.py", "http_client.py", "lazy_genomics.py", "lazy_database.py", "job_manager.py", "job_worker.py", "mcp_server.py", "web_gateway.py", "compute_policy.py", "transcriptomics_ext.py", "limma_pipeline.R", "count_models.R", "qc_ext.py", "molecular_ext.py", "systems_ext.py", "software_ext.py"):
        raw = (HERE / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        path = folder / (digest + ".py")
        if not path.exists():
            path.write_bytes(raw)
        manifest.append({"name": name, "sha256": digest, "snapshot": str(path)})
    return manifest


def _save_result(category: str, name: str, parameters: dict, result: object, implementation="Biomni pinned source", elapsed_seconds=None) -> dict:
    raw = json.dumps(_clean(result), ensure_ascii=False, indent=2, default=str, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = RESULTS / f"{stamp}_{category}_{name}_{uuid.uuid4().hex[:8]}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)
    preview = raw[:40000].decode("utf-8", errors="ignore")
    success = result.get("success", "error" not in result and not result.get("errors")) if isinstance(result, dict) else not (isinstance(result, str) and result.lower().startswith(("error", "an error occurred", "failed")))
    packages = {}
    for package in ("biomni", "numpy", "pandas", "scanpy", "gseapy"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            pass
    receipt = {
        "tool": f"biomni.tool.{category}.{name}",
        "parameters": parameters,
        "result_file": str(path),
        "sha256": digest,
        "success": bool(success),
        "truncated": len(raw) > 40000,
        "result_preview": preview,
        "created_at": utc(),
        "elapsed_seconds": elapsed_seconds,
        "implementation": implementation,
        "sources": TRACE.get() or [],
        "input_files": _input_files(parameters),
        "environment": {"python": sys.version.split()[0], "executable": sys.executable, "packages": packages, "biomni_commit": "400c1f366b96a35ca253e13c9b06c5076af41d65", "bridge_version": "2.6"},
        "bridge_source_manifest": _source_manifest(),
    }
    receipt_path = path.with_suffix(".receipt.json")
    receipt["receipt_file"] = str(receipt_path)
    atomic_json(receipt_path, receipt)
    error = result.get("error") or result.get("errors") if isinstance(result, dict) else None
    observe(f"{category}.{name}", success, receipt_path, error)
    return receipt


def _execute(category, name, parameters, function, implementation="Biomni pinned source"):
    token = TRACE.set([])
    started = time.monotonic()
    submitted_parameters = copy.deepcopy(parameters)
    try:
        try:
            result = function()
        except Exception as exc:
            result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
        return _save_result(category, name, submitted_parameters, result, implementation, round(time.monotonic() - started, 3))
    finally:
        TRACE.reset(token)


def run_tool(category: str, name: str, parameters: dict) -> dict:
    """Call a registered Biomni tool, excluding code execution and lab automation."""
    _validate_parameters(parameters)
    extension = extension_registry().get((category, name))
    if extension:
        inspect.signature(extension["function"]).bind(**parameters)
        def call_extension():
            missing = [package for package, available in extension.get('dependency_check', {}).items() if not available]
            if missing:
                raise RuntimeError('Optional dependencies missing: ' + ', '.join(missing) + '. Use the omics profile for these local helpers; keep large analyses on the server.')
            return extension['function'](**parameters)
        return _execute(category, name, parameters, call_extension, extension["implementation"])
    if category == "literature" and name == "advanced_web_search_claude" or category == "genomics" and name == "annotate_celltype_scRNA":
        raise ValueError("This upstream function invokes a separate model; use the direct bridge extensions")
    if category in EXCLUDED_MODULES or category == "database":
        raise ValueError("Use the selected direct database query tool for database calls.")
    module_name = f"biomni.tool.{category}"
    schemas = _registry().get(module_name)
    if not schemas:
        raise ValueError(f"Unknown Biomni category: {category}")
    schema = next((item for item in schemas if item["name"] == name), None)
    if schema is None:
        raise ValueError(f"Unknown registered Biomni tool: {category}.{name}")
    permitted = {p["name"] for p in schema.get("required_parameters", []) + schema.get("optional_parameters", [])}
    extras = set(parameters) - permitted
    if extras:
        raise ValueError(f"Unsupported parameters: {sorted(extras)}")
    missing = {p["name"] for p in schema.get("required_parameters", [])} - set(parameters)
    if missing:
        raise ValueError(f"Missing required parameters: {sorted(missing)}")
    def call():
        if category == "genomics":
            from lazy_genomics import load
            module = load()
        else:
            module = importlib.import_module(module_name)
        return getattr(module, name)(**parameters)
    return _execute(category, name, parameters, call)


def readiness() -> dict:
    try:
        from lazy_database import load
        load()
        database_ready = True
        database_error = None
    except Exception as exc:
        database_ready = False
        database_error = f"{type(exc).__name__}: {exc}"

    return {
        "checkout": str(HERE.parent),
        "mode": "direct Biomni tools",
        "model_or_api_key_required": False,
        "database_module_ready": database_ready,
        "database_import_error": database_error,
        "available_tools": sorted(DATABASE_TOOLS),
        "bridge_version": "2.6",
        "compute_edition": __import__("compute_policy").edition(),
        "compute_placement": "Large calculations and data downloads run on the server. Local scope: retrieval, task preparation, command handoff, status/receipt and result auditing.",
        "runtime_health": health(),
        "extensions": sorted({category for category, name in extension_registry()}),
        "jobs_directory": str(HERE / "jobs"),
        "dependency_scope": "Direct adapters and local omics extensions do not invoke a separate model; upstream specialist functions may require optional software, data, or services.",
        "catalog": "Use biomni_tool_catalog for registered specialist functions; runtime dependencies vary.",
    }


def query_database(name: str, parameters: dict) -> dict:
    _validate_parameters(parameters)
    if name not in DATABASE_TOOLS:
        raise ValueError(f"Unsupported Biomni database tool: {name}")
    function_name, permitted = DATABASE_TOOLS[name]
    if name in SPECS:
        validate_database(name, parameters)
        return _execute("database", function_name, parameters, lambda: _database_call(name, parameters), "bridge adapter + pinned Biomni database functions")
    extras = set(parameters) - permitted
    if extras:
        raise ValueError(f"Unsupported parameters for {name}: {sorted(extras)}")
    if not parameters:
        raise ValueError("Provide direct query parameters; natural-language LLM queries are unavailable.")
    needed = "search_term" if name == "geo" else "uniprot_id" if name == "alphafold" else "endpoint"
    if needed not in parameters or not parameters[needed]:
        raise ValueError(f"{name} requires {needed}")
    if name in OFFICIAL_HOSTS:
        _validate_endpoint(name, parameters["endpoint"])
    if name == "alphafold" and parameters.get("endpoint", "prediction") not in {"prediction", "summary", "annotations"}:
        raise ValueError("Unsupported AlphaFold endpoint")

    return _execute("database", function_name, parameters, lambda: _database_call(name, parameters))


def _database_call(name, parameters):
    if name in SPECS:
        adapted = adapted_query(name, parameters)
        if adapted is not None:
            return adapted
    from lazy_database import load
    database = load()

    function = getattr(database, DATABASE_TOOLS[name][0])

    class TimedRequests:
        def __init__(self, original_requests):
            self.original = original_requests

        def __getattr__(self, attribute):
            return getattr(self.original, attribute)

        def get(self, *args, **kwargs):
            kwargs.setdefault("timeout", 20)
            response = self.original.get(*args, **kwargs)
            trace_response(response)
            return response

        def post(self, *args, **kwargs):
            kwargs.setdefault("timeout", 20)
            response = self.original.post(*args, **kwargs)
            trace_response(response)
            return response

    with _REQUEST_LOCK:
        original_requests = database.requests
        database.requests = TimedRequests(original_requests)
        try:
            result = function(**parameters)
        finally:
            database.requests = original_requests
    if isinstance(result, dict) and isinstance(result.get("result"), dict) and result["result"].get("errors"):
        result["success"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--query", choices=sorted(DATABASE_TOOLS))
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("--check-imports", action="store_true", help="Check optional upstream imports while listing the catalog")
    parser.add_argument("--category")
    parser.add_argument("--search")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--run", help="Registered specialist tool as category.name")
    parser.add_argument("--params", default="{}", help="JSON object of direct query parameters")
    parser.add_argument("--params-file", help="UTF-8 JSON file of tool parameters")
    parser.add_argument("--job-submit", help="JSON operation object for a detached job")
    parser.add_argument("--job-status")
    parser.add_argument("--job-cancel")
    parser.add_argument("--job-list", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--evidence-record", help="JSON file with claim, receipts, context, limitations")
    args = parser.parse_args()
    parameters = json.loads(Path(args.params_file).read_text(encoding="utf8")) if args.params_file else json.loads(args.params)
    if args.status:
        output = readiness()
    elif args.query:
        with redirect_stdout(sys.stderr):
            output = query_database(args.query, parameters)
    elif args.catalog:
        output = tool_catalog(args.category, args.search, args.limit, args.check_imports)
    elif args.run:
        if "." not in args.run:
            parser.error("--run must be category.name")
        category, name = args.run.split(".", 1)
        with redirect_stdout(sys.stderr):
            output = run_tool(category, name, parameters)
    elif args.job_submit:
        from job_manager import submit
        output = submit(json.loads(args.job_submit), args.timeout)
    elif args.job_status:
        from job_manager import status
        output = status(args.job_status)
    elif args.job_cancel:
        from job_manager import cancel
        output = cancel(args.job_cancel)
    elif args.job_list:
        from job_manager import list_jobs
        output = list_jobs(args.limit)
    elif args.evidence_record:
        from evidence import record_claim
        output = record_claim(**json.loads(Path(args.evidence_record).read_text(encoding="utf8")))
    else:
        parser.error("Specify --status, --query, --catalog, or --run")
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
