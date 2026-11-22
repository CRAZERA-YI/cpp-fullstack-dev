# 技术栈规范仓库（Stack Reference Catalog）

本目录是**按需读取的参考规范库**，目前已收录 **22 份专题规范**（覆盖 40+ 高频 C++ / Web / Python 工程库），支撑两种技术栈获取方式：
1. **用户自供技术栈**：直接从下表查找对应标识；若用户使用的库不在表中，严格执行下方「未收录栈兜底协议」，**绝不擅自替换为表内库**。
2. **AI 协助规划技术栈**：结合 [技术栈规划指南](../workflow/stack-planner.md) 从本仓库挑选默认组合并说明备选方案，经用户确认后实施。

## 1. 已收录技术栈清单

### 桌面 GUI 与图形工具
| 标识 | 覆盖库与能力 | 适用构建与环境 | 规范指南 |
| --- | --- | --- | --- |
| `qt-widgets` | Qt Widgets 桌面界面、信号槽、多线程与分层 | Qt5 / Qt6 · CMake / 已有 qmake | [Qt Widgets 规范](qt-widgets.md) |
| `qt-quick` | Qt Quick / QML 绑定、Model、模块部署 | Qt5 / Qt6 · CMake / 已有 qmake | [Qt Quick 规范](qt-quick.md) |
| `qt-network-client` | `QNetworkAccessManager`、TLS/OpenSSL、`libcurl` / `cpr` | Qt Network / CMake | [桌面网络客户端规范](qt-network-client.md) |
| `dear-imgui` | Dear ImGui + GLFW/SDL2 + OpenGL/DX11/Vulkan（含中文与 DPI） | CMake · 即时模式工具界面 | [Dear ImGui 规范](dear-imgui.md) |

### 网络通信、Web 后端与消息中间件
| 标识 | 覆盖库与能力 | 适用构建与环境 | 规范指南 |
| --- | --- | --- | --- |
| `drogon` | Drogon 异步 HTTP/WebSocket、协程、`drogon::orm` | CMake · 高并发 Web 服务 | [Drogon 规范](drogon.md) |
| `cpp-http-lightweight` | `cpp-httplib` / `Crow` / `Oat++` | CMake · 轻量内嵌/REST 服务 | [轻量 HTTP 服务规范](cpp-http-lightweight.md) |
| `boost-asio-beast` | `Boost.Asio` / 独立 `Asio` + `Boost.Beast`（TCP/HTTP/WS） | CMake · 自定义异步网络与协议 | [Asio & Beast 规范](boost-asio-beast.md) |
| `grpc-protobuf` | gRPC + Protocol Buffers（契约演进、流式、Deadline） | CMake · RPC 与二进制协议 | [gRPC & Protobuf 规范](grpc-protobuf.md) |
| `messaging-zmq-mqtt` | ZeroMQ (`cppzmq`) / MQTT (`Paho MQTT`) / AMQP (`AMQP-CPP`) | CMake · 低延迟流与可靠消息队列 | [ZeroMQ / MQTT / AMQP 规范](messaging-zmq-mqtt.md) |

### 协议契约与序列化
| 标识 | 覆盖库与能力 | 适用构建与环境 | 规范指南 |
| --- | --- | --- | --- |
| `openapi` | OpenAPI 3.0 / 3.1、`application/problem+json`、代码生成 | 接口契约（前后端共用） | [OpenAPI 规范](openapi.md) |
| `json` | `nlohmann/json`、`simdjson`、`Glaze`、`jsoncpp` | CMake · JSON 严格校验与高性能解析 | [JSON 边界规范](json.md) |

