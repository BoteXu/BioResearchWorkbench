> 以下为保留的 v2 历史说明。当前 v3 的 71 项更新、运行边界与未实测台账请先读 README71项扩展.md。

# 私有深度整合 v2：QC、分析、训练、结构预测与结果验收

本版是对上一版“元数据编排层”的实质补充。新增服务器科学代码和读取实际诊断输出的验收器；仍复用原 Biomni 共享工具、私有转录组/CADD 规范与既有服务器环境。本机不训练模型、不处理科研矩阵/轨迹、不推理结构，不安装科学环境或下载权重。

**当前状态：代码已实现并完成本地静态/有界返回审查测试；所有新增科学后端尚未进行服务器实机验收。** 用户本轮确认服务器暂未就绪，因此没有把条件分支或源码存在标成真实运行通过。

## 上版复查与修复

| 上版不足 | v2 的实际补充 |
|---|---|
| 计划和状态字段不能验证原始数据 QC | 独立 matrix_qc 科学阶段读取真实矩阵/元数据，计算样本指标、设计秩、独立支持、PCA/相关性；正式 R 分析核对确切 QC 产物、原矩阵与元数据哈希和审查记录 |
| 统计咨询之后缺少可执行分析 | DESeq2、limma、ORA、fgsea、WGCNA、MOFA2 的固定服务器 R 分支；完整保留未显著、NA、过滤和失败记录 |
| 单细胞只有对象/样本契约 | 读取真实计数层的 QC、逐样本支持、条件性 Scrublet、聚类/描述 marker；pseudobulk 必须消费对应的实际细胞 QC 决定 |
| 机器学习只有划分和接口 | 实际训练、训练折内插补/标准化/特征选择、分组嵌套验证、独立校准、锁定测试、预测/曲线/选择稳定性和有条件导出 |
| CADD 只有声明审查 | 实际结构/残基映射、化学状态与 PoseBusters 检查、固定 Vina 执行、真实轨迹诊断、热力学账本与删失事件计算 |
| 结果验收只核对角色和哈希 | 必须选回实际科学诊断文件；检查观察值、概率、P 值、轨迹时间、姿势检查、收敛警告和模型划分，而非只读 passed |
| 跨组学到结构主要是非空 ID | 检查 gene→transcript→protein_isoform→structure 的真实选定映射表、物种/版本/唯一性、测量状态与共享队列；表达方向不变成蛋白活性方向 |
| 序列/AF3 未串入 | 复用现有公共序列查询，保留异构体/版本；AF3 输入、序列来源、现有服务器多 seed/sample 执行与全输出验收 |

## 可执行科学分支

`profiles.json` 列出 23 类执行后端及参数/输入/结果要求。`server/` 中是实际计算代码，只有服务器入口通过当前计算节点和派发检查后才调用。

