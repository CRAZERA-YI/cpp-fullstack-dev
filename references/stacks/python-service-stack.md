# Python 服务与编排协作栈规范（FastAPI / Pydantic v2 / uvicorn / httpx / uv）

适用范围：`C++ + Python` 全栈架构中的 Python API 网关、AI 推理服务编排或异步客户端（Python >= 3.10）。

## 1. 适用场景与选型边界

- **何时选用**：用 **FastAPI + Pydantic v2 + `uvicorn`** 作为外层 HTTP/WebSocket API 编排层，内部调用同进程 C++ 扩展（[Python 绑定规范](python-bindings.md)）或通过 **`httpx` / `grpcio`** 转发给独立 C++ 微服务（[gRPC & Protobuf](grpc-protobuf.md)）。
- **包与环境管理**：新工程优先用 **`uv`** + `pyproject.toml` 锁死 Python 版本与依赖版本，保持开发与部署环境可复现。

## 2. 高频踩坑（反模式 vs 正解）

1. **在 `async def` 路由中直接调用阻塞 C++ 扩展（冻结整个服务事件循环！）**：
   - `uvicorn` 的 `asyncio` 事件循环是单线程的！如果在 `async def` 里直接调用耗时计算或阻塞 I/O 的 C++ `nanobind`/`pybind11` 函数（即便 C++ 侧释放了 GIL），**当前事件循环仍然会被该协程阻塞死**，所有并发 HTTP 请求全部卡住。
   - **正解**：要么把该路由声明为普通同步 **`def`**（FastAPI 会自动放进 AnyIO 线程池执行），要么在 `async def` 中通过 `await asyncio.to_thread(cpp_fn, ...)` 调度——且两者都**必须配合 C++ 绑定层释放 GIL（`gil_scoped_release`）**，线程池才会真正并发。

```python
# 正确：async def 通过 asyncio.to_thread 卸载 + C++ 内部释放 GIL
@app.post("/compute")
async def run_compute(payload: ComputeRequest) -> ComputeResponse:
    result = await asyncio.to_thread(cpp_engine.compute, payload.values)
    return ComputeResponse(score=result)
```

2. **全局无生命周期管理导致资源/子进程泄漏**：
   - C++ 核心引擎实例、数据库连接池或 `httpx.AsyncClient` / `grpc.aio.Channel` 必须在 FastAPI **`lifespan` 上下文管理器**中初始化并在退出阶段显式 `aclose()` / `shutdown()`，不要在每次请求里新建连接，也不要靠进程强杀回收。
3. **跨边界超时与 `X-Request-Id` 丢失**：
   - 使用 `httpx.AsyncClient` 调用下游 C++ HTTP 服务时显式设置 `timeout=httpx.Timeout(...)`，并在中间件透传 `X-Request-Id`；捕获 `httpx.TimeoutException` / `grpc.RpcError` 后映射为稳定的 502/504 `application/problem+json` 响应，避免直接抛出 `500 Internal Server Error` 暴露堆栈。
4. **Pydantic v2 校验边界混淆**：
   - 使用 Pydantic v2（`model_validate`、`ConfigDict(strict=True)` 按需控制隐式类型转换），在进入 C++ 核心前完成数值范围、字符串长度与编码验证。

## 3. 验证要点

- 用 `pytest`（配合 `httpx.AsyncClient` + `ASGITransport` 或真实 `uvicorn` 子进程）验证：并发调用阻塞 C++ 算子时健康检查 `/healthz` 仍保持毫秒响应（证明事件循环未被堵死）、非法输入返回 422、下游超时映射正确，以及进程退出时无线程/子进程残留。