### 数据存储、缓存与列式分析
| 标识 | 覆盖库与能力 | 适用构建与环境 | 规范指南 |
| --- | --- | --- | --- |
| `sqlite` | SQLite3 C API / Qt SQL (`QSQLITE`)、WAL + `BEGIN IMMEDIATE` | CMake / qmake · 单机嵌入式存储 | [SQLite 规范](sqlite.md) |
| `postgresql-libpqxx` | PostgreSQL 迁移 + `libpqxx` 连接池与 SQLSTATE 重试 | CMake · 企业级服务端数据库 | [PostgreSQL & libpqxx 规范](postgresql-libpqxx.md) |
| `mysql-mariadb` | `Boost.MySQL` / `libmysqlclient` / `libmariadb` / `utf8mb4` | CMake / Qt SQL · MySQL 生态对接 | [MySQL & MariaDB 规范](mysql-mariadb.md) |
| `redis-cache` | `redis-plus-plus` / `hiredis`（分布式锁、Pipeline、Pub/Sub） | CMake · 缓存与状态协调 | [Redis 规范](redis-cache.md) |
| `duckdb-analytics` | DuckDB + Apache Arrow / Parquet 嵌入式列式分析 | CMake / Python · 桌面与混合 OLAP | [DuckDB & Arrow 规范](duckdb-analytics.md) |

### C++ 通用基础设施
| 标识 | 覆盖库与能力 | 适用构建与环境 | 规范指南 |
| --- | --- | --- | --- |
| `cpp-core-utils` | `fmt`、`CLI11`、`yaml-cpp`、`toml++`、OpenSSL 3、`Eigen`、`OpenCV` | CMake · 通用基础、配置、加密与计算 | [C++ 通用基础库规范](cpp-core-utils.md) |
| `observability-security` | `spdlog`、`QLoggingCategory`、OS 凭据库、PDB/DWARF/dSYM | 全栈日志、Request-ID 与崩溃诊断 | [可观测性与安全规范](observability-security.md) |
| `testing` | GoogleTest、Catch2、Google Benchmark、Qt Test、`pytest`、CTest | 全栈单测、基准测试与集成测试 | [全栈测试规范](testing.md) |

### Web 与 Python 跨端协作栈
| 标识 | 覆盖库与能力 | 适用构建与环境 | 规范指南 |
| --- | --- | --- | --- |
| `web-frontend-stack` | React / Vue 3 + TypeScript + Vite + Tailwind + TanStack Query | Node / npm / pnpm · `C++ + Web` 前端 | [Web 前端协作栈规范](web-frontend-stack.md) |
| `python-bindings` | `nanobind` / `pybind11` / C ABI + `scikit-build-core` | CMake + Python · 同进程扩展与 GIL | [Python 绑定规范](python-bindings.md) |
| `python-service-stack` | FastAPI + Pydantic v2 + `uvicorn` + `httpx` + `uv` | Python 3.10+ · `C++ + Python` 编排服务 | [Python 服务协作栈规范](python-service-stack.md) |

## 2. 用户自供未收录技术栈兜底协议

当项目或用户指定了仓库未收录的库（如 `RocksDB`、`LevelDB`、`SDL_net`、`libuv`、`POCO`、`Doctest` 等），按以下 4 步处理：

1. **尊重选型并探测真实接口**：从项目构建文件（`vcpkg.json`、`conanfile`、`CMakeLists.txt`、`pyproject.toml`、`package.json`）、本机已装头文件或官方最新包文档确认确切的导入 target 名、命名空间与版本 API，绝不靠记忆猜测 API。
2. **强制沿用通用工程约束**：
   - ABI、符号导出与编码约定遵循 [C++ 规范与 ABI 边界](../workflow/cpp-standards-and-abi.md)。
   - 跨线程/事件循环、超时预算、幂等性与事务边界遵循对应架构指南（[C++ + Web](../architectures/cpp-web.md) / [C++ + Qt](../architectures/cpp-qt.md) / [C++ + Python](../architectures/cpp-python.md)）。
   - 验证与证据遵循 [验证与质量门禁](../workflow/verification-and-quality.md)。
3. **如实标注覆盖范围**：在交付报告中说明该技术栈依据项目既有配置及头文件实现。
4. **（可选）沉淀为新规范**：若团队长期高频使用该库，可套用 [`stack-spec.md` 模板](../../assets/templates/stack-spec.md) 在本目录新增 `<stack-id>.md` 并于上表登记，然后运行 `python <skill_dir>/scripts/validate_skill.py` 校验。
