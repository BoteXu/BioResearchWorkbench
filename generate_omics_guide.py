"""Generate workflow documentation from the public static contracts, without importing analysis tools."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def generate():
    data = json.loads((ROOT / 'omics_workflows.json').read_text(encoding='utf8'))
    workflows = data['workflows']; extensions = data['extensions']
    out = [
        '# 组学标准流程与条件拓展', '',
        '这是 BioResearchWorkbench 原创的流程、QC 和结果契约，最初工具基础来自 Biomni。第三方算法、文档和数据库保留原归属。本页从 `omics_workflows.json` 自动生成。', '',
        f"版本 {data['catalog_version']}：{len(workflows)} 条流程、{len(extensions)} 类拓展、{sum(len(w['extensions']) for w in workflows)} 个流程到拓展的关联。关联数量不是独立算法或已经验收的执行后端。", '',
        '## 调用与状态', '',
        '- `omics_workflows.inspect_omics_workflows(workflow="", family="", detail=false, limit=40)`：离线发现目录；完整细节包括标准步骤、QC、输出角色和官方参考。',
        '- `omics_workflows.plan_omics_workflow(workflow, context, design, input_manifest, extensions=null)`：只生成绑定版本的计划，拓展必须主动选择。',
        '- `omics_workflows.audit_omics_readiness(plan, checks, statistical_receipt=null, backend_receipt=null)`：审查有定位来源的 QC、统计咨询和已有服务器验收摘要。',
        '- `omics_workflows.audit_omics_result_bundle(plan, result_manifest, execution_receipt, checks, statistical_receipt=null, backend_receipt=null)`：审查必需结果和真实回执的声明，不读取原始矩阵或观察服务器进程。', '',
        '新接口均仅用 Python 标准库，不创建分析环境、下载数据、调用公共数据库、连接服务器或运行算法。计算经用户已有 SSH/调度流程明确派发。共享服务串行运行，本地科研禁令优先于安装 profile。原始 RNA 私有附加包保持独立，未纳入本目录或公开包。', '',
        '目录可用、契约检查完成、源文件哈希、QC 摘要一致、引擎真实完成和科学有效性分别报告。`summary_consistent=true` 只是提交摘要无阻断问题，`analysis_authorized=false` 与 `scientific_validity_established=false` 始终保留。', '',
        '## 输入契约', '',
        '单次工具输入为有限 JSON，最多 400 KB；网关自身还有请求上限。仅选定元数据/返回摘要，不能传入大矩阵、完整质谱、全库或患者表。无隐式目录扫描或联网。', '',
        '| 对象 | 必需内容 |', '|---|---|',
        '| `context` | `species`, `model`, `assay`, `reference`, `reference_version`, `feature_namespace`。序列/基因组流程另需 `assembly`, `annotation_version`；每条流程的 `required_context_fields` 明示范围。质谱/微生物参考注明数据库。 |',
        '| `design` | `estimand`, `biological_unit`, `unit_type`, `contrast`, `missingness_plan`, `inference_mode`, `batch_confounded`, `repeated_measures`, `covariates`, `units`。 |',
        '| `unit_type` | donor / animal / independent_culture / biological_sample / pedigree / study。来源摘要还须独立核验，不能通过改名把细胞或技术重复变为生物学重复。 |',
        '| `units` | 至多 1000 条唯一 `id` 与 `group`。单位是独立单位清单，重复时间点/切片映射另用 `dependence_structure` 说明；不是每个观测一行。 |',
        '| `input_manifest` | 1–100 条唯一 `id`, 工作流支持的 `kind`, 小写 `sha256`, `source_location`。哈希是调用者声明；与真实文件独立核验。 |',
        '| `extensions` | 最多 12 个无重复兼容 ID；省略即不添加。每个前提在 `design.capabilities` 中提供 `available=true`, `source_location`, `source_sha256`。 |', '',
        '正式推断每声明组至少两个独立单位只是结构底线，不能当作统计功效或方法适用性验收。完全混杂阻断推断；需要预先说明重复测量结构、协变量和缺失处理。描述性模式不要求推断咨询，但仍要求 QC、方法和服务器来源；它不交付差异显著性结果，需提供 `descriptive_results`。需要推断拓展时重新建立 inferential 计划。', '',
        '## QC 与精确绑定', '',
        '计划含 `plan_sha256`、`catalog_sha256`、`context_sha256`、`design_sha256`、`inputs_sha256`。每条 QC、统计/后端摘要、输出记录和运行回执须携带完全一致的这些字段。目录、输入、设计或拓展改变必须重新生成和实质审核计划；改哈希不能代替审核。', '',
        '每个 `checks` 对象含唯一 `id`（必须来自 `required_qc`）、`status=passed/failed/unknown`、绑定、`source_location`、`source_sha256` 和 `reviewed_by_host=true`。缺失、unknown、failed 或 unreviewed 均阻断；没有用 not-applicable 绕过必需项的入口。不同起始数据层应定位上游 QC 回执，无法恢复的原始 QC 保留缺口，不能凭空补成 passed。', '',
        '有数值的 QC 可附 `measurements`，每项含唯一 `id`, `definition`, `unit`, `observation_scope`, `threshold_basis`, 数值 `value`, `operator=ge/le/between` 和 `bound`。between 用两个有序数值；拒绝布尔值、数字字符串和非有限数。显式比较会捕获“状态 passed 但数值未达声明阈值”。FRiP、TSS、线粒体比例、覆盖、CV、FDR 和位点定位都不统一套固定阈值；按协议、定义、单位及问题预先说明判据。', '',
        'inferential 计划的 `statistical_receipt` 包含绑定、定位/哈希、`reviewed_by_host=true`, `status=reviewed` 及相同 `estimand`/`biological_unit`。这是从实际 `statistics.guide_study_statistics` 及宿主审核形成的私有摘要，不自动伪造咨询。后端摘要含同样绑定/来源、`status=runtime_verified`, `route=existing_server`, 非空 `method_versions`；latest/dev/main 等浮动标记不算固定版本。还须独立检查原始服务器测试与方法适用性。', '',
        '## 结果契约', '',
        '输出 manifest 至多 200 条，含唯一 `id`, 唯一 `role`, 非空文件的正整数 `bytes`, `sha256`, `source_location` 和全部绑定。同一角色需要分片时先由服务器生成分片索引摘要，用索引承担该角色，保留原始文件清单。角色存在不表示表内内容或图形已经正确。', '',
        '运行回执需要相同绑定/来源/宿主审核、`state=COMPLETED`、整数 `exit_code=0` 和非空 `scheduler_receipt_id`/`runner_receipt_id`。它是对实际回执的声明；本工具不连接调度器，不自动重试 unknown，也不自称已哈希本地文件。接着用现有 `workflow.verify_remote_results` 在明确范围核验文件，再做独立科学解释。', '',
        '## 通用 QC', '',
    ]
    out += ['- `' + c['id'] + '`：' + c['description'] for c in data['common_qc']]
    out += ['', '## 流程概览', '', '| ID | 方向 | 输入类型 | 可选拓展 |', '|---|---|---|---|']
    for w in workflows:
        out.append(f"| `{w['id']}` | {w['title']} | {', '.join(w['input_kinds'])} | {', '.join(w['extensions'])} |")
    out += ['', '## 标准流程、方法 QC 与结果', '']
    for w in workflows:
        out += ['### ' + w['title'] + ' (`' + w['id'] + '`)', '', '**输入**：' + w['input_description'], '', '**方法 QC**：', '']
        out += ['- `' + q['id'] + '`：' + q['description'] for q in w['qc_gates']]
        out += ['', '**标准步骤**：', '']
        out += [str(i + 1) + '. ' + s for i, s in enumerate(w['standard_analysis'])]
        out += ['', '**服务器方法候选**：' + '；'.join(w['method_candidates']) + '。需选择、固定版本并核验已有环境；不是新执行器。', '',
                '**必需结果**：' + '、'.join('`' + r + '`' for r in list(dict.fromkeys(data['common_result_roles'] + w['result_roles']))) + '。', '',
                '**解释边界**：' + '；'.join(w['interpretation_limits']) + '。', '',
                '**官方参考**：' + '、'.join('[' + r + '](' + data['references'][r]['url'] + ')' for r in w['reference_ids']) + '。', '']
    out += ['## 条件拓展', '']
    for key, e in extensions.items():
        out += ['### ' + e['label'] + ' (`' + key + '`)', '',
                '- 前提：' + '、'.join('`' + v + '`' for v in e['prerequisites']),
                '- 服务器候选：' + '；'.join(e['method_candidates']),
                '- 新增结果角色：' + '、'.join('`' + v + '`' for v in e['result_roles']),
                '- 解释边界：' + e['interpretation_limit'], '']
    out += ['## 版本和归属', '',
            '官方参考核对日期为 2026-10-10，观察到的文档版本不能替代执行版本。固定实际 pipeline 版本、方法参数、参考数据库及软件/容器版本，并复用已有服务器环境。quantms 旧 nf-core 页面已标注归档，仅作历史方法参考；现有质谱软件需单独验收，不自动安装旧入口。', '',
            '本目录没有复制第三方 pipeline、脚本、权重或数据库，也没有把第三方算法当作本项目原创。公开合成契约测试验证拒绝/一致性语义，不表示所有组学后端已真实运行或得出有效科学结论。', '']
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    path = ROOT / 'OMICS_WORKFLOWS.md'; expected = generate()
    if args.check:
        if not path.exists() or path.read_text(encoding='utf8') != expected:
            raise SystemExit('Omics guide is stale; regenerate from its catalog')
        print('OMICS_GUIDE_CURRENT')
    else:
        path.write_text(expected, encoding='utf8', newline='\n'); print('OMICS_GUIDE_UPDATED')


if __name__ == '__main__':
    main()
