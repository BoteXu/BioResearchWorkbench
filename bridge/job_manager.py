"""Detached, inspectable local jobs with timeout and verified process cancellation."""
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
import psutil
from evidence import atomic_json, utc

HERE = Path(__file__).resolve().parent
JOBS = HERE / "jobs"
TERMINAL = {"succeeded", "failed", "timed_out", "cancelled", "interrupted"}


def folder(job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("Invalid job_id")
    target = JOBS / job_id
    if not target.is_dir():
        raise ValueError("Unknown job_id")
    return target


def submit(operation: dict, timeout_seconds: int = 600):
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 86400:
        raise ValueError("timeout_seconds must be 1..86400")
    if not isinstance(operation, dict) or operation.get("kind") not in {"database", "tool"}:
        raise ValueError("operation.kind must be database or tool")
    allowed = {"kind", "name", "parameters", "category"}
    if set(operation) - allowed or not isinstance(operation.get("parameters"), dict) or not isinstance(operation.get("name"), str):
        raise ValueError("Provide operation name and a parameters object")
    from bridge import DATABASE_TOOLS, EXCLUDED_MODULES, _registry
    from extensions import registry
    if operation["kind"] == "database" and operation["name"] not in DATABASE_TOOLS:
        raise ValueError("Unknown database")
    if operation["kind"] == "tool":
        category = operation.get("category")
        if category in EXCLUDED_MODULES or category == "database" or not category:
            raise ValueError("Unsupported specialist category")
        if (category, operation["name"]) not in registry() and not any(item["name"] == operation["name"] for item in _registry().get("biomni.tool." + category, [])):
            raise ValueError("Unknown specialist tool")
    job_id = uuid.uuid4().hex
    target = JOBS / job_id
    target.mkdir(parents=True)
    atomic_json(target / "request.json", {"operation": operation, "timeout_seconds": timeout_seconds})
    atomic_json(target / "state.json", {"job_id": job_id, "state": "queued", "stage": "process_start", "created_at": utc()})
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    runtime = HERE.parent / ".venv_tools" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    try:
        with (target / "supervisor.log").open("ab") as log:
            process = subprocess.Popen([str(runtime if runtime.exists() else Path(sys.executable)), str(HERE / "job_worker.py"), job_id], stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=HERE.parent, env={**os.environ, "PYTHONUTF8": "1"}, **options)
        atomic_json(target / "process.json", {"pid": process.pid, "create_time": psutil.Process(process.pid).create_time()})
    except Exception as exc:
        atomic_json(target / "state.json", {"job_id": job_id, "state": "failed", "error": f"Process launch failed: {exc}", "finished_at": utc()})
    return status(job_id)


def _verified_process(target):
    info = json.loads((target / "process.json").read_text(encoding="utf8"))
    process = psutil.Process(info["pid"])
    if abs(process.create_time() - info["create_time"]) > 0.01:
        raise psutil.NoSuchProcess(info["pid"])
    command = process.cmdline()
    if str(HERE / "job_worker.py") not in command or target.name not in command:
        raise ValueError("Process identity no longer matches this Biomni job")
    return process


def stop_process_tree(process):
    children = process.children(recursive=True)
    for child in reversed(children):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        process.kill()
    except psutil.NoSuchProcess:
        pass
    psutil.wait_procs(children + [process], timeout=5)


def status(job_id):
    target = folder(job_id)
    state = json.loads((target / "state.json").read_text(encoding="utf8"))
    if (target / "CANCEL").exists():
        state.update(state="cancelled", stage="cancelled", finished_at=(target / "CANCEL").read_text(encoding="utf8"))
    if state["state"] not in TERMINAL and (target / "process.json").exists():
        try:
            _verified_process(target)
        except psutil.NoSuchProcess:
            # The worker may have committed its final state between these reads.
            state = json.loads((target / "state.json").read_text(encoding="utf8"))
            if state["state"] not in TERMINAL:
                state.update(state="interrupted", error="Worker exited without a completion receipt", finished_at=utc())
                atomic_json(target / "state.json", state)
    state["job_directory"] = str(target)
    state["logs"] = {name: str(target / name) for name in ("stdout.log", "stderr.log", "supervisor.log") if (target / name).exists()}
    result_path = target / "result.json"
    if state["state"] in {"succeeded", "failed"} and result_path.exists():
        state["result"] = json.loads(result_path.read_text(encoding="utf8"))
    return state


def cancel(job_id):
    target = folder(job_id)
    state = status(job_id)
    if state["state"] in TERMINAL:
        return state
    try:
        process = _verified_process(target)
    except psutil.NoSuchProcess:
        return status(job_id)
    (target / "CANCEL").write_text(utc(), encoding="utf8")
    stop_process_tree(process)
    return status(job_id)


def list_jobs(limit=20):
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    JOBS.mkdir(exist_ok=True)
    paths = sorted((p for p in JOBS.iterdir() if p.is_dir() and (p / "state.json").exists()), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"jobs": [status(p.name) for p in paths[:limit]], "total": len(paths)}
