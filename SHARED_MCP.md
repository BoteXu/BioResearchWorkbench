# 多会话共享后台

## 使用与启动

v2.13.1 的服务器配置默认使用带认证的 Streamable HTTP MCP。多个聊天连接同一个后台；客户端配置没有启动 Python 的 `command` 或 `args`。安装器生成配置，后台由使用者启动，不自动修改系统登录项。

共享配置提供检索、服务器准备、回执状态、统计设计咨询、证据记录和有界检查。科研分析、数值计算、全库索引、原生应用初始化和本地工作进程提交不开放。大计算使用既有服务器路线。

新安装使用 `install.py --transport shared`，通过 `--shared-port` 选择未占用的本机端口。服务器配置的 Codex、VS Code 和 portable 默认选择 shared；本地版和 Desktop 配置保留 stdio。本项目不生成未经验证的共享 Desktop JSON。共享连接失败不会自动回退到 stdio。

在自己的安装目录执行。Windows：

```powershell
& .\.venv_tools\Scripts\python.exe .\.local\shared_mcp.py start
& .\.venv_tools\Scripts\python.exe .\.local\shared_mcp.py status
```

macOS / Linux：

```sh
.venv_tools/bin/python .local/shared_mcp.py start
.venv_tools/bin/python .local/shared_mcp.py status
```

重复启动复用认证健康的实例；启动锁和服务锁防止同时初始化多个后台。持锁实例没有健康响应时不会另开第二套或杀掉原进程。端口被占用、源码变化或可用内存低于 3 GiB 时拒绝新启动。内存检查是最低拒绝线，不是峰值保证；主机已有更严格的准入规则时先执行该规则。Windows 虚拟环境可能带有一个小启动器，它和实际 Python 子进程属于同一个逻辑实例。

登录后启动是使用者的明确选择：手动验证后，可把同一条 `start` 命令加入自己的 Windows 登录项、macOS 用户 LaunchAgent 或 Linux 用户服务。安装器不写这些配置，不修改防火墙或开启其他 MCP。`serve` 可以在自己的终端前台运行。停止后台前先核对认证状态、PID/创建时间和队列，不能按名称批量终止进程；操作状态未知时先核查真实回执，不自动重试。

## 既有安装的迁移

1. 按 [EVOLUTION.md](EVOLUTION.md) 审核源码升级，保留私有配置与定制 skill。
2. 用已安装 Python 执行 `.local/shared_mcp.py init`，可通过 `--port` 指定端口。本机生成认证，不需要另一个模型密钥。
3. 在下载包目录执行 `python client_config.py --install-dir <私有安装目录> --output-dir <新的私有配置目录> --server-name <现有注册名> --transport shared`。曾明确信任 DNS 代理时，初始化和配置生成同时加 `--trust-dns-proxy`。
4. 私下备份客户端配置，用生成的 HTTP 表替换原 stdio 表，移除旧 `command`、`args` 和 stdio `env` 子表。同一客户端不能同时启用两套指向同一安装的注册。
5. 启动服务，让空闲会话重新连接。分别调用 `biomni_shared_runtime`，核对各客户端的 PID 和实例标识一致。

安装器仅自动添加新的 Codex 注册名，拒绝覆盖现有名称，核对其他设置并保留字节备份。正在工作的聊天可能缓存旧配置；修改配置不证明所有聊天已切换，不要为此重启正在工作的客户端或批量清理进程。

桥接源码升级后，旧共享接受记录失效。先审查源码、停止自己确认的空闲后台，再执行 `init --review-current-source`，保留认证信息并重新启动验收。没有自动轮换凭据或自动重启。

## 队列、认证和隐私

- 所有调用共用一个队列，同时只执行一个工具。最多等待 8 项，等待 30 秒尚未开始则明确失败；这不是运行超时。
- 客户端取消等待后，真正运行的线程继续持锁，直到结束才允许下一项执行。
- 协议使用 stateless HTTP。研究隔离依赖显式项目、输入、输出目录、版本和审核哈希；认证持有人具有主机工具权限，它不是多租户沙箱。
- 只监听本机回环地址，检查 Bearer、Host 和 Origin，拒绝超过 512 KiB 的请求。不提供局域网、公网或手机直接连接模式。
- `shared_mcp_private` 中的设置、锁和状态保持私有。POSIX 目录/文件仅所有者可读写；Windows 初始化限制目录为当前用户和 SYSTEM。共享层不记录请求参数、载荷或访问日志，错误只记录类型。
- 客户端认证头同样属于私有配置，不能复制到截图、公开仓库或 issue。认证、生成配置、个人路径、运行日志和回执均排除在发行包之外。

鸿蒙浏览器仍使用独立的 [浏览器访问路线](PLATFORMS.md)，该 JSON 网关与共享 MCP 是两个接口。

## 验收

`tests/test_shared_mcp.py` 检查锁、凭据保护、源码变化、配置保留、队列超时、取消后的执行串行和禁止的操作。`tests/shared_process_check.py` 同时启动三个入口，用两个独立 MCP 客户端验证一个后台、断开隔离、并发计数、认证与请求限制。只调用元数据，不执行科研分析或公共查询。

默认启动准入线保持 3 GiB，单元测试单独验证不足时不创建进程。托管 CI 的元数据连接 fixture 明确配置 2 GiB 准入线，报告同时列出 fixture 和生产默认值；它不代表宿主在默认 3 GiB 条件下已经获准启动。该配置只在所选临时测试安装内生效。其他使用者可在初始化时明确传入 `--minimum-available-gib` 审核自己的主机预算，允许范围为 2–1024 GiB；既有配置不自动改写。主机自己的更严格政策优先，不能借此绕过。

CI 在 Windows、Linux、macOS ARM 和 Intel 的 core 环境执行连接验收。以该版本的真实通过结果为准；原生客户端 GUI、鸿蒙硬件和长期内存峰值需独立验证。共享减少重复初始化开销，不能据此证明内核/驱动泄漏已修复或系统不会再有内存压力。
