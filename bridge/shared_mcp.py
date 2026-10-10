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
import importlib.util
import io
import ipaddress
import json
import math
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
# Configuration writers load this file by filename, without the bridge on sys.path.
# Resolve the reviewed sibling explicitly rather than depending on ambient module search.
_support_spec = importlib.util.spec_from_file_location('brw_shared_support', Path(__file__).with_name('shared_support.py'))
_support = importlib.util.module_from_spec(_support_spec)
_support_spec.loader.exec_module(_support)
admission, MemoryHistory, BoundedCache, inspect_client_config = (
    _support.admission, _support.MemoryHistory, _support.BoundedCache, _support.inspect_client_config)

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
    for file in sorted(p for p in BRIDGE.iterdir() if p.is_file() and (p.suffix in {'.py','.R','.ps1'} or p.name == 'omics_workflows.json')):
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
        json.dump(value, file, indent=2, allow_nan=False)
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
            or type(settings.get('minimum_available_gib', 3)) not in {int, float}
            or not 2 <= settings.get('minimum_available_gib', 3) <= 1024
            or not isinstance(settings.get('token'), str) or len(settings['token']) < 40
            or not isinstance(settings.get('installation_id'), str)):
        raise ValueError('Invalid private shared configuration')
    for key, lower, upper in [('reserve_gib', 0, 1024), ('minimum_after_reserve_gib', 2, 1024),
                              ('maximum_commit_pct', 1, 100), ('maximum_projected_commit_pct', 1, 100)]:
        value = settings.get(key)
        if value is not None and (type(value) not in {int, float} or not math.isfinite(value) or not lower<=value<=upper):
            raise ValueError('Invalid memory admission option')
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


def initialize(port=8768, review_current_source=False, trust_dns_proxy=False, minimum_available_gib=3, memory_options=None):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('An unprivileged TCP port is required')
    if type(minimum_available_gib) not in {int, float} or not 2 <= minimum_available_gib <= 1024:
        raise ValueError('Explicit memory admission floor must be between 2 and 1024 GiB')
    memory_options = memory_options or {}
    if set(memory_options)-{'reserve_gib','minimum_after_reserve_gib','maximum_commit_pct','maximum_projected_commit_pct'}:
        raise ValueError('Unknown memory admission option')
    for key, value in memory_options.items():
        low, high = (0,1024) if key=='reserve_gib' else (2,1024) if key=='minimum_after_reserve_gib' else (1,100)
        if type(value) not in {int,float} or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Invalid explicit memory admission option')
    private_directory()
    guard = ProcessLock(PRIVATE / 'configure.private.lock')
    try:
        path = PRIVATE / 'settings.private.json'
        if path.exists():
            settings = load_settings()
            if (settings['port'] != port or settings.get('trust_dns_proxy', False) != trust_dns_proxy
                    or settings.get('minimum_available_gib', 3) != minimum_available_gib
                    or any(settings.get(k)!=v for k,v in memory_options.items())):
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
                        'source_sha256': source_hash(), 'trust_dns_proxy': bool(trust_dns_proxy),
                        'minimum_available_gib': minimum_available_gib, **memory_options}
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
        decision = admission(settings)
        if not decision['allowed']:
            return {'action': 'refused', 'reason': decision['reasons'][0], **decision}
        options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
        child = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), 'serve'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=BRIDGE, **options)
        current = wait_healthy(settings, wait_seconds)
        if not current:
            return {'action': 'starting_or_unavailable',
                    'reason': 'child_exited' if child.poll() is not None else 'startup_timeout',
                    'child_exit_code': child.poll(), 'new_process_started': True,
                    'automatic_retry': False, 'requires_private_state_review': True}
        return {'action': 'started', 'pid': current['pid']}
    finally:
        launch_lock.close()


