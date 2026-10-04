"""Scope-bound structured MCP table reads using DuckDB; never expose arbitrary SQL."""
import argparse
from pathlib import Path
from table_query_ext import query_selected_table, _name


def main(database,table_names):
    from fastmcp import FastMCP
    path=Path(database).resolve(strict=True)
    if not table_names or len(table_names)>30 or len(set(table_names))!=len(table_names):raise ValueError('Explicit table allowlist required')
    for name in table_names:_name(name)
    mcp=FastMCP('Workbench selected DuckDB')
    @mcp.tool()
    def query_table(table_name: str, columns: list[str], filters: list[dict] | None = None, limit: int = 100, order_by: str = '') -> dict:
        """Read explicitly selected table columns with bound scalar predicates; no arbitrary SQL, external files or network functions."""
        if table_name not in table_names:raise ValueError('Table is outside configured scope')
        return query_selected_table(str(path),table_name,columns,filters,limit,order_by)
    @mcp.tool()
    def selected_scope() -> dict:
        """Describe selected table names and bounded access policy without listing other databases or files."""
        return {'tables':table_names,'read_only':True,'external_access':False,'row_limit':500,'timeout_seconds':10,'scientific_validation':False}
    mcp.run(transport='stdio')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--allow-table',action='append',required=True);a=p.parse_args();main(a.database,a.allow_table)
