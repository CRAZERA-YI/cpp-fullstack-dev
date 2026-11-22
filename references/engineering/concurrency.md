# C++ 并发编程规范与陷阱

适用于标准 C++17/20 多线程、线程池、异步任务调度与跨线程状态共享。库级并发约束另见 [Boost.Asio](../stacks/boost-asio-beast.md)、[Qt Widgets](../stacks/qt-widgets.md) 与 [Python 绑定 GIL](../stacks/python-bindings.md)。

## 1. 锁纪律与死锁预防

- **多锁必须用 `std::scoped_lock`**：同时锁多个互斥量时，严禁分两行手写 `m1.lock(); m2.lock();`（加锁顺序颠倒即死锁），统一使用 `std::scoped_lock lock(m_a, m_b);`。
- **持锁区间绝不调用外部回调、虚函数或阻塞 I/O**：在持有 `std::mutex` 期间触发用户回调、发射 Qt 信号或等待网络/磁盘 I/O，极易造成锁重入死锁或拖垮所有等待线程；先在锁内拷贝/交换必要数据，解锁后再回调。
- **慎用 `std::shared_mutex`**：仅当读远多于写且临界区耗时非微秒级时考虑；高频写入下很多实现的 `shared_mutex` 存在写者饥饿或比普通 `std::mutex` 更高的原子争用开销，切勿凭直觉盲用。

## 2. 条件变量（`std::condition_variable`）

- **永远使用带谓词的 `wait` 重载**：`cv.wait(lock, [&] { return m_stopped || !m_queue.empty(); });` 防止虚假唤醒（spurious wakeup）或错过 `notify` 导致逻辑错乱。
- **先在锁保护下修改状态再通知**：变更条件变量依赖的共享状态必须在同一 `mutex` 保护下完成；不要先 `notify` 再改标志。区分单消费者唤醒（`notify_one`）与关闭广播（`notify_all`）。

```cpp
class BoundedTaskQueue {
public:
    explicit BoundedTaskQueue(std::size_t maxCapacity)
        : m_maxCapacity(maxCapacity > 0 ? maxCapacity : 1) {
        if (maxCapacity == 0) {
            throw std::invalid_argument("BoundedTaskQueue capacity must be > 0");
        }
    }

    bool push(Task task) {
        std::unique_lock<std::mutex> lock(m_mutex);
        m_notFullCv.wait(lock, [this]() {
            return m_stopped || m_queue.size() < m_maxCapacity;
        });
        if (m_stopped) {
            return false;
        }
        m_queue.push_back(std::move(task));
        lock.unlock();
        m_notEmptyCv.notify_one();
        return true;
    }

    std::optional<Task> pop() {
        std::unique_lock<std::mutex> lock(m_mutex);
        m_notEmptyCv.wait(lock, [this]() { return m_stopped || !m_queue.empty(); });
        if (m_queue.empty()) {
            return std::nullopt;
        }
        Task task = std::move(m_queue.front());
        m_queue.pop_front();
        lock.unlock();
        m_notFullCv.notify_one();
        return task;
    }

    void stop() {
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_stopped = true;
        }
        m_notEmptyCv.notify_all();
        m_notFullCv.notify_all();
    }

private:
    std::size_t m_maxCapacity = 0;
    std::mutex m_mutex;
    std::condition_variable m_notEmptyCv;
    std::condition_variable m_notFullCv;
    std::deque<Task> m_queue;
    bool m_stopped = false;
};
```

## 3. 原子操作、内存序与缓存行

- **默认使用 `std::memory_order_seq_cst`**：仅在性能分析确认原子操作成为瓶颈、且能严谨证明成对同步关系时，才降级为 `release` / `acquire`（单计数统计可用 `relaxed`）。禁止凭猜测写 `memory_order_consume` 或弱内存序。
- **绝不把 `volatile` 当作并发同步原语**：`volatile` 只禁止编译器寄存器缓存优化硬件 MMIO 访问，不提供原子性与跨核内存屏障（`std::atomic` 才是并发语义）。
- **警惕伪共享（False Sharing）**：多个高频写入的线程局部计数器或原子标志不要紧密排列在同一缓存行内。x86_64 缓存行为 64 字节，而 **Apple Silicon（`macos-arm64`）及部分 ARM64 处理器为 128 字节**；x86_64 可用 `alignas(64)`，跨平台（含 Apple Silicon）隔离建议直接用 `alignas(128)`（`std::hardware_destructive_interference_size` 在 GCC 12+ 默认会触发 `-Winterference-size` 警告且部分旧版 `libc++` 未实现，显式 `alignas(64)` / `alignas(128)` 更稳妥）。

## 4. 线程生命周期、异步与背压

- **优先 `std::jthread` + `std::stop_token`（C++20）**：C++17 下必须通过 RAII 包装保证析构先发停止信号再 `join()`，**严禁对仍访问全局/成员状态的 `std::thread` 调用裸 `detach()`**（程序退出析构静态对象时极易崩溃）。
- **`std::async` 陷阱**：必须显式传入 `std::launch::async`（默认策略可能延迟到 `get()` 才同步执行），且**绝不丢弃返回的 `std::future`**（临时 `future` 析构会原地阻塞等到任务结束，使并发退化成串行）。
- **任务队列必须有界**：线程池与消息生产者设容量上限及拒绝/等待策略，防止消费慢时内存无限膨胀。
- **C++20 协程（`co_await`）跨挂起点悬空陷阱**：协程参数与捕获变量若以引用（`const std::string&` / `std::string_view`）或临时 lambda 捕获传入，在首次 `co_await` 挂起后调用方栈帧与临时 lambda 对象即被销毁，恢复执行即触发 Use-After-Free！协程函数优先**按值传参**，**禁止把带捕获的临时 lambda 直接作为协程调用**（应改为命名成员/自由协程函数或显式按值传参），成员协程跨越挂起点前用 `shared_from_this()` 保活 `this`。

## 5. 验证要点

- 并发代码改动必须至少跑一次 **ThreadSanitizer (TSan)**（见 [验证与质量门禁](../workflow/verification-and-quality.md)），并重点测：满队列背压、并发入队/出队同时触发 `stop()` 退出以及异常退出时线程是否干净 `join`。
