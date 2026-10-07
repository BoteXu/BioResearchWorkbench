# 分子生物学干实验工作台

BioResearchWorkbench 最初基于 Biomni，现在提供可复用的工具衔接、QC、证据审查和结果交付。宿主模型负责推理。上游算法、数据库、MCP 和技能保留各自归属，见 [ORIGINS.md](ORIGINS.md)。

## 使用入口与完成边界

Bridge 2.13 新增 `molecular_biology` 类别，共 13 个函数。`guide_molecular_drylab` 将问题转为六个阶段：问题与估计目标、输入/参考/独立单位 QC、方法与环境审查、明确服务器派发、真实回执与结果 QC、证据和解释。它返回当前工具目录与运行状态，生成计划，不运行分析。方法候选不表示已经安装或封装成可执行后端。

大计算、大下载和索引继续使用已有服务器；本地进行公开检索、命令准备、回执追踪、返回结果审查和轻量交付。可选本地分析版继续保留，其已有能力和资源边界见 [LOCAL_ANALYSIS.md](LOCAL_ANALYSIS.md)。本文中的新审查工具都能在核心版运行，不增加科学计算依赖。

| 干实验方向 | 主要问题与 QC | 可用衔接与状态 |
|---|---|---|
| 基因/转录本/蛋白注释 | 物种、组装、发布版、命名空间、一对多映射 | 复用 Ensembl、UniProt、InterPro 与标识审查 |
| Bulk/单细胞/空间表达 | 矩阵来源、样本顺序、供体、细胞构成、设计与批次 | 复用已有分析与 QC；重计算在服务器 |
| 可变剪接/异构体/长读长 | 事件与转录本估计目标、覆盖、链方向、参考、测试全集 | 新增返回结果审查；rMATS、LeafCutter、DEXSeq、DRIMSeq、IsoQuant、FLAIR、SQANTI3 为服务器候选，未新增执行器 |
| ATAC/ChIP/CUT&Tag/甲基化 | 背景与对照、片段/峰 QC、重复一致性、坐标与峰到基因映射 | 新增调控证据审查；复用 ENCODE/JASPAR；方法执行需要服务器配置 |
| CLIP/RNA 调控/翻译 | RNA 结合与剪接后果、转录本映射、Ribo-seq 周期性/P-site、配对 RNA 与交互模型 | 新增证据审查；不把结合或核糖体占据直接升级成调控或翻译效率 |
| 调控网络/通路/跨组学 | 调控集物种、观察单位、混杂、重采样、共享背景与上下文 | 复用 decoupleR、通路/PPI/共定位与稳定性审查；Arboreto/SCENIC 仅候选 |
| 蛋白组/PTM/功能注释 | 肽到蛋白、异构体、序列/残基绑定、GO 否定与证据代码、PTM 位点与功能 | 新增注释审查；复用 PRIDE、QuickGO、HPA、结构工具 |
| 分子互作/复合体 | 实验与预测、物理与功能关系、复合体展开、片段/突变、物种 | 新增 IntAct/Complex Portal 官方查询与互作审查；复用 STRING/Cytoscape |
| 分子扰动/功能筛选 | 真正生物学重复、匹配对照、靶点特异性、混杂、效应与区间 | 新增返回结果审查，先做统计咨询；不设计编辑试剂或运行筛选引擎 |
| 结构/对接/动力学 | 链和残基、模型置信度、准备状态、对照、评分域、独立运行 | 复用 v2.12 CADD 与服务器流程，不复制第三方引擎/权重 |
| 机制与证据链 | 每条边的来源、身份、方向、模型、时间、阴性、冲突与替代解释 | 新增机制图审查；复用论文主张核验、证据矩阵和项目谱系 |

## 之前各模块的协同

文献检索与全文定位、统计指导、代码/Notebook 审查、组学、通路/PPI、医学证据、服务器调度、Zotero/私有文献库、科研图与论文协作继续保留。分子工作台通过已有工具路线衔接这些模块，见 [SKILLS.md](SKILLS.md)、[WORKBENCH.md](WORKBENCH.md)、[CODE_WORKFLOWS.md](CODE_WORKFLOWS.md)、[STATISTICS.md](STATISTICS.md)、[ACADEMIC_WORKFLOWS.md](ACADEMIC_WORKFLOWS.md)。临床推断仍有自身设计和证据限制；表达、网络或结构预测不能自动成为治疗证据。

交付记录分开标注计划、已派发、已运行、文件完整性、QC 一致性和科学解释。正式推断先使用 `statistics.guide_study_statistics` 定义估计目标、独立单位、端点、重复、协变量和缺失。已有项目阶段和分析 QC 绑定仍以具体输入/设计/参考版本为准，不将一个绿色摘要复制为其他分析的通行证。

## 官方只读查询

三个新增查询都要求 `approved_public_data=true`，含义是用户明确批准此次公开标识外发，不是程序自行代填的许可。只接受固定标识和固定官方端点；原始响应通过现有 HTTP 来源追踪进入私有回执。

