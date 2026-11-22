# C++ + Python 全栈架构指南

适用于 **C++ 高性能核心/计算/硬件接口 + Python 应用层/Web API/数据分析/AI 推理编排**。

## 1. 集成模式选型：同进程绑定 vs 跨进程服务

| 维度 | 模式 A：同进程绑定 (`nanobind` / `pybind11` / C ABI) | 模式 B：跨进程通信 (`gRPC` / HTTP / UDS / Named Pipe) |
| --- | --- | --- |
| **调用延迟与数据吞吐** | 纳秒级调用；支持 NumPy/Buffer 零拷贝内存共享 | 毫秒~亚毫秒级序列化开销 |
| **故障隔离** | C++ 段错误直接导致 Python 解释器崩溃 | 进程完全隔离，各自独立崩溃重启与弹性扩缩 |
| **依赖与环境冲突** | 需对齐编译器 ABI、Python 主版本及 Wheel 打包 | C++ 与 Python 拥有完全独立的依赖树（如 CUDA / PyTorch 隔离） |
| **推荐场景** | 高频算法算子、图像/信号矩阵处理、本地 SDK 封装 | C++ 核心引擎 + FastAPI/Web 网关、GPU 推理旁路、异构部署 |

选型前若尚未确定模式，参考 [技术栈规划指南](../workflow/stack-planner.md)。

## 2. 模式 A：同进程混合架构关键约束

具体绑定语法、GIL 与打包见 [Python 绑定规范](../stacks/python-bindings.md)。核心架构纪律：
1. **核心层尽量保持纯 C++（无 Python.h 依赖）**：将算法/业务放在独立的纯 C++ 目标（可用 GoogleTest 独立测），绑定层只做薄薄一层类型映射、GIL 释放与异常转换。
2. **显式管理 GIL**：纯计算/阻塞 I/O 进入 C++ 前释放 GIL，避免阻塞 Python 多线程或 FastAPI 事件循环；任何接触 `PyObject`/Python 回调前必须重新持有 GIL。
3. **跨边界生命周期**：涉及零拷贝视图（如向 Python 暴露 C++ 内存指针）必须绑定 `keep_alive` 或 Capsule 析构器，严禁 C++ 释放内存后 Python 视图仍悬空。
4. **打包与测试双闭环**：使用 `scikit-build-core` 统一 CMake 与 Python Wheel 构建；验证同时跑 CTest（C++ 侧）与 `pytest`（Python 侧导入、异常、线程并发及包安装）。

## 3. 模式 B：跨进程服务架构关键约束

1. **契约先行**：内部高性能 RPC 优先 [gRPC + Protobuf](../stacks/grpc-protobuf.md)，对前端或轻量编排可选 REST + [OpenAPI](../stacks/openapi.md)；双方从同一 `.proto` 或 OpenAPI 文件生成代码。
2. **双向超时与优雅退出**：Python 网关（如 FastAPI/httpx/grpcio）必须将请求剩余 deadline 向下游 C++ 服务透传；主控拉起子进程时实现 `/healthz` 就绪探针与退出时信号清理，防止僵尸进程。
3. **统一追踪**：请求入口生成 `requestId` 经由 HTTP Header / gRPC Metadata 传入 C++ 服务，两侧日志共享同一追踪键（见 [日志与安全指南](../stacks/observability-security.md)）。
