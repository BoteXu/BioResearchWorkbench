# I01 至 I08 筛选与命中发现数据契约

本目录的 example.json 是可填写的数据模板，不是引擎输入或自动验收的 JSON Schema。module_id 对应完整手册章节；rows 为空表示尚无观测。schema_version 管理数据格式，module_version 管理研究规范。实际填写时保持身份、单位、缺失原因与来源一致。

I01 记录查询和参考化学状态。feature_ids 是特征ID数组，required_feature_logic 是明确的组合规则，tolerances_and_units 是逐特征数值与单位对象。更改特征半径或排斥体积要升级 query_version；不能沿用旧查询的通过率。

I02 记录片段锚点、连接原子映射和截断补氢定义。heavy_atom_count 是整数；化学状态、pose_cluster_id 和 evidence_id 使用字符串。由大配体截断的片段不是未经记录即可获得相同化学身份的小配体。

I03 每行是某候选在某靶点和方法/实验背景下的证据。value 为数值或 null，relation 保留 =、<、> 等关系符号，unit 明确量纲；status 区分有效测定、失败、未测和不适用。不能把跨靶点原始对接分差写成实测选择性。

I04 使用共同核心及取代位点建立系列关系。匹配分子对与环境由显式映射定义；实验终点与条件不一致时分层保留。值相同但删失关系不同的记录不能直接算活性差。

I05 每行保留实物批次、观测、检测方法、独立单位与技术重复。measurement_validity 与 evidence_level 分别记录数据有效性和证据层次。计算失败、采购失败和无效测定不能产生 inactive 标签。

I06 每条变换边保存 source_node、target_node、atom_mapping_path、charge_change 及 direction。charge_change 为有符号整数；费用估计同时写单位和估计依据。没有相连路径的节点不能与其他节点共享已标定自由能尺度。

I07 冻结每轮当时可见数据。data_cutoff、selected_at 和 label_available_at 用带时区的 ISO 时间；pending_status 单独保存。新标签不得倒填为旧轮已知标签。

I08 记录变更影响。各 changed_* 和 reusable_raw_outputs 使用 ID 或明确文件引用数组；所需汇总单独列出。原始分数可复用不代表全库百分位、多样性聚类、候选选择也可直接复用。

通用要求：稳定ID为非空字符串，数值不混入单位文本；未知值用 null 并在相应记录中注明原因。field_names 和 row_template 提供字段起点，研究特定字段应添加到字段字典。输入文件表记录路径、内容哈希、版本与来源；review 初始为 pending，只有真实审查完成后填写审查人和证据。
