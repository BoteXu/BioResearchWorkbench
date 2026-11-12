> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 用户提供 bulk 流程的静态审查

## 范围与方法

检查来源压缩包的 26 个文件（15 个 Python、配套 skill/说明/配置与 3 个基因集）及学习讲义正文。归档目录、重复成员、符号链接、压缩展开预算、UTF-8 和 Python AST 检查通过。所有源脚本仅静态阅读，未执行。扫描发现 18 个候选匹配；手工区分正常科学软件调用、网络传输及危险默认行为，未发现明显提示覆盖或凭据窃取指令。静态扫描不能保证没有恶意或动态风险。

原始来源保持本机原样，仓库存入选定代码的非执行文本快照，避免原始 DOCX 属性和机器环境描述泄露。源文件中的安装/执行说明不视为授权。

## 需要拦截或修正的项目

| 项目 | 源码位置 | 发现及当前处置 |
|---|---|---|
| QC 非强制门禁 | `step1_qc.py`, `run.py` | QC 输出标记但后续没有检查接受/拒绝决定；单独 `--steps de` 可绕过。新的适配不执行该入口，正式分析复用已有强制 QC。 |
| 数据尺度含混 | `utils.load_expression` | 自动 log2 和负值 clip；不能将原始计数这样送入 limma-trend。新配置拒绝隐式尺度与转换。 |
| 样本静默取交集 | `utils.setup_contrast` | 缺失样本或额外元数据被静默丢弃。新入口要求精确样本集。 |
| 协变量静默丢弃 | `utils.covariates_frame`, `step2_de.py` | 缺列只警告，设计发生改变。新入口拒绝缺列/缺值。 |
| 独立单位和设计 | 配置/DE | 原配置没有 unit、配对或必需设计秩/残差自由度门禁。新入口显式检查，统计咨询复用现有工具。 |
| 参考和物种 | `utils`, PPI/WGCNA | 原脚本默认 human，未绑定 assembly/annotation/namespace。新配置要求来源上下文与参考版本。 |
| QC 深度与性别 | `step1_qc.py` | Σ2^normalized 不等于实测 read depth；固定 sex-marker 12 阈值不足以证明错标或污染。适配不沿用这些结论。 |
| 自动联网 | `utils.attach_symbols`, `step7_ppi.py`, `step5_tf.py` | 候选列表自动传到 MyGene/STRING；网络资源未绑定许可/版本。新工具离线，公共查询独立授权。 |
| 清空旧输出 | `step6_wgcna.py` | `shutil.rmtree` 删除 wgcna_run。原脚本禁用，采用新输出目录与回执。 |
| 旧结果和状态 | `run.py`, `utils.provenance` | 下游失败继续，最终可能退出 0；跳过也可被记录为完成；只哈希配置，没有输入/输出/源码/版本绑定。新验收拒绝失败/跳过阶段和错配。 |
| ORA universe | `step3_enrichment.py`, `step9_key.py` | 只传 universe 的数量，不能保证基因集被正确限制到可检验 ID 宇宙。现有富集路由使用显式测试基因集合。 |
| GSEA 显著性标签 | `step3_enrichment.py` | 无 FDR<0.25 结果时回退到所有结果，但图标题仍写 FDR<0.25。报告必须显式标明探索性及无显著结果。 |
| GSVA | `step3_enrichment.py` | `gsva_scores` 有定义但 `run` 没有调用，且输入 Ensembl 与 symbol 基因集未做对应。原 GSVA 功能未验收。 |
| DoRothEA/VIPER | `step5_tf.py` | 没有实现；PROGENy 调用重复，返回类型/方向依赖版本。复用已存在固定服务器 ULM/MLM 接口，VIPER 保持未实现标签。 |
| WGCNA kME | `step6_wgcna.py` | Z 是 samples × genes，却按 `Z[i]` 与 sample eigengene 相关，行/列轴错配。原引擎保持 review_only。 |
| WGCNA traits/热图 | `step6_wgcna.py` | 对两类非空字符串 `.astype(bool)` 可变成全部 True；转置后热图按模块取列错轴。需在服务器修正并验证。 |
| WGCNA 解释 | skill/methods | 多病因混合或 R²<0.8 不能单独给出“网络必然失败”结论；需问题对应的混杂、连接度、稳定性与保留性检查。 |
| PPI 展示 | `step7_ppi.py` | 只留最大连通分量，遗漏孤立点和其他组件；STRING functional 不能直接说物理互作。新路由要求完整组件审计。 |
| cell/key 基因轴 | `step8_deconvolution.py`, `step9_key.py` | 判断基因 ID 是否在 `expr.columns`（样本轴），可导致候选全部丢弃。原流程禁用。 |
| 心脏固定 marker | `step8_deconvolution.py` | 不是通用组织分解；且 symbol marker 对 Ensembl 直接评分可能无覆盖。适配要求选定组织、物种、命名空间与覆盖。 |
| SHAP/candidate 合同 | `step10_ml.py`, `step9_key.py` | SHAP 写 gene_id/symbol，key 读 gene；新 SHAP 返回数组轴以及排序也需验证。训练集解释不得称验证。 |
| ML 选择乐观偏倚 | `step10_ml.py` | Pipeline 内选特征有帮助，但同一 CV 比较众多模型再挑赢家未给独立外层评估；无 unit-aware split。要求独立单位拆分与 nested 模型选择。 |
| 外部模型未冻结 | `step11_validation.py` | 按每个外部队列可用基因重训，并用测试队列总体均值/SD 标准化。不能称为一个预先锁定模型的严格外部验证；保留 review_only。 |
| 格式和功能差异 | `SKILL.md`, figures/report | skill 引用若干不存在的脚本名；图注声称自动删样本；缺失图被静默跳过；Word 只有标题/极少正文，不能称完整可编辑报告。复用既有交付流程，验收实际内容。 |
| HTML 私有内容安全 | `step13_report.py` | project/case/control 插入 HTML 时没有转义；原报告生成器禁用，正式交付需转义文本并验证无外部请求与遗漏。 |

## 文档与算法边界

讲义是方法地图，覆盖的 FASTQ、DTU、剪接、生存、时间序列等并不在压缩包中完整实现。讲义建议和机器特定安装状态不能作为当前服务器验证证据。

相关权威方法依据：

- [scikit-learn 的交叉验证与训练集变换原则](https://scikit-learn.org/stable/modules/cross_validation.html)：预处理从训练集学习并用于未见数据，模型选择与最终评估需要相应独立性。
- [limma 用户指南](https://bioconductor.org/packages/release/bioc/vignettes/limma/inst/doc/usersguide.pdf)：方法应符合输入尺度与设计。
- [WGCNA 项目](https://cran.r-project.org/package=WGCNA)：共表达分析不能从软件调用直接推断因果驱动。

这些依据支撑方法边界，不等于原始源码被验证。没有真实研究分析结论产生。
