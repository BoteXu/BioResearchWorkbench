# 工具适配与调用

## 发现

按名称在当前 `biomni_tool_catalog` 检索下列工具，读取当前所需参数、版本、`runtime_state`、`last_attempt_success` 与依赖检查。每个工具通过 `biomni_run_tool(category, name, parameters)` 调用；不要从工具名猜测参数。

- `statistics.guide_study_statistics`
- `qc.preflight_transcriptomics`
- `workflow.audit_sample_metadata`
- `server.prepare_standard_pipeline`
- `reporting.audit_analysis_result`

本地后备调用形式为 `<已有运行环境的 Python> <私有安装的 bridge.py> --catalog --category <类别>`；确定当前参数后，用 `--run <类别.工具> --params-file <私有参数文件>`。占位字段由本次私有环境提供，不写入公开配置。CLI 目录、参数文件和结果回执保留私有。

## 执行与验收

先按任务选择工具，不自动执行此列表的全部功能。若函数不存在或依赖未验证，报告缺失并使用已授权的官方来源或现有软件；不得宣称未执行的步骤完成。

长本地任务可用 `biomni_job_submit` 并检查 `biomni_job_status`；这不是 HPC 调度器。远程任务需要真实 SSH/调度提交和完成回执。关键科学主张使用 `biomni_evidence_record` 关联回执、物种、模型、assay、独立单位、对比和局限；完整性检查不证明主张成立。

## 可移植性

流程说明可由不同宿主模型阅读；客户端是否自动发现 skill、是否提供文件/渲染/SSH 功能应单独确认。鸿蒙浏览器网关提供工具 JSON 访问，不承诺原生 skill 执行或 MCP 接入。所有可选软件维持现有权限和私有配置。


## Bridge 2.10 additions
- `code_review.audit_data_contract`
- `code_review.bind_analysis_qc`
- `code_review.check_analysis_qc`

Read CODE_WORKFLOWS.md and CLINICAL_RESEARCH.md in the private installation. Code execution and large clinical/omics computation stay on the server. Scaffolds and passing static checks are not runtime or scientific validation.

## Package 2.14 workflow contracts
- `omics_workflows.inspect_omics_workflows`
- `omics_workflows.plan_omics_workflow`
- `omics_workflows.audit_omics_readiness`
- `omics_workflows.audit_omics_result_bundle`

Read OMICS_WORKFLOWS.md. All new functions are offline plans or bounded summary audits. Reuse actual server environments; reference methods are candidates, not installed engines. Explicit statistical consultation and independent units precede inference.
