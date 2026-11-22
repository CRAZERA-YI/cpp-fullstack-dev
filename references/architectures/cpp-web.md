# C++ + Web 全栈架构指南

适用于 **C++ 后端服务（HTTP/REST/WebSocket/SSE）+ Web 前端（TypeScript / React / Vue / Vite / Next.js 等）**。

## 1. 核心分层与契约流

```text
[OpenAPI 3.1 / .proto] ──▶ openapi-typescript / orval ──▶ [Web TS Client + UI]
         │                                                       │ (Vite Dev Proxy / Nginx)
         ▼                                                       ▼
[C++ HTTP Handler (Drogon等)] ──▶ [DTO Adapter] ──▶ [Service + DB (PostgreSQL/SQLite)]
```

- **单一契约源**：先改 `openapi.yaml` 再同步 C++ 路由与前端类型；绝不各自手写一套字段定义。具体版本兼容与空值语义见 [OpenAPI 规范](../stacks/openapi.md)。
- **统一错误体**：所有 4xx/5xx API 统一返回结构化错误（推荐 `application/problem+json`：`type`、`title`、`status`、`detail`、`requestId`），禁止把底层 SQL、文件路径或异常栈透传给前端。
- **JSON 解析单一边界**：若后端用 Drogon，选定 `Json::Value` 或 `nlohmann::json` 之一作为边界转换器（见 [Drogon 指南](../stacks/drogon.md)），禁止双重反序列化。

## 2. 前后端联调与生命周期坑点

1. **开发期跨域（CORS）vs 生产同源**：
   - 开发期优先配置前端开发服务器代理（如 Vite `server.proxy` 将 `/api`、`/ws` 转发到 C++ 后端随机/约定端口），避开宽泛的 `Access-Control-Allow-Origin: *`。
   - 若必须跨域且携带 Cookie/Credentials，服务端不能返回 `*`，需精确白名单校验 Origin 并显式处理 `OPTIONS` 预检。
2. **异步耗时与超时预算**：
   - 浏览器/Fetch 超时、网关超时、C++ 服务异步等待与数据库超时必须满足：`前端超时 > 后端处理上限 > 下游 DB 查询超时`。
   - 长任务用“202 Accepted + 任务 ID 轮询 / SSE / WebSocket 推送”替代长时间挂起 HTTP 连接；前端切路由或卸载组件时用 `AbortController` 取消在途请求。
3. **生产静态资源托管**：
   - **方案 A（内网/单二进制工具）**：前端 `npm run build` 产出的 `dist/` 由 C++ 服务直接托管静态文件，并把未知前端路由回退到 `index.html`（SPA History Fallback），但 `/api/*` 必须明确返回 JSON 404，不能误返回 `index.html`！**静态资源读取前必须先规范化 URL 路径（`std::filesystem::weakly_canonical`）并校验其仍位于 `dist/` 根目录内，防止 `../../` 目录穿越读取任意宿主文件。**
   - **方案 B（生产部署）**：Nginx/Caddy 托管静态资源 + 压缩/TLS，仅反向代理 `/api`、`/ws` 到 C++ 服务。
4. **认证、CSRF 与限额安全边界**：Web 端会话 Token 用 `HttpOnly; SameSite=Lax; Secure` Cookie 或内存短时 Token；**若采用 Cookie 鉴权，对所有状态变更请求（POST/PUT/PATCH/DELETE）必须叠加 CSRF 防护**（如 Double-Submit Token / 校验 `Origin` & `Referer` 或自定义请求头），服务端须显式配置最大请求体字节数与基本限流，并遵循 [日志与安全指南](../stacks/observability-security.md) 传递 `X-Request-Id`。

## 3. 端到端验证要求

- **后端**：运行 CTest 单元测试 + 独立端口集成测试（覆盖成功、非法字段、DB 冲突）。
- **前端**：执行项目 `typecheck` / `lint` / `build`（如 `tsc --noEmit && npm run build`）。
- **双端真实联调**：用测试配置启动 C++ 后端（等待 `/healthz` 就绪），通过真实 HTTP 请求或前端页面走通至少一条完整读写闭环并检查持久化落库，测试退出时确保清理后台服务进程与临时库。
- 界面布局与样式（若使用 `DESIGN.md`）：按 [UI 布局与交互](../ui/layouts.md) 与 [主题总览](../ui/themes/index.md) 映射为 CSS Custom Properties。
