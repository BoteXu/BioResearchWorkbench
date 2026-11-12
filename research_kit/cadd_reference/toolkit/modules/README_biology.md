# I16 至 I22 计算生物学增量模块数据契约

本目录的七个 JSON 文件是可填写的数据契约草稿。所有实际数据行均为空，`null` 表示待填写，`row_template` 是字段样板而非一条观测。它们不包含示例患者、假设样本、虚构效应、预测结果或已完成分析。`schema_version` 是本项目契约的版本，并不表示这些文件已经过独立 JSON Schema 或科学有效性验证。

这些模板没有配套的自动统计验收器，也不会调用数据库、提交模拟、训练模型或生成研究结论。JSON 能被解析只说明语法正确；身份、设计、数值单位、来源和科学适用性仍须按手册 I16–I22 审阅。

## 一般填写方式

1. 复制所需文件作为当前项目配置，保留原 `.example.json` 不变。
2. 填写 `project_id` 和 `release_id`。复制 `row_template` 的字段结构到 `rows`，加入真实记录后再填写其值。不要把样板对象本身计入数据行。
3. `related_tables` 是相关表，每张表也有空 `rows` 和独立 `row_template`。先在相关表建立真实实体，再填写引用它的 ID。一个 ID 必须在该表定义的唯一键范围内稳定；多对多关系保留独立行，不取第一条映射。
4. 无资料、未测、低覆盖、不适用和测定失败分别记录，不用零代替。允许缺失的字段使用 `null` 并填写 `missing_reason`、`missing_fields` 或相关 QC 字段；不能用缺失原因绕过进入下一阶段所必需的身份信息。
5. 原始值和来源先保存，转换、合并及统计结果用新分析 ID 保存。旧发布数据与新测量分别留档，不能用后来结果覆盖预测时点的记录。
6. `status` 保持 `draft`，直到项目自行完成检查并记录审阅；这些模板不定义自动发布状态机，不要因填完表就宣称通过科学验收。

### 通用类型约定

| 类型 | 填写规则 |
|---|---|
| string | JSON 字符串；适用于 ID、名称、路径、版本、单位、描述、枚举值和公式。所有未另列类型的字段按 string 填写 |
| number | 有限数值，不允许 `NaN`、`Infinity`；数值与单位分开。删失符号另存 `relation` 等字段 |
| integer | 非小数整数；计数应非负，残基序号遵循所在编号体系，不能把插入码拼进数值字段 |
| boolean | 真实逻辑状态用 `true` 或 `false`；未知用 `null`，不能把未知默认写成 `false` |
| array | 数组；具体元素类型见各模块。`[]` 表示尚未录入或明确没有元素，二者含义在上下文注明 |
| object | 键值对象；嵌套字段含义见下文。不要把 JSON 对象编码成带引号的字符串 |
| null | 草稿中的待填项，或实际数据中被允许且明确解释的缺失。必需身份不允许在正式分析输入中仍为 `null` 或 `__FILL__` |

`schema_version`、`module_id`、`status`、`table_name`、`project_id`、`release_id` 为字符串；`rows` 为记录对象数组，`row_template`、`missing_fields`、`related_tables` 为对象。`missing_fields` 使用“字段名 → 缺失原因字符串”，例如只有实际无法取得信息时才填写相应原因；不能写成“通过”或填造一个数据值。

路径以项目根目录为参照，导出时记录根目录规则。`*_sha256` 必须是对应真实文件或明确序列规范化结果的 64 位十六进制摘要，不是文件名、目录摘要或手填标签。日期时间字段采用带时区的 ISO 8601；临床和样本标识使用项目允许的去标识 ID，不在模板中填入无必要的个人身份信息。

## I16_evidence.example.json

### 表和字段含义

主表 `target_evidence` 的行单位是一个原始研究中一个可解释的证据终点。`evidence_id` 为行唯一键，`study_id` 为研究 ID；`cohort_id` 和 `sample_overlap_group` 用于辨认样本重叠；`target_id` 与 `hypothesis_id` 连接实体和假说表。

