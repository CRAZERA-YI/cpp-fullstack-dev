# DuckDB 与 Apache Arrow 规范

适用范围：CMake（`duckdb`、`Arrow::arrow_shared` / `Parquet::parquet_shared`）及 `C++ + Python` / `C++ + Qt` 本地数据分析。

## 1. 适用场景与选型边界

- **何时选用**：桌面端或混合架构内嵌高性能 OLAP 聚合分析、直接查询海量 Parquet / CSV / JSON 文件，或在 C++ 与 Python 间高效交换列式大数据集。
- **何时避免**：高并发在线短事务读写（OLTP）选 [PostgreSQL](postgresql-libpqxx.md) 或 [SQLite](sqlite.md)；多客户端同时向同一文件高频写入时勿直写单机 DuckDB 文件。

## 2. 构建与接入

- C++ 嵌入 DuckDB 链接 `duckdb`（注意静态与动态库符号体积较大，Release 下显式开启优化）；跨 Python（`duckdb` / `pyarrow` / `polars` / `pandas`）交换数据时优先使用 **Arrow C Data Interface**（`ArrowArray` / `ArrowSchema` 零拷贝指针协议），避免先序列化成 CSV/JSON 再反序列化。

## 3. 高频踩坑（反模式 vs 正解）

1. **多线程共享同一个 `duckdb::Connection`**：
   - `duckdb::DuckDB` 实例（database 对象）可多线程共享，但 **`duckdb::Connection` 不是线程安全的**！每个工作线程必须从同一 `DuckDB` 实例创建各自独立的 `Connection`，绝不跨线程共用同一连接发查询。
2. **文件数据库多进程写锁冲突**：
   - DuckDB 单文件同时只允许 **1 个写进程** 或多个只读进程（需传只读 `AccessMode::READ_ONLY` 打开）。两个进程以读写模式打开同一 `.duckdb` 文件会直接失败，应由单一后台写入或分文件归档。
3. **逐条 `INSERT` 极慢**：
   - 批量导入 C++ 内存数据严禁循环执行单行 `INSERT INTO ... VALUES (...)`；使用 **`duckdb::Appender`** 流式写入或直接扫描 Arrow / Parquet 批量导入，吞吐差数个数量级。
4. **未限制内存上限导致 OOM**：
   - 处理超出物理内存的大数据集时，初始化连接后显式配置 `SET memory_limit = '2GB'` 与 `SET temp_directory = '<writable-temp-dir>'` 开启磁盘溢写，并在结束或错误路径清理临时溢写目录。
5. **Arrow C Data Interface 所有权泄漏**：
   - 导出端填充的 `ArrowSchema` / `ArrowArray` 若未移交给消费端并由消费端调用 `release()` 回调，会导致整块缓冲区永久泄漏或二次释放崩溃。

## 4. 验证要点

- 覆盖：多线程各自持独立 `Connection` 并发读、`Appender` 大批量写入后持久化重开校验、超内存阈值查询溢写清理，以及与 Python `pyarrow`/`duckdb` 零拷贝往返与类型精度（时间戳/Decimal/NULL）核对。
