> Public source edition. Local data, credentials, generated configuration and execution receipts remain private by default. Historical private-review wording below describes the prior review scope. Native server/scientific acceptance is still unverified.

# 对接执行模板

本目录用于一个已经完成结构与化学状态准备的刚性受体、一个配体状态/起始构象，按多个固定种子执行 Vina 对接。它不负责决定 pH、修补蛋白、选择口袋、枚举化学状态、做验证或判定结合活性。正文规定的科学检查应在运行前完成。

## 文件

- run_vina.py：配置校验、命令预览、可选执行、逐阶段日志和校验值记录。
- task.example.json：配置样例。所有 __FILL_*__ 都要替换，box 的 null 要换成三个数值的列表。
- manual_commands.sh.txt：用于理解流程的逐条命令；它不是可直接提交的批处理脚本。

## 输入与范围

受体为已有正确化学状态、完整关键原子和必要成分的带氢 PDB；配体为单一确定化学状态、单一起始构象、显式氢和三维坐标的 SDF。多个化合物/状态应拆为独立配置，保持 parent_id、state_id、conformer_id 对应。路径相对于 JSON 所在目录解析，也可以使用绝对路径。输出目录必须不存在，防止不同状态、种子或重跑覆盖已有数据。

这一路线不覆盖柔性受体、共价反应、特殊金属配位或专门 hydrated docking。需要这些模型时使用对应官方协议并另行验证；不要仅添加一个开关后假定本模板已经适用。

## 填配置

1. 将 task.example.json 复制成项目的 task.json。
2. 填写 ID、输入路径、site_definition、chemical_state_record 和独立 output_dir。
3. box.center_A 和 box.size_A 各填三个有限数，尺寸均为正值，单位为 Å。中心可以为负。参数没有默认的“通用口袋”。
4. 默认种子为三个不同非零整数；32、20、5 kcal/mol、4 核只是本 SOP 的搜索预算示例。应先用参考体系验证，再冻结配置。
5. 保存结构准备、box 可视化和对接验证记录。配置中有相应说明字段，但脚本不会读取你的生物学证据并自动判定其正确。

## 先预览再执行

~~~bash
python run_vina.py --config task.json
~~~

默认模式检查配置、输入文件存在性、单一 SDF 记录和 PDB 多模型标记并打印命令，不调用外部程序、不创建输出目录。它不解析配体化学结构，因此文件层检查通过不代表结构合格。

在已经配置好的 Meeko/Vina 环境中执行：

~~~bash
python run_vina.py --config task.json --execute
~~~

执行时先检查四个可执行文件及帮助中的必要参数，再依次完成受体准备、配体准备、每个种子的对接与 SDF 导出。采用参数数组调用程序，没有 shell 命令拼接。当前模板按种子顺序运行；批量并行请在外层按任务分配资源，不能让每个任务都自动占满节点。

## 输出解释

输出目录含 receptor.pdbqt、receptor.box.txt、receptor.box.pdb、ligand.pdbqt、各 seed 子目录的 poses.pdbqt/poses.sdf、完整日志、config.resolved.json 和 execution_manifest.json。

execution_manifest 的 execution_complete 只表示程序正常退出且规定文件非空；scientific_qc_status 保持 pending，后续仍需检查分子身份、手性、碰撞、位姿聚类、重对接/其他验证以及进入 MD 的选择理由。失败或中断保留日志，重新运行应使用新目录并说明版本关系。脚本不会把失败任务伪装成低分候选，也不会自动恢复部分完成的任务。

版本记录包括可执行文件位置、帮助文本、Vina 版本输出及运行脚本所用 Python 可见的包版本。若命令来自另一个环境，Python 可见包版本不保证等于该命令使用版本，应进一步核对环境清单。

## 必须知道的版本与化学细节

- 使用 --read_pdb 读 PDB；官方 -i/--read_with_prody 入口可能需要 ProDy。需要 mmCIF 时按安装版本选择合适入口。
- 不含忽略坏残基的选项。部分旧教程用 -a/--allow_bad_res，当前 develop CLI 文档出现 --delete_bad_res；这些开关可能删除体系的一部分，不应为了消除报错而照搬。
- mk_prepare_ligand.py 要求显式氢和 3D 坐标，它不是自动解决全部质子化与互变异构状态的软件。
- 用 mk_export.py 读取 Meeko 写入的 SMILES 与原子映射，恢复 SDF。不要经通用格式转换猜测键级后直接进入 MD。
- PDBQT 电荷、类型与简化氢表示用于对接。Amber/GROMACS 参数化需要回到已核对的化学状态和分子图。
- Vina 输出 rmsd l.b./u.b. 参照其最佳模式，不能直接当作与实验结构相比的重对接 RMSD。
- 不同 Vina/AutoDock/GNINA 评分的量纲、训练目标和方向应分别解释。

## 验证范围

交付时只进行了 Python 语法、CLI、占位符拒绝和预览模式检查；没有向任何真实蛋白/配体运行对接，也没有验证用户机器上的软件安装。实际首次运行应使用有可靠参考的体系完成本 SOP 的科学验证。

## 官方资料

- https://autodock-vina.readthedocs.io/en/latest/docking_basic.html
- https://autodock-vina.readthedocs.io/en/latest/faq.html
- https://meeko.readthedocs.io/en/develop/lig_prep_basic.html
- https://meeko.readthedocs.io/en/develop/rec_cli_options.html
- https://meeko.readthedocs.io/en/develop/export_usage.html

文档核对日期：2026-10-24。用于真实项目时保存实际安装版本的帮助与环境清单。
