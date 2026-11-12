> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 分子对接与动力学详细流程配套模板

版本 3.1 私有修订，2026-10-24；父版本 3.0 保留。与《分子对接与分子动力学及计算生物学操作规范》配套使用。SOP.md 是可检索、可版本管理的完整手册文本，references.json 保存主要出处。

## 本版新增

保留原有 28 个科研与工程模块，新增 I29–I34 六个专用补充模块；每个新增模块含操作、QC、验收、图源规范和待填合同。incremental/ 提供内容哈希与依赖规划、审查绑定及结果登记、排名版本比较；visualization/plot_incremental.py 增加复用状态与排名变化图。研究模块的专用软件仍需实际安装与验证。

已有项目优先阅读 modules/module_registry.json、modules/README.md 和 incremental/README.md；首次开展的项目沿用下面的基础顺序。

## 本机与服务器边界

本机只进行检索、任务准备、有限元数据和返回结果检查。对接、分子准备、模拟、轨迹分析和大型下载使用既有服务器路线；下述科研命令不能据此在本机自动运行。

## 使用顺序

1. 阅读 SOP.md 的研究设计、身份与化学状态、所需计算分支和质量关卡。
2. 复制 project/project.example.json 为自己的项目配置，填写实际信息。示例数值用于启动设计；保留原始数据及残基和原子映射。
3. 在实际计算环境运行 environment/environment_audit.py，只读记录程序与版本信息。
4. 先按 screening/README.md 登记候选库、规则与预算，再按 docking/README.md 准备输入、查看计划，在输入审查完成后执行对接。
5. 阅读 md/README.md，按所选引擎及实际拓扑修改模板。完成参数、选择、位置限制、预处理和短程试跑检查，再运行正式阶段。
6. 按 analysis/ 内的配置和图表规范分析各独立运行，保存时间轴、单位和选择定义；按 visualization/README.md 从实际数据制作基础图。
7. 用 quality/decision_record.example.json 逐关保存科学审查，再用元数据检查器核对最终交付。

命令以 Linux、WSL 或容器中的 Python 3.10 及以上环境为例。Amber、GROMACS、Meeko、Vina 和专用分析程序按各自文档安装与授权。本包不会安装这些软件。

## 独立检查器

在本目录下进行只读环境盘点：

```bash
python3 environment/environment_audit.py --output environment_audit.json
```

检查项目登记完整性，不调用模拟引擎：

```bash
python3 quality/audit_project.py project/project.example.json
```

示例配置含待填字段，草稿模式会列出缺失信息。最终交付检查示例：

```bash
python3 quality/audit_project.py /path/to/project.json \
  --root /path/to/project --check-files --ready \
  --output audit_report.json
```

`--ready` 指最终交付的元数据就绪。该模式要求必需字段已填、输入 SHA256 已核对、所列科学审查有通过记录及非空的 path/sha256/bytes 证据列表；示例模板在此模式下应被拒绝。审查记录由研究者依据证据填写，脚本不判断化学、参数和采样是否科学正确。

`--check-files` 读取登记输入并核对路径和校验值；相对路径以 `--root` 解释。检查器适用于本包示例登记结构，设计改变后可扩展字段和检查，不应删除必要字段来获得通过。

## 文件职责

- project/：项目与比较登记、结果表字段。
- quality/：元数据检查与科学审查记录。
- environment/：实际环境的只读盘点，不读取认证信息。
- docking/：Meeko/Vina 输入、命令与受控执行模板。
- md/：Amber/GROMACS 阶段输入、生成器与衔接说明。
- analysis/：分析定义、配置、命令示例与图表规范。
- screening/：虚拟筛选方案、筛选规则和进入 MD 的选择记录。
- visualization/：读取真实计数和观测数据的基础出图程序。
- modules/：34 个增量模块的独立说明、登记和数据模板。
- incremental/：增量计划、审查绑定、结果登记与排名比较。
- operations/：批处理与续算记录、发布清单。
- SOP.md：详细流程正文。
- references.json：正文参考资料。
- sources_by_module.json：模块引用键与原始出处对应。
- VALIDATION.md：父版本作者报告的历史验证范围；VALIDATION_v3.1.json 为本轮实际回归回执。

## 按体系填写的内容

结构与序列、配体状态、净电荷、拓扑、原子选择、分子编号、位置限制 include、盒与离子、力场兼容性、版本、种子和路径均需按实际体系确定。`__FILL_*__`、null 或其他明确待填字段表示尚未完成。

Amber mask、GROMACS index group 与 MDAnalysis selection 采用不同语法，应分别核对实际选中原子。拓扑转换后也需要重新核对索引。

## 验证范围

原 VALIDATION.md 的内容保留为历史来源记录，本轮独立完成的检查见 VALIDATION_v3.1.json；真实分子计算及用户硬件兼容性需在实际环境用代表体系验证。本包未产生对接、MD、收敛或亲和力结果。

失败后先读取日志和模块验收规则，保留原始文件、失败记录、已完成阶段及输出版本。模板说明与科学检查一起使用。


## 私有 v3.1 增量

请先读 [本轮修订及采用边界](PRIVATE_REVISION_v3.1.md)。新增 I29–I34，原有画法和模块保留；本轮验收与历史来源验收分开记录。
