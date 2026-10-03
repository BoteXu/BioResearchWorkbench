# BioResearchWorkbench 改名与兼容

从发行包 2.8.2 起，产品名称为 **BioResearchWorkbench（生物医学科研工作台）**，原名称为 Biomni Direct Tools。最初的底层基于 Biomni，来源与归属详见 [ORIGINS.md](ORIGINS.md)。

## 现有用户

现有 `biomni`、`biomni-local` MCP 注册、`biomni_*` 函数和 `biomni-*` skill 名称继续可用。它们是兼容接口名称，不代表所有功能均来自 Biomni。当前桥运行版本保持 2.8，skill 包保持 2.8.1；2.8.2 是工作台的品牌与来源说明发行更新。

无需为了改名移动私人安装目录、索引、文献、软件注册表或服务器配置。改名不会自动删除或改写现有客户端设置。已有安装继续按原注册调用；公开仓库新名称不需要写进私人数据文件。

## 新安装

默认 MCP 注册名称为 `bioresearch`，本地分析版为 `bioresearch-local`；工具函数名与 skill 名保留兼容形式。可通过 `--mcp-name biomni` / `--mcp-name biomni-local` 选择旧名称，也可使用已支持的自定义名称。默认安装文件夹为 `BioResearchWorkbench` / `BioResearchWorkbenchLocal`，选择新目录以免覆盖已有安装。

新发行包为 `bioresearch-workbench-v2.8.2-server.zip` 和 `bioresearch-workbench-v2.8.2-local.zip`。旧发行包仍保留原名称和内容，不追溯修改历史版本。生成的私人客户端配置与注册名保持一致；不要重复注册同一实例，也不要把含私人路径的生成配置发布。

GitHub 仓库改名后，旧仓库地址的跳转行为需发布时验证。新文档和下载链接使用新地址；底层 Biomni 的官方地址保持不变。