class SerialExecutor:
    """The actual worker retains the gate when a client stops waiting."""
    def __init__(self, max_waiting=8, queue_timeout=30, journal=None):
        self.gate = asyncio.Lock()
        self.max_waiting, self.queue_timeout = max_waiting, queue_timeout
        self.counters = {'active': 0, 'waiting': 0, 'completed': 0, 'max_active': 0}
        self.tasks = set()
        self.accepting = True
        self.records = {}
        self.journal = journal
        if journal and journal.exists():
            previous = json.loads(journal.read_text(encoding='utf8'))
            for row in previous.get('calls', [])[-256:]:
                if row['state'] in {'QUEUED', 'RUNNING', 'RESERVED'}:
                    row['state'] = 'UNKNOWN_INTERRUPTED'
                self.records[row['call_id']] = row

    def persist(self):
        if self.journal:
            atomic_json(self.journal, {'schema': 1, 'calls': list(self.records.values()),
                        'arguments_and_results_recorded': False, 'automatic_retry': False})

    def reserve(self):
        if not self.accepting: raise ValueError('Service draining; no operation was started')
        while len(self.records) >= 256:
            oldest = next((k for k, v in self.records.items() if v['state'] not in {'QUEUED', 'RUNNING', 'RESERVED'}), None)
            if oldest is None: raise ValueError('Call ledger full; no operation was started')
            self.records.pop(oldest)
        call_id = secrets.token_hex(16)
        self.records[call_id] = {'call_id': call_id, 'state': 'RESERVED', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                                 'operation_started': False, 'automatic_retry': False}
        self.persist()
        return call_id

    def status(self, call_id):
        if not isinstance(call_id, str) or len(call_id) != 32 or any(c not in '0123456789abcdef' for c in call_id):
            raise ValueError('Use an opaque call ID returned by this service')
        row = self.records.get(call_id)
        if row is None:
            return {'call_id': call_id, 'state': 'UNKNOWN_NOT_RETAINED', 'automatic_retry': False,
                    'scope': 'bounded ledger is not an exhaustive history'}
        value = dict(row)
        if row['state'] == 'QUEUED':
            queued = [v['call_id'] for v in self.records.values() if v['state'] == 'QUEUED']
            value['queue_position'] = queued.index(call_id)+1
        return value

    async def call(self, function, *arguments, call_id=None):
        call_id = self.reserve() if call_id is None else call_id
        row = self.records.get(call_id)
        if not row or row['state'] != 'RESERVED':
            raise ValueError('Call ID is unknown or already dispatched; inspect status and never replay it')
        if not self.accepting:
            row['state'] = 'REFUSED_NOT_STARTED'; self.persist()
            raise ValueError('Service draining; no operation was started')
        if self.counters['waiting'] >= self.max_waiting:
            row['state'] = 'REFUSED_NOT_STARTED'; self.persist()
            raise ValueError('Shared queue full; no operation was started')
        started = time.monotonic(); row['state'] = 'QUEUED'; self.persist()
        self.counters['waiting'] += 1
        try:
            await asyncio.wait_for(self.gate.acquire(), timeout=self.queue_timeout)
        except asyncio.TimeoutError:
            row.update(state='TIMED_OUT_NOT_STARTED', wait_seconds=round(time.monotonic()-started, 3)); self.persist()
            raise ValueError('Shared queue timed out before execution; no operation was started') from None
        except asyncio.CancelledError:
            row.update(state='CANCELLED_NOT_STARTED', wait_seconds=round(time.monotonic()-started, 3)); self.persist()
            raise
        finally:
            self.counters['waiting'] -= 1
        row.update(state='RUNNING', operation_started=True, wait_seconds=round(time.monotonic()-started, 3))
        try: self.persist()
        except Exception:
            self.gate.release(); row['state'] = 'REFUSED_NOT_STARTED'; row['operation_started'] = False; raise
        self.counters['active'] += 1
        self.counters['max_active'] = max(self.counters['max_active'], self.counters['active'])
        async def execute():
            executing = time.monotonic()
            try:
                result = await asyncio.to_thread(function, *arguments)
                row['state'] = 'COMPLETED'; return result
            except Exception as error:
                row.update(state='FAILED_OUTCOME_REQUIRES_REVIEW', error_type=type(error).__name__)
                raise
            finally:
                row['execution_seconds'] = round(time.monotonic()-executing, 3)
                self.counters['active'] -= 1
                self.counters['completed'] += 1
                self.gate.release()
                self.persist()
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
    if not admission(settings)['allowed']:
        raise ValueError('Memory admission refused before tool imports')
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
    executor = SerialExecutor(journal=PRIVATE/'calls.private.json')
    history = MemoryHistory()
    catalog_cache = BoundedCache(ttl=10)
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
            decision = admission(settings)
            if not decision['allowed']:
                raise ValueError('Memory admission refused: '+', '.join(decision['reasons']))
        cache_key = None
        if tool.name == 'biomni_tool_catalog' and not arguments.get('check_imports'):
            # Exact bytes invalidate cached health/configuration; private contents never become keys on disk.
            digest = hashlib.sha256(source_hash().encode())
            for file in sorted(BRIDGE.iterdir()):
                if file.is_file() and (file.suffix == '.json' or file.name.startswith('health.sqlite3')) and file.stat().st_size <= 2*1024**2:
                    digest.update(file.name.encode()); digest.update(file.read_bytes())
            cache_key = digest.hexdigest()+json.dumps(arguments, sort_keys=True)
            cached = catalog_cache.get(cache_key)
            if cached is not None: return cached
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
        if cache_key is not None: catalog_cache.put(cache_key, result)
        return result

    def wrap(tool):
        from pydantic import BaseModel, create_model
        signature = inspect.signature(tool.fn)
        annotations = typing.get_type_hints(tool.fn)
        returned = annotations.get('return')
        if isinstance(returned, type) and issubclass(returned, BaseModel):
            returned = create_model('Shared'+returned.__name__, __base__=returned, shared_call=(dict | None, None))
            signature = signature.replace(return_annotation=returned)
            annotations['return'] = returned
        @functools.wraps(tool.fn)
        async def invoke(**arguments):
            call_id = executor.reserve()
            result = await executor.call(perform, tool, arguments, call_id=call_id)
            if isinstance(result, BaseModel): result = result.model_dump(mode='json')
            if isinstance(result, dict): result = {**result, 'shared_call': executor.status(call_id)}
            return result
        invoke.__signature__ = signature
        invoke.__annotations__ = annotations
        return invoke
    for tool in original.mcp._tool_manager.list_tools():
        if tool.name in ALLOWED_MCP_TOOLS:
            shared.add_tool(wrap(tool), name=tool.name, description=tool.description)

    @shared.tool()
    def biomni_shared_runtime() -> dict:
        """Read the shared process identity and queue counters; no worker is started."""
        return {**state, 'status': 'RUNNING' if executor.accepting else 'DRAINING', **executor.counters,
                'source_matches_review': settings['source_sha256'] == source_hash(),
                'runtime_rss_mib': round(psutil.Process().memory_info().rss/1024**2, 2),
                'memory_admission': admission(settings), 'memory_history': history.sample(executor.counters),
                'catalog_cache': catalog_cache.summary(), 'all_client_adoption_verified': False}

    @shared.tool()
    def biomni_shared_reserve_call() -> dict:
        """Reserve an opaque ID before dispatch. Keep it privately to inspect an interrupted client wait."""
        return executor.status(executor.reserve())

    @shared.tool()
    def biomni_shared_call_status(call_id: str) -> dict:
        """Read retained call state and timings without starting/retrying an operation or returning its private payload."""
        return executor.status(call_id)

    @shared.tool()
    async def biomni_shared_dispatch(call_id: str, tool_name: str, arguments: dict) -> dict:
        """Dispatch one reserved ID exactly once to an exposed original tool. Unknown/replayed IDs are refused."""
        selected = next((t for t in original.mcp._tool_manager.list_tools() if t.name == tool_name and t.name in ALLOWED_MCP_TOOLS), None)
        if selected is None: raise ValueError('Selected tool is not exposed')
        signature = inspect.signature(selected.fn); signature.bind(**arguments)
        result = await executor.call(perform, selected, arguments, call_id=call_id)
        return {'result': result, 'call': executor.status(call_id)}

    @shared.tool()
    def biomni_shared_connection_check(expected_identity: str = '') -> dict:
        """Read this connection's runtime identity; compare with a selected other connection's identity."""
        return {'identity': state['identity'], 'pid': state['pid'],
                'matches_selected_connection': expected_identity == state['identity'] if expected_identity else None,
                'all_client_adoption_verified': False}

    async def health_response(request):
        return JSONResponse({**state, 'status': 'RUNNING' if executor.accepting else 'DRAINING', **executor.counters})
    async def control_response(request):
        if int(request.headers.get('content-length', '0')) > 8192:
            return JSONResponse({'error': 'Control body too large'}, status_code=413)
        raw = await request.body()
        if len(raw)>8192: return JSONResponse({'error': 'Control body too large'}, status_code=413)
        try: command = json.loads(raw)
        except ValueError: return JSONResponse({'error': 'Invalid control JSON'}, status_code=400)
        if not isinstance(command, dict) or command.get('identity') != state['identity']:
            return JSONResponse({'error': 'Exact runtime identity required'}, status_code=409)
        action = command.get('action')
        if action == 'drain': executor.accepting = False
        elif action == 'resume' and not stop['requested']: executor.accepting = True
        elif action == 'stop':
            if executor.accepting or executor.counters['active'] or executor.counters['waiting']:
                return JSONResponse({'error': 'Drain and wait for actual workers first'}, status_code=409)
            stop['requested'] = True
        else: return JSONResponse({'error': 'Unknown control action'}, status_code=400)
        return JSONResponse({'action': action, 'identity': state['identity'], **executor.counters})
    stop = {'requested': False}
    app = shared.streamable_http_app()
    app.routes.append(Route('/health', endpoint=health_response, methods=['GET']))
    app.routes.append(Route('/control', endpoint=control_response, methods=['POST']))
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
    authenticated = Authentication(app)
    authenticated.runtime_control = (stop, history, executor)
    return authenticated, state


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
        stop, history, executor = app.runtime_control
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
            async def monitor():
                last_sample = 0
                while not running.done():
                    if time.monotonic()-last_sample >= 15:
                        atomic_json(PRIVATE/'memory.private.json', history.sample(executor.counters))
                        last_sample = time.monotonic()
                    if stop['requested'] and not executor.counters['active'] and not executor.counters['waiting']:
                        server.should_exit = True
                    await asyncio.sleep(1)
            monitoring = asyncio.create_task(monitor())
            try: await running
            finally:
                monitoring.cancel()
                try: await monitoring
                except asyncio.CancelledError: pass
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


