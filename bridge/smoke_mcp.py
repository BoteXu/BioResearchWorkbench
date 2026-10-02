import asyncio
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def checked_receipt(reply, expected_tool):
    assert not reply.isError, reply
    payload = reply.structuredContent
    if not payload:
        payload = json.loads(next(item.text for item in reply.content if item.type == "text"))
    assert payload["tool"] == expected_tool, payload
    assert payload["success"] is True, payload
    raw = Path(payload["result_file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == payload["sha256"], payload
    return json.loads(raw)


async def main(network=False):
    here = Path(__file__).resolve().parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(here / "mcp_server.py")],
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = [tool.name for tool in listed.tools]
            assert {"biomni_status", "biomni_database_query", "biomni_tool_catalog", "biomni_run_tool", "biomni_job_submit", "biomni_job_status", "biomni_job_cancel", "biomni_job_list", "biomni_evidence_record"}.issubset(names), names
            status = await session.call_tool("biomni_status", {})
            assert not status.isError, status
            catalog = await session.call_tool("biomni_tool_catalog", {"category": "omics", "limit": 30})
            assert not catalog.isError, catalog
            payload = catalog.structuredContent or json.loads(next(item.text for item in catalog.content if item.type == "text"))
            assert payload["total_matches"] == 7, payload
            for category, expected in [('atlas', 4), ('workflow', 8)]:
                discovered = await session.call_tool('biomni_tool_catalog', {'category':category, 'limit':30})
                assert not discovered.isError, discovered
                data = discovered.structuredContent or json.loads(next(x.text for x in discovered.content if x.type == 'text'))
                assert data['total_matches'] == expected, data
            if shutil.which('ssh'):
                route = await session.call_tool('biomni_run_tool', {'category':'workflow','name':'inspect_ssh_route','parameters':{'alias':'server'}})
                route_result = checked_receipt(route, 'biomni.tool.workflow.inspect_ssh_route')
                assert route_result['authenticated'] is False
            else:
                print('MCP_SSH_ROUTE_SKIPPED_NOT_INSTALLED')
            print('MCP_THIN_CLIENT_CATALOG_AND_ROUTE_OK')
            if network:
                queried = await session.call_tool(
                    "biomni_database_query",
                    {"name": "uniprot", "parameters": {"endpoint": "uniprotkb/P01308?fields=accession"}},
                )
                uniprot_result = checked_receipt(queried, "biomni.tool.database.query_uniprot")
                assert "P01308" in json.dumps(uniprot_result), uniprot_result
                print('MCP_UNIPROT_QUERY_OK')
            fixture = here / 'data' / 'smoke_result.csv'
            fixture.parent.mkdir(exist_ok=True)
            fixture.write_text('id,effect,p,q\nexample,0.2,0.05,0.1\n',encoding='utf8')
            specialist = await session.call_tool(
                "biomni_run_tool",
                {"category": "workflow", "name": "audit_result_table", "parameters": {"path":str(fixture),'analysis':'differential','columns':{'feature':'id','effect':'effect','p':'p','q':'q'},'context':{}}},
            )
            result = checked_receipt(specialist, "biomni.tool.workflow.audit_result_table")
            assert result['table_format_pass'] and result['scientific_validity'] == 'not_established'
            print("MCP_TOOLS_OK", ", ".join(names))
            print("MCP_STATUS_OK")
            print("MCP_SPECIALIST_TOOL_OK")
            jobs = await session.call_tool("biomni_job_list", {"limit": 1})
            assert not jobs.isError, jobs
            print("MCP_JOB_LIST_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--network',action='store_true')
    args = parser.parse_args()
    asyncio.run(main(args.network))
