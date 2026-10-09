"""Actual multi-client shared MCP check; fixed metadata only, no public queries."""
import asyncio
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

import httpx
import psutil
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
STAGE = 'setup'


def is_fixture_process(process, bridge):
    arguments = process.cmdline()
    expected = (bridge/'shared_mcp.py').resolve()
    return 'serve' in arguments and any(Path(arg).resolve()==expected for arg in arguments if arg.endswith('shared_mcp.py'))


def payload(result):
    if result.isError: raise RuntimeError('MCP metadata call failed')
    return result.structuredContent or json.loads(next(x.text for x in result.content if x.type=='text'))


async def clients(settings, shared):
    global STAGE
    url = 'http://'+shared.LOOPBACK+':'+str(settings['port'])+'/mcp'
    headers = {'Authorization':'Bearer '+settings['token']}
    async with httpx.AsyncClient(trust_env=False, timeout=20) as untrusted:
        assert (await untrusted.get(url.replace('/mcp','/health'))).status_code == 401
        assert (await untrusted.get(url.replace('/mcp','/health'), headers={'Authorization':'Bearer wrong'})).status_code == 401
        assert (await untrusted.get(url.replace('/mcp','/health'), headers={**headers,'Host':'foreign.example.invalid'})).status_code == 403
        assert (await untrusted.post(url, headers={**headers,'Origin':'https://foreign.example.invalid'},json={})).status_code == 403
    async with httpx.AsyncClient(headers=headers, trust_env=False, timeout=30) as http_b:
        async with streamable_http_client(url, http_client=http_b) as (read_b, write_b, _):
            async with ClientSession(read_b, write_b) as client_b:
                STAGE = 'initialize-second'; await client_b.initialize()
                async with httpx.AsyncClient(headers=headers, trust_env=False, timeout=30) as http_a:
                    async with streamable_http_client(url, http_client=http_a) as (read_a, write_a, _):
                        async with ClientSession(read_a, write_a) as client_a:
                            STAGE = 'initialize-first'; await client_a.initialize()
                            STAGE = 'list-tools'
                            names = {tool.name for tool in (await client_a.list_tools()).tools}
                            assert 'biomni_job_submit' not in names and 'biomni_job_cancel' not in names
                            STAGE = 'runtime-pair'
                            a, b = await asyncio.gather(client_a.call_tool('biomni_shared_runtime',{}), client_b.call_tool('biomni_shared_runtime',{}))
                            a, b = payload(a), payload(b)
                            assert a['pid']==b['pid'] and a['identity']==b['identity']
                            STAGE = 'catalog-pair'
                            calls = await asyncio.gather(client_a.call_tool('biomni_tool_catalog',{'category':'workflow','limit':1}), client_b.call_tool('biomni_tool_catalog',{'category':'server','limit':1}))
                            assert all(payload(x)['tools'] for x in calls)
                            STAGE = 'policy-refusals'
                            assert (await client_a.call_tool('biomni_tool_catalog',{'check_imports':True})).isError
                            assert (await client_a.call_tool('biomni_run_tool',{'category':'transcriptomics','name':'run_bulk_rnaseq','parameters':{}})).isError
                            STAGE = 'body-limit'
                            assert (await http_a.post(url, content=b' '*(513*1024), headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'})).status_code==413
                STAGE = 'after-first-disconnect'
                after = payload(await client_b.call_tool('biomni_shared_runtime',{}))
                assert after['pid']==a['pid'] and after['max_active']==1 and after['active']==0
                assert after['source_matches_review']
                return after


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--minimum-available-gib', type=float, default=3)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        bridge = Path(folder)/'.local'; shutil.copytree(ROOT/'bridge', bridge,
            ignore=shutil.ignore_patterns('__pycache__','shared_mcp_private','results','jobs','outputs','sources','source_snapshots','evidence','data','downloads','articles','supplements','compute_config.json','privacy_config.json','software_registry.json'))
        spec = importlib.util.spec_from_file_location('shared_fixture', bridge/'shared_mcp.py')
        shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
        with socket.socket() as temporary:
            temporary.bind((shared.LOOPBACK,0)); port = temporary.getsockname()[1]
        shared.initialize(port, minimum_available_gib=args.minimum_available_gib)
        settings = shared.load_settings()
        process = None
        launchers = []
        try:
            # Simultaneous cold launchers must create one backend, then reuse it.
            for _ in range(3):
                launchers.append(subprocess.Popen([sys.executable,str(bridge/'shared_mcp.py'),'start'],
                    stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
            outputs=[]
            for launcher in launchers:
                stdout, stderr = launcher.communicate(timeout=60)
                if launcher.returncode:
                    try:
                        failed = json.loads(stdout)
                        detail = {k:failed[k] for k in ['action','reason','new_process_started'] if k in failed}
                    except (ValueError, TypeError):
                        text = stderr.decode('utf8',errors='replace')
                        detail = {'exception_types':__import__('re').findall(r'\b([A-Za-z]+Error):', text)}
                    print(json.dumps({'launcher_failure':detail,'available_gib':round(psutil.virtual_memory().available/1024**3,2)}))
                    raise RuntimeError('Shared launcher failed: '+str(launcher.returncode))
                outputs.append(json.loads(stdout))
            assert len({r['pid'] for r in outputs})==1
            assert sum(r['action']=='started' for r in outputs)==1
            runtime = shared.health(settings)
            assert runtime and runtime['pid']==outputs[0]['pid']
            process = psutil.Process(runtime['pid'])
            assert abs(process.create_time()-runtime['process_create_time']) < 0.01
            assert is_fixture_process(process, bridge)
            observed = asyncio.run(clients(settings, shared))
            assert observed['pid']==process.pid
            assert shared.start()['action']=='reused'
            print(json.dumps({'passed':True,'concurrent_launchers':3,'backend_instances':1,
                'independent_mcp_clients':2,'client_disconnect_isolated':True,
                'max_parallel_tool_calls':observed['max_active'],'authentication_and_limits':True,
                'local_scientific_workers_exposed':False,'public_queries':0,
                'fixture_minimum_available_gib':args.minimum_available_gib,
                'production_default_minimum_available_gib':3,
                'native_client_gui_adoption':'not verified'}))
        except BaseException as error:
            def error_types(exc):
                return [name for item in exc.exceptions for name in error_types(item)] if isinstance(exc, BaseExceptionGroup) else [type(exc).__name__]
            print(json.dumps({'failed_stage':STAGE,'error_types':error_types(error),
                              'service_still_healthy': bool(shared.health(settings))}))
            raise
        finally:
            for launcher in launchers:
                if launcher.poll() is None:
                    launcher.terminate(); launcher.wait(timeout=10)
            # Only terminate this test's exact authenticated fixture, never an existing host.
            runtime = shared.health(settings)
            if runtime:
                owned = psutil.Process(runtime['pid'])
                if abs(owned.create_time()-runtime['process_create_time'])<0.01 and is_fixture_process(owned, bridge):
                    owned.terminate(); owned.wait(timeout=15)


if __name__ == '__main__': main()