| 字段组 | 类型与含义 | 必需条件 |
|---|---|---|
| `evidence_class`, `measured_entity`, `intervention_or_exposure`, `outcome` | string；说明证据类别、实测对象、干预/暴露与终点 | 每条实质证据必需；观察性资料没有干预时显式写明其性质 |
| `effect`, `effect_unit` | number 与 string；效应和单位 | 定量证据必需；仅定性证据允许效应缺失并解释 |
| `direction`, `context` | string；方向含义与物种、组织、条件背景 | 必需；方向不能仅凭效应正负猜测，应写比较顺序 |
| `uncertainty` | object；`kind`/`definition` 为 string，`level`/`lower`/`upper`/`standard_error` 为 number | 定量推断应给原文支持的不确定性；没有则明确缺失，不自行计算不存在的区间 |
| `source_url`, `source_release`, `limitations` | string；原始来源、来源版本/访问快照和限制 | 必需；来源不是搜索结果摘要的自编引文 |
| `entity_map.species_taxon` | integer；分类单元 ID | 实体必需 |
| `entity_map.gene_id_version`, `transcript_id_version`, `protein_accession_isoform` | string；带版本/异构体的原始 ID | 基因身份必需；转录本/蛋白形式在相关结论和结构计算前必需 |
| `sequence_path`, `sequence_sha256`, `construct_range`, `maturation_state`, `structure_id_chain` | string；序列、构建体范围、加工状态和结构链 | 进入结构分支时必需；范围明确是哪个序列上的编号 |
| `mapping_status`, `mapping_notes` | string；唯一、歧义、缺失及决策说明 | 映射审阅必需，歧义不得静默选第一条 |
| `hypothesis_register.evidence_ids` | array[string]；所用证据行 ID | 有证据的假说必需，不能填写无对应行的 ID |
| `statement`, `intended_direction`, `primary_readout`, `competing_explanation`, `decision_status`, `decision_reason` | string；可检验假说及决策 | 假说进入计算前必需；作用方向可明确为未知 |

`entity_map` 中的 `gene_symbol` 供显示；连接使用稳定 ID 和序列。`tissue`、`cell_type`、`disease_or_phenotype_id`、`source_release` 描述实际研究背景。`protein_form_id` 应连接项目确认的具体蛋白形式。

**错误例子。** 同一队列被两个数据库收录就计作两项独立支持；把最长转录本默认当作研究组织的主要异构体；把“基因上调”填成“抑制该蛋白已被验证有效”；把原文没有报告的置信区间补成零。这些均需在人工审阅中拒绝。

## I17_sample_design.example.json

### 样本表和设计计划

主表一行对应一个明确的技术文库及其生物样本，不自动等同一个独立供体。`dataset_id`、`donor_id`、`sample_id`、`technical_library_id` 必需；`library_relation_to_sample` 说明同一样本多文库如何处理。

| 字段组 | 类型与含义 | 必需条件 |
|---|---|---|
| `condition`, `tissue_region`, `assay_type`, `batch` | string；生物条件、区域、技术及技术批次 | 每个样本必需；未记录批次不能伪填为同一批次 |
| `sex`, `age_or_age_group`, `age_unit` | string；年龄可为 number，但必须有单位；年龄分组为 string | 按来源保留；拟调整协变量缺失时先定处理规则 |
| `paired_id`, `collection_context` | string；真实配对关系和采样背景 | 使用配对分析时配对 ID 必需；不得由样本名相近推定 |
| `raw_accession`, `counts_path`, `counts_sha256`, `gene_annotation_release` | string；真实数据和参考版本 | 计算输入必需；若无公开 accession，给内部可追溯来源 |
| `analysis_plan.biological_unit`, `design_formula`, `contrast_reference`, `contrast_test` | string；统计独立层级、模型与比较方向 | 正式统计前必需 |
| `pairing_definition`, `tissue_region_strategy`, `pseudobulk_grouping_definition` | string；配对、多区域和汇总单位 | 涉及对应设计时必需；非配对必须明确说明 |
| `covariates` | array[string] | 明确纳入的协变量；空数组必须来自设计决策而非遗漏 |
| `required_comparisons` | array[object]；每项说明比较 ID、参考、测试和对应细胞/区域 | 多比较项目必需；单比较也须在 contrast 字段定义 |
| `counts_layer`, `qc_release`, `annotation_release`, `feature_order_sha256` | string；原始计数层、QC/标签版本及特征顺序 | 使用分析对象时必需 |
| `frozen_reference_model_id`, `integration_role` | string；参考映射模型和整合用途 | 使用冻结参考时必需；不得把整合表示当作原始计数 |
| `cell_metadata.annotation_confidence` | number 或 string；必须说明数值定义或等级体系 | 用于标签过滤时必需 |
| `cell_metadata.qc_status`, `qc_reason`, `doublet_status`, `ambient_rna_processing` | string；QC、双细胞和环境 RNA 记录 | 相关技术适用时必需 |
| `spatial_metadata.x`, `y` | number；坐标 | 空间样本必需，配合 `coordinate_unit` |
| `section_id`, `image_path`, `image_sha256`, `coordinate_transform_id`, `segmentation_or_spot_definition` | string；切片、图像和坐标/观测定义 | 相应空间分析必需 |

