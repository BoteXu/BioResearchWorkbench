# 检索、标识符、服务器结果与证据追溯

v2.13.2 增加 `research_quality` 类别。五个入口复用既有检索、统计咨询、服务器流程和回执系统，不安装分析引擎，不扫描整个项目或文献库。使用 `biomni_run_tool`，参数与模板见 [自动功能目录](TOOL_CATALOG.json)。

| 工具 | 作用 | 验证边界 |
|---|---|---|
| audit_literature_set | DOI/PMID 重复与冲突、预印本/出版关系、更新声明、检索覆盖 | 标题相同不自动合并；没有更新记录不等于没有撤稿；有界检索不等于穷尽 |
| audit_identifier_context | 物种、构建、注释版本、转录本、蛋白异构体、一对多映射 | 不转换坐标、不证明序列相同或同源，不选第一个候选 |
| resolve_public_identifiers | 最多十个明确获准公开查询的 ID，顺序调用官方解析工具 | 保留逐项失败、原始来源和部分回退；缓存不是新抓取 |
| audit_returned_analysis | 六类服务器结果角色、方法上下文、QC 绑定、选定文件完整性 | 不提交或运行分析；声明的回执需独立核验；文件完整不等于方法有效 |
| audit_evidence_trace | 逐条结论连接来源版本/哈希/位置和实验边界 | 不自动建立直接支持；定位和哈希不能建立科学真实性 |

对应路由是 literature_quality、identifier_context、public_identifier_batch、server_result_depth、evidence_trace_depth。

## 文献检索

记录有唯一 `id`、`search_id`。检索记录有 source、exact_query、retrieved_at_utc、reported_total、returned_count、coverage_state。覆盖状态为 bounded_page、all_reported_records、interrupted；计数不一致阻断完整性声明。出版类型为 preprint、article、review、correction、retraction_notice、other。

强标识符只形成重复候选组，保留全部原记录；标题相同仅供复核。出版关系类型为 is_preprint_of、corrects、retracts、is_version_of，必须记录 source_reference 和 source_locator。勘误/撤稿声明仍需核对出版方或数据库的实际返回内容。

## 标识符

期望上下文包含 species、annotation_version；基因、转录本、变异还需要 assembly。每行有 namespace、source_id、target_id、source_reference、source_version、candidate_coverage_complete。转录本保留 transcript_version；异构体保留 isoform_id 并明确 canonical_substituted=false。一对多关系或不完整覆盖须先制定保留/汇总规则。

批量解析要求对这些具体公开 ID 的 `approved_public_data=true`。缓存最多 32 项、2 MiB、五分钟，仅在内存，返回原抓取时间；失败不缓存。可用 use_cache=false 强制真实查询。既有隐私策略仍在每个公共请求前执行，私有文稿、表格、笔记、服务器信息和文献库内容不能加入查询。

## 六类服务器结果

| analysis | 必需结果角色 |
|---|---|
| bulk | input_qc、design、normalization、differential、diagnostics |
| single_cell | cell_qc、doublet_review、annotation、donor_design、differential、diagnostics |
| spatial | spot_qc、spatial_coordinates、annotation、donor_design、spatial_model、diagnostics |
| pathway | identifier_mapping、gene_universe、enrichment、multiple_testing、redundancy_review |
| ppi | identifier_mapping、network_edges、edge_evidence、network_controls、stability |
| docking | input_qc、protocol、controls、poses、pose_review、score_domain |

context 记录 species、model、biological_unit、contrast、method、method_version、reference_version、design_sha256。QC、完成声明与每份结果绑定同一 context_sha256，计算规则是 `sha256(json.dumps(context, sort_keys=True, ensure_ascii=False, allow_nan=False).encode())`。完成声明需要 state=completed、整数 exit_code=0、receipt_reference；这只检查内部一致性。继续通过既有调度器/运行器核验真实回执。

结果有 id、role、source_reference、locator、sha256、context_sha256。可选择私有 path 流式检查哈希；单文件最大 20 MiB、合计最大 100 MiB。大矩阵和原始文件留在服务器；未选择文件则明确显示字节未检查。细胞/空间点不代替独立供体；通路保留背景集合版本和排序/选择规则；功能网络不代替物理结合证据；对接不代替实验活性。

## 逐条证据与验收

来源有 id、reference、version、sha256、locator、excerpt，以及 species/model/assay/biological_unit/contrast。结论有 text、source_ids、claim_type、support_label，记录 reviewed_negation_and_context。支持等级为 direct、indirect、conflicting、insufficient、unreviewed。关联、共表达、motif、对接和数据库预测不能单独承担因果结论。审计始终明确 direct_support_established=false；最终等级需要实际原文语义审查。

`tests/test_research_quality.py` 验证重复/冲突、撤稿声明、异构体歧义、授权、缓存日期、旧 QC、坏哈希、缺失结果和证据过度推断。这是合成审计契约验收，不是实际科研、真实服务器后端或一般科学有效性验收。
