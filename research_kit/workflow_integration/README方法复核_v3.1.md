# 私有 71 项逐项方法源码复核 v3.1

本轮已形成 71/71 条逐项方法判断，范围为：声明实现的方法与估计目标、独立单位、实际 QC、分析分支、输出语义、结果验收及跨流程衔接。每项记录对应的源码位置/哈希、具体修复和与原标准软件的差异，见 `71项逐项方法源码复核.md`、`method_review71.json` 和 TSV。

这是源码审阅完成，不是科学验收通过。科学运行仍为 0/71；所有状态保持 `NOT_RUN_SERVER_UNAVAILABLE`、`scientific_acceptance: NOT_ESTABLISHED`。本机只做语法、契约、拒绝/返回格式检查与私有打包，没有运行 NumPy/R 拟合、模型训练或分子计算。生产使用仍需实际服务器版本、真实输入/上游数值 QC、对照/基准、诊断和独立科学复核。

本轮实质补充包括：

- 显式 Welch/配对/HC3 对比；跨单位、秩亏、缺失、零变异和未检验状态分开；不能冒充 moderated limma。
- DRIMSeq 真实 gene/feature 过滤与 stageR 层级控制；DEXSeq 原生 perGeneQValue；APA 在拟合前检查输入证据；真正的 isoform 增减配对及 CDS、结构域、NMD 差异。
- SKAT、burden、SKAT-O 的实际调用与 null calibration；定量表型 SD/病例比例明确；ABF 和新增 coloc.susie 多信号路线，signed LD/等位基因/收敛/后验质量分别验收。
- PSM 与 peptide 层 target-decoy 控制，按样本/搜索类别保留完整分母；不宣称已控制 variant/protein 层 FDR。
- 供者可比 LR 丰度分数衔接，禁止各供者 rank 直接相减；参考复合体亚基、缺失细胞群和低覆盖未评估保留。
- 甲基化预定义区域/配对变化关联、HUMAnN 分类丰度/CLR 背景、脂质独立单位斜率、未分配 clonotype 和 rarefaction 解释范围修正。
- 空间 block null/置信与 residual Moran、时间 nuisance/group 样条及有效重采样分母、Slingshot 边 Jaccard、SPIEC-EASI 原生边选择频率。
- ORF 保留条件 read 级结果，新增真实独立单位匹配阴性 ORF 对照的 sign-test 分支；完整单位/ties/覆盖分母，不能称确认翻译。
- 多版本 RCTD、真实 MuSiC 参考覆盖、持出 SCENIC 单位排除和真实训练集合、实际 PLINK 变异/allele-count/连续或二分类验证分支。

服务器对完整结果做流式身份/列/数值/概率/空表检查，保存完整分母证明和每表最多 40 行预览；实际敏感性重跑按同一身份与每列原单位比较，不把均值或行数变化等同于稳健性。Monte Carlo 次数变化明确为数值精度；科学稳健性不由此自动建立。大结果不需要为本地检查导入整张矩阵。

返回检查要求精确输入集合、当前源码、原请求/计划与实际完成回执；历史成功不能代替当前服务器/依赖验证。跨流程 materialize 绑定具体源结果角色、源科学上下文、已审阅变换源码/规格、关闭执行的目标模板/输入字段，产出后必须重新 QC 和生成新计划。转换不是提交，未知提交不得自动重试。

Biomni code_review 静态扫描只用于定位候选问题；结果与人工语义复核分别保存。匹配项不是漏洞/方法错误的自动判决，扫描成功不等于科学正确。本轮所有材料、旧规范、配置、回执、草稿及 ZIP 只保存在私有库，原已采用版本和原始文件保留，公开 GitHub 不更新。

调用仍复用现有 workbench.py 的 plan/accept/workflow71-plan。`examples71/` 是禁用的结构示例，需要真实输入、版本、数值 QC 和当前服务器信息；不能把示例当实际分析或原始参考结果。旧计划因方法名称、结果语义和源码变更而失效，必须重新生成，详见 `method_migration.json`。
