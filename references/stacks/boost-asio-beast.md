# Boost.Asio / Asio 与 Boost.Beast 规范

适用范围：CMake（vcpkg port `boost-asio`、`boost-beast` 或独立 `asio`；导出 target 如 `Boost::asio` / `Boost::beast` 或 `asio::asio`）。

## 1. 适用场景与选型边界

- **何时选用**：需要完全掌控 TCP/UDP/串口、自定义二进制帧协议、高性能 HTTP/WebSocket 客户端/服务端，或配合 C++20 协程（`asio::awaitable`）构建无外部重型框架依赖的网络层。
- **何时避免 / 替代方案**：开发标准 REST/JSON Web 业务服务且需要路由/中间件/ORM 一体化时优先选 [Drogon](drogon.md) 或 [轻量 HTTP 服务](cpp-http-lightweight.md)；Qt 桌面客户端普通 HTTP 请求优先选 [Qt 网络客户端](qt-network-client.md)。

## 2. 构建与接入

- Windows 下编译 Boost.Asio 必须显式传入目标系统版本宏（如 `_WIN32_WINNT=0x0A00`）以消除构建警告与旧版 Winsock 分支差异；使用 TLS（`asio::ssl::stream`）时还需链接 `OpenSSL::SSL` 与 `OpenSSL::Crypto`。
- 独立版 `asio` 需定义 `ASIO_STANDALONE`（CMake `asio::asio` 通常已自动传播），禁止在同一目标同时混用独立 `asio` 与 `boost::asio` 头文件。

## 3. 高频踩坑（反模式 vs 正解）

1. **同一 socket 并发调用 `async_write` 导致数据交错与未定义行为**：`asio::async_write` 内部会拆分成多次 `async_write_some`，在上一笔写完成前再次调用 `async_write` 会把两帧字节流混在一起。必须通过每连接独立的写队列 + 串行 `strand` 保证同一时刻只有 1 个在途 `async_write`。
2. **对象已析构而异步回调仍触发（悬空 `this`）**：所有长生命周期异步会话继承 `std::enable_shared_from_this<Session>`，回调捕获 `self = shared_from_this()`；外部关闭时投递到同一 `strand` 再取消 socket，不要直接从另一线程硬 `delete`。
3. **`io_context::run()` 提前返回或退出时永久阻塞**：空载常驻循环使用 `asio::make_work_guard(ioContext)`；退出时按顺序「停止接收新连接 → `workGuard.reset()` → 关闭活动 socket/定时器 → `join()` 工作线程」，避免直接 `ioContext.stop()` 粗暴丢弃半截资源清理。
4. **Boost.Beast 缓冲区与连接复用坑点**：
   - `beast::flat_buffer` 应在同一个 keep-alive 连接的多次 `http::async_read` 间复用，不可每次读完就新建临时 buffer 丢弃已预读的下个请求首部。
   - 回复前必须显式设置 `res.keep_alive(req.keep_alive())`；HTTP/1.1 短连接读到 `http::error::end_of_stream` 是正常关闭，勿当成系统异常报错。
   - `asio::ssl::stream` 退出前执行 `async_shutdown`，部分对端直接断开 TCP 会返回 `asio::ssl::error::stream_truncated`（`short read`），应按正常截断关闭处理而非致命异常。

```cpp
class TcpSession : public std::enable_shared_from_this<TcpSession> {
public:
    explicit TcpSession(boost::asio::ip::tcp::socket socket)
        : m_strand(boost::asio::make_strand(socket.get_executor())),
          m_socket(std::move(socket)) {}

    bool enqueueSend(std::string payload) {
        if (payload.size() > kMaxFrameBytes) {
            return false;
        }
        boost::asio::post(
            m_strand, [self = shared_from_this(), data = std::move(payload)]() mutable {
                if (self->m_closed) {
                    return;
                }
                if (self->m_writeQueue.size() >= kMaxPendingFrames) {
                    // 超出每连接发送高水位：标记关闭并停用 socket，仅丢弃未发送的尾部队列
                    // 切勿在 async_write 在途时销毁 m_writeQueue.front()（Windows IOCP / reactor UAF），
                    // 留待写完成回调统一清理队首缓冲
                    self->m_closed = true;
                    boost::system::error_code ignored;
                    self->m_socket.close(ignored);
                    while (self->m_writeQueue.size() > 1) {
                        self->m_writeQueue.pop_back();
                    }
                    return;
                }
                const bool writeInFlight = !self->m_writeQueue.empty();
                self->m_writeQueue.push_back(std::move(data));
                if (!writeInFlight) {
                    self->doWriteNext();
                }
            });
        return true;
    }

private:
    static constexpr std::size_t kMaxFrameBytes = 1024 * 1024;
    static constexpr std::size_t kMaxPendingFrames = 256;
    void doWriteNext() {
        boost::asio::async_write(
            m_socket,
            boost::asio::buffer(m_writeQueue.front()),
            boost::asio::bind_executor(
                m_strand,
                [self = shared_from_this()](boost::system::error_code ec, std::size_t) {
                    if (ec || self->m_closed) {
                        self->m_closed = true;
                        self->m_writeQueue.clear();
                        return;
                    }
                    if (!self->m_writeQueue.empty()) {
                        self->m_writeQueue.pop_front();
                    }
                    if (!self->m_writeQueue.empty()) {
                        self->doWriteNext();
                    }
                }));
    }

    boost::asio::strand<boost::asio::any_io_executor> m_strand;
    boost::asio::ip::tcp::socket m_socket;
    std::deque<std::string> m_writeQueue;
    bool m_closed = false;
};
```

## 4. 验证要点

- 开启 **TSan / ASan**（见 [验证与质量门禁](../workflow/verification-and-quality.md)）压测：并发发送大量分片帧 + 客户端中途断连 + 服务端带在途写队列优雅关闭，确认无数据错乱、无内存泄漏且工作线程正常退出。
