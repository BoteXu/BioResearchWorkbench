> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 综合科研绘图工作台：私有增量 1.0

本增量将本轮评审的 **9 个方向** 纳入现有 transcriptomics-figure-workbench。原有 136 个注册入口、42 个历史升级配方、三维和动画画法保留。新能力通过同一个工作台的 `increments` 子命令调用；不重复安装外部 skill、MCP 或科学计算环境。

适用范围：已完成分析的多组学、计算生物学和建模结果展示。冻结输入里的数值、对象标识、顺序、供体、坐标和单位保持不变。SVG 使用物理尺寸，保留可编辑文字和形状；大热图可仅栅格化单元格。示例是软件显示测试素材，不是新跑出的生物学分析。

## 九项纳入情况

|来源方向|实际实现与调用|验收范围|
|---|---|---|
|scientific-visualization|`audit` 检查 SVG 描述/外部资源、PDF 页面/字体、PNG/TIFF 的透明度/ICC/目标宽度有效 DPI；`document-export` 生成 PDF 和预览|真实文件元数据；不能代替美观或期刊验收|
|heatmaps-clustering|`heatmap`：冻结树、行列分组条、效应和 QC 边注释、缺失值、局部栅格化、均衡分页|不重算聚类、标准化或显著性|
|spatial-visualization|`spatial`：spot/cell/molecule/segmentation 类型、显式仿射、物理比例尺、多切片、选定本地 PNG 背景|不生成分割或配准；圆盘和多边形边界超出裁剪区即阻断|
|genome-tracks|`genome`：覆盖、peak、基因外显子/方向/可扩展 lanes、loop、Hi-C；`native-plan` 生成真实 Gviz R 或 pyGenomeTracks INI 和固定命令|原生后端未在服务器实测；保留组装版本、坐标定义和单位|
|oncoprint-mutation-matrices|`oncoprint`：同格多事件、未检测与已检测未见变异分离、分组、事件数和 altered/tested|右侧分母使用完整输入样本轴，跨页保持一致；事件数不能替代 TMB|
|Scanpy|`markers` 与 `server/anndata_snapshot.py`：明确 raw/X/layer、精确细胞/基因 ID、现成 embedding、供体和外部已提供的 mean/fraction 汇总|读取适配器有代码和门禁，服务器未实测；不做 QC 分析、归一、UMAP、聚类或 marker 重估|
|interactive-visualization|`interactive`：离线 HTML、键盘选中、跨面板对象对应、过滤、匹配 SVG 与 scope JSON 的导出|真实嵌入 JS 的 DOM 行为测试通过；浏览器的实际下载授权行为另行验证|
|color-palettes|`palette`：按正文/大字/图形/类别等角色检查合成背景与 alpha 对比、顺序亮度|颜色视觉障碍模拟/认证未做；示例故意包含低对比失败色|
|circos-plots|`circos`：多环、连接、正负发散色标、坐标端点、相同区间/色标的线性配套图|不把示意圆形外观当成环状基因组或因果证据|

## 调用

在已有工作台入口下：

```text
python workbench.py increments catalog
python workbench.py increments example heatmap --size medium --output heatmap.figure.json
python workbench.py increments plan --spec heatmap.figure.json --output preflight.json
python workbench.py increments render --spec heatmap.figure.json --output fresh_heatmap_output
python workbench.py increments audit --file figure.pdf --width-mm 178 --output metadata.json
```

独立包使用 `python cli.py ...`，省去前面的 `workbench.py increments`。输出目录必须为新目录。PDF 检查和转换使用已有文档渲染环境中的 PyMuPDF；栅格元数据使用已有 Pillow。不安装额外依赖。1000 像素 PNG 是检查预览，按 178 mm 投放时并不达到 300 DPI；投稿优先使用矢量 SVG/PDF，栅格最终尺寸另验。

现成的调用数据在 `examples/<kind>_<size>/source.figure.json`；每例有 SVG、PDF、PNG、输入和生成回执。`examples/index.html` 用于逐张浏览。可直接用同例 JSON 重新渲染到新目录。

## 自定义布局

FigureSpec 的 `layout` 支持 `width_mm`、`height_mm`、`columns`、`rows`、`panel_width_mm`、`cell_pt` 和 `page_panels`。未指定高度时随内容增长；指定高度太小、列宽太窄、面板数超过显式行列容量时拒绝。大矩阵按列均衡分段并重复行标识；marker 汇总按可读宽度均衡分组，不丢弃最后几个 marker。只有一个面板的末页居中显示。过多圆环须另分图，不能压缩到无法辨识。

示例：保留 `data`，仅将 `layout` 改为 `{"width_mm":260,"columns":2,"page_panels":2}`。画布、列数、行数或字号相关实现变化后，旧视觉评审不可直接沿用；检查本次实际导出的画面。标签/对象超过示例范围时也需重新看图，自动排版不保证任意长标签都好看。

## 输入和结果验收

- 必须带输入来源、SHA256、单位、独立单位、选择范围、已做变换及是否合成。JSON 最多 16 MB；这是有界结果检查，不是组学分析内存准入。
- 不自动补缺失均值、fraction、p 值、TMB、供体或基因映射，不重新估计置信区间。缺失/未测保留可见标识。
- marker 汇总默认与所选非缺失对象/供体计数严格对应。若汇总来自另一个上游总体，必须设置 `summary_scope={kind:upstream_population,source_id,source_sha256,selection}`，保留该总体的来源和选择范围。不能默默把总体汇总当作显示子集的汇总。
- 生成状态是 `RENDERED_UNREVIEWED`。本轮示例的实际逐页复核在 `qa/visual_review.private.json`，绑定 SVG/PDF/PNG 与源码哈希。它是自检，不是独立审稿或科学结果验收。
- 变更输入、大小、布局或源码后需要新输出及新评审。不要修改旧回执的通过状态来代表新图通过。
- 标准库单元测试检验身份/数值保留、分页和拒绝分支；不把“测试通过”表述成科学方法验证。

## 服务器适配

见 [服务器适配与接入](SERVER_ADAPTERS.md)。仅准备代码/文件，不自动 SSH、下载或提交。AnnData、Gviz 和 pyGenomeTracks 的真实运行均标为 `NOT_RUN_SERVER_UNAVAILABLE`。本轮未安装或运行这些科学后端。

## 隐私与来源

仅存私有库；不发布、push 或上传真实数据/图/路径/供体信息。共享 Biomni 进程和注册不变。新入口为短时绘图/文件检查，不启动额外常驻服务。来源与许可在 [SOURCES](SOURCES.md)，仅借鉴经选定文件审阅的思路；本包实现为原创，未打包外部 skill、脚本、字体或权重。保留 Biomni 初始基础与各原算法/数据库的归属。
