> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 增量任务规划与排名快照

这些工具需要 Python 3.10 及以上，仅使用标准库。它们不运行对接、MD、自由能或调度器，也不判定科学有效性。

## 路径与配置

从模板包根目录运行示例命令。先创建自己的 project 目录，把 workflow.example.json 复制为 project/workflow.json，填写实际路径、参数、程序身份和代码路径。项目内部数据路径相对于 `--root project`，不能使用绝对路径、`..` 或逃出项目根目录的符号链接；输出路径只能由一个任务拥有。

外部输入写为 `{"path":"inputs/source.sdf"}`；已由上游产生的输入写为 `{"task":"prepare_L001","output":"sdf"}`。`depends_on` 用于额外前置任务。任务不能在执行时修改原始输入。每个 task 必须声明 id、kind、entity_id、inputs、outputs、parameters、software、code、depends_on，未知顶层字段会被拒绝，以避免科学参数被静默忽略。

参数中应包含种子、单位、化学与模型状态、选择、算法设置、权重版本以及任何会改变结果的运行设置。软件身份由使用者提供；日志应保存实际版本或环境摘要。脚本检查文件内容，不证明声明的软件确实是执行的软件。

## 计划与审查绑定

```bash
python3 incremental/plan_incremental.py plan project/workflow.json \
  --root project --output project/plan_r01.json
```

`reuse` 表示输入指纹、已记录输出和审查证据匹配；`run` 表示当前任务需执行或重新验收；`waiting` 表示先完成上游；`blocked` 表示缺文件、未填配置或上游受阻。脚本遇到 blocked 或无效配置返回 2，正常计划返回 0。没有任何状态触发自动计算。

实际任务完成后，复制 review.example.json 为项目中的 reviews/prepare_L001_draft.json，填写执行记录和证据路径。先绑定当前输出与证据的字节快照：

```bash
python3 incremental/plan_incremental.py bind-review project/workflow.json \
  --root project --task prepare_L001 \
  --review reviews/prepare_L001_draft.json \
  --output project/reviews/prepare_L001.json
```

绑定会填写 reviewed_outputs、reviewed_evidence 和当前任务指纹，并将 status、每条 check.status 重置为 pending，reviewer/reviewed_at 重置为空。**绑定不是验收。** 在核对真实结果后，由研究者在绑定的 JSON 中填写检查结论、审查人、带时区时间和 accepted。保留执行开始、结束、审查的正确时间顺序；不改写快照中的哈希。

```bash
python3 incremental/plan_incremental.py record project/workflow.json \
  --root project --task prepare_L001 --review reviews/prepare_L001.json \
  --output project/state_r01.json
```

下一次 record/plan/bind-review 使用最近的 `--state project/state_r01.json`。新的状态写入 state_r02.json，保持历史不可变。`--targets dock_L001` 只规划该任务及必需上游。由一个协调者串行写入状态；该工具不提供分布式锁、数据库事务或多进程状态合并。

record 对全部输出、执行日志和证据重新计算哈希。旧审查不能用于验收后来改动的文件。科学判断仍由研究者完成；被漏报的依赖、伪造的审查或错误的物理模型不可能由文件哈希识别。

所有写出文件均采用独占创建，已有文件不会被覆盖。读文件过程中若大小、mtime 或 inode 改变，工具拒绝记录；应在冻结的文件快照上规划，不在仍被引擎写入的轨迹上计算哈希。大型轨迹哈希消耗 I/O，本工具未实现海量数据索引缓存。

## 排名比较

复制 ranking_snapshot.example.json，填入两轮实际的母体级结果。一个 parent_id 只出现一次；位姿和受体分数先按已冻结规则聚合。`direction` 为 lower 或 higher，`unit` 对无量纲评分写 unitless。failed/not_evaluated 的值必须为 null，不能写 0 或差分数。

```bash
python3 incremental/compare_rankings.py project/ranking_r01.json \
  project/ranking_r02.json --top-n 20 \
  --output project/rank_change_r02.json
```

comparison_key、score_name、unit、direction 必须一致。score_model 不同默认拒绝；`--allow-model-change` 只允许排名比较，此时不输出分数差。共同成员 Spearman 使用共同集合内重新计算的平均并列秩。少于 3 个共同成员或秩为常数时报告不可计算。Top N 纳入边界全部完全相同的并列分数，实际数目可能超过 N。

同时查看共同成员覆盖率、新增/消失母体和 Top 集合变化。脚本不推断显著性、活性或亲和力。

## 绘图

```bash
python3 visualization/plot_incremental.py reuse project/plan_r01.json \
  --output-prefix project/fig_reuse_r01
python3 visualization/plot_incremental.py rank-change project/rank_change_r02.json \
  --output-prefix project/fig_rank_r02
```

绘图另需 Matplotlib；输出 SVG 与 PNG。中文文字可用 `--font-file /path/to/chinese-font.otf`。复用图最多显示 80 个任务，超过时选择具体 targets 分面。排名图显示共同候选在各自完整库中的秩，图上相关系数则基于共同集合重新排名，两者含义有意区分。
