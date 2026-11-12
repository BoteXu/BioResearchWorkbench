# Amber 阶段命令与文件衔接

在生成的单个重复目录执行，每完成一个阶段先按正文验收。最小化示例使用 sander；动力学示例使用 pmemd.cuda，实际可执行文件应按本地版本和功能支持选择。以下命令不会自动检查科学有效性。

## 00_min_solvent

    sander -i 00_min_solvent.in -p system.prmtop -c system.rst7 -ref system.rst7 -o 00_min_solvent.out -r 00_min_solvent.rst7 -inf 00_min_solvent.info

## 01_min_all

    sander -i 01_min_all.in -p system.prmtop -c 00_min_solvent.rst7 -o 01_min_all.out -r 01_min_all.rst7 -inf 01_min_all.info

## 02_heat

    pmemd.cuda -i 02_heat.in -p system.prmtop -c 01_min_all.rst7 -ref 01_min_all.rst7 -o 02_heat.out -r 02_heat.rst7 -inf 02_heat.info -x 02_heat.nc

## 03_nvt

    pmemd.cuda -i 03_nvt.in -p system.prmtop -c 02_heat.rst7 -ref 01_min_all.rst7 -o 03_nvt.out -r 03_nvt.rst7 -inf 03_nvt.info -x 03_nvt.nc

## 04_npt_strong

    pmemd.cuda -i 04_npt_strong.in -p system.prmtop -c 03_nvt.rst7 -ref 01_min_all.rst7 -o 04_npt_strong.out -r 04_npt_strong.rst7 -inf 04_npt_strong.info -x 04_npt_strong.nc

## 05_npt_medium

    pmemd.cuda -i 05_npt_medium.in -p system.prmtop -c 04_npt_strong.rst7 -ref 01_min_all.rst7 -o 05_npt_medium.out -r 05_npt_medium.rst7 -inf 05_npt_medium.info -x 05_npt_medium.nc

## 06_npt_weak

    pmemd.cuda -i 06_npt_weak.in -p system.prmtop -c 05_npt_medium.rst7 -ref 01_min_all.rst7 -o 06_npt_weak.out -r 06_npt_weak.rst7 -inf 06_npt_weak.info -x 06_npt_weak.nc

## 07_npt_free

    pmemd.cuda -i 07_npt_free.in -p system.prmtop -c 06_npt_weak.rst7 -o 07_npt_free.out -r 07_npt_free.rst7 -inf 07_npt_free.info -x 07_npt_free.nc

## 08_pilot

    pmemd.cuda -i 08_pilot.in -p system.prmtop -c 07_npt_free.rst7 -o 08_pilot.out -r 08_pilot.rst7 -inf 08_pilot.info -x 08_pilot.nc

## 09_production_001

    pmemd.cuda -i 09_production_001.in -p system.prmtop -c 08_pilot.rst7 -o 09_production_001.out -r 09_production_001.rst7 -inf 09_production_001.info -x 09_production_001.nc

## 后续生产段

例：第二段从第一段的正常终止重启文件继续，保留不同的 ig：

    pmemd.cuda -i 09_production_002.in -p system.prmtop -c 09_production_001.rst7 -o 09_production_002.out -r 09_production_002.rst7 -inf 09_production_002.info -x 09_production_002.nc

每段 20 ns；五段累计 100 ns。这些段是同一个重复。中断时，应根据最新可读重启点重新计算剩余 nstlim，并使用新的未用过 ig；不要重新分配速度，不覆盖原段文件。生成器不会自动生成中断恢复输入。

检查总时间与重复帧，分析时以实际轨迹时间和生产阶段边界为准。不同重复在独立目录分别执行。


默认命令不启用 -O 覆盖选项。同名结果已存在时，应先核对已有任务和恢复点；确需重算则使用新的输出前缀并保留旧结果。