| 后端 | 实际工作和结果 |
|---|---|
| matrix_qc | 原始计数或明确的 log2 强度；样本/基因身份、缺失/库量/检出、配对/技术重复、设计秩、QC PCA 与样本相关；保留原正式矩阵 |
| r_omics：DESeq2 | 严格原始整数计数、预设过滤、设计与对比、离散度/size factor、完整差异表和 NA、归一化/VST/PCA/相关性 |
| r_omics：limma | 明确 log2 强度/标准化表达；缺失保持可见、设计/对比、eBayes 或预设 treat；适用于经协议审查的芯片、蛋白/代谢等强度分支 |
| r_omics：ORA/fgsea | 实际受检背景、集合版本、完整有向排名、集合大小、检验家族与完整结果；富集不建立机制 |
| r_omics：WGCNA | 实际网络输入 QC、soft-threshold 诊断、模块/特征归属、eigengene、membership；条件性 trait 关联及独立参考 preservation |
| r_omics：MOFA2 | 显式样本轴与视图尺度/缺失、实际拟合、scores/loadings、view variance、模型；因子与结局关联另作预设检验 |
| singlecell | 原始计数 QC、明确线粒体 ID、细胞/供者流失；只有适配的 droplet UMI 才可选 Scrublet；HVG/PCA/邻接/Leiden/UMAP/描述 marker |
| pseudobulk | 依实际 QC keep 表按独立单位×条件×细胞类型求和；保留低细胞支持组的资格状态，不把它们变为生物零值 |
| scvi | SCVI、TOTALVI 实际训练与训练历史；TOTALVI 必须是同细胞原始 RNA/ADT 计数。未知 API/依赖报错，不装软件补洞 |
| multiomics_concordance | 真正配对独立单位、版本化 feature map、完整缺失分母的关联与 FDR；不是协变量调整、中介或因果证明 |
| ml | 分类/回归的有界模型比较、组约束嵌套 CV、独立校准/可选 split-conformal、锁定测试、基线、曲线和选择稳定性 |
| survival | 独立 first-event/censoring 输入、嵌套分组 CV、C-index/IPCW/时间 AUC；不适用的竞争风险、左截断会在拟合前拒绝 |
| graph_training | 图级独立单位的 GCN/GAT/GraphSAGE；归纳式 train/tune/test、训练节点特征缩放、tune early stopping、测试结果、训练历史与可选 safetensors |
| structure_qc | PDB/mmCIF 真坐标、链/残基/插入码、altloc、占据率、必需骨架原子、选定残基对应；不自动修结构或质子化 |
| molecular_qc / pose_qc | RDKit 化学状态/立体/3D/碎片检查、失败分母；PoseBusters 真检查、公共受体坐标系下的对称性 RMSD（条件性） |
| vina_docking | 已有 Vina 可执行文件和版本、受体/QC/准备谱系、完整化学状态×seed、参考/阴性对照、真实退出/日志/pose/评分；评分后仍需姿势 QC |
| md_analysis | 明确 PBC 预处理、拓扑/参考原子轴、稳定时间轴、RMSD/RMSF/Rg/接触及可用 ESS；帧不当作独立重复 |
| free_energy / kinetics | 单微态有符号单位/标准态/协方差账本；独立起点 first-passage 风险时间/删失/限定常风险模型。它们不替代 FEP/ABFE 引擎或证明无偏动力学 |
| af3 | 现有授权 AF3 安装的真实推理调用；全部 seed/sample、实际 mmCIF 和完整 confidence/summary、token-chain 轴及选定链对；不下载/分发权重 |

上表若把组合行拆开，共 23 类 Python 入口，其中 R 入口内含 6 个具体方法。目录数量不代表都已运行。

## 机器学习/模型训练选择

已实现 27 个模型/方法选择：

- 表格分类/回归：elastic net、ridge、lasso、SVM、随机森林、ExtraTrees、直方图/普通梯度提升、AdaBoost、KNN、MLP、同划分基线；分类 Naive Bayes；条件性 XGBoost、LightGBM、CatBoost。
- 生存：CoxPH、Cox elastic net、随机生存森林、梯度提升生存、survival SVM。
- 图模型：GCN、GAT、GraphSAGE（当前为归纳图级分类，不能套到含所有测试节点的传导网络）。
- 单细胞/多组学潜变量：SCVI、TOTALVI、MOFA2。

训练质量要求包括：真实独立单位与家系/队列隔离、每折类别/事件支持、训练内学习一切变换、搜索预算、独立校准集、测试集不参与调参/阈值/早停、完整 per-unit 预测、同划分基线、不把训练 SHAP/重要性当因果、可用的不确定性及负结果。

不把“所有模型都比较一遍，再挑测试集最高分”作为默认。监督多组学输入必须先完成真实匹配、缺失策略和尺度合同。Cox 还需 PH/敏感性审查；风险分数不是生存概率。当前通用 sklearn 后端不宣称支持训练状态断点恢复；图模型的 safetensors 是权重产物，不是含优化器/RNG 的恢复检查点。未知训练提交始终先核查，不自动重试。

## 序列与 AF3

`sequence-plan` 和 `sequence-fetch` 复用已有 bridge 的 UniProt/Ensembl 查询，没有创建新的数据库客户端。外发只允许用户明确批准的公共 accession；不把本地 FASTA、私有构建体、患者变异或草稿发送到公共服务。NCBI/RefSeq 继续复用已安装的 NCBI 工具。版本化 Ensembl ID 不会被默默去掉版本查询当前序列。

