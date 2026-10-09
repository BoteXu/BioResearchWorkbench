"""Bounded shared-runtime admission, diagnostics and public read-only caching."""
from collections import OrderedDict, deque
import copy
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time

GIB = 1024**3


def utc():
    return datetime.now(timezone.utc).isoformat()


def memory_snapshot():
    import psutil
    memory = psutil.virtual_memory()
    result = {'at_utc': utc(), 'available_gib': memory.available/GIB,
              'total_gib': getattr(memory, 'total', 0)/GIB,
              'commit_pct': None, 'commit_limit_gib': None, 'nonpaged_gib': None}
    if os.name == 'nt':
        class Performance(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong)] + [(name, ctypes.c_size_t) for name in
                ['CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable',
                 'SystemCache', 'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize']] + [
                (name, ctypes.c_ulong) for name in ['HandleCount', 'ProcessCount', 'ThreadCount']]
        value = Performance(); value.cb = ctypes.sizeof(value)
        function = ctypes.WinDLL('psapi', use_last_error=True).GetPerformanceInfo
        function.argtypes = [ctypes.POINTER(Performance), ctypes.c_ulong]
        function.restype = ctypes.c_int
        if not function(ctypes.byref(value), value.cb):
            result['platform_metrics_error'] = 'performance_info_unavailable'
        else:
            result['commit_limit_gib'] = value.CommitLimit*value.PageSize/GIB
            result['commit_pct'] = 100*value.CommitTotal/value.CommitLimit if value.CommitLimit else None
            result['nonpaged_gib'] = value.KernelNonpaged*value.PageSize/GIB
    return result


def admission(settings, snapshot=None):
    """Fresh point-in-time check, not a reservation or a scientific-compute authorization."""
    try:
        snapshot = memory_snapshot() if snapshot is None else snapshot
        available = snapshot['available_gib']
        if not isinstance(available, (float, int)) or not math.isfinite(available):
            raise ValueError('Invalid memory measurement')
        reserve = settings.get('reserve_gib', 0.25)
        floor = settings.get('minimum_available_gib', 3)
        reasons = []
        if available < floor: reasons.append('available_memory_below_configured_floor')
        if available-reserve < settings.get('minimum_after_reserve_gib', max(2, floor-reserve)):
            reasons.append('projected_available_memory_below_floor')
        commit, limit = snapshot.get('commit_pct'), snapshot.get('commit_limit_gib')
        if commit is not None:
            if commit >= settings.get('maximum_commit_pct', 80): reasons.append('commit_pressure')
            if limit and commit+100*reserve/limit >= settings.get('maximum_projected_commit_pct', 85):
                reasons.append('projected_commit_pressure')
        pool, total = snapshot.get('nonpaged_gib'), snapshot.get('total_gib')
        if pool is not None and total and pool >= 4 and pool/total >= 0.15:
            reasons.append('nonpaged_pool_pressure')
        if os.name == 'nt' and snapshot.get('platform_metrics_error'):
            reasons.append('platform_pressure_metrics_unavailable')
        return {'allowed': not reasons, 'reasons': reasons, 'reserve_gib': reserve,
                'minimum_available_gib': floor, 'snapshot': snapshot,
                'scope': 'instantaneous admission; no peak guarantee or unrelated-process control',
                'unavailable_metrics': [k for k in ['commit_pct', 'nonpaged_gib'] if snapshot.get(k) is None]}
    except (OSError, ValueError, TypeError, KeyError) as error:
        return {'allowed': False, 'reasons': ['memory_measurement_unavailable'],
                'error_type': type(error).__name__, 'minimum_available_gib': settings.get('minimum_available_gib', 3)}


