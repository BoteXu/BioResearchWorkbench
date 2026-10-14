# 组学标准流程与条件拓展

这是 BioResearchWorkbench 原创的流程、QC 和结果契约，最初工具基础来自 Biomni。第三方算法、文档和数据库保留原归属。本页从 `omics_workflows.json` 自动生成。

版本 2.15.0：28 条流程、22 类拓展、81 条细分分析路线，细分路线与流程有 285 个适用关联。路线和关联数量不是新增算法或已经验收的执行后端。

## 调用与状态

- `omics_workflows.inspect_omics_workflows(workflow="", family="", detail=false, limit=40)`：离线发现目录；完整细节包括标准步骤、QC、输出角色和官方参考。
- `omics_workflows.inspect_omics_extensions(workflow="", parent="", search="", detail=false, offset=0, limit=12)`：按检测技术、父类和问题检索细分路线；最多 20 条一页，按 `next_offset` 继续。
- `omics_workflows.plan_omics_workflow(workflow, context, design, input_manifest, extensions=null, analysis_requests=null)`：只生成绑定版本的计划，拓展必须主动选择；推荐选具体路线。
- `omics_workflows.audit_omics_readiness(plan, checks, statistical_receipt=null, backend_receipt=null)`：审查有定位来源的 QC、统计咨询和已有服务器验收摘要。
- `omics_workflows.audit_omics_result_bundle(plan, result_manifest, execution_receipt, checks, statistical_receipt=null, backend_receipt=null)`：审查必需结果和真实回执的声明，不读取原始矩阵或观察服务器进程。

新接口均仅用 Python 标准库，不创建分析环境、下载数据、调用公共数据库、连接服务器或运行算法。计算经用户已有 SSH/调度流程明确派发。共享服务串行运行，本地科研禁令优先于安装 profile。原始 RNA 私有附加包保持独立，未纳入本目录或公开包。

目录可用、契约检查完成、源文件哈希、QC 摘要一致、引擎真实完成和科学有效性分别报告。`summary_consistent=true` 只是提交摘要无阻断问题，`analysis_authorized=false` 与 `scientific_validity_established=false` 始终保留。

## 输入契约

单次工具输入为有限 JSON，最多 400 KB；网关自身还有请求上限。仅选定元数据/返回摘要，不能传入大矩阵、完整质谱、全库或患者表。无隐式目录扫描或联网。

| 对象 | 必需内容 |
|---|---|
| `context` | `species`, `model`, `assay`, `reference`, `reference_version`, `feature_namespace`。序列/基因组流程另需 `assembly`, `annotation_version`；每条流程的 `required_context_fields` 明示范围。质谱/微生物参考注明数据库。 |
| `design` | `estimand`, `biological_unit`, `unit_type`, `contrast`, `missingness_plan`, `inference_mode`, `batch_confounded`, `repeated_measures`, `covariates`, `units`。 |
| `unit_type` | donor / animal / independent_culture / biological_sample / pedigree / study。来源摘要还须独立核验，不能通过改名把细胞或技术重复变为生物学重复。 |
| `units` | 至多 1000 条唯一 `id` 与 `group`。单位是独立单位清单，重复时间点/切片映射另用 `dependence_structure` 说明；不是每个观测一行。 |
| `input_manifest` | 1–100 条唯一 `id`, 工作流支持的 `kind`, 小写 `sha256`, `source_location`。哈希是调用者声明；与真实文件独立核验。 |
| `extensions` | 最多 12 个无重复兼容 ID；省略即不添加。每个前提在 `design.capabilities` 中提供 `available=true`, `source_location`, `source_sha256`。 |

## 细分分析的选择与验收

`analysis_requests` 每项恰好含 `id`, `method`, `decisions`, `null_model`, `multiplicity_family`, `sensitivity_plan`。`id` 由细分检索返回；`method` 选该路线的明确候选。`decisions` 必须逐一填写该路线全部 `decision_fields`，不能用泛化模板省略背景全集、比较单位、参考版本、尺度或验证划分等关键决定。其余三项为非空有界文字；代码只核对结构，宿主须审查内容是否成立。

每条细分路线生成输入、设计、诊断、敏感性四项专用 QC 和明确输出角色。前提证据还要求 `reviewed_by_host=true`；缺少来源、诊断或稳健性结果会阻断摘要验收。已有父类入口保持兼容，但同一计划不能同时选父类及其子路线；父类加子路线合计最多 12 项，较大研究拆成有版本谱系的阶段计划。

真实服务器后端摘要除原有字段外，`analysis_methods[id]` 需给出 `status=runtime_verified`, 精确 `method`, 该请求的 `request_sha256`、定位来源及宿主审核；`method_versions` 必须包含所选方法的固定版本。改方法、参数决定或敏感性计划会改变请求/计划哈希，旧验收不能沿用。通用后端曾跑通不能代替具体方法验收。

正式推断每声明组至少两个独立单位只是结构底线，不能当作统计功效或方法适用性验收。完全混杂阻断推断；需要预先说明重复测量结构、协变量和缺失处理。描述性模式不要求推断咨询，但仍要求 QC、方法和服务器来源；它不交付差异显著性结果，需提供 `descriptive_results`。需要推断拓展时重新建立 inferential 计划。

## QC 与精确绑定

计划含 `plan_sha256`、`catalog_sha256`、`context_sha256`、`design_sha256`、`inputs_sha256`。每条 QC、统计/后端摘要、输出记录和运行回执须携带完全一致的这些字段。目录、输入、设计或拓展改变必须重新生成和实质审核计划；改哈希不能代替审核。

每个 `checks` 对象含唯一 `id`（必须来自 `required_qc`）、`status=passed/failed/unknown`、绑定、`source_location`、`source_sha256` 和 `reviewed_by_host=true`。缺失、unknown、failed 或 unreviewed 均阻断；没有用 not-applicable 绕过必需项的入口。不同起始数据层应定位上游 QC 回执，无法恢复的原始 QC 保留缺口，不能凭空补成 passed。

有数值的 QC 可附 `measurements`，每项含唯一 `id`, `definition`, `unit`, `observation_scope`, `threshold_basis`, 数值 `value`, `operator=ge/le/between` 和 `bound`。between 用两个有序数值；拒绝布尔值、数字字符串和非有限数。显式比较会捕获“状态 passed 但数值未达声明阈值”。FRiP、TSS、线粒体比例、覆盖、CV、FDR 和位点定位都不统一套固定阈值；按协议、定义、单位及问题预先说明判据。

inferential 计划的 `statistical_receipt` 包含绑定、定位/哈希、`reviewed_by_host=true`, `status=reviewed` 及相同 `estimand`/`biological_unit`。这是从实际 `statistics.guide_study_statistics` 及宿主审核形成的私有摘要，不自动伪造咨询。后端摘要含同样绑定/来源、`status=runtime_verified`, `route=existing_server`, 非空 `method_versions`；latest/dev/main 等浮动标记不算固定版本。还须独立检查原始服务器测试与方法适用性。

## 结果契约

输出 manifest 至多 200 条，含唯一 `id`, 唯一 `role`, 非空文件的正整数 `bytes`, `sha256`, `source_location` 和全部绑定。同一角色需要分片时先由服务器生成分片索引摘要，用索引承担该角色，保留原始文件清单。角色存在不表示表内内容或图形已经正确。

运行回执需要相同绑定/来源/宿主审核、`state=COMPLETED`、整数 `exit_code=0` 和非空 `scheduler_receipt_id`/`runner_receipt_id`。它是对实际回执的声明；本工具不连接调度器，不自动重试 unknown，也不自称已哈希本地文件。接着用现有 `workflow.verify_remote_results` 在明确范围核验文件，再做独立科学解释。

## 通用 QC

- `input_integrity`：选定输入的实际哈希、尺度、内容类型及样本顺序
- `reference_context`：物种、参考/数据库、发布版本和特征标识映射
- `independent_units`：独立生物学单位、嵌套/技术重复及对比方向
- `design_estimability`：估计目标、秩/混杂、配对、协变量及缺失处理
- `normalization_review`：测量尺度适配归一化、过滤与批次处理
- `resource_route`：既有服务器环境、实际资源预算与调度路线

## 流程概览

| ID | 方向 | 输入类型 | 可选拓展 |
|---|---|---|---|
| `bulk_rna` | Bulk RNA-seq | raw_reads, raw_counts | pathway, ppi, coexpression, deconvolution, splicing, timecourse, prediction, multiomics, regulatory, composition |
| `scrna` | 单细胞/单核 RNA-seq | raw_reads, raw_counts | pathway, ppi, trajectory, velocity, communication, regulatory, composition, repertoire, multiomics, timecourse, prediction, sv_cnv |
| `spatial_rna` | 空间转录组 | raw_counts, segmented_features | pathway, deconvolution, communication, regulatory, multiomics, ppi, timecourse, prediction, composition, spatial_context |
| `small_rna` | small RNA / miRNA | raw_reads, raw_counts | pathway, ppi, multiomics |
| `long_read_rna` | 长读长 RNA 与异构体 | raw_reads, aligned_reads, transcript_models | splicing, pathway, multiomics, ppi, regulatory, timecourse, prediction, te |
| `splicing` | 可变剪接 / DTU | junction_counts, transcript_counts | pathway, ppi, multiomics, splicing |
| `riboseq` | Ribo-seq / 翻译组 | raw_reads, aligned_reads, footprint_counts | te, pathway, timecourse |
| `clipseq` | CLIP / RNA 结合 | raw_reads, aligned_reads, peak_counts | splicing, regulatory, multiomics |
| `expression_array` | 表达芯片 | raw_intensity, normalized_expression | pathway, ppi, coexpression, deconvolution, prediction, regulatory, timecourse, multiomics |
| `bulk_atac` | ATAC-seq | raw_reads, fragments, peak_counts | regulatory, chromatin_links, pathway, multiomics |
| `scatac` | 单细胞 ATAC-seq | fragments, peak_counts | regulatory, chromatin_links, multiomics, trajectory |
| `chipseq` | ChIP-seq | raw_reads, aligned_reads, peak_counts | regulatory, chromatin_links, pathway, multiomics |
| `cutandrun` | CUT&RUN / CUT&Tag | raw_reads, fragments, peak_counts | regulatory, chromatin_links, pathway, multiomics |
| `methylseq` | WGBS / RRBS / EM-seq | raw_reads, methylation_counts | pathway, regulatory, multiomics, chromatin_links |
| `methylation_array` | 甲基化芯片 | raw_intensity, methylation_beta, methylation_m | pathway, regulatory, multiomics, prediction, chromatin_links |
| `hic` | Hi-C / 三维基因组 | raw_reads, contact_pairs, contact_matrix | chromatin_links, regulatory, multiomics |
| `germline` | 胚系 WGS / WES / panel | raw_reads, aligned_reads, variants | sv_cnv, genetic_causality, prediction |
| `somatic` | 体细胞 WGS / WES / panel | raw_reads, aligned_reads, variants | sv_cnv, pathway |
| `gwas_qtl` | GWAS / eQTL / sQTL | genotypes, summary_statistics | genetic_causality, pathway, prediction, multiomics |
| `proteomics` | DDA / DIA / TMT 蛋白组 | mass_spectra, peptide_abundance, protein_abundance | pathway, ppi, coexpression, multiomics, prediction, timecourse, protein_activity |
| `phosphoproteomics` | 磷酸化 / PTM 组 | site_abundance, mass_spectra | protein_activity, pathway, ppi, multiomics, prediction |
| `metabolomics` | 靶向 / 非靶向代谢组 | mass_spectra, feature_abundance, concentration | pathway, multiomics, prediction, timecourse, lipid_classes |
| `lipidomics` | 脂质组 | mass_spectra, feature_abundance, concentration | lipid_classes, pathway, multiomics, timecourse, prediction |
| `amplicon` | 16S / ITS 扩增子 | raw_reads, feature_counts | composition, timecourse, multiomics |
| `metagenomics` | 宏基因组概况 | raw_reads, taxonomic_abundance | composition, functional_profile, multiomics |
| `singlecell_multiome` | 单细胞多模态 / CITE / RNA+ATAC | modality_matrices | regulatory, chromatin_links, trajectory, communication, multiomics, pathway, ppi, velocity, timecourse, prediction, composition, sv_cnv, repertoire |
| `multiomics` | Bulk 多组学整合 | modality_matrices | pathway, ppi, prediction, genetic_causality, coexpression, deconvolution, regulatory, timecourse, chromatin_links, te, protein_activity, multiomics |
| `perturbation` | 扰动组学 / 功能筛选结果 | feature_counts, raw_counts, effect_summaries | pathway, ppi, regulatory, multiomics |

## 标准流程、方法 QC 与结果

### Bulk RNA-seq (`bulk_rna`)

**输入**：FASTQ 或原始基因计数与样本表

**方法 QC**：

- `bulk_rna__1`：读长、方向、适配器及污染摘要
- `bulk_rna__2`：比对/定量、rRNA 和基因体偏倚
- `bulk_rna__3`：计数类型、文库量与样本顺序
- `bulk_rna__4`：离群样本、批次及可估计设计

**标准步骤**：

1. 原始输入 QC 和参考锁定
2. 定量/低表达过滤及方法适配的归一化
3. 预先定义对比的效应、区间和多重比较
4. 诊断与可重复报告

**服务器方法候选**：nf-core/rnaseq；DESeq2；edgeR；limma-voom。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`quantification`、`normalization`、`differential`、`diagnostics`。

**解释边界**：TPM/FPKM 不冒充原始计数；批次调整不可移除目标信号。

