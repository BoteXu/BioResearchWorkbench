"""Shared transport safety checks; no biomedical analysis or public queries."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import socket
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'bridge'))
import shared_mcp
import client_config


class SharedChecks(unittest.TestCase):
    def test_lifetime_lock_and_release(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve()/'instance.lock'
            first = shared_mcp.ProcessLock(path)
            try:
                with self.assertRaises(BlockingIOError): shared_mcp.ProcessLock(path)
            finally:
                first.close()
            second = shared_mcp.ProcessLock(path); second.close()

    def test_reconfiguration_preserves_credentials_and_refuses_changed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); (root/'fixture.py').write_text('fixture = 1')
            with patch.object(shared_mcp, 'BRIDGE', root), patch.object(shared_mcp, 'PRIVATE', root/'private'):
                shared_mcp.initialize()
                first = shared_mcp.load_settings()
                shared_mcp.initialize()
                self.assertEqual(first, shared_mcp.load_settings())
                (root/'fixture.py').write_text('fixture = 2')
                with self.assertRaises(ValueError): shared_mcp.initialize()
                with patch.object(shared_mcp, 'health', return_value=None):
                    shared_mcp.initialize(review_current_source=True)
                after = shared_mcp.load_settings()
                self.assertEqual(first['token'], after['token'])
                self.assertNotEqual(first['source_sha256'], after['source_sha256'])
                with self.assertRaises(ValueError): shared_mcp.initialize(port=8769)

    def test_shared_configs_have_no_worker_command_and_registration_preserves_others(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()/'install'; local = root/'.local'; local.mkdir(parents=True)
            python = root/'.venv_tools'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            python.parent.mkdir(parents=True); python.touch(); (local/'mcp_server.py').touch()
            private = local/'shared_mcp_private'; private.mkdir()
            token = 'synthetic-authentication-'+'x'*48
            (private/'settings.private.json').write_text(json.dumps({'schema':1,'port':8768,'token':token}))
            output = Path(folder).resolve()/'configs'
            data = client_config.generate(root, output, server_name='fixture', transport='shared')
            entry = json.loads(data['portable.mcp.json'])['mcpServers']['fixture']
            self.assertNotIn('command', entry); self.assertNotIn('args', entry)
            self.assertEqual(entry['headers']['Authorization'], 'Bearer '+token)
            self.assertNotIn('claude-desktop.json', data)
            home = Path(folder).resolve()/'home'; (home/'.codex').mkdir(parents=True)
            config = home/'.codex/config.toml'; before = 'model = "fixture"\n[mcp_servers.other]\ncommand = "fixture"\n'
            config.write_text(before)
            before_bytes = config.read_bytes()
            with patch.object(Path, 'home', return_value=home):
                client_config.register_shared_codex(output, 'fixture')
                with self.assertRaises(ValueError): client_config.register_shared_codex(output, 'fixture')
            self.assertIn(before.rstrip(), config.read_text())
            self.assertEqual(next(output.glob('*.private.toml')).read_bytes(), before_bytes)

    def test_cancelled_wait_does_not_release_actual_worker_gate(self):
        async def scenario():
            executor = shared_mcp.SerialExecutor()
            entered = threading.Event(); order = []
            def work(name):
                order.append((name, 'start')); entered.set(); time.sleep(0.08)
                order.append((name, 'end')); return name
            first = asyncio.create_task(executor.call(work, 'first'))
            while not entered.is_set(): await asyncio.sleep(0.005)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError): await first
            self.assertEqual(await executor.call(work, 'second'), 'second')
            self.assertEqual(order, [('first','start'),('first','end'),('second','start'),('second','end')])
            self.assertEqual(executor.counters['max_active'], 1)
        asyncio.run(scenario())

    def test_queue_timeout_starts_no_operation_and_worker_failure_releases_gate(self):
        async def scenario():
            executor = shared_mcp.SerialExecutor(queue_timeout=0.02)
            entered = threading.Event(); called = []
            def slow(): entered.set(); time.sleep(0.08)
            first = asyncio.create_task(executor.call(slow))
            while not entered.is_set(): await asyncio.sleep(0.005)
            with self.assertRaisesRegex(ValueError, 'before execution'):
                await executor.call(lambda: called.append('unexpected'))
            await first
            self.assertEqual(called, [])
            def fails(): raise RuntimeError('fixture')
            with self.assertRaises(RuntimeError): await executor.call(fails)
            self.assertEqual(await executor.call(lambda: 'ready'), 'ready')
            self.assertEqual(executor.counters['active'], 0)
        asyncio.run(scenario())

    def test_execution_profile_denies_numerical_and_unknown_operations(self):
        exports = {'statistics':('fixture', ['guide_study_statistics','compare_groups']),
                   'transcriptomics':('fixture',['run_bulk_rnaseq'])}
        self.assertTrue(shared_mcp.permitted('statistics','guide_study_statistics',exports))
        self.assertFalse(shared_mcp.permitted('statistics','compare_groups',exports))
        self.assertFalse(shared_mcp.permitted('transcriptomics','run_bulk_rnaseq',exports))
        self.assertFalse(shared_mcp.permitted('unknown','unknown',exports))
        self.assertNotIn('biomni_job_submit', shared_mcp.ALLOWED_MCP_TOOLS)

    def test_default_admission_refuses_low_memory_without_launching(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); (root/'fixture.py').touch()
            with socket.socket() as selected:
                selected.bind(('localhost',0)); port = selected.getsockname()[1]
            with patch.object(shared_mcp,'BRIDGE',root), patch.object(shared_mcp,'PRIVATE',root/'private'):
                shared_mcp.initialize(port)
                fake = SimpleNamespace(virtual_memory=lambda:SimpleNamespace(available=int(2.9*1024**3)))
                with patch.dict(sys.modules,{'psutil':fake}), patch.object(shared_mcp,'health',return_value=None), patch.object(shared_mcp.subprocess,'Popen') as launched:
                    result = shared_mcp.start()
                self.assertEqual(result['action'],'refused')
                self.assertEqual(result['minimum_available_gib'],3)
                launched.assert_not_called()


if __name__ == '__main__': unittest.main()
