> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# BioResearchWorkbench 私有分析工作版本 v3.4

本轮完成了71项方法逐项源码复核，并为剩余12个具名工具补入13条明确的调用/导入分支，衔接实际QC、完整结果证明和绘图端。原71项注册表字节保留，当前契约覆盖旧“服务器不可用”标签，统一显示本轮未实测；没有探测当前服务器是否在线。

- 方法报告：[71项逐项审查](71项方法逐项审查_v3.4.md)；机器可读：[逐项JSON](method_review71.json)。
- 新工具的原算法、许可、实际参数、调用顺序及边界：[调用指南](非商业工具实际调用_v3.4.md)。
- 绘图衔接：[Figure integration](FIGURE_INTEGRATION_v3.4.md)；当前图形身份仍是scientific-visualization，140个模板/22模块/7复合配方没有增删重复计数。
- 历史稳定入口仍由已有私有索引管理，本版本只登记为工作草稿。现有Biomni共享服务、默认注册和独立QC旧skill不变。

本轮为11类方法/实现修正，包括残差相关自由度、配对甲基化单位数、时间曲线的干扰项、零覆盖未知状态、StrainPhlAn覆盖记录、缺失GO、CellRank端状态、LR复合物亚基、复合物离散度以及可识别的配对RNA/Ribo翻译效率交互。

工程检查、静态源码复核、实际服务器引擎运行和科学验收分别记录。服务器引擎执行数为0，`scientific_acceptance=NOT_ESTABLISHED`。新代码不是通用方法等价性或研究发现的证明。旧测试与旧回执保留为历史，不能认定当前环境已验证。

只更新私有库；没有公开仓库提交、外部上传、安装模型/依赖、自动重试未知任务或全局服务切换。大计算继续使用已有服务器及共享SSH流程。
