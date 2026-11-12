# 私有结果到绘图衔接 v3.4 / scientific-visualization v2.2

`figure_routes71.json` 与绘图包 `assets/analysis71_routes.json` 对应同一71项方法身份、实际输出角色和解释边界。新13条原生分支也有独立数据语义。不是根据列名相似就把所有结果套入一个图。

准备绘图：在一个私有请求JSON内填写 `public_upload:false`、选定 `skill_root`、已有结果目录下的 `scientific_request/server_receipt/return_acceptance` 相对路径，以及 `selected_outputs:{role:[exact_path,...]}`；然后执行 `python workbench.py figure-plan --request FIGURE_REQUEST.json --root OWNED_RESULT_ROOT --out FRESH_FIGURE_PLAN.json`。只准备计划，不提交、不拟合、不安装。

绘图Python接口：

```python
from analysis_results import plan_result_figures, render_result
plan = plan_result_figures(request, receipt, result_root, acceptance,
                           selected_outputs, current_backend_source_sha256)
fig, meta = render_result(
    plan, role="ACTUAL_RESULT_ROLE", view="interval",
    channels={"id":"ACTUAL_ID", "estimate":"ACTUAL_EFFECT",
              "lo":"ACTUAL_LO", "hi":"ACTUAL_HI"},
    unit="ACTUAL_PRODUCER_EFFECT_UNIT",
    interval_label="ACTUAL_COVERAGE_AND_INTERVAL_DEFINITION",
    width="onehalf", outdir="NEW_FIGURE_OUTPUT")
```

可选视图为matrix、scatter、interval、rank、curve、edges、proportions、volcano，受各方法的实际通道约束。`image_channels`使用独立 `render_generated_channels`，保留真实五通道顺序和模型生成标识。没有真实返回图像时，不将该分支的目检记为通过。

- matrix：明确index与数值列；保持数值、缺失和顺序；可显示转置，但不重新聚类或归一。条件注释从同回执选定metadata角色按字面ID对齐，不猜后缀。`annotations={role,path,id,group}`。
- scatter/curve：必须分别给出实际X单位 `xunit` 和Y单位 `unit`。少量散点默认显示真实点身份；重复时间值不擅自连成总体轨迹。
- interval：必须提供完整估计/两端及真实区间定义；不从CI造分布，SEM和90%CrI不得写成95%CI。
- rank：保存源顺序，以清晰横条展示，不默认继续堆叠棒棒糖图；不得把排名分数写成概率。
- proportions：只读已存在的真实比例/概率，保留原值且要求行和1；不重新归一，不显示虚假的n=1。丰度可用matrix，不能冒充比例。
- volcano：必须是真正adjusted P、明确效应阈值/FDR及依据。效应轴采用实际单位，不将自然对数、交互系数写成log2FC。
- curves：连接同一已有series的严格递增横轴；不合并供者、不拟合平滑器、不重新定轨迹方向。

图内默认英文、受控栏宽89/120/183mm、共享风格和固定项目身份颜色。调用方应复用已审阅的project theme；行Z、原始ssGSEA分数、latent或模型生成表达各用自己的单位。本轮真实冻结数据只用于显示衔接检查，没有新分析拟合或服务器引擎运行。实际方法运行后仍需新结果的科学与目检验收。