- `query_intact_interactions(uniprot_id, taxon_id, approved_public_data, page=0, page_size=10)`：按 UniProt 标识只读一页，最多 50 条；在这一页内筛选至少一个参与者属于指定物种的记录，保留跨物种配对。`total_records_before_species_filter` 是筛选前该标识的总量，不能当作指定物种总量；分页范围及 `candidate_coverage_complete` 明示覆盖情况。空页或筛选后为空不能证明没有互作。保留原始检测方法、发表来源、阴性/展开信息，亚型、加工片段、突变和缺项必须另行定位。
- `query_complex_record(complex_id, approved_public_data)`：核对 CPX 主标识，保留参与者、计量关系、物种和证据。复合体成员不等于所有成员两两直接结合。
- `query_cell_line(accession, approved_public_data)`：只读一条 Cellosaurus 的身份、物种、版本和 caution/problematic 相关元数据。合并/次级标识不静默接受；参考记录不能证明实际细胞库存已认证。

代码许可证不覆盖源数据使用权。遵守 IntAct/Complex Portal 的 EMBL-EBI 条款和 Cellosaurus 的自身条款，不打包或转售抓取数据。

## 摘要审查契约

五个领域审查工具和机制图工具均离线运行，输入为有界 JSON，不读取全库或自动找文件。`success=true` 表示完成检查；`qc_gate_pass` 只表示所给摘要与本契约一致，`scientific_validity` 始终为 `not_established`。

`context` 必须含非空 `species`、`model`、`biological_unit`、`contrast`、`source_version`。剪接/调控审查还需 `assembly`。记录必须有唯一 `id`、对应上下文、`assay`、`source_location`、原始摘要 `source_sha256`、`source_reviewed=true` 以及不重复的 `independent_units`。声明需要宿主独立核验；工具不会仅凭哈希证明引文成立。

- 剪接：`analysis_level` 为 `exon_event` / `transcript_usage` / `transcript_abundance` / `transcript_structure`；明确 `gene_id`、`feature_id`、`annotation_version`、`method_version`、`library_type`，提供 `mapping_qc_pass`、`coverage_qc_pass`、`design_qc_pass`。`evidence_type` 区分基因表达、junction 计数、转录本估计、全长结构。推断结果需 `effect`、`effect_unit`、`adjusted_pvalue` 和 `tested_universe_recorded`；delta-PSI/usage 用 fraction，不能混入百分数。RNA 变化不能自动证明蛋白变化。
- 调控：`evidence_type` 区分 motif、accessibility、coexpression、chip_binding、clip_binding、chromatin_contact、perturbation、methylation_association、ribosome_occupancy。提供 `regulator_id`、`target_id`、`claim`、`direction`、映射/背景/重复 QC。只有符合特异扰动与对照的摘要才能支持条件限定的调控主张；占据到翻译效率还需要配对 RNA 和交互模型。
- 蛋白：`annotation_type`、`protein_id`、`isoform_id`、`annotation_id`、`annotation_version`、`sequence_sha256`、残基映射；区分 experimental、computational、homology、curated_inference。GO 保留 `evidence_code` 和 `qualifiers`；域/PTM 用一基闭区间；PTM 提供位点概率及任务预先声明的判据，不设通用阈值。
- 互作：明确 `participant_a/b`、`evidence_type`、`claim`、`expansion`、`negative`、`direction`、参与者映射和对照。pairwise direct binding 要求相应检测、无复合体展开并完成检查；共沉淀、共表达、预测、STRING 功能关系与复合体成员不能自动变成直接结合或有符号调控。
- 扰动：`target_id`、`endpoint`、`method_version`、设计/对照/特异性/混杂/测试全集声明、`effect`、`effect_unit`、`ci_low/high`、`ci_method`、`adjusted_pvalue`、`direction`。技术重复不能充当独立单位；条件特异效应不自动外推成一般因果关系。
- 机制图：节点含 `identifier`、`species`、`mapping_reviewed`；边含 `source`、`target`、`claim`、`direction`、`evidence_ids`。证据 `kind` 为 interaction / regulatory / perturbation，并遵循相应记录契约。核对边与参与者/目标/端点、声明方向、来源和冲突；单条边或链条均不能证明整体机制或传递性因果。

## 外部 skill/MCP 的增量筛选

`inspect_molecular_resources` 返回 [molecular_resources.json](molecular_resources.json) 中固定提交的候选、审查范围、许可证和增量。`plan_molecular_extension` 只生成包含公开标识哈希的私有接入审查计划，不安装、不注册、不联网。第三方入口说明属于审查材料，不是自动执行指令。

检索覆盖 BioMCP、BioContextAI Knowledgebase、ToolUniverse、K-Dense scientific-agent-skills 和已经归档的 bioSkills。现有 Ensembl、UniProt、InterPro、表达/文献/结构/通路客户端继续复用。BioMCP 的跨实体检索可作为候选；BioContextAI 与大量现有客户端重叠；ToolUniverse 需逐个检查选中接口；K-Dense 的版本兼容记录可供方法选择；归档 bioSkills 仅作覆盖参考。未复制第三方 skill、安装脚本或分析代码。

外部服务的具体功能仍需所选源代码、依赖锁、数据条款、外发范围和真实运行验收。它们不因出现在目录中而成为已经连接的 MCP。
