"""Expose selected Biomni tools directly to Codex over MCP."""

import sys
import threading
from contextlib import redirect_stdout

from mcp.server.fastmcp import FastMCP

from bridge import query_database, readiness, run_tool, tool_catalog
from evidence import record_claim
from job_manager import submit, status, cancel, list_jobs
from tool_contracts import MolecularContext, MolecularTask, ExecutionReceipt, Availability
from evidence import health

# Load descriptions and direct routing before worker threads, without a model stack.
with redirect_stdout(sys.stderr):
    tool_catalog(limit=1)


mcp = FastMCP("BioResearchWorkbench")
_STDIO_LOCK = threading.RLock()


@mcp.tool()
def biomni_status() -> dict:
    """List available direct Biomni biomedical tools; no model or API key is needed."""
    return readiness()


@mcp.tool()
def biomni_database_query(name: str, parameters: dict) -> ExecutionReceipt:
    """Call a selected Biomni database tool with explicit API parameters. Use biomni_status for supported names. Natural-language prompt parameters are disabled because they require a separate model. Full source response is saved with a SHA-256 receipt."""
    with _STDIO_LOCK, redirect_stdout(sys.stderr):
        return ExecutionReceipt(**query_database(name, parameters))


@mcp.tool()
def biomni_tool_catalog(category: str = "", search: str = "", limit: int = 30, check_imports: bool = False) -> dict:
    """Find Biomni's registered specialist tools by category or keyword. import_ready means the module loads, not that every tool's optional runtime dependencies are present."""
    with _STDIO_LOCK, redirect_stdout(sys.stderr):
        return tool_catalog(category or None, search or None, limit, check_imports)


@mcp.tool()
def biomni_run_tool(category: str, name: str, parameters: dict) -> ExecutionReceipt:
    """Run a registered Biomni scientific tool after inspecting its catalog entry and parameters. Database calls use biomni_database_query. Code-execution helpers and lab automation are excluded. Results are saved with a SHA-256 receipt."""
    with _STDIO_LOCK, redirect_stdout(sys.stderr):
        return ExecutionReceipt(**run_tool(category, name, parameters))


@mcp.tool()
def biomni_job_submit(operation: dict, timeout_seconds: int = 600) -> dict:
    """Start an actual detached local job. operation={kind:'database'|'tool', name, parameters, category for tool}. Returns a job_id and durable status; accepted does not mean completed. Partial files and logs are retained on failure/cancellation."""
    return submit(operation, timeout_seconds)


@mcp.tool()
def biomni_job_status(job_id: str) -> dict:
    """Read a durable job state and, after completion, its result receipt. Progress stages are lifecycle states, not scientific percentages."""
    return status(job_id)


@mcp.tool()
def biomni_job_cancel(job_id: str) -> dict:
    """Cancel this bridge's verified worker process and descendants while preserving partial files and logs."""
    return cancel(job_id)


@mcp.tool()
def biomni_job_list(limit: int = 20) -> dict:
    """List recent local jobs, including completed, failed, timed-out and cancelled tasks."""
    return list_jobs(limit)


@mcp.tool()
def biomni_evidence_record(claim: str, receipts: list[str], context: dict, limitations: list[str]) -> dict:
    """Link an explicit scientific claim to receipt/source hashes and caller-supplied context (species, model, assay, biological unit, contrast). Verifies file integrity, not the truth of the interpretation."""
    return record_claim(claim, receipts, context, limitations)


@mcp.tool()
def biomni_tool_availability(category: str, name: str) -> Availability:
    """Separate historical success, latest attempt and verification of the current source/dependencies/configuration; no tool execution."""
    with _STDIO_LOCK, redirect_stdout(sys.stderr):
        catalog = tool_catalog(category=category, search=name, limit=100)
        if not any(e['name'] == name for e in catalog['tools']): raise ValueError('Select a registered tool')
        return Availability(**health(category+'.'+name))


@mcp.tool()
def biomni_molecular_plan(task: MolecularTask, context: MolecularContext) -> ExecutionReceipt:
    """Prepare a molecular dry-lab route with explicit scientific context and QC. This does not submit or run analysis."""
    with _STDIO_LOCK, redirect_stdout(sys.stderr):
        return ExecutionReceipt(**run_tool('molecular_biology', 'guide_molecular_drylab', {'task':task, 'context':context.model_dump(exclude_none=True)}))


@mcp.tool()
def biomni_splicing_audit(records: list[dict], context: MolecularContext) -> ExecutionReceipt:
    """Review returned event/isoform results. Fraction units are required for delta-PSI/usage; read MOLECULAR_DRYLAB.md for nested record fields."""
    with _STDIO_LOCK, redirect_stdout(sys.stderr):
        return ExecutionReceipt(**run_tool('molecular_biology','audit_splicing_results',{'records':records,'context':context.model_dump(exclude_none=True)}))


@mcp.tool()
def biomni_regulatory_audit(records: list[dict], context: MolecularContext) -> ExecutionReceipt:
    """Review returned chromatin, RNA-binding or translation links, retaining binding/association/regulatory-direction boundaries."""
    with _STDIO_LOCK, redirect_stdout(sys.stderr):
        return ExecutionReceipt(**run_tool('molecular_biology','audit_regulatory_links',{'records':records,'context':context.model_dump(exclude_none=True)}))


if __name__ == "__main__":
    mcp.run(transport="stdio")