def control(action, expected_identity):
    settings = load_settings(); current = health(settings)
    if not current or not expected_identity or current['identity'] != expected_identity:
        raise ValueError('Exact current runtime identity required; no control was dispatched')
    request = Request('http://'+LOOPBACK+':'+str(settings['port'])+'/control', method='POST',
                      headers={'Authorization': 'Bearer '+settings['token'], 'Content-Type': 'application/json'},
                      data=json.dumps({'action': action, 'identity': expected_identity}).encode())
    with build_opener(ProxyHandler({})).open(request, timeout=3) as response:
        return json.load(response)


def diagnose():
    settings = load_settings(); current = health(settings)
    if current: return {**current, 'memory_admission': admission(settings), 'automatic_restart': False}
    try:
        lock = ProcessLock(PRIVATE/'service.private.lock'); lock.close(); held = False
    except BlockingIOError: held = True
    try:
        with socket.socket() as probe: probe.bind((LOOPBACK, settings['port']))
        occupied = False
    except OSError: occupied = True
    error_file = PRIVATE/'last-error.private.json'
    error_type = json.loads(error_file.read_text()).get('error_type') if error_file.exists() and not error_file.is_symlink() else None
    return {'status': 'UNAVAILABLE', 'service_lock_held': held, 'port_occupied': occupied,
            'reason': 'owned_instance_unhealthy' if held else 'port_occupied_without_owned_lock' if occupied else 'no_owned_instance',
            'last_error_type': error_type, 'source_matches_review': settings['source_sha256'] == source_hash(),
            'memory_admission': admission(settings), 'automatic_restart': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'start', 'serve', 'status', 'doctor', 'drain', 'resume', 'stop'])
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--review-current-source', action='store_true')
    parser.add_argument('--trust-dns-proxy', action='store_true')
    parser.add_argument('--minimum-available-gib', type=float, default=3)
    parser.add_argument('--minimum-after-reserve-gib', type=float)
    parser.add_argument('--reserve-gib', type=float)
    parser.add_argument('--maximum-commit-pct', type=float)
    parser.add_argument('--maximum-projected-commit-pct', type=float)
    parser.add_argument('--expected-identity')
    parser.add_argument('--client-config', help='One explicitly selected private JSON/TOML configuration; read only')
    args = parser.parse_args()
    if args.action == 'serve':
        serve(); return
    if args.action == 'init':
        options = {key:getattr(args,key) for key in ['minimum_after_reserve_gib','reserve_gib','maximum_commit_pct','maximum_projected_commit_pct'] if getattr(args,key) is not None}
        value = initialize(args.port, args.review_current_source, args.trust_dns_proxy, args.minimum_available_gib, options)
    elif args.action == 'start':
        value = start()
    elif args.action in {'drain', 'resume', 'stop'}:
        value = control(args.action, args.expected_identity)
    elif args.action == 'doctor':
        value = diagnose()
        if args.client_config:
            settings = load_settings()
            value['selected_client_configuration'] = inspect_client_config(args.client_config, settings['port'], settings['token'])
    else:
        current = health(load_settings())
        value = {'status': 'RUNNING' if current else 'UNAVAILABLE',
                 'pid': current['pid'] if current else None, 'identity': current['identity'] if current else None}
    print(json.dumps(value))
    if value.get('action') in {'refused', 'starting_or_unavailable', 'existing_instance_unavailable'} or value.get('status') == 'UNAVAILABLE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
