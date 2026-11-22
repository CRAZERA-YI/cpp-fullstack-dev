# Drogon 后端服务规范

适用范围：CMake（vcpkg port `drogon`，导出的 target 为 `Drogon::Drogon`）。

## 1. JSON 与数据库两条核心边界选型（消除架构摩擦）

Drogon 原生自带基于 `jsoncpp` 的 `Json::Value`（`req->getJsonObject()`）以及基于 `trantor` 事件循环的非阻塞 `drogon::orm::DbClient`。引入项目时必须明确以下二选一边界，**不要在同一条链路里混写**：

| 边界 | 方案 A（推荐纯 Drogon 新服务） | 方案 B（已有 `nlohmann/json` 或 `libpqxx`/SQLite 共享核心） |
| --- | --- | --- |
| **JSON 解析与响应** | 统一用 Drogon 原生 `req->getJsonObject()` 与 `HttpResponse::newHttpJsonResponse()`（`jsoncpp`） | 弃用 `getJsonObject()`，直接读 `req->body()` 交由 `nlohmann::json` 解析校验，并用 `HttpResponse::newHttpResponse()` + `CT_APPLICATION_JSON` 返回（绝不二次解析）。 |
| **数据库访问** | 用 Drogon 异步 `drogon::orm::DbClient`（支持 PostgreSQL / SQLite3 / MySQL）或 C++20 协程 `Task<HttpResponsePtr>`，天然不阻塞事件循环。 | 把同步 `libpqxx` / `sqlite3` 包装为有界线程池/工作队列，完成后切回响应回调；绝不在 Drogon IO 线程内直接执行阻塞 SQL。 |

## 2. 异步生命周期与单次完成约束

1. **回调有且只有一条完成路径**：成功、输入校验失败、超时、服务端关停可能并发触发回调时，使用 `std::shared_ptr<std::atomic_bool>` 或封装完成的上下文确保 `callback(resp)` 只执行一次。
2. **禁止悬空捕获**：异步 lambda 或投递给工作队列的任务只能按值/智能指针持有输入数据与共享状态，**禁止捕获 `req` 的裸字符串视图或栈局部引用**。

```cpp
void NotesController::createNote(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback) {
    auto sharedCallback = std::make_shared<std::function<void(const HttpResponsePtr&)>>(
        std::move(callback));
    auto completed = std::make_shared<std::atomic_bool>(false);

    auto completeOnce = [sharedCallback, completed](const HttpResponsePtr& resp) {
        if (!completed->exchange(true)) {
            (*sharedCallback)(resp);
        }
    };

    // 将解析后的 DTO 投递至有界工作队列或异步 ORM，在所有分支通过 completeOnce 返回
    m_service->createAsync(std::string(req->body()), completeOnce);
}
```

## 3. 错误映射与验证

- **契约映射与请求限额**：在应用初始化配置合理的请求体上限（`app().setClientMaxBodySize(...)`）与连接/速率限制，防止超大载荷或突发流量耗尽内存；请求格式错误返回 `400`/`422`（附带契约字段错误，禁止泄露 parser 栈）；资源不存在返回 `404`；数据库唯一冲突返回 `409`；未知异常记录携带 `requestId` 的内部日志并返回通用 `500` `application/problem+json`。
- **集成验证**：使用独立端口与隔离临时库启动实例，等待就绪后用真实 HTTP 客户端核对状态码、`Content-Type`、JSON 字段与并发超时下仅响应一次；测试结束必须优雅退出服务并确认无残留工作线程。