细胞元数据的 `cell_id` 应项目内唯一，原始 `barcode` 必须连同样本/文库才能定位。空间记录的 `location_id` 为位置唯一键，不能用坐标数值替代供体标识。`analysis_plan` 是待审核设计，模板不会自动判断满秩或混杂。

**错误例子。** 给一名供体的两块组织生成两个新 `donor_id`；把 5,000 个细胞写成 5,000 个生物重复；疾病只在某批次出现却假定批次校正已恢复对照；用整合后的表达值冒充原始计数；把低覆盖细胞类型的表达设为零。

## I18_isoform_mapping.example.json

### 剪接事件及蛋白形式链条

主表 `splice_events` 一行是一项有固定坐标定义的事件及指定比较。事件唯一键至少需包含 `event_id` 与参考/注释版本及比较；如项目允许同一事件多比较，不能仅按 `event_id` 覆盖旧行。

| 字段组 | 类型与含义 | 必需条件 |
|---|---|---|
| `genome_build`, `annotation_release`, `event_type`, `chromosome`, `strand`, `coordinate_convention`, `event_coordinates` | string；事件和坐标体系 | 每个事件必需；明确 0/1 起点和区间闭开规则 |
| `junction_count_mode` | string；明确如工具实际 JC/JCEC 口径 | rMATS 等事件结果必需，不能混合口径 |
| `condition_reference`, `condition_test`, `delta_psi`, `psi_scale` | string、string、number、string；比较方向和 PSI 尺度 | 定量事件比较必需；尺度为 0–1 或百分比之一 |
| `p_value`, `adjusted_p_value` | number；范围 0–1 | 有统计检验时填写真实输出，缺失不得补零 |
| `test_family`, `coverage_rule`, `qc_status`, `qc_reason` | string；多重检验集合、覆盖规则和审阅结果 | 形成筛选结论前必需 |
| `analysis_context` | object；其字段均为 string | reads、链特异性、比对/参考、工具版本、组别和重复设计应可审阅 |
| `event_by_sample.inclusion_count`, `exclusion_count` | integer；非负读段/连接计数，须遵从工具口径 | 使用相关计数模型时必需 |
| `event_by_sample.psi` | number；与 `psi_scale` 一致 | 有足够支持时填写；无覆盖为 null 并写原因 |
| `transcript_evidence` 的所有字段 | string；转录本、序列、完整转录本支持、阅读框和蛋白证据 | 对事件作蛋白解释前必需；支持不足可明确为 unknown |
| `protein_forms` 的所有字段 | string；具体蛋白形式、序列、加工及环境 | 进入结构建模前必需；糖基化/膜环境状态按实际问题说明 |
| `residue_map.reference_residue_number`, `model_residue_number` | integer | 对应位置存在时必需；缺失为 null |
| `residue_map.author_residue_number` | string；保留结构作者编号 | 有实验结构时填写，`insertion_code` 另存 string |
| `residue_map` 其余字段 | string；参考/结构/模型身份、氨基酸和映射状态 | 每条有效映射必需；不可映射保留原因 |
| `model_plan` 的所有字段 | string；比较、共同拟合、口袋、环境及不确定性 | 结构分支前必需；不适用的字段明确说明 |

