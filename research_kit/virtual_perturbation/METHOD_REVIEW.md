# 虚拟扰动源码复核与剩余验收

本记录覆盖原有 8 条适配源码；新增 CPA、scGPT、BoolNet 和 MaBoSS 的独立审阅见 [新增四方法审阅.md](新增四方法审阅.md)，当前合计 12 条。前述 71 项已完成声明范围内的逐项源码复核并形成单独的 v3.1 修订；这两类审阅均不是服务器运行或科学验收记录。2026-10-25 未派发任何科学任务，未使用本机分析环境。所有适配均 `IMPLEMENTED_ADAPTER_SOURCE_RUNTIME_UNVERIFIED`。

| 方法 | 审阅发现与代码处理 | 与原方法/其他实现的差别 | 必须完成的服务器科学验收 |
|---|---|---|---|
| bulkKnk | 正确识别 fengsh27mail/bulkKnk，固定 c49b106a4383e44ee19d08a75d7edcc99a865ea7。核对 README、DESCRIPTION 与核心 R 源码的版本/API 差异。调用实际 GENIE3/RWR；训练集决定特征/网络，评估单位分开；同时传播 WT 空扰动和 KO，检查固定点残差和逐样本靶点归零。控制基因完整记录。 | 上游 batch 路线把群体平均位移回填全部个体；本包明确改为逐个体 anchor/null/KO。权重转置/归一化明确写入代码，结果不声称完全复制其 batch 输出。GENIE3 无符号重要性网络、启发式 DPI 不等于识别了因果有向抑制/激活。未采用其 RF/生存外推模块。 | 对固定点做独立线性代数参考解核对；验证图方向、归一化、无出边/入边、靶点删除、单/多基因、无效/断联靶点；对表达/度数匹配控制做实际比较；真实扰动对照验证。控制清单本身不能证明匹配。 |
| scTenifoldKnk | 对实际 raw counts 做每供者/细胞类型路线；外部真实 QC 后显式 qc=FALSE，不能假装原生 QC 已执行；表达/变异过滤后 KO 必须仍覆盖，记录实际子网络规模与 RDS。适配真实 nCores、seed 等参数，并检查导出函数形参。 | 不把 bulk 样本传作细胞；不将一个供者中的细胞当 donor 重复。保留原生 gene-space p.adj/FC 字段原义，未把 FC 改名为 RNA log2FC。 | 原生输出 schema、版本/多 KO 支持、模拟控制、供者复制与真实 perturb-seq/实验对照；网络重建的变异性和细胞数敏感性。 |
| GenKI | 使用正确生物学仓库 yjgeno/GenKI 的 VGAE API。显式保留完整 gene denominator，不用原生只返回 bagging 命中者的结果替代全部测试。保存原生训练损失、边重构 AUC/AP、KL 和原生 bootstrap 高排名频率、检查点。每供者重新建网/训练。 | 使用原生潜变量距离与bootstrap 重采样算法，但未把其筛选频率伪称 p/FDR。边预测指标与 KO 响应验证分开。没有训练外供者泛化声明。 | 版本/API、范数层、KL 协方差数值稳定、graph split/随机性、bootstrap 重采样语义、控制靶点和真实 KO 对照；当前训练 API 在选定依赖环境中的兼容性。 |
| CellOracle | 检查实际已拟合检查点/训练回执/单位台账，稀疏层通过 toarray 正确处理。`simulate_shift` 保持 ignore_warning=False、clip_delta_X=True；保存实际靶点均值与 donor 汇总。 | 训练范围裁剪是主动约束，目标可能不能精确归零；结果称 clipped conditional shift。它不等于测量 counts 或证明了 fate 改变。 | 验证已有 GRN 对当前细胞类型的适用性；剪裁/OOD 警告、实际靶点幅度、参考网络敏感性、独立控制/扰动真值。 |
| GEARS | 检查实际 CRISPR 训练类型、组合训练证据、冻结 checkpoint/graph tensors/GO 缓存和全部资产哈希。逐 donor 使用匹配 ctrl，清空 saved_pred/saved_logvar_sum，防止上一 donor 预测复用。按当前原生单 batch 行为最多使用 300 control，记录抽样范围。 | 已训练条件预测，不新增自动训练/下载。CRISPRi 与 KO 分开；单扰动训练不宣传可靠组合预测；原生 inverse-exp-logvariance 分数不叫 CI。 | 实际 checkpoint/API、原生 graph/基因轴、对原工具同输入复现；供者与扰动留出不泄漏；同尺度 delta error、no-change/合理线性基线及真实组合真值。 |
| Geneformer | 审核当前 InSilicoPerturber 参数和 cell_emb 输出格式。固定模型/token 版本与可信本地权重，按 donor/cell type 过滤，只测试含全部目标 token 的细胞；保存覆盖分母和原始文件。检查输出条目数及相似度范围，版本不符拒绝。 | 输入 rank-token 删除、联合目标列表的含义明确；输出 cell embedding 距离，不是 RNA fold change，无激活/抑制方向。基础模型预训练成员不透明时不能宣称 donor 全面独立。 | Token/version/模型兼容、真实原生文件 schema与分母、全零/缺 token/空 donor、模型层/抽样敏感性；独立任务基准与合适简单基线。 |
| Dynamo | 使用实际 pd.KO 已拟合向量场路线。输出 PCA velocity change、UMAP velocity difference、cell norm 与原生对象。替代拟合必须对照冻结 npz 验证 PC 载荷、基因/细胞轴和坐标完全一致，防止旋转的 PC1 被直接相减。 | KO 向量场与局部 Jacobian 扰动是不同路线；本入口明确选前者。不是稳态表达或已测细胞命运概率；描述性平均速度不代表独立细胞重复。 | 已拟合 vector field 的有效性、速度层/基因选择/坐标兼容、有限差分/原工具对照、reference fits 与实际扰动轨迹；禁止把相同 seed 重跑说成模型稳健。 |
| COBRApy | 审核 GPR/质量平衡/介质/目标/求解器，WT 可行性先于 KO。对基因使用 native knock_out，保留联合与单删除、GPR 涉及反应和所有通量。MOMA/ROOM 从指定生物目标反应读取 flux，避免把距离/变化目标当增长。失败可行性不自动当致死。 | FBA、linear MOMA、linear ROOM 优化假设不同；结果只在给定介质/GPR/WT 参考解下成立。单个代谢模型不构成生物学重复；不同 WT 可行通量可影响 MOMA。 | 与官方小型模型/独立解对照；冗余 OR/必需 AND GPR、单/双 KO、培养基依赖、不可行/无界、替代 WT 解和模型外实测必需性。 |

源码门禁是降低错误调用风险，不是证明算法准确。版本/API 不符、回执/哈希/身份不完整或真实 QC 不合格时应保留失败和部分结果；不可通过伪造来源、默认填 passed 或在本地运行科学计算绕过。

所有主来源与实际 score kind 在 `catalog.json`。本包未分发第三方源码、权重或数据。v1.0 的三个候选已分别落实为 CPA、scGPT、BoolNet 和 MaBoSS 四条实际服务器调用源码；当前无未实现候选。12 条服务器科学运行均为 NOT_RUN_SERVER_UNAVAILABLE。

补充源码核对：GenKI 当前训练源码自动选择 CUDA，但其潜变量导出直接调用 Tensor.numpy()；本适配在导入 torch 前明确选 CPU 路线，仍然只允许服务器运行，未修改上游算法。其名为 pmt 的函数实际以 replacement 抽样细胞并内部固定 numpy seed=0，因此结果标为原生 bootstrap 频率，不称标签置换 p 值。Geneformer 源码部分路径显式使用 CUDA，本适配要求真实分配 GPU；没有把未经验证的 CPU 兼容性写成支持。
