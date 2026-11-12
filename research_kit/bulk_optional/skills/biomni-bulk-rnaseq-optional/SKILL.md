> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

---
name: biomni-bulk-rnaseq-optional
description: "私有可选 bulk 表达矩阵流程：配置/输入门禁、13 阶段工具路由与返回结果验收；仅在明确选择此可选流程时使用。"
---

# 私有可选 bulk 矩阵流程

这是一套用户提供流程的审查后适配。初始工具基础为 Biomni，由当前宿主负责推理；没有新增模型或科学计算环境。此技能单独安装，基础 14 个技能和公开版本不变。

## 使用条件

用户明确选择私有标准 bulk 流程，或让你检查该流程的配置、输入、返回结果。普通检索、单细胞/空间和纯绘图仍使用现有相关技能。不能根据“全分析”自动运行全部可选阶段。

## 流程

1. 先调用 `biomni_status` 和 `biomni_tool_catalog`，搜索 `bulk_optional`。当前缓存目录缺少时，使用已有私有 bridge CLI 的新进程；不重装科学软件。
2. 调用 `bulk_optional.guide_optional_bulk_pipeline` 查看每阶段真实状态。原始脚本都是 review_only 文本，禁止直接运行原始 run.py。
3. 在用户选定项目内按 `1.1-private` 合同声明 genes × samples、raw_counts/log2_normalized、精确样本、独立单位、配对、协变量类型、对照和参考版本。没有隐式转换或默认删样本。
4. 用 `statistics.guide_study_statistics` 审阅估计目标、重复、缺失和协变量；再用配置和输入审查工具。输入结构成功不能替代完整 QC。
5. 使用现有 `qc.preflight_transcriptomics` 或服务器上的确切设计 QC，审查 PCA/样本相关/技术质量/批次与样本标记。固定 sex-marker 阈值不证明错标或污染，normalized 值不能冒充实测 read depth。
6. 调用 `bulk_optional.plan_optional_bulk_workflow`，按科学问题选择阶段。计数用计数模型；已标准化 log2 用合理 limma 模型；连续协变量或配对重复设计需匹配已存在后端。
7. 大计算和下载留在已有服务器。通过原有共享 SSH/调度路径明确派发，记录当前计算节点与真实提交、完成回执。准备不等于提交，unknown 不自动重试。
8. 公共数据库只接受独立明确批准的准确查询。私有候选列表/数据/路径不自动发给 MyGene、STRING、Enrichr。基因集、marker 和调控网络使用选定本地资源并审核版本/许可/命名空间。
9. 用 `bulk_optional.audit_optional_bulk_outputs` 对指定输出快照核验阶段状态、版本、配置与输入哈希、每阶段输出；再核对现有服务器与结果审查工具的回执。哈希通过不证明科学有效性。
10. 交付已完成、失败、跳过、计划与未验证的分别记录。WGCNA/原始 GSVA/ML/严格外部验证需要修正和服务器验收；不能从原始文档描述推断已实现。图与报告复用已存在交付技能，缺失面板必须说明。

## 解释边界

ORA/GSEA 富集不是直接活化；共表达/STRING hub 不是因果；marker score 不是绝对细胞比例，相关性不是细胞来源；同一队列的多方法一致性不是独立验证。模型冻结包括特征、变换、系数、阈值，测试队列重标准化须声明适配而不能称完全冻结。

## 本地 CLI

发现当前私有桥接器后使用其既有 Python：`bridge.py --catalog --category bulk_optional`、`bridge.py --run bulk_optional.plan_optional_bulk_workflow --params-file <selected-private-json>`。具体个人目录、主机、地址或客户端设置不得写入 Git 或公共查询。

可选包说明、配置模板与审查报告在私有仓库；整个可选包保持 private，不能同步到公开主仓库或公开技能包。
