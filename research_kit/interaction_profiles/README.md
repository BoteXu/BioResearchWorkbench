> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 私有交互画像、约束生成与原生评价扩展 v1.2

BioResearchWorkbench 的私有可选模块。最初工具层基于 Biomni；ShEPhERD-2、shepherd-score、xTB、RDKit 与各科学算法归原作者。本包只包含自行编写的适配、QC、验收、示例和来源说明，不附上游代码、权重、数据库或私人接口。

## 范围与状态

6 条实际服务器源码路线、16 类生成条件/采样分支。所有路线仍 NOT_RUN_SERVER_UNAVAILABLE，科学运行 0/6，生成分支运行 0/16；scientific_acceptance=NOT_ESTABLISHED。标准库测试、AST 与返回格式检查的实际数量见 qa/verification.private.json，不代表模型、分子引擎或科学结果通过。

| 路线 | 实际调用与输出 | 接续与限制 |
|---|---|---|
| prepare_reference_profiles | 固定几何 GFN2-xTB 单点、原子/药效团完整编号与画像 | 本机只绑定明确选择与真实返回轴；不替用户选择骨架或点 |
| score_fixed_pose | 同一给定姿势的形状、ESP、药效团评分 | 需要来源、化学状态、框架与实际 QC；相似性不是结合能 |
| align_profiles | 原作者 ESP 对齐、完整 SE(3) 变换与同一姿势分数 | 新姿势需重新对接/姿势 QC，不与固定姿势混淆 |
| shepherd2_generate | generate/generate_composition 原生条件采样，保存原始头、源坐标结果、实际 SDF 与每候选约束报告 | 化学有效、硬约束通过、评分和最终资格分别验收；不自动授予结合活性 |
| paper_native_evaluation | ConditionalEvalPipeline 构象优化、独立模态最优对齐、HP/LP Tversky、原生性质与 xTB 逐次审计 | 不需生成权重；全请求分母，不按合格候选预过滤；优化/独立对齐分数不产生对接资格 |
| prepare_generated_identities | 服务器 RDKit 状态/电荷保持互变异构/中和互变异构分组；原图与原坐标的 SDF 读回核对 | 标准化只用于身份副本，重复候选保留；计算母体不是优势质子化态或真实实验母体 |

## 完整私有工作链

1. 用既有统计/靶点/结构/CADD流程审阅来源、化学状态、受体位点、独立单位与解释范围。仅在现有服务器计算节点准备已审核参考画像和真实编号；大下载、推断与计算不放本机。
2. bind-reference-selections 把明确的骨架原子/药效团点选择绑定完整、有序的参考轴；输出保持 example_only=true。部分参考子集需新的来源准备请求，不能保留不相容的完整 manifest。
3. 生成请求锁定源码、现有软件版本、可信检查点及单独权重许可。force_download=False；哈希不能代替反序列化信任审查。没有自动安装、下载、重试、覆盖或恢复未知任务。
4. 实际采样保存全部 requested 候选。有效条件按原生实际覆盖规则、固定点、释放时点、早停与对齐窗口计算；不生效设置拒绝。骨架条件不自动保证化学子图，XYZ 转换按原生方法重推成键，不冒称预测 bond head 已成为最终图。
5. 保存 SDF 后重新读取实际图、元素/电荷/同位素/立体信息/身份/坐标，再做骨架子图与实际重新提取的药效团检查。逐点按类型、距离、方向和一对一匹配；芳香平面法向正负等价。达到子图枚举上限且无见证，标记搜索不完整，不能当完整失败。
6. 每个参考保留 profile_fidelity_scores，失败和缺失仍在分母；负引导不建立选择性。化学有效、硬约束通过和最终 eligible 分开计数。profile_scores 表是 eligible × 全参考，完整候选报告保留约束失败但已算出的描述性分数。
7. 可选原生论文评价对一个原生成 variant 的全部请求候选运行；可评价纯数值质量 HOLD 的 campaign，但不能绕过来源/身份/分支/格式 HOLD。全部 raw NPZ 及请求/receipt/contract 精确绑定，失败留全分母。
8. 可选身份整理只接收完整来源审阅通过的明确候选。状态图、保持电荷的规范互变异构、中和副本的规范互变异构三策略分别明确；保留同位素 H，显式立体设置、枚举上限和 Completed 状态。新 SDF 保存原状态与坐标，仅增加计算分组信息；不静默删除重复或挑选最优候选。
9. accept 本地只读有限 JSON、完整分母流扫描证明、预览、逐候选报告与 SHA/字节身份。单 JSON <=8MB、总选定返回 <=32MB，超限 HOLD，不截断后放行。最多 RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW，不能表示科学真值。
10. 所有候选路线 handoff 前重新执行完整返回检查；将精确 SDF、BRW_STATE_ID/BRW_PARENT_ID、来源约束和身份报告接入既有 molecular_qc。原生评价没有合格对接输出。任何新质子化、原子或坐标改变后重新验收相关约束、姿势/应变和对照，再审阅新的对接计划；准备不是提交。