`site/position` 跨版本迁移须通过实际序列对齐，不能仅按整数相等连线。`premature_stop_status` 或 `protein_evidence_status` 是证据状态，不能从是否能预测结构自动产生。

**错误例子。** 单个 exon-skipping PSI 被填为完整蛋白异构体占比；没有覆盖时填 PSI=0；JC 和 JCEC 结果合并成重复；把参考残基 100 与作者编号 100 当作同一位置；删除一段原子后沿用未重建拓扑。

## I19_signature_query.example.json

### 查询和参考上下文

主表一行是一个查询签名中的一个基因。`query_id` 与带版本基因 ID 共同唯一；上游比较方向、细胞背景和签名生成规则由 `query_context` 定义。

| 字段组 | 类型与含义 | 必需条件 |
|---|---|---|
| `effect`, `rank_statistic`, `p_value`, `adjusted_p_value` | number | 对应方法有输出时填写，不能把不同量互相代替 |
| `effect_unit`, `rank_statistic_definition`, `direction`, `detection_status`, `source_analysis_id` | string | 查询形成前必需；方向关联 reference/test |
| `query_context.donor_count` | integer；独立供体数量 | 供体研究中必需，不能填写细胞数量 |
| `query_context.source_dataset_ids` | array[string] | 必需；连接实际来源 |
| `input_gene_space`, `reference_gene_space`, `mapping_release` | string；可比较特征空间和映射版本 | 查询前必需 |
| `signature_rule`, `signature_size_rule`, `primary_or_sensitivity`, `query_sha256` | string；查询冻结规则 | 主/敏感性分析须区分，不在看结果后覆盖主规则 |
| `reference_context.dose`, `time`, `qc_metric_value` | number；分别配合单位/指标名称 | 对应参考资料存在时必需；缺失标注来源局限 |
| `parent_id`, `state_id`, `perturbation_type`, `cell_line`, `database_release`, `feature_space` | string | 参考签名身份必需；不能只有药名 |
| `replicate_definition`, `qc_metric_name`, `qc_status`, `reference_file_sha256` | string | 复用和比较参考签名前必需 |
| `connectivity_results.score`, `p_value`, `adjusted_p_value` | number | 真实输出；原始值、tau 和 P 值不混存 |
| `score_name`, `score_definition`, `normalization_background_id`, `test_family`, `algorithm_version`, `computation_id` | string | 有得分的结果行必需 |
| `repurposing_decision`, `control_plan` 中各字段 | string | 将候选推进前填写实际审阅及预定对照规则 |

`score` 的允许数值范围由 `score_name` 和实际算法规定，模板不假定所有分数都在 0–1。`context_consistency` 记录各条件方向是否一致，不是自动投票结果。

**错误例子。** 把 tau=-95 写成 95% 疗效概率；同一药物仅保留最有利细胞/剂量结果；用未检出基因填零扩大交集；参考库改变后保留依赖旧背景的百分位或 FDR，却标为新库结果。

## I20_multiomics_pairs.example.json

### 测量与真实配对

主表 `assay_manifest` 一行是一个样本的一次明确组学测量。`assay_id` 唯一，`donor_id`、`sample_id`、`modality`、`condition`、`batch`、原始文件和测量尺度必需。技术重复和生物重复身份分别保留。

