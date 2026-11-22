# Python 绑定规范（nanobind / pybind11 / C ABI）

适用范围：CMake + `scikit-build-core`（新项目推荐 `nanobind`；存量项目沿用 `pybind11` 或纯 C ABI `ctypes`/`cffi`）。

## 1. 选型与构建接入

| 方案 | 适用场景 | 打包工具链 |
| --- | --- | --- |
| **`nanobind`** | 新建 C++17+ Python 扩展；体积小、编译快、一流支持 `ndarray`/Buffer 协议及 Python 3.12+ 稳定 ABI | `scikit-build-core` + CMake (`nanobind_add_module`) |
| **`pybind11`** | 已有 `pybind11` 生态、需复杂 STL/多重继承特性或兼容旧工具链 | `scikit-build-core` 或 `vcpkg`/`find_package(pybind11)` |
| **纯 C ABI (`ctypes`/`cffi`)** | C++ 动态库已对外稳定发布、需彻底隔离 STL 与编译器 CRT ABI | 标准共享库导出宏（见 [C++ ABI 边界](../workflow/cpp-standards-and-abi.md)） |

- Python 包通过 `pyproject.toml` 声明 `[build-system] build-backend = "scikit_build_core.build"`。若当前激活虚拟环境已预装 `scikit-build-core`、`nanobind`/`pybind11`、`cmake` 与 `ninja`（如离线构建），可用 `pip install --no-build-isolation -e .` 加速本地开发联调；否则使用标准隔离构建 `pip install -e .`（或 `uv pip install -e .`），确保 CMake target 名字与 Python `import` 模块名一致。

## 2. 高频踩坑（GIL、零拷贝与异常边界）

1. **阻塞运算不释放 GIL**：耗时的 C++ 算法或网络/磁盘 I/O 若不释放 GIL，会冻结整个 Python 进程的其他线程甚至导致死锁。**但在释放 GIL 区间绝不可访问任何 `nb::object`/`py::object` 或 Python 回调函数**，触碰前必须重新获取 GIL。

```cpp
// nanobind 示例：输入转换完立刻释放 GIL，纯 C++ 计算结束后再返回 Python
double computeMean(
    nb::ndarray<nb::numpy, const double, nb::c_contig> data) {
    const double* ptr = data.data();
    const std::size_t count = data.size();
    double result = 0.0;
    {
        nb::gil_scoped_release release;
        result = computeMeanOnPureCpp(ptr, count);
    }
    return result;
}
```

2. **零拷贝返回值的悬空指针**：向 Python 返回借用 C++ 内部缓冲区的视图（`ndarray` 或指针引用）时，必须通过 `nb::capsule`（或 `rv_policy::reference_internal` / `py::keep_alive`）绑定底层 C++ 对象生命周期，防止 C++ 对象被释放后 NumPy 读取野指针。
3. **跨边界异常崩溃**：禁止让未捕获的异常或 `std::terminate` 穿过 C ABI 边界；C++ 异常由绑定层映射为明确的 `ValueError` / `RuntimeError` / 自定义 Python 异常，C ABI 则返回错误码并通过配套字符串接口获取错误信息。
4. **Windows DLL 搜索路径变化（Python 3.8+）**：Python 3.8+ 在 Windows 不再从 `PATH` 自动加载扩展模块依赖的第三方 DLL（如 OpenCV、Qt、OpenSSL）。必须随包安装同目录并在 `__init__.py` 调用 `os.add_dll_directory(...)` 或通过 `delvewheel` 打包。

## 3. 验证要点

- C++ 核心跑 GoogleTest；Python 侧用 `pytest` 验证：模块导入、正确值与零拷贝修改语义、异常类型转换、多线程释放 GIL 并发运行、非编辑模式打包（`pip wheel` + 干净虚拟环境安装导入）以及 Linux `auditwheel` / macOS `delocate` / Windows `delvewheel` 依赖检查。
