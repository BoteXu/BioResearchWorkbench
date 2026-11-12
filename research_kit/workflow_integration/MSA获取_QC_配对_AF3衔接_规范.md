# MSA 获取、QC、配对和 AF3 衔接

本模块按“序列身份 → 同源检索/选定同源集 → 比对 → A3M/来源审查 → 条件性配对 → AF3 输入 → 结构与不确定性复核”组织。科学搜索/比对/Neff 计算只在已有服务器运行。原始查询、原始命中、原始 MSA 和失败记录保留，清洗/截取/采样必须生成派生版本。

## 1. 查询合同先于检索

每条查询记录 accession/稳定 ID、数据库/序列版本、物种、基因与转录本/蛋白异构体、成熟链或全长/构建体、切割/标签/突变/缺失注释、序列哈希，以及后续链 ID。canonical 不能自动替代研究中的 isoform。保留不确定/非标准残基并明确处理：不能为通过 AF3 把 X、缺口或终止符随意改成其他氨基酸。

蛋白同源检索不是核酸序列检索；RNA/DNA 不能送入蛋白 MMseqs2 路线后当成有效进化信息。相似序列不是已证明的直系同源、相同功能或相同互作对象。

私有序列、构建体和临床变异默认留在已有服务器的本地数据库检索，不自动送到公共 ColabFold/MMseqs2/EBI 等服务。公共 accession 查询通过已有工具；一个“生成能力”请求不授权上传真实私有序列。

## 2. 已实现的获取路线

| 任务 | 实际入口 | 适用边界 |
|---|---|---|
| AF3 原生 MSA/模板 | `af3_data_pipeline` 调用已有 run_alphafold.py，data pipeline=true、inference=false | 复用其本地 JackHMMER/核酸搜索/模板流程和已有数据库；不下载模型/数据库、不运行结构推理 |
| 本地蛋白数据库搜索 | `msa_search` 使用现有 MMseqs2 的 createdb/search/convertalis/result2msa | 单查询、明确蛋白数据库、版本与二进制哈希；产生真实 hits 和 A3M，不把多查询二进制数据库当文本 |
| 已选同源序列的 MSA | `msa_align` 调用已有 MAFFT、Clustal Omega 或 MUSCLE5 | 它们是比对步骤，不自动证明同源集/分类/完整性正确；MUSCLE5 不与 v3 CLI 混用 |
| 已有 A3M 复核 | `msa_qc` | 实际解析 query/列坐标、覆盖、重复、模糊残基和限定定义的有效深度 |
| 有记录的派生过滤 | `msa_filter` | 显式 coverage、ambiguity、精确重复策略；保留 query，保存逐行保留/排除原因，原件不改 |
| 手工跨链配对 | `msa_pair` | 明确 ledger、物种和唯一同源审查；可选显式缺失 padding，不能把它计作观察到的同源序列 |

AF3 原生数据阶段会提取每链 MSA、模板和完整 prepared data JSON，并保存 registry。空 MSA 以明确 empty 状态报告，不创建一个空文件后称作“已有 MSA”。该阶段不需要宣称权重可用，也不产生预测构象。

MMseqs2 入口使用 mode 5 的平面 A3M，并核对 query；无法解析、含二进制分隔、query 被工具改变或 match 列数异常时停止，不猜测编码修复。MMseqs2 数据库与普通 FASTA 不是同一输入类型。数据库必须是已安装且已选择的版本。

## 3. 来源与参数清单

至少保存：查询文件/序列哈希；检索程序路径与二进制/源码哈希、版本；数据库来源、release、索引/格式和 engine-used 文件清单；E-value、覆盖定义/模式、命中上限、敏感度、线程；比对方法；query ID；A3M 输出与日志；是否过滤/子采样、精确规则和 seed。

数据库完整性有两个明确层次：`full_sha256` 在服务器复核所列组件实际字节；`verified_snapshot_stat` 核对已有已验证快照的大小/mtime 与先前回执。后者不能被表述成本轮重算了全部数据库哈希。两者都只覆盖所列 engine-used 组件，仍需核对安装引擎实际使用的数据库路径配置。只写一个 release 名称或 dbtype marker 不足以证明数据库内容没变。

数据库命中上限被触及、数据库没有目标物种覆盖或来源只包含部分分支时，应标识搜索并不穷尽。不得把无命中写成“该蛋白没有进化同源”，也不得把同一母体的片段/重复/近重复当成独立多样性。

## 4. A3M 坐标与实际 QC

服务器解析器要求第一条是确切 ungapped query。大写残基和 `-` 占 query match 列，小写残基表示插入；删除插入后，每行列数必须等于 query 长度。大小写、点号、缺口和模板索引各有语义，不能简单把所有字符大写或截成相同长度。

对 aligned FASTA 的转换依 query 的 gap 列决定插入状态，保留同源中的插入为小写，不直接删除生物学残基。query 发生异构体替换、截短、错位或未知残基替换时，停止并重新绑定来源。手工配对中整行 gap 可是明确结构性 padding；它不是一个观测同源序列，不能参加普通同源深度计算。

实际输出包括每行 query 覆盖、在共同非缺口 query 列上的 identity、模糊残基、精确重复、序列来源哈希，以及全部/唯一 match 序列数。蛋白 N 是 Asn，不会被错误当成核酸 N 的模糊碱基。

本版 Neff 的定义明确为：每行权重等于与它达到指定 identity 阈值的行数的倒数，再对行求和。identity 分母是共同非 gap 的 query 列；它不是默认等同于所有 HHsuite/AF/文献定义。阈值、全量/子集范围和计算预算必须记录。超过本次明确预算时报告未计算，不能把子集 Neff 写成全体 Neff 或编一个数通过验收。

