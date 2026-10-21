# 冻结结果的来源交接

复用 `research_quality.prepare_figure_handoff`，不安装新服务。明确 input_path、FigureSpec、context、qc、execution、sources 和可选新 output_dir。context 包含 independent_unit、contrast、method_version、reference_version、units、selected_scope、limitations；QC 绑定准确输入与规范 JSON 的上下文 SHA256。

消费端使用现有综合绘图 skill 的 `handoff-plan`，通过后再 render。变更输入、来源、QC 或源码均需新计划。`frozen_results_supplied` 不声明服务器运行；completed 声明还要绑定回执内容。哈希与内部一致性不认证调度器或科学正确性。

完整参数与算法：[FigureHandoff v1](https://github.com/BoteXu/BioResearchWorkbench/blob/v2.16.0/CONNECTED_FIGURES.md)。可重放的公开合成示例在综合绘图包 `assets/connected-examples/handoff/`；私人结果、配置、日志和计划只留在私有项目中。
