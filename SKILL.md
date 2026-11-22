---
name: cpp-fullstack-dev
description: "开发、规划、接手和验证 C++ 全栈项目，支持 C++ + Web（OpenAPI/REST/React/Vue/TypeScript）、C++ + Qt（Qt5/Qt6 Widgets/Quick/qmake）与 C++ + Python（nanobind/pybind11/gRPC/FastAPI）三种全栈架构及纯 C++ 服务与工具。Use when building, planning, maintaining, or verifying C++, C++ + Web, C++ + Qt, or C++ + Python full-stack repositories; not for bare-metal/RTOS firmware, Linux kernel drivers, or pure Web/Python repos without C++. 包含并发/网络/泛型工程规范与模块化低耦合架构/设计模式指引，支持用户自供技术栈与 AI 协助规划技术栈，内置 22 份常用库规范仓库、CMake/vcpkg/CTest/Conan 构建体系与可自定义 DESIGN.md 主题系统。"
---

# C++ 全栈开发

先按用户意图确定交付边界：方案规划与只读设计在分析完即可交付；代码改动必须核对真实源码、构建配置并基于实际执行结果汇报。**工程既有约定、构建文件和源码事实优先于 Skill 默认规则。**

> 路径约定：下文 `<skill_dir>` 指本 `SKILL.md` 所在目录；在用户目标仓库执行探测时请使用 `<skill_dir>/scripts/...` 绝对或解析后路径（Linux/macOS 请将 `python` 替换为 `python3`）。

## 标准执行流程

1. **探测工程现状与分流模式**：只读运行 `python <skill_dir>/scripts/inspect_project.py [project_root]` 获取仓库画像（构建系统、目标、依赖、接口文件、自定义主题及可选 `cpp-stack.json` 校验）。无需强行在用户仓库写入 `cpp-stack.json`。按 [模式与路由](references/workflow/modes-and-routing.md) 区分「从零开发 / 存量维护 / 续做」。
2. **确定全栈形态与技术栈获取方式**：
   - **用户自供技术栈**：以用户声明或工程实测配置为准。查 [技术栈规范仓库](references/stacks/catalog.md)，命中则按需读取；未命中时严格按仓库中的「未收录栈兜底协议」处理，**不擅自替换用户选型**。
   - **AI 协助规划技术栈**：建议先运行 `python <skill_dir>/scripts/probe_env.py` 核对本机已安装编译器、Qt、vcpkg、Node 与 Python 环境，再读取 [技术栈规划指南](references/workflow/stack-planner.md) 与 [技术栈规范仓库](references/stacks/catalog.md)（纯规划确认前最多再加读 1 份对应架构指南，具体库与平台文档待用户确认后再按需加载），先给出推荐组合、备选方案与取舍边界，待用户确认后再建工程。
3. **按需加载专题指南（渐进披露）**：从下方速查表仅读取本轮任务直接涉及的 1~3 份文档，避免通读无关目录。
4. **编码实现与构建验证**：需要编译、测试或部署前，运行 `python <skill_dir>/scripts/probe_env.py` 探测本机编译器、CMake、vcpkg、Qt、Node、Python 及激活脚本路径。编写代码遵循 [C++ 规范与 ABI 边界](references/workflow/cpp-standards-and-abi.md)、`references/engineering/` 通用工程约束及对应构建/平台文档。
5. **基于证据交付**：按 [验证与质量门禁](references/workflow/verification-and-quality.md) 汇报改动、实际命令、退出码、运行环境与未验证项及原因。需要跨会话续做时使用 [任务交接模板](assets/templates/task-handoff.md)。

## 速查路由表

