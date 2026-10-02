## Biomni for biomedical work

For substantive biomedical research requests, inspect the globally configured biomni MCP server with biomni_status and biomni_tool_catalog. Use a suitable verified tool when it improves the task. Do not install a skill to duplicate a working function.

Codex supplies reasoning; Biomni supplies tools. No separate Biomni reasoning model, E1 environment or data lake is included. Import readiness is not runtime proof. Verify primary sources and keep species, model, assay, biological unit and causal limits explicit. Do not send sensitive data to public endpoints without specific authorization.

Large calculations and downloads run on the user's own server; local scope is retrieval, command preparation/dispatch, task tracking, returned-result checks and interpretation. Reuse existing server environments. Confirm the current compute hostname before dispatch; keep heavy work off the login node. Server authentication and routing must be configured by the recipient.

Bridge 2.1 atlas routes provide GTEx/HPA/CELLxGENE/ENA public metadata. workflow helpers prepare tasks and inventories, inspect returned lifecycle snapshots, check output hashes, sample metadata and result tables. Preparation is not submission; a local biomni_job_submit worker is not an HPC scheduler. Require real SSH/scheduler receipts. Reject stale output reuse, inspect active processes before recovery, and retain failed/partial outputs.

When MCP tools are unavailable, use {{INSTALL_DIR}}/.venv_tools/Scripts/python.exe with {{INSTALL_DIR}}/.local/bridge.py. Inspect --status, --catalog, --run and --params-file. Scientific validity is not established by table formatting, caller-supplied context or file integrity.