## 16 类生成分支

全画像、模态/子字段、固定骨架、仅骨架、骨架阶段释放、原子/键/形式电荷 inpainting、完整固定药效团、逐点优先、仅优先点、带权多画像组合、坐标框架/内部对齐、可变数量、高级 inpainting、随机 EDM、无条件对照、中和 ESP。分支可组合，不是 16 个独立算法。具体接口/限制见 branch_review16.json/TSV 和 generation_contracts.py。

保留原生不支持的组合拒绝：ESP 包含 shape；组合接口没有逐参考优先向量，也不消费单参考 exit-vector；整数早停和比例早停不同。预期对齐步号只是计划，不冒充服务器已执行。全部分支含禁用示例，实际阈值需事前说明依据，示例数值不是已校准的通用门槛。

## 原生评价与固定姿势 QC 的区别

论文 v1 §4.5.1、pp.21–22 已通过作者正文镜像定位：评价包括 GFN2-xTB 局部优化和各模态独立对齐，HP/LP 在完整药效团对齐后计算 Tversky。当前源码调用原作者 pipeline，并旁路保留其导出会丢掉的错误/有效性/图一致性状态；不自行改写评分定义。v2 全文、补充材料、完整训练和所有外部基准仍未完成复核或复现，未引用未核验性能数字。

原生命令未显式 --gfn，报告期望方法、实际 argv、二进制和版本，method_cli_explicit=false；不能假定默认引擎模式已经独立验证。strain_energy 以 Hartree 保留，不是 kcal/mol 或结合能。超时约束单次 xTB 调用；整任务时限需既有调度规则。原生可吞掉内部异常，所以 error=None 不等于 xTB 成功；逐次回执保留超时、非零退出、缺失/收敛证据与原始产物。各模态最优分数不保证一个共同姿势，优化结果不生成 docking eligibility。

## 调用与示例

    python cli.py catalog
    python cli.py plan --request REVIEWED_PROJECT.json --out FRESH_BUNDLE
    python cli.py accept --request BOUNDED_RETURN_SELECTION.json --root BOUNDED_RETURN_ROOT
    python cli.py bind-reference-selections --request EXPLICIT_AXIS_SELECTION.json --root BOUNDED_RETURN_ROOT --out DISABLED_BOUND_DRAFT.json
    python cli.py handoff --request REVIEWED_SELECTED_CANDIDATES.json --out FRESH_QC_HANDOFF.json

plan 仅复制适配代码与请求，不搬运科研资产；在已有服务器选定项目内按精确相对路径核对 inputs、原生成请求与返回目录，未齐备不能执行。

服务器入口仅为 python3 server/runtime.py request.private.json FRESH_OUTPUT_DIRECTORY，使用既有环境、精确当前计算节点和用户另行明确派发。prepared request 的 server_execution_authorized 只有实际派发时才设 true；未知提交不自动重试。本机执行入口会在科学导入前拒绝 Windows/WSL/非分配节点。

examples/ 包含 6 条路线禁用项目示例；examples/branches/ 包含 16 类生成分支。新增两条路线的 structure_manifest 输入角色读取 templates/*.lineage.example.private.json 所示的原生成请求/回执/返回目录与候选选择。示例不是已经运行的分子结果，不以虚构科学输入冒充实际案例。

原生评价：选择一个 origin_variant 和完整 reference_id，candidate_ids 必须 []，意为覆盖所有请求；原生输入/回调/引擎/图有效率分别报告。身份整理：reference_id 必须 null、显式选择 generated_N，不能拿失败/未知来源候选做合格母体。

## 版本、归属与隐私

方法差异、定位和保留边界见 METHOD_REVIEW_v1_2.md；当前机器可读状态见 CURRENT.json。v1 与 v1.1 安装保持原字节；旧计划/验收因源码变化失效。旧 README 和来源资料保留为历史，新增 v1.2 审阅记录说明当前结果。

只更新私有库与已有 skill 的私有引用。不改 MCP 注册/共享服务，不连接服务器，不公开推送 GitHub，不上传代码、路径、主机、私有数据、日志或结果。包内含私有来源与采用记录，不能公开分发。
