# gRPC 与 Protocol Buffers 规范

适用范围：CMake（`protobuf::libprotobuf`、`gRPC::grpc++`）。

## 1. `.proto` 契约演进规则

- **永不复用字段编号**：删除已发布字段必须使用 `reserved` 同时保留其编号与字段名，避免旧客户端/旧持久化数据错解。

```proto
syntax = "proto3";

message Note {
  reserved 2;
  reserved "legacy_title";

  string id = 1;
  optional string title = 3;
}
```

- **区分“未传”与“默认值”**：需要存在性（presence）语义时使用 proto3 `optional` 或 `oneof`；枚举始终以 `*_UNSPECIFIED = 0` 开头并妥善处理未知枚举值。
- **二进制 vs JSON**：若接口需经由 JSON 网关转换，单独验证 `optional` presence 与未知字段的保留行为。

## 2. 构建生成与交叉编译依赖

- 生成规则必须将主 `.proto`、所有被 `import` 的 `.proto` 文件、`protoc` 及 `grpc_cpp_plugin` 一并列为输入依赖，输出放入 `CMAKE_CURRENT_BINARY_DIR`（勿将生成代码提交进 Git 源码树造成版本漂移）。
- **交叉编译**：代码生成阶段调用**宿主机可执行**的 `protoc` 与插件，链接阶段链接**目标架构**的 `libprotobuf` 与 `grpc++`，并确保主次版本兼容。

## 3. 高频踩坑（Deadline、取消与流式生命周期）

1. **无期限挂起**：所有外发 RPC（包括同步调用）必须在 `ClientContext` 设置合理 `deadline`；中间服务将剩余预算向下游传递，并在长循环中主动检查 `ServerContext::IsCancelled()`。
2. **盲目重试非幂等写操作**：传输层 `UNAVAILABLE` 重试前确认写接口具有业务幂等键（Idempotency Key）；`INVALID_ARGUMENT` 绝不重试。
3. **异步 `ClientContext` 过早销毁**：每次调用创建独立 `ClientContext`；异步模式下 `ClientContext`、request/response 与 `Status` 必须存活到对应回调或 `CompletionQueue` 事件被彻底消费。
4. **流式读写并发违规**：同一条 gRPC stream 任何时刻至多允许 **1 个并发 `Read()` 和 1 个并发 `Write()`**，不能并发两次 `Write()`；服务关停前先停止接收新请求并排干完成队列。

## 4. 验证要点

- 本地随机端口起服务，覆盖：正常请求、故意延迟触发 `DEADLINE_EXCEEDED`、客户端主动取消、对端中途断流及 `Server::Shutdown()` 优雅关停；协议变更时使用旧版 wire bytes 做交叉兼容反序列化测试。
