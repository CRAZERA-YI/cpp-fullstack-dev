# 轻量 HTTP 服务规范（cpp-httplib / Crow / Oat++）

适用范围：CMake（vcpkg port：`cpp-httplib`、`crow`、`oatpp`；导出 target 如 `httplib::httplib`、`Crow::Crow`、`oatpp::oatpp`）。

## 1. 适用场景与选型边界

| 库 | 定位与优势 | 局限性 / 何时切走 |
| --- | --- | --- |
| **`cpp-httplib`** | 单头文件零繁琐依赖，极适合嵌入桌面/测试替身或低并发内部管理接口 | **一连接一线程阻塞模型**（长连接多时线程膨胀），高并发 Web 服务请切 [Drogon](drogon.md) 或 [Boost.Beast](boost-asio-beast.md)。 |
| **`Crow`** | 类似 Flask 的路由语法、内置 JSON 与 WebSocket，header-only 快速搭建 REST API | 模板编译耗时相对较高；自带简版 JSON 解析易与全局 JSON 契约分裂。 |
| **`Oat++`** | 零第三方重依赖、强类型 DTO 宏 + `ObjectMapper` + 内置 OpenAPI/Swagger 生成 | 宏风格侵入性较强；高吞吐异步模式（`oatpp::async`）心智负担明显高于同步线程模式。 |

## 2. 构建与接入

- **`cpp-httplib`**：启用 HTTPS 必须定义 `CPPHTTPLIB_OPENSSL_SUPPORT` 并链接 `OpenSSL::SSL` / `OpenSSL::Crypto`；若需压缩加 `CPPHTTPLIB_ZLIB_SUPPORT`。注意 vcpkg 中 `cpp-httplib` 默认开启 `brotli` 等可选压缩特性，纯本地/内网工具若无需压缩，建议在 `vcpkg.json` 声明 `{"name": "cpp-httplib", "default-features": false}` 以精简依赖图并缩短构建耗时。
- **`Crow`**：注意确认工程是走独立 `Asio` 还是 `Boost.Asio`（vcpkg 默认依赖独立 `asio`），不要与同进程其他 `Boost.Asio` 版本冲突。
- **`Oat++`**：大型项目将 `oatpp-swagger` 接入统一 API 文档入口时，需确保前端静态资源目录随安装树一并打包。

## 3. 高频踩坑（反模式 vs 正解）

1. **`cpp-httplib` 默认并发与请求大小限制**：
   - 未限制线程池与队列上限时大量空闲 Keep-Alive 或突发请求会耗尽线程或打爆内存；需要显式设 `server.new_task_queue = [] { return new httplib::ThreadPool(kThreads, kMaxQueuedRequests); }`（有界队列，对齐 [并发编程规范](../engineering/concurrency.md)）、读取/写入超时及 `set_payload_max_length()` 防 OOM。
   - **禁止**把阻塞 `httplib::Client` 放在 GUI 主线程或高并发网关事件循环内直接同步调用。
2. **`Crow` 路由与生命周期隐患**：
   - `crow::SimpleApp` 路由 lambda 由内部多工作线程并发调用，共享状态必须加锁或无锁化；在多个 `.cpp` 拆分路由时使用 `crow::Blueprint` 注册并把大路由体放到独立编译单元，缓解单文件模板编译爆炸。
   - 统一选用 `nlohmann::json`（读 `req.body`）或 `crow::json::rvalue` 之一做边界校验，避免混用。
3. **`Oat++` DTO 校验与连接池边界**：
   - `Oat++` 读取 DTO（`request->readBodyToDto`）后必须核对必填字段是否为 `nullptr`（DTO 字段默认可空），不要未判空直接解引用 `dto->title`。
   - 多线程同步 `ConnectionProvider` 下确保服务退出调用 `server.stop()` 与连接池正确释放顺序。

```cpp
// cpp-httplib 生产安全起手式：限定线程数与有界等待队列及超时，防止 Keep-Alive 与突发流量耗尽资源
httplib::Server server;
server.new_task_queue = []() {
    return new httplib::ThreadPool(kWorkerThreads, kMaxQueuedRequests);
};
server.set_read_timeout(5, 0);
server.set_write_timeout(5, 0);
server.set_payload_max_length(kMaxPayloadBytes);
```

## 4. 验证要点

- 测试超大请求体拒绝（`413`）、超时断开、并发请求下共享状态竞争以及信号触发后 `stop()` 在限时内干净退出（绑定随机端口 `bind_to_any_port` 运行集成测试）。
