# 可选研究 skill 包

这些流程属于 BioResearchWorkbench。项目最初底层基于 Biomni，第三方算法与工具归属见 [ORIGINS.md](ORIGINS.md)。现有 `biomni-*` 名称保留兼容；改名不意味着上游算法成为本项目原创，见 [MIGRATION.md](MIGRATION.md)。

Package 2.8.1 adds 14 original Apache-2.0-licensed workflow skills to bridge 2.8. They provide task instructions, tool routing and acceptance boundaries; they do not introduce another model, duplicate database clients, or install analysis/Office software. Existing installed specialist skills remain reusable. The static security reviewer is the only new skill-local executable helper.

## 包含的流程

| Skill | 用途 |
|---|---|
| `biomni-claim-audit` | 科学主张、原始研究与真实引用链 |
| `biomni-omics-design` | Bulk、单细胞和空间转录组设计、QC 与验收 |
| `biomni-scientific-figures` | 冻结结果表、可追溯科研图表与视觉验收 |
| `biomni-academic-delivery` | 论文、PDF、LaTeX 与汇报交付 |
| `biomni-remote-compute` | 已有服务器流程、真实调度状态与结果回收 |
| `biomni-structure-review` | 蛋白链、残基、结构来源与分子结果审查 |
| `biomni-workflow-maintenance` | 已验证流程提炼、版本和回归样例维护 |
| `biomni-skill-security` | 第三方 skill 有界静态扫描与人工审查 |
| `biomni-systematic-review` | 检索覆盖、筛选、偏倚和综合的流程审查 |
| `biomni-statistical-plan` | 估计目标、独立单位、统计计划与停止条件 |
| `biomni-target-evidence` | 遗传、组学、药理和结构证据整合 |
| `biomni-docking-review` | 对接输入 QC、对照与姿势验收 |
| `biomni-personal-library` | 指定 Zotero 范围与私有索引维护 |
| `biomni-submission-audit` | 投稿前结论、引用、图表和格式检查 |

## 安装

两个发行版均包含同一 skill 包，但客户端发现安装是可选的。先验证，再安装：

```text
python install_skills.py --validate-only
python install_skills.py --dry-run
python install_skills.py
```

默认位置是当前用户的 Codex skills 文件夹，遵循 `CODEX_HOME`。可用 `--destination <私有客户端的 skill 文件夹>` 指定其他位置，用重复的 `--skill biomni-...` 选择子集。现有相同文件跳过；任何有差异的同名 skill 拒绝覆盖。安装器只复制经过哈希检查的文件，不执行 skill 脚本，不改 MCP、模型或私人软件配置。中断留下的安装锁需先检查，不能自动删除重试。

全新工具安装时也可运行 `python install.py --install-skills`；Windows 包装器支持 `-InstallSkills`，自定义位置支持 `--skills-dir` / `-SkillsDir`。生成的工具安装目录始终保留 `skills` 和独立安装器，便于稍后选择客户端接入。

安装后打开新会话。Codex 中可以直接请求相应工作，或显式使用 `$biomni-claim-audit` 等名称。其他客户端只有在支持其 skill 发现机制时才会自动加载；也可按需将单个 `SKILL.md` 作为工作说明。技能说明可移植并不证明每个模型、客户端或鸿蒙设备的运行功能都已验证。

## 工具发现与边界

每个 skill 自带 `references/tool-routing.md`，先发现当前 Biomni 参数再调用，不硬编码私人目录。目录中的函数名已与实际扩展注册表交叉检查；运行依赖、真实数据、GUI 和服务器验证仍按任务进行。缓存 MCP 进程可能仍暴露旧版本，使用已有私有 bridge 或刷新客户端后检查。

PDF 全文/OCR/向量检索、后台同步、完整自动 RoB/GRADE、双评审界面、原生 Word 插件等并未因安装说明而新增。已有图表、文档、结构查看和 SSH skill 可复用；本包不重新分发它们的代码、字体或商业插件。核心版不增加科学计算依赖，大计算仍留在服务器。

## 隐私、许可证与验证

这是原创通用工作流，按仓库 Apache-2.0 许可证发布。随包只含流程、固定工具名和静态扫描器，无私人配置。外部工具和任何可选第三方 skill 的许可证独立核对；不继承本包许可证。

静态扫描器只对指定目录有界读取，报告候选问题和未审文件；无命中不证明安全。其报告、参数、文献内容、草稿、服务器信息和运行回执保留私有。接入 skill 不授权读全库、修改 Zotero、执行未知脚本、公开私人查询、提交计算或发出稿件。

工程验收覆盖文件哈希、skill 结构、工具路由、安装不覆盖、目录越界拒绝、扫描上限和实际安装发现。它不测量所有宿主模型的科研推理质量，也不替代任务本身的科学验收。
