# 全栈自动化测试规范

适用范围：GoogleTest（C++ 核心与集成）、Catch2（BDD/现代 C++ 轻量单测）、Google Benchmark（微基准性能测）、Qt Test（Qt 信号与界面）、`pytest`（`C++ + Python`）、CTest 统一编排。

## 1. 测试工具选型边界

- **GoogleTest (`GTest::gtest_main`)**：测纯 C++ 业务逻辑、数据结构、协议序列化、SQLite/PostgreSQL 数据层及 HTTP/gRPC 本地集成契约。
- **Catch2 (`Catch2::Catch2WithMain`)**：适合偏好 `TEST_CASE` + 嵌套 `SECTION` 树状隔离或轻量 BDD 风格（`SCENARIO`/`GIVEN`/`WHEN`/`THEN`）的纯 C++ 模块；`REQUIRE` 为致命断言，`CHECK` 记录后继续执行。注意每次进入新的最深层 `SECTION` 时外层局部变量都会重新构造，勿跨同级 `SECTION` 依赖可变全局状态；配合 `catch_discover_tests()` 注册 CTest。
- **Google Benchmark (`benchmark::benchmark` / `benchmark::benchmark_main`)**：用于量化解析、矩阵计算或零拷贝热点改动；**仅在 Release（关闭调试断言/Sanitizer）下跑基准**，用 `benchmark::DoNotOptimize(...)` 与 `benchmark::ClobberMemory()` 防止编译器把无副作用计算整段优化掉，并在对比前后关注稳定重复次数与方差，勿在 CI 共享嘈杂虚机把单次抖动当成回归门禁。
- **Qt Test (`Qt6::Test` / `Qt5::Test`)**：测 Qt 信号槽异步时序、`QAbstractItemModel`、控件交互状态与焦点。纯逻辑/模型用轻量入口（`QTEST_GUILESS_MAIN` / `QTEST_MAIN` 视模块而定），涉及 `QWidget` 必须使用支持 `QApplication` 的入口（`QTEST_MAIN`）。
- **`pytest`**：测 `C++ + Python` 绑定的导出行为、异常转换、GIL 多线程并发及独立 Wheel 安装，也可作为 `C++ + Web` 后端 API 端到端集成测试驱动。

## 2. GoogleTest 关键约束

- **`ASSERT_*` vs `EXPECT_*`**：前置条件失败会导致后续空指针/无效状态的用 `ASSERT_*`，其余独立校验用 `EXPECT_*`。**注意：工作线程中的 `ASSERT_*` 只会退出该工作线程的当前函数**，不会中断主测试线程；工作线程结果应带回测试线程断言。
- **RAII 隔离清理**：端口、临时数据库目录、子进程、环境变量修改一律用 RAII Fixture 管理，确保用例因 `ASSERT_*` 提前退出或抛异常时仍彻底清理。

```cpp
TEST(NotesRepositoryTest, RejectsMissingTitle) {
    TemporaryDatabase database;
    ASSERT_TRUE(database.open());

    NotesRepository repository(database.path());
    const auto result = repository.save(Note{});

    ASSERT_FALSE(result);
    EXPECT_EQ(result.errorCode(), SaveError::MissingTitle);
}
```

## 3. Qt Test 信号槽异步验证

- 先创建 `QSignalSpy` 并立即用 `QVERIFY(spy.isValid())` 校验连接有效，**再**触发被测操作；异步等待用带超时上限的 `QTRY_COMPARE` / `QTRY_COMPARE_WITH_TIMEOUT`（按项目 Qt 版本选用），严禁靠固定 `QTest::qWait(500)` 赌时序。

```cpp
QSignalSpy finishedSpy(&controller, &Controller::finished);
QVERIFY(finishedSpy.isValid());
controller.save();
QTRY_COMPARE_WITH_TIMEOUT(finishedSpy.count(), 1, 1000);
```

## 4. CTest 发现、并行隔离与防假绿

- 跑测试前先运行 `ctest --test-dir <build-dir> -N`（或配合 `--preset`），确认目标用例实际被发现（不因漏构建测试目标、动态库缺 PATH 导致 0 用例静默退出）。
- 允许并行执行（`ctest -j`）下不冲突：每个用例使用随机/OS 分配临时目录与临时端口；随机种子与临时路径失败时打印出来以供复现；永远不依赖测试用例执行顺序。
- 无头环境注记：Linux 下 `QT_QPA_PLATFORM=offscreen` 或 `xvfb-run` 仅证明该受限环境通过，窗口管理与缩放仍需按平台文档实测。
