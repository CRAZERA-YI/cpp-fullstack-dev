# OpenAPI 契约规范

适用范围：接口契约文档（OpenAPI 3.0 / 3.1），适用于 `C++ + Web` 与 HTTP 客户端联调。

## 1. 3.0 与 3.1 核心差异（禁止混用语法）

- **可空语义**：
  - OpenAPI **3.0** 使用 `type: string` + `nullable: true`。
  - OpenAPI **3.1**（对齐 JSON Schema 2020-12）使用 `type: ["string", "null"]`，不再依赖 `nullable`。
- **`required` vs 可空**：`required` 仅表示 JSON 对象中 **键必须存在**（值仍可以是 `null`），两者正交，不可混淆。
- **`default` 语义**：服务端反序列化与生成客户端对 `default` 的自动注入行为可能不同，需在契约测试中明测。

## 2. 最小契约样例（OpenAPI 3.1 + `application/problem+json`）

```yaml
openapi: 3.1.0
info:
  title: Notes API
  version: 1.0.0
servers:
  - url: https://api.example.invalid
paths:
  /notes/{noteId}:
    get:
      operationId: getNote
      parameters:
        - name: noteId
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: Note found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Note"
        "404":
          description: Note not found
          content:
            application/problem+json:
              schema:
                $ref: "#/components/schemas/Problem"
components:
  schemas:
    Note:
      type: object
      required: [id, title]
      properties:
        id: { type: string }
        title: { type: [string, "null"] }
    Problem:
      type: object
      required: [title, status]
      properties:
        type: { type: string }
        title: { type: string }
        status: { type: integer }
        detail: { type: [string, "null"] }
        requestId: { type: [string, "null"] }
```

注意：`.invalid` 为 RFC 保留占位域名；多接口复用同一错误模型与分页结构（明确游标/排序稳定性和匿名访问安全策略）。

## 3. 兼容性与验证要点

- **破坏性变更**：删字段、改名、改类型、新加必填请求字段或收紧枚举，均属破坏性变更，需升版本或分阶段兼容。新增响应字段前检查严格模式的旧客户端是否拒绝未知字段。
- **固定生成工具版本**：若通过 `openapi-typescript` / `orval` 等生成代码，在 `package.json` 或配置中锁死工具版本并将生成产物 diff 纳入审查。
- **真实契约测试**：发起真实 HTTP 请求分别测试：缺必填键、显式传 `null`、合法值与 4xx/5xx `Content-Type`，确认与文档逐字一致。
