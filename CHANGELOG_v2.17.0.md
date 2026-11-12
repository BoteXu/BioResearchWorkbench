# v2.17.0 — reviewed research sources and visualization

## v2.17.0：完整研究源码与综合绘图公开版

公开此前已审阅的研究增量源码：71项方法逐项审查、QC/实际分析调用/结果验收、虚拟扰动、相互作用轮廓与ShEPhERD-2、转录组/CADD参考工具，以及scientific-visualization v2.2。详见[可选研究源码包](research_kit/README.md)、[71项方法报告](research_kit/workflow_integration/71项方法逐项审查_v3.4.md)和[绘图skill](research_kit/scientific-visualization/SKILL.md)。原始可选bulk接口与全部旧工作流保留。

本次新增的13条原生/导入分支覆盖MAGPIE、DIA-NN Academia、SIRIUS、CSI结果导入、GNPS、DOCKovalent、PRnet、scDiffusion、Squidiff、CellNavi、Stack以及MorphDiff的g2i/i2i。源码调用与完整结果合同已经编写；**实际服务器引擎本轮未实测**，依赖/权重/许可仍是运行前提。CSI新在线预测与scDiffusion真实起始细胞插值不在这些已实现分支中，不声明覆盖全部上游功能。

公开源码保持“项目数据默认私有”。个人目录/标识/地址、凭据、原始Office/ZIP附件、原始附件指纹、机器配置、运行日志和回执均不分发。私有仓库、保存的skill、本机默认注册及共享服务不被此次发布修改。静态`.private`源文件名已提供公开别名；私有运行结果的命名和保护仍保留。

科研绘图保留140个唯一图标识、22模块、7复合配方、Python/R以及既有交互/三维/动画入口；SHAP默认保留内嵌小玫瑰。旧42个历史升级配方及旧绘图库仍在[绘图仓库](https://github.com/BoteXu/transcriptomics-figure-workbench)兼容入口中。已完成的16张冻结真实结果显示验收不等于本轮重跑全部140图或所有交互/三维输出；缺失的原生科学验收继续明确标注。

新安装会带上研究源码而不安装其科学计算依赖、不额外启动MCP；既有安装仍通过审核升级计划更新，自定义内容继续受保护。研究代码按明确QC和统计计划准备，经已有共享SSH/调度显式提交到计算节点。默认核心依赖保持轻量。


Source inspection, contract checks, exact exported displays, native server execution and scientific acceptance remain separate. The primary method/licensing/source boundaries are documented per component.
