# BioResearchWorkbench

**以分子生物学干实验为重点的生物医学科研工作台：公开检索、统计与分析设计、输入 QC、服务器计算衔接、返回结果审查、证据追溯和论文交付。**

最初的底层基于 [Biomni](https://github.com/snap-stanford/Biomni)。本项目在此基础上编写桥接、检查、任务衔接和工作流，并组合第三方研究软件。上游算法、数据库、模型、软件和客户端插件保留各自归属；详见 [来源与第三方归属](ORIGINS.md) 和 [组件清单](third_party_components.json)。这是独立的下游工作台。

The original foundation is Biomni. This independent downstream project adds tool adapters, QC/evidence checks and workflow orchestration, while preserving third-party attribution. The host model supplies reasoning; this tool layer needs no additional model API key or local LLM. It does not include Biomni-R0, the full E1 environment or a data lake.

[![Public verification](https://github.com/BoteXu/BioResearchWorkbench/actions/workflows/verify.yml/badge.svg)](https://github.com/BoteXu/BioResearchWorkbench/actions/workflows/verify.yml)

## v2.13.1 更新：多会话共享后台

服务器安装默认生成认证的 HTTP MCP 配置，让多个聊天共用一个 BioResearchWorkbench 后台。启动锁和服务锁防止重复初始化；调用统一排队，即使会话取消等待，真正运行的任务结束后才放行下一项。共享配置提供检索、服务器准备和有界检查，关闭本地科研工作进程与批量依赖导入。

Windows、macOS 和 Linux 使用同一共享入口。安装器生成私有认证和配置，由使用者启动后台；登录自启是明确的可选配置。原 stdio 和可选本地版保留。已有聊天可能缓存旧连接，需核对实际实例。操作与迁移见 [SHARED_MCP.md](SHARED_MCP.md)。

## v2.13.0 的分子生物学与工程扩展

本次深化分子生物学干实验，并补齐八个工程方向。扩展函数定义、必需参数、默认值、枚举、模板、模块信息与版本差异由公开源码生成，见 [功能目录](TOOL_CATALOG.md) / [机器可读合同](TOOL_CATALOG.json)。模板中的占位符必须替换为经审查的真实输入。

<!-- GENERATED:CATALOG:BEGIN -->
**公开目录（自动生成）**：242 个扩展函数、37 个类别、147 个任务路由、15 个原始工作流 skill。上游 Biomni 工具和客户端插件另行发现；这些数量不代表全部后端都已验收。
<!-- GENERATED:CATALOG:END -->

| 工程方向 | 本版提供什么 | 验收和使用边界 |
|---|---|---|
| 准确的工具状态 | 历史成功、最近尝试、当前环境验证分开；源码、依赖元数据、配置、解释器与登记软件变化使验证过期 | `passed` 只针对该环境下的已观测调用；旧成功不能覆盖最近失败 |
| 安全升级与回滚 | 包完整性校验、升级预览、配置/依赖兼容检查、审核哈希、逐文件备份与失败回滚；复用配置迁移工具 | 自定义 skill 保留；定制桥接代码需合并；升级不迁移凭据、安装依赖或改客户端注册 |
| 文档与目录同步 | 自动生成工具目录、参数合同、调用模板、版本差异和 README 数量；CI 检查一致性 | 静态目录不是运行验收；上游工具由运行目录另行发现 |
| 可选模块加载 | `BIOMNI_MODULES` 选择类别，按实际调用延迟导入；专用 MCP 入口随所选模块暴露 | 不自动安装依赖，不授予文件/网络/库写权限 |
| 更明确的 MCP 调用 | 保留通用入口，增加状态、分子路线、剪接与调控专用入口，提供输入约束、输出 schema 和结构化结果 | 检查 `success`、具体 QC 和原始来源；schema 一致不证明科学主张成立 |
| 科学基准 | 许可明确的 pasilla/DESeq2 和 ToothGrowth/Welch 参考检查；接口、后端完成、参考一致分层 | 在独立 CI 或获准服务器运行；只覆盖所列设计和指标范围 |
| 服务器任务管理 | pilot 资源/成本预算、不明提交核查、增量回传计划；复用队列观测与检查点审查 | 使用已有共享 SSH/调度环境；准备不是提交，未知提交不自动重试 |
| 按问题操作 | 认证页面选择研究方向、查看 QC、来源和缺失结果；项目页显示证据谱系和阶段阻断 | 路线按钮只生成计划；浏览器令牌和私有结果留在受控环境 |

具体合同、升级说明和限制见 [EVOLUTION.md](EVOLUTION.md)。

## 分子生物学入口

`molecular_biology.guide_molecular_drylab` 提供 16 个问题方向；也可使用有类型约束的 MCP 入口 `biomni_molecular_plan`。先明确物种、模型、真正独立的生物学单位、比较方向、来源/注释版本；涉及基因组坐标时还需组装版本。正式推断先做统计咨询和输入/设计/参考 QC。

- **基因与 RNA**：注释/映射、表达、单细胞、可变剪接、异构体、长读长结果审查。
- **调控与蛋白**：染色质、RNA 结合、翻译、表观遗传、调控网络、蛋白功能与蛋白组/PTM。
- **互作与机制**：PPI/复合体、条件特异扰动、结构/CADD、逐条机制证据和冲突。
- **三个新增官方只读查询**：IntAct、Complex Portal、Cellosaurus。每次需明确批准所查询的公开标识；IntAct 只读一页，返回筛选与覆盖范围，空页不能证明没有互作。
- **六种新增摘要审查**：剪接、调控、蛋白注释、互作、扰动、机制图。记录需绑定来源和上下文；`qc_gate_pass` 表示摘要合同一致，科学有效性仍需独立审查。
- **固定流程准备**：nf-core ATAC/ChIP/甲基化按固定提交、参考和输入绑定 QC，生成服务器任务包；不执行引擎或下载参考。

rMATS、LeafCutter、DEXSeq、DRIMSeq、IsoQuant、FLAIR、SQANTI3、SCENIC 等列为方法候选，需要所选服务器环境和真实运行验收，不能当作已新增的可执行后端。外部 BioMCP、BioContextAI、ToolUniverse 和技能候选也保留审查状态，不自动安装/连接。详细路线见 [MOLECULAR_DRYLAB.md](MOLECULAR_DRYLAB.md)。

## 既有模块继续协同

| 模块 | 使用说明 |
|---|---|
| 文献、主张核验、综述与论文协作 | [学术工作流](ACADEMIC_WORKFLOWS.md)、[工作流 skill](SKILLS.md) |
| 统计指导与正式分析前设计 | [统计学模块](STATISTICS.md) |
| Bulk、单细胞、空间、通路与 PPI | [分析与研究流程](RESEARCH_WORKFLOWS.md)、[有界本地版](LOCAL_ANALYSIS.md) |
| 结构、对接、MD 与 CADD 审查 | [CADD 工作流](CADD_WORKFLOWS.md)、[第三方 skill 审查](CADD_SKILL_REVIEW.md) |
| 代码/Notebook/工作流与医学研究 | [代码工作流](CODE_WORKFLOWS.md)、[临床研究](CLINICAL_RESEARCH.md) |
| 私有项目、证据谱系、复现与服务器适配器 | [项目工作台](WORKBENCH.md)、[科学后端](SCIENTIFIC_BACKENDS.md) |
| Zotero、个人研究索引与本机软件 | [Zotero](ZOTERO_LOCAL.md)、[个人文献库](PERSONAL_LIBRARY.md)、[软件接口](SOFTWARE_INTERFACES.md) |
| 可选 MCP 和平台访问 | [MCP 接入](MCP_INTEGRATIONS.md)、[平台说明](PLATFORMS.md) |

## 两个发行版

在 [Releases](https://github.com/BoteXu/BioResearchWorkbench/releases) 选择所需安装包。两个包共享工具源码，默认依赖和计算边界不同。

| 发行版 | 默认 profile | 适合的使用方式 |
|---|---|---|
| `server` | `core` | 本地检索、命令准备、任务/回执追踪、结果检查与交付；大计算、大下载、索引在已有服务器 |
| `local` | `local` | 在服务器版能力上选择有界的小型转录组、通路/PPI 和分子计算；先做 QC/资源检查，R/外部软件仍需配置和实测 |

私有配置、库、研究资料、运行回执和可选私有补充不随公开包分发。公开工作台的实现请求不授权修改私有文献库或对外传输敏感数据。

## 持续升级

### v2.13.2：共享服务可靠性与科研检查深化

新增统一内存准入、有界内存趋势、串行调用编号、选定连接/配置诊断、等待已有任务结束的停止流程，以及有容量和失效规则的缓存。升级与回滚持有共享服务锁。详见 [多会话共享后台](SHARED_MCP.md)。

新增文献去重与出版更新声明、物种/转录本/异构体映射、获准公开 ID 批量解析、六类服务器结果检查、逐条证据追溯。详见 [科研质量检查](RESEARCH_QUALITY.md)。检索完整性、真实回执、文件哈希、方法适用范围和科学结论分别报告。

新安装仍使用下面的平台安装器，并要求新目录。已有安装使用下载包中的 `upgrade.py`，先阅读 [升级与回滚说明](EVOLUTION.md)，检查与当前版本对应的受管文件基线。

```text
python upgrade.py --install-dir <私有安装目录> --preview-file <新的私有计划文件>
python upgrade.py --apply-plan <私有计划文件> --reviewed-sha256 <审核后的计划哈希>
python upgrade.py --rollback-journal <本次升级的私有 journal 文件>
```

未记录基线的旧安装只能从对应原版包显式初始化；定制源码不能被当作原版采用。源码/环境升级后重新启动工具进程，再进行实际调用验收。依赖变化、未知升级状态和升级后的定制内容需要分别核查；回滚源码不等于恢复分析任务。

## Cross-platform installation

For macOS and Linux run `sh ./Install.sh`; for HarmonyOS use the compatible environment or browser route in [PLATFORMS.md](PLATFORMS.md). The same lightweight core profile is used across desktop platforms.

## Install on Windows

Prerequisites: Windows x64 and `uv`. The `codex` command is required only for automatic Codex registration. OpenSSH is required for SSH-specific helpers. Installation downloads Python 3.11 if needed, the pinned official Biomni source and Python dependencies.

Download this repository, open PowerShell in its folder, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1
```

The default destination is a new `BioResearchWorkbench` folder under the current user's profile. Use `-InstallDir` to select another new folder. Use `-ValidateOnly` to check repository file hashes. The installer refuses to overwrite an existing directory or an existing MCP entry with the selected registration name. `-SkipRegistration` permits installing separately before choosing how to register it.

### Profiles and other clients

| Profile | Scope |
|---|---|
| `core` (default) | Retrieval, documents, evidence, tasks and CSV/TSV result checks. No numpy, pandas, scipy, torch or model SDK stack is needed. |
| `local` | Bounded local transcriptomics, pathways, PPI and molecular tools. R backends and external software require their own configured installations. |
| `omics` | Core plus optional matrix/H5AD, enrichment and label-transfer helpers. Large analysis still belongs on the server. |
| `full` | Previous dependency snapshot for additional upstream specialist imports; this is not E1 or proof that every upstream function works. |

Use `-Profile omics` or `-Profile full` only when those optional local helpers are required.

For another client, use `-Client claude-desktop`, `-Client vscode` or `-Client portable`. These choices do not require the Codex CLI. Server profiles default to shared HTTP for Codex, VS Code and portable configurations; the local/Desktop profiles retain stdio. Choose `-Transport` explicitly when needed. Private snippets contain paths or authentication headers. Only the Codex choice adds a new registration automatically; existing names are refused and unrelated settings are preserved with a private backup. Start the shared backend once using [SHARED_MCP.md](SHARED_MCP.md), then reconnect idle clients.

The formats follow the documented [local MCP configuration](https://modelcontextprotocol.io/docs/develop/connect-local-servers) and [VS Code MCP configuration](https://code.visualstudio.com/docs/agent-customization/mcp-servers). The server protocol and generated JSON/TOML schemas are tested; individual client GUIs and models need their own connection validation. Provider login/API billing belongs to the chosen client and is separate from this tool layer.

Merge the generated `AGENTS.generated.md` Biomni section into your own Codex instructions, then open a new chat. Check `biomni_status`, inspect `biomni_tool_catalog` and test a public query.

If a trusted local DNS proxy uses synthetic addresses, review the proxy setup before explicitly passing `-TrustDnsProxy`. This option trusts that resolver's domain routing; it does not allow private IP literals or local hostnames. It is off by default.

## Server workflow

Configure your own SSH route and verify the current compute hostname. Credentials and server addresses are not bundled. Heavy jobs should not execute on a login node.

`prepare_remote_task` and `prepare_server_inventory` only create bundles. They do not connect or submit. Use your existing shared terminal or scheduler, then return small result files and execution receipts for review. Expected output paths must be fresh. Inspect current processes/logs before recovering interrupted tasks or stale locks.

`inspect_remote_task` reads a receipt snapshot; it is not live process polling. `biomni_job_submit` starts a local bridge worker, not a remote scheduler job. Submission is not completion.

## Privacy and evidence

This repository contains generic source, fixed dependencies and instructions. It does not distribute installation-specific paths, server configuration, credentials, names, research files or runtime receipts. The pinned official upstream source is fetched separately; its public attribution and license are retained.

Runtime records may contain paths, hostnames, parameters and input hashes. Keep them private. Do not attach logs, generated task bundles or result receipts to public issues without review. Runtime directories and credentials are excluded by `.gitignore`.

Import readiness does not establish runtime readiness. Table formatting, caller-supplied context and file integrity do not establish scientific validity. Keep species, model, assay, independent biological unit, contrast and causal limits explicit. Do not send sensitive data to public endpoints without specific authorization.

Tool catalog descriptions are read without importing a scientific/model stack. Upstream `import_ready: null` means its import was deferred. The shared profile refuses `check_imports=true` and marks inaccessible catalog entries; inspect selected availability receipts instead. Legacy stdio import probing remains explicit. Observed runtime passes remain distinct from dependency presence.

对于固定公开端点的只读 GET，收到 429/500/502/503/504 后最多尝试三次，每次响应保留来源记录。持续失败仍报告失败；连接状态不明和 POST 不自动重试。这不适用于服务器任务提交、原生写入或文献库写入。

## Verification

### Research helpers

Use `research.select_tools` through `biomni_run_tool` with the current explicit intents listed in the automatically generated [tool catalog](TOOL_CATALOG.md). Molecular dry-lab routes, engineering contracts and acceptance limits are described in [MOLECULAR_DRYLAB.md](MOLECULAR_DRYLAB.md) and [EVOLUTION.md](EVOLUTION.md). It returns catalog parameters, optional dependency checks and observed runtime state. It only prepares a plan. Set `large_computation=true` to select server preparation; `sensitive_data=true` blocks recommendations that would transmit the data to a public endpoint until specific authorization is obtained. These flags guide planning; they do not replace access controls or user consent.

`research.resolve_identifier` checks a single explicit public gene symbol, Ensembl gene ID, UniProt accession, rsID, PDB entry, PubChem CID or ChEMBL molecule ID. Gene/protein/variant queries require a supported species; rsID queries also require an assembly. Ambiguous candidates and source records are retained. Version mismatches, wrong species and unavailable assemblies are reported. Isoform lookups and genome build conversion are not silently substituted. PDB entry checks do not verify chain identity.

`research.audit_identifier_mapping` accepts a small local list of rows with `source_namespace`, `source_id`, `target_namespace`, `target_id`, `species`, `assembly` and `evidence_reference`. It detects malformed IDs, missing context, duplicate mappings, version suffixes and one-to-many/many-to-one joins. It makes no public queries and does not verify caller-supplied source assertions. Keep ambiguous relationships; do not select the first match merely to make a join work.

If the Ensembl symbol service times out or has a server failure, the resolver can collect UniProt gene cross-references and verify each candidate through Ensembl lookup. This fallback retains the failed attempt and marks candidate coverage incomplete (`partial` for a single candidate). A passing candidate identity check does not establish exhaustive symbol mapping; do not use a partial result as a guaranteed one-to-one join.

Official API contracts: [Ensembl symbol cross-references](https://rest.ensembl.org/documentation/info/xref_external), [Ensembl identifier lookup](https://rest.ensembl.org/documentation/info/lookup), [UniProt API](https://www.uniprot.org/help/api_queries), [RCSB Data API](https://data.rcsb.org/), [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest), and [ChEMBL web services](https://www.ebi.ac.uk/chembl/api/data/docs).

Run `python run_acceptance.py` for fixed offline checks. In an installed core environment, add `--network` to test six public identifier cases and an OLS candidate lookup, saving standard bridge receipts. Optional `--output-file` saves a private report and refuses overwriting. An offline pass explicitly says the network suite was not requested. A pass measures listed engineering checks, not general biomedical reasoning or scientific validity.

`python -m unittest discover -s tests -v` verifies synthetic sample/result audits, client formats, stale outputs and privacy gates. `bridge/smoke_mcp.py` verifies MCP discovery and a tiny result-table fixture; add `--network` for a real public database query.

GitHub Actions runs privacy/history/manifest checks and unit tests, then installs the core profile on clean Windows, Linux, macOS ARM and macOS Intel runners and tests MCP over the network. A separate browser check uses synthetic data at desktop and mobile viewport sizes; this does not certify HarmonyOS hardware. Inspect the actual run result before claiming clean-install success. Other client GUI integrations, optional profiles and a real HPC deployment are not implied by a core CI pass.

联网报告区分 `engineering_pass`、`network_pass` 和严格的 `pass`。CLI 默认要求所有请求的检查通过。CI 的安装门禁显式使用 `--allow-unavailable-public-services`：只对有完整回执的已识别 HTTP 429/500/502/503/504 或超时另列 `external_unavailable`，仍保留 `network_pass=false` 和 `pass=false`。身份不匹配、输入/认证/协议错误、回执损坏或离线失败均阻断。CI 绿色不代表所有外部服务此刻可用，需检查报告中的 `public_service_outages`。

Before release, follow [PRIVACY.md](PRIVACY.md). The privacy gate scans current candidates and historical blobs, checks generic commit identities and avoids printing matched values. Names and research context still require manual review.

## Upstream and license

Official Biomni: [snap-stanford/Biomni](https://github.com/snap-stanford/Biomni)

Pinned upstream revision: `400c1f366b96a35ca253e13c9b06c5076af41d65`.

Apache-2.0; see `LICENSE` and `NOTICE`. This repository provides a direct-tool integration layer and is not an official upstream release.
