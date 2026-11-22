# Web 前端协作栈规范（React / Vue / TypeScript / Vite）

适用范围：`C++ + Web` 全栈中的前端应用（React / Vue 3 + TypeScript + Vite + Tailwind CSS + TanStack Query / Pinia + `openapi-typescript`）。

## 1. 适用场景与选型边界

- **默认组合**：中后台管理台、桌面级 Web 工作台与设备控制面板优先 **React 或 Vue 3 + TypeScript（`strict: true`）+ Vite**；服务端状态缓存用 **TanStack Query**（React/Vue 通用），前端状态按轻量 Store（Zustand / Pinia）管理。
- **契约衔接**：与 C++ 后端对接的接口类型一律由 [OpenAPI 契约](openapi.md) 自动生成（`openapi-typescript` / `orval`），禁止手写第二份独立 DTO 接口。

## 2. 高频踩坑（反模式 vs 正解）

1. **手写接口类型导致前后端字段静默漂移**：
   - 每次修改后端 OpenAPI 后先重新执行类型生成脚本，再跑 `tsc --noEmit` 让编译器立即暴露所有字段改名、可空性变化（`string | null` vs `undefined`）与枚举新增。
2. **页面切换/卸载后在途请求覆盖当前状态或报错**：
   - 所有 `fetch` / `axios` 请求必须接入 **`AbortController`（`signal`）**；在组件卸载或查询 key 切换时自动取消未完成请求（TanStack Query 会传 `signal`，手动请求务必透传）。
3. **误解析非 JSON 错误响应（如 SPA Fallback 或 502 HTML 页）**：
   - `response.json()` 前先核对 `response.ok` 与 `Content-Type`（区分 `application/json` / `application/problem+json` 与网关纯文本/HTML 报错），将结构化错误统一映射为 UI 四态（见 [UI 布局与交互](../ui/layouts.md)）。
4. **WebSocket 无退避死循环重连**：
   - 对接 C++ WebSocket 服务端（Drogon / Boost.Beast）时，断线重连必须采用 **指数退避 + 随机抖动（Exponential Backoff + Jitter）** 并在组件销毁时 `close()`，避免后端重启瞬间被大量客户端重连打爆。
5. **`DESIGN.md` 主题变量映射 & 生产部署路径**：
   - 按 [主题总览](../ui/themes/index.md) 将色板、字阶（含中文回退）和间距写入 CSS Custom Properties（`--bg-canvas`、`--accent-primary` 等），不要硬编码散落十六进制色值。
   - 若 C++ 后端把前端托管在非根子路径（如 `/ui/`），构建需配置对应的 Vite `base` 并确保 `/api/*` 路由优先于 SPA `index.html` 回退规则。

## 3. 验证要点

- **静态门禁**：`npx tsc --noEmit` + 项目 `lint` + `npm run build` 必须全绿。
- **联调验证**：开发代理（`vite.config.ts` `server.proxy`）与真实构建产物 `dist/` 均需对接真实 C++ 后端跑通核心 CRUD、表单校验失败（4xx）、断网/超时取消与窄屏响应式布局。
