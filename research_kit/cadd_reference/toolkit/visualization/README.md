> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 可视化实现模板

完整图目录见 ../analysis/figure_catalog.md。这里提供两类基础图的生成器，使用已经得到的真实记录，不计算分子指标、不运行筛选，也不生成虚构结果。依赖 Python 3.10+ 和 Matplotlib；采用 JSON 输入，输出 SVG 与 300 dpi PNG。

## 筛选阶段图

填写 funnel.example.json 后执行：

```bash
python3 visualization/plot_results.py funnel /path/to/counts.json \
  --out-prefix /path/to/figures/screening_counts
```

每阶段满足 input_count = retained_count + filtered_count + failed_count，下一阶段 input_count 等于前一阶段 retained_count。Filtered 表示按照规则筛去，Failed 表示未成功得到可评价结果。当前模板只处理串行阶段；有并行路线、合并、重新引入候选或化学状态扩增时分别绘图，保留对应关系。

同一张图必须使用同一种计数单位，例如 parent_compound；不能在前半段数化合物、后半段数 protomer 或 pose。示例文件中的 null 应替换为经过核对的记录；未填写时脚本拒绝出图。若绘制预算方案，应在 title 中明确写 planned budget 或预算，不能展示成实际筛选结果。图例放在数据区右侧，并由布局自动保留空间，避免遮挡各阶段计数；正式排版时仍应检查长标题和长阶段名。

## 独立重复时间序列

填写 timeseries.example.json 的 records，每条记录有 system_id、replicate_id、time 和 value。例如字段结构为：

```json
{"system_id": "system01", "replicate_id": "rep01", "time": "实际时间数值", "value": "实际观测值"}
```

上面只展示字段，字符串说明不能作为数值输入。实际 time/value 使用数字；缺失观测可用 null，绘图将保留断开。每条重复内时间必须严格递增；不同重复不能拼接成一条连续曲线。

```bash
python3 visualization/plot_results.py timeseries /path/to/observables.json \
  --out-prefix /path/to/figures/ligand_pose_rmsd
```

系统分面、重复分别画线，保持共同纵轴。脚本不合并全部帧计算 SEM，不自动去除平衡段，不平滑或删除事件。平均值、区间与比较统计由相应分析模块另行产生。

## 字体和输出

中文数据自动查找常见中文字体；找不到时通过 --font-file 指定本地字体文件，避免生成缺字图。输出目录需先创建；同名 SVG 或 PNG 已存在时拒绝覆盖。SVG 保留文字，导入排版软件后应检查字体替换；默认图幅适合阅读，正式输出按目标版面调整尺寸。

参考 API：

- https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.barh.html
- https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html


## 版本3增量图形

plot_incremental.py新增复用状态图和候选排名变化图，输入分别来自incremental/plan_incremental.py与compare_rankings.py。详细字段和命令见incremental/README.md。两类图输出SVG与PNG，保留输入报告与版本；它们不计算分子观测或生成科学标签。图形规范扩展目录在analysis/incremental_figure_catalog.md与同名JSON中。