FASTA 审查检查确切 ID/异构体、字母表、重复、长度和序列哈希；物种、release、构建体、切割/标签与链映射仍需来源复核。AF3 的 sequence_manifest 把每条链的序列哈希、物种、序列版本、异构体/构建体和源回执连起来。

AF3 输入区分 native dialect/version、链数与化学计量、明确 seeds、RNA/DNA/protein/ligand、修饰和共价 atom mapping。离线推理不得把缺失 MSA/template 字段偷偷当成空；显式空字段是用户选定的无 MSA/无模板试验。输入 schema 与具体已安装引擎源码必须匹配，不假定最新文档等于服务器版本。

多个 seed/sample 是随机预测候选，不是平衡态构象分布、群体比例或独立生物重复。按实际 token_chain_ids 审查选定链对，不取目录第一个文件或直接以链文件顺序猜矩阵轴。ipTM/pTM/PAE 不自动建立亲和力、靶点结合或药效。AF3 结果进入后续真实结构、姿势及模拟准备 QC；不能跳过。

## 使用

本机只运行根目录的准备和有界审查入口，使用既有 Biomni Python。所有新目录/输出使用新路径。

```text
<existing-python> workbench.py coverage --out selected-contracts.private.json
<existing-python> workbench.py plan --request scientific-plan.private.json --out server-bundle-new
<existing-python> workbench.py accept --request acceptance-request.private.json --root selected-return --out reviewed.private.json
<existing-python> workbench.py crosslink --request crosslink.private.json --root selected-tables --out handoff.private.json
<existing-python> workbench.py sequence-plan --request approved-public-sequence.private.json --out query-plan.private.json
<existing-python> workbench.py sequence-fetch --request approved-public-sequence.private.json --out sequence-receipt.private.json
<existing-python> workbench.py fasta-check --request fasta-scope.private.json --root selected-fasta --out sequence-qc.private.json
<existing-python> workbench.py af3-input-check --request af3_input.private.json --out af3-qc.private.json
```

`plan` 默认生成 `server_execution_authorized:false`，不会连接或提交。真正派发仍用现有共享 SSH，确认当次计算节点和已安装环境，再明确派发。运行时检查精确主机、源码/参数哈希、CPU/GPU预算、新输出目录和原输入哈希；失败保留日志/部分产物，不自动安装/下载/恢复。

服务器上才可执行：

```text
<existing-server-python> server/runtime.py server_request.private.json NEW_OUTPUT_DIR
```

`server/scientific_smoke.py --host CURRENT_COMPUTE_HOST --out NEW_DIR` 是后续实测准备好的真实合成运行脚本：训练有基线/嵌套划分的模型、验证真实设计秩混杂阻断；指定已有 Rscript 时再检验已知模拟对比方向。**本轮未运行它。** AF3/Vina/MD 等仍需单独的引擎/体系验收，不会由该脚本的一次成功代替。

## 完整性边界和剩余验收

28 类标准工作流、81 项分析契约、65 个私有转录组模块、34 个 CADD 模块均保留。`coverage_depth.tsv` 逐项区分本轮新增科学路线与必须复用/验收现有服务器软件的分支，不能把目录全覆盖当成 81 个执行后端全覆盖。遗传/MR/coloc、部分表观/微生物、复杂通讯/轨迹/扰动、增强采样、跨引擎物理资格和真实自由能模拟仍需选定已有服务器后端及专用诊断，不由本版通用模型替代。

本次新增的科学代码尚未在服务器执行；R 与科学包 API、数值结果、GPU/引擎许可和实际体系仍属待验收层。根目录本地测试验证语法、准入/拒绝、文件/参数绑定和有界结果逻辑；不代表科学运行或科学有效性。私有安装可以用于准备与审查，不能据此宣布真实课题已经分析通过。

所有源码、示例、私有配置、服务器路径、回执和研究结果保持私有；不修改公开主仓库或当前共享 MCP 注册。原 v1、原转录组/CADD 规范和源文档保留。

## MSA 增补

新增 MSA search/align/QC/filter/pair 和 AF3 data-only 阶段，详见 [MSA 获取与 AF3 衔接规范](MSA获取_QC_配对_AF3衔接_规范.md)。手工配对不会误放进 AF3 pairedMsa 再被内部重排；明确使用 unpairedMsa、清空 pairedMsa 并关闭 overlap resolution。