| 字段组 | 类型与含义 | 必需条件 |
|---|---|---|
| `collection_time` | number 或带时区日期时间 string | 与研究问题相关时必需，数值需 `collection_time_unit` |
| `measurement_unit`, `transform`, `normalization`, `missingness_definition`, `identification_filter` | string | 每种测量进入整合前必需 |
| `pairing` 的所有字段 | string；真实样本关系 | 使用配对整合前必需，`pairing_basis` 说明实际依据 |
| `feature_map.site_position` | integer；所声明蛋白序列上的位置 | 位点分析必需 |
| `localization_probability` | number；0–1 | 来自实际定位输出时填写；其他置信量不得改名成概率 |
| `protein_group_id`, `protein_accession_isoform`, `peptide_sequence`, `modified_sequence`, `site_residue`, `protein_sequence_sha256` | string | 对应层级必需；歧义蛋白组不能悄然降为唯一蛋白 |
| `mapping_status`, `ambiguity_reason`, `sequence_release` | string | 身份审阅必需 |
| `effects.effect`, `standard_error`, `lower`, `upper`, `p_value`, `adjusted_p_value`, `uncertainty_level` | number | 有真实估计时填写；效应必须有 `effect_unit` |
| `effects.n_biological_units` | integer | 推断结果必需，不是肽段或技术重复数 |
| `effects.protein_abundance_adjusted` | boolean | PTM结果必需；未知为 null 并说明，不能默认 false 或 true |
| `prior_network.sign` | number 或 string；必须在网络定义中说明编码 | 有符号网络必需；无方向的物理互作不得强行赋激活/抑制 |
| `prior_network.weight` | number | 有权重时填写，同时给 `weight_definition` |
| `edge_type`, `direction`, `source_resource`, `source_release`, `evidence_url` | string | 使用网络边解释机制前必需 |
| `integration_plan.included_assay_ids` | array[string] | 必需；必须能连接 assay 表 |
| `input_transform_by_modality` | object；模态名到变换说明 | 整合模型必需 |
| `integration_plan` 其余字段 | string；模型目的、缺失策略、因子选择、训练/留出、混杂和因子对齐 | 使用该模型时必需；无模型则保留草稿，不填造结果 |

`effects` 的统计单位与模型应由 `analysis_id` 追溯到分析记录。若 RNA 和蛋白来自不同队列，`pairing` 不应填入虚假的样本对，而应声明为非配对比较。

**错误例子。** 两组均叫“disease”便将不同个体配对；缺失全蛋白被视为丰度不变；蛋白调整后的位点变化被标为绝对磷酸化占有率；新模型的因子 3 直接与旧因子 3 相减；相关网络边一律绘为因果箭头。

## I21_exposure_evidence.example.json

### 暴露和脱靶终点

主表一行是一项有明确分析物、基质、时间和来源的暴露记录。`exposure_id`、`parent_id`、`state_id`、`analyte`、`species`、`matrix`、`route_or_assay_context` 和 `evidence_origin` 是解释记录的最少身份；化学状态不能确定时保持限制并暂不建立状态特异的结构结论。

| 字段组 | 类型与含义 | 必需条件 |
|---|---|---|
| `dose`, `time`, `concentration` | number | 真实记录中可取得时填写，各自配套单位 |
| `concentration_relation` | string；如精确、上界、下界、区间关系 | 定量记录必需；删失不得改成精确点 |
| `total_or_unbound`, `protein_binding_basis` | string | 暴露比较前必需；未知明确写 unknown，不默认游离 |
| `evidence_origin` | string；measurement / prediction / literature_extrapolation / unknown 之一 | 必需；区分实测与模型 |
| `source`, `source_release`, `uncertainty_definition`, `qc_status` | string | 必需；来源支持的具体测量上下文应可回查 |
| `uncertainty.kind`, `level`, `lower`, `upper` | string 与三个 number | 按实际报告填写；区间/SD/SE/假设范围不可混称 |
| `offtarget_evidence.value`, `maximum_test_concentration` | number | 有对应结果时必需，配合单位和 `relation` |
| `target_form`, `assay_method`, `endpoint`, `test_conditions` | string | 每个可比较效力终点必需 |
| `model_id`, `model_version`, `applicability_domain` | string | 预测记录必需；实验记录可明确不适用 |
| `exposure_comparisons.free_fraction`, `result` | number | 真实依据或明确条件分析才填写；游离分数范围 0–1 |
| `comparison_formula`, `unit_conversion_definition`, `free_fraction_source`, `comparable_entities_review`, `comparable_context_review`, `decision_scope` | string | 计算暴露效力比前必需 |
| `review_plan` 的所有字段 | string | 决定候选推进前填写；这些是研究规则，不是用药或临床判断 |

`value_unit`、`concentration_unit`、`result_unit` 必须配合所代表的量。摩尔浓度和质量浓度转换应记录用的分析物与分子量来源。`result` 只存可重算的真实比较结果；只有预测而没有暴露依据时不填写“安全边界”。

**错误例子。** 将血浆总浓度与培养液游离浓度直接相比；把 `>10 µM` 写成精确 `10` 而不记录关系符号；把代谢物的效力与母体暴露无说明配对；将 hERG 预测或对接排名写成临床安全结论。

