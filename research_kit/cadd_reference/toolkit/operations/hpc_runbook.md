# 批处理与续算运行记录

执行前冻结 task_manifest、资源配置、输入及代码版本。每个实际任务使用独立工作目录、日志、输出前缀、run_id 和 attempt_id。Slurm 数组索引只映射不可变清单，不在运行期间增删行。数组作业的启动顺序不是分子排序。

资源记录至少包括程序/版本、原子数或任务尺寸、GPU 型号与数量、显存、CPU 线程、内存、输出频率、实测速度和样本测试时长。按实测性能估算项目成本，分别记录排队与运行时间；不按显卡型号承诺产出速度。

失败后保留原日志，先归类输入错误、参数错误、资源故障或科学验收失败。节点中断可从一致 checkpoint 恢复；改变物理模型需建新模型分支。不要用自动重试掩盖持续约束错误或不合理结构。

GROMACS 续算核对 tpr/checkpoint/拓扑及所需原始输出，遵循所用版本的 append/noappend 规则；Amber 续算核对重启坐标、速度、盒、irest/ntx 和随机动力学设置。引擎 checkpoint 与分析轨迹不是同一种文件。

在 segment registry 保留 system_model_id、replicate_id、segment_id、parent_checkpoint_hash、起止时间、拓扑哈希和边界帧处理。续段不增加独立重复数量。检查分析时间轴重叠、缺口和原子顺序后再合并。

任务实际完成后，运行模块 QC 并准备字节绑定的审查快照，再写入增量状态。退出码 0、文件非空与科学验收是不同关卡。状态由单个协调进程更新，worker 不抢写同一 state 文件。

本包不自动提交集群任务，也没有测试用户集群的账户、分区、GPU 映射或调度器插件。按现有经验证的集群执行流程应用上述清单。

官方依据：
- https://slurm.schedmd.com/job_array.html
- https://manual.gromacs.org/current/user-guide/managing-simulations.html
- https://ambermd.org/Manuals.php
