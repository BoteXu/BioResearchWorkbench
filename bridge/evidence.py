"""Durable receipts, source bytes, and observed tool health for the local bridge."""
import contextvars
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACE = contextvars.ContextVar("biomni_sources", default=None)


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding="utf8")
    temporary.replace(path)


@contextmanager
def connection():
    conn = sqlite3.connect(HERE / "health.sqlite3", timeout=15)
    conn.execute("CREATE TABLE IF NOT EXISTS observations(tool TEXT PRIMARY KEY, success INTEGER, tested_at TEXT, receipt TEXT, error TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS runtime_passes(tool TEXT PRIMARY KEY, tested_at TEXT, receipt TEXT)")
    conn.execute("INSERT OR IGNORE INTO runtime_passes SELECT tool,tested_at,receipt FROM observations WHERE success=1")
    conn.execute("CREATE TABLE IF NOT EXISTS throttle(service TEXT PRIMARY KEY, last_request REAL)")
    # Bootstrap/migration writes start a transaction. Finish it before callers
    # request their own BEGIN IMMEDIATE for the shared NCBI throttle.
    conn.commit()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def observe(tool, success, receipt, error=None):
    with connection() as conn:
        conn.execute("INSERT OR REPLACE INTO observations VALUES(?,?,?,?,?)", (tool, int(success), utc(), str(receipt), str(error)[:2000] if error else None))
        if success:
            conn.execute("INSERT OR REPLACE INTO runtime_passes VALUES(?,?,?)", (tool, utc(), str(receipt)))


def health(tool=None):
    with connection() as conn:
        rows = conn.execute("SELECT * FROM observations" + (" WHERE tool=?" if tool else ""), (tool,) if tool else ()).fetchall()
        passed = {r[0]: {"tested_at": r[1], "receipt": r[2]} for r in conn.execute("SELECT * FROM runtime_passes").fetchall()}
    items = {row[0]: {"runtime_state": "passed" if row[0] in passed else "failed", "tested_at": row[2], "receipt": row[3], "error": row[4], "last_attempt_success": bool(row[1]), "last_success": passed.get(row[0])} for row in rows}
    return items.get(tool, {"runtime_state": "untested"}) if tool else items


def throttle(service, interval):
    # Shared across MCP workers and detached jobs, including the NCBI no-key limit.
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT last_request FROM throttle WHERE service=?", (service,)).fetchone()
        delay = max(0, (row[0] if row else 0) + interval - time.time())
        if delay:
            time.sleep(delay)
        conn.execute("INSERT OR REPLACE INTO throttle VALUES(?,?)", (service, time.time()))


def trace_response(response, body=None):
    raw = response.content if body is None else body
    digest = hashlib.sha256(raw).hexdigest()
    folder = HERE / "sources"
    folder.mkdir(exist_ok=True)
    path = folder / (digest + ".bin")
    if not path.exists():
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_bytes(raw)
        temporary.replace(path)
    entry = {"url": response.url, "status_code": response.status_code, "retrieved_at": utc(), "content_type": response.headers.get("Content-Type"), "bytes": len(raw), "sha256": digest, "source_file": str(path)}
    active = TRACE.get()
    if active is not None:
        active.append(entry)
    return entry


def record_claim(claim, receipts, context, limitations):
    if not claim.strip() or not receipts or not isinstance(context, dict) or not limitations:
        raise ValueError("Provide claim, receipt files, context, and explicit limitations")
    verified = []
    for item in receipts:
        path = Path(item).resolve()
        if path.parent != (HERE / "results").resolve() or not path.name.endswith(".receipt.json"):
            raise ValueError("Use bridge .receipt.json files from the results directory")
        receipt = json.loads(path.read_text(encoding="utf8"))
        result_file = Path(receipt["result_file"]).resolve()
        if result_file.parent != (HERE / "results").resolve():
            raise ValueError("Unexpected result location")
        if hashlib.sha256(result_file.read_bytes()).hexdigest() != receipt["sha256"]:
            raise ValueError("Receipt hash mismatch")
        for snapshot in receipt.get("bridge_source_manifest", []):
            snapshot_path = Path(snapshot["snapshot"]).resolve()
            if snapshot_path.parent != (HERE / "source_snapshots").resolve() or hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != snapshot["sha256"]:
                raise ValueError("Bridge source snapshot hash mismatch")
        for source in receipt.get("sources", []):
            source_path = Path(source["source_file"]).resolve()
            if source_path.parent != (HERE / "sources").resolve() or hashlib.sha256(source_path.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError("Source hash mismatch")
        verified.append({"receipt_file": str(path), "tool": receipt["tool"], "success": receipt["success"], "sha256": receipt["sha256"]})
    identifier = uuid.uuid4().hex
    path = HERE / "evidence" / (identifier + ".json")
    record = {"id": identifier, "claim": claim, "created_at": utc(), "receipts": verified, "context": context, "limitations": limitations, "verification_scope": "File integrity verified; scientific interpretation is supplied by the caller."}
    atomic_json(path, record)
    return {"evidence_file": str(path), **record}
