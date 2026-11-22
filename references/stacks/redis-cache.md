# Redis 缓存与状态协调规范

适用范围：CMake（推荐 `redis-plus-plus` `redis++::redis++` 或底层 C 客户端 `hiredis::hiredis`）。

## 1. 适用场景与选型边界

- **何时选用**：高频热点读缓存、跨实例分布式锁、限流计数器、短期会话态（Session/Token）或轻量 Pub/Sub 广播。
- **何时避免**：需要强事务 ACID、复杂关联查询或持久化主存储时不得用 Redis 替代关系型数据库；需要持久化消息消费与死信队列语义时选 [消息中间件](messaging-zmq-mqtt.md)（如 AMQP）。

## 2. 构建与接入

- `redis-plus-plus` 依赖 `hiredis`；启用 TLS 时核对 vcpkg features（`redis-plus-plus[cxx17,tls]` 与 `hiredis` 的 OpenSSL/`ssl` 支持）；静态与动态链接导出目标可能分别为 `redis++::redis++_static` 或 `redis++::redis++`（接入前核对实际 CMake target）。Windows/Linux 构建均需注意匹配 C++17 `std::optional` / `sw::redis::OptionalString` ABI。

## 3. 高频踩坑（反模式 vs 正解）

1. **未设超时与无界连接池导致整机雪崩**：构造 `sw::redis::ConnectionOptions` 与 `ConnectionPoolOptions` 时**必须显式设置 `connect_timeout`、`socket_timeout` 与池上限 `size` / `wait_timeout`**，否则 Redis 抖动或网络黑洞会把整个后端线程卡死。
2. **分布式锁误删他人锁**：
   - 加锁必须带唯一随机 token 与自动过期：`SET lock:key <uuid> NX PX <ttlMs>`（单条原子命令，勿拆成 `SETNX` + `EXPIRE`）。
   - 解锁**严禁直接 `DEL`**（若自身 GC/卡顿超时，可能删掉别人新加的锁），必须用 Lua 脚本校验 token 相等后再删。

```cpp
// 安全释放分布式锁：仅当值匹配当前持锁 token 时删除（文件/类作用域常量用 k 前缀以符合 .clang-tidy）
static constexpr std::string_view kUnlockLuaScript =
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end";

const long long released = redisClient.eval<long long>(
    kUnlockLuaScript, {lockKey}, {lockToken});
```

3. **误把 Redis `nil` 回复当成空字符串或未判空**：`redis++` 查询缺失键返回 `OptionalString`（空 `std::optional`），解引用前务必 `if (val)`；原始 `hiredis` 需检查 `reply == nullptr`（连接级错误）与 `reply->type == REDIS_REPLY_NIL`，且所有非空 `redisReply*` 必须配对 `freeReplyObject`。
4. **把 `Pipeline` 当成原子事务 & Pub/Sub 重连断档**：
   - `Pipeline` 只合并网络往返（RTT），不保证命令间原子隔离；多键原子更新使用 `MULTI/EXEC` 或 Lua 脚本（集群下相关键需共享 `{hashTag}` 确保落入同一 Slot）。
   - `Subscriber` 连接进入阻塞监听后**不可再用同一连接发普通命令**，断线重连后必须重新执行 `subscribe()`。
5. **缓存穿透与雪崩**：空结果可短 TTL 缓存占位或用布隆过滤拦截；同批热点 key 的 TTL 增加随机抖动时间（Jitter）。

## 4. 验证要点

- 验证键不存在（`nil`）、并发抢锁与超时后不会误删别人锁、`socket_timeout` 触发时业务降级不挂起，以及 Redis 重启后连接池自动恢复。
