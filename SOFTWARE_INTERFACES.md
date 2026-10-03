# Persistent software interfaces

The `software` category provides a private persistent registry. `software.register_local_software` accepts a known adapter name and installed executable path, runs only its fixed version probe, and saves the result in `software_registry.json` inside that installation. `software.software_inventory` reports discovered/registered paths and states without starting analyses or services.

Registry files, executable binaries, server paths and runtime receipts remain private and are excluded from source publication. Moving or upgrading software requires re-registering and checking a real task. A successful version probe does not establish an analysis run or installed R-package availability.

| Interface | Supported behavior | Boundary |
|---|---|---|
| Rscript | Persistent path reused by limma/edgeR analysis backends | R and packages are installed separately in the intended environment. |
| AutoDock Vina | Persistent path reused by one-ligand docking | A bounded local run; libraries and MD stay on the server. |
| Open Babel | Fixed structure-conversion adapter with explicit pH and optional 3D generation | Preparation chemistry and docking atom types need review. |
| Cytoscape | GraphML import into a running local CyREST service | Local host only; an import response does not prove visual inspection or analysis. |
| samtools, STAR, Salmon, kallisto, FastQC, MultiQC, Nextflow | Version/discovery contracts and software roles for your server workflow | Local registry is not server discovery. Use returned server inventory and real scheduler/SSH receipts; the bridge does not launch heavy commands locally. |
| Docker | Runtime inventory/version contract | No image download, daemon start or container launch is performed by this adapter. |
| Model clients | Existing MCP stdio interface for Codex/Claude Desktop/VS Code/portable clients | Provider login and model API billing belong to that client. |

The registry is not a generic shell runner. There is no free-form command string, arbitrary software name or automatic execution of a new plugin. New software needs an explicit adapter with declared inputs, output checks and tests. This keeps software interfaces reusable without distributing credentials or relying on catalog labels as runtime proof.

## Cytoscape

With Cytoscape's local CyREST service already running, call `software.cytoscape_import_network` with the reviewed GraphML path and local port. The bridge posts the network through the documented [CyREST API](https://github.com/cytoscape/cyREST/wiki). It does not start the GUI or contact an external host. Imported networks still require visual review.

## Server software

Use the existing `workflow.prepare_server_inventory` bundle and your own shared SSH/scheduler workflow. Read the returned inventory snapshot, verify the current compute node, and choose the already installed server software. Preparation is not submission, and a receipt snapshot is not live process polling.

## Portability

Private registry settings are host-specific. Share the public package and these contracts with another person; they register their own installations and server route. Do not copy your private registry or generated client configurations into their package or a public issue.

## Version 2.7 health and preparation

Fixed version health comparisons and local CyREST health queries are available. Meeko single-ligand preparation has a bounded local adapter; receptor preparation is a server command adapter. Open Babel optional binary packaging is listed in requirements-interfaces.txt; a Windows synthetic conversion has executed. A live Cytoscape GUI remains unverified. See RESEARCH_WORKFLOWS.md and PRIVACY_SECURITY.md.
