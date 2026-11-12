> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 私有虚拟扰动扩展 v1.2

这是 BioResearchWorkbench 的私有可选扩展。当前纳入 12 条带实际后端调用的服务器源码路线；所有科学后端状态均为 `NOT_RUN_SERVER_UNAVAILABLE`，科学验收为 `NOT_ESTABLISHED`。本地完成的是来源/API 审阅、语法解析和契约/拒绝测试。不可据此宣称运行成功、数值正确或具备泛化预测能力。

本扩展保持原 71 项扩展与原始 SOP 不变。71 项逐项源码复核已形成独立的私有 v3.1 修订和逐方法判断，服务器科学实测仍为 0/71。本扩展与该修订分别采用，旧版本完整保留。扩展通过已有 Biomni 工作流 skill 的私有引用发现，不新增模型、MCP 注册、服务或本机科学环境。

| 入口 | 实际调用与输出 | 前提与主要解释限制 |
|---|---|---|
| `bulk_virtual_ko` | bulkKnk 的 GENIE3 网络与 RWR，逐个体保存 model WT、model KO、差值、网络、收敛残差和控制基因结果 | 训练与评估供者不重叠；线性非负归一化表达。固定源码提交。逐个体空扰动基线是明确适配；不采用队列共同均值平移、RF“挽救率”或生存获益推算。 |
| `singlecell_virtual_ko` | scTenifoldKnk 原生逐供者/细胞类型扰动、完整差异调控结果、原生 RDS 与覆盖信息 | 原始单细胞计数、实际 assay QC、每供者细胞覆盖；单供者基因空间的统计量不能当作供者总体效应。多基因需要兼容版本。 |
| `genki` | GenKI 原生 VGAE 拟合、KL 距离、完整基因分母、原生 bootstrap 高排名频率、训练和图边指标 | 已审核 norm 层和固定基因轴；KL 不是表达 FC，原生 bootstrap 高排名频率不是基因 p 值/FDR，图边 AUC 不是 KO 预测准确率。 |
| `celloracle` | 已拟合 Oracle 的 `simulate_shift`，供者汇总 model delta、实际靶点预测值、训练谱系 | 仅已有检查点，实际训练回执与单位台账。保持训练范围裁剪并检查警告；裁剪后未必实现靶点精确归零，不把它称为完全敲除。 |
| `gears` | 已有 GEARS 检查点的 `predict`，每供者匹配 control、预测表达与差值、原生不确定性指标 | 必须实际扰动训练数据和已有 GO/图缓存；组合预测需要组合训练证据。清空跨供者缓存，限制当前原生单批预测至 300 control。CRISPRi 与完整 KO 分开。 |
| `geneformer` | 原生 rank-token 删除，逐供者输出 cell-embedding 余弦相似度和距离、token 覆盖、原始文件 | 模型与 token 字典版本、权重来源明确；每个测试细胞包含全部选定 token。预测的是嵌入变化，没有表达 FC/上调下调方向。 |
| `dynamo` | 原生 `pd.KO`，已拟合向量场中 PCA 速度变化、单细胞变化范数、UMAP 速度差与原生对象 | 需要实际动力学/向量场拟合证据；不输出稳态表达或已测命运概率。替代向量场必须使用相同 PC 基、基因/细胞轴和坐标。 |
| `metabolic_gene_deletion` | COBRApy 按 GPR 删除基因，FBA、linear MOMA、linear ROOM；保留单基因和联合删除、反应通量与控制 | 必须审核 SBML、GPR、质量平衡、培养基、求解器和目标函数。MOMA/ROOM 读取指定生物目标反应通量；优化器的距离目标不能冒充生长率。代谢目标受抑不等于实测细胞死亡。 |

v1.1 新增以下实际调用路线，候选数现为 0，实际适配源码数为 12；没有科学后端已验收声明。