**官方参考**：[rnaseq](https://nf-co.re/rnaseq/3.27.0/)。

### 单细胞/单核 RNA-seq (`scrna`)

**输入**：计数、细胞元数据、供体和样本映射；可有 FASTQ

**方法 QC**：

- `scrna__1`：计数层、空液滴/ambient RNA
- `scrna__2`：每样本线粒体/复杂度和 doublet 判定依据
- `scrna__3`：供体独立性与每组覆盖
- `scrna__4`：整合前后保留生物信号及细胞标签依据

**标准步骤**：

1. 每样本 QC、归一化及可视化
2. 聚类、细胞注释及标记审查
3. 供体水平 pseudobulk/设计适配差异状态
4. 细胞组成、敏感性与报告

**服务器方法候选**：nf-core/scrnaseq；Seurat；Scanpy；muscat。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`cell_qc`、`annotation`、`donor_design`、`differential`、`diagnostics`。

**解释边界**：细胞数不等于生物学 n；整合表达不默认用于差异检验。

**官方参考**：[scrnaseq](https://nf-co.re/scrnaseq/4.2.0/)、[osca](https://bioconductor.org/books/release/OSCA/)。

### 空间转录组 (`spatial_rna`)

**输入**：计数、坐标、组织图像/分割摘要、切片/供体关系

**方法 QC**：

- `spatial_rna__1`：坐标、像素/长度单位与图像配准
- `spatial_rna__2`：spot/bin/cell 分割及组织区域 QC
- `spatial_rna__3`：供体-切片-区域嵌套
- `spatial_rna__4`：空间邻接及局部覆盖与测量尺度

**标准步骤**：

1. 平台适配 QC、归一化与注释
2. 空间域和空间变异基因
3. 嵌套/空间依赖适配比较
4. 组织学核对与诊断

**服务器方法候选**：Bioconductor spatial workflows；Squidpy；platform-compatible deconvolution。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`coordinates`、`segmentation_qc`、`annotation`、`spatial_model`、`diagnostics`。

**解释边界**：spot 或 bin 不构成独立供体；共定位不能直接证明互作。

**官方参考**：[osta](https://bioconductor.org/books/release/OSTA/)。

### small RNA / miRNA (`small_rna`)

**输入**：小 RNA 测序或原始小 RNA 计数

**方法 QC**：

- `small_rna__1`：接头与长度分布
- `small_rna__2`：rRNA/tRNA 等 RNA 类别比例
- `small_rna__3`：多重比对和 miRNA/isomiR 定义
- `small_rna__4`：参考版本与重复文库可比性

**标准步骤**：

1. 小 RNA 专用预处理
2. 类别定量和 isomiR 归属
3. 差异丰度与多重比较
4. 报告参考歧义及覆盖

**服务器方法候选**：nf-core/smrnaseq；edgeR；DESeq2。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`small_rna_quantification`、`annotation`、`differential`、`diagnostics`。

**解释边界**：预测 miRNA 靶点不是已验证调控。

**官方参考**：[smrnaseq](https://nf-co.re/smrnaseq/2.4.1/)。

### 长读长 RNA 与异构体 (`long_read_rna`)

**输入**：长读长/比对及转录本结构与样本表

**方法 QC**：

- `long_read_rna__1`：读长、全长性与链方向
- `long_read_rna__2`：内引物、嵌合及转录本支持
- `long_read_rna__3`：剪接连接和参考注释版本
- `long_read_rna__4`：定量不确定性和重复覆盖

**标准步骤**：

1. 比对和转录本重建 QC
2. 新颖结构分类与支持统计
3. 异构体定量及设计适配比较
4. 参考与不确定性报告

**服务器方法候选**：IsoQuant；FLAIR；SQANTI3。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`transcript_models`、`transcript_qc`、`quantification`、`differential`、`diagnostics`。

**解释边界**：新结构发现和差异使用为不同估计目标。

**官方参考**：[flair](https://github.com/BrooksLabUCSC/flair)。

### 可变剪接 / DTU (`splicing`)

**输入**：junction/event 计数或转录本定量及参考

**方法 QC**：

- `splicing__1`：链方向、事件/转录本定义
- `splicing__2`：junction/转录本覆盖和可比性
- `splicing__3`：参考、坐标及基因-转录本关系
- `splicing__4`：delta PSI/使用比例单位和测试全集

**标准步骤**：

1. 过滤和事件/使用估计目标锁定
2. 覆盖适配模型与设计对比
3. 多重比较和效应大小
4. 事件图与稳健性检查

**服务器方法候选**：rMATS；LeafCutter；DEXSeq；DRIMSeq。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`splicing_coverage`、`splicing_results`、`tested_universe`、`diagnostics`。

**解释边界**：基因表达变化不是剪接变化；转录本变化不是蛋白变化。

**官方参考**：[drimseq](https://bioconductor.org/packages/release/bioc/html/DRIMSeq.html)。

### Ribo-seq / 翻译组 (`riboseq`)

**输入**：核糖体 footprint、比对摘要及可选配对 RNA-seq

**方法 QC**：

- `riboseq__1`：footprint 长度及 rRNA/tRNA 污染
- `riboseq__2`：P-site 校准和三碱基周期性
- `riboseq__3`：ORF/CDS 覆盖及链方向
- `riboseq__4`：配对 RNA 状态与文库特性

**标准步骤**：

1. footprint 专用预处理和 QC
2. P-site 与 ORF/占据定量
3. 占据变化的设计适配比较
4. 周期性、覆盖和模型诊断

**服务器方法候选**：nf-core/riboseq；RiboTaper；RiboCode。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`periodicity`、`psite_calibration`、`occupancy`、`differential`、`diagnostics`。

**解释边界**：单独核糖体占据不证明翻译效率。

**官方参考**：[riboseq](https://nf-co.re/riboseq/1.2.0/)。

### CLIP / RNA 结合 (`clipseq`)

**输入**：CLIP 比对、输入/背景与重复映射

**方法 QC**：

- `clipseq__1`：交联协议、UMI/重复和链方向
- `clipseq__2`：输入/大小匹配背景与阴性对照
- `clipseq__3`：位点和重复一致性
- `clipseq__4`：转录本/基因组坐标与可比性

**标准步骤**：

1. 协议适配预处理
2. 结合位点及背景富集
3. 重复支持与位点注释
4. 覆盖及阴性证据报告

**服务器方法候选**：PureCLIP；CLIPper。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`binding_sites`、`controls`、`replicate_support`、`annotation`、`diagnostics`。

**解释边界**：RNA 结合不直接证明调控后果。

**官方参考**：[pureclip](https://github.com/skrakau/PureCLIP)。

### 表达芯片 (`expression_array`)

**输入**：原始芯片强度或已标准化矩阵及探针映射

**方法 QC**：

- `expression_array__1`：平台/探针和原始处理来源
- `expression_array__2`：背景、强度分布和离群阵列
- `expression_array__3`：探针到基因一对多映射
- `expression_array__4`：批次与设计可估计性

**标准步骤**：

1. 平台适配预处理及探针审查
2. 标准化和样本诊断
3. limma 设计适配对比
4. 版本和多重比较报告

**服务器方法候选**：platform-specific preprocessing；limma。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`probe_mapping`、`normalization`、`differential`、`diagnostics`。

**解释边界**：标准化矩阵不得再次按原始强度处理。

**官方参考**：[limma](https://bioconductor.org/packages/release/bioc/html/limma.html)。

### ATAC-seq (`bulk_atac`)

**输入**：ATAC 读段/片段及峰计数

**方法 QC**：

- `bulk_atac__1`：片段长度、线粒体和文库复杂度
- `bulk_atac__2`：TSS enrichment、FRiP 的精确定义
- `bulk_atac__3`：blacklist/重复峰及参考
- `bulk_atac__4`：一致峰全集、计数与重复设计

**标准步骤**：

1. ATAC 专用 QC/峰识别
2. 一致峰集与样本计数
3. 差异可及性与诊断
4. 峰注释和可重复报告

**服务器方法候选**：nf-core/atacseq；DiffBind；DESeq2。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`fragment_qc`、`consensus_peaks`、`peak_counts`、`differential`、`diagnostics`。

**解释边界**：可及性不等于 TF 结合或调控。

**官方参考**：[atacseq](https://nf-co.re/atacseq/2.1.2/)。

### 单细胞 ATAC-seq (`scatac`)

**输入**：片段、细胞/供体元数据与 peak-by-cell

**方法 QC**：

- `scatac__1`：每样本 TSS、片段复杂度和 doublet
- `scatac__2`：一致峰集/参考与稀疏度
- `scatac__3`：供体独立性和 pseudobulk 聚合
- `scatac__4`：RNA 整合标签及基因活性代理

**标准步骤**：

1. 细胞 QC 与 LSI 等平台适配表示
2. 注释和 donor-aware 峰比较
3. 可及性/motif 覆盖
4. 整合敏感性和报告

**服务器方法候选**：Signac；ArchR。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`cell_qc`、`consensus_peaks`、`annotation`、`donor_design`、`differential`、`diagnostics`。

**解释边界**：gene activity 为代理量，不等于 RNA 表达。

**官方参考**：[signac](https://stuartlab.org/signac/)。

### ChIP-seq (`chipseq`)

**输入**：ChIP/input 对照、峰与重复样本

**方法 QC**：

- `chipseq__1`：输入对照与目标/抗体元数据
- `chipseq__2`：复杂度、FRiP 和 signal/background
- `chipseq__3`：宽峰/窄峰选择和重复一致性
- `chipseq__4`：统一峰集、参考及定量设计

**标准步骤**：

1. 对照适配峰识别与 QC
2. 重复峰和一致计数全集
3. 差异结合/修饰及诊断
4. 注释与背景报告

**服务器方法候选**：nf-core/chipseq；DiffBind。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`controls`、`peak_qc`、`consensus_peaks`、`differential`、`diagnostics`。

**解释边界**：结合/标记占据不直接证明调控方向。

**官方参考**：[chipseq](https://nf-co.re/chipseq/2.1.0/)。

### CUT&RUN / CUT&Tag (`cutandrun`)

**输入**：协议明确的读段、阴性对照及 spike-in 信息

**方法 QC**：

- `cutandrun__1`：协议和目标对应的阴性/阳性对照
- `cutandrun__2`：低背景片段、复杂度与峰形
- `cutandrun__3`：spike-in/校准的适用性和归一化
- `cutandrun__4`：宽窄峰选择、重复一致性及参考

**标准步骤**：

1. 协议适配 QC 和峰识别
2. 重复及校准摘要
3. 峰集定量与设计适配比较
4. 注释和诊断

**服务器方法候选**：nf-core/cutandrun；SEACR；MACS-family callers when appropriate。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`controls`、`calibration`、`peak_qc`、`differential`、`diagnostics`。

**解释边界**：CUT&RUN 与 CUT&Tag 不自动共用相同参数或归一化。

**官方参考**：[cutandrun](https://nf-co.re/cutandrun/3.2.2/)。

### WGBS / RRBS / EM-seq (`methylseq`)

**输入**：转换协议明确的测序及甲基化覆盖

**方法 QC**：

- `methylseq__1`：转换效率与 M-bias/适配器
- `methylseq__2`：CpG/非 CpG 覆盖与检出范围
- `methylseq__3`：链、重复和参考坐标
- `methylseq__4`：覆盖适配模型及细胞构成混杂

**标准步骤**：

1. 协议适配比对和位点提取
2. 覆盖过滤与甲基化估计
3. DMP/DMR 和区域多重比较
4. 覆盖与模型诊断

**服务器方法候选**：nf-core/methylseq；DSS；bsseq。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`conversion_qc`、`coverage`、`methylation`、`differential_regions`、`diagnostics`。

**解释边界**：覆盖缺失不是未甲基化；区域关联不直接证明表达调控。

**官方参考**：[methylseq](https://nf-co.re/methylseq/4.2.0/)。

### 甲基化芯片 (`methylation_array`)

**输入**：IDAT 或 beta/M 值矩阵与平台探针信息

**方法 QC**：

- `methylation_array__1`：平台、检测 P 值与 bead 数
- `methylation_array__2`：交叉反应/多态性探针及样本身份
- `methylation_array__3`：beta/M 尺度、批次与细胞组成
- `methylation_array__4`：探针参考、DMP/DMR 测试全集

**标准步骤**：

1. 平台适配背景和探针 QC
2. 尺度适配模型与可视化
3. DMP/DMR 比较
4. 敏感性和报告

**服务器方法候选**：minfi；sesame；limma。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`probe_qc`、`normalization`、`differential_regions`、`diagnostics`。

**解释边界**：beta 与 M 值不可混用且不可双重转换。

**官方参考**：[minfi](https://bioconductor.org/packages/release/bioc/html/minfi.html)。

### Hi-C / 三维基因组 (`hic`)

**输入**：有效接触对或 contact matrix 与分辨率

**方法 QC**：

- `hic__1`：有效对、重复及 cis/trans 概况
- `hic__2`：酶切/协议、距离衰减和覆盖
- `hic__3`：参考、分箱尺度及平衡状态
- `hic__4`：独立重复和跨条件深度可比性

**标准步骤**：

1. 接触对过滤及矩阵构建
2. 分辨率适配平衡与诊断
3. compartment/TAD/loop 按问题选择
4. 独立重复比较与报告

**服务器方法候选**：nf-core/hic；cooler；HiCExplorer。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`contact_qc`、`resolution`、`contacts`、`structural_features`、`diagnostics`。

**解释边界**：结构特征尺度依赖；接触不等于调控或直接结合。

**官方参考**：[hic](https://nf-co.re/hic/2.1.0/)。

### 胚系 WGS / WES / panel (`germline`)

**输入**：测序、覆盖或已过滤变异及样本元数据

**方法 QC**：

- `germline__1`：样本身份、污染/亲缘和重复
- `germline__2`：覆盖范围、callability 与平台
- `germline__3`：参考、等位基因及变异表示
- `germline__4`：过滤、基因型和注释版本

**标准步骤**：

1. 覆盖/身份 QC 与 calling 适配
2. 变异过滤及规范化
3. 物种/组装限定注释与解释
4. 检出范围和不确定性报告

**服务器方法候选**：nf-core/sarek；GATK-style calling；VEP-style annotation。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`coverage`、`variant_qc`、`variants`、`annotation`、`diagnostics`。

**解释边界**：科研注释不构成临床诊断；未调用不代表该位点不存在变异。

**官方参考**：[sarek](https://nf-co.re/sarek/3.10.0/)。

### 体细胞 WGS / WES / panel (`somatic`)

**输入**：肿瘤/正常配对或明确无配对设计及测序

**方法 QC**：

- `somatic__1`：tumor/normal 配对和样本身份
- `somatic__2`：纯度、污染、覆盖及 panel 边界
- `somatic__3`：背景噪声、normal panel 与过滤
- `somatic__4`：参考、VAF、倍性和注释

**标准步骤**：

1. 配对/无配对方法选择
2. 体细胞调用、过滤和规范化
3. 注释及克隆/拷贝数上下文
4. 检出限和诊断

**服务器方法候选**：nf-core/sarek；assay-specific somatic calling。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`matched_design`、`coverage`、`variants`、`somatic_filter`、`annotation`、`diagnostics`。

**解释边界**：无正常样本的解释边界保留；VAF 不直接等于细胞克隆比例。

**官方参考**：[sarek](https://nf-co.re/sarek/3.10.0/)。

### GWAS / eQTL / sQTL (`gwas_qtl`)

**输入**：基因型和表型或 summary statistics 与 LD 来源

**方法 QC**：

- `gwas_qtl__1`：等位基因、效应单位与坐标/组装
- `gwas_qtl__2`：样本身份、祖源/亲缘、缺失和频率
- `gwas_qtl__3`：协变量、表型与 LD 群体匹配
- `gwas_qtl__4`：样本重叠、覆盖、有效样本量与多重比较

**标准步骤**：

1. 输入及群体结构 QC
2. 估计目标适配关联/汇总核验
3. 多重比较和位点结果
4. 方向/LD 与敏感性报告

**服务器方法候选**：PLINK-style QC；Matrix eQTL-style mapping；SuSiE/coloc when qualified。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`allele_alignment`、`association`、`ld_context`、`multiple_testing`、`diagnostics`。

**解释边界**：区域关联、基因归属、共定位和因果分别报告。

**官方参考**：[plink](https://www.cog-genomics.org/plink/2.0/)。

### DDA / DIA / TMT 蛋白组 (`proteomics`)

**输入**：原始质谱或 peptide/protein 定量及 SDRF 类设计

**方法 QC**：

- `proteomics__1`：采集方式、批次、定量和校准
- `proteomics__2`：PSM/peptide/protein FDR 与共享肽
- `proteomics__3`：缺失机制、归一化和插补敏感性
- `proteomics__4`：蛋白组/异构体归属和独立样本

**标准步骤**：

1. 采集适配鉴定/定量 QC
2. 肽到蛋白映射和尺度审查
3. 缺失机制适配差异丰度
4. FDR 层级和诊断报告

**服务器方法候选**：existing DIA-NN/MaxQuant/OpenMS workflow；MSstats；limma。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`identification_fdr`、`peptide_mapping`、`normalization`、`differential`、`diagnostics`。

**解释边界**：quantms 旧入口已归档，只作历史参考，不作为默认新部署；技术质谱重复不增加生物学 n。

**官方参考**：[msstats](https://bioconductor.org/packages/release/bioc/html/MSstats.html)、[quantms_legacy](https://nf-co.re/quantms/1.2.0/)。

### 磷酸化 / PTM 组 (`phosphoproteomics`)

**输入**：位点定量、定位概率与可选总蛋白数据

**方法 QC**：

- `phosphoproteomics__1`：富集/鉴定 FDR 与位点定位
- `phosphoproteomics__2`：序列、残基编号和异构体
- `phosphoproteomics__3`：缺失与总蛋白丰度上下文
- `phosphoproteomics__4`：批次、独立重复和位点测试全集

**标准步骤**：

1. 鉴定和定位 QC
2. 位点定量、蛋白归属及尺度
3. 位点差异和总蛋白背景
4. 多重比较及诊断

**服务器方法候选**：assay-specific PTM pipeline；MSstatsPTM；decoupleR。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`site_localization`、`site_mapping`、`differential`、`protein_context`、`diagnostics`。

**解释边界**：定位概率阈值需按方法预声明；PTM 改变不直接证明功能或激酶活性。

**官方参考**：[msstatsptm](https://bioconductor.org/packages/release/bioc/html/MSstatsPTM.html)。

### 靶向 / 非靶向代谢组 (`metabolomics`)

**输入**：LC/GC-MS 谱或峰表、blank/pooled QC 与注释

**方法 QC**：

- `metabolomics__1`：blank、pooled QC、内标与进样顺序
- `metabolomics__2`：漂移、批次和峰重复性
- `metabolomics__3`：加合物/同位素、缺失/检出限
- `metabolomics__4`：MS/MS 鉴定层级与参考版本

**标准步骤**：

1. 峰检测/对齐和仪器 QC
2. 漂移校正及适配归一化
3. 效应、区间与多重比较
4. 鉴定置信度和敏感性报告

**服务器方法候选**：existing XCMS/MS-DIAL workflow；assay-compatible feature statistics。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`instrument_qc`、`drift`、`missingness`、`feature_annotation`、`differential`、`diagnostics`。

**解释边界**：未知峰不自动映射成确定代谢物；浓度与相对峰面积必须区分。

**官方参考**：[metaboigniter](https://nf-co.re/metaboigniter/2.0.1/)。

### 脂质组 (`lipidomics`)

**输入**：脂类峰/谱、内标、加合物与鉴定层级

**方法 QC**：

- `lipidomics__1`：blank/QC/内标和批次漂移
- `lipidomics__2`：加合物与同位素去重
- `lipidomics__3`：脂类类属、链与异构体置信度
- `lipidomics__4`：检出限/缺失及浓度单位

**标准步骤**：

1. 仪器及峰 QC
2. 鉴定层级和定量
3. 脂类差异与多重比较
4. 类属及链组成解释

**服务器方法候选**：existing lipid annotation workflow；class-aware summaries。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`instrument_qc`、`lipid_annotation`、`normalization`、`differential`、`diagnostics`。

**解释边界**：总碳数不能自动升级为位置异构体。

**官方参考**：[lipidr](https://bioconductor.org/packages/release/bioc/html/lipidr.html)。

### 16S / ITS 扩增子 (`amplicon`)

**输入**：批准数据的扩增子读段/ASV 表及阴性对照

**方法 QC**：

- `amplicon__1`：引物/区域、长度和质控
- `amplicon__2`：污染阴性对照、嵌合与 ASV 覆盖
- `amplicon__3`：分类数据库版本和物种分辨率
- `amplicon__4`：组成型尺度、测序深度和独立样本

**标准步骤**：

1. 区域适配去噪与 ASV
2. 对照审查和分类注释
3. 多样性及设计适配丰度比较
4. 零值、检出范围与诊断

**服务器方法候选**：nf-core/ampliseq；DADA2；ANCOM-BC2/ALDEx2 when qualified。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`controls`、`asv_qc`、`taxonomy`、`diversity`、`differential`、`diagnostics`。

**解释边界**：区域分类分辨率保留；组成关系和群落变化不证明致病机制。

**官方参考**：[ampliseq](https://nf-co.re/ampliseq/2.18.0/)。

### 宏基因组概况 (`metagenomics`)

**输入**：批准数据的公共读段或分类/功能丰度摘要

**方法 QC**：

- `metagenomics__1`：数据范围、宿主敏感信息与污染
- `metagenomics__2`：读段 QC 和阴性对照
- `metagenomics__3`：分类数据库版本及覆盖
- `metagenomics__4`：组成型尺度和独立样本

**标准步骤**：

1. 只处理明确批准范围的分类概况
2. 分类丰度和未分类覆盖
3. 组成/设计适配比较
4. 数据库与不确定性报告

**服务器方法候选**：nf-core/taxprofiler；reviewed functional profiler。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`controls`、`profiling_qc`、`taxonomy`、`coverage`、`differential`、`diagnostics`。

**解释边界**：不提供病原体重建、增强或传播流程；计算功能概况不等于实验功能。

**官方参考**：[taxprofiler](https://nf-co.re/taxprofiler/2.0.1/)。

### 单细胞多模态 / CITE / RNA+ATAC (`singlecell_multiome`)

**输入**：RNA/ATAC/ADT 模态及同细胞/供体映射

**方法 QC**：

- `singlecell_multiome__1`：模态各自 QC、背景/阈值与稀疏度
- `singlecell_multiome__2`：条码对应、同细胞与缺失模态
- `singlecell_multiome__3`：供体/批次独立性与权重
- `singlecell_multiome__4`：整合前后保留模态特有信号

**标准步骤**：

1. 模态内处理和条码核验
2. 联合表示、注释和权重敏感性
3. 供体适配模态比较
4. 缺失模态与诊断报告

**服务器方法候选**：Seurat WNN；MOFA2；ArchR/Signac integration when qualified。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`modality_qc`、`barcode_mapping`、`integration`、`annotation`、`donor_design`、`diagnostics`。

**解释边界**：ADT 不等于全面蛋白组；联合嵌入不直接给出调控机制。

**官方参考**：[osca](https://bioconductor.org/books/release/OSCA/)、[osta](https://bioconductor.org/books/release/OSTA/)、[mofa](https://biofam.github.io/MOFA2/)。

### Bulk 多组学整合 (`multiomics`)

**输入**：已 QC 的多模态矩阵与同样本/部分重叠映射

**方法 QC**：

- `multiomics__1`：每模态原始尺度/处理及 QC
- `multiomics__2`：相同/重叠样本与缺失模态
- `multiomics__3`：独立单位、批次与整合估计目标
- `multiomics__4`：无监督/监督选择与泄漏边界

**标准步骤**：

1. 模态内 QC 和样本绑定
2. 尺度适配与缺失审查
3. 因子/关联或严格预测建模
4. 重采样稳定性及模态贡献

**服务器方法候选**：MOFA2；supervised integration with nested validation。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`modality_qc`、`sample_overlap`、`integration`、`stability`、`diagnostics`。

**解释边界**：不同队列不能假称同一样本配对；共同因子和多组学一致性不证明因果。

**官方参考**：[mofa](https://biofam.github.io/MOFA2/)。

### 扰动组学 / 功能筛选结果 (`perturbation`)

**输入**：已产生的扰动计数/效应或 Perturb-seq 数据与对照摘要

**方法 QC**：

- `perturbation__1`：输入丰度、筛选覆盖和对照
- `perturbation__2`：标签/扰动分配及 doublet
- `perturbation__3`：独立培养/供体和批次
- `perturbation__4`：靶点特异性、混杂与多重比较

**标准步骤**：

1. 既有实验输入及对照 QC
2. 任务适配聚合和效应估计
3. 特异性、阴性与多重比较
4. 设计限定的结果和报告

**服务器方法候选**：MAGeCK-style result review；donor/culture-aware models。需选择、固定版本并核验已有环境；不是新执行器。

**必需结果**：`input_qc`、`design`、`methods_versions`、`completion_receipt`、`report`、`controls`、`assignment_qc`、`differential`、`specificity`、`diagnostics`。

**解释边界**：仅审查既有结果，不设计编辑试剂；扰动效应不自动外推为普遍机制。

**官方参考**：[osca](https://bioconductor.org/books/release/OSCA/)。

## 条件拓展

### 通路富集与活性 (`pathway`)

- 前提：`identifier_mapping`、`background_universe`
- 服务器候选：ORA；ranked GSEA；decoupleR when signed network fits
- 新增结果角色：`pathway_results`、`pathway_universe`
- 解释边界：数据库版本、测试全集及方向必须保留；富集和推断分数不直接证明通路激活。

### PPI 与网络模块 (`ppi`)

- 前提：`identifier_mapping`、`interaction_evidence`
- 服务器候选：STRING functional network；IntAct experimental interactions；Cytoscape
- 新增结果角色：`ppi_edges`、`ppi_controls`
- 解释边界：功能关系、复合体成员与直接物理结合分开；网络中心性不证明因果。

### 共表达与模块稳定性 (`coexpression`)

- 前提：`replicate_design`、`sample_size_review`、`resampling_plan`
- 服务器候选：WGCNA；hdWGCNA with donor-aware design
- 新增结果角色：`coexpression_modules`、`network_stability`
- 解释边界：相关网络需独立样本与重采样；不给少量样本设通用可接受阈值。

### 细胞组成反卷积 (`deconvolution`)

- 前提：`compatible_reference`、`cell_composition_design`
- 服务器候选：MuSiC；BisqueRNA；platform-compatible spatial deconvolution
- 新增结果角色：`composition_results`、`reference_coverage`
- 解释边界：参考物种、组织、平台和细胞覆盖必须匹配；估计比例不是直接测量。

### 轨迹与状态转换 (`trajectory`)

- 前提：`trajectory_design`、`root_review`、`donor_structure`
- 服务器候选：Slingshot；Monocle3；diffusion pseudotime
- 新增结果角色：`trajectory_results`、`trajectory_sensitivity`
- 解释边界：拟时序不等于真实时间或谱系，根节点与采样结构需做敏感性检查。

### RNA velocity (`velocity`)

- 前提：`spliced_unspliced`、`kinetic_model_review`、`donor_structure`
- 服务器候选：scVelo；velocyto
- 新增结果角色：`velocity_results`、`velocity_diagnostics`
- 解释边界：层定义、动力学假设及稳健性必须核验；箭头不能自动解释成细胞命运。

### 细胞通信与邻域 (`communication`)

- 前提：`ligand_receptor_reference`、`replicate_design`、`expression_support`
- 服务器候选：LIANA；CellChat；spatial neighborhood models
- 新增结果角色：`communication_results`、`communication_controls`
- 解释边界：表达兼容关系是候选通信；不直接证明分泌、结合或功能。

### 调控网络与 motif (`regulatory`)

- 前提：`regulatory_reference`、`background_universe`、`mapping_context`
- 服务器候选：chromVAR；SCENIC；decoupleR；matched-background motif enrichment
- 新增结果角色：`regulatory_results`、`regulatory_controls`
- 解释边界：motif、可及性、结合与有方向的调控主张须分级。

### 可变剪接与异构体 (`splicing`)

- 前提：`junction_or_transcript_input`、`annotation_compatibility`
- 服务器候选：rMATS；LeafCutter；DEXSeq；DRIMSeq
- 新增结果角色：`splicing_results`、`splicing_coverage`
- 解释边界：事件、转录本使用和丰度估计目标不同；RNA 变化不自动推出蛋白变化。

### 时间序列与重复测量 (`timecourse`)

- 前提：`time_metadata`、`repeated_measure_design`
- 服务器候选：interaction models；limma splines；mixed effects when identifiable
- 新增结果角色：`timecourse_results`、`timecourse_diagnostics`
- 解释边界：相同个体各时间点不能当作独立样本；时间与批次完全混杂时阻断。

### 预测与外部验证 (`prediction`)

- 前提：`prediction_estimand`、`donor_disjoint_splits`、`validation_cohort`
- 服务器候选：nested cross-validation；locked external validation；calibration
- 新增结果角色：`prediction_results`、`leakage_audit`
- 解释边界：归一化、插补、筛特征和调参必须在训练折内；外部队列不得参与选择。

### QTL、共定位与 MR (`genetic_causality`)

- 前提：`allele_harmonization`、`ancestry_ld`、`sample_overlap_review`
- 服务器候选：SuSiE/coloc；instrument-qualified MR；sensitivity analyses
- 新增结果角色：`genetic_alignment`、`genetic_sensitivity`
- 解释边界：关联、共定位及 MR 的假设分别核验；单一路径不能自动成为机制链。

### 峰/接触到基因 (`chromatin_links`)

- 前提：`coordinate_compatibility`、`matched_expression`、`distance_background`
- 服务器候选：ABC when required inputs exist；co-accessibility；contact-supported links
- 新增结果角色：`chromatin_links`、`link_controls`
- 解释边界：最近基因与空间接触均不等于功能靶基因；保留候选歧义。

### 翻译效率 (`te`)

- 前提：`paired_rna_assay`、`p_site_calibration`、`interaction_design`
- 服务器候选：Ribo-seq by RNA-seq interaction model
- 新增结果角色：`translation_efficiency`、`te_diagnostics`
- 解释边界：核糖体占据与 RNA 丰度共同建模；不能只用比值证明翻译效率。

### 激酶/TF 活性与 PTM (`protein_activity`)

- 前提：`site_localization`、`signed_network`、`protein_abundance_context`
- 服务器候选：decoupleR；KSEA；substrate-set sensitivity
- 新增结果角色：`activity_results`、`activity_coverage`
- 解释边界：位点变化、总蛋白丰度与推断活性分别报告；缺失位点不作零值。

### 跨组学整合 (`multiomics`)

- 前提：`sample_overlap_mapping`、`modality_specific_qc`、`integration_estimand`
- 服务器候选：MOFA2；supervised integration with nested validation
- 新增结果角色：`integration_factors`、`integration_stability`
- 解释边界：同一样本/重叠样本映射与尺度明确；共同因子不建立因果。

### 组成型数据拓展 (`composition`)

- 前提：`compositional_design`、`zero_handling_plan`、`absolute_abundance_context`
- 服务器候选：ANCOM-BC2；ALDEx2；compositional sensitivity
- 新增结果角色：`composition_sensitivity`、`abundance_context`
- 解释边界：相对丰度不等于绝对丰度；零值、检出限和混杂须单独处理。

### 微生物功能概况 (`functional_profile`)

- 前提：`database_version`、`profiling_scope`
- 服务器候选：HUMAnN-style functional profiling when backend reviewed
- 新增结果角色：`functional_profile`、`functional_coverage`
- 解释边界：仅做声明的公共/批准数据功能概况，不将丰度关联推成致病或功能验证。

### 脂类与链组成 (`lipid_classes`)

- 前提：`lipid_annotation_confidence`、`adduct_review`
- 服务器候选：class enrichment；chain-length/unsaturation summaries
- 新增结果角色：`lipid_class_results`、`lipid_annotation`
- 解释边界：鉴定层级、异构体和加合物歧义保留；峰不直接等同特定分子。

### 结构变异与拷贝数 (`sv_cnv`)

- 前提：`coverage_design`、`matched_normal_or_baseline`、`ploidy_context`
- 服务器候选：assay-compatible SV/CNV callers；orthogonal review
- 新增结果角色：`sv_cnv_results`、`sv_cnv_qc`
- 解释边界：深度、倍性、纯度与检测范围影响可检出性；无调用不证明无变异。

### 免疫受体与克隆型 (`repertoire`)

- 前提：`vdj_input`、`donor_structure`、`clonotype_definition`
- 服务器候选：VDJ annotation；donor-level repertoire diversity
- 新增结果角色：`repertoire_results`、`repertoire_qc`
- 解释边界：克隆型和细胞数不能替代独立供体；受体序列不证明抗原特异性。

### 空间统计、组织结构与邻域 (`spatial_context`)

- 前提：`registered_coordinates`、`tissue_boundaries`、`donor_structure`
- 服务器候选：Squidpy；SPARK-X；SpatialDE
- 新增结果角色：`spatial_statistics`、`spatial_controls`
- 解释边界：空间邻近、表达模式、组织域与因果机制分开；spot 不是独立供者。

## 细分分析路线

| ID | 父类 | 具体问题 | 适用流程 |
|---|---|---|---|
| `ora` | `pathway` | GO/Reactome 等过度代表分析 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics |
| `preranked_gsea` | `pathway` | 全受检列表的预排序 GSEA | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics |
| `camera_sets` | `pathway` | 考虑基因间相关的集合检验 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, singlecell_multiome, multiomics |
| `gsva_scores` | `pathway` | GSVA 样本级集合分数 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, singlecell_multiome, multiomics |
| `ssgsea_scores` | `pathway` | ssGSEA 样本级排序分数 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, singlecell_multiome, multiomics |
| `leading_edge` | `pathway` | Leading-edge 与集合冗余审查 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics |
| `physical_ppi` | `ppi` | 物理 PPI 证据网络 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics |
| `ppi_modules` | `ppi` | PPI 模块与中心性稳健性 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics |
| `network_diffusion` | `ppi` | 网络传播与候选排序 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics |
| `wgcna_modules` | `coexpression` | WGCNA 模块与性状关联 | bulk_rna, expression_array, proteomics, multiomics |
| `module_preservation` | `coexpression` | 独立队列模块保留与复现 | bulk_rna, expression_array, proteomics, multiomics |
| `differential_coexpression` | `coexpression` | 差异相关与网络重连 | bulk_rna, expression_array, proteomics, multiomics |
| `bulk_deconvolution` | `deconvolution` | 参考驱动的 bulk 细胞组成估计 | bulk_rna, expression_array, multiomics |
| `spatial_deconvolution` | `deconvolution` | 空间 spot 细胞丰度估计 | spatial_rna |
| `trajectory_topology` | `trajectory` | 轨迹拓扑与根节点稳健性 | scrna, singlecell_multiome |
| `trajectory_dynamics` | `trajectory` | 沿轨迹与分支的表达变化 | scrna, singlecell_multiome |
| `kinetic_velocity` | `velocity` | RNA velocity 动力学与相图 | scrna, singlecell_multiome |
| `fate_probabilities` | `velocity` | CellRank 状态与命运概率 | scrna, singlecell_multiome |
| `lr_consensus` | `communication` | 配体受体多方法共识 | scrna, spatial_rna, singlecell_multiome |
| `lr_differential` | `communication` | 供者层级的差异通信 | scrna, spatial_rna, singlecell_multiome |
| `ligand_target_links` | `communication` | 配体到受体细胞靶基因 | scrna, spatial_rna, singlecell_multiome |
| `spatial_lr` | `communication` | 空间约束的配体受体关系 | spatial_rna |
| `tf_activity` | `regulatory` | 有符号调控靶集合的 TF 活性 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, singlecell_multiome, multiomics |
| `scenic_regulons` | `regulatory` | SCENIC 共表达与 motif 支持 regulon | scrna, singlecell_multiome |
| `motif_enrichment` | `regulatory` | 匹配背景的 motif 富集 | bulk_atac, scatac, chipseq, cutandrun, singlecell_multiome |
| `motif_deviation` | `regulatory` | chromVAR motif 可及性偏差 | bulk_atac, scatac, singlecell_multiome |
| `footprinting` | `regulatory` | ATAC footprint 与偏倚审查 | bulk_atac, scatac, singlecell_multiome |
| `enhancer_grn` | `regulatory` | 增强子—TF—基因候选网络 | singlecell_multiome, multiomics |
| `exon_usage` | `splicing` | 外显子相对使用 | bulk_rna, splicing, long_read_rna |
| `junction_events` | `splicing` | 剪接事件与 junction cluster | bulk_rna, splicing |
| `transcript_usage` | `splicing` | 差异转录本使用 DTU | bulk_rna, long_read_rna, splicing |
| `apa_usage` | `splicing` | 可变多聚腺苷酸化 APA | bulk_rna, long_read_rna, splicing |
| `isoform_switch` | `splicing` | 异构体转换及功能后果候选 | long_read_rna, bulk_rna, splicing |
| `longitudinal_effects` | `timecourse` | 纵向、交互与重复测量效应 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, singlecell_multiome, multiomics, proteomics, metabolomics, lipidomics |
| `impulse_response` | `timecourse` | 非线性时间响应 | bulk_rna, expression_array |
| `temporal_modules` | `timecourse` | 时间模式模块与稳定性 | bulk_rna, expression_array, proteomics, metabolomics |
| `nested_prediction` | `prediction` | 无泄漏嵌套验证预测 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics, metabolomics, lipidomics, germline, gwas_qtl |
| `survival_prediction` | `prediction` | 生存结局模型与动态性能 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics |
| `external_validation` | `prediction` | 冻结模型的外部验证 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics, metabolomics, lipidomics, gwas_qtl |
| `signature_matching` | `prediction` | 扰动签名相似与反向匹配 | bulk_rna, expression_array, scrna |
| `fine_mapping` | `genetic_causality` | 位点精细定位与可信集合 | gwas_qtl, germline |
| `colocalization` | `genetic_causality` | 多信号共定位 | gwas_qtl, multiomics |
| `two_sample_mr` | `genetic_causality` | 工具变量与两样本 MR 审查 | gwas_qtl, multiomics |
| `rare_variant_burden` | `genetic_causality` | 稀有变异聚合关联 | germline, gwas_qtl |
| `polygenic_score` | `genetic_causality` | 多基因评分与迁移性 | germline, gwas_qtl |
| `differential_binding` | `chromatin_links` | 差异峰、结合与可及性 | bulk_atac, scatac, chipseq, cutandrun, singlecell_multiome |
| `peak_gene_links` | `chromatin_links` | 峰—基因关联与顺式候选 | bulk_atac, scatac, singlecell_multiome, multiomics |
| `hic_loops_tads` | `chromatin_links` | Hi-C 环与 TAD 边界 | hic |
| `methylation_gene_links` | `chromatin_links` | DMR 与表达/注释整合 | methylseq, methylation_array, multiomics |
| `hic_compartments` | `chromatin_links` | A/B compartment 与切换 | hic |
| `translation_efficiency` | `te` | 配对 Ribo/RNA 翻译效率 | riboseq, multiomics |
| `uorf_translation` | `te` | uORF 与候选翻译 ORF | riboseq, long_read_rna |
| `kinase_activity` | `protein_activity` | 激酶—底物活性候选 | phosphoproteomics, multiomics |
| `ptm_adjustment` | `protein_activity` | PTM 相对总蛋白变化 | phosphoproteomics, multiomics |
| `protein_complexes` | `protein_activity` | 复合体丰度与协调变化 | proteomics, multiomics |
| `proteogenomic_links` | `protein_activity` | 蛋白基因组与变异肽证据 | proteomics, multiomics |
| `mofa_factors` | `multiomics` | MOFA 潜在因子与视图解释 | multiomics, singlecell_multiome |
| `supervised_multiomics` | `multiomics` | 监督式多组学整合 | multiomics, singlecell_multiome |
| `rna_protein_concordance` | `multiomics` | RNA—蛋白/代谢关联与不一致 | multiomics |
| `multiomics_mediation` | `multiomics` | 有条件的中介分析审查 | multiomics |
| `cross_study_meta` | `multiomics` | 跨研究效应综合与异质性 | bulk_rna, scrna, spatial_rna, expression_array, long_read_rna, proteomics, phosphoproteomics, singlecell_multiome, multiomics, metabolomics, lipidomics, gwas_qtl |
| `singlecell_abundance` | `composition` | Milo 细胞邻域差异丰度 | scrna, singlecell_multiome |
| `microbe_differential` | `composition` | 微生物差异丰度与组成偏差 | amplicon, metagenomics |
| `microbe_diversity` | `composition` | α/β 多样性与群落差异 | amplicon, metagenomics |
| `microbe_network` | `composition` | 组成数据微生物关联网络 | amplicon, metagenomics |
| `cell_fraction_contrasts` | `composition` | 细胞类型组成与差异比例 | scrna, spatial_rna, singlecell_multiome, bulk_rna |
| `microbe_pathways` | `functional_profile` | 微生物功能与通路丰度 | metagenomics |
| `microbe_strain` | `functional_profile` | 菌株分辨与群体结构 | metagenomics |
| `microbe_gene_context` | `functional_profile` | 微生物基因功能注释与上下文 | metagenomics |
| `lipid_class_enrichment` | `lipid_classes` | 脂质类别与链特征富集 | lipidomics, metabolomics |
| `lipid_chain_patterns` | `lipid_classes` | 脂质链长与不饱和模式 | lipidomics |
| `singlecell_cnv` | `sv_cnv` | 表达推断的单细胞 CNV | scrna, singlecell_multiome |
| `bulk_cnv` | `sv_cnv` | DNA 拷贝数与等位基因状态 | somatic, germline |
| `clonal_phylogeny` | `sv_cnv` | 亚克隆组成与演化树 | somatic |
| `repertoire_clonotypes` | `repertoire` | TCR/BCR 克隆型与配对 | scrna, singlecell_multiome |
| `repertoire_diversity` | `repertoire` | 受体谱多样性与克隆扩增 | scrna, singlecell_multiome |
| `clonotype_phenotype` | `repertoire` | 克隆型—细胞状态关联 | scrna, singlecell_multiome |
| `spatial_variable_genes` | `spatial_context` | 空间变异基因与空间零模型 | spatial_rna |
| `spatial_niches` | `spatial_context` | 邻域富集与组织生态位 | spatial_rna |
| `spatial_gradients` | `spatial_context` | 组织边界距离与空间梯度 | spatial_rna |
| `spatial_domains` | `spatial_context` | 空间域与组织学一致性 | spatial_rna |

### GO/Reactome 等过度代表分析 (`ora`)

**问题**：选定列表相对实际受检背景是否过度代表功能集合？

**服务器方法候选**：clusterProfiler

**输入前提**：`tested_universe`、`gene_sets`、`identifier_mapping`

**必须作出的决定**：`universe_definition`、`list_selection`、`set_size_range`

**专用 QC**：

- `input`：核对 tested_universe、gene_sets、identifier_mapping 的选定来源、尺度、完整分母及版本
- `design`：预先固定列表选择、方向、实际可测受检背景及多重比较族；同源转换不可静默扩展基因数
- `diagnostics`：核对集合版本、映射丢失、集合大小、背景包含关系、重叠基因及重复 ID
- `sensitivity`：比较合理背景、集合大小范围和映射规则；保留未富集条目

**必需输出**：`ora_table`、`ora_universe`、`ora_overlap`、`ora_sensitivity`

**解释边界**：富集不是活性方向或机制证明。

**原方法参考**：[clusterprofiler](https://bioconductor.org/packages/release/bioc/html/clusterProfiler.html)


### 全受检列表的预排序 GSEA (`preranked_gsea`)

**问题**：整个受检排序中是否存在协调变化？

**服务器方法候选**：fgsea

**输入前提**：`complete_signed_ranks`、`gene_sets`、`tested_universe`

**必须作出的决定**：`ranking_metric`、`null_definition`、`permutation_precision`

**专用 QC**：

- `input`：核对 complete_signed_ranks、gene_sets、tested_universe 的选定来源、尺度、完整分母及版本
- `design`：声明有符号排序统计量、竞争性零假设及 FDR 比较族；不能仅输入显著 DEG
- `diagnostics`：检查排序并列、零值、重复映射、集合覆盖和蒙特卡洛误差
- `sensitivity`：比较预先合理的排序量、集合大小和重复随机种子；保留 NES 方向

**必需输出**：`gsea_table`、`gsea_ranks`、`gsea_leading_edge`、`gsea_uncertainty`

**解释边界**：预排序置换不等同于样本标签置换。

**原方法参考**：[fgsea](https://bioconductor.org/packages/release/bioc/html/fgsea.html)


### 考虑基因间相关的集合检验 (`camera_sets`)

**问题**：考虑基因间相关后集合是否关联指定对比？

**服务器方法候选**：limma camera

**输入前提**：`expression_design`、`contrast_matrix`、`gene_sets`

**必须作出的决定**：`contrast_definition`、`correlation_model`、`set_size_range`

**专用 QC**：

- `input`：核对 expression_design、contrast_matrix、gene_sets 的选定来源、尺度、完整分母及版本
- `design`：使用与表达模型相同的独立单位、设计和对比；声明竞争性检验族
- `diagnostics`：检查设计秩、残差自由度、集合内相关及权重
- `sensitivity`：比较相关估计、集合范围和离群样本影响

**必需输出**：`camera_table`、`camera_design`、`camera_diagnostics`、`camera_sensitivity`

**解释边界**：集合关联不能推出全部成员发生同方向变化。

**原方法参考**：[limma](https://bioconductor.org/packages/release/bioc/html/limma.html)


### GSVA 样本级集合分数 (`gsva_scores`)

**问题**：冻结的集合如何在样本之间变化？

**服务器方法候选**：GSVA

**输入前提**：`expression_scale`、`gene_sets`、`sample_metadata`

**必须作出的决定**：`expression_scale`、`kernel_choice`、`score_model`

**专用 QC**：

- `input`：核对 expression_scale、gene_sets、sample_metadata 的选定来源、尺度、完整分母及版本
- `design`：打分与分数上的组间推断分开；分数模型沿用独立单位与重复结构
- `diagnostics`：检查输入分布、核分布选择、常量特征及集合覆盖
- `sensitivity`：比较核设置、集合覆盖和队列构成的影响

**必需输出**：`gsva_scores`、`gsva_coverage`、`gsva_diagnostics`、`gsva_contrasts`

**解释边界**：分数不是绝对通路活性，也不能任意跨队列比较。

**原方法参考**：[gsva](https://bioconductor.org/packages/release/bioc/html/GSVA.html)


### ssGSEA 样本级排序分数 (`ssgsea_scores`)

**问题**：样本内集合排序富集如何变化？

**服务器方法候选**：GSVA ssGSEA

**输入前提**：`expression_scale`、`gene_sets`、`sample_metadata`

**必须作出的决定**：`normalization_definition`、`rank_weight`、`score_model`

**专用 QC**：

- `input`：核对 expression_scale、gene_sets、sample_metadata 的选定来源、尺度、完整分母及版本
- `design`：保留打分归一化规则及后续分数模型；细胞打分不增加独立 n
- `diagnostics`：检查秩并列、低覆盖、集合大小及归一化范围
- `sensitivity`：比较归一化开关及参考集合覆盖

**必需输出**：`ssgsea_scores`、`ssgsea_coverage`、`ssgsea_parameters`、`ssgsea_sensitivity`

**解释边界**：不同算法的分数不能当作同一单位直接合并。

**原方法参考**：[gsva](https://bioconductor.org/packages/release/bioc/html/GSVA.html)


### Leading-edge 与集合冗余审查 (`leading_edge`)

**问题**：哪些成员驱动已计算的集合信号，哪些集合重复？

**服务器方法候选**：fgsea leadingEdge

**输入前提**：`gsea_results`、`complete_signed_ranks`、`gene_sets`

**必须作出的决定**：`representative_rule`、`overlap_definition`、`retained_test_family`

**专用 QC**：

- `input`：核对 gsea_results、complete_signed_ranks、gene_sets 的选定来源、尺度、完整分母及版本
- `design`：保留原检验族；展示代表项不得改写原 FDR 或只保留支持故事的集合
- `diagnostics`：检查成员集合、rank 位置和 ES 方向与原始结果一致
- `sensitivity`：比较预先说明的冗余阈值并保留未合并原表

**必需输出**：`leading_edge_members`、`term_overlap`、`representative_terms`、`full_term_index`

**解释边界**：共享成员不证明共享独立机制。

**原方法参考**：[fgsea](https://bioconductor.org/packages/release/bioc/html/fgsea.html)


### 物理 PPI 证据网络 (`physical_ppi`)

**问题**：哪些候选蛋白具有指定证据等级的相互作用？

**服务器方法候选**：IntAct；STRING physical network

**输入前提**：`interaction_evidence`、`identifier_mapping`、`tested_universe`

**必须作出的决定**：`relation_type`、`evidence_channels`、`confidence_rule`

**专用 QC**：

- `input`：核对 interaction_evidence、identifier_mapping、tested_universe 的选定来源、尺度、完整分母及版本
- `design`：指定物理/功能关系、物种、来源通道及网络受检背景
- `diagnostics`：检查重复边、自环、同源映射、置信度通道及实验来源
- `sensitivity`：比较证据门槛及去除文本挖掘/预测通道后的网络

**必需输出**：`physical_edges`、`interaction_sources`、`network_universe`、`network_sensitivity`

**解释边界**：数据库边不自动证明当前细胞模型中的结合。 STRING physical 也含预测支持，不能全部标成实验物理结合。

**原方法参考**：[string_docs](https://string-db.org/help/api/)、[intact](https://www.ebi.ac.uk/intact/home)


### PPI 模块与中心性稳健性 (`ppi_modules`)

**问题**：模块和候选枢纽是否对网络构建稳健？

**服务器方法候选**：Cytoscape；igraph

**输入前提**：`reviewed_network`、`network_background`、`resampling_plan`

**必须作出的决定**：`edge_weight_definition`、`module_method`、`null_network`

**专用 QC**：

- `input`：核对 reviewed_network、network_background、resampling_plan 的选定来源、尺度、完整分母及版本
- `design`：声明方向、边权及匹配度分布的零模型；选择规则不能用结局反复调参
- `diagnostics`：检查孤立点、连通分量、中心性定义与模块大小
- `sensitivity`：边删减/证据通道/随机种子敏感性；报告模块稳定性

**必需输出**：`network_modules`、`network_centrality`、`network_null`、`network_stability`

**解释边界**：高度节点不等于因果靶点。

**原方法参考**：[igraph_docs](https://igraph.org/python/)


### 网络传播与候选排序 (`network_diffusion`)

**问题**：给定种子和网络先验，哪些候选可优先复核？

**服务器方法候选**：igraph personalized PageRank

**输入前提**：`reviewed_network`、`seed_evidence`、`heldout_evidence`

**必须作出的决定**：`seed_selection`、`restart_rule`、`validation_split`

**专用 QC**：

- `input`：核对 reviewed_network、seed_evidence、heldout_evidence 的选定来源、尺度、完整分母及版本
- `design`：隔离构建种子与验证来源；用度匹配基线评估先验泄漏
- `diagnostics`：检查种子覆盖、传播参数、网络连通性与度偏倚
- `sensitivity`：留一种子/留一来源与重启参数敏感性

**必需输出**：`diffusion_ranks`、`diffusion_seeds`、`diffusion_null`、`diffusion_holdout`

**解释边界**：传播得分是优先级，不是作用效应或药效。

**原方法参考**：[igraph_docs](https://igraph.org/python/)


### WGCNA 模块与性状关联 (`wgcna_modules`)

**问题**：独立样本的哪些共表达模块关联预定性状？

**服务器方法候选**：WGCNA

**输入前提**：`independent_expression`、`sample_size_review`、`trait_design`

**必须作出的决定**：`network_signedness`、`soft_threshold_basis`、`trait_model`

**专用 QC**：

- `input`：核对 independent_expression、sample_size_review、trait_design 的选定来源、尺度、完整分母及版本
- `design`：先审样本量、有效独立 n、协变量及重复结构；模块与性状的检验族需明确
- `diagnostics`：检查缺失、离群样本、软阈值/连通性、模块大小、eigengene 方向及性状混杂
- `sensitivity`：软阈值、分模块参数、独立单位重采样与离群敏感性

**必需输出**：`wgcna_modules`、`module_trait_effects`、`wgcna_diagnostics`、`wgcna_resampling`

**解释边界**：相关模块和 hub 不是调控因果；无统一小样本合格阈值。

**原方法参考**：[wgcna](https://cran.r-project.org/web/packages/WGCNA/index.html)


### 独立队列模块保留与复现 (`module_preservation`)

**问题**：冻结模块在独立队列是否保留？

**服务器方法候选**：WGCNA modulePreservation

**输入前提**：`frozen_reference_modules`、`independent_validation_cohort`、`shared_features`

**必须作出的决定**：`reference_modules`、`validation_independence`、`preservation_rule`

**专用 QC**：

- `input`：核对 frozen_reference_modules、independent_validation_cohort、shared_features 的选定来源、尺度、完整分母及版本
- `design`：训练/验证样本和供者独立；冻结模块定义、映射与复现判据
- `diagnostics`：检查共享特征、模块大小效应、平台及样本量差异
- `sensitivity`：匹配基因背景和置换次数；保留非保留模块

**必需输出**：`preservation_table`、`preservation_mapping`、`preservation_null`、`preservation_failures`

**解释边界**：保留统计与性状效应复现需分别判断。

**原方法参考**：[wgcna](https://cran.r-project.org/web/packages/WGCNA/index.html)


### 差异相关与网络重连 (`differential_coexpression`)

**问题**：条件间相关结构是否改变？

**服务器方法候选**：diffcoexp

**输入前提**：`independent_expression`、`replicate_design`、`network_background`

**必须作出的决定**：`correlation_metric`、`permutation_unit`、`edge_test_family`

**专用 QC**：

- `input`：核对 independent_expression、replicate_design、network_background 的选定来源、尺度、完整分母及版本
- `design`：独立单位内置换或分层重采样；区分均值变化与相关变化
- `diagnostics`：检查组内 n、方差范围、离群点、批次及边数检验族
- `sensitivity`：稳健相关、分层置换与重采样稳定性

**必需输出**：`differential_edges`、`group_correlations`、`edge_uncertainty`、`rewiring_stability`

**解释边界**：网络差异不等同于新的直接物理互作。

**原方法参考**：[diffcoexp](https://bioconductor.org/packages/release/bioc/html/diffcoexp.html)


### 参考驱动的 bulk 细胞组成估计 (`bulk_deconvolution`)

**问题**：混合样本的细胞组成可否由参考合理估计？

**服务器方法候选**：MuSiC；BisqueRNA

**输入前提**：`compatible_reference`、`donor_reference`、`expression_scale`

**必须作出的决定**：`reference_population`、`proportion_definition`、`unknown_cell_policy`

**专用 QC**：

- `input`：核对 compatible_reference、donor_reference、expression_scale 的选定来源、尺度、完整分母及版本
- `design`：参考与目标独立性、物种/组织/平台匹配；组成比较使用样本级设计
- `diagnostics`：检查参考细胞覆盖、标记特异性、残差、负值与总和约束
- `sensitivity`：留一参考供者、缺失细胞类型及不同参考敏感性

**必需输出**：`cell_fraction_estimates`、`reference_coverage`、`reconstruction_residuals`、`reference_sensitivity`

**解释边界**：RNA 贡献与细胞数比例需要区分。

**原方法参考**：[music](https://github.com/xuranw/MuSiC)


### 空间 spot 细胞丰度估计 (`spatial_deconvolution`)

**问题**：混合 spot 的细胞丰度如何空间分布？

**服务器方法候选**：cell2location；RCTD

**输入前提**：`compatible_reference`、`registered_coordinates`、`tissue_metadata`

**必须作出的决定**：`abundance_unit`、`reference_scope`、`spatial_validation`

**专用 QC**：

- `input`：核对 compatible_reference、registered_coordinates、tissue_metadata 的选定来源、尺度、完整分母及版本
- `design`：切片/供者嵌套；训练参考和验证组织学独立，保留单位和分辨率
- `diagnostics`：检查参考覆盖、后验/拟合诊断、组织边界和空间残差
- `sensitivity`：参考、超参数及分辨率敏感性

**必需输出**：`spatial_abundance`、`spatial_reference_fit`、`spatial_uncertainty`、`histology_checks`

**解释边界**：spot 不是独立受试者；空间丰度仍为估计。

**原方法参考**：[cell2location](https://cell2location.readthedocs.io/en/latest/)


### 轨迹拓扑与根节点稳健性 (`trajectory_topology`)

**问题**：状态之间有哪些对采样和根节点稳健的路径？

**服务器方法候选**：Slingshot；Monocle3

**输入前提**：`frozen_cell_states`、`root_evidence`、`donor_structure`

**必须作出的决定**：`root_definition`、`branch_selection`、`donor_sampling`

**专用 QC**：

- `input`：核对 frozen_cell_states、root_evidence、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：根节点依据独立生物学信息；不以期望结论选择分支
- `diagnostics`：检查供者覆盖、批次混合、断裂群及分支支持
- `sensitivity`：替代根、供者留出和参数敏感性

**必需输出**：`trajectory_topology`、`pseudotime_assignments`、`root_evidence`、`trajectory_resampling`

**解释边界**：拟时序不是实测时间或谱系追踪。

**原方法参考**：[slingshot](https://bioconductor.org/packages/release/bioc/html/slingshot.html)


### 沿轨迹与分支的表达变化 (`trajectory_dynamics`)

**问题**：基因沿既定轨迹或不同分支如何变化？

**服务器方法候选**：tradeSeq

**输入前提**：`frozen_pseudotime`、`lineage_weights`、`donor_structure`

**必须作出的决定**：`hypothesis_family`、`knot_selection`、`dependence_model`

**专用 QC**：

- `input`：核对 frozen_pseudotime、lineage_weights、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：声明关联/起终点/分支差异的不同假设；供者相关与轨迹不确定性须审核
- `diagnostics`：检查拟合收敛、结点、有效样本覆盖及分支权重
- `sensitivity`：结点数、轨迹替代及供者重采样

**必需输出**：`trajectory_gene_tests`、`trajectory_curves`、`trajectory_fit`、`trajectory_test_family`

**解释边界**：同一数据的轨迹选择和检验可能存在选择偏差。

**原方法参考**：[tradeseq](https://bioconductor.org/packages/release/bioc/html/tradeSeq.html)


### RNA velocity 动力学与相图 (`kinetic_velocity`)

**问题**：动力学假设下是否存在稳定方向信息？

**服务器方法候选**：scVelo

**输入前提**：`spliced_unspliced`、`kinetic_model_review`、`donor_structure`

**必须作出的决定**：`kinetic_model`、`layer_definition`、`confidence_rule`

**专用 QC**：

- `input`：核对 spliced_unspliced、kinetic_model_review、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：声明模型、层来源、适用细胞范围；不得把细胞数作为生物学重复
- `diagnostics`：检查相图、基因拟合、层定义、速度置信度及批次
- `sensitivity`：模型、邻域、基因集与供者留出敏感性

**必需输出**：`velocity_vectors`、`kinetic_parameters`、`phase_diagnostics`、`velocity_sensitivity`

**解释边界**：二维箭头展示不验证分化方向或命运。

**原方法参考**：[scvelo](https://scvelo.readthedocs.io/en/stable/)


### CellRank 状态与命运概率 (`fate_probabilities`)

**问题**：指定转移核下到达终末状态的概率如何变化？

**服务器方法候选**：CellRank

**输入前提**：`transition_kernel`、`terminal_state_evidence`、`donor_structure`

**必须作出的决定**：`kernel_definition`、`terminal_rule`、`state_count_basis`

**专用 QC**：

- `input`：核对 transition_kernel、terminal_state_evidence、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：区分 velocity/pseudotime/实测时间核；终末状态需外部依据
- `diagnostics`：检查核归一化、宏状态稳定性、不可达状态和吸收假设
- `sensitivity`：核权重、状态数及终末状态敏感性

**必需输出**：`fate_probabilities`、`terminal_states`、`kernel_diagnostics`、`fate_sensitivity`

**解释边界**：模型命运概率不是实际追踪到的细胞命运。

**原方法参考**：[cellrank](https://cellrank.readthedocs.io/en/stable/)


### 配体受体多方法共识 (`lr_consensus`)

**问题**：哪些配体受体关系有表达与多方法支持？

**服务器方法候选**：LIANA+

**输入前提**：`ligand_receptor_reference`、`expression_support`、`donor_structure`

**必须作出的决定**：`resource_version`、`complex_rule`、`expression_support_rule`

**专用 QC**：

- `input`：核对 ligand_receptor_reference、expression_support、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：完整供者和细胞群分母；复合物亚基、物种和数据库版本固定
- `diagnostics`：检查表达覆盖、群大小、亚基、方法分数方向与缺失组合
- `sensitivity`：数据库/表达阈值/方法集合与供者稳定性

**必需输出**：`lr_consensus`、`lr_method_scores`、`lr_coverage`、`lr_sensitivity`

**解释边界**：表达兼容不证明分泌、接触或结合。

**原方法参考**：[liana](https://liana.readthedocs.io/en/stable/tutorials.html)


### 供者层级的差异通信 (`lr_differential`)

**问题**：通信摘要是否随预定条件改变？

**服务器方法候选**：LIANA+ differential workflows

**输入前提**：`per_donor_lr`、`replicate_design`、`comparable_cell_types`

**必须作出的决定**：`donor_model`、`missing_pair_policy`、`contrast_family`

**专用 QC**：

- `input`：核对 per_donor_lr、replicate_design、comparable_cell_types 的选定来源、尺度、完整分母及版本
- `design`：供者级重复、缺失细胞群和组成差异分开处理；固定 LR 检验族
- `diagnostics`：检查每组供者覆盖、缺失对、群丰度及分数可比性
- `sensitivity`：组成调整、供者重采样和数据库敏感性

**必需输出**：`lr_contrasts`、`lr_donor_support`、`lr_missing_pairs`、`lr_contrast_sensitivity`

**解释边界**：通信得分差异不等同于信号传递效应。

**原方法参考**：[liana](https://liana.readthedocs.io/en/stable/tutorials.html)


### 配体到受体细胞靶基因 (`ligand_target_links`)

**问题**：哪些候选配体可解释指定受体细胞的响应基因？

**服务器方法候选**：NicheNet

**输入前提**：`sender_receiver_definition`、`receiver_target_genes`、`ligand_target_prior`

**必须作出的决定**：`receiver_target_definition`、`sender_scope`、`prior_version`

**专用 QC**：

- `input`：核对 sender_receiver_definition、receiver_target_genes、ligand_target_prior 的选定来源、尺度、完整分母及版本
- `design`：响应基因选择与可测背景明确；训练先验与验证证据分离
- `diagnostics`：检查受体表达、靶基因覆盖、先验来源和方向
- `sensitivity`：背景/候选配体/先验覆盖的敏感性

**必需输出**：`ligand_priorities`、`ligand_target_links`、`receiver_universe`、`ligand_controls`

**解释边界**：先验一致性不是配体扰动的因果验证。

**原方法参考**：[nichenet](https://github.com/saeyslab/nichenetr)


### 空间约束的配体受体关系 (`spatial_lr`)

**问题**：候选通信是否与局部空间邻域相容？

**服务器方法候选**：LIANA+ spatial

**输入前提**：`registered_coordinates`、`ligand_receptor_reference`、`tissue_boundaries`

**必须作出的决定**：`distance_unit`、`neighborhood_definition`、`spatial_null`

**专用 QC**：

- `input`：核对 registered_coordinates、ligand_receptor_reference、tissue_boundaries 的选定来源、尺度、完整分母及版本
- `design`：组织掩膜、切片/供者内空间零模型；避免跨供者坐标拼接
- `diagnostics`：检查距离单位、邻域、边界、稀疏性及混合 spot
- `sensitivity`：距离半径、掩膜与空间置换敏感性

**必需输出**：`spatial_lr_scores`、`spatial_lr_pairs`、`spatial_null`、`spatial_lr_radius`

**解释边界**：共定位不能证明接触或实际分泌作用。

**原方法参考**：[liana](https://liana.readthedocs.io/en/stable/tutorials.html)


### 有符号调控靶集合的 TF 活性 (`tf_activity`)

**问题**：靶基因模式是否支持 TF 活性变化候选？

**服务器方法候选**：decoupleR；decoupler

**输入前提**：`signed_regulon`、`expression_scale`、`tested_universe`

**必须作出的决定**：`regulon_resource`、`coverage_rule`、`activity_model`

**专用 QC**：

- `input`：核对 signed_regulon、expression_scale、tested_universe 的选定来源、尺度、完整分母及版本
- `design`：固定 regulon 版本/置信度及供者级模型；表达量与推断活性分开
- `diagnostics`：检查靶覆盖、符号、最低靶数与方法间一致性
- `sensitivity`：资源、置信度、覆盖阈值和方法敏感性

**必需输出**：`tf_activity_scores`、`tf_target_coverage`、`tf_activity_effects`、`tf_activity_sensitivity`

**解释边界**：推断活性不证明 TF 蛋白量、结合或磷酸化。

**原方法参考**：[decoupler](https://github.com/saezlab/decoupler-py)


### SCENIC 共表达与 motif 支持 regulon (`scenic_regulons`)

**问题**：哪些共表达靶集合获得 motif 先验支持？

**服务器方法候选**：pySCENIC

**输入前提**：`independent_expression`、`motif_rank_database`、`donor_structure`

**必须作出的决定**：`ranking_database`、`region_definition`、`donor_validation`

**专用 QC**：

- `input`：核对 independent_expression、motif_rank_database、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：声明细胞与供者抽样、数据库版本及训练/验证分离
- `diagnostics`：检查基因覆盖、共表达稳定性、motif 物种/基因区域和 regulon 覆盖
- `sensitivity`：随机种子、细胞抽样、供者留出与数据库敏感性

**必需输出**：`regulon_edges`、`regulon_activity`、`motif_support`、`regulon_stability`

**解释边界**：共表达加 motif 支持不等于直接调控实验证据。

**原方法参考**：[pyscenic](https://pyscenic.readthedocs.io/en/latest/)


### 匹配背景的 motif 富集 (`motif_enrichment`)

**问题**：目标区域相对匹配背景是否富集 motif？

**服务器方法候选**：motifmatchr；HOMER

**输入前提**：`peak_sequences`、`matched_peak_background`、`motif_database`

**必须作出的决定**：`background_matching`、`region_window`、`motif_version`

**专用 QC**：

- `input`：核对 peak_sequences、matched_peak_background、motif_database 的选定来源、尺度、完整分母及版本
- `design`：背景匹配长度/GC/可及性且固定受检 TF 族
- `diagnostics`：检查坐标构建、序列、GC、黑名单及相似 motif 冗余
- `sensitivity`：不同匹配背景、窗口和 motif 库敏感性

**必需输出**：`motif_enrichment`、`motif_background`、`motif_matches`、`motif_sensitivity`

**解释边界**：motif 匹配不等同于真实结合或 TF 身份唯一。

**原方法参考**：[signac](https://stuartlab.org/signac/)


### chromVAR motif 可及性偏差 (`motif_deviation`)

**问题**：含 motif 的区域可及性偏差如何变化？

**服务器方法候选**：chromVAR

**输入前提**：`peak_counts`、`motif_matches`、`gc_background`

**必须作出的决定**：`background_rule`、`motif_resource`、`comparison_unit`

**专用 QC**：

- `input`：核对 peak_counts、motif_matches、gc_background 的选定来源、尺度、完整分母及版本
- `design`：样本/供者级比较；声明深度和 GC 背景校正及检验族
- `diagnostics`：检查片段深度、偏差分布、背景峰与稀疏群覆盖
- `sensitivity`：背景峰、低深度过滤及供者聚合敏感性

**必需输出**：`motif_deviation_scores`、`motif_deviation_effects`、`chromvar_background`、`chromvar_diagnostics`

**解释边界**：偏差分数不是直接结合或转录激活。

**原方法参考**：[chromvar](https://bioconductor.org/packages/release/bioc/html/chromVAR.html)


### ATAC footprint 与偏倚审查 (`footprinting`)

**问题**：偏倚校正后 motif 位点是否存在 footprint 模式？

**服务器方法候选**：TOBIAS

**输入前提**：`insertion_profiles`、`tagmentation_bias`、`motif_sites`

**必须作出的决定**：`bias_model`、`site_selection`、`depth_matching`

**专用 QC**：

- `input`：核对 insertion_profiles、tagmentation_bias、motif_sites 的选定来源、尺度、完整分母及版本
- `design`：独立重复及区域匹配；深度和细胞混合影响需分开
- `diagnostics`：检查 Tn5 偏倚、链方向、覆盖、峰定义和核小体背景
- `sensitivity`：覆盖下采样、窗口与偏倚模型敏感性

**必需输出**：`footprint_profiles`、`footprint_scores`、`bias_profiles`、`footprint_sensitivity`

**解释边界**：footprint 不足以证明单个 TF 的直接结合。

**原方法参考**：[tobias](https://github.com/loosolab/TOBIAS)


### 增强子—TF—基因候选网络 (`enhancer_grn`)

**问题**：哪些候选调控链受到多模态支持？

**服务器方法候选**：SCENIC+

**输入前提**：`matched_rna_atac`、`enhancer_candidates`、`motif_database`

**必须作出的决定**：`pairing_definition`、`enhancer_scope`、`validation_split`

**专用 QC**：

- `input`：核对 matched_rna_atac、enhancer_candidates、motif_database 的选定来源、尺度、完整分母及版本
- `design`：匹配/非匹配模态必须声明；先验和验证不重用同一证据
- `diagnostics`：检查供者对齐、区域/基因映射、eRegulon 覆盖和平台
- `sensitivity`：区域窗口、链接阈值和供者留出敏感性

**必需输出**：`enhancer_tf_gene_links`、`eregulon_scores`、`link_support`、`grn_holdout`

**解释边界**：相关链接不是增强子扰动或调控因果证明。

**原方法参考**：[scenicplus](https://scenicplus.readthedocs.io/en/latest/)


### 外显子相对使用 (`exon_usage`)

**问题**：外显子的相对使用是否随条件改变？

**服务器方法候选**：DEXSeq

**输入前提**：`exon_counts`、`exon_annotation`、`replicate_design`

**必须作出的决定**：`exon_definition`、`filtering_rule`、`hierarchical_testing`

**专用 QC**：

- `input`：核对 exon_counts、exon_annotation、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：外显子/基因层级检验、独立单位及批次设计明确
- `diagnostics`：检查覆盖、可比外显子边界、模型拟合及离群样本
- `sensitivity`：过滤、注释与高影响样本敏感性

**必需输出**：`exon_usage_effects`、`exon_counts_qc`、`exon_test_family`、`exon_diagnostics`

**解释边界**：相对使用不同于基因总量变化。

**原方法参考**：[dexseq](https://bioconductor.org/packages/release/bioc/html/DEXSeq.html)


### 剪接事件与 junction cluster (`junction_events`)

**问题**：事件 PSI 或内含子簇相对使用是否改变？

**服务器方法候选**：rMATS；LeafCutter

**输入前提**：`junction_counts`、`library_protocol`、`replicate_design`

**必须作出的决定**：`event_model`、`psi_unit`、`coverage_rule`

**专用 QC**：

- `input`：核对 junction_counts、library_protocol、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：声明事件/簇、delta PSI 单位、配对关系和 FDR 族
- `diagnostics`：检查唯一比对、链特异性、读长、覆盖与事件可估计性
- `sensitivity`：覆盖阈值、注释与模型选择敏感性

**必需输出**：`junction_effects`、`junction_coverage`、`event_definitions`、`splicing_sensitivity`

**解释边界**：不同事件模型的效应与检验全集不能直接混用。

**原方法参考**：[rmats](https://github.com/Xinglab/rmats-turbo)


### 差异转录本使用 DTU (`transcript_usage`)

**问题**：同一基因内转录本组成是否改变？

**服务器方法候选**：DRIMSeq；satuRn

**输入前提**：`transcript_abundance`、`transcript_gene_map`、`replicate_design`

**必须作出的决定**：`usage_denominator`、`annotation_version`、`stagewise_testing`

**专用 QC**：

- `input`：核对 transcript_abundance、transcript_gene_map、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：区分 DTU 和 DTE；基因/转录本层级检验及不确定性需明确
- `diagnostics`：检查可识别异构体、映射、低使用过滤及离散度
- `sensitivity`：定量/注释/过滤敏感性

**必需输出**：`dtu_effects`、`transcript_mapping`、`dtu_diagnostics`、`dtu_hierarchical_tests`

**解释边界**：短读长异构体可识别性限制解释。

**原方法参考**：[drimseq](https://bioconductor.org/packages/release/bioc/html/DRIMSeq.html)


### 可变多聚腺苷酸化 APA (`apa_usage`)

**问题**：3′ 端或 poly(A) 位点相对使用是否改变？

**服务器方法候选**：QAPA；DaPars2

**输入前提**：`three_prime_evidence`、`utr_annotation`、`library_protocol`

**必须作出的决定**：`three_prime_protocol`、`site_definition`、`usage_denominator`

**专用 QC**：

- `input`：核对 three_prime_evidence、utr_annotation、library_protocol 的选定来源、尺度、完整分母及版本
- `design`：协议适配、基因内分母与供者级对比；基因总量变化分开
- `diagnostics`：检查 3′ 偏倚、内部引物、覆盖和末端注释
- `sensitivity`：位点窗口、注释和覆盖敏感性

**必需输出**：`apa_usage`、`apa_sites`、`apa_coverage`、`apa_sensitivity`

**解释边界**：普通 RNA-seq 对 APA 的证据强度取决于协议。

**原方法参考**：[qapa](https://github.com/morrislab/qapa)


### 异构体转换及功能后果候选 (`isoform_switch`)

**问题**：使用转换是否伴随有依据的功能注释差异？

**服务器方法候选**：IsoformSwitchAnalyzeR

**输入前提**：`transcript_usage`、`isoform_sequences`、`domain_annotation`

**必须作出的决定**：`orf_evidence`、`consequence_scope`、`isoform_filter`

**专用 QC**：

- `input`：核对 transcript_usage、isoform_sequences、domain_annotation 的选定来源、尺度、完整分母及版本
- `design`：先验与观测结构分开；DTU 及后果筛选的比较族明确
- `diagnostics`：检查 ORF、NMD、结构域映射、异构体覆盖与版本
- `sensitivity`：ORF/结构域注释及最低使用量敏感性

**必需输出**：`isoform_switches`、`isoform_consequences`、`isoform_mapping`、`consequence_limits`

**解释边界**：RNA 注释后果不能直接推断蛋白表达或活性。

**原方法参考**：[isoformswitch](https://bioconductor.org/packages/release/bioc/html/IsoformSwitchAnalyzeR.html)


### 纵向、交互与重复测量效应 (`longitudinal_effects`)

**问题**：时间、条件及其交互效应如何变化？

**服务器方法候选**：limma；variancePartition dream

**输入前提**：`time_metadata`、`dependence_structure`、`replicate_design`

**必须作出的决定**：`time_scale`、`time_function`、`covariance_structure`

**专用 QC**：

- `input`：核对 time_metadata、dependence_structure、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：区分纵向和横断面时间；随机效应、时间尺度和估计目标预先明确
- `diagnostics`：检查设计秩、时间覆盖、协方差结构、缺失与残差
- `sensitivity`：时间函数、缺失假设与协方差结构敏感性

**必需输出**：`time_contrasts`、`time_design`、`time_diagnostics`、`time_sensitivity`

**解释边界**：时间先后关联不建立因果次序。

**原方法参考**：[limma](https://bioconductor.org/packages/release/bioc/html/limma.html)、[dream](https://bioconductor.org/packages/release/bioc/html/variancePartition.html)


### 非线性时间响应 (`impulse_response`)

**问题**：预定非线性响应是否受到数据支持？

**服务器方法候选**：maSigPro

**输入前提**：`time_metadata`、`sufficient_time_coverage`、`replicate_design`

**必须作出的决定**：`response_family`、`time_hypothesis`、`extrapolation_policy`

**专用 QC**：

- `input`：核对 time_metadata、sufficient_time_coverage、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：核对时间点覆盖和有效重复；明确条件/时间零假设
- `diagnostics`：检查拟合收敛、外推、低计数与时间覆盖
- `sensitivity`：函数形式、异常时间点和留出时间验证

**必需输出**：`nonlinear_time_tests`、`fitted_time_curves`、`time_coverage`、`nonlinear_sensitivity`

**解释边界**：稀疏时间点不能可靠恢复任意动力学。

**原方法参考**：[masigpro](https://bioconductor.org/packages/release/bioc/html/maSigPro.html)


### 时间模式模块与稳定性 (`temporal_modules`)

**问题**：哪些特征具有稳健的时间变化模式？

**服务器方法候选**：maSigPro；WGCNA

**输入前提**：`frozen_time_effects`、`time_metadata`、`resampling_plan`

**必须作出的决定**：`curve_scaling`、`module_selection`、`block_resampling`

**专用 QC**：

- `input`：核对 frozen_time_effects、time_metadata、resampling_plan 的选定来源、尺度、完整分母及版本
- `design`：模块生成与显著性推断分开；按供者/时间块重采样
- `diagnostics`：检查缩放定义、曲线不确定性、模块大小和缺测
- `sensitivity`：模块数、距离度量和时间块留出敏感性

**必需输出**：`temporal_modules`、`temporal_centroids`、`temporal_uncertainty`、`temporal_stability`

**解释边界**：聚类相似时间曲线不是共同调控证明。

**原方法参考**：[masigpro](https://bioconductor.org/packages/release/bioc/html/maSigPro.html)


### 无泄漏嵌套验证预测 (`nested_prediction`)

**问题**：冻结应用场景中模型是否优于预定基线？

**服务器方法候选**：scikit-learn Pipeline nested CV

**输入前提**：`outcome_definition`、`independent_splits`、`sample_size_review`

**必须作出的决定**：`split_unit`、`primary_metric`、`preprocessing_scope`

**专用 QC**：

- `input`：核对 outcome_definition、independent_splits、sample_size_review 的选定来源、尺度、完整分母及版本
- `design`：供者/研究/时间分组；特征筛选、填补、标准化和调参全部在训练折内
- `diagnostics`：检查泄漏、类别失衡、校准、置信区间及每折有效 n
- `sensitivity`：替代划分、基线、学习曲线与外部分布漂移

**必需输出**：`out_of_fold_predictions`、`nested_splits`、`prediction_metrics`、`leakage_audit`

**解释边界**：内部交叉验证不等同于外部验证或临床效用。

**原方法参考**：[sklearn](https://scikit-learn.org/stable/common_pitfalls.html)


### 生存结局模型与动态性能 (`survival_prediction`)

**问题**：指定时间起点与结局下风险预测是否可靠？

**服务器方法候选**：survival；scikit-survival

**输入前提**：`time_event_definition`、`censoring_metadata`、`independent_splits`

**必须作出的决定**：`time_zero`、`event_definition`、`competing_risk_policy`

**专用 QC**：

- `input`：核对 time_event_definition、censoring_metadata、independent_splits 的选定来源、尺度、完整分母及版本
- `design`：明确 time zero、删失、竞争风险、事件数和验证；避免不死时间及结局后特征
- `diagnostics`：检查比例风险、校准、时间依赖指标和删失权重
- `sensitivity`：风险定义、竞争风险、时间窗与外部验证敏感性

**必需输出**：`survival_predictions`、`survival_diagnostics`、`survival_calibration`、`censoring_checks`

**解释边界**：风险关联不等于治疗效果，C-index 不代表校准。

**原方法参考**：[survival_docs](https://scikit-survival.readthedocs.io/en/stable/user_guide/evaluating-survival-models.html)


### 冻结模型的外部验证 (`external_validation`)

**问题**：冻结模型对独立目标人群能否推广？

**服务器方法候选**：scikit-learn frozen estimator

**输入前提**：`frozen_model`、`independent_validation_cohort`、`frozen_preprocessing`

**必须作出的决定**：`model_lock`、`validation_population`、`update_policy`

**专用 QC**：

- `input`：核对 frozen_model、independent_validation_cohort、frozen_preprocessing 的选定来源、尺度、完整分母及版本
- `design`：禁止外部队列重新选特征或阈值；校准更新需另列分析
- `diagnostics`：检查训练重叠、输入映射、预测失败、漂移及结局定义
- `sensitivity`：预设亚组、失败样本和不同适用范围的性能

**必需输出**：`external_predictions`、`model_lock`、`external_metrics`、`transportability_audit`

**解释边界**：外部验证只覆盖实际纳入的人群和测量条件。

**原方法参考**：[sklearn](https://scikit-learn.org/stable/common_pitfalls.html)


### 扰动签名相似与反向匹配 (`signature_matching`)

**问题**：哪些已知扰动签名与目标变化相似或相反？

**服务器方法候选**：CLUE Connectivity Map offline exports

**输入前提**：`approved_public_signature`、`perturbation_reference`、`direction_definition`

**必须作出的决定**：`matching_direction`、`reference_context`、`public_query_scope`

**专用 QC**：

- `input`：核对 approved_public_signature、perturbation_reference、direction_definition 的选定来源、尺度、完整分母及版本
- `design`：细胞系、剂量、时间和签名方向匹配；未知/私有签名不得自动外发
- `diagnostics`：检查映射、参考覆盖、排序统计、基线和细胞背景
- `sensitivity`：签名定义、细胞系/剂量/时间和候选稳定性

**必需输出**：`signature_matches`、`signature_context`、`signature_null`、`signature_sensitivity`

**解释边界**：反向表达签名不是疾病逆转、药效或安全性。

**原方法参考**：[clue](https://clue.io/connectopedia)


### 位点精细定位与可信集合 (`fine_mapping`)

**问题**：关联位点中哪些变异具有模型后验支持？

**服务器方法候选**：SuSiE；susieR

**输入前提**：`harmonized_summary`、`ancestry_matched_ld`、`locus_definition`

**必须作出的决定**：`ld_population`、`signal_prior`、`locus_window`

**专用 QC**：

- `input`：核对 harmonized_summary、ancestry_matched_ld、locus_definition 的选定来源、尺度、完整分母及版本
- `design`：LD、祖源、样本量、等位基因与参考构建一致；允许多信号
- `diagnostics`：检查 LD/统计量一致性、等位基因、收敛与集合纯度
- `sensitivity`：LD 来源、信号数与先验敏感性

**必需输出**：`variant_pip`、`credible_sets`、`ld_diagnostics`、`finemap_sensitivity`

**解释边界**：PIP 是模型条件下概率，不直接指定效应基因。

**原方法参考**：[susie](https://stephenslab.github.io/susieR/)


### 多信号共定位 (`colocalization`)

**问题**：两个关联信号是否支持共享因果变异候选？

**服务器方法候选**：coloc；coloc.susie

**输入前提**：`harmonized_trait_qtl`、`locus_definition`、`ancestry_matched_ld`

**必须作出的决定**：`prior_grid`、`signal_model`、`overlap_definition`

**专用 QC**：

- `input`：核对 harmonized_trait_qtl、locus_definition、ancestry_matched_ld 的选定来源、尺度、完整分母及版本
- `design`：共享变异全集、样本重叠、信号数和先验明确
- `diagnostics`：检查等位基因、缺失变异、LD、QTL 强度及全部假设后验
- `sensitivity`：先验、位点窗口、单/多信号及 LD 敏感性

**必需输出**：`coloc_hypotheses`、`shared_variant_set`、`signal_pairs`、`coloc_sensitivity`

**解释边界**：共定位不自动证明基因介导、方向或 MR 假设成立。

**原方法参考**：[coloc](https://chr1swallace.github.io/coloc/)


### 工具变量与两样本 MR 审查 (`two_sample_mr`)

**问题**：在可辩护工具变量假设下暴露与结局是否关联？

**服务器方法候选**：TwoSampleMR

**输入前提**：`instrument_evidence`、`harmonized_trait_qtl`、`ancestry_matched_ld`

**必须作出的决定**：`instrument_selection`、`overlap_policy`、`pleiotropy_plan`

**专用 QC**：

- `input`：核对 instrument_evidence、harmonized_trait_qtl、ancestry_matched_ld 的选定来源、尺度、完整分母及版本
- `design`：预先审相关性、独立性、排除限制、样本重叠、弱工具与祖源
- `diagnostics`：检查 F 统计、回文位点、方向、异质性、多效性及共定位证据
- `sensitivity`：留一、稳健估计、方向与工具选择敏感性；方法选择取决于工具数

**必需输出**：`mr_estimates`、`instrument_audit`、`mr_assumption_checks`、`mr_sensitivity`

**解释边界**：多个估计器一致不能证明排除限制成立。

**原方法参考**：[twosamplemr](https://mrcieu.github.io/TwoSampleMR/)


### 稀有变异聚合关联 (`rare_variant_burden`)

**问题**：基因或掩膜中的稀有变异负担是否关联结局？

**服务器方法候选**：SKAT；SAIGE-GENE+

**输入前提**：`variant_qc`、`ancestry_kinship`、`functional_masks`

**必须作出的决定**：`mask_definition`、`frequency_reference`、`relatedness_model`

**专用 QC**：

- `input`：核对 variant_qc、ancestry_kinship、functional_masks 的选定来源、尺度、完整分母及版本
- `design`：频率/功能掩膜预先定义；亲缘、病例失衡和祖源受控
- `diagnostics`：检查可调用区域、携带者数、批次、掩膜及校准
- `sensitivity`：频率阈值、掩膜、单变异驱动与祖源分层

**必需输出**：`burden_results`、`variant_masks`、`carrier_counts`、`burden_calibration`

**解释边界**：聚合关联不说明所有变异作用方向一致。

**原方法参考**：[skat](https://cran.r-project.org/web/packages/SKAT/index.html)


### 多基因评分与迁移性 (`polygenic_score`)

**问题**：独立目标人群中遗传评分是否有可重复预测价值？

**服务器方法候选**：PRSice-2；LDpred2

**输入前提**：`discovery_gwas`、`target_genotypes`、`ancestry_matched_ld`

**必须作出的决定**：`discovery_overlap`、`ancestry_scope`、`calibration_target`

**专用 QC**：

- `input`：核对 discovery_gwas、target_genotypes、ancestry_matched_ld 的选定来源、尺度、完整分母及版本
- `design`：发现/训练/验证无重叠；祖源、LD、协变量及绝对风险校准分开
- `diagnostics`：检查等位基因、重叠、群体结构、基线及校准
- `sensitivity`：祖源、LD、阈值和外部验证敏感性

**必需输出**：`prs_weights`、`prs_predictions`、`prs_metrics`、`prs_overlap_audit`

**解释边界**：PRS 不是个体诊断或因果效应估计。

**原方法参考**：[prsice](https://choishingwan.github.io/PRSice/)


### 差异峰、结合与可及性 (`differential_binding`)

**问题**：区域信号在条件之间是否改变？

**服务器方法候选**：DiffBind；csaw

**输入前提**：`consensus_peak_counts`、`library_controls`、`replicate_design`

**必须作出的决定**：`consensus_regions`、`normalization_basis`、`control_definition`

**专用 QC**：

- `input`：核对 consensus_peak_counts、library_controls、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：独立重复、输入/IgG、共识区域和归一化假设明确；全局变化需外源依据
- `diagnostics`：检查 FRiP、复杂度、片段、spike-in、重复一致性及背景
- `sensitivity`：峰集、归一化与低计数过滤敏感性

**必需输出**：`differential_regions`、`consensus_peak_set`、`binding_normalization`、`binding_diagnostics`

**解释边界**：峰强度与蛋白结合/可及性含义依协议而异。

**原方法参考**：[diffbind](https://bioconductor.org/packages/release/bioc/html/DiffBind.html)


### 峰—基因关联与顺式候选 (`peak_gene_links`)

**问题**：哪些峰与基因表达存在可复核顺式关联？

**服务器方法候选**：Signac LinkPeaks；ArchR

**输入前提**：`matched_rna_atac`、`genomic_mapping`、`donor_structure`

**必须作出的决定**：`pairing_definition`、`cis_window`、`background_model`

**专用 QC**：

- `input`：核对 matched_rna_atac、genomic_mapping、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：匹配单位、距离窗口和受检峰基因全集明确，控制深度与组成
- `diagnostics`：检查构建、TSS、窗口、GC/深度及供者混杂
- `sensitivity`：距离、背景和供者留出敏感性

**必需输出**：`peak_gene_links`、`peak_gene_universe`、`link_covariates`、`link_stability`

**解释边界**：相关不等于增强子因果靶基因。

**原方法参考**：[signac](https://stuartlab.org/signac/)


### Hi-C 环与 TAD 边界 (`hic_loops_tads`)

**问题**：接触富集或结构域边界是否稳健？

**服务器方法候选**：cooltools；HiCExplorer

**输入前提**：`balanced_contact_maps`、`resolution_metadata`、`replicate_design`

**必须作出的决定**：`bin_resolution`、`distance_background`、`boundary_definition`

**专用 QC**：

- `input`：核对 balanced_contact_maps、resolution_metadata、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：样本级重复、距离衰减和可比 bin 分辨率；bin 对不视为独立生物学重复
- `diagnostics`：检查平衡收敛、覆盖、距离、低可映射区域和边界
- `sensitivity`：分辨率、窗口及归一化敏感性

**必需输出**：`chromatin_loops`、`tad_boundaries`、`contact_expected`、`hic_sensitivity`

**解释边界**：空间接触不证明调控作用。

**原方法参考**：[cooltools](https://cooltools.readthedocs.io/en/latest/)


### DMR 与表达/注释整合 (`methylation_gene_links`)

**问题**：甲基化区域变化与基因/表达是否存在有条件关联？

**服务器方法候选**：DMRcate；bsseq

**输入前提**：`methylation_qc`、`region_mapping`、`expression_context`

**必须作出的决定**：`methylation_scale`、`region_definition`、`composition_adjustment`

**专用 QC**：

- `input`：核对 methylation_qc、region_mapping、expression_context 的选定来源、尺度、完整分母及版本
- `design`：beta/M 值、覆盖权重、细胞组成和区域层级检验分开；匹配单位明确
- `diagnostics`：检查探针交叉反应、SNP、覆盖、构建、区域及效应尺度
- `sensitivity`：区域定义、组成调整和注释敏感性

**必需输出**：`dmr_effects`、`dmr_gene_mapping`、`methylation_expression`、`methylation_sensitivity`

**解释边界**：甲基化方向不普遍等同于表达抑制或因果。

**原方法参考**：[dmrcate](https://bioconductor.org/packages/release/bioc/html/DMRcate.html)


### A/B compartment 与切换 (`hic_compartments`)

**问题**：一致定向和分辨率下 compartment 是否改变？

**服务器方法候选**：cooltools eigs-cis

**输入前提**：`balanced_contact_maps`、`compartment_orientation`、`replicate_design`

**必须作出的决定**：`orientation_signal`、`bin_resolution`、`eigenvector_rule`

**专用 QC**：

- `input`：核对 balanced_contact_maps、compartment_orientation、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：PC 符号需外部信号定向；按样本检验并保留不确定区
- `diagnostics`：检查距离背景、染色体、特征向量选择及低覆盖 bins
- `sensitivity`：分辨率、定向信号与PC选择敏感性

**必需输出**：`compartment_scores`、`compartment_switches`、`orientation_evidence`、`compartment_sensitivity`

**解释边界**：PC 符号可任意翻转，未经定向不能称 A/B 切换。

**原方法参考**：[cooltools](https://cooltools.readthedocs.io/en/latest/)


### 配对 Ribo/RNA 翻译效率 (`translation_efficiency`)

**问题**：Ribo 与 RNA 条件交互是否支持翻译变化？

**服务器方法候选**：RiboDiff；DESeq2 interaction design

**输入前提**：`paired_ribo_rna`、`psite_qc`、`replicate_design`

**必须作出的决定**：`interaction_estimand`、`psite_definition`、`matched_samples`

**专用 QC**：

- `input`：核对 paired_ribo_rna、psite_qc、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：配对样本、assay×condition 交互；不能直接比较两次显著性或简单比值检验
- `diagnostics`：检查读长、三核苷酸周期、P-site、rRNA、CDS 覆盖和 RNA 匹配
- `sensitivity`：读长过滤、CDS 范围、低计数及模型敏感性

**必需输出**：`translation_interactions`、`ribo_rna_pairs`、`periodicity_qc`、`translation_sensitivity`

**解释边界**：Ribo 占据不直接等于蛋白生成速率。

**原方法参考**：[riboseq](https://nf-co.re/riboseq/1.2.0/)


### uORF 与候选翻译 ORF (`uorf_translation`)

**问题**：候选 ORF 是否具有翻译相关周期性证据？

**服务器方法候选**：RiboTaper；RiboCode

**输入前提**：`ribo_periodicity`、`transcript_annotation`、`start_site_context`

**必须作出的决定**：`orf_universe`、`periodicity_rule`、`annotation_scope`

**专用 QC**：

- `input`：核对 ribo_periodicity、transcript_annotation、start_site_context 的选定来源、尺度、完整分母及版本
- `design`：固定受检 ORF 集及多重比较；异构体映射和可识别性审查
- `diagnostics`：检查 frame、周期、起止覆盖与重复支持
- `sensitivity`：注释、ORF边界、读长和周期阈值敏感性

**必需输出**：`candidate_orfs`、`orf_periodicity`、`orf_mapping`、`orf_controls`

**解释边界**：翻译迹象不证明稳定蛋白或功能。

**原方法参考**：[ribocode](https://github.com/xryanglab/RiboCode)


### 激酶—底物活性候选 (`kinase_activity`)

**问题**：底物位点模式是否支持激酶活性候选？

**服务器方法候选**：decoupleR；KSEA

**输入前提**：`localized_phosphosites`、`kinase_substrate_reference`、`protein_abundance`

**必须作出的决定**：`substrate_resource`、`localization_rule`、`protein_adjustment`

**专用 QC**：

- `input`：核对 localized_phosphosites、kinase_substrate_reference、protein_abundance 的选定来源、尺度、完整分母及版本
- `design`：位点定位、底物覆盖和总蛋白调整明确，按生物学单位检验
- `diagnostics`：检查位点映射、缺失机制、总蛋白与底物方向
- `sensitivity`：资源/覆盖/总量调整敏感性

**必需输出**：`kinase_scores`、`kinase_coverage`、`protein_adjustment`、`kinase_sensitivity`

**解释边界**：底物模式不是激酶直接活性测定。

**原方法参考**：[decoupler](https://github.com/saezlab/decoupler-py)、[msstatsptm](https://bioconductor.org/packages/release/bioc/html/MSstatsPTM.html)


### PTM 相对总蛋白变化 (`ptm_adjustment`)

**问题**：PTM 变化是否超过对应蛋白总量变化？

**服务器方法候选**：MSstatsPTM

**输入前提**：`matched_ptm_protein`、`localized_phosphosites`、`replicate_design`

**必须作出的决定**：`paired_protein_definition`、`ptm_scale`、`missingness_model`

**专用 QC**：

- `input`：核对 matched_ptm_protein、localized_phosphosites、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：配对映射、尺度和缺失机制明确；调整后不自动代表位点占有率
- `diagnostics`：检查定位概率、蛋白组映射、重复肽及调整不确定性
- `sensitivity`：蛋白汇总、缺失和定位阈值敏感性

**必需输出**：`adjusted_ptm_effects`、`total_protein_effects`、`ptm_mapping`、`ptm_uncertainty`

**解释边界**：没有占有率测量时不能声称绝对磷酸化比例。

**原方法参考**：[msstatsptm](https://bioconductor.org/packages/release/bioc/html/MSstatsPTM.html)


### 复合体丰度与协调变化 (`protein_complexes`)

**问题**：已注释复合体成员是否协调变化？

**服务器方法候选**：MSstats；CORUM membership review

**输入前提**：`protein_abundance`、`complex_membership`、`replicate_design`

**必须作出的决定**：`complex_resource`、`coverage_rule`、`aggregation_definition`

**专用 QC**：

- `input`：核对 protein_abundance、complex_membership、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：复合体定义、成员覆盖及缺失结构明确；蛋白共享肽不可重复计数
- `diagnostics`：检查成员数、方向不一致、共享肽与批次
- `sensitivity`：成员覆盖、汇总方法和资源版本敏感性

**必需输出**：`complex_effects`、`complex_coverage`、`member_effects`、`complex_sensitivity`

**解释边界**：共丰度不证明复合体组装或直接互作。

**原方法参考**：[msstats](https://bioconductor.org/packages/release/bioc/html/MSstats.html)


### 蛋白基因组与变异肽证据 (`proteogenomic_links`)

**问题**：变异/异构体是否具有可定位肽段支持？

**服务器方法候选**：OpenMS proteogenomics review

**输入前提**：`matched_variant_transcript`、`peptide_spectrum_evidence`、`decoy_strategy`

**必须作出的决定**：`search_database`、`decoy_definition`、`peptide_uniqueness`

**专用 QC**：

- `input`：核对 matched_variant_transcript、peptide_spectrum_evidence、decoy_strategy 的选定来源、尺度、完整分母及版本
- `design`：搜索空间、target-decoy 和分层 FDR明确；转录和肽证据独立报告
- `diagnostics`：检查谱图、独特性、蛋白推断、序列版本及污染
- `sensitivity`：数据库扩展、竞争肽和独立谱图验证

**必需输出**：`variant_peptide_links`、`peptide_spectrum_index`、`search_space_fdr`、`proteogenomic_controls`

**解释边界**：扩展数据库命中不是功能或表达量证明。

**原方法参考**：[openms](https://openms.de/)


### MOFA 潜在因子与视图解释 (`mofa_factors`)

**问题**：多个视图共享和特有变异由哪些因子解释？

**服务器方法候选**：MOFA2

**输入前提**：`matched_sample_views`、`view_scales`、`missing_view_design`

**必须作出的决定**：`view_scaling`、`factor_count`、`missing_view_policy`

**专用 QC**：

- `input`：核对 matched_sample_views、view_scales、missing_view_design 的选定来源、尺度、完整分母及版本
- `design`：样本/供者对齐、缺失视图和视图权重明确；因子与结局关联另作检验
- `diagnostics`：检查收敛、视图方差、载荷、缺失模式及批次驱动
- `sensitivity`：随机种子、因子数、缩放及视图留出敏感性

**必需输出**：`factor_scores`、`factor_loadings`、`view_variance`、`factor_stability`

**解释边界**：潜在因子不是自动发现的机制或因果轴。

**原方法参考**：[mofa](https://biofam.github.io/MOFA2/)


### 监督式多组学整合 (`supervised_multiomics`)

**问题**：多视图组合是否提供可验证预测增益？

**服务器方法候选**：mixOmics DIABLO

**输入前提**：`matched_sample_views`、`outcome_definition`、`independent_splits`

**必须作出的决定**：`split_unit`、`view_weighting`、`feature_selection_scope`

**专用 QC**：

- `input`：核对 matched_sample_views、outcome_definition、independent_splits 的选定来源、尺度、完整分母及版本
- `design`：全部特征选择/调参在训练折内；与单视图基线同划分比较
- `diagnostics`：检查视图匹配、类别失衡、泄漏及视图缺失
- `sensitivity`：视图消融、嵌套验证和外部验证

**必需输出**：`multiview_predictions`、`multiview_weights`、`single_view_baselines`、`multiview_validation`

**解释边界**：监督分离图不是泛化性能证据。

**原方法参考**：[mixomics](https://mixomics.org/mixdiablo/)


### RNA—蛋白/代谢关联与不一致 (`rna_protein_concordance`)

**问题**：不同模态的变化是否一致或存在可解释差异？

**服务器方法候选**：matched effects and sample-level models

**输入前提**：`matched_sample_views`、`feature_crosswalk`、`uncertainty_estimates`

**必须作出的决定**：`matching_unit`、`effect_scale`、`mapping_policy`

**专用 QC**：

- `input`：核对 matched_sample_views、feature_crosswalk、uncertainty_estimates 的选定来源、尺度、完整分母及版本
- `design`：相关单位、时间尺度、标识映射及效应不确定性明确
- `diagnostics`：检查多对多映射、缺失选择、动态范围与测量误差
- `sensitivity`：匹配方式、时滞、缺失及稳健模型敏感性

**必需输出**：`cross_modal_effects`、`crosswalk_audit`、`discordant_features`、`concordance_sensitivity`

**解释边界**：不一致可能来自测量和时间差，不能直接称翻译后调控。

**原方法参考**：[mofa](https://biofam.github.io/MOFA2/)


### 有条件的中介分析审查 (`multiomics_mediation`)

**问题**：在明确假设下能否定义和估计间接效应？

**服务器方法候选**：mediation

**输入前提**：`temporal_order`、`confounder_design`、`mediation_identifiability`

**必须作出的决定**：`causal_estimand`、`temporal_order`、`confounding_assumptions`

**专用 QC**：

- `input`：核对 temporal_order、confounder_design、mediation_identifiability 的选定来源、尺度、完整分母及版本
- `design`：定义直接/间接效应、时序、暴露后混杂、测量误差及可识别性
- `diagnostics`：检查模型、支持域、缺失、交互和未测混杂假设
- `sensitivity`：未测混杂、模型形式与测量误差敏感性

**必需输出**：`mediation_estimands`、`mediation_effects`、`mediation_assumptions`、`mediation_sensitivity`

**解释边界**：横断面多组学相关不能直接建立中介因果链。

**原方法参考**：[mediation](https://cran.r-project.org/web/packages/mediation/index.html)


### 跨研究效应综合与异质性 (`cross_study_meta`)

**问题**：可比研究效应是否一致，异质性来自哪里？

**服务器方法候选**：metafor

**输入前提**：`study_effect_uncertainty`、`cohort_independence`、`comparable_estimands`

**必须作出的决定**：`effect_scale`、`overlap_policy`、`heterogeneity_model`

**专用 QC**：

- `input`：核对 study_effect_uncertainty、cohort_independence、comparable_estimands 的选定来源、尺度、完整分母及版本
- `design`：确认效应尺度、方向、重复队列和目标人群；研究数限制元回归
- `diagnostics`：检查 SE/CI、效应方向、队列重叠、影响点与选择性报告
- `sensitivity`：留一研究、模型/尺度选择及小样本稳健性

**必需输出**：`meta_effects`、`heterogeneity`、`overlap_matrix`、`meta_influence`

**解释边界**：综合不可比对象不会创造共同估计目标。

**原方法参考**：[metafor](https://www.metafor-project.org/doku.php)


### Milo 细胞邻域差异丰度 (`singlecell_abundance`)

**问题**：细胞状态邻域相对丰度是否改变？

**服务器方法候选**：miloR

**输入前提**：`cell_neighborhoods`、`donor_counts`、`replicate_design`

**必须作出的决定**：`neighborhood_definition`、`sample_offset`、`graph_parameters`

**专用 QC**：

- `input`：核对 cell_neighborhoods、donor_counts、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：以供者计数和设计检验；邻域重叠需适用的多重比较处理
- `diagnostics`：检查图结构、邻域覆盖、供者支持及批次
- `sensitivity`：邻域参数、图构建与供者留出敏感性

**必需输出**：`neighborhood_effects`、`neighborhood_counts`、`neighborhood_fdr`、`neighborhood_stability`

**解释边界**：相对丰度变化不证明细胞绝对增殖或死亡。

**原方法参考**：[milor](https://bioconductor.org/packages/release/bioc/vignettes/miloR/inst/doc/milo_demo.html)


### 微生物差异丰度与组成偏差 (`microbe_differential`)

**问题**：组成和测量偏差下哪些类群关联条件？

**服务器方法候选**：ANCOM-BC2；ALDEx2

**输入前提**：`taxon_counts`、`sampling_fraction_design`、`replicate_design`

**必须作出的决定**：`zero_policy`、`prevalence_filter`、`sampling_fraction_model`

**专用 QC**：

- `input`：核对 taxon_counts、sampling_fraction_design、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：零值/结构零、测序深度、协变量和重复测量处理明确
- `diagnostics`：检查污染、低流行率、零值、库大小与模型校准
- `sensitivity`：过滤、零值、偏差模型和批次敏感性

**必需输出**：`taxon_effects`、`structural_zero_audit`、`composition_diagnostics`、`taxon_sensitivity`

**解释边界**：相对丰度不等于绝对菌量或定植因果。

**原方法参考**：[ancombc](https://bioconductor.org/packages/release/bioc/html/ANCOMBC.html)


### α/β 多样性与群落差异 (`microbe_diversity`)

**问题**：样本内和样本间多样性是否关联预定因素？

**服务器方法候选**：vegan；phyloseq

**输入前提**：`taxon_counts`、`distance_definition`、`replicate_design`

**必须作出的决定**：`distance_metric`、`depth_policy`、`permutation_blocks`

**专用 QC**：

- `input`：核对 taxon_counts、distance_definition、replicate_design 的选定来源、尺度、完整分母及版本
- `design`：度量/深度处理明确；PERMANOVA 配合离散度审查及受限置换
- `diagnostics`：检查测序深度、距离、树映射、离散度与置换单位
- `sensitivity`：距离、过滤和深度处理敏感性

**必需输出**：`alpha_diversity`、`beta_distances`、`diversity_tests`、`dispersion_audit`

**解释边界**：显著 PERMANOVA 可能受组间离散度差异影响。

**原方法参考**：[vegan](https://cran.r-project.org/web/packages/vegan/index.html)


### 组成数据微生物关联网络 (`microbe_network`)

**问题**：哪些条件关联对组成效应和抽样稳健？

**服务器方法候选**：SPIEC-EASI

**输入前提**：`taxon_counts`、`prevalence_design`、`resampling_plan`

**必须作出的决定**：`zero_transform`、`regularization_selection`、`edge_stability`

**专用 QC**：

- `input`：核对 taxon_counts、prevalence_design、resampling_plan 的选定来源、尺度、完整分母及版本
- `design`：零值、稀疏性及独立样本量先审；边不是独立生物学重复
- `diagnostics`：检查流行率、正则化、网络稀疏度及批次
- `sensitivity`：过滤、正则化和重采样稳定性

**必需输出**：`microbe_edges`、`network_selection`、`microbe_network_stability`、`microbe_network_null`

**解释边界**：统计关联边不是生态互作或因果。

**原方法参考**：[spieceasi](https://github.com/zdk123/SpiecEasi)


### 细胞类型组成与差异比例 (`cell_fraction_contrasts`)

**问题**：细胞群组成如何随条件变化？

**服务器方法候选**：scCODA；propeller

**输入前提**：`sample_cell_counts`、`donor_structure`、`composition_denominator`

**必须作出的决定**：`reference_group`、`denominator_definition`、`annotation_resolution`

**专用 QC**：

- `input`：核对 sample_cell_counts、donor_structure、composition_denominator 的选定来源、尺度、完整分母及版本
- `design`：以供者/样本为单位，参考群、分母及缺失群明确；估计组成需传播不确定性
- `diagnostics`：检查供者支持、总细胞数、捕获偏差和参考群稳定性
- `sensitivity`：参考群、注释粒度、低丰度过滤与供者留出

**必需输出**：`cell_fraction_effects`、`cell_count_denominators`、`reference_group_audit`、`composition_sensitivity`

**解释边界**：捕获组成不等同于组织绝对细胞数。

**原方法参考**：[sccoda](https://sccoda.readthedocs.io/en/latest/)


### 微生物功能与通路丰度 (`microbe_pathways`)

**问题**：功能贡献及物种来源如何变化？

**服务器方法候选**：HUMAnN

**输入前提**：`functional_abundance`、`taxon_stratification`、`reference_database`

**必须作出的决定**：`abundance_unit`、`pathway_coverage`、`stratification_policy`

**专用 QC**：

- `input`：核对 functional_abundance、taxon_stratification、reference_database 的选定来源、尺度、完整分母及版本
- `design`：基因/通路长度、单位、未比对比例和组成模型明确
- `diagnostics`：检查数据库版本、覆盖、未归类及物种分层贡献
- `sensitivity`：数据库、归一化、检测阈值和分类分层敏感性

**必需输出**：`microbe_function_effects`、`stratified_function`、`unclassified_fraction`、`function_sensitivity`

**解释边界**：功能基因丰度不等于实际代谢通量。

**原方法参考**：[humann](https://github.com/biobakery/humann)


### 菌株分辨与群体结构 (`microbe_strain`)

**问题**：样本间菌株差异是否得到足够覆盖支持？

**服务器方法候选**：StrainPhlAn

**输入前提**：`species_marker_coverage`、`strain_reference`、`cohort_design`

**必须作出的决定**：`marker_coverage`、`mixed_strain_policy`、`tree_reference`

**专用 QC**：

- `input`：核对 species_marker_coverage、strain_reference、cohort_design 的选定来源、尺度、完整分母及版本
- `design`：混合菌株、覆盖和样本独立性明确；不自动推断传播方向
- `diagnostics`：检查标记覆盖、缺失、比对和系统树支持
- `sensitivity`：覆盖阈值、标记集合与参考敏感性

**必需输出**：`strain_profiles`、`strain_tree`、`strain_coverage`、`strain_sensitivity`

**解释边界**：遗传相似不能单独证明宿主间直接传播。

**原方法参考**：[strainphlan](https://github.com/biobakery/MetaPhlAn/wiki/StrainPhlAn-4)


### 微生物基因功能注释与上下文 (`microbe_gene_context`)

**问题**：现有序列/基因表支持哪些功能注释？

**服务器方法候选**：HUMAnN；eggNOG-mapper

**输入前提**：`assembled_gene_evidence`、`functional_reference`、`contamination_controls`

**必须作出的决定**：`annotation_threshold`、`reference_version`、`ambiguity_policy`

**专用 QC**：

- `input`：核对 assembled_gene_evidence、functional_reference、contamination_controls 的选定来源、尺度、完整分母及版本
- `design`：同源阈值、数据库版本、拷贝/丰度单位及可比背景明确
- `diagnostics`：检查污染、覆盖、同源歧义和上下文完整性
- `sensitivity`：参考版本、同源阈值和映射完整性敏感性

**必需输出**：`gene_function_annotations`、`gene_annotation_evidence`、`context_coverage`、`annotation_ambiguity`

**解释边界**：同源注释不证明功能表达、致病性或实验表型。

**原方法参考**：[eggnog](https://github.com/eggnogdb/eggnog-mapper)


### 脂质类别与链特征富集 (`lipid_class_enrichment`)

**问题**：脂质类别或链特征是否协调变化？

**服务器方法候选**：lipidr LSEA

**输入前提**：`lipid_identifications`、`tested_lipid_universe`、`lipid_effects`

**必须作出的决定**：`identity_level`、`lipid_background`、`class_definition`

**专用 QC**：

- `input`：核对 lipid_identifications、tested_lipid_universe、lipid_effects 的选定来源、尺度、完整分母及版本
- `design`：鉴定等级、同分异构和受检脂质背景明确；避免同一分子重复计数
- `diagnostics`：检查命名、类映射、链解析、检测覆盖和 FDR族
- `sensitivity`：鉴定等级、背景和类别粒度敏感性

**必需输出**：`lipid_set_results`、`lipid_universe`、`lipid_identity_audit`、`lipid_set_sensitivity`

**解释边界**：类别富集不是脂代谢通量。

**原方法参考**：[lipidr](https://bioconductor.org/packages/release/bioc/html/lipidr.html)


### 脂质链长与不饱和模式 (`lipid_chain_patterns`)

**问题**：链长/双键模式是否在独立样本中变化？

**服务器方法候选**：lipidr

**输入前提**：`lipid_chain_annotation`、`lipid_abundance`、`internal_standard_qc`

**必须作出的决定**：`chain_resolution`、`class_stratification`、`abundance_unit`

**专用 QC**：

- `input`：核对 lipid_chain_annotation、lipid_abundance、internal_standard_qc 的选定来源、尺度、完整分母及版本
- `design`：总碳/总双键与精确酰链分辨率分开；同分异构不可伪拆
- `diagnostics`：检查链注释等级、离子加合、内标及单位
- `sensitivity`：注释等级、类别分层和缺失处理敏感性

**必需输出**：`chain_pattern_effects`、`chain_annotation`、`chain_denominators`、`chain_sensitivity`

**解释边界**：总和注释不能定位具体脂肪酸或酶活性。

**原方法参考**：[lipidr](https://bioconductor.org/packages/release/bioc/html/lipidr.html)


### 表达推断的单细胞 CNV (`singlecell_cnv`)

**问题**：表达沿基因组的模式是否与大尺度 CNV 相容？

**服务器方法候选**：inferCNV；CopyKAT

**输入前提**：`ordered_expression`、`normal_reference`、`donor_structure`

**必须作出的决定**：`normal_reference`、`genomic_smoothing`、`dna_validation`

**专用 QC**：

- `input`：核对 ordered_expression、normal_reference、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：正常参考、肿瘤纯度及供者边界明确；表达程序偏倚单独审查
- `diagnostics`：检查参考污染、染色体排序、平滑尺度和周期程序
- `sensitivity`：正常参考、平滑、低表达与独立 DNA 验证

**必需输出**：`inferred_cnv_profiles`、`normal_reference_audit`、`cnv_diagnostics`、`dna_concordance`

**解释边界**：RNA 推断不是 DNA CNV 测量，不能单凭此认定恶性。

**原方法参考**：[infercnv](https://github.com/broadinstitute/infercnv)


### DNA 拷贝数与等位基因状态 (`bulk_cnv`)

**问题**：DNA 覆盖与等位基因证据支持何种拷贝状态？

**服务器方法候选**：CNVkit；FACETS

**输入前提**：`dna_depth_baf`、`matched_normal`、`purity_ploidy_design`

**必须作出的决定**：`normal_reference`、`purity_ploidy`、`segmentation_rule`

**专用 QC**：

- `input`：核对 dna_depth_baf、matched_normal、purity_ploidy_design 的选定来源、尺度、完整分母及版本
- `design`：平台、正常参考、纯度/倍性和分段模型明确
- `diagnostics`：检查覆盖噪声、BAF、性染色体、分段与纯度可识别性
- `sensitivity`：纯度/倍性解、分段和正常参考敏感性

**必需输出**：`copy_segments`、`allele_copy_states`、`purity_ploidy_solutions`、`cnv_validation`

**解释边界**：模型整数状态存在纯度/倍性歧义。

**原方法参考**：[cnvkit](https://cnvkit.readthedocs.io/en/stable/)


### 亚克隆组成与演化树 (`clonal_phylogeny`)

**问题**：哪些克隆结构与现有 VAF/CNV 相容？

**服务器方法候选**：PyClone-VI；PhyloWGS

**输入前提**：`variant_allele_counts`、`copy_number_context`、`purity_estimates`

**必须作出的决定**：`mutation_multiplicity`、`purity_solution`、`tree_constraints`

**专用 QC**：

- `input`：核对 variant_allele_counts、copy_number_context、purity_estimates 的选定来源、尺度、完整分母及版本
- `design`：多区域/时间对应、拷贝数、多重性及纯度不确定性明确
- `diagnostics`：检查后验、克隆数、约束、低覆盖及替代树
- `sensitivity`：克隆数、CNV/纯度解及抽样敏感性

**必需输出**：`clonal_fractions`、`candidate_phylogenies`、`clonality_uncertainty`、`phylogeny_constraints`

**解释边界**：一棵拟合树不证明唯一演化历史或传播路线。

**原方法参考**：[pyclone](https://github.com/Roth-Lab/pyclone-vi)


### TCR/BCR 克隆型与配对 (`repertoire_clonotypes`)

**问题**：哪些细胞属于何种明确规则的受体克隆型？

**服务器方法候选**：Scirpy

**输入前提**：`vdj_contigs`、`cell_barcode_mapping`、`receptor_protocol`

**必须作出的决定**：`receptor_type`、`chain_pairing`、`clonotype_rule`

**专用 QC**：

- `input`：核对 vdj_contigs、cell_barcode_mapping、receptor_protocol 的选定来源、尺度、完整分母及版本
- `design`：TCR/BCR、链配对、productive 和多链规则明确，供者分开
- `diagnostics`：检查条码、链数、doublet、序列完整性及测序深度
- `sensitivity`：核苷酸/氨基酸、链配对和距离定义敏感性

**必需输出**：`clonotype_assignments`、`chain_qc`、`barcode_crosswalk`、`clonotype_definition`

**解释边界**：相似受体序列不自动证明相同抗原特异性。

**原方法参考**：[scirpy](https://scirpy.scverse.org/en/latest/)


### 受体谱多样性与克隆扩增 (`repertoire_diversity`)

**问题**：供者层级受体谱多样性或扩增是否不同？

**服务器方法候选**：Scirpy

**输入前提**：`clonotype_counts`、`donor_structure`、`sampling_depth`

**必须作出的决定**：`diversity_metric`、`depth_matching`、`biological_unit`

**专用 QC**：

- `input`：核对 clonotype_counts、donor_structure、sampling_depth 的选定来源、尺度、完整分母及版本
- `design`：测序深度、抽样单位、克隆定义和检验族明确
- `diagnostics`：检查每供者细胞/克隆数、覆盖、稀有克隆和批次
- `sensitivity`：深度匹配、克隆规则和供者重采样

**必需输出**：`repertoire_diversity`、`expansion_summary`、`repertoire_sampling`、`diversity_sensitivity`

**解释边界**：捕获频率不是整体机体克隆频率。

**原方法参考**：[scirpy](https://scirpy.scverse.org/en/latest/)


### 克隆型—细胞状态关联 (`clonotype_phenotype`)

**问题**：克隆扩增与转录状态是否关联？

**服务器方法候选**：Scirpy

**输入前提**：`clonotype_assignments`、`frozen_cell_states`、`donor_structure`

**必须作出的决定**：`state_definition`、`clone_dependence`、`permutation_unit`

**专用 QC**：

- `input`：核对 clonotype_assignments、frozen_cell_states、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：供者内克隆和细胞依赖需控制；不能把同克隆细胞当独立受试者
- `diagnostics`：检查状态注释、条码匹配、克隆大小及供者覆盖
- `sensitivity`：注释、克隆规则和供者/克隆重采样

**必需输出**：`clone_state_associations`、`clone_state_counts`、`clone_dependence`、`clone_state_sensitivity`

**解释边界**：状态关联不证明抗原特异性或谱系转换。

**原方法参考**：[scirpy](https://scirpy.scverse.org/en/latest/)


### 空间变异基因与空间零模型 (`spatial_variable_genes`)

**问题**：基因表达是否偏离预定空间零模型？

**服务器方法候选**：SPARK-X；SpatialDE

**输入前提**：`registered_coordinates`、`expression_scale`、`tissue_boundaries`

**必须作出的决定**：`spatial_kernel`、`tissue_mask`、`sample_replication`

**专用 QC**：

- `input`：核对 registered_coordinates、expression_scale、tissue_boundaries 的选定来源、尺度、完整分母及版本
- `design`：切片内空间相关、供者重复及受检全集明确
- `diagnostics`：检查坐标单位、表达深度、组织掩膜、边界和模型校准
- `sensitivity`：空间核、尺度、组织分区与切片复现

**必需输出**：`spatial_gene_tests`、`spatial_kernel`、`spatial_gene_qc`、`spatial_gene_replication`

**解释边界**：空间变异不等于条件差异或细胞特异性。

**原方法参考**：[sparkx](https://github.com/xzhoulab/SPARK)


### 邻域富集与组织生态位 (`spatial_niches`)

**问题**：细胞类型邻接是否超过组织约束下预期？

**服务器方法候选**：Squidpy neighborhood enrichment

**输入前提**：`registered_coordinates`、`frozen_cell_states`、`tissue_boundaries`

**必须作出的决定**：`neighborhood_definition`、`permutation_constraint`、`density_control`

**专用 QC**：

- `input`：核对 registered_coordinates、frozen_cell_states、tissue_boundaries 的选定来源、尺度、完整分母及版本
- `design`：按供者/切片分层，组织分区内置换并保留密度/边界约束
- `diagnostics`：检查邻域构建、半径、密度、掩膜及稀有类型
- `sensitivity`：半径、kNN/距离、注释粒度和受限置换敏感性

**必需输出**：`neighborhood_enrichment`、`spatial_graph`、`constrained_null`、`niche_stability`

**解释边界**：邻近不证明通信或功能依赖。

**原方法参考**：[squidpy](https://squidpy.readthedocs.io/en/stable/)


### 组织边界距离与空间梯度 (`spatial_gradients`)

**问题**：表达或组成是否随预定组织距离变化？

**服务器方法候选**：Squidpy spatial graph；mgcv

**输入前提**：`registered_coordinates`、`reviewed_tissue_boundaries`、`donor_structure`

**必须作出的决定**：`boundary_definition`、`physical_unit`、`spatial_dependence`

**专用 QC**：

- `input`：核对 registered_coordinates、reviewed_tissue_boundaries、donor_structure 的选定来源、尺度、完整分母及版本
- `design`：边界独立定义、物理单位和供者内空间相关；避免用表达先选边界再检验
- `diagnostics`：检查配准、边界误差、距离方向、采样密度和残差
- `sensitivity`：边界扰动、距离窗口与供者留出

**必需输出**：`distance_gradients`、`boundary_coordinates`、`spatial_residuals`、`gradient_sensitivity`

**解释边界**：距离梯度不是时间进程或因果暴露。

**原方法参考**：[squidpy](https://squidpy.readthedocs.io/en/stable/)


### 空间域与组织学一致性 (`spatial_domains`)

**问题**：空间域是否稳定且与独立组织学相符？

**服务器方法候选**：BayesSpace；BANKSY

**输入前提**：`registered_coordinates`、`expression_scale`、`independent_histology`

**必须作出的决定**：`domain_count`、`spatial_weight`、`histology_validation`

**专用 QC**：

- `input`：核对 registered_coordinates、expression_scale、independent_histology 的选定来源、尺度、完整分母及版本
- `design`：聚类与独立验证分开；域数选择不能依期望结论
- `diagnostics`：检查配准、图结构、批次、域覆盖及组织学一致性
- `sensitivity`：域数、空间权重、分辨率和切片留出敏感性

**必需输出**：`spatial_domains`、`domain_parameters`、`histology_concordance`、`domain_stability`

**解释边界**：域边界不自动等于细胞谱系或病理诊断。

**原方法参考**：[bayesspace](https://bioconductor.org/packages/release/bioc/html/BayesSpace.html)

## 版本和归属

官方参考核对日期为 2026-10-10，观察到的文档版本不能替代执行版本。固定实际 pipeline 版本、方法参数、参考数据库及软件/容器版本，并复用已有服务器环境。quantms 旧 nf-core 页面已标注归档，仅作历史方法参考；现有质谱软件需单独验收，不自动安装旧入口。

本目录没有复制第三方 pipeline、脚本、权重或数据库，也没有把第三方算法当作本项目原创。公开合成契约测试验证拒绝/一致性语义，不表示所有组学后端已真实运行或得出有效科学结论。
