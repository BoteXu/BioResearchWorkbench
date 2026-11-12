# 来源、固定版本及采用边界

本轮代码为原创显示/验收实现；下列 skill 仅作为已静态审阅的设计参考，未整体安装、执行或复制。上游项目独立保留归属。归档源不自动更新。

GPTomics/bioSkills 固定提交 `d91ed3d563019e649dc854c56ccd62551359488a`，仓库 MIT，已归档：

- [heatmaps-clustering](https://github.com/GPTomics/bioSkills/blob/d91ed3d563019e649dc854c56ccd62551359488a/data-visualization/heatmaps-clustering/SKILL.md)：冻结树与注释矩阵；未照搬聚类或标准化。
- [spatial-visualization](https://github.com/GPTomics/bioSkills/blob/d91ed3d563019e649dc854c56ccd62551359488a/spatial-transcriptomics/spatial-visualization/SKILL.md)：平台/几何语义与共享尺度；未接入配准拟合。
- [genome-tracks](https://github.com/GPTomics/bioSkills/blob/d91ed3d563019e649dc854c56ccd62551359488a/data-visualization/genome-tracks/SKILL.md)：原生轨道；新服务器适配代码另行验收。
- [oncoprint-mutation-matrices](https://github.com/GPTomics/bioSkills/blob/d91ed3d563019e649dc854c56ccd62551359488a/data-visualization/oncoprint-mutation-matrices/SKILL.md)：多事件与检测状态；不接受事件数就是 TMB。
- [interactive-visualization](https://github.com/GPTomics/bioSkills/blob/d91ed3d563019e649dc854c56ccd62551359488a/data-visualization/interactive-visualization/SKILL.md)：离线交互/静态配对；未采用固定点数必崩溃等说法。
- [color-palettes](https://github.com/GPTomics/bioSkills/blob/d91ed3d563019e649dc854c56ccd62551359488a/data-visualization/color-palettes/SKILL.md)：按角色而非通用阈值筛查；不声称色盲认证。
- [circos-plots](https://github.com/GPTomics/bioSkills/blob/d91ed3d563019e649dc854c56ccd62551359488a/data-visualization/circos-plots/SKILL.md)：多环与线性配套图；不引申基因组结构。

K-Dense-AI/scientific-agent-skills 固定提交 `a25cf9ec00e2745d03f8704acf6f6919694ccd9a`，仓库 MIT：

- [scientific-visualization](https://github.com/K-Dense-AI/scientific-agent-skills/blob/a25cf9ec00e2745d03f8704acf6f6919694ccd9a/skills/scientific-visualization/SKILL.md)：导出元数据、对象角色和可达性。另静态阅读 figure_export.py、image_metadata.py、palette_audit.py，未执行、复制或重新分发它们。
- [scanpy](https://github.com/K-Dense-AI/scientific-agent-skills/blob/a25cf9ec00e2745d03f8704acf6f6919694ccd9a/skills/scanpy/SKILL.md)：该 skill 自身声明 BSD-3-Clause，与仓库 MIT 分开记录。只借鉴显式 X/raw/layer、已有对象和 marker 展示的语义。

原始选定文件的 SHA256 在 source_ledger.json，供私有追溯。该静态审阅不覆盖完整仓库、传递依赖或服务器运行环境。未重新分发第三方代码，因此不把上游 MIT/BSD 误作为本原创私有增量的发布授权。
