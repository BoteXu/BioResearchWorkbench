# 私有 ShEPhERD-2 v1.2 方法复核与增量

日期：2026-10-29。本文区分作者算法、适配层 QC、只读返回验收与实际科学运行。当前所有科学路线仍为 NOT_RUN_SERVER_UNAVAILABLE，scientific_acceptance=NOT_ESTABLISHED。

## 来源与版本

ShEPhERD-2 作者源码固定为 e0ce03ff80ce80115b1e0a3eb0b1fdba5943023b；shepherd-score 为 20ebed761e055b55a31f4fb1e3c849b86d6ae5e5。实际服务器必须核对完整 Python 源清单、已安装依赖版本和选定引擎身份。只读源码与 Git blob 一致不构成运行通过。

本轮找到可定位的作者 v1 预印本正文镜像，DOI 10.64898/2026.09.10.750648，页脚标记 2026-09-12、CC BY 4.0；核对 §4.4–4.5.1、pp.21–22。官方 v2 页面存在，但本轮正文/PDF访问受限，v2全文及补充材料未复核；不将 v1 定位冒称 v2 全文复核。没有用摘要或检索概括补写性能数字。

公开来源：

- [作者论文 v1 正文镜像](https://www.researchgate.net/publication/414270247_Interaction_Profiles_as_a_Universal_Language_for_Generative_Molecular_Design_with_ShEPhERD-2)
- [官方 v2 页面](https://www.biorxiv.org/content/10.64898/2026.09.10.750648v2)
- [固定原生评价 pipeline](https://github.com/coleygroup/shepherd-score/blob/20ebed761e055b55a31f4fb1e3c849b86d6ae5e5/shepherd_score/evaluations/evaluate/pipelines.py)
- [固定逐分子评价与异常处理](https://github.com/coleygroup/shepherd-score/blob/20ebed761e055b55a31f4fb1e3c849b86d6ae5e5/shepherd_score/evaluations/evaluate/evals.py)
- [固定原生 xTB 调用](https://github.com/coleygroup/shepherd-score/blob/20ebed761e055b55a31f4fb1e3c849b86d6ae5e5/shepherd_score/conformer_generation.py)
- [RDKit 官方标准化接口](https://www.rdkit.org/docs/source/rdkit.Chem.MolStandardize.rdMolStandardize.html)

## 三种目的分别验收

| 路线 | 实际处理 | 合法解释 | 不成立的外推 |
|---|---|---|---|
| 固定姿势画像评分 | 同一原始几何下 xTB 单点、表面与药效团提取，同一姿势评分 | 所给姿势中的配体画像相似性 | 不是论文 relaxed optimal 分数、蛋白结合能或对接有效性 |
| 原生论文评价 | ConditionalEvalPipeline，局部构象优化、独立模态对齐、原生药效团 HP/LP Tversky | 原作者评价定义下的构象与画像性质；保留完整失败分母 | 各模态最优可能是不同姿势，不能拼成一个联合最优对接构象；不自动授予对接资格 |
| 生成候选身份整理 | 在副本上计算状态/母体分组键；保存原始化学图、原子顺序、立体信息与坐标 | 版本与规则锁定的计算身份分组，可供后续去重/数据划分审查 | 不是 pH/pKa、优势质子化态、真实母体或独立样本数预测；不能以标准化副本替换原构象 |

论文 v1 把局部优化后的分子重建与有效性、应变能、图性质及各模态对齐相似性纳入评价；HP/LP Tversky 在完整药效团对齐后评价子集。Tanimoto 与 Tversky 的含义分别保留，不直接当同一标尺合并。

## 原生评价的可审计实现

原生评价可直接接收参考 Molecule 和生成的原子序数/坐标，无需加载生成模型权重。输入读取全部请求的 raw NPZ（恢复源坐标版），使用 allow_pickle=False、压缩展开字节预算、轴/有限值检查。不能只评估 eligible 清单：输入缺失、构图失败、优化失败和评分缺失均留在 requested 分母，同时记录 native 实际评估分母。

原生 pipeline 不完整保留 error、有效性与图一致性标志，本包用同签名回调旁路保存原始结果。审计列表不挂到 pipeline 实例，防止原生 to_pandas 遍历实例属性时误当逐行数据。原生内部可能吞掉 xTB 异常，error=None 不等于引擎成功。

仅在服务器独立评价进程中替换 conformer_generation 的 subprocess 模块引用，逐次捕获本来会被删除的临时输入、charges、优化坐标和日志；不修改全局 subprocess，不更改物理参数或用另一个优化器替代。单 worker 是当前审计支持范围，xTB 可用核数仍不得超过实际分配。临时目录必须在本次新输出范围内，未知旧任务绝不自动恢复/重试。

原生 xTB 命令未显式指定 --gfn：记录论文期望 GFN2、实际 argv、版本和日志证据，method_cli_explicit=false；不能仅凭默认参数宣称引擎模型已验证。原生 strain_energy=优化前能量减优化后能量，保留 Hartree；不是结合能。timeout_minutes 转为每一次 xTB 调用的超时，不能当整个候选/作业的总运行时限。无化学导入的本地检查不验证收敛或物理合理性。

## 身份整理与对接衔接

只选择通过完整生成返回审阅的显式候选。state_graph 直接按原状态图分组；charge_preserving_tautomer 在保持电荷的副本上枚举；uncharged_tautomer 先在副本上 Uncharger 再枚举。明确 max_tautomers/max_transforms 和三项 stereo 设置，枚举状态不为 Completed 时不给已接受母体键。RDKit 规范互变异构体不保证是给定条件下最稳定者。

原 SDF 重新读取核对 BRW_STATE_ID、BRW_MICROSTATE_ID 与来源约束。新 SDF 只更新母体分组属性，逐原子图、原子顺序、坐标再次完全比较，失败保留。BRW_PARENT_ID 由精确策略哈希和规范母体 SMILES 计算。重复候选不丢弃；展示代表、组内数量与全请求分母均明确。后续分子 QC 仍需审阅化学状态、原子/点映射、受体与位点和姿势，不自动提交对接。

## 本轮修复的现有分支

- 依据实际 inpainting 开关、固定药效团、释放时点和解析后的优先掩码计算生效条件；全部关闭不能继续声称 joint_profile。
- 对齐窗口按实际采样步、间隔、上一轮预测条件和提前结束计算；没有任何可执行对齐步时拒绝。
- 化学有效、硬约束通过、最终资格与评分成功分别统计，全请求作分母。历史别名保留但明确弃用语义。
- 对称子图枚举达到上限且未找到见证时标为未评估/不完整，不把未找到当完整失败证据。
- 所有候选路线交接前重新执行完整返回检查；来源化学身份、完整 candidate×reference 覆盖、逐候选状态和预览/完整报告必须一致。
- 源坐标恢复平移与 origin/auto/显式偏移交叉核对；参考轴选择须保留完整且有序参考集合。不同子集需新的显式准备请求。

旧 v1/v1.1 原包、失败路径和资料保持不变。新源码使历史计划、结果验收和交接资格过期，必须用新版本重新规划或单独迁移审查。尚未实现完整训练和全部外部基准复现；不以通用命令壳冒充这些科学分支完成。