| 任务场景 | 第一入口 | 关联参考 |
| --- | --- | --- |
| 新建工程 / 选型规划 / 确定组件边界 | [模式与路由](references/workflow/modes-and-routing.md) | [技术栈规划指南](references/workflow/stack-planner.md) · [CMakeLists 模板](assets/templates/CMakeLists.txt) · [可选 cpp-stack.json 模板](assets/templates/cpp-stack.json) |
| **C++ + Web** 全栈（OpenAPI / REST / 前端联调） | [C++ + Web 架构](references/architectures/cpp-web.md) | [Drogon](references/stacks/drogon.md) · [轻量 HTTP](references/stacks/cpp-http-lightweight.md) · [Web 前端栈](references/stacks/web-frontend-stack.md) · [OpenAPI](references/stacks/openapi.md) |
| **C++ + Qt** 桌面与图形工具（Widgets / Quick / ImGui） | [C++ + Qt 架构](references/architectures/cpp-qt.md) | [Widgets](references/stacks/qt-widgets.md) · [Quick](references/stacks/qt-quick.md) · [Qt 网络客户端](references/stacks/qt-network-client.md) · [Dear ImGui](references/stacks/dear-imgui.md) |
| **C++ + Python** 混合开发（原生扩展 / 服务编排） | [C++ + Python 架构](references/architectures/cpp-python.md) | [Python 绑定](references/stacks/python-bindings.md) · [Python 服务栈](references/stacks/python-service-stack.md) · [gRPC & Protobuf](references/stacks/grpc-protobuf.md) |
| 界面布局、交互四态与 `DESIGN.md` 主题/自定义 | [UI 布局与交互](references/ui/layouts.md) | [主题总览](references/ui/themes/index.md) · [自定义主题接口](references/ui/themes/custom-interface.md) |
| 网络、存储、缓存、消息与通用基础库规范 | [技术栈规范仓库](references/stacks/catalog.md) | [Asio/Beast](references/stacks/boost-asio-beast.md) · [SQLite](references/stacks/sqlite.md) · [PG](references/stacks/postgresql-libpqxx.md) · [MySQL](references/stacks/mysql-mariadb.md) · [Redis](references/stacks/redis-cache.md) · [DuckDB](references/stacks/duckdb-analytics.md) · [通用库](references/stacks/cpp-core-utils.md) |
| **并发 / 网络 / 泛型** 底层 C++ 编程陷阱 | [并发规范](references/engineering/concurrency.md) | [网络规范](references/engineering/networking.md) · [泛型与模板规范](references/engineering/generics.md) |
| **项目管理、低耦合架构与设计模式** | [架构与项目管理](references/engineering/architecture-and-project-management.md) | [C++ 规范与 ABI](references/workflow/cpp-standards-and-abi.md) · [模式与路由](references/workflow/modes-and-routing.md) |
| CMake / vcpkg / CTest / qmake / Conan 构建与发布 | [CMake / vcpkg / CTest](references/build/cmake-vcpkg-ctest.md) | [qmake 与其他构建](references/build/legacy-and-alt-builds.md) · [Windows](references/build/platforms/windows.md) · [Linux](references/build/platforms/linux.md) · [macOS](references/build/platforms/macos.md) |
| 测试、Sanitizer、静态分析与交付验收 | [验证与质量门禁](references/workflow/verification-and-quality.md) | [测试指南](references/stacks/testing.md) · [C++ 规范与 ABI](references/workflow/cpp-standards-and-abi.md) |

## 内置确定性工具

- `python <skill_dir>/scripts/inspect_project.py [project_root]`：只读分析项目构建系统、目标、依赖、接口与可选 `cpp-stack.json`。
- `python <skill_dir>/scripts/probe_env.py`：只读探测本机编译器（含 Windows VS `vcvars64.bat`）、CMake、vcpkg、Qt、Node、Python 与质量工具。
- `python <skill_dir>/scripts/extract_theme.py <preset|path|--list>`：只读提取预设或自定义 `DESIGN.md` / `theme.json` 的精简语义 Token JSON（避免通读数百行预设文本）。
- `python <skill_dir>/scripts/validate_skill.py`：修改本 Skill 文档、模板或新增技术栈/自定义主题后执行自检与脚本单元测试。
