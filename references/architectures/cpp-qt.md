# C++ + Qt 桌面全栈架构指南

适用于 **Qt5 / Qt6 桌面应用（Qt Widgets 或 Qt Quick）+ 本地业务/SQLite 存储 或 远端 HTTP/gRPC 后端**。

## 1. 端到端分层与边界

- **GUI / View 层**（Widgets / QML）：只负责控件创建、视觉呈现与发出语义动作信号（如 `saveRequested()`），禁止在按钮槽函数中直接写 SQL、阻塞文件 I/O 或同步网络调用。
- **Application / Controller 层**：装配窗口、后台任务、网络客户端与本地模型；负责跨层 DTO 转换与线程切换。
- **Service / Repository 层**：封装纯 C++ 业务规则、本地存储（[SQLite](../stacks/sqlite.md)）或网络客户端（[Qt 网络客户端](../stacks/qt-network-client.md)），尽量保持不依赖 `QWidget`/`QQmlEngine`，以便独立单测。

## 2. 桌面全栈高频踩坑

1. **GUI 线程冻结与跨线程回调悬空**：
   - 所有耗时 I/O 与计算必须在工作线程或异步事件循环执行；结果回传 GUI 线程前，必须绑定接收端 `QObject` 上下文并用 **请求代次（`requestGeneration`）/ 当前选中业务 ID** 过滤过期回调，防止“先点 A 再点 B，A 慢返回覆盖 B 的详情页”。
   - 窗口关闭时取消在途网络请求并按顺序等待或清理后台任务（详见 [Qt Widgets](../stacks/qt-widgets.md) / [Qt Quick](../stacks/qt-quick.md)）。
2. **网络/存储失败的用户可恢复反馈**：
   - 界面需明确区分「空状态 / 加载中 / 成功 / 可恢复错误」（见 [UI 布局与交互](../ui/layouts.md)），失败时保留用户输入与重试入口，不能静默吞错或把 DB 异常原文弹窗给用户。
3. **主题与 DPI 适配**：
   - 桌面主题（包括内置 `linear`/`cursor`/`notion` 与自定义 `DESIGN.md`）按窗口作用域映射，注意中文系统字体回退、高分屏缩放（100% / 150% / 200%）及无边框/缩放下的最小窗口可用性（见 [主题总览](../ui/themes/index.md)）。
4. **本地数据与版本迁移**：
   - 本地数据库与配置写入 OS 标准可写目录（`QStandardPaths::AppDataLocation`），绝不写进程序安装目录或当前工作目录（macOS Finder 启动 / Windows Program Files 只读）。

## 3. 桌面全栈验证门禁

1. **自动化测试**：纯逻辑用 GoogleTest，信号槽/异步状态与控件交互用 Qt Test（见 [测试指南](../stacks/testing.md)）。
2. **安装树干净环境启动**（关键）：先 `cmake --install` 生成 Release staging 目录并运行平台部署工具（`windeployqt` / `macdeployqt` / RPATH 检查），脱离构建树和开发机 PATH 启动验证，确认 Qt 平台插件、QML 模块、OpenSSL 及 SQLite 驱动全部齐全（参见对应 [Windows](../build/platforms/windows.md) / [Linux](../build/platforms/linux.md) / [macOS](../build/platforms/macos.md) 指南）。
3. **代表性交互实测**：验证正常操作、慢响应时快速切换条目/重复点击、断网错误反馈、窗口缩放/中文长文本与关闭重启后数据持久化。
