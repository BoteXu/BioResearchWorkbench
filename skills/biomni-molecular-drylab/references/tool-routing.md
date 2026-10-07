# 工具路线

先查当前实例的 `biomni_status`、`biomni_tool_catalog`；缓存缺少新工具时使用已有私有 bridge CLI。新 portable 安装默认使用 bioresearch 名称，旧 biomni 名称继续兼容。

- `molecular_biology.guide_molecular_drylab`
- `molecular_biology.inspect_molecular_resources`
- `molecular_biology.plan_molecular_extension`
- `molecular_biology.query_intact_interactions`
- `molecular_biology.query_complex_record`
- `molecular_biology.query_cell_line`
- `molecular_biology.audit_splicing_results`
- `molecular_biology.audit_regulatory_links`
- `molecular_biology.audit_protein_annotations`
- `molecular_biology.audit_interaction_records`
- `molecular_biology.audit_perturbation_results`
- `molecular_biology.audit_mechanism_graph`
- `molecular_biology.prepare_molecular_pipeline`
- `statistics.guide_study_statistics`
- `code_review.bind_analysis_qc`
- `code_review.check_analysis_qc`
- `code_execution.prepare_code_execution`
- `server_operations.plan_server_budget`
- `server_operations.review_unknown_submission`
- `server_operations.plan_incremental_return`
- `validation.inspect_scientific_benchmarks`
- `validation.audit_benchmark_receipt`

固定 nf-core 准备器仅覆盖所列版本的 ATAC、ChIP 与 methylation 输入合同，且需要已审核的 QC 绑定。其他方法候选通过现有服务器代码准备流程衔接，不是新增执行后端。原始 HTTP、配置、计划和运行回执均私有。摘要输入字段按 MOLECULAR_DRYLAB.md 填写；字段声明、哈希一致和工具成功都不能证明科学真实性。
