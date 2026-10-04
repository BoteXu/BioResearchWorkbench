"""Real external process acceptance with synthetic sources only; temporary output remains private."""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'bridge'))
import academic_common
import configure_mcp
import semantic_index_ext
from probe_mcp import probe


def main(runtime_root,browser_executable=''):
    runtime=Path(runtime_root).resolve(strict=True)
    if not browser_executable:
        # Keep path construction out of Git Bash/MSYS argument conversion.
        if sys.platform.startswith('linux') and shutil.which('google-chrome'):
            browser_executable=shutil.which('google-chrome')
        else:
            browser_executable=subprocess.check_output([shutil.which('node'),'-e','process.stdout.write(require(process.argv[1]).chromium.executablePath())',str(runtime/'playwright/node_modules/playwright')],text=True)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp).resolve();academic_common.HERE=root
        project=root/'fixture-code';project.mkdir();(project/'analysis.py').write_text('def summarize(values):\n    return sum(values) / len(values)\n\ndef report():\n    return summarize([1,3])\n')
        def executable(name,command):return runtime/name/('Scripts' if os.name=='nt' else 'bin')/(command+'.exe' if os.name=='nt' else command)
        env={**os.environ,'SERENA_HOME':str(root/'initial-serena-private'),'PATH':str(executable('serena','python').parent)+os.pathsep+os.environ.get('PATH','')}
        p=subprocess.run([str(executable('serena','serena')),'project','create','--language','python_jedi',str(project)],capture_output=True,text=True,env=env,timeout=90)
        if p.returncode:raise RuntimeError('Synthetic code project initialization failed')
        database=root/'selected.duckdb'
        code="import duckdb; c=duckdb.connect("+repr(str(database))+"); c.execute('CREATE TABLE observations AS SELECT 1 AS id,2 AS value UNION ALL SELECT 2,4'); c.close()"
        subprocess.run([str(executable('duckdb','python')),'-c',code],check=True)
        records=[{'id':'fixture-paper-a','text':'Synthetic heart fibrosis study; this is not an actual paper.','source_version':'fixture-v1','source_location':'paragraph:1'},
                 {'id':'fixture-paper-b','text':'Synthetic telescope calibration study; this is not an actual paper.','source_version':'fixture-v1','source_location':'paragraph:2'}]
        result=semantic_index_ext.prepare_semantic_index(records,'selected',str(root/'index'),True)
        subprocess.run([str(executable('qdrant','python')),str(ROOT/'provision_mcp_model.py'),'--cache-dir',str(runtime/'embedding-cache')],check=True)
        subprocess.run([str(executable('qdrant','python')),str(ROOT/'bridge/semantic_index_runner.py'),str(Path(result['output_directory'])/'index_plan.json'),'--reviewed-sha256',result['plan_sha256'],'--cache',str(runtime/'embedding-cache')],check=True)
        data=configure_mcp.generate(str(runtime),str(root/'profiles'),str(project),str(database),str(root/'index'),'selected',shutil.which('node'),str(runtime/'playwright/node_modules/@playwright/mcp/cli.js'),browser_executable)
        calls={'brw-serena':[{'tool':'get_symbols_overview','arguments':{'relative_path':'analysis.py'},'contains':'summarize'},{'tool':'find_referencing_symbols','arguments':{'name_path':'summarize','relative_path':'analysis.py'},'contains':'report'}],
               'brw-duckdb':[{'tool':'query_table','arguments':{'table_name':'observations','columns':['id','value']},'contains':'4'},{'tool':'query_table','arguments':{'table_name':'foreign','columns':['id']},'expect_error':True}],
               'brw-qdrant':[{'tool':'qdrant-find','arguments':{'query':'heart fibrosis'},'contains':'fixture-paper-a'}],
               'brw-playwright':[{'tool':'browser_navigate','arguments':{'url':'about:blank'},'contains':'about:blank'},{'tool':'browser_evaluate','arguments':{'function':'() => { document.body.innerHTML = "<button id=inc>Increase</button><output id=count>0</output>"; document.getElementById("inc").onclick = () => document.getElementById("count").textContent = "1"; document.getElementById("inc").click(); return document.getElementById("count").textContent; }'},'contains':'1'}]}
        output=root/'acceptance';output.mkdir()
        results=asyncio.run(probe(data,calls,output))
        for result in results:
            if result['state']!='calls_passed':
                # This test uses only synthetic records and a disposable browser, never a private project/library.
                for call in result['calls']:
                    if not call['passed']:
                        message=json.dumps(call['response'],ensure_ascii=True).replace(str(root),'[fixture-root]').replace(str(runtime),'[runtime-root]')
                        print('SYNTHETIC_CALL_DIAGNOSTIC',result['server'],call['tool'],message[:3000])
        assert all(r['state']=='calls_passed' for r in results),'Actual MCP calls did not all pass'
        assert next(r for r in results if r['server']=='brw-qdrant')['tools']==['qdrant-find'],'Index write tool must not be exposed'
        assert set(next(r for r in results if r['server']=='brw-serena')['tools'])=={'get_symbols_overview','find_symbol','find_referencing_symbols','get_current_config'},'Unexpected code capabilities'
        print('ALL_FOUR_EXTERNAL_MCP_PROCESSES_ACCEPTED; SYNTHETIC_SCOPE_ONLY')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime-root',required=True);p.add_argument('--browser-executable',default='');a=p.parse_args();main(a.runtime_root,a.browser_executable)
