"""Execute explicitly supplied acceptance calls; keep all detailed MCP receipts private."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path


async def probe(profiles,calls,output):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from datetime import timedelta
    result=[]
    for name,entry in profiles['mcpServers'].items():
        state={'server':name,'state':'unavailable','calls':[]}
        # Do not echo exception bodies, command paths, requests or tool output to console.
        try:
            env={**os.environ,**entry.get('env',{})}
            params=StdioServerParameters(command=entry['command'],args=entry['args'],env=env,cwd=entry.get('cwd'))
            with (output/(name+'.stderr.private.txt')).open('w',encoding='utf8') as log:
                async with stdio_client(params,errlog=log) as (read,write):
                    async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=90)) as session:
                        await session.initialize();listed=await session.list_tools();state['tools']=[t.name for t in listed.tools]
                        for call in calls.get(name,[]):
                            value=await session.call_tool(call['tool'],call.get('arguments',{}));data=value.model_dump(mode='json')
                            check=value.isError if call.get('expect_error') else not value.isError
                            rendered=json.dumps(data,ensure_ascii=False)
                            if call.get('contains'):check=check and call['contains'] in rendered
                            state['calls'].append({'tool':call['tool'],'passed':bool(check),'response':data})
                        state['state']='calls_passed' if state['calls'] and all(c['passed'] for c in state['calls']) else 'connected_unprobed' if not state['calls'] else 'call_failed'
        except Exception as exc:state['error_type']=type(exc).__name__
        result.append(state)
        (output/'mcp-acceptance.private.json').write_text(json.dumps({'schema':1,'private':True,'servers':result},indent=2),encoding='utf8')
        print(name,state['state'],len(state.get('tools',[])),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profiles',required=True);p.add_argument('--calls',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=False)
    states=asyncio.run(probe(json.loads(Path(a.profiles).read_text()),json.loads(Path(a.calls).read_text()),out))
    raise SystemExit(0 if all(s['state']=='calls_passed' for s in states) else 1)