class MemoryHistory:
    """At most 120 samples; no request values, result payloads or client identifiers."""
    def __init__(self, size=120):
        self.samples = deque(maxlen=size); self.lock = threading.Lock()
        self.peak_rss_mib = 0; self.peak_private_mib = None

    def sample(self, counters):
        import psutil
        info = psutil.Process().memory_info()
        rss = info.rss/1024**2; private = getattr(info, 'private', None)
        row = {'at_utc': utc(), 'monotonic_seconds': round(time.monotonic(), 3),
               'rss_mib': round(rss, 2), 'private_mib': round(private/1024**2, 2) if private is not None else None,
               'active': counters.get('active', 0), 'waiting': counters.get('waiting', 0)}
        with self.lock:
            self.samples.append(row); self.peak_rss_mib = max(rss, self.peak_rss_mib)
            if private is not None: self.peak_private_mib = max(private/1024**2, self.peak_private_mib or 0)
            return self._report()

    def _report(self):
        rows = list(self.samples)
        duration = rows[-1]['monotonic_seconds']-rows[0]['monotonic_seconds'] if len(rows)>1 else 0
        return {'samples': rows, 'retained_samples': len(rows), 'maximum_samples': self.samples.maxlen,
                'window_seconds': round(duration, 3), 'peak_rss_mib': round(self.peak_rss_mib, 2),
                'peak_private_mib': round(self.peak_private_mib, 2) if self.peak_private_mib is not None else None,
                'rss_change_mib': round(rows[-1]['rss_mib']-rows[0]['rss_mib'], 2) if rows else None,
                'leak_established': False, 'long_term_acceptance': 'requires observed endurance receipts'}


class BoundedCache:
    """In-memory LRU with byte/item/TTL limits. Caller must restrict keys to public read-only data."""
    def __init__(self, max_items=32, max_bytes=2*1024**2, ttl=30):
        self.items = OrderedDict(); self.max_items = max_items; self.max_bytes = max_bytes
        self.ttl = ttl; self.bytes = 0; self.lock = threading.Lock(); self.hits = 0; self.misses = 0

    def get(self, key):
        with self.lock:
            item = self.items.get(key)
            if item and time.monotonic()-item[0] <= self.ttl:
                self.items.move_to_end(key); self.hits += 1
                return copy.deepcopy(item[1])
            if item: self.bytes -= self.items.pop(key)[2]
            self.misses += 1
            return None

    def put(self, key, value):
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())
        if size > self.max_bytes: return
        with self.lock:
            if key in self.items: self.bytes -= self.items.pop(key)[2]
            while self.items and (len(self.items)>=self.max_items or self.bytes+size>self.max_bytes):
                self.bytes -= self.items.popitem(last=False)[1][2]
            self.items[key] = (time.monotonic(), copy.deepcopy(value), size); self.bytes += size

    def summary(self):
        with self.lock:
            return {'items': len(self.items), 'bytes': self.bytes, 'hits': self.hits, 'misses': self.misses,
                    'ttl_seconds': self.ttl, 'maximum_bytes': self.max_bytes}


def inspect_client_config(path, expected_port, expected_token=None):
    """Selected JSON/TOML only; expose counts/issues, never credentials, labels or filesystem paths."""
    path = Path(path)
    if path.stat().st_size > 2*1024**2: raise ValueError('Selected client configuration exceeds 2 MiB')
    if path.suffix == '.toml':
        import tomllib
        data = tomllib.loads(path.read_text(encoding='utf8')); entries = data.get('mcp_servers', {})
    else:
        data = json.loads(path.read_text(encoding='utf8'))
        entries = data.get('mcpServers', data.get('servers', data.get('mcp', {}).get('servers', {})))
    relevant = [entry for name, entry in entries.items() if name in {'biomni', 'bioresearch'}]
    issues = []; shared = 0; legacy = 0; disabled = 0
    for entry in relevant:
        if entry.get('enabled') is False: disabled += 1; continue
        if 'command' in entry or 'args' in entry:
            legacy += 1; issues.append('legacy_stdio_registration')
        else:
            from urllib.parse import urlsplit
            endpoint = urlsplit(entry.get('url', ''))
            if endpoint.hostname not in {'localhost', __import__('ipaddress').ip_address(__import__('socket').INADDR_LOOPBACK).compressed} or endpoint.port != expected_port or endpoint.path != '/mcp':
                issues.append('unexpected_endpoint')
            elif not entry.get('http_headers', entry.get('headers', {})).get('Authorization', '').startswith('Bearer '):
                issues.append('authentication_header_missing')
            else:
                shared += 1
                if expected_token is not None:
                    import secrets
                    if not secrets.compare_digest(entry.get('http_headers', entry.get('headers', {}))['Authorization'], 'Bearer '+expected_token):
                        issues.append('authentication_header_does_not_match_owned_service')
    if shared+legacy > 1: issues.append('multiple_enabled_compatibility_aliases')
    return {'selected_config_only': True, 'shared_entries': shared, 'legacy_entries': legacy,
            'disabled_entries': disabled, 'issues': sorted(set(issues)),
            'live_client_adoption': 'not established by static configuration', 'processes_started': False}
