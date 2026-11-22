# 日志、凭据安全与崩溃诊断规范

适用于所有 `C++ + Web`、`C++ + Qt` 及 `C++ + Python` 全栈工程的线上可观测性与基础安全基线。

## 1. 结构化日志与全链路追踪

- **选型**：纯 C++ / 后端服务优先 `spdlog`（异步 logger 注意进程退出前显式 `spdlog::shutdown()` 刷盘）；Qt 组件可用 `QLoggingCategory` 按模块控制日志级别并支持重定向到同一日志文件。
- **禁止污染标准输出与敏感字段**：
  - 数据库密码、API Token、`Authorization` 头、Cookie、完整身份证/私钥及含密码的数据库连接串**严禁**写入日志或错误弹窗。
  - 若 C++ 核心作为 Python 绑定或子进程 CLI 输出 JSON 结果，诊断日志只能写向 `stderr` 或日志文件，不得破坏 `stdout` 结构化输出。
- **Request-ID 贯穿全栈**：前端（Web/Qt/Python）为每次操作生成或接收 `X-Request-Id`（UUID/随机串），通过 HTTP Header / gRPC Metadata 透传至 C++ 后端、工作队列日志和错误响应体（`Problem.requestId`），便于从用户报错一键关联后端堆栈。
- **日志轮转与路径**：桌面端日志写入用户可写标准日志目录（如 `QStandardPaths::AppLocalDataLocation` / macOS `~/Library/Logs/<App>`），配置大小轮转上限，防止撑爆用户磁盘。

## 2. 凭据与传输安全

- **桌面端秘密存储**：用户认证 Token、API Key 与数据库口令**禁止明文存入 `QSettings`、`.ini` 或 `.json`**；必须存入操作系统原生凭据库（Windows Credential Manager、`libsecret` on Linux、macOS Keychain），或由用户在内存/环境变量注入。
- **传输层默认安全校验**：HTTPS / gRPC TLS 生产环境必须校验主机名与证书链；仅在本地隔离测试环境且显式开关控制下允许自定义测试 CA，绝不把“关闭证书验证”写进默认分支。

## 3. 崩溃诊断与符号保留

每次正式 Release 构建必须保留调试符号（**不要把完整符号直接打进公开发布包，而是归档保存用于还原堆栈**）：
- **Windows (MSVC)**：在 Release 启用 `/Zi` + 链接 `/DEBUG /OPT:REF /OPT:ICF` 生成 `.pdb` 文件并归档；可选集成 Crashpad / Windows MiniDump（`MiniDumpWriteDump`）记录崩溃上下文。
- **Linux**：剥离（`objcopy --only-keep-debug` + `strip --strip-debug`）后保留独立 `.debug` 符号文件以便解析 core dump。
- **macOS**：生成并归档与发布构建一一对应的 `.dSYM` 包。
