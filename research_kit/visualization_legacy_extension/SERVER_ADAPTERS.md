# 服务器适配：已实现代码，未做真实运行验收

三项均保留 `NOT_RUN_SERVER_UNAVAILABLE`。配置检查、静态阅读、合成文件准备并不证明真实科学后端可用。不在本机读取 H5AD、运行 R/Scanpy/pyGenomeTracks、安装环境或调度作业。

## AnnData 冻结结果

`server/anndata_snapshot.py PLAN OUTPUT` 在已有计算节点提取明确范围的 stored X/raw/layer 数值、已有 embedding、分组和供体。需要：

1. `schema=anndata-frozen-display/1`；`dispatch_authorized=true` 只能在已有服务器路线明确派发时设置。
2. 当前真实 `expected_host` 与 `node_role=compute`；还需 SSH/Slurm 上下文，拒绝 Windows/WSL/登录节点。
3. `input={path,sha256}`、确切 `expected_anndata_version`；输入必须位于选定项目。
4. 明确 `object_ids`、`marker_ids`、`embedding_key`、`group_key`、`donor_key`；不能自动选择全库。显示子集上限 50000 个对象，不代表浏览器性能承诺。
5. `representation={kind:raw|X|layer,layer:null|明确层名,unit:明确单位}`。raw 不能夹带 layer，X 也不能静默忽略 layer。
6. `summaries={path,sha256}` 指向上游已验收的完整 group×marker 汇总列表，每行有 mean、fraction、n_donors、n_objects。不在提取中重算这些结果。
7. `figure_template` 采用同包 marker 示例的 FigureSpec；明确真实 palette、groups、value_limits、provenance.synthetic。提取后来源哈希更新为真实 H5AD，receipt 保留精确子集标识。

输出冻结 JSON 和独立回执；重新核对标识、单位、输入前后哈希、后端版本、基因表示、供体完整性和上游分析 QC，再进入绘图。没有 embedding/结果汇总时回到上游分析，不在绘图入口补算。

## 基因组原生绘图

```text
python cli.py native-plan --spec genome.figure.json --backend Gviz --output fresh_gviz_bundle
python cli.py native-plan --spec genome.figure.json --backend pyGenomeTracks --assets approved_assets.json --output fresh_pygt_bundle
```

Gviz 路线支持 coverage/peaks/genes，实际生成 DataTrack、AnnotationTrack、GeneRegionTrack 和外显子文件。转换 0-based half-open 到 R 的 1-based closed 时 start+1、end 保持不变。loop/Hi-C 使用本包 SVG 或 pyGenomeTracks；不能假装 Gviz 支持这里未实现的轨道。

pyGenomeTracks 需要每条轨道一个明确 native asset：`track_id,path,sha256,file_type`。文件格式必须匹配语义：coverage→bigwig，peaks→bed，genes→gtf/bed，loops→links，hic→hic_matrix。仅允许项目内的已审核相对文件名；不从网络自动下载。生成 tracks.ini、固定参数列表和完整源清单。

准备后的 `native_plan.json` 默认为未授权。派发前填入真实 compute host、已有可执行文件 SHA256 和 exact expected_versions，再计算 `review_sha256`：对除 dispatch_authorized/review_sha256 外的完整 JSON，按 contracts.digest 的规范化方式计算。此后任何源文件或配置改变都应重新审查。

明确通过既有共享 SSH 派发：`python server/native_track_runner.py native_plan.json fresh_server_output`。它按固定 argv 启动已有后端、使用新目录、保留日志/失败文件、检查源前后哈希并写真实结果回执。未知提交不重试。成功退出只证明后端绘图完成；返回 PDF 后还需尺寸/字体检查及实际视觉复核。

## 跨流程关系

上游 QC/分析验收 → 冻结结果/源哈希 → 显式子集和表示层 → FigureSpec 预检 → 新目录绘制 → 输入不变/结果清单 → 文档元数据检查 → 实际画面评审。

绘图不改变差异表达、富集、聚类、空间注册、细胞注释或模型训练结论。检验结果、未验证后端和合成演示必须保留不同状态。
