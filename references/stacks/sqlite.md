# SQLite 规范

适用范围：直接使用 SQLite3 C API（CMake `SQLite::SQLite3`）或通过 Qt SQL `QSQLITE` 驱动。

## 1. 连接配置、并发与 `BEGIN IMMEDIATE`

- **每个新连接显式初始化（注意顺序）**：连接打开后**务必先设置等待超时**，再执行其他 PRAGMA（`busy_timeout` 与 `foreign_keys` 仅对当前连接有效；`journal_mode = WAL` 持久化在库文件头部但切换时需写锁）：
  - `PRAGMA busy_timeout = 5000;`（先设忙等待毫秒数，避免后续并发初始化或建 WAL 立刻返回 `SQLITE_BUSY`；勿设为 0）
  - `PRAGMA foreign_keys = ON;`（SQLite 默认关闭外键约束！）
  - `PRAGMA journal_mode = WAL;`（允许读并发且提高写入吞吐，但**同一时刻仍仅允许一个写者**）
- **写事务必须使用 `BEGIN IMMEDIATE`**（关键并发坑）：
  - SQLite 默认的 `BEGIN`（`DEFERRED`）在事务内先读后写时，会试图从读锁升级为写锁；若此时已有另一写者，SQLite **会直接忽略 `busy_timeout` 并立刻返回 `SQLITE_BUSY`** 以避免死锁！
  - 所有包含写入的事务显式用 `BEGIN IMMEDIATE`，使锁竞争在事务一开始就按 `busy_timeout` 排队等待。

## 2. 参数绑定、编码与 RAII

- 一律使用预编译语句（`sqlite3_prepare_v2` + `sqlite3_bind_*`），严禁字符串拼接 SQL。
- UTF-8 文本长度可能超过 `INT_MAX` 时用 `sqlite3_bind_text64` 或在转换 `int` 前做明确范围校验；注意默认构造的空 `std::string_view{}` 可能满足 `data() == nullptr`，而 `sqlite3_bind_text` 遇到 `nullptr` 指针会将其绑定为 **SQL `NULL` 而非空字符串 `""`**，传入文本时请写 `title.empty() ? "" : title.data()`。通过 `std::unique_ptr<sqlite3_stmt, decltype(&sqlite3_finalize)>` 确保所有错误/提前返回路径自动销毁语句句柄，每一步检查返回码。

```cpp
sqlite3_stmt* rawStatement = nullptr;
int rc = sqlite3_prepare_v2(
    database, "INSERT INTO notes(title) VALUES(?)", -1, &rawStatement, nullptr);
if (rc != SQLITE_OK) {
    return makeDatabaseError(database);
}

const std::unique_ptr<sqlite3_stmt, decltype(&sqlite3_finalize)> statement(
    rawStatement, &sqlite3_finalize);
if (title.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
    return makePayloadTooLargeError();
}

rc = sqlite3_bind_text(
    statement.get(),
    1,
    title.empty() ? "" : title.data(),
    static_cast<int>(title.size()),
    SQLITE_TRANSIENT);
if (rc != SQLITE_OK) {
    return makeDatabaseError(database);
}

rc = sqlite3_step(statement.get());
if (rc != SQLITE_DONE) {
    return makeDatabaseError(database);
}
```

- **Qt SQL 线程归属**：`QSqlDatabase` 与其派生的所有 `QSqlQuery` 只能在创建该连接的同一线程使用；调用 `QSqlDatabase::removeDatabase()` 前必须确保所有引用该连接的 `QSqlQuery` 与 `QSqlDatabase` 局部对象已全部析构离开作用域。

## 3. 迁移与活库备份坑点

1. **误把 `:memory:` 当持久化库或路径含中文失败**：`:memory:` 每个独立连接各自拥有隔离库；Windows 路径传给 `sqlite3_open_v2` 必须为 UTF-8（不能传本地 ACP/GBK 编码）。
2. **拷贝活库丢数据**：WAL 模式下近期写入尚在 `-wal`/`-shm` 文件中，直接文件拷贝主 `.db` 文件会导致数据丢失或损坏。备份活库必须使用 SQLite Online Backup API（`sqlite3_backup_init`/`step`/`finish`）或 `VACUUM INTO '<safe-path>'`。
3. **迁移事务原子性**：DDL 与 `PRAGMA user_version`（或版本表）放在同一事务更新，迁移失败回滚后确认版本号未提前递增。

## 4. 验证要点

- 用磁盘临时库（勿只测 `:memory:`）覆盖：增删改查后关闭重开验证落盘、双独立连接并发写事务测试、旧版本库升级迁移与失败回滚，以及 `VACUUM INTO`/Backup API 导出后重新打开校验数据一致。
