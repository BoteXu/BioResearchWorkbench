"""One authenticated, owner-local MCP runtime for multiple clients.

No scientific worker, model stack, OS login entry or remote endpoint is started.
The existing bridge supplies tools; this module only manages their shared transport.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import functools
import hashlib
import inspect
import io
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import typing
from datetime import datetime, timezone
from urllib.request import Request, ProxyHandler, build_opener

BRIDGE = Path(__file__).resolve().parent
PRIVATE = BRIDGE / 'shared_mcp_private'
LOOPBACK = ipaddress.ip_address(socket.INADDR_LOOPBACK).compressed
POLICY = 'shared-server-only-1'
SERVICE = 'BioResearchWorkbench-shared-MCP'
BLOCKED_CATEGORIES = {'omics', 'transcriptomics', 'molecular', 'advanced', 'systems',
                      'software', 'qc', 'table_query', 'semantic_index', 'word_native'}
BLOCKED_FUNCTIONS = {'adjust_pvalues', 'compare_groups', 'plan_sample_size',
    'meta_analyze_effects', 'fit_statistical_model', 'execute_workflow_stage',
    'create_private_backup', 'apply_private_restore', 'index_pdf_folder',
    'index_selected_fulltext', 'apply_zotero_incremental_sync',
    'import_reference_library', 'apply_personal_library_ingest',
    'apply_cytoscape_revision', 'export_cytoscape_snapshot', 'download_publisher_supplement'}
ALLOWED_MCP_TOOLS = {'biomni_status', 'biomni_database_query', 'biomni_tool_catalog',
    'biomni_run_tool', 'biomni_job_status', 'biomni_job_list', 'biomni_evidence_record',
    'biomni_tool_availability', 'biomni_molecular_plan', 'biomni_splicing_audit',
    'biomni_regulatory_audit'}


def source_hash():
    value = hashlib.sha256()
    for file in sorted(BRIDGE.glob('*.py')):
        value.update(file.name.encode()); value.update(file.read_bytes())
    return value.hexdigest()


def private_directory(directory=None):
    directory = PRIVATE if directory is None else Path(directory)
    if any(p.is_symlink() for p in [directory, *directory.parents]):
        raise ValueError('Linked private service directories are refused')
    directory.mkdir(mode=0o700, exist_ok=True)
    if os.name == 'nt':
        result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                                capture_output=True, text=True, check=True)
        sid = next(csv.reader(io.StringIO(result.stdout)))[-1].strip()
        if not sid.startswith('S-1-') or not all(c in 'S-0123456789' for c in sid):
            raise ValueError('Could not verify the owner SID')
        subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r',
                        '*'+sid+':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        directory.chmod(0o700)


def atomic_json(path, value):
    if path.is_symlink():
        raise ValueError('Linked service state is refused')
    temporary = path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf8') as file:
        json.dump(value, file, indent=2)
    os.replace(temporary, path)


def load_settings():
    path = PRIVATE / 'settings.private.json'
    if path.is_symlink() or PRIVATE.is_symlink():
        raise ValueError('Linked service settings are refused')
    if os.name != 'nt' and (PRIVATE.stat().st_mode & 0o077 or path.stat().st_mode & 0o077):
        raise ValueError('Shared settings must be owner-only')
    settings = json.loads(path.read_text(encoding='utf8'))
    if (settings.get('schema') != 1 or settings.get('policy') != POLICY
            or type(settings.get('port')) is not int or not 1024 <= settings['port'] <= 65535
            or not isinstance(settings.get('token'), str) or len(settings['token']) < 40
            or not isinstance(settings.get('installation_id'), str)):
        raise ValueError('Invalid private shared configuration')
    return settings


class ProcessLock:
    """Kernel-backed lifetime lock; an exited process never leaves a held lock."""
    def __init__(self, path):
        if path.is_symlink():
            raise ValueError('Linked service locks are refused')
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        self.file = os.fdopen(descriptor, 'r+b', buffering=0)
        try:
            # Reading the locked byte itself is denied on Windows. Stat it instead.
            if os.fstat(descriptor).st_size == 0:
                self.file.write(b'0')
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise BlockingIOError('A shared instance or launcher already owns this lock') from None

    def close(self):
        if self.file.closed:
            return
        self.file.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file, fcntl.LOCK_UN)
        self.file.close()


def health(settings):
    request = Request('http://'+LOOPBACK+':'+str(settings['port'])+'/health',
                      headers={'Authorization': 'Bearer '+settings['token']})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=1) as response:
            data = json.load(response)
        if data.get('service') == SERVICE and data.get('installation_id') == settings['installation_id']:
            return data
    except Exception:
        pass
    return None


def initialize(port=8768, review_current_source=False, trust_dns_proxy=False):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('An unprivileged TCP port is required')
    private_directory()
    guard = ProcessLock(PRIVATE / 'configure.private.lock')
    try:
        path = PRIVATE / 'settings.private.json'
        if path.exists():
            settings = load_settings()
            if settings['port'] != port or settings.get('trust_dns_proxy', False) != trust_dns_proxy:
                raise ValueError('Existing endpoint/options differ; review them privately before migration')
            if settings['source_sha256'] != source_hash():
                if not review_current_source:
                    raise ValueError('Source changed; explicit --review-current-source is required after review')
                if health(settings):
                    raise ValueError('Review/restart the existing service before changing its accepted source')
                settings['source_sha256'] = source_hash()
                atomic_json(path, settings)
        else:
            settings = {'schema': 1, 'port': port, 'policy': POLICY,
                        'token': secrets.token_urlsafe(48),
                        'installation_id': secrets.token_hex(16),
                        'source_sha256': source_hash(), 'trust_dns_proxy': bool(trust_dns_proxy)}
            atomic_json(path, settings)
        return {'action': 'configured', 'transport': 'streamable-http',
                'private_credentials_written': True, 'local_scientific_execution': False}
    finally:
        guard.close()


def wait_healthy(settings, seconds):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        current = health(settings)
        if current:
            return current
        time.sleep(0.25)
    return None


def start(wait_seconds=30):
    settings = load_settings()
    current = health(settings)
    if current:
        return {'action': 'reused', 'pid': current['pid']}
    if settings['source_sha256'] != source_hash():
        raise ValueError('Shared source changed; review configuration before starting')
    try:
        launch_lock = ProcessLock(PRIVATE / 'launch.private.lock')
    except BlockingIOError:
        current = wait_healthy(settings, wait_seconds)
        return {'action': 'reused' if current else 'starting_or_unavailable',
                'pid': current['pid'] if current else None, 'new_process_started': False}
    try:
        current = health(settings)
        if current:
            return {'action': 'reused', 'pid': current['pid']}
        try:
            service_lock = ProcessLock(PRIVATE / 'service.private.lock')
        except BlockingIOError:
            current = wait_healthy(settings, wait_seconds)
            return {'action': 'reused' if current else 'existing_instance_unavailable',
                    'pid': current['pid'] if current else None, 'new_process_started': False}
        service_lock.close()
        # Never compete with another installation/application occupying this port.
        with socket.socket() as probe:
            probe.bind((LOOPBACK, settings['port']))
        import psutil
        if psutil.virtual_memory().available < 3 * 1024**3:
            return {'action': 'refused', 'reason': 'available_memory_below_3_GiB'}
        options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
        child = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), 'serve'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=BRIDGE, **options)
        current = wait_healthy(settings, wait_seconds)
        if not current:
            raise RuntimeError('Shared service did not become ready; inspect private state. No retry or process termination was made')
        return {'action': 'started', 'pid': current['pid']}
    finally:
        launch_lock.close()


class SerialExecutor:
    """The actual worker retains the gate when a client stops waiting."""
    def __init__(self, max_waiting=8, queue_timeout=30):
        self.gate = asyncio.Lock()
        self.max_waiting, self.queue_timeout = max_waiting, queue_timeout
        self.counters = {'active': 0, 'waiting': 0, 'completed': 0, 'max_active': 0}
        self.tasks = set()

    async def call(self, function, *arguments):
        if self.counters['waiting'] >= self.max_waiting:
            raise ValueError('Shared queue full; no operation was started')
        self.counters['waiting'] += 1
        try:
            await asyncio.wait_for(self.gate.acquire(), timeout=self.queue_timeout)
        except asyncio.TimeoutError:
            raise ValueError('Shared queue timed out before execution; no operation was started') from None
        finally:
            self.counters['waiting'] -= 1
        self.counters['active'] += 1
        self.counters['max_active'] = max(self.counters['max_active'], self.counters['active'])
        async def execute():
            try:
                return await asyncio.to_thread(function, *arguments)
            finally:
                self.counters['active'] -= 1
                self.counters['completed'] += 1
                self.gate.release()
        task = asyncio.create_task(execute())
        self.tasks.add(task)
        def completed(done):
            self.tasks.discard(done)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(completed)
        return await asyncio.shield(task)


def permitted(category, name, exports):
    return (category in exports and category not in BLOCKED_CATEGORIES
            and name in exports[category][1] and name not in BLOCKED_FUNCTIONS)


def build_app(settings):
    if settings['source_sha256'] != source_hash():
        raise ValueError('Shared sources differ from the reviewed configuration')
    os.environ['BIOMNI_COMPUTE_EDITION'] = 'server'
    from extensions import EXPORTS
    os.environ['BIOMNI_MODULES'] = ','.join(sorted((set(EXPORTS)-BLOCKED_CATEGORIES)|{'database'}))
    if settings.get('trust_dns_proxy'):
        os.environ['BIOMNI_TRUST_DNS_PROXY'] = '1'
    import psutil
    import mcp_server as original
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    executor = SerialExecutor()
    state = {'service': SERVICE, 'installation_id': settings['installation_id'],
             'pid': os.getpid(), 'process_create_time': psutil.Process().create_time(),
             'started_at_utc': datetime.now(timezone.utc).isoformat(),
             'identity': secrets.token_hex(16), 'policy': POLICY,
             'max_parallel_tool_calls': 1, 'local_scientific_execution': False}
    atomic_json(PRIVATE/'runtime.private.json', {**state, 'status': 'STARTING'})
    port = settings['port']
    shared = FastMCP('BioResearchWorkbench',
        instructions='Multiple clients share one authenticated local runtime. Calls are serialized. Local scientific workers are unavailable. Use existing privacy, evidence and reviewed-write gates.',
        host=LOOPBACK, port=port, stateless_http=True, json_response=True,
        max_request_body_size=512*1024,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
            allowed_hosts=['localhost:'+str(port), LOOPBACK+':'+str(port)],
            allowed_origins=['http://localhost:'+str(port), 'http://'+LOOPBACK+':'+str(port)]))

    def perform(tool, arguments):
        if tool.name == 'biomni_run_tool' and not permitted(arguments.get('category'), arguments.get('name'), EXPORTS):
            raise ValueError('Shared profile exposes retrieval, server preparation and bounded checks only')
        if tool.name == 'biomni_tool_catalog' and arguments.get('check_imports'):
            raise ValueError('Bulk import probing is disabled in the shared profile')
        metadata = {'biomni_status', 'biomni_tool_catalog', 'biomni_job_status', 'biomni_job_list', 'biomni_tool_availability'}
        if tool.name not in metadata:
            if settings['source_sha256'] != source_hash():
                raise ValueError('Sources changed; review and restart before further operations')
            if psutil.virtual_memory().available < 3*1024**3:
                raise ValueError('Low memory; pause new tool operations')
        result = tool.fn(**arguments)
        if tool.name == 'biomni_tool_catalog':
            for row in result.get('tools', []):
                if row.get('category') != 'database' and not permitted(row.get('category'), row.get('name'), EXPORTS):
                    row['callable_route'] = 'not_exposed_in_shared_server_profile'
            result['shared_profile'] = POLICY
        if tool.name == 'biomni_status':
            result['shared_profile'] = POLICY
            result['local_worker_submission_exposed'] = False
            result['compute_placement'] = 'Scientific computation uses the existing server; this local profile provides retrieval, preparation and bounded checks.'
        return result

    def wrap(tool):
        @functools.wraps(tool.fn)
        async def invoke(**arguments):
            return await executor.call(perform, tool, arguments)
        invoke.__signature__ = inspect.signature(tool.fn)
        invoke.__annotations__ = typing.get_type_hints(tool.fn)
        return invoke
    for tool in original.mcp._tool_manager.list_tools():
        if tool.name in ALLOWED_MCP_TOOLS:
            shared.add_tool(wrap(tool), name=tool.name, description=tool.description)

    @shared.tool()
    def biomni_shared_runtime() -> dict:
        """Read the shared process identity and queue counters; no worker is started."""
        return {**state, 'status': 'RUNNING', **executor.counters,
                'source_matches_review': settings['source_sha256'] == source_hash(),
                'runtime_rss_mib': round(psutil.Process().memory_info().rss/1024**2, 2)}

    async def health_response(request):
        return JSONResponse({**state, 'status': 'RUNNING'})
    app = shared.streamable_http_app()
    app.routes.append(Route('/health', endpoint=health_response, methods=['GET']))
    class Authentication:
        def __init__(self, wrapped):
            self.wrapped = wrapped
        async def __call__(self, scope, receive, send):
            if scope['type'] == 'http':
                headers = {k.lower(): v for k, v in scope.get('headers', [])}
                expected = ('Bearer '+settings['token']).encode('ascii')
                code = None
                if not secrets.compare_digest(headers.get(b'authorization', b''), expected):
                    code = 401
                elif (scope.get('client', (None,))[0] != LOOPBACK
                      or headers.get(b'host') not in {('localhost:'+str(port)).encode(), (LOOPBACK+':'+str(port)).encode()}
                      or b'origin' in headers and headers[b'origin'] not in {('http://localhost:'+str(port)).encode(), ('http://'+LOOPBACK+':'+str(port)).encode()}):
                    code = 403
                if code:
                    await JSONResponse({'error': 'Local authentication or origin refused'}, status_code=code)(scope, receive, send)
                    return
            await self.wrapped(scope, receive, send)
    return Authentication(app), state


def serve():
    settings = load_settings()
    try:
        guard = ProcessLock(PRIVATE/'service.private.lock')
    except BlockingIOError:
        return
    state = None
    class Discard:
        def write(self, value): return len(value)
        def flush(self): pass
        def isatty(self): return False
    prior = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = Discard()
    try:
        app, state = build_app(settings)
        import uvicorn
        server = uvicorn.Server(uvicorn.Config(app, host=LOOPBACK, port=settings['port'],
            workers=1, access_log=False, log_config=None, proxy_headers=False,
            limit_concurrency=16, timeout_keep_alive=5))
        async def run():
            running = asyncio.create_task(server.serve())
            while not server.started and not running.done():
                await asyncio.sleep(0.05)
            if server.started:
                atomic_json(PRIVATE/'runtime.private.json', {**state, 'status': 'RUNNING'})
            await running
        asyncio.run(run())
    except (Exception, SystemExit) as error:
        # No argument values, query payloads, paths or exception text are logged.
        atomic_json(PRIVATE/'last-error.private.json', {'error_type': type(error).__name__,
            'at_utc': datetime.now(timezone.utc).isoformat(), 'automatic_retry': False})
        raise
    finally:
        if state:
            atomic_json(PRIVATE/'runtime.private.json', {**state, 'status': 'STOPPED'})
        sys.stdout, sys.stderr = prior
        guard.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'start', 'serve', 'status'])
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--review-current-source', action='store_true')
    parser.add_argument('--trust-dns-proxy', action='store_true')
    args = parser.parse_args()
    if args.action == 'serve':
        serve(); return
    if args.action == 'init':
        value = initialize(args.port, args.review_current_source, args.trust_dns_proxy)
    elif args.action == 'start':
        value = start()
    else:
        current = health(load_settings())
        value = {'status': 'RUNNING' if current else 'UNAVAILABLE',
                 'pid': current['pid'] if current else None}
    print(json.dumps(value))
    if value.get('action') in {'refused', 'starting_or_unavailable', 'existing_instance_unavailable'} or value.get('status') == 'UNAVAILABLE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
