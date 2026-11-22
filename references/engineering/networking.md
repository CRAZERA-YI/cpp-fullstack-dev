# 网络编程通用规范与协议陷阱

适用于底层 Socket（POSIX/Winsock）与自定义传输协议设计。具体框架实现见 [Asio & Beast](../stacks/boost-asio-beast.md)、[Drogon](../stacks/drogon.md)、[gRPC](../stacks/grpc-protobuf.md) 与 [Qt 网络客户端](../stacks/qt-network-client.md)。

## 1. TCP 流式分帧（无天然消息边界）

- **永远不要假设一次 `recv()` / `async_read_some()` 等于一条完整消息**：TCP 是字节流，一次读可能只收到半包，也可能一次粘连多条消息。
- **强制显式分帧**：自定义二进制协议推荐 `[4 字节长度前缀] + [版本/类型] + [载荷]`（或行分隔 / HTTP / gRPC），**解码前必须先校验长度前缀 `<= kMaxFrameBytes`**，否则恶意或损坏的超大长度字节会直接触发 OOM 分配崩溃。
- **循环处理部分读写（Short Read / Short Write）**：阻塞或非阻塞 Socket 写大数据时 `send()` 可能只发出部分字节，必须循环写入剩余偏移直到全部发完或遇到致命错误。

## 2. 线路编码、字节序与版本兼容

- **严禁直接 `memcpy` C++ `struct` 发送到网络**：不同编译器/架构的 struct 内存对齐填充（padding）、枚举大小、布尔表示与端序均可能不同，且指针/STL 容器直接内存发送毫无意义。
- **固定宽度与显式字节序**：全部协议字段使用 `std::uint16_t` / `std::uint32_t` / `std::uint64_t`，按网络字节序（大端）或明确定义的小端编解码；新协议头部预留版本号（`protocolVersion`）和扩展标志位，或直接复用 [Protobuf](../stacks/grpc-protobuf.md) / [JSON](../stacks/json.md)。

## 3. 超时体系、半开连接与 OS 信号

- **拆分三类超时**：建立连接超时（Connect Timeout）、单次读写空闲超时（Idle Read/Write Timeout）与全链路请求总预算（Deadline），避免慢速攻击（Slowloris）耗尽服务端连接槽位。
- **POSIX / Winsock 差异与信号抑制**：
  - Linux/macOS 下向已关闭对端 `send()` 会触发 **`SIGPIPE`**，默认直接杀死整个进程！进程初始化必须忽略 `SIGPIPE`（`std::signal(SIGPIPE, SIG_IGN)`）或在发送传 `MSG_NOSIGNAL`（macOS 用 `SO_NOSIGPIPE`），把断连变成常规错误码 `EPIPE`。
  - 阻塞调用遇到 `EINTR`（信号中断）应重试；非阻塞遇 `EAGAIN` / `EWOULDBLOCK`（Windows `WSAEWOULDBLOCK`）交由 `epoll`/`kqueue`/`IOCP` 等待下次就绪。
- **探测半开连接（Half-Open TCP）**：网线拔掉或对端宿主机断电时，如果没有数据交互，TCP 本身不会主动告知断连。长连接必须在应用层实现 **Ping/Pong 心跳 + 超时踢出**（勿仅依赖长达数小时的 OS 默认 `SO_KEEPALIVE`）。

## 4. 背压、重连风暴与端口绑定

- **每连接有界发送缓冲**：慢客户端读取不及时时，服务端无限制往发送队列塞包会撑爆内存；超出高水位线（HWM）时应降级丢弃非关键帧或主动踢断慢连接。
- **指数退避 + 随机抖动（Jitter）**：客户端重连必须采用带上限的指数退避与随机抖动，防止服务端重启瞬间所有客户端同时重连引发惊群雪崩。
- **端口绑定与双栈**：服务端监听设置 `SO_REUSEADDR`（避免重启卡在 `TIME_WAIT`）；明确区分仅本机回环（`127.0.0.1`）还是全网卡暴露（`0.0.0.0`），优先用 `getaddrinfo` 同时兼容 IPv4 与 IPv6，不硬编码 IPv4 结构。

## 5. 进程信号安全优雅退出（Signal Safety）

- **严禁在原始 POSIX 信号处理器中加锁、分配内存、写日志或直接调 `Server::Shutdown()`**：`SIGINT` / `SIGTERM` 异步信号处理器只能调用 async-signal-safe 函数（例如只置位 `volatile std::sig_atomic_t` 或向 self-pipe/eventfd 写 1 字节）。
- **推荐优雅退出接入方式**：使用 `boost::asio::signal_set`、独立 `sigwait` 线程（配合 `pthread_sigmask` 屏蔽业务线程信号），或在 Windows 下通过 `SetConsoleCtrlHandler` 向事件循环投递异步停机任务。

## 6. 幂等性与传输安全

- 非幂等写请求超时后不可无条件重发，必须配合业务幂等键（详见 [Drogon](../stacks/drogon.md) / [gRPC](../stacks/grpc-protobuf.md)）；除本机闭环测试外，公网或跨机传输默认启用 TLS 并开启证书链与主机名校验。
