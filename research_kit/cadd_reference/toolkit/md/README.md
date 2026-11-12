> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# Amber / GROMACS 分阶段模板

这些模板是可审查的项目起点，未用 Amber/GROMACS 引擎和你的实际体系运行测试。生成器只渲染输入文件，不运行模拟、不安装软件、不连接集群。正式使用需要完成拓扑、原子选择、力场组合、版本功能和短程试跑检查。

## 适用模型

示例：常规可溶性非共价蛋白或蛋白—小分子复合物；ff14SB/TIP3P，适用的小分子 GAFF2 参数；300 K、1 bar；NVT 升温后 NPT。升温 1 fs，之后约束与氢相连的共价键并使用 2 fs。实际项目可采用其他经过验证的组合，但更换力场、水模型、温度或非键方案后要重新审查。

Amber 使用 Langevin 和 Monte Carlo barostat；GROMACS 使用 v-rescale 和 C-rescale。这是阶段目的相同的两套演示输入，不保证动力学或逐帧轨迹等价。示例非键采用约 1 nm 实空间截断与 PME；PME 网格等自动设置仍须从日志核查，跨引擎能量/力验证不能仅凭模板完成。

## 文件

- amber_templates：10 个阶段的 mdin 模板。
- gromacs_templates：10 个阶段的 mdp 模板。
- preparation：GAFF2 命令、LEaP 结构建系及位置限制 include 示例。
- stages.json：阶段时长、位置限制和最小化起点。
- make_md_inputs.py：生成指定重复的输入与种子清单。
- salt_count.py：最初不含盐的单价 1:1 电解质计数示例。
- commands_amber.md / commands_gromacs.md：每阶段文件衔接、续跑与验收位置。

## 必须先完成的项目设置

1. 生成并审核完整拓扑与坐标，确认全部原子/残基编号及组件数量。
2. 选择实际软件版本、可执行程序和受支持选项，保存版本与运行日志。
3. 定义需要位置限制的溶质重原子，保存列表与结构快照。
4. 对 GROMACS 每个 molecule type 单独建立局部原子索引的 posre 文件，并在正确作用域 include。
5. 核实每个生产体系的对照、重复、长度和延长规则。
6. 先完成一条诊断路径；每阶段检查实际解析后的配置及日志，再进入后续阶段。

## 生成输入

输出目录必须不存在，防止覆盖已有计算结果。下例残基范围仅演示语法，使用前必须改为你的真实审查结果：

    python3 make_md_inputs.py --engine amber --replicate 1 --base-seed 48271 --production-segments 5 --amber-mask ':1-250&!@H=' --out run_amber_r01
    python3 make_md_inputs.py --engine gromacs --replicate 1 --base-seed 48271 --production-segments 5 --out run_gromacs_r01

不同体系使用登记过的 base-seed，replicate_id 也须登记。生成器保证单次生成内部种子不同；全项目仍应检查种子清单。Amber 为每个生产段输出独立输入；GROMACS 只生成首个 20 ns 输入，随后通过 convert-tpr 与 checkpoint 延长至计划总量。

在输出目录放入或链接已冻结的拓扑和坐标。每条重复分开运行。Amber 初始文件名为 system.prmtop、system.rst7；GROMACS 为 topol.top、system.gro，以及拓扑引用的全部 itp/力场文件。命令文档使用这些名称，路径不一致时应统一修改并记录。

## 位置限制系数

Amber ntr 在每个方向上的限制势能等于其系数乘以位移平方；GROMACS 对应项还包含 1/2。考虑 Å 与 nm、kcal/mol 与 kJ/mol 的单位差异，并保持限制原子、参考位置和参考缩放处理相同后，GROMACS 系数数值应为 Amber 系数数值的 836.8 倍，因此：
- 最小化初段：Amber 5.0；GROMACS 4184.0。
- 升温、NVT、强限制 NPT：2.0；1673.6。
- 中限制：0.5；418.4。
- 弱限制：0.1；83.68。
- 自由平衡、试跑和生产：无溶质位置限制。

纯单位换算的 418.4 没包含势函数里的 1/2。上述换算只针对这些位置限制定义；GROMACS NPT 参考缩放设为 all，跨引擎还要核对 Amber 对应处理。系数匹配不等于整个受限 NPT 过程完全相同。

GROMACS 模板的 POSRES_SOLUTE 与 POSRES_FC 只在 include 已正确建立时生效。必须检查 grompp -pp 生成的展开拓扑，确认目标原子、强度和生产阶段的关闭状态。不能直接用全体系索引给每个 molecule type 建限制。

## 升温与参考

02_heat 在 0–150 ps 从 10 K 线性升到 300 K，150–200 ps 保持 300 K。实际温度不必瞬间等于参考。00_min_solvent 参考最初体系，01_min_all 无位置限制；02_heat 到 06_npt_weak 参考 01_min_all 输出。若改参考文件，需记录原因及校验值。

只在新初始化的升温阶段生成速度；连续阶段读入已有速度。Amber 每个动态阶段/生产段使用不同 ig。GROMACS 进入生产后用 checkpoint 续跑，不能通过重新 gen-vel 来“接上”旧轨迹。

## 离子计数

    python3 salt_count.py --volume-nm3 1000 --salt-molar 0.15 --solute-charge 4

此例得到 90 对盐及额外 4 个负离子。它假设最初无盐、盐为单价 NaCl，并以整个盒体积定义名义浓度。已存在离子、多价离子或目标为指定离子强度时需另算。使用实际盒矩阵行列式获得体积；NPT 后重新报告实际平均体积。

LEaP 模板中的 __ION_COMMANDS__ 必须替换为审查过的正计数加离子命令，无需加离子时删除该整行；不要用计数 0 代替省略，因为 0 在相关加离子命令中可能具有“中和”语义。

## 模板验收与限制

生成器只检查占位符、基本整数范围、文件覆盖风险和种子，不能判断 mask 是否命中了科学上正确的原子。模板中不存在默认 -maxwarn，也不提供会跳过阶段检查的自动长跑脚本。LEaP、grompp 和试跑结果通过之后，才有项目级可运行证据。

正文的阶段表是建议起点；每步是否结束由实际结构和统计检查决定。模板选用固定体积升温、分段放松和无偏生产，膜、金属、反应、强偏置或其他特殊体系应换成相应方案。

