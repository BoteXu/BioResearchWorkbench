# GROMACS 阶段命令与文件衔接

在生成的单个重复目录执行；每阶段检查 grompp notes/warnings、展开拓扑、实际参数、日志及结构后再推进。mdrun 的硬件分配先使用软件默认或已基准验证的配置，不强制所有特性上 GPU。

## 00_min_solvent

    gmx grompp -f 00_min_solvent.mdp -c system.gro -r system.gro -p topol.top -o 00_min_solvent.tpr -po 00_min_solvent.expanded.mdp -pp 00_min_solvent.processed.top
    gmx mdrun -deffnm 00_min_solvent -cpt 10

## 01_min_all

    gmx grompp -f 01_min_all.mdp -c 00_min_solvent.gro -p topol.top -o 01_min_all.tpr -po 01_min_all.expanded.mdp -pp 01_min_all.processed.top
    gmx mdrun -deffnm 01_min_all -cpt 10

## 02_heat

    gmx grompp -f 02_heat.mdp -c 01_min_all.gro -r 01_min_all.gro -p topol.top -o 02_heat.tpr -po 02_heat.expanded.mdp -pp 02_heat.processed.top
    gmx mdrun -deffnm 02_heat -cpt 10

## 03_nvt

    gmx grompp -f 03_nvt.mdp -c 02_heat.gro -t 02_heat.cpt -r 01_min_all.gro -p topol.top -o 03_nvt.tpr -po 03_nvt.expanded.mdp -pp 03_nvt.processed.top
    gmx mdrun -deffnm 03_nvt -cpt 10

## 04_npt_strong

    gmx grompp -f 04_npt_strong.mdp -c 03_nvt.gro -t 03_nvt.cpt -r 01_min_all.gro -p topol.top -o 04_npt_strong.tpr -po 04_npt_strong.expanded.mdp -pp 04_npt_strong.processed.top
    gmx mdrun -deffnm 04_npt_strong -cpt 10

## 05_npt_medium

    gmx grompp -f 05_npt_medium.mdp -c 04_npt_strong.gro -t 04_npt_strong.cpt -r 01_min_all.gro -p topol.top -o 05_npt_medium.tpr -po 05_npt_medium.expanded.mdp -pp 05_npt_medium.processed.top
    gmx mdrun -deffnm 05_npt_medium -cpt 10

## 06_npt_weak

    gmx grompp -f 06_npt_weak.mdp -c 05_npt_medium.gro -t 05_npt_medium.cpt -r 01_min_all.gro -p topol.top -o 06_npt_weak.tpr -po 06_npt_weak.expanded.mdp -pp 06_npt_weak.processed.top
    gmx mdrun -deffnm 06_npt_weak -cpt 10

## 07_npt_free

    gmx grompp -f 07_npt_free.mdp -c 06_npt_weak.gro -t 06_npt_weak.cpt -p topol.top -o 07_npt_free.tpr -po 07_npt_free.expanded.mdp -pp 07_npt_free.processed.top
    gmx mdrun -deffnm 07_npt_free -cpt 10

## 08_pilot

    gmx grompp -f 08_pilot.mdp -c 07_npt_free.gro -t 07_npt_free.cpt -p topol.top -o 08_pilot.tpr -po 08_pilot.expanded.mdp -pp 08_pilot.processed.top
    gmx mdrun -deffnm 08_pilot -cpt 10

## 09_production

    gmx grompp -f 09_production.mdp -c 08_pilot.gro -t 08_pilot.cpt -p topol.top -o 09_production.tpr -po 09_production.expanded.mdp -pp 09_production.processed.top
    gmx mdrun -deffnm 09_production -cpt 10

## 同一生产段中断后继续

在原输出完整、未被改写的目录，使用原 tpr 和 checkpoint：

    gmx mdrun -deffnm 09_production -cpi 09_production.cpt -cpt 10

## 首个 20 ns 正常完成后延长至 40 ns

    gmx convert-tpr -s 09_production.tpr -extend 20000 -o 09_production_40ns.tpr
    gmx mdrun -s 09_production_40ns.tpr -deffnm 09_production -cpi 09_production.cpt -cpt 10

extend 的单位为 ps；20000 ps = 20 ns。随后以已延长的 tpr 再延长，直到计划长度。若只想一次设定到 100 ns，可以从原 20 ns tpr 增加 80000 ps，再接原 checkpoint。保留各 tpr 的来源和最终目标长度。

追加写入需要 checkpoint 中的输出校验与现有文件相符。若有意使用 -noappend，新的 part 文件名须加入轨迹清单，并检查时间重叠；不能把 part 当独立重复。不要修改原输出后强行追加。常规精确续跑不需要重新 grompp，也不重新 gen-vel。

