# AI 技术栈规划指南

当用户未指定完整技术栈、要求选型建议或从零规划新工程时启用本流程。核心原则：**只提供经过验证的清晰取舍，经用户确认后再落盘脚手架；不替用户盲目锁定冷门或过度复杂的依赖。**

> 渐进披露提示：在**仅规划、尚未获用户确认**阶段，只需阅读本文件、[技术栈规范仓库](../stacks/catalog.md) 以及对应 1 份架构文档（如 `cpp-web.md`）；具体第三方库规范与平台部署指南推迟到用户确认技术栈、进入编码实现后再按需加载。常规中小型新工程的拟定骨架无需默认附带 `cpp-stack.json`。

## 1. 规划前先锚定 4 个维度

在给方案前，先从用户需求中核实（缺失且影响选型的简明追问）：
1. **全栈形态**：`C++ + Web`、`C++ + Qt`、`C++ + Python` 还是 `纯 C++ 服务/工具`？
2. **交付形态与目标平台**：桌面安装包 / 内网服务 / Web 应用 / Python Wheel？覆盖 Windows、Linux 还是 macOS？
3. **负载与数据规模**：单机嵌入式存储 vs 多用户并发读写？微秒级同进程计算 vs 可独立扩缩容服务？OLTP vs 列式 OLAP 分析？
4. **团队与存量约束**：是否受限于 Qt5、既有 MySQL/Redis 基础设施、指定编译器版本或必须离线构建？

## 2. 按全栈形态的默认选型矩阵

默认优先从 [技术栈规范仓库](../stacks/catalog.md) 选择高成熟度组合；若用户业务更适合未收录方案，如实推荐并在方案中标明。

### A. C++ + Web（后端服务 + 浏览器前端）

| 层级 | 默认推荐 | 备选方案 | 取舍依据 |
| --- | --- | --- | --- |
| C++ HTTP/API | **Drogon**（异步事件循环 + HTTP/WS + ORM） | **Crow / Oat++ / cpp-httplib**（轻量内嵌）或 **Boost.Beast / gRPC** | 常规高并发 REST/WS 首选 Drogon；极简内嵌伴随工具用 Crow/`cpp-httplib`；完全自定义协议栈用 Boost.Asio/Beast。 |
| 前后端契约 | **OpenAPI 3.1** + `openapi-typescript` | `gRPC` + Protobuf / 手写共享 DTO | 用 OpenAPI 作为唯一契约源自动生成 TS 客户端，避免手写类型漂移。 |
| Web 前端 | **React 或 Vue 3 + TypeScript + Vite + Tailwind** | **Next.js**（仅需 SSR/SEO 时） | 管理台、工具面板与内网系统优先 Vite SPA + TanStack Query，由 C++ 或 Nginx 托管。 |
| 存储与缓存 | **PostgreSQL (`libpqxx` / Drogon ORM)** 或 **SQLite** | **MySQL (`Boost.MySQL`)** · **Redis (`redis++`)** · **DuckDB** | 多并发 OLTP 选 PostgreSQL；单机轻运维选 SQLite；热点缓存/分布式锁配 Redis；大数据分析配 DuckDB。 |

### B. C++ + Qt / 桌面工具（桌面客户端 + 本地或远端后端）

| 层级 | 默认推荐 | 备选方案 | 取舍依据 |
| --- | --- | --- | --- |
| 桌面 UI | **Qt 6 Widgets**（生产力工作台/复杂表单/Dock） | **Qt 6 Quick (QML)**（强动效）· **Dear ImGui**（图形/调试工具）· **Qt5 qmake**（存量） | 通用桌面软件选 Qt Widgets/Quick；性能分析器、算法/渲染调试工具选 Dear ImGui。 |
| 客户端网络 | **`QNetworkAccessManager`** | **`libcurl` / `cpr`** · **Boost.Asio** · **MQTT/ZeroMQ** | 标准 HTTP 复用系统代理选 `QNetworkAccessManager`；UI 无关 SDK 用 `cpr`/`libcurl`；设备遥测与低延迟流用 MQTT/ZeroMQ。 |
| 本地存储与计算 | **SQLite**（事务存储） | **DuckDB**（本地大数据集分析）· **Eigen / OpenCV**（计算/视觉） | 常规桌面数据持久化用 SQLite；本地读取海量 Parquet/CSV 分析用 DuckDB；矩阵/图像内核用 Eigen/OpenCV。 |

### C. C++ + Python（高性能核心 + Python 生态）

| 层级 | 默认推荐 | 备选方案 | 取舍依据 |
| --- | --- | --- | --- |
| 集成边界 | **同进程绑定（`nanobind` / `pybind11`）** | **跨进程通信（`gRPC` / HTTP / ZeroMQ）** | 追求零拷贝数组（NumPy/Arrow）、纳秒调用且运行时可控选同进程；需隔离崩溃或独立 GPU/ML 环境选跨进程。 |
| Python 构建与服务 | **`scikit-build-core` + `uv`**（打包）；**FastAPI + Pydantic v2 + `uvicorn`**（服务） | `httpx` + `pytest` | 新型扩展优先 `nanobind` + `scikit-build-core`；API 编排层用 FastAPI 并通过 `asyncio.to_thread` 对接释放 GIL 的 C++ 扩展。 |
| 列式数据与测试 | **GoogleTest / Catch2**（C++）+ **pytest**（Python） | **Arrow / DuckDB**（大数据零拷贝交换） | 两侧分别验证算法与 GIL/异常/内存边界；列式大数据优先 Arrow C Data Interface。 |

### D. 通用构建、序列化与基础设施

- **构建体系**：`CMake (>= 3.23) + CMakePresets.json + Ninja + vcpkg (manifest)` + `CTest`（非 vcpkg 体系按 [qmake 与其他构建系统](../build/legacy-and-alt-builds.md) 适配）。
- **基础库组合**：日志 `spdlog`（配合 `fmt` 外部对齐 `SPDLOG_FMT_EXTERNAL`）、命令行 `CLI11`、配置 `yaml-cpp` / `toml++` / `nlohmann/json`（高吞吐只读解析可选 `simdjson` / `Glaze`）、密码学 `OpenSSL 3`、测试 `GoogleTest` / `Catch2` + `Google Benchmark`。

## 3. 输出规划方案的固定结构

向用户交付选型规划时，输出简明决策表而非泛泛介绍：
1. **推荐技术栈清单**（按组件/层列出：语言标准、框架、通信契约、存储/缓存/消息、构建与测试工具）。
2. **备选方案与关键取舍**（说明为什么这样选，以及什么条件下该切换备选方案）。
3. **风险与边界提醒**（如跨端部署、ABI、OpenSSL 版本、GIL 阻塞或首版刻意不引入的复杂度）。
4. **等待确认**：请用户确认或微调后再生成模板文件与目录骨架。
