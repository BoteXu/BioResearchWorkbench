"""Job supervisor and isolated execution process; stdout/stderr remain on disk."""
import json
import os
import subprocess
import sys
from pathlib import Path
import psutil
from evidence import atomic_json, utc
from job_manager import folder, stop_process_tree


def execute(job_id):
    target = folder(job_id)
    request = json.loads((target / "request.json").read_text(encoding="utf8"))
    operation = request["operation"]
    from bridge import query_database, run_tool
    if operation["kind"] == "database":
        result = query_database(operation["name"], operation["parameters"])
    else:
        result = run_tool(operation["category"], operation["name"], operation["parameters"])
    atomic_json(target / "result.json", result)


def supervise(job_id):
    target = folder(job_id)
    request = json.loads((target / "request.json").read_text(encoding="utf8"))
    state = json.loads((target / "state.json").read_text(encoding="utf8"))
    state.update(state="running", stage="executing", started_at=utc())
    atomic_json(target / "state.json", state)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        with (target / "stdout.log").open("ab") as output, (target / "stderr.log").open("ab") as errors:
            child = subprocess.Popen([sys.executable, __file__, job_id, "--execute"], stdin=subprocess.DEVNULL, stdout=output, stderr=errors, cwd=target, env={**os.environ, "PYTHONUTF8": "1"}, **options)
            state.update(worker_pid=child.pid)
            atomic_json(target / "state.json", state)
            try:
                exit_code = child.wait(timeout=request["timeout_seconds"])
            except subprocess.TimeoutExpired:
                stop_process_tree(psutil.Process(child.pid))
                state.update(state="timed_out", stage="timed_out", error="Execution exceeded the requested timeout; partial files/logs retained")
            else:
                result_path = target / "result.json"
                result = json.loads(result_path.read_text(encoding="utf8")) if result_path.exists() else {}
                succeeded = exit_code == 0 and result.get("success") is True
                state.update(state="succeeded" if succeeded else "failed", stage="finished", exit_code=exit_code)
                if not succeeded:
                    state["error"] = "Inspect the result receipt and stderr.log"
    except Exception as exc:
        state.update(state="failed", stage="supervisor_error", error=f"{type(exc).__name__}: {exc}")
    state["finished_at"] = utc()
    if not (target / "CANCEL").exists():
        atomic_json(target / "state.json", state)


if __name__ == "__main__":
    if "--execute" in sys.argv:
        execute(sys.argv[1])
    else:
        supervise(sys.argv[1])
