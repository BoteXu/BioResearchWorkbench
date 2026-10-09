# 项目起源、第三方归属与我们的工作

## 最初底层：Biomni

**BioResearchWorkbench 最初的底层建立在 [Biomni](https://github.com/snap-stanford/Biomni) 上。** 最早的实现复用了 Biomni 的工具目录、工具描述、部分生物医学工具和数据库查询代码，并将它们接入宿主模型可直接调用的工具桥。项目随后扩展了研究流程、QC、统计咨询、软件接口、文献与论文审查等功能，因此采用独立名称。

上游固定来源为 `snap-stanford/Biomni`，提交 `400c1f366b96a35ca253e13c9b06c5076af41d65`。安装器从官方仓库获取该版本，保留上游源文件、许可证与已有归属信息；本发行包本身只含桥接和扩展源文件，不把整个 Biomni 源码或数据湖重新打包。

本项目不是 Biomni 官方发行版，没有包含完整 Biomni 推理智能体、Biomni-R0、E1 环境或数据湖。宿主客户端的模型负责推理，本工作台提供工具与研究流程。使用或引用上游方法时，应按对应项目要求引用其原始工作；工作台名称不替代上游归属。

## 哪些来自第三方，哪些由我们组合与适配

| 部分 | 原始来源及归属 | 我们的工作 | 明确不作为本项目原创的内容 |
|---|---|---|---|
| 最初工具底层 | [Biomni](https://github.com/snap-stanford/Biomni)，上游 Apache-2.0 许可证 | 直接调用桥、目录发现、运行状态和来源回执；新增受控查询适配 | Biomni 原有工具、目录描述、上游方法和品牌 |
| MCP 通信与网络 | [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)、[Requests](https://requests.readthedocs.io/) 等 | MCP 注册、客户端配置、参数检查与隐私路由 | 协议、SDK、HTTP 库和模型本身 |
| 数据与统计基础库 | NumPy、pandas、SciPy、statsmodels、scikit-learn | 输入合同、设计检查、固定适配、结果保存与验收 | 基础数值、统计和机器学习算法 |
| 转录组与单细胞 | [PyDESeq2](https://github.com/owkin/PyDESeq2)、[Scanpy](https://scanpy.readthedocs.io/)、[AnnData](https://anndata.readthedocs.io/)、igraph、leidenalg | QC 门禁、样本/独立单位检查、对比配置、受限执行和报告 | 差异表达模型、单细胞算法、Leiden 聚类 |
| R 差异分析后端 | [limma](https://bioconductor.org/packages/limma/)、[edgeR](https://bioconductor.org/packages/edgeR/) | 复用安装者已有 R 环境，通过固定脚本交换数据和检查回执 | limma、edgeR 的统计方法与软件；其许可证独立适用 |
| 新增服务器推断 | [coloc](https://github.com/chr1swallace/coloc)、[susieR](https://github.com/stephenslab/susieR)、[decoupleR](https://github.com/saezlab/decoupleR)、[metafor](https://github.com/wviechtb/metafor) | 输入与 LD/网络/协方差 QC、固定任务程序、诊断和来源回执 | 共定位、精细定位、活性推断和荟萃模型；算法归原作者 |
| OCR 与原生文档 | [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF)、[Tesseract](https://github.com/tesseract-ocr/tesseract)、Microsoft Word 与 Zotero 原生模板 | 服务器 OCR 任务、页位置检查、固定原生批注/修订/渲染接口 | OCR 引擎、Office 软件、引用刷新插件；这些软件未随包提供 |
| 通路、网络与绘图 | [GSEApy](https://gseapy.readthedocs.io/)、NetworkX、Matplotlib、[Cytoscape](https://cytoscape.org/) | 标识/背景检查、网络导入、结果组织、绘图适配与审查 | 富集方法、图算法、绘图库和 Cytoscape GUI |
| 分子与对接 | [RDKit](https://www.rdkit.org/)、[Meeko](https://github.com/forlilab/Meeko)、Gemmi、[AutoDock Vina](https://github.com/ccsb-scripps/AutoDock-Vina)、[Open Babel](https://openbabel.org/) | 输入与资源 QC、固定软件调用、姿势汇总、对照和回执检查 | 化学算法、配体准备算法、对接评分/搜索引擎和格式转换软件 |
| 文档与参考文献 | [pypdf](https://pypdf.readthedocs.io/)、Beautiful Soup、[Zotero](https://www.zotero.org/) | 有界文档读取、局部库访问、写入计划、字段保护和审计 | PDF 解析器、Zotero 软件、引用生态与 Word 插件 |
| 公共文献与数据库 | NCBI、Europe PMC、Crossref、UniProt、Ensembl、Reactome、STRING 等原提供方 | 查询适配、来源快照、标识检查和证据记录 | 数据库内容、知识库注释、论文正文和数据库方法 |
| 客户端及可选 specialist skills | 安装者已有的模型客户端、文档/绘图/结构查看/SSH skill 或插件 | 按可用能力选择调用，编写可移植研究工作流 | 外部模型、商业插件，以及未随包分发的第三方 skill 源码 |
| 本项目新增代码与说明 | 工作台维护者 | 安装与兼容、隐私门禁、QC 和任务/结果检查、软件接口、私有索引、论文审计适配、15 套工作流说明与工程测试 | 不将通用科研方法、上游算法或第三方能力包装成自研模型 |

这些部分的作用主要是**拿现有工具搭建可追溯的研究工作台**。即使由我们编写了一个调用函数，也不代表其调用的算法由我们发明；即使接口检查通过，也不代表第三方软件在所有设备、模型或真实数据上已经验证。

## 许可证与分发边界

- 本仓库新增桥接代码和工作流按 Apache-2.0 发布，见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。它不重新许可上游依赖、外部服务的数据或第三方文档。
- Biomni 固定版本的原许可证见 [上游 LICENSE](https://github.com/snap-stanford/Biomni/blob/400c1f366b96a35ca253e13c9b06c5076af41d65/LICENSE)。安装后保留在获取的上游源码中。
- Python 锁文件记录依赖版本，安装器从包分发渠道分别获取依赖，并保留包自身的许可证元数据。可选 R/外部软件由用户配置；Vina 仅在明确选择时从固定官方发行获取。
- 每项依赖的许可证与引用要求以对应版本的原始文件为准。本表是来源和使用关系说明，不是完整的许可证合规认证或许可证文本替代品。
- 外部数据库、全文、模型服务及商业插件具有自己的访问、引用和再分发条件；能查询不等于能公开重发其内容。
- 可选第三方 skill 的代码、模板、字体和插件没有被批量复制入本包。随包 15 套说明是本项目编写的组合工作流，不宣称通用科研方法原创。

机器可读的组件使用关系见 [third_party_components.json](third_party_components.json)。其 `use` 字段区分获取的底层源码、安装依赖、可选外部软件、外部服务和宿主能力；锁文件仍是完整版本清单的依据。

## Bridge 2.10 attribution
Original additions: source-scoped code/numeric/clinical contracts, located review ledgers, fixed code/workflow/clinical adapters, private version bindings and acceptance fixtures. Existing Python/Jupyter, Nextflow, Snakemake, pydicom, survival, cmprsk, uv, renv and CodeQL retain upstream authorship/licenses. No clinical guideline or bias grading rules are redistributed. Official RxNorm/DailyMed services retain NLM provenance and regional scope.

## CADD source review and original audits in 2.12

The gap review considered [makabaka007x/cadd-skill at a fixed commit](https://github.com/makabaka007x/cadd-skill/tree/49f09d57b9c5ace7f404b4eeb6a870b571c8efaf). No explicit redistribution license was found in that snapshot, so its skills, scripts, templates and binaries are not copied or installed. New `cadd_ext.py` and workflow notes are independently authored bounded audits and routing instructions. Official GROMACS, PLUMED, Amber, HADDOCK and AlphaFold documentation informs their contracts. Scientific methods, software, databases and weights retain original authorship/licenses. These additions do not implement MD, docking search, advanced AF metrics or protein design. See [CADD_SKILL_REVIEW.md](CADD_SKILL_REVIEW.md) and [cadd_sources.json](cadd_sources.json).

## Optional MCP processes in 2.11
Serena (the installed 1.7.0 distribution), Context7, MotherDuck MCP/DuckDB, Qdrant/FastEmbed, Playwright and Docker MCP Gateway are separately installed external components. Their original authors and exact-version licenses remain applicable. This package supplies original scoped adapters, configuration generation and acceptance checks. It does not redistribute or relicense upstream executables, model weights or container images. The Docker public-fetch candidate comes from the MCP reference-server project and Docker image catalog. The compact embedding model originates from sentence-transformers and Qdrant ONNX packaging; its fixed revision and hashes are in mcp_embedding_model.json. Consult a new revision's actual license before upgrading.

## Molecular dry-lab and engineering additions in 2.13

The shared MCP transport in package 2.13.1 is original integration code built on the separately installed MCP Python SDK/FastMCP, Starlette, Uvicorn and psutil, plus operating-system locking primitives. Their existing authorship and licenses remain unchanged. No private deployment configuration or runtime receipt is redistributed.

The molecular routing/audits, upgrade manager, validation lifecycle, generated catalog, server review helpers and question interface are original integration code. IntAct, Complex Portal, Cellosaurus, nf-core methods, DESeq2, pasilla, R datasets/stats and all prior upstream algorithms retain their original authorship and independent terms. External candidate metadata records fixed commits and limited review scope in molecular_resources.json; no candidate skill code, installation script, weights or provider dataset is redistributed. A repository license is not a license for every individual skill or upstream data source.
