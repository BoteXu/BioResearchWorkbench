> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# scientific-visualization — public source v2.2.0

## 公开源码 v2.2.0：方法结果衔接

新增71项方法与13条工具分支的精确结果角色/单位/回执衔接，见[方法结果使用说明](references/analysis-result-handoff.md)。保留140个图模板、22个模块、7个复合配方及既有R/交互/动画能力；新增消费者不重复计数为新图。SHAP内嵌小玫瑰仍为原默认，其他旧画法继续保留。

本轮只针对改变的结果消费、单位、条件注释和比例语义做工程与真实冻结结果检查；既往全库验收记录保留为历史，不宣称本轮重新运行了全部原生科学后端或全库所有交互输出。服务器仍未实测，MorphDiff真实结果尚不能进行目检。本次提供公开源码；本机安装和默认配置未切换。


A scientific figure workflow for bulk/multi-omics, single-cell, docking,
molecular dynamics, machine learning, quantum chemistry and QC. It consumes
supplied analysis results and preserves original Python/R capabilities.

The merge retains the main skill identity and all 140 original figure IDs,
22 figure-set modules and seven actual composite recipes. QC has its own
section within the main skill; the independent QC skill and original ZIPs
remain intact. Counts are unique catalog identities, not a claim of 140
independent scientific methods or fully validated analysis engines.

The shared design engine provides 16 palettes, fixed project identity colors,
Liberation Sans, exact 89/120/183 mm widths, PNG 300 dpi and editable SVG.
Data-aware layouts, clear guides and explicit pagination replace arbitrary
fixed grids and tiny text. Existing styles remain optional. Preserve older
excellent designs, including SHAP swarms/rose insets/share rings; newly written
code is not automatically a visual improvement.

Read [SKILL.md](SKILL.md), [current API](references/v2-api.md),
[selection policy](references/selection-policy.md) and
[SHAP preservation](references/shap-preservation.md) and
[native workflow results](references/workflow-results.md). The machine-readable
catalog and observed real-case input structures are in `assets`.

Demonstration data, executors, source receipts, browser captures, individual
reviews and the offline gallery are deliberately outside this production skill.
The separate validation report records actual rendering, mathematical checks,
visual inspection and interaction status. A rendered file or catalog entry is
not scientific acceptance. Channel-limited real examples are identified there.

This is a public source release. It does not freeze, install or
delete any saved skill, or authorize uploading private project data. Original tools, scientific algorithms, datasets,
Matplotlib/R libraries and the bundled viewer/fonts retain attribution and
licenses; no private configuration or source-data download belongs in this ZIP.

The v2.1 review fixes actual SHAP defaults and output-scale labels, removes
example-specific labels/validation claims from generic ML views, preserves
source hierarchies, and adds receipt/QC-bound consumers for native results.
The 49-route semantic map is distinct from runtime acceptance. The native
engines were not run or remotely probed in this update. Targeted figure reviews
do not replace a complete new visual review of every inherited template.
