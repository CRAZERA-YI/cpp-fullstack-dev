# 消息通信规范（ZeroMQ / MQTT / AMQP）

适用范围：CMake（`cppzmq` / `libzmq`、`PahoMqttCpp::paho-mqttpp3`、`amqpcpp`）。

## 1. 适用场景与选型边界

| 协议 / 库 | 定位与优势 | 选型禁忌 |
| --- | --- | --- |
| **ZeroMQ (`cppzmq` / `libzmq`)** | 无中心 Broker 的极低延迟进程间/跨机传输（`PUB/SUB`、`REQ/REP`、`DEALER/ROUTER`），适合 `C++ + Python` 实时流或分布式节点 | 无原生消息持久化落盘保障；需要离线缓存与严格签收时不要硬造轮子。 |
| **MQTT (`Paho MQTT C/C++`)** | 轻量 IoT / 设备遥测与桌面端推送（QoS 0/1/2、遗嘱 LWT、断网缓冲） | 大载荷文件或复杂路由拓扑（请用 AMQP / HTTP）。 |
| **AMQP (`AMQP-CPP` / RabbitMQ)** | 企业级可靠队列、延迟/死信队列（DLQ）、多消费者 ACK 负载均衡 | 追求微秒级无 Broker 直连时开销过大。 |

## 2. 高频踩坑（反模式 vs 正解）

### ZeroMQ (`cppzmq`)
1. **跨线程共享 `zmq::socket_t`（崩溃/竞态根源）**：`zmq::context_t` 是线程安全的，但 **`zmq::socket_t` 严格属于单个创建它的线程**！禁止加互斥锁在不同线程间传递或读写同一 socket；线程间通信应通过 `inproc://` 独立 socket 对完成。
2. **退出时 `zmq_ctx_term` 永久卡死**：默认 `ZMQ_LINGER` 为 `-1`（无限等待），如果对端失联且发送队列尚有未发包，销毁 `context_t` 会永远挂起！关闭每个 socket 前显式设 `socket.set(zmq::sockopt::linger, 0)`（或有限毫秒超时）再 `close()`。
3. **`PUB/SUB` 慢连接丢失前几条 & 内存爆仓**：订阅端连上并完成过滤传播前发布的消息会被直接丢弃（需同步握手或业务容忍）；高吞吐下必须设置合理 `ZMQ_SNDHWM` / `ZMQ_RCVHWM` 并处理 `EAGAIN`。

### MQTT (`Paho MQTT`)
1. **QoS 1 至少一次投递带来重复消息**：消费端必须基于业务消息 ID 实现幂等去重；不要在回调线程 `message_arrived` 内执行阻塞数据库/网络调用或同步重连。
2. **断线重连丢订阅**：使用 `clean_session = true` 时每次重连 Broker 都会清空订阅，必须在 `connected()` 回调里**重新订阅所有 Topic**；若需离线积压，设 `clean_session = false` 并保证全局唯一的 `client_id`。
3. **遗嘱消息（LWT）未配置**：设备或子进程异常掉线需要立刻感知时，在 `connect_options` 预先注册 Will Topic/Payload。

### AMQP (`AMQP-CPP`)
- 必须确保事件循环与网络库（libuv / Boost.Asio / libev）按时驱动心跳（Heartbeat）；消费异常无法处理的消息需明确 `nack(requeue=false)` 送入死信交换机，防止毒丸消息无限重投打死消费者。

## 3. 验证要点

- 覆盖：无接收方时关闭发送端确认退出不卡死（验证 `LINGER`）、断网重连后订阅恢复与消息幂等去重，以及高背压队列满载时的丢弃/阻塞契约。
