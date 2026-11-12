> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# BioResearchWorkbench private add-ons

此目录提供可选 bulk 源码更新，运行数据保持私有。本次仅发布审核后的源码与空白模板；不发布项目数据、机器配置或原始附件。

## Bulk RNA-seq optional 0.1.0-private

来源是用户提供的矩阵分析流程与配套学习讲义。BioResearchWorkbench 最初的工具基础是 Biomni；现有第三方科学算法、数据库和软件保留各自归属。这里的新增适配只负责合同检查、设计检查、工具路由和返回结果检查。

- 实际新增：5 个 `bulk_optional` 工具和一个单独选择的 `biomni-bulk-rnaseq-optional` 工作流 skill。
- 包含 13 个阶段的逐项路由及门禁。默认基础技能包仍为 14 个，公开 v2.12.0 未修改。
- 表达矩阵是入口；从 FASTQ 到矩阵使用现有独立服务器流程。
- 重计算、WGCNA、模型训练、原始数据下载留在现有服务器环境。没有安装新的科学计算栈。
- 所有新工具离线，不调用分析引擎，不安装依赖，不读取整个文献库，不连接服务器。
- 原始 15 个 Python 文件保留为 `review_only/*.py.txt` 静态审查材料；不放入 skill 的可执行目录，不由桥接器导入。
- 原始压缩包、DOCX、机器环境说明、研究数据、原基因集内容和任何私人配置不进仓库。原基因集只记录版本和内容哈希，实际使用需在服务器选择许可合适的本地资源。

使用说明见 [OPTIONAL_BULK.md](OPTIONAL_BULK.md)，审查见 [AUDIT.md](AUDIT.md)，真实完成状态见 [VALIDATION.md](VALIDATION.md)。

## 本机可选接入

已有私有桥接器可显式安装：

```text
python install_private_addon.py --bridge-dir <selected-private-bridge-dir> --skills-dir <selected-client-skills-dir>
```

安装器不安装科学依赖、不改变软件注册表和客户端连接设置、不修改公开仓库。已有不同版本文件会拒绝覆盖；备份保存在所选私有桥接目录。更新后新进程可发现新工具，已缓存进程需要重新连接或使用已有 bridge CLI。

本项目维护的新增代码与说明按附带Apache-2.0分发；外部科学软件、资源、模型和数据各自保留许可。原始附件不随包分发。
