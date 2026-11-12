> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 虚拟药物筛选规划与决策附件

这些文件把主手册的筛选章节落实为可填写计划、可审查决策与资源核算。当前提供的是模板和假设预算，没有真实候选库、实际对接结果、ADMET 预测、采购或实验结果。已有 Amber/GROMACS 可用于下游模拟；Vina、Meeko、RDKit、GNINA 等工具的可用性和版本仍按项目环境清单核对。

## 文件用途

| 文件 | 用途 |
|---|---|
| screening_plan.example.json | 冻结目标、来源、身份政策、对照、排名与 10,000 个母体的示例容量 |
| filter_decisions.example.json | 区分化学硬错误、结构警报、预测不确定性、实验可行性和预算决定；保存逐次审查 |
| plan_screening.py | 仅检查规划数值、计算任务数量和示例核时，输出未填写字段清单 |
| selection_rules.md | 后续诊断/生产 MD 的多维决策规范，包括具体门控和候选模型审查 |

selection_rules.md 演示候选审查与 MD 资源分配；本目录 JSON 演示 10,000 个已登记母体的筛选容量。两者是不同层级的计划，实际项目应冻结一致的总预算，并以实际台账生成筛选漏斗。

## 填写顺序与输入要求

1. 复制示例 JSON 为新的项目文件，给定 project_id、版本和主要问题。先决定研究直接结合、酶抑制、互作调节还是细胞功能，并固定结构域、isoform 和测定终点。
2. 填来源快照、查询条件、原始文件和 SHA-256；核对使用条件及库存/采购信息。导入结构、数据库关联和供应记录分别保留证据角色。
3. 冻结母体身份政策，保留既定立体化学和盐型映射；登记状态生成依据、原子映射和构象。parent、state、conformer、run、pose 分表，不用多状态扩增后的条目数当独立化合物数。
4. 填写阳性、已测无活性和 decoy 的独立表。没有相应数据时写明缺失与探索性状态，不伪造对照。unknown 不改为 inactive；计算失败不生成实验标签。
5. 完成对接方法开发与独立评价，记录姿势、排序和物理 QC 三类结果。选择快速/精细参数及受体集合，保留全流程失败核算。
6. 冻结共识规则、缺失策略、多样性配额、ADMET 端点与适用域、可获得性及下一步预算。候选进入 MD 时使用 selection_rules.md 的审查清单。
7. 用真实分层试算替换资源假设。由实际 parent/state/conformer 表展开精确任务清单，再交给项目选定的调度方式。

所有未确定的值用同一形式占位：__FILL_字段名__。真实运行的输入清单不得含占位符。示例容量、种子和搜索投入已经有数值，属于“项目起点或预算假设”，填写完成并不自动证明这些数值适合实际体系。

## 只做计划和预算核算

在本目录运行：

    python plan_screening.py

默认读取 screening_plan.example.json，把 JSON 报告打印到终端，不写文件，不导入 RDKit，不启动对接、MD、外部 API 或付费服务。未填模板可以报告任务数和缺失字段，因为预算核算不等于可提交的作业计划。输出中 execution_performed 和 screening_validated 始终为 false。

指定自己的规划文件：

    python plan_screening.py --config __FILL_PROJECT_SCREENING_PLAN_JSON__

如需保存报告，给出一个尚不存在的真实路径：

    python plan_screening.py --config __FILL_PROJECT_SCREENING_PLAN_JSON__ --out __FILL_NEW_PLAN_REPORT_JSON__

请先替换上面路径占位符。输出文件以独占创建模式写入，已有文件会报错；程序不会自动创建目录或覆盖旧结果。

示例应得到以下纯算术结果：

| 项目 | 假设计算 | 结果 |
|---|---|---:|
| 快速对接任务 | 10,000 母体×2 平均状态×1 构象×1 受体×1 种子 | 20,000 |
| 精细对接任务 | 1,000 母体×2 平均状态×2 构象×3 受体×3 种子 | 36,000 |
| 精细层姿势记录上限 | 假设每任务最多输出 10 个姿势 | 360,000 |
| 快速层示例核时 | 假设每任务 2 分钟、4 核 | 约 2,666.7 CPU 核时 |
| 理想墙钟下界 | 假设持续有效占用 64 核 | 约 41.7 小时 |

这里的运行时间是假设值，不是软件性能声明，也没有把排队、I/O、任务不均衡、预处理、对照、失败和重试算进去。平均状态数与平均构象数用于容量规划；正式任务数应对每个实际母体的状态、构象和受体/种子组合求和。

程序检查正数/整数、重复 stage_id、同阶段重复种子、部分配额合计和输出覆盖风险。它不是化学检查器、实验标签验证器、通用 schema 验证器或调度器；它不会证明盒子、分子状态、参数和排名公式科学有效。

## 对接执行的衔接

单任务参考 ../docking/README.md 与 ../docking/run_vina.py。筛选批处理需在其外层展开经审查的任务清单，保证每个任务有独立目录、确定参数、输入哈希、随机种子、软件版本和完整日志。不同 receptor_id、state_id 或参数版本使用不同任务身份；同一任务的技术重试追加 attempt_id。

GNINA 如使用，需保存可执行程序版本、CNN 模型、受体与配体输入状态、使用模式和原始输出。对现有姿势评分、重新最小化和重新对接分别登记。empirical_score、CNNscore 与 CNNaffinity 分列，不能只保留“AI 综合得分”。程序输出单位以具体版本为准；CNNaffinity 的预测 pK 标度不能标成 kcal/mol。

## 过滤与决策文件怎么用

filter_decisions.example.json 分成 rules 与 decision_records。规则记录测试定义和可能动作；逐个决策记录观察值、命中子结构/原子、证据文件哈希、版本、处置、理由、审查者和下一步。变更决定时保存 supersedes_decision_id，保留旧决定。

PAINS 或反应性命中默认触发审查；最终排除要有项目理由，不能由一个警报直接生成“无活性”标签。溶解度、聚集和 ADMET 各自保留测定/预测条件。预算暂缓、无货、超时、结构缺失与已评估未选用不同原因编码。

每层母体终态互斥：advance、evaluated_not_selected、qc_failed、repair_pending、budget_not_computed；终态总数等于本层输入数。软警报可以多重共存，但不能让同一个母体在流量图的多个排除分支重复计数。任务成功率与母体状态覆盖率分别报告。

## 最低结果与图表包

建议输出来源/身份映射、清洗与状态日志、assay 与对照表、方法验证、全部任务与失败、每母体和每姿势的原始分数、物理 QC、排序敏感性、多样性、库存/成本、候选决策与 MD 入口表。

优先制作母体筛选流量、性质分布、警报热图、骨架网格、相似性关系、药效团/形状叠合、独立验证的 PR/EF、候选×受体名次热图、评分冲突散点、排名带和候选证据卡。没有真实结果时只提供空表或注明为假设的预算图。

完整科学依据见 sources_by_module.json 中的筛选模块 S01–S20 及主手册参考资料。关键官方接口：

- RDKit：https://www.rdkit.org/docs/GettingStartedInPython.html
- Vina：https://autodock-vina.readthedocs.io/en/latest/docking_basic.html
- GNINA：https://github.com/gnina/gnina
- ChEMBL：https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions
