#!/usr/bin/env python3
"""Plan content-based incremental work; record explicitly reviewed results.

Python 3.10+, standard library only. Never executes engines or a scheduler.
All data paths are relative to --root and must remain within it.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = 1
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class Invalid(ValueError):
    pass


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    def bad_constant(value):
        raise Invalid(f"Non-finite JSON number: {value}")
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=no_duplicates,
                         parse_constant=bad_constant)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def need(condition, message):
    if not condition:
        raise Invalid(message)


def text_value(value):
    return isinstance(value, str) and bool(value.strip())


def has_placeholder(value):
    if isinstance(value, str):
        return "__FILL" in value
    if isinstance(value, dict):
        return any(has_placeholder(x) for x in value.values())
    if isinstance(value, list):
        return any(has_placeholder(x) for x in value)
    return False


def missing_identity(value):
    if value is None: return True
    if isinstance(value, str): return not value.strip() or value.strip().lower() in {"unknown", "tbd", "na", "null"}
    if isinstance(value, dict): return not value or any(missing_identity(x) for x in value.values())
    if isinstance(value, list): return not value or any(missing_identity(x) for x in value)
    return False


def safe_path(root, relative):
    need(text_value(relative), "File path must be a nonempty string")
    path = Path(relative)
    need(not path.is_absolute() and ".." not in path.parts,
         f"Use a project-relative path without '..': {relative}")
    resolved = (root / path).resolve()
    need(resolved.is_relative_to(root), f"Path escapes project root: {relative}")
    return resolved


def file_info(root, relative):
    path = safe_path(root, relative)
    need(path.is_file(), f"Missing regular file: {relative}")
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    after = path.stat()
    need((before.st_size, before.st_mtime_ns, before.st_ino) ==
         (after.st_size, after.st_mtime_ns, after.st_ino),
         f"File changed while hashing; use a frozen snapshot: {relative}")
    return {"path": relative, "sha256": h.hexdigest(), "bytes": after.st_size}


def load_workflow(path, root):
    cfg = read_json(path)
    need(isinstance(cfg, dict), "Workflow must be a JSON object")
    need(set(cfg) == {"schema_version", "project_id", "tasks"},
         "Workflow keys must be schema_version, project_id, tasks")
    need(type(cfg["schema_version"]) is int and cfg["schema_version"] == SCHEMA,
         "Unsupported schema version")
    need(text_value(cfg["project_id"]), "Missing project_id")
    need(isinstance(cfg["tasks"], list) and cfg["tasks"], "tasks must be nonempty")
    tasks, owned, external = {}, {}, set()
    required = {"id", "kind", "entity_id", "inputs", "outputs", "parameters",
                "software", "code", "depends_on"}
    for task in cfg["tasks"]:
        need(isinstance(task, dict) and set(task) == required,
             f"Task requires exactly these fields: {sorted(required)}")
        tid = task["id"]
        need(text_value(tid) and ID.fullmatch(tid), f"Invalid task ID: {tid}")
        need(tid not in tasks, f"Duplicate task ID: {tid}")
        for key in ("kind", "entity_id"):
            need(text_value(task[key]), f"{tid}: missing {key}")
        for key in ("inputs", "outputs", "parameters", "software", "code"):
            need(isinstance(task[key], dict), f"{tid}: {key} must be an object")
        need(task["outputs"] and task["software"] and task["code"],
             f"{tid}: outputs, software and code must be explicit and nonempty")
        need(isinstance(task["depends_on"], list) and
             all(text_value(x) for x in task["depends_on"]),
             f"{tid}: depends_on must be a list of task IDs")
        need(len(task["depends_on"]) == len(set(task["depends_on"])),
             f"{tid}: duplicate dependency")
        for label, spec in task["inputs"].items():
            need(text_value(label) and isinstance(spec, dict), f"{tid}: invalid input")
            need(set(spec) in ({"path"}, {"task", "output"}),
                 f"{tid}/{label}: use path or task/output")
            if "path" in spec:
                external.add(str(safe_path(root, spec["path"])))
            else:
                need(text_value(spec["task"]) and text_value(spec["output"]),
                     f"{tid}/{label}: invalid upstream reference")
        for label, relative in task["code"].items():
            need(text_value(label), f"{tid}: invalid code label")
            external.add(str(safe_path(root, relative)))
        for label, relative in task["outputs"].items():
            need(text_value(label), f"{tid}: invalid output label")
            resolved = str(safe_path(root, relative))
            need(resolved not in owned, f"Shared output path: {relative}")
            owned[resolved] = tid
        tasks[tid] = task
    need(not external.intersection(owned),
         "A produced file cannot be an external input or code file; use task/output")
    deps = {}
    for tid, task in tasks.items():
        found = set(task["depends_on"])
        for spec in task["inputs"].values():
            if "task" in spec:
                other = spec["task"]
                need(other in tasks, f"{tid}: unknown input task {other}")
                need(spec["output"] in tasks[other]["outputs"],
                     f"{tid}: unknown output {other}/{spec['output']}")
                found.add(other)
        need(all(x in tasks for x in found), f"{tid}: unknown dependency")
        deps[tid] = sorted(found)
    order, active, done = [], set(), set()
    def visit(tid):
        need(tid not in active, f"Dependency cycle involving {tid}")
        if tid in done:
            return
        active.add(tid)
        for other in deps[tid]:
            visit(other)
        active.remove(tid)
        done.add(tid)
        order.append(tid)
    for tid in tasks:
        visit(tid)
    return cfg, tasks, deps, order


def load_state(path, project_id):
    if path is None:
        return {"schema_version": SCHEMA, "project_id": project_id, "records": {}}
    state = read_json(path)
    need(isinstance(state, dict) and state.get("schema_version") == SCHEMA,
         "Invalid state schema")
    need(state.get("project_id") == project_id, "State belongs to another project")
    need(isinstance(state.get("records"), dict), "Invalid state records")
    need(all(isinstance(v, dict) for v in state["records"].values()),
         "Each state record must be an object")
    return state


def accepted_outputs(root, task, record):
    reasons = []
    if record.get("status") != "accepted":
        return ["previous record is not accepted"]
    old_outputs = record.get("outputs", {})
    if set(old_outputs) != set(task["outputs"]):
        return ["declared output set changed"]
    for label, relative in task["outputs"].items():
        try:
            current = file_info(root, relative)
            if current != old_outputs[label]:
                reasons.append(f"output changed: {label}")
        except (Invalid, OSError) as exc:
            reasons.append(str(exc))
    evidence = record.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        reasons.append("accepted record lacks review evidence")
    else:
        for item in evidence:
            try:
                if file_info(root, item["path"]) != item:
                    reasons.append(f"review evidence changed: {item['path']}")
            except (Invalid, OSError, KeyError, TypeError) as exc:
                reasons.append(f"review evidence unavailable: {exc}")
    return reasons


def assess(cfg, tasks, deps, order, state, root, targets):
    selected = set()
    def include(tid):
        need(tid in tasks, f"Unknown requested task: {tid}")
        if tid in selected:
            return
        selected.add(tid)
        for other in deps[tid]:
            include(other)
    for target in targets or order:
        include(target)
    result = {}
    for tid in order:
        if tid not in selected:
            continue
        task = tasks[tid]
        failed, inputs, code = [], {}, {}
        if has_placeholder(task) or has_placeholder(cfg["project_id"]):
            failed.append("unfilled __FILL placeholder in project/task configuration")
        if missing_identity(task["software"]):
            failed.append("software identity contains an unfilled value")
        for label, spec in task["inputs"].items():
            if "path" in spec:
                try:
                    inputs[label] = file_info(root, spec["path"])
                except (Invalid, OSError) as exc:
                    failed.append(str(exc))
        for label, relative in task["code"].items():
            try:
                code[label] = file_info(root, relative)
            except (Invalid, OSError) as exc:
                failed.append(str(exc))
        entry = {"id": tid, "kind": task["kind"], "entity_id": task["entity_id"],
                 "depends_on": deps[tid], "status": "blocked", "reasons": failed,
                 "fingerprint": None, "component_hashes": None,
                 "existing_output_paths": [v for v in task["outputs"].values() if safe_path(root, v).exists()],
                 "execution_authorized": False}
        result[tid] = entry
        if failed:
            continue
        unavailable = [x for x in deps[tid] if result[x]["status"] == "blocked"]
        if unavailable:
            entry["reasons"] = ["blocked dependency: " + ", ".join(unavailable)]
            continue
        pending = [x for x in deps[tid] if result[x]["status"] != "reuse"]
        if pending:
            entry["status"] = "waiting"
            entry["reasons"] = ["await accepted upstream result: " + ", ".join(pending)]
            continue
        for label, spec in task["inputs"].items():
            if "task" in spec:
                record = state["records"][spec["task"]]
                inputs[label] = {"task": spec["task"], "output": spec["output"],
                                 "file": record["outputs"][spec["output"]]}
        dependency_keys = {x: state["records"][x]["fingerprint"] for x in deps[tid]}
        payload = {"schema_version": SCHEMA, "project_id": cfg["project_id"],
                   "task_id": tid, "kind": task["kind"], "entity_id": task["entity_id"],
                   "parameters": task["parameters"], "software": task["software"],
                   "code": code, "inputs": inputs, "dependencies": dependency_keys,
                   "output_paths": task["outputs"]}
        signature = digest(payload)
        entry["fingerprint"] = signature
        parts = {key: digest(value) for key, value in payload.items()}
        entry["component_hashes"] = parts
        previous = state["records"].get(tid)
        if not previous:
            entry.update(status="run", reasons=["no accepted result recorded"])
        elif previous.get("fingerprint") != signature:
            old_parts = previous.get("component_hashes", {})
            changed = [key for key, value in parts.items() if old_parts.get(key) != value]
            entry.update(status="run", reasons=["fingerprint component changed: " + key for key in changed])
        else:
            problems = accepted_outputs(root, task, previous)
            entry.update(status="run" if problems else "reuse",
                         reasons=problems or ["fingerprint, outputs and review evidence match"])
    counts = {s: sum(x["status"] == s for x in result.values())
              for s in ("reuse", "run", "waiting", "blocked")}
    return {"schema_version": SCHEMA, "project_id": cfg["project_id"],
            "mode": "plan_only", "execution_authorized": False,
            "dispatch_policy": "No dispatch. Existing artifacts require reviewed recovery or a new output path; run is a planning status, not overwrite permission.", "counts": counts, "tasks": list(result.values()),
            "unselected_tasks": [x for x in order if x not in selected]}


def timestamp(value):
    need(text_value(value), "Timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Invalid(f"Invalid ISO timestamp: {value}") from exc
    need(parsed.tzinfo is not None, "Timestamp must include a timezone")
    return parsed


def record_review(task, entry, review_path, root):
    need(entry["status"] in {"run", "reuse"},
         f"Cannot record {task['id']}: {entry['status']}")
    review = read_json(safe_path(root, review_path))
    need(review.get("task_id") == task["id"] and review.get("status") == "accepted",
         "Review must explicitly accept the exact task")
    need(text_value(review.get("reviewer")), "Review requires a named reviewer")
    execution = review.get("execution", {})
    need(isinstance(execution, dict) and type(execution.get("exit_code")) is int
         and execution["exit_code"] == 0, "Execution exit_code must be integer 0")
    need(execution.get("fingerprint") == entry["fingerprint"],
         "Review fingerprint does not match the current executable plan")
    need(text_value(execution.get("run_id")), "Execution run_id is required")
    started = timestamp(execution.get("started_at"))
    ended = timestamp(execution.get("ended_at"))
    reviewed = timestamp(review.get("reviewed_at"))
    need(started <= ended <= reviewed, "Execution/review timestamps are inconsistent")
    checks = review.get("checks")
    need(isinstance(checks, list) and checks, "Review must list passed checks and evidence")
    paths = {review_path, execution.get("log_path")}
    for check in checks:
        need(isinstance(check, dict) and text_value(check.get("name"))
             and check.get("status") == "passed", "All declared checks must pass")
        files = check.get("evidence")
        need(isinstance(files, list) and files and all(text_value(x) for x in files),
             "Each check needs one or more evidence paths")
        paths.update(files)
    need(all(text_value(x) for x in paths), "Execution log path is required")
    outputs = {key: file_info(root, path) for key, path in task["outputs"].items()}
    need(all(info["bytes"] > 0 for info in outputs.values()),
         "Declared result files must be nonempty; use an explicit no-result record")
    need(review.get("reviewed_outputs") == outputs,
         "Reviewed output snapshot does not match current outputs; perform a new review")
    reviewed_paths = sorted(paths - {review_path})
    evidence_snapshot = [file_info(root, p) for p in reviewed_paths]
    need(review.get("reviewed_evidence") == evidence_snapshot,
         "Reviewed evidence/log snapshot does not match current files; perform a new review")
    return {"status": "accepted", "fingerprint": entry["fingerprint"],
            "component_hashes": entry["component_hashes"],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "outputs": outputs, "evidence": [file_info(root, p) for p in sorted(paths)],
            "reviewer": review["reviewer"], "run_id": execution["run_id"]}


def bind_review(task, entry, review_path, root):
    """Bind a draft to exact bytes; never mark the review as accepted."""
    need(entry["status"] in {"run", "reuse"},
         f"Cannot prepare review for {task['id']}: {entry['status']}")
    review = read_json(safe_path(root, review_path))
    need(isinstance(review, dict), "Review draft must be an object")
    execution = review.get("execution")
    checks = review.get("checks")
    need(isinstance(execution, dict) and isinstance(checks, list) and checks,
         "Draft requires execution and named checks")
    paths = {execution.get("log_path")}
    for check in checks:
        need(isinstance(check, dict) and text_value(check.get("name")),
             "Each draft check requires a name")
        evidence = check.get("evidence")
        need(isinstance(evidence, list) and evidence and all(text_value(x) for x in evidence),
             "Draft checks require evidence file paths")
        paths.update(evidence)
        check["status"] = "pending"
    need(all(text_value(x) for x in paths), "Draft requires an execution log path")
    need(review_path not in paths, "Review cannot cite itself as scientific evidence")
    outputs = {key: file_info(root, path) for key, path in task["outputs"].items()}
    need(all(x["bytes"] > 0 for x in outputs.values()), "Outputs must be nonempty")
    review.update(task_id=task["id"], status="pending", reviewer=None, reviewed_at=None,
                  reviewed_outputs=outputs,
                  reviewed_evidence=[file_info(root, p) for p in sorted(paths)])
    execution["fingerprint"] = entry["fingerprint"]
    return review


def emit(value, destination):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if destination:
        path = Path(destination)
        need(path.parent.is_dir(), "Output parent directory does not exist")
        # Exclusive creation prevents overwriting a previous state or plan.
        with path.open("x", encoding="utf-8") as handle:
            handle.write(data)
    else:
        print(data, end="")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "record", "bind-review"):
        cmd = sub.add_parser(name)
        cmd.add_argument("workflow", type=Path)
        cmd.add_argument("--root", type=Path)
        cmd.add_argument("--state", type=Path)
        cmd.add_argument("--output", type=Path, required=name != "plan")
        if name == "plan":
            cmd.add_argument("--targets", nargs="+")
        else:
            cmd.add_argument("--task", required=True)
            cmd.add_argument("--review", required=True,
                             help="Review JSON path relative to project root")
    args = parser.parse_args()
    root = (args.root or args.workflow.parent).resolve()
    need(root.is_dir(), "Project root must already exist")
    cfg, tasks, deps, order = load_workflow(args.workflow, root)
    state = load_state(args.state, cfg["project_id"])
    targets = args.targets if args.command == "plan" else [args.task]
    plan = assess(cfg, tasks, deps, order, state, root, targets)
    if args.command == "plan":
        emit(plan, args.output)
        return 2 if plan["counts"]["blocked"] else 0
    entry = next(x for x in plan["tasks"] if x["id"] == args.task)
    if args.command == "bind-review":
        emit(bind_review(tasks[args.task], entry, args.review, root), args.output)
        return 0
    state["records"][args.task] = record_review(tasks[args.task], entry, args.review, root)
    emit(state, args.output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Invalid, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
