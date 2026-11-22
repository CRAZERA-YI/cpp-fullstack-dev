# 验证、Sanitizer 与交付质量门禁

所有结论以真实工具输出为准，严禁在未运行或未核对产物时口头宣布“已通过”。

## 1. 编译器警告与静态分析基线

新工程建议对自有源码目标开启高警告（注意仅作用于自有 target，勿污染第三方头文件）：
- **MSVC**：`/W4 /permissive-`（第三方头用 `/external:W0` 或 `SYSTEM` 包含）
- **GCC / Clang**：`-Wall -Wextra -Wpedantic`
- **Clang-Tidy 与格式校验**：新工程可复用 [`.clang-tidy`](../../assets/templates/.clang-tidy) 与 [`.clang-format`](../../assets/templates/.clang-format) 模板；在 `CMakePresets.json` 开启 `CMAKE_EXPORT_COMPILE_COMMANDS=ON`，通过 `clang-tidy -p <build-dir> <changed-files>` 与 `clang-format --dry-run --Werror <changed-files>` 仅扫描本次修改文件，避免旧库噪音淹没新缺陷。注意：**Visual Studio 多配置生成器（`windows-vs2022`）会忽略 `CMAKE_EXPORT_COMPILE_COMMANDS=ON`**，Windows 下需使用 Ninja 预设生成 `compile_commands.json`（若 `compile_commands.json` 含 `cl.exe` 参数，执行 `clang-tidy` 时加 `--extra-arg=--driver-mode=cl` 或使用 `clang-cl` 预设）。
- **Release 安全编译加固与模糊测试**：对外暴露或处理非信任输入的服务，建议在 Release（`-O1` 及以上）启用加固选项（Linux GCC/Clang：`-fstack-protector-strong -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=2 -Wl,-z,relro,-z,now`，先 `-U` 避免在默认预定义该宏的发行版配合 `-Werror` 触发重定义报错；Windows MSVC：`/GS /guard:cf`）；自定义网络帧、二进制或文件格式解析器建议配合 Clang `libFuzzer`（`-fsanitize=fuzzer,address,undefined`）做模糊测试。

## 2. Sanitizer 动态检测（强烈建议在 CI 与并发/内存改动启用）

| 检测器 | 适用场景 | GCC / Clang CMake 选项 | MSVC 选项 / 限制 |
| --- | --- | --- | --- |
| **ASan + UBSan** | 越界、Use-After-Free、内存泄漏、未定义行为 | `-fsanitize=address,undefined -fno-omit-frame-pointer` | `/fsanitize=address`（需确保同进程所有 DLL 一致开启且附带对应 `clang_rt.asan*` DLL） |
| **TSan** | 线程竞态、跨线程信号槽/回调生命周期问题 | `-fsanitize=thread`（与 ASan 互斥） | Windows MSVC 不原生支持 TSan；改用 Linux/macOS Clang 跑并发单测 |

注意：Sanitizer 会改变二进制 ABI，必须使用独立的 Preset / Build Tree，切勿与常规构建混用缓存。在 Linux 下若主工程启用 Clang ASan 而链接默认 GCC 编译的 vcpkg 静态库，可能因 `std::vector` 注解差异触发 `container-overflow` 误报（需统一编译器/triplet 编译依赖，或在确认非真问题时临时配合 `ASAN_OPTIONS=detect_container_overflow=0` 排查）；**若启用 Clang TSan，同样切勿直接混链未做 TSan 插桩的第三方 C++ 静态/动态库（如默认 `x64-linux` vcpkg 产物）**，否则易因 `std::shared_ptr`/锁原语未插桩引发大量假竞态或崩溃，应优先在纯 C++ 核心或自定义 TSan triplet 上运行 TSan。

## 3. 按交付形态的验收要求

| 交付形态 | 必查验收项 |
| --- | --- |
| **局部改动** | 受影响组件编译 + 相关单测（GoogleTest / Qt Test / pytest）+ 受影响调用方验证。 |
| **C++ + Web 全栈** | 后端服务单测 + 前端 `typecheck`/`build` + 真实启动 C++ 后端与前端执行至少 1 条端到端 HTTP/WS 业务流 + 清理后台进程。 |
| **C++ + Qt 桌面端** | 测试通过 + 从 **`cmake --install` 产物目录（脱离 build tree 与开发机 PATH）** 启动 Release 可执行文件，核对界面状态、Qt 插件、缩放及中文/空格路径。 |
| **C++ + Python** | C++ 单测 + `pip install -e .`（若环境已预装全部构建依赖则可用 `--no-build-isolation`）或 Wheel 安装 + `pytest` 验证返回值、异常转换、GIL 并发与无内存崩溃。 |
| **二进制 SDK / 库** | 验证安装树头文件自包含、导出宏、Debug/Release 链接与最小外部调用方示例。 |

## 4. 证据记录与失败退出准则

- **必须记录**：执行目录、Preset/配置、完整命令、**真实退出码**（PowerShell 原生命令后读取 `$LASTEXITCODE`）、OS/架构/编译器/Qt/Python/Node 版本及产物或日志路径。
- **后台服务与超时**：集成测试必须使用独立临时端口和隔离数据库/目录，设置明确启动等待上限与超时，结束时清理拉起的后台进程。
- **失败止损原则**：同命令在相同环境无新假设的情况下连续失败 **2 次**（或缺少目标编译器/运行环境）时，停止盲目重试；明确记录失败症状、根因定位、阻塞项及恢复条件，或填入 [交接模板](../../assets/templates/task-handoff.md) 交付。
