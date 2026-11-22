# 桌面 HTTP / WebSocket 客户端规范

适用于 `C++ + Qt` 桌面客户端（首选 `QNetworkAccessManager`）及不依赖 Qt 的纯 C++ SDK 客户端（`libcurl` / `cpr`）。

## 1. `QNetworkAccessManager` 核心模式

- **每线程/每服务长生命周期单实例复用（而非全局可变单例），禁止每次请求都 `new QNetworkAccessManager`**：`QNetworkAccessManager` 内部维护 TCP 连接池、TLS 会话缓存与代理状态，应当在所属客户端/服务上下文生命周期内每线程复用单个实例（参见 [架构与项目管理](../engineering/architecture-and-project-management.md)）。
- **跨线程禁止**：`QNetworkAccessManager` 及其创建的 `QNetworkReply*` 必须在其所属线程使用，不可跨线程调用 `get()`/`post()` 或直接读取 `reply`。

```cpp
void ApiClient::fetchNote(const QString& noteId, int generation) {
    QNetworkRequest request(buildUrl(noteId));
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    request.setTransferTimeout(kDefaultRequestTimeoutMs); // 需 Qt 5.15+

    QNetworkReply* reply = m_networkManager->get(request);
    m_activeReplies.insert(reply);

    connect(reply, &QNetworkReply::finished, this, [this, reply, generation]() {
        m_activeReplies.remove(reply);
        const auto guard = qScopeGuard([reply]() { reply->deleteLater(); });

        if (generation != m_currentGeneration) {
            return;
        }
        if (reply->error() != QNetworkReply::NoError) {
            emit requestFailed(mapNetworkError(reply));
            return;
        }
        emit noteLoaded(reply->readAll());
    });
}
```

## 2. 高频踩坑（反模式 vs 正解）

1. **内存泄漏 `QNetworkReply`**：`finished` 槽函数所有分支都必须调用 `reply->deleteLater()`（如上例用 `qScopeGuard` 兜底，但绝不要用 `delete reply` 同步删除）。
2. **无超时与析构取消迭代器失效**：
   - `setTransferTimeout()` 需 **Qt 5.15+**（早期 Qt5 需配合单次 `QTimer` 调用 `reply->abort()`）。
   - `QNetworkReply::abort()` 会在当前线程**同步发射 `finished` 信号**，直接重入槽函数并修改 `m_activeReplies`！在析构或关闭窗口清理在途请求时**严禁直接遍历 `m_activeReplies` 调用 `abort()`**（会导致迭代器失效并在 `~ApiClient()` 阶段误发射信号）。正确做法是先转移副本、递增 `m_currentGeneration` 并断开连接再中止：

```cpp
void ApiClient::cancelAllReplies() {
    ++m_currentGeneration;
    const auto replies = std::exchange(m_activeReplies, {});
    for (QNetworkReply* reply : replies) {
        if (!reply) {
            continue;
        }
        disconnect(reply, nullptr, this, nullptr);
        reply->abort();
        reply->deleteLater();
    }
}
```
3. **TLS / OpenSSL DLL 失配（Windows 最高频故障）**：
   - Qt 5 默认依赖 OpenSSL 1.1.x（`libssl-1_1-x64.dll` / `libcrypto-1_1-x64.dll`）；Qt 6 默认支持 OpenSSL 3.x 或 Windows Schannel backend。
   - **禁止忽略证书错误**：严禁全局屏蔽 `sslErrors`（`ignoreSslErrors()` 仅限明确受控的本地测试/自签证书固定指纹场景）。
   - 部署后先用 `QSslSocket::supportsSsl()` 与 `QSslSocket::sslLibraryBuildVersionString()` 核对目标机运行时实际加载的 TLS 后端。
4. **重复提交与状态映射**：非幂等写入（POST）在网络超时后不可盲目自动重试；界面收到错误时区分「校验错误 (400/422) / 认证过期 (401) / 服务端故障 (5xx) / 连接或超时」。

## 3. UI 无关纯 C++ 客户端（`libcurl` / `cpr`）

当核心 SDK 需要同时被 CLI、Python 绑定和 Qt 共用时，可用 `libcurl` 或 `cpr`：
- 进程初始化/结束配对 `curl_global_init` / `curl_global_cleanup`；多线程共用连接池时按 `CURLSH` 规则加锁，不得跨线程共享同一 `CURL*` easy handle。
- 与 Qt 相同：所有请求必设 `CURLOPT_CONNECTTIMEOUT_MS` 与 `CURLOPT_TIMEOUT_MS`，并挂载进度回调实现即时取消。