| 新入口 | 实际调用 | 专用 QC、结果与解释边界 |
|---|---|---|
| `cpa` | 当前 `CPA.load` / `CPA.predict` | 实际遗传扰动训练检查点、训练单位/剂量/类别支持、同轴注册参考、X 层、实际 checkpoint registry 重注册和控制重建 RMSE 门槛；配对 predicted-control 与 predicted-perturbation，避免把重建误差当效应。不同剂量是新研究对比，不冒充稳健性重跑；不兼容的历史 CPA API 明确拒绝。 |
| `scgpt` | 原生 `TransformerGenerator` 前向与 mlm_output | 必须扰动任务微调、固定架构/vocab/gene axis、严格加载全部权重；control/perturbation flags 配对，完整基因保留，控制重建门槛。基础预训练、缺基因静默填 pad、部分加载、未经实现的零膨胀 Monte Carlo 均不冒充支持。 |
| `boolnet` | 原生 `loadNetwork` / `fixGenes` / `stateTransition` | 静态非执行 Boolean grammar、完整加权初始状态、固定 KO、同步周期与异步有限时域分开；同步未解析吸引子要失败，异步未收敛结果保留有限时域标签。不是 RNA 表达或独立生物重复。 |
| `maboss` | 原生加载、copy_and_mutate、Simulation.run 及概率轨迹 | 实际已安装 MaBoSS 二进制哈希、BND/CFG/rates审阅、完整独立 Bernoulli 初始概率、KO 初态归零与 OFF、完整状态质量/节点概率和时间覆盖。返回 MC error 与末步变化，末时点不自动称稳态或真实细胞命运。 |

源码和专用方法差异详见 METHOD_REVIEW.md 与 [新增四方法审阅.md](新增四方法审阅.md)；这些实际调用均未服务器实测。

## 选择和使用

本机可读取目录或准备关闭执行的计划。用已有工具 Python 调用：

```text
python cli.py catalog
python cli.py plan --request YOUR_REVIEWED_PROJECT.json --out NEW_PREPARATION_DIRECTORY
python cli.py accept --request YOUR_RETURN_SELECTION.json --root SELECTED_RETURN_DIRECTORY
```

`examples/` 给出全部 12 条的完整配置结构、参数、输入角色、两套替代参数和数值验收规则结构。它们是被门禁拒绝的示例：`example_only: true`，没有真实输入哈希、模型、QC、主机或实际后端代码指纹。必须根据真实来源改成经审核的项目，不能直接运行示例或把示例当分析结果。

准备完成不等于提交。服务器就绪后，通过已有共享 SSH/调度流程取得当下计算节点与资源，核对现有安装版本和源码指纹，人工明确派发；仅该请求的 `server_execution_authorized` 从 false 切到 true，其他字段与计划哈希保持一致。不要更改方法、输入或主机后仍复用旧计划。未知提交先核查真实回执，禁止自动重试。

已有服务器上可用 `python server/identity.py METHOD_ID` 只读查看所选已安装后端代码清单/指纹。该命令不导入模型、不安装包、不运行分析；指纹仍需要对照实际审阅的来源，不能以“有哈希”代替方法审核。科学运行使用准备包内 `python server/runtime.py request.private.json NEW_OUTPUT_DIRECTORY`。不在登录节点或本机/本机 WSL 运行。

## QC、模型资产和统计单位

输入 `context` 明确物种、构建、注释版本、assay、尺度、独立单位、估计目标与局限；`measurement_state` 固定为 predicted，public_upload 固定为 false。尺度按方法严格区分，不把 token、潜变量距离、原始计数、归一化表达、速度或代谢通量互换。

`qc_receipt` 必须是已完成、exit_code=0 的上游真实回执；`qc_measurements` 必须被该回执的输出哈希登记；每条数值 QC 必须指向同一输入哈希和实际测量字段，再按预先给定的阈值判断。文本 passed、目录存在或 caller 自报成功不能替代测量。

CellOracle/GEARS/Dynamo/CPA/scGPT 的 `asset_manifest` 逐文件登记真实哈希、原始来源/许可审阅和信任决定，目录必须完整盘点。训练证据绑定实际完成回执、实际检查点输出、真实训练单位台账及物种/注释。`heldout_donor` 禁止复用训练供者；`in_sample_conditional` 明示为训练内条件预测。模型或缓存的 pickle/检查点只可来自已审核可信来源；本包不分发权重、上游代码或数据库，也不自动下载它们。

