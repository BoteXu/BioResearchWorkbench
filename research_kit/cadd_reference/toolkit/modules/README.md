> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 增量模块索引与使用顺序

版本3.0.0。每个模块具有独立说明 Ixx.md 和一个可填写 example.json，全部科研观测表初始为空。模板格式版本统一为 schema_version 1.0.0；它们是交接契约而非自动运行配置。incremental/ 的执行计划器采用另一个明确定义的整数版本1，二者不能混用。

先确定研究缺口，再阅读相应模块的输入与退出条件。dependencies 是供人理解的条件前提，不是必须全部运行的任务DAG。具体项目的可执行依赖需在 incremental/workflow.json 中声明。

| 模块 | 内容 | 说明文件 | 数据模板 |
|---|---|---|---|
| I01 | 多参考药效团与形状查询的增量验证 | I01.md | I01_query_validation.example.json |
| I02 | 片段锚点与可扩展方向的计算评估 | I02.md | I02_fragment_anchor.example.json |
| I03 | 跨靶点选择性与反筛证据矩阵 | I03.md | I03_selectivity_panel.example.json |
| I04 | 系列 SAR 匹配分子对与活性悬崖 | I04.md | I04_sar_series.example.json |
| I05 | 命中证据升级与实验反馈标签 | I05.md | I05_feedback_labels.example.json |
| I06 | 相对自由能候选网络与预算决策 | I06.md | I06_rbfe_priority.example.json |
| I07 | 具有延迟标签的分批主动学习 | I07.md | I07_active_learning_round.example.json |
| I08 | 新化合物与新标签接入后的筛选重算 | I08.md | I08_screening_update.example.json |
| I09 | 化学状态与参数及水网络的敏感性分析 | I09.md | I09_state_water.example.json |
| I10 | 受体构象与动态口袋及隐蔽口袋 | I10.md | I10_pocket_panel.example.json |
| I11 | 膜蛋白与脂质及糖基化体系 | I11.md | I11_membrane_glycan.example.json |
| I12 | 金属与辅因子及共价结合的专用模型 | I12.md | I12_special_chemistry.example.json |
| I13 | 相对与绝对结合自由能的项目化计算 | I13.md | I13_free_energy_network.example.json |
| I14 | 增强采样与动力学及停留时间 | I14.md | I14_sampling_protocol.example.json |
| I15 | 动态网络与变构及界面敏感性 | I15.md | I15_dynamic_network.example.json |
| I16 | 靶点证据与生物学实体对齐 | I16.md | I16_evidence.example.json |
| I17 | 供体层面的组学整合与新增样本接入 | I17.md | I17_sample_design.example.json |
| I18 | 剪接异构体到蛋白结构与口袋 | I18.md | I18_isoform_mapping.example.json |
| I19 | 扰动表达与药物重定位 | I19.md | I19_signature_query.example.json |
| I20 | 多组学与蛋白状态证据 | I20.md | I20_multiomics_pairs.example.json |
| I21 | 暴露与ADMET及心血管证据矩阵 | I21.md | I21_exposure_evidence.example.json |
| I22 | 图形复用与交互浏览及实验反馈 | I22.md | I22_figure_registry.example.json |
| I23 | 模块接口与数据身份契约 | I23.md | I23_identity_contract.example.json |
| I24 | 新数据接入与结果复用计划 | I24.md | I24_change_request.example.json |
| I25 | 批量运行与动力学断点续算 | I25.md | I25_segment_registry.example.json |
| I26 | 追加采样与统计更新规则 | I26.md | I26_sampling_update.example.json |
| I27 | 排名变动与图形版本发布 | I27.md | I27_release_figures.example.json |
| I28 | 失败恢复与模块升级验收 | I28.md | I28_failure_release.example.json |

## 模板约定

稳定ID用字符串；value等数值字段使用数值并分列单位；未知用null且保留原因；未测、计算失败、测量无效和阴性分开。rows为实际观测数组，row_template仅示范字段，不应并入数据统计。路径、哈希、审查状态与时间必须来自实际项目。

I01至I08详见README_screening.md；I09至I15详见README_md.md；I16至I22详见README_biology.md。I23至I28的具体工程步骤详见对应模块及incremental/README.md和operations/hpc_runbook.md。

## 实现范围

本包可运行的辅助工具包括环境盘点、登记审计、任务预算、对接包装、双引擎文本模板生成、离子数算术、基础出图、增量规划/审查登记和排名比较。模块登记和JSON模板不代表各专业科学软件已经安装或计算结果已经通过验证。


## 私有 v3.1 专用补充

原 I01–I28 保留。以下模块是规范与待填合同，未执行科学后端：

- [I29 tREMD 与 REST2 的协议及交换谱系](I29.md)
- [I30 跨引擎资格矩阵与可审计的转换试验](I30.md)
- [I31 化学微态、标准态与自由能账本](I31.md)
- [I32 解离事件、删失与动力学推断资格](I32.md)
- [I33 对接验证的位姿、检索与前瞻分层](I33.md)
- [I34 审查证据绑定与 Biomni 私有交接](I34.md)
