> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 分析模板使用说明

此目录提供分析协议、配置表和 CPPTRAJ 输入骨架，不是自动完成任意体系的运行器。未连接用户的 Amber/GROMACS 环境，未运行真实轨迹。JSON 已按语法读取验证；CPPTRAJ 命令语义依据官方文档核对，尚未由具体版本 CPPTRAJ 对真实拓扑执行验证。

## 文件

- `analysis_config.example.json`：需要逐项填写的分析计划。`null`、空数组和 `false` 审计项保留待决状态；`execution_enabled=false` 表示尚未形成可执行项目配置。
- `cpptraj_bound_complex.in.template`：展示先拟合受体、再测量配体位姿 RMSD，最后计算不修改坐标的配体内部 RMSD 与核心拟合条件下 RMSF 的顺序。
- `figure_catalog.md`：71 种图的输入、单位、统计层级和主要误区，覆盖 MD/自由能、筛选/机器学习及计算生物学。
- `sources.json`：本分析模块核对的官方文档与原始论文。
- `sources_ml.json`：新增筛选/机器学习模块核对的官方文档与原始论文，保留旧分析来源表独立不变。

## 先填什么

先固定研究问题与主要指标，再填每条独立重复的路径、原子顺序、实际时间轴、分析区间和依据。`replicate_id` 指一次独立初始化的运行；连续 checkpoint 重启只作为该运行的 segments。不同初始位姿和化学状态使用不同 `initial_model_id`，不能静默合并。

拟合选择和测量选择分别填写。核对实际匹配原子数量，并在结构中显示这些原子。若同一残基编号存在于多条链，选择表达式必须进一步区分链/分子或用明确原子索引。CPPTRAJ 掩码、GROMACS 选择和 MDAnalysis 选择语法不同，不能直接复制同一个字符串跨工具使用。

## CPPTRAJ 骨架如何转为项目输入

1. 复制模板为新的分析输入；替换全部双下划线占位符。
2. 确认参考结构已经完整且与拓扑同原子顺序。源轨迹、参考和拟合选择中原子对应必须正确。
3. 从轨迹实际时间推导帧索引，记录 CPPTRAJ 入口的索引约定；不要把 ns 数值填入 START_FRAME。
4. 确认 `autoimage` 的锚点和分子重映射适于当前结合状态。该骨架不适用于以扩散或解离路径为目标的分析；那些任务需另行定义连续展开策略。
5. 先用少量帧检查选择、输出单位、PBC 及几何。再在所有重复上按同一协议运行。
6. 每条重复在独立输出目录运行，避免同名结果覆盖。将原帧号与真实时间写入结果映射。

`nofit` 与 `nomod` 不同。前者在当前坐标下计算而不重新拟合；后者计算拟合后的 RMSD，但不改变后续分析所用坐标。因此模板中的 LigPose 反映受体参考系中的位姿，LigInternal 反映配体内部构象。RMSF 使用已经完成核心拟合的坐标，不会自动拟合平均结构。

## 阈值与统计

JSON 中 4.5 Å 接触、D–A 3.5 Å / D–H–A 150° 氢键和 4.0 Å 盐桥是明确标记的分析示例。MDAnalysis 氢键默认 D–A 是 3.0 Å，因此采用 3.5 Å 时必须显式传入。供受体和电荷状态需化学审查；不存在一个对所有体系适用的相互作用占有率合格线。

最高重采样层为独立模拟重复，必要时在重复内再重采样连续时间块。只有 3 个重复时，区间可能很不稳定，应展示全部值并记录局限。增加同盆地的保存帧数不能解决缺乏跨状态转移的问题。模拟重复与生物供体/动物重复分别报告。

## 单位与端点能量

输出拟统一为 Å、ns、Å²、kJ/mol，但读取工具的实际默认单位必须先核对。GROMACS 原生坐标常用 nm；MDAnalysis 常见内部长度单位为 Å；CPPTRAJ 上述几何结果为 Å。不要对已经转换过的量重复转换。

MMPBSA 工具的输出单位按结果表头读取。GROMACS 轨迹经过 gmx_MMPBSA 后，常见结果仍为 kcal/mol，不能自动标为 kJ/mol。GB/PB 的半径、电介质、盐浓度入口单位、结构水和辅因子归属必须冻结。未含熵结果明确标为“未含熵项的端点能量估计”。

## 建议输出

原始观测表保留 system、initial_model、replicate、segment、frame、time、metric、value、unit；残基结果另加原始序列映射。每张图提供源数据与来源卡。最终报告同时包含支持结果、失败或不一致结果、敏感性、适用范围和替代解释。
