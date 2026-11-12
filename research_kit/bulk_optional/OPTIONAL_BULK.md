> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 私有可选矩阵转录组流程

## 工具

| 调用 | 做什么 | 完成边界 |
|---|---|---|
| `bulk_optional.guide_optional_bulk_pipeline` | 展示 13 阶段、原代码状态、现有工具和门禁 | 指南，不执行分析 |
| `bulk_optional.audit_optional_bulk_configuration` | 检查数据尺度、方向、单位、对照、配对、协变量类型、参考版本与统计咨询输入 | 声明检查，不能验证数据来源 |
| `bulk_optional.audit_optional_bulk_inputs` | 在选定目录内检查有界 CSV/TSV、数值、精确样本集、独立单位、配对、设计秩/自由度和计数深度 | 结构检查，不能替代 PCA/相关性等完整 QC |
| `bulk_optional.plan_optional_bulk_workflow` | 生成选择阶段的明确计划，复用现有工具 | 准备不等于提交或执行 |
| `bulk_optional.audit_optional_bulk_outputs` | 检查指定返回文件、版本、阶段状态、设计/输入绑定及哈希 | 返回快照一致性，不证明科学结论 |

## 使用顺序

1. 对当前 Biomni 实例调用状态与工具目录。私有可选工具未出现时，使用已有私有 bridge CLI 的新进程。
2. 使用 `examples/config.template.json` 的明确字段。原始 v1.0 配置缺少尺度与生物学单位，必须显式转换；没有隐式迁移或自动补值。
3. 使用 `statistics.guide_study_statistics` 检查实际估计目标和单位，再对明确配置调用配置审查与输入审查。
4. 调用现有 `qc.preflight_transcriptomics`，或在服务器使用确切设计的 QC；审阅相关性、PCA、样本标记与建库/参考资料。结构检查成功仍不能直接开始正式分析。
5. 选择适合问题的阶段，用工作流规划工具生成路由。原始脚本为审查材料，不能直接调用 `run.py --steps all`。
6. 在已有服务器环境核验包版本、当前计算节点、设计和输入哈希。准备、已有共享 SSH 显式派发、真实调度回执、真实结束回执分别记录。
7. 使用 `examples/returned-receipt.template.json` 的合同审查指定返回快照；提供独立核查的输入哈希，并用现有服务器回执工具核查真实完成状态。

## 严格输入规则

- 明确 `raw_counts` 或 `log2_normalized`。不自动 log、clip、转置、舍入、映射或取样本交集。
- 矩阵必须 genes × samples。元数据第一列为声明的 sample ID；不要求第一列名固定为 sample_id。
- 只接受显式准备的两组输入。额外疾病组/未说明排除需要独立、记录来源的准备步骤。
- 生物学单位单独声明。技术重复不能变成独立个体；同一单位/条件多行需另行记录合并或指定重复测量模型。
- 协变量声明 numeric/categorical。缺列、空值、重复、完全混杂或饱和设计停止。
- 本机审查每个文件最大 50 MB、500 样本、60,000 基因、200 万矩阵元素；更大数据走服务器 QC。这是审查预算，不是分析内存保证。
- 没有自动剔除样本。性别相关标记需要物种/平台/组织/生物学背景核验，不能用固定阈值直接判定标签错误或污染。
- 正式推断前必须保留统计咨询、完整 QC、恰当模型与效应/不确定性。不把结构审查的通过标记当作正式分析许可。

## 阶段范围

QC、DE、ORA/GSEA、ssGSEA、调控活性、PPI 与组成分析复用现有工具；同名方法不重复实现。现有后端版本和工具参数必须从当前目录获取。

原始 GSVA、WGCNA、程序聚类、分类器基准、严格外部验证尚需修正与服务器运行验收。文档中的 DoRothEA/VIPER、原始 FASTQ、时间序列、剪接和临床模型不能由原始包“自动获得”。可按研究问题路由到已有专用服务器接口，但需要相应输入和单独运行证据。

## 隐私

本可选适配默认离线。私有基因候选列表不自动上传 STRING、MyGene 或 Enrichr；公共数据库查询需独立批准准确查询内容。个人路径、地址、配置、草稿、临床数据、日志和运行回执不进 Git。结果快照仅在明确所选本地目录内检查。

GitHub 仓库必须保持 private，后续公开需要新的明确授权。公开主仓库里的任何分支都不能用于暂存这个更新。
