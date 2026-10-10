# 工作台工程优化 2.13

## Package 2.14：组学契约与可选拓展

新增静态 `omics_workflows.json` 与自动生成的 OMICS_WORKFLOWS.md。新目录含 28 条流程、21 类拓展及四个只做规划/摘要验收的接口；不增加科学执行器或依赖环境。输入/参考/设计/目录/计划绑定共同约束 QC 与返回结果；统计咨询、任务定义的数值阈值和实际服务器来源保留独立验收层。描述性计划与推断计划的结果角色分开。参见 [OMICS_WORKFLOWS.md](OMICS_WORKFLOWS.md)。

安装与升级复制同一静态目录；共享实例源码审查哈希包含该目录，旧计划在目录改变后不能继续使用。公共合成测试覆盖尺度错误、伪重复入口、缺失/未知 QC、数值判据矛盾、拓展缺条件、计划篡改、浮动后端版本及未知服务器完成状态。这些测试不建立真实组学后端或科学结果验收。

v2.13.2 的源码升级/回滚增加共享服务生命周期锁。先对精确实例执行 drain，等待真实工作线程和队列结束，再 stop；持锁服务会阻断升级预览。应用和回滚期间持有同一锁，避免并发启动旧后台。具体步骤见 [SHARED_MCP.md](SHARED_MCP.md)。未知调用与服务器提交仍须核对回执，不能自动重试。主机已有旧服务但缺少控制接口时，需要使用者选择空闲切换或下次登录启用，不能据此批量结束其他进程。

本次同时深化分子生物学干实验，并补充此前八个工程方向。实际目录、签名、默认参数、枚举、模板与来源哈希见 [TOOL_CATALOG.md](TOOL_CATALOG.md) / [TOOL_CATALOG.json](TOOL_CATALOG.json)。大计算仍留在服务器，用户私有安装和研究资料不随公开包发布。

## 工具状态与验证过期

当前工具状态分为 `untested`、`passed`、`failed`、`expired`。`historical_success` 表示曾成功，`last_attempt_success` 表示最近尝试，`current_environment_verified` 要求最近调用成功且验证指纹仍匹配。最近失败不会因旧成功记录显示 passed。

指纹绑定当前桥接源码、安装依赖的版本/元数据、Python、本地 JSON 配置哈希与模块/网络设置。配置值不出现在指纹说明中。旧版无绑定的成功记录先过期；原记录保留。源文件更新后，持久 MCP 进程仍可能导入旧代码，需重新启动才可能完成新验证。依赖元数据指纹不等于逐文件供应链审计；第三方服务状态、外部引擎和所有参数路径仍需要任务级实测。

## 升级预览、兼容性和回滚

`upgrade.py` 先校验公开包 manifest，再对便携安装的受管文件做预览。全新安装会在成功验收后记录 `upgrade_state.json`。旧安装可从其对应原版包显式初始化基线，只有受管文件全部匹配时才接受，不将定制文件伪装成原版。

```text
python upgrade.py --install-dir <私有安装目录> --preview-file <新的私有计划文件>
python upgrade.py --apply-plan <私有计划文件> --reviewed-sha256 <审核后的计划哈希>
python upgrade.py --rollback-journal <本次升级的私有 journal 文件>
```

预览绑定包、基线和目标前置哈希。计算版配置和依赖集变化需要单独环境迁移；不静默安装依赖、不修改客户端注册/凭据/软件路径。用户自定义 skill 保留；定制 Python、R 或 PowerShell 桥接源码阻断直接覆盖，需要先手工合并。已审核配置迁移可复用现有 `code_review.prepare_configuration_migration` / `apply_configuration_migration`，其具体计划必须审查并绑定哈希。

应用前创建独占锁与升级日志，备份所改文件，并在每次写入前核对哈希。失败尝试回滚受管文件；无法安全恢复时保留 journal 供明确核查。显式回滚不会覆盖升级后用户再修改的内容。未知/中断升级、旧锁和不明任务均不能自动重试。恢复源码不是恢复科学任务或依赖环境，重启后还需运行验收。

## 目录同步与模块加载

`generate_catalog.py` 从公开 AST 生成扩展目录、参数 schema、调用模板、类别与任务数量。CI 执行 `--check`，目录不一致即失败。模板不是有效真实输入，嵌套科学字段须阅读领域合同。上游 Biomni 原始工具和当前客户端插件仍通过运行目录发现，不重复打包其注册表。

`BIOMNI_MODULES` 可选择扩展类别，以逗号分隔，例如 `literature,research,statistics,molecular_biology,workflow`。默认保持所有既有能力。`database` 启用固定数据库入口，`upstream` 启用原始 Biomni 专家工具。扩展在调用时才导入，未选模块不加载、不对外暴露。元数据解析成功不宣称 import_ready；依赖缺少和真实导入失败由具体调用报告。可选分析依赖继续按发行版分开，选模块不会自动安装任何依赖。

## 更明确的调用合同

保留通用入口，并增加 `biomni_tool_availability`、`biomni_molecular_plan`、`biomni_splicing_audit`、`biomni_regulatory_audit`。专用入口有任务枚举、科学上下文结构和输出回执 schema；失败回执保留 `error_type` / `error_code`。通用工具运行错误区分输入错误、依赖缺失和运行失败。调用前的协议/参数校验可能以 MCP tool error 返回，不伪造执行回执。

结构化输出有利于客户端检查，不能证明嵌套字段的科学真实性。宿主仍需检查 `success`、具体 QC 字段、原始数据和证据限制。

## 科学基准的三层验收

[benchmark_catalog.json](benchmark_catalog.json) 定义许可明确的公开 pasilla/DESeq2 示例和 R ToothGrowth/Welch 示例，不复制数据进公开包。独立 CI 实际运行方法并比较事先列出的方向/数值范围。`validation.audit_benchmark_receipt` 分开报告接口合同、后端完成和参考一致。

合成测试继续覆盖拒绝路径和工程合同；公开基准只测所列设计/版本和数值范围，不能成为全部分子生物学方法或宿主推理质量的统一证明。服务器运行验收仍使用该服务器真实环境与回执，不从 CI 推断真实集群可用。

## 服务器预算、恢复与增量回传

新增 `server_operations.plan_server_budget` 复用真实 pilot 资源预估，给出 CPU/memory 小时预算，可按用户提供的费率估算区间，不猜测实时价格和队列等待。已有 Slurm 监控准备器继续采集 owned job 的真实队列/记账快照；准备器不是活体观测。

`review_unknown_submission` 汇总明确提供的新鲜请求绑定观察，保留多 job 冲突/缺失状态；自动重提始终为 false。检查点相容性继续复用 `code_execution.audit_resume_compatibility` 的精确环境/输入/设计/参考/检查点审查，不能由文件存在判为可恢复。

`plan_incremental_return` 比较显式返回文件 manifest，按预算列出新增/变化文件，保留缺失与超预算/活动写入文件。不执行连接、传输或删除；完成返回后用原有完整性检查验证实际字节。共享 SSH 派发和真实服务器状态验收保持明确执行边界。

## 按问题操作与可追溯结果

已有认证浏览器入口新增研究方向选择、背景/参考表单、路线/QC 准备，以及阻断、来源和缺失结果面板。高级工具入口保留。路线按钮不发起分析或公开查询。项目状态页增加研究问题、QC 阶段阻断、证据和谱系。所有源内容通过文本节点或转义显示；令牌只在当前页面内存，不增加公开端点或后台上传。
