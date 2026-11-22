# Qt Widgets 规范

适用范围：Qt5 / Qt6 · CMake 或存量 qmake（qmake 工程构建见 [qmake 与其他构建](../build/legacy-and-alt-builds.md)）。

## 1. 构建接入与分层

- **最小模块链接**：按主版本仅链接实际用到的模块（如 `Qt6::Widgets`、`Qt5::Widgets`），不要默认引入 `Network` / `Sql`；包含 `Q_OBJECT` / `.ui` / `.qrc` 的 CMake target 开启 `AUTOMOC` / `AUTOUIC` / `AUTORCC`。
- **三层隔离**：
  - **View (`QWidget` / `QMainWindow`)**：创建控件、管理布局，通过语义信号（如 `saveRequested()`）发出意图。
  - **Controller / Presenter**：装配窗口与后台服务，管理取消令牌与结果回写。
  - **Service / Model**：纯 C++ 或 `QtCore` 数据模型，不反向依赖 `QWidget`。
- **界面文案与编码**：所有用户可见文案使用 `tr()`；外部字节流显式指定编码（`QString::fromUtf8` 等）；旧版 Qt5 代码仅在最低支持版本确认可用且行为等价时替换 `QRegExp` / `Q_FOREACH`。

## 2. 高频踩坑（反模式 vs 正解）

1. **老式 `SIGNAL/SLOT` 字符串连接与信号槽重复连接泄漏**：
   - 一律使用函数指针语法连接信号槽（重载先用 `qOverload` 明确签名）。
   - 连接 lambda 时必须传入接收端 `QObject` 上下文，并检查 `connect()` 返回值；需要观测非拥有 `QObject` 时用 `QPointer`。
   - **禁止在每次用户操作里对长期复用的 `m_worker` 重复 `connect()`**：会叠加多条永久连接导致同一事件重复触发多次回调。复用成员 worker 应在构造函数只连接一次并由信号携带 `generation`；若确为单次请求绑局部上下文，必须使用一次性任务对象（完成后 `deleteLater`）或 Qt 6 `Qt::SingleShotConnection`。

```cpp
// 在构造函数中仅连接一次复用成员 m_worker，通过信号携带 generation 过滤过期结果
const auto connection = connect(
    m_worker, &Worker::finished, this,
    [this](int generation, const SaveResult& result) {
        if (generation != m_activeGeneration) {
            return;
        }
        showSaveResult(result);
    },
    Qt::QueuedConnection);
if (!connection) {
    handleConnectionFailure();
}
```

2. **工作线程直接操作 `QWidget`**：任何 `QWidget` 的创建、修改与销毁只能在 GUI 主线程执行；跨线程使用自定义类型传递 `QueuedConnection` 信号时，确认已在所用 Qt 版本注册元类型（`Q_DECLARE_METATYPE` + `qRegisterMetaType`）。
3. **跨线程提前析构 `QObject` 与多所有权**：每个 `QObject` 只保留单一所有权（Qt 父对象树 或 `std::unique_ptr`，不可混管）；关闭窗口时先取消或等待后台任务，再结束事件循环；跨线程或当前正在派发事件的 `QObject` 释放用 `deleteLater()`。
4. **保存半成品损坏配置文件**：本地关键文件保存用 `QSaveFile`，检查 `open()`、写入与 `commit()` 返回值，失败时保留原文件并向用户报告路径与可恢复动作。

## 3. 验证要点

- 覆盖正常路径、重复点击、异步慢返回前切换选中项/关闭窗口（验证不崩溃且旧结果不覆盖新状态）、错误恢复提示及键盘焦点。