## I22_figure_registry.example.json

### 图源和图形规范

主表一行是一张有固定问题、数据版本和生成方法的图。`figure_id` 唯一，至少填写 `question`、`data_id`、`data_path`、`data_sha256`、`analysis_id`、`unit_of_analysis`、`transform`、`units`、`uncertainty_definition`、`created_from_release` 和 `caption`。没有误差区间的图也需说明“无误差区间”及数据单位，不能留成含义不明的空白。

| 字段组 | 类型与含义 | 必需条件 |
|---|---|---|
| `filters` | array[object]；各项含字段、操作符和值 | 图进行筛选时必需；无筛选可明确保留空数组 |
| `color_mapping` | object；类别/数值到配色及图例含义 | 用颜色表达数据时必需 |
| `limits` | object；轴和色标范围及是否自动 | 比较面板或可复现导出时必需 |
| `script_path`, `script_sha256`, `software_environment_id` | string | 代码生成的图必需；GUI 图要在图注/会话中保留实际方法 |
| `static_svg_path`, `static_png_path`, `interactive_state_id` | string | 相应产物实际存在时填写，不能填不存在的路径充完成状态 |
| `entity_links.original_frame_index`, `frame_id` | integer 与 string | 轨迹原帧联动时必需；保留 `segment_id` 避免不同片段重号 |
| `entity_links.time` | number，另有 `time_unit` | 时间联动必需；不能按播放秒数替代模拟时间 |
| `entity_links` 其余字段 | string；筛选、结构、序列、样本和空间的真实链接 | 仅填当前关系适用的实体；允许不相关层级为空 |
| `decision_snapshots.data_cutoff_at` | 带时区日期时间 string | 冻结预测时必需 |
| `prediction` | number 或 string | 与 `prediction_endpoint` 一致；分类标签不能装成概率 |
| `selection_reason`, `model_version`, `source_release`, `prediction_unit`, `prediction_interval_definition` | string | 预测或选择快照必需；不存在区间时明确说明 |
| `measurement_feedback.value` | number，另有 `unit` 和 `relation` | 有可解释定量测量时填写 |
| `qc_status`, `comparability_status`, `feedback_status`, `training_eligibility_reason` | string | 回流训练/评估前必需，失败和上下文不匹配单列 |
| `view_state_template.selected_entity_ids` | array[string] | 保存联动选择时使用 |
| `view_state_template.filters` | array[object] | 同上过滤规则 |
| `axis_limits`, `color_limits` | object | 保存固定浏览/导出状态时使用 |
| `external_input_dependencies` | array[object]；含资源路径/URI、校验和、嵌入或外部依赖说明 | 会话引用外部结构、轨迹或表时必需 |
| `feedback_plan` 的所有字段 | string | 实验回流前明确规则，不随结果好坏临时改标签定义 |

不要把 `view_state_template` 当作已保存视图，需另存真实状态及其 ID。`entity_links` 的一行不能随意连起互不相关的候选、供体和细胞；多对多关系保留映射依据 `source_mapping_id`。每个图的独立分析单位由数据定义，不是浏览器当前点数。

**错误例子。** 处理后第 100 帧被当作原轨迹第 100 帧；显示配体内部 RMSD 却写成受体对齐后的位姿 RMSD；图中删除失败任务但分母仍用全库；将同一批实验结果既用于调模型又作为独立测试；三维会话只保存远程 URL 却声称已归档全部输入。

## 手工检查与完成范围

本次提供了 7 个空数据契约模板及其字段说明，检查内容是 JSON 语法、模板 ID、草稿状态和实际数据行确实为空。字段含义、单位、真实样本层级、配对、统计设计、因果解释和结论有效性需要使用者在项目中审阅。本 README 不是可执行 JSON Schema；`schema_version` 不会自动触发验证。

正式使用前至少逐项确认：必需身份有值；引用 ID 能连接到真实对象；有实际文件的路径和摘要正确；数值和单位可解释；缺失原因与零值分开；配对与独立重复真实；原始来源与软件版本可追溯；所有输出图和分析对应当前发布。未完成的模块保持草稿，不将空模板写成已执行的科研结果。