Neff、总行数、query coverage、各结构域/界面区域的局部覆盖、分类/系统发育多样性需要合看。没有适用于所有蛋白、抗体、无序区、跨膜或 RNA 任务的统一最低深度。低复杂度、跨域架构不同、片段或特定谱系过量命中需要单独审查；高深度也可能只是在重复同一类信息。

## 5. 配对合同与 AF3 的重要区别

手工 ledger 记录 pair_id、chain_id、sequence_id、taxon_id、源序列哈希、同源资格和测量状态。默认是同物种且经过唯一同源审查；旁系同源歧义保留，不自动取最高 identity 的一条宣称正确配对。跨物种复合体使用单独的 reviewed-cross-species 路线，不能硬套同物种配对。

AF3 的 `pairedMsa` 通常用于其内部基于 UniProt 物种信息的配对，并不等于“我的每条链已经具有相同行序”。[官方输入说明](https://github.com/google-deepmind/alphafold3/blob/main/docs/input.md)建议精确手工行配对使用 `unpairedMsa`，同时 `pairedMsa=""` 且 `--resolve_msa_overlaps=false`。否则内部重配对/去重可能改变精心构造的行对应。

本版手工配对入口会记录该目标字段和开关；提供 AF3 输入时还可物化一个新的 manual-MSA 输入及绑定回执。AF3 推理入口对手工模式核对相同的蛋白链、输入哈希、行 ID/顺序，拒绝重跑会改变它的数据阶段或打开 overlap resolution。非蛋白实体的来源不因此丢失。

若明确需要缺失链 padding，ledger 必须标为 structural_padding，sequence_id/序列哈希留空，且单独授权这个表示策略。输出保留“未观察到同源”的事实，不把 gap 行当成实验配对、不把所有 gap 行计入有效深度。若没有合理配对证据，保留 unpaired 路线并比较结构结果；不为了凑 paired 数量制造关系。

## 6. 模板与敏感性分析

模板需要源 PDB/mmCIF、链/构建体/物种、版本/发布与实验日期、相似性和缺失片段、queryIndices/templateIndices 的明确 0-based 对应。模板 query 坐标必须落在实际序列内，未解析残基必须计入模板轴；不能把作者残基编号直接当数组下标。

预测/基准任务预先定义 template cutoff 和训练/测试隔离，不用答案结构回填再宣称 blind prediction。保留无模板、保持同一 MSA 的模板对照；可比地改变 MSA 来源、过滤/深度、配对策略或结构域方案时，固定模型/模板/seed/sample 预算并分别记录。不要同时改很多项后把改善归因于其中一项。

建议按问题而非套餐选择：原始与过滤 MSA、来源/谱系多样性差异、不同深度子集、native pairing 与有证据的 manual/unpaired 路线、template/no-template。每种保留完整候选和失败，不按最高置信度挑一个就删除其余；不以 query-only 或深度最高作为通用最优默认。

## 7. 返回验收

应返回：query/链来源、数据库与工具版本回执、hits（若存在）、原始/派生 MSA 哈希、逐行 QC/过滤原因、Neff 定义与计算范围、配对 ledger 与实际行对齐说明、模板映射、prepared AF3 JSON，以及后续每个 seed/sample 的实际结构/完整 confidence/summary。

MSA 为空、仅 query、浅/偏倚、来源未明、配对冲突、模板轴不明、截断数据库搜索或包/模型版本不匹配，分别保留状态和限制。接收 MSA 文件不等于接受其生物学配对，接受结构文件不等于证明构象比例或结合活性。

大型 MSA/数据库和全量结构留在服务器。本地仅检查选择过的有界报告、清单和源绑定；没有要求把全数据库下载到电脑。`workbench.py accept` 必须看到真实诊断数据，不能仅凭 passed；本轮所有新增科学搜索/比对/Neff/AF3 数据阶段仍未实机运行。

## 8. 本次 SciSpace 与原始来源复核

本次 SciSpace 的检索及限制提取保存在 evidence。检索返回的限制有些明确只覆盖摘要/片段，没有给出全文限制；这不是“论文没有限制”，也没有被当作完整系统审查。

- [MULTICOM4 单链 CASP16 研究](https://www.nature.com/articles/s42003-025-08960-6)核对到多源 MSA、domain、采样和排名的组合策略；其单链结果不能直接变成任意多链/核酸体系的最优规则。
- [MULTICOM4 复合体研究](https://doi.org/10.1002/prot.26850)涉及复合体与化学计量条件，不能把两阶段信息可用性不同的结果混作相同任务。
- [AF3Complex](https://doi.org/10.1093/bioinformatics/btaf432)是可选方法研究，未自动替换已有 AF3 引擎。
- SciSpace 还返回 2026 年 depth-over-pairing、MSA/模板工程和解释研究预印本；只作为候选敏感性方案线索，未据此强制采用“越深越好”或“永远不需要配对”。
- [MMseqs2 官方格式定义](https://github.com/soedinglab/MMseqs2/blob/master/src/commons/Parameters.cpp)核对 mode 5 是 A3M、mode 6 含 alignment info；[AF3 原生 pipeline](https://github.com/google-deepmind/alphafold3/blob/main/src/alphafold3/data/pipeline.py)用于复用本地 MSA/模板检索。

没有安装/分发这些研究的代码、模型或数据库。后续在用户已有服务器按所选版本、真实输入和实际回执验收，才能把源码实现提升到已验证运行。
