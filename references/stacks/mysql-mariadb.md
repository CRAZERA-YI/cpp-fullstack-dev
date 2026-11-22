# MySQL 与 MariaDB 规范

适用范围：CMake（`boost-mysql` 异步原生客户端、`mysql-connector-cpp`、`libmysqlclient` / `libmariadb` 或 Qt SQL `QMYSQL`）。

## 1. 适用场景与选型边界

- **何时选用**：对接既有 MySQL 8.x / MariaDB 业务库、阿里云/AWS RDS MySQL 或强要求使用 MySQL 生态的服务端项目。
- **客户端选型**：基于 `Boost.Asio` 协程/异步服务优先 **`Boost.MySQL`**（无阻塞、天然融合事件循环）；同步 C++ 服务用 **`libmysqlclient` / `libmariadb`（加 RAII 封装）** 或 `MySQL Connector/C++`；全栈新选型若无历史包袱，后端更推荐 [PostgreSQL & libpqxx](postgresql-libpqxx.md)。

## 2. 构建与接入

- **vcpkg port**：`boost-mysql`（导出 `Boost::mysql`）、`libmysql` 或 `libmariadb`。
- **Windows / Linux 动态部署**：`libmysql.dll` / `libmariadb.dll`（及所依赖的 OpenSSL 与认证插件如 `caching_sha2_password`）必须随安装包放进 staging 目录，Qt `QMYSQL` 驱动尤其容易因缺少匹配架构的 `libmysql.dll` 而加载失败。

## 3. 高频踩坑（反模式 vs 正解）

1. **误用 `utf8` 字符集导致中文生僻字与 Emoji 截断报错**：MySQL 历史上的 `utf8`（`utf8mb3`）最多只支持 3 字节 UTF-8！建表、连接串与握手初始化**一律显式指定 `utf8mb4`**（`SET NAMES utf8mb4` 或连接选项）。
2. **长连接被服务端 `wait_timeout` 静默掐断**：连接池闲置超过 MySQL `wait_timeout` 后，下次直接执行 SQL 会报 `CR_SERVER_GONE_ERROR` / `MySQL server has gone away`。连接池必须在归还/借出时做存活检测（轻量 ping 或超时淘汰）并在只读/幂等查询允许重建连接重连。
3. **预编译语句未绑定或参数类型漂移**：C API 使用 `MYSQL_STMT` 时，`MYSQL_BIND` 结构体数组及所指向的缓冲区必须在 `mysql_stmt_execute` 期间始终有效；每条语句结束释放 `mysql_stmt_close`。`Boost.MySQL` 则优先使用 `conn.prepare_statement` + `stmt.bind(...)`。
4. **并发死锁与 `REPEATABLE READ` 间隙锁**：MySQL InnoDB 默认隔离级别为 `REPEATABLE READ`，范围更新易产生 Gap Lock 死锁（错误码 `1213` / SQLSTATE `40001`）。遇到死锁按完整事务有限次退避重试，大批量变更分批提交。
5. **多线程初始化竞争**：使用传统 `libmysqlclient` 时，在创建工作线程前于主线程调用一次 `mysql_library_init(0, nullptr, nullptr)`；不要跨线程共享同一个 `MYSQL*` 连接对象。

## 4. 验证要点

- 连接真实 MySQL/MariaDB 实例测试：包含 4 字节 Emoji/UTF-8 生僻字读写往返、断网或主动 `KILL CONNECTION` 后连接池自动恢复、`NULL` 值与日期时区转换及并发事务死锁回滚无残留。
