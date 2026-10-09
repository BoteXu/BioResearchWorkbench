"""Safety and recovery contracts using bounded local fixtures, without analysis engines."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
from shared_support import admission, BoundedCache, MemoryHistory, inspect_client_config
from shared_mcp import SerialExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import upgrade


class LifecycleChecks(unittest.TestCase):
    def test_filename_import_does_not_require_ambient_bridge_path(self):
        root = Path(__file__).resolve().parents[1]
        code = "import importlib.util,sys;spec=importlib.util.spec_from_file_location('selected',sys.argv[1]);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);assert callable(v.admission)"
        subprocess.run([sys.executable,'-I','-c',code,str(root/'bridge/shared_mcp.py')], check=True, capture_output=True)
    def test_upgrade_lease_prevents_concurrent_start_and_refuses_owned_runtime(self):
        from shared_mcp import ProcessLock
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); private = root/'.local/shared_mcp_private'; private.mkdir(parents=True)
            lease = upgrade.acquire_service_lease(root)
            try:
                self.assertTrue(upgrade.shared_service_held(root))
                with self.assertRaises(BlockingIOError): ProcessLock(private/'service.private.lock')
            finally: lease.close()
            runtime = ProcessLock(private/'service.private.lock')
            try:
                with self.assertRaises(ValueError): upgrade.acquire_service_lease(root)
            finally: runtime.close()
    def test_admission_checks_projected_commit_and_nonpaged_pressure(self):
        row = {'available_gib':8, 'total_gib':32, 'commit_pct':79, 'commit_limit_gib':16, 'nonpaged_gib':1}
        result = admission({'reserve_gib':1}, row)
        self.assertFalse(result['allowed']); self.assertIn('projected_commit_pressure', result['reasons'])
        row.update(commit_pct=40, nonpaged_gib=5)
        self.assertIn('nonpaged_pool_pressure', admission({}, row)['reasons'])
        row.update(nonpaged_gib=1, available_gib=6.1)
        self.assertTrue(admission({'minimum_available_gib':6, 'minimum_after_reserve_gib':4}, row)['allowed'])
        self.assertFalse(admission({}, {**row, 'available_gib':float('nan')})['allowed'])

    def test_cache_has_ttl_limits_and_copy_isolation(self):
        cache = BoundedCache(max_items=1, max_bytes=64, ttl=0.01)
        cache.put('a', {'data':[1]}); a = cache.get('a'); a['data'].append(2)
        self.assertEqual(cache.get('a'), {'data':[1]})
        cache.put('b', {'data':[2]}); self.assertIsNone(cache.get('a'))
        time.sleep(0.02); self.assertIsNone(cache.get('b'))
        cache.put('large', {'data':'x'*128}); self.assertIsNone(cache.get('large'))

    def test_call_ledger_rejects_replay_and_unknown_restart_outcome(self):
        async def scenario(root):
            journal = root/'calls.private.json'; executor = SerialExecutor(journal=journal)
            call_id = executor.reserve(); seen = []
            self.assertEqual(await executor.call(lambda:seen.append(1) or 'done', call_id=call_id), 'done')
            with self.assertRaisesRegex(ValueError, 'already dispatched'):
                await executor.call(lambda:seen.append(2), call_id=call_id)
            self.assertEqual(seen, [1]); self.assertEqual(executor.status(call_id)['state'], 'COMPLETED')
            pending = executor.reserve()
            recovered = SerialExecutor(journal=journal)
            self.assertEqual(recovered.status(pending)['state'], 'UNKNOWN_INTERRUPTED')
            with self.assertRaises(ValueError): await recovered.call(lambda:seen.append(3), call_id=pending)
            saved = json.loads(journal.read_text())
            self.assertFalse(saved['arguments_and_results_recorded'])
            self.assertTrue(all('arguments' not in v and 'result' not in v for v in saved['calls']))
            self.assertNotIn('done', journal.read_text())
        with tempfile.TemporaryDirectory() as folder: asyncio.run(scenario(Path(folder)))

    def test_drain_refuses_new_calls_and_keeps_running_worker(self):
        async def scenario():
            executor = SerialExecutor(); entered = threading.Event(); release = threading.Event()
            def work(): entered.set(); release.wait(2); return 'complete'
            call_id = executor.reserve(); first = asyncio.create_task(executor.call(work, call_id=call_id))
            while not entered.is_set(): await asyncio.sleep(0.005)
            executor.accepting = False
            with self.assertRaisesRegex(ValueError, 'draining'): await executor.call(lambda:'unexpected')
            first.cancel()
            with self.assertRaises(asyncio.CancelledError): await first
            self.assertEqual(executor.status(call_id)['state'], 'RUNNING')
            self.assertEqual(executor.counters['active'], 1)
            release.set()
            while executor.counters['active']: await asyncio.sleep(0.005)
            self.assertEqual(executor.status(call_id)['state'], 'COMPLETED')
        asyncio.run(scenario())

    def test_bounded_ledger_unknown_id_never_reexecutes(self):
        async def scenario():
            executor = SerialExecutor(); oldest = None
            for index in range(260):
                ticket = executor.reserve(); oldest = oldest or ticket
                await executor.call(lambda:None, call_id=ticket)
            self.assertEqual(len(executor.records), 256)
            self.assertEqual(executor.status(oldest)['state'], 'UNKNOWN_NOT_RETAINED')
            with self.assertRaises(ValueError): await executor.call(lambda:None, call_id=oldest)
        asyncio.run(scenario())

    def test_selected_config_report_never_discloses_labels_or_token(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            path.write_text(json.dumps({'mcpServers':{'biomni':{'command':'fixture'}, 'bioresearch':{'command':'fixture'}}}))
            result = inspect_client_config(path, 8768)
            self.assertIn('multiple_enabled_compatibility_aliases', result['issues'])
            self.assertNotIn('fixture', json.dumps(result)); self.assertNotIn(str(path), json.dumps(result))


if __name__ == '__main__': unittest.main()