Geneformer 使用同样完整的资产盘点与模型/token 版本谱系。它的基础模型预训练样本成员未能逐一审计时，不声称供者独立外部验证。代谢模型以 model_id 为建模单位，不伪造 donor 重复。

当前 Geneformer 原生扰动路径要求服务器 GPU，示例分配 1 个 GPU；CPU 兼容性不作承诺。GenKI 当前源码的 CUDA 训练/潜变量 numpy 导出存在兼容问题，本适配明确走服务器 CPU 路线。所有最小单位数、细胞数、重采样数等下限只是技术拒绝门槛，不能替代功效、网络稳定性、预测校准或实际科学验收。

## 结果验收、敏感性与衔接

每种方法真实执行 primary 和至少两套显式替代配置，完整保留输出、诊断、日志和原生对象。服务器对完整结果流式检查列语义、身份唯一性、数值、概率、空表规则和完整分母，生成与真实输出字节哈希绑定的证明及每表最多 40 行预览。预览不是完整结果；空/未评估不能解释为生物学阴性。

`server/comparison.py` 计算逐独立单位、同一特征轴上的覆盖变化、绝对分数变化、描述性排序一致性、top-k 重叠，适用时提供方向一致性。不产生基因作为重复的伪 p 值。单纯换 seed 标为随机可重复性，不当作方法稳健性。未启用的 DPI/ROOM 参数不能冒充有效替代分析。

本地 `acceptance.py` 仅有界核对回执、精确计划/源码/输入哈希、完整分母证明、预览、实际数值诊断、预设门槛和解释边界。即使一致也只返回 `RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW`；不是科学验收通过，也不证明服务器此刻环境已验证。

`server/benchmark.py` 提供仅限服务器的实测扰动对照评估 helper：完整单位/扰动/基因轴、同尺度同扰动类型、独立留出、delta MSE、no-change 基线、delta 相关与预定阈值以上方向准确率。它不是自动训练/自动验收接口，尚未运行；没有实测 truth 就不给“预测准确率”。潜变量/嵌入/速度距离禁止套用 RNA 表达误差指标。

`handoff.py` 仅准备 predicted-hypothesis 衔接，可进入条件通路探索、假说优先级或实测验证计划；必须保留物种、版本、独立单位、来源哈希和局限。不能把虚拟 KO 自动变成实测差异基因、因果靶点证据、药物有效性或 CADD 实验验证。新下游流程需新的输入 QC 和计划。

## 验证和归属

详见 `METHOD_REVIEW.md` 和 `qa/verification.private.json`。本机未拟合任何网络、模型或科学计算，未下载权重/大库，未修改共享服务或公开仓库。科学后端状态始终单独记录。

BioResearchWorkbench 最初工具层源自 Biomni；这里新增的适配/门禁/验收逻辑为派生集成。bulkKnk、scTenifoldKnk、GenKI、CellOracle、GEARS、Geneformer、Dynamo、COBRApy、CPA、scGPT、BoolNet 与 MaBoSS 的算法、软件和引用归各原作者。原始入口和论文见 `catalog.json`，应按真实使用的软件/模型版本引用。这里没有把第三方算法改称自研，也不重新授权其代码、模型或数据。

## v1.2 进一步修订

修复了可用虚构回执重现的三个返回检查漏口：空预览、未登记结果路径及重复敏感性记录。现在检查真实规范路径/角色、预览行数、每独立单位分母、WT/KO/差值算术一致性和每单位/变体唯一覆盖。训练内、验证/模型选择、校准及预处理拟合单位均纳入留出供者泄漏检查；原始训练回执和台账仍需真实复核，不扩大到基础预训练的未知成员。子进程的科学上下文、参数数值类型、输入集合、资源、实现和已批准解释器都绑定同一审阅计划。模拟时域改变明确为时点估计目标变化，Monte Carlo次数仍只是数值精度。78项本地契约/拒绝/返回格式检查通过；服务器科学运行仍0/12。
