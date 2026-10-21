# 检索证据、冻结结果与综合绘图的交接

## 从检索到可审查证据

`research_quality.audit_search_snapshot` 消费已有 SciSpace／通用元数据，不发送新请求。SciSpace 输入采用原始 `unique_id`、`doi`、`title`、`publication_type`、`date` 等字段；通用输入用 `id`。搜索对象包含 `id, source, exact_query, retrieved_at_utc, reported_total, returned_count, coverage_state`。source 与 provider 一致；returned_count 是这次快照实际记录数。平台未知的全局总数用 `null`，不能填成当前页长度。

保留原始出版类型和日期，识别 DOI 前缀提示及冲突，区分 DOI／PMID 完全重复、仅标题相似与有来源定位的出版关系。所有版本均保留。原始摘要或生成的问答不是已核验原文；类型、日期、方法和局限须通过原始论文审阅。审计不会证明检索穷尽、没有撤稿或科学结论正确。

## FigureHandoff v1

入口：`research_quality.prepare_figure_handoff(input_path, figure_spec, context, qc, execution, sources, output_dir='')`。不启动分析、绘图、额外 MCP 或网络；只读取明确选择的有界结果。

| 参数 | 必须说明 |
|---|---|
| input_path | 一份本地冻结 TSV；最大 5 MiB、20,000 行、250 列；不跟随文件符号链接 |
| figure_spec | 综合绘图工作台现有 FigureSpec v1，准确 input.sha256；实际绘图器和参数在消费端再验 |
| context | 恰好七个非空文本字段：independent_unit、contrast、method_version、reference_version、units、selected_scope、limitations |
| qc | 恰好 state=`passed`、input_sha256、context_sha256、review_reference；绑定本次结果和上下文 |
| execution | 已提供冻结结果，或有绑定内容的完成回执；submitted／unknown 不作为完成 |
| sources | 1–50 条，id 唯一，各有 reference、version、locator，可选准确 sha256 |
| output_dir | 可选的新目录；显式选择时仅复制该 TSV 和交接 JSON，不复制环境、日志、配置或文件夹 |

context_sha256 是 `sha256(json.dumps(context, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf8'))`。同名计算辅助函数 `figure_handoff_contract.hash_value` 可复用。context 中独立单位、contrast 必须与 FigureSpec 的 provenance.experimental_unit、contrast 逐字一致；synthetic 必须显式为布尔值。

已提供结果声明：`{"state":"frozen_results_supplied","source_reference":"已审查的冻结结果来源"}`，不会声称运行过服务器任务。

已完成执行声明还需 `receipt`、`receipt_sha256`。嵌入的 receipt 至少包括 state=`completed`、整数 exit_code=0、input_sha256 和 context_sha256；receipt_sha256 使用相同规范 JSON 算法。只验证调用者交来的内容和一致性，**不认证调度器、不独立证实执行或科学正确性**。完整分析必须继续使用既有服务器真实回执和 `audit_returned_analysis`。

输出包含 schema_version、contract、table、figure_spec、context、qc、execution、sources 和整体 binding_sha256。可移植目录使用 `frozen.tsv` 与 `figure-handoff.json`。消费端用 `handoff-plan` 核对当前字节、QC、来源、参数和源码；后续 render 会重新检查这份交接，不接受旧计划覆盖变化。输出计划留在私有项目内。

实际配套包：[Scientific Figure Workbench](https://github.com/BoteXu/transcriptomics-figure-workbench)。其 `assets/connected-examples/handoff/` 包含公开合成坐标、完整交接 JSON 和实际可调用 FigureSpec；不是额外的模型服务，也不改变注册名字。

## 共享对象联动与来源设计

[Vitessce 原始论文](https://www.nature.com/articles/s41592-024-02436-x) 将多模态数据的共同对象与协调状态连接到多视图，在线发表于 2024 年、卷期为 2025 年。我们采用“明确共享对象身份、统一配色、联动选中”的设计思路，独立实现无网络的轻量结果检查；没有集成 Vitessce 后端或声称继承其大规模能力。

[Workflow Run RO-Crate 原始论文](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0309210) 区分工作流描述和实际运行来源，并用不同层级表示来源。我们据此把准备、交接、实际执行证据及结果审阅分开；当前格式是自有 FigureHandoff v1，**不是 RO-Crate 兼容实现或认证**。

两个项目共享的原始 `figure_handoff_contract.py` 字节一致。没有复制第三方脚本、图像、模型或权重。真实临床或研究结果只在所选私有目录传递；公开示例都是已公开的合成绘图测试结果。
