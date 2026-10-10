# 组学标准流程与条件拓展

这是 BioResearchWorkbench 原创的流程、QC 和结果契约，最初工具基础来自 Biomni。第三方算法、文档和数据库保留原归属。本页从 `omics_workflows.json` 自动生成。

版本 2.14.0：28 条流程、21 类拓展、108 个流程到拓展的关联。关联数量不是独立算法或已经验收的执行后端。

## 调用与状态

- `omics_workflows.inspect_omics_workflows(workflow="", family="", detail=false, limit=40)`：离线发现目录；完整细节包括标准步骤、QC、输出角色和官方参考。
- `omics_workflows.plan_omics_workflow(workflow, context, design, input_manifest, extensions=null)`：只生成绑定版本的计划，拓展必须主动选择。
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
| `bulk_rna` | Bulk RNA-seq | raw_reads, raw_counts | pathway, ppi, coexpression, deconvolution, splicing, timecourse, prediction, multiomics |
| `scrna` | 单细胞/单核 RNA-seq | raw_reads, raw_counts | pathway, ppi, trajectory, velocity, communication, regulatory, composition, repertoire, multiomics |
| `spatial_rna` | 空间转录组 | raw_counts, segmented_features | pathway, deconvolution, communication, regulatory, multiomics |
| `small_rna` | small RNA / miRNA | raw_reads, raw_counts | pathway, ppi, multiomics |
| `long_read_rna` | 长读长 RNA 与异构体 | raw_reads, aligned_reads, transcript_models | splicing, pathway, multiomics |
| `splicing` | 可变剪接 / DTU | junction_counts, transcript_counts | pathway, ppi, multiomics |
| `riboseq` | Ribo-seq / 翻译组 | raw_reads, aligned_reads, footprint_counts | te, pathway, timecourse |
| `clipseq` | CLIP / RNA 结合 | raw_reads, aligned_reads, peak_counts | splicing, regulatory, multiomics |
| `expression_array` | 表达芯片 | raw_intensity, normalized_expression | pathway, ppi, coexpression, deconvolution, prediction |
| `bulk_atac` | ATAC-seq | raw_reads, fragments, peak_counts | regulatory, chromatin_links, pathway, multiomics |
| `scatac` | 单细胞 ATAC-seq | fragments, peak_counts | regulatory, chromatin_links, multiomics, trajectory |
| `chipseq` | ChIP-seq | raw_reads, aligned_reads, peak_counts | regulatory, chromatin_links, pathway, multiomics |
| `cutandrun` | CUT&RUN / CUT&Tag | raw_reads, fragments, peak_counts | regulatory, chromatin_links, pathway, multiomics |
| `methylseq` | WGBS / RRBS / EM-seq | raw_reads, methylation_counts | pathway, regulatory, multiomics |
| `methylation_array` | 甲基化芯片 | raw_intensity, methylation_beta, methylation_m | pathway, regulatory, multiomics, prediction |
| `hic` | Hi-C / 三维基因组 | raw_reads, contact_pairs, contact_matrix | chromatin_links, regulatory, multiomics |
| `germline` | 胚系 WGS / WES / panel | raw_reads, aligned_reads, variants | sv_cnv, genetic_causality |
| `somatic` | 体细胞 WGS / WES / panel | raw_reads, aligned_reads, variants | sv_cnv, pathway |
| `gwas_qtl` | GWAS / eQTL / sQTL | genotypes, summary_statistics | genetic_causality, pathway |
| `proteomics` | DDA / DIA / TMT 蛋白组 | mass_spectra, peptide_abundance, protein_abundance | pathway, ppi, coexpression, multiomics, prediction |
| `phosphoproteomics` | 磷酸化 / PTM 组 | site_abundance, mass_spectra | protein_activity, pathway, ppi, multiomics |
| `metabolomics` | 靶向 / 非靶向代谢组 | mass_spectra, feature_abundance, concentration | pathway, multiomics, prediction |
| `lipidomics` | 脂质组 | mass_spectra, feature_abundance, concentration | lipid_classes, pathway, multiomics |
| `amplicon` | 16S / ITS 扩增子 | raw_reads, feature_counts | composition, timecourse, multiomics |
| `metagenomics` | 宏基因组概况 | raw_reads, taxonomic_abundance | composition, functional_profile, multiomics |
| `singlecell_multiome` | 单细胞多模态 / CITE / RNA+ATAC | modality_matrices | regulatory, chromatin_links, trajectory, communication, multiomics |
| `multiomics` | Bulk 多组学整合 | modality_matrices | pathway, ppi, prediction, genetic_causality |
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

## 版本和归属

官方参考核对日期为 2026-10-10，观察到的文档版本不能替代执行版本。固定实际 pipeline 版本、方法参数、参考数据库及软件/容器版本，并复用已有服务器环境。quantms 旧 nf-core 页面已标注归档，仅作历史方法参考；现有质谱软件需单独验收，不自动安装旧入口。

本目录没有复制第三方 pipeline、脚本、权重或数据库，也没有把第三方算法当作本项目原创。公开合成契约测试验证拒绝/一致性语义，不表示所有组学后端已真实运行或得出有效科学结论。
