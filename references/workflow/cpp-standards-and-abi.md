# C++ 编码、命名、注释规范与跨库 ABI 边界

存量工程优先遵守项目根/目标目录下的 `AGENTS.md`、`.clang-format`、`.clang-tidy`、`.editorconfig` 及邻近源码风格；禁止对未修改的存量文件做全盘重格式化。以下规范适用于新工程及工程未作约定的新增代码。

## 1. 格式、文件组织与命名规范

直接复用配套模板：[`.clang-format`](../../assets/templates/.clang-format) · [`.clang-tidy`](../../assets/templates/.clang-tidy) · [`.editorconfig`](../../assets/templates/.editorconfig)。

### 格式与头文件组织
- **排版基线**：UTF-8（无 BOM）、LF 行尾、4 空格缩进、大括号同行（`Attach`）、100 列行宽、指针/引用靠左（`int* ptr`、`const T& ref`）。
- **头文件自包含与顺序**：使用 `#pragma once`（纯 C 头文件或特殊要求可用唯一宏保护）；`.cpp` 第一行先 `#include` 自身对应头文件，随后依次按「本项目头文件 → 第三方库头文件 → C++ 标准库头文件」（或项目既有固定顺序）分组空行隔开；禁止头文件出现全局 `using namespace`。
- **文件命名与大小写**：
  - 新纯 C++ 工程推荐 **`snake_case`**（如 `note_repository.hpp` / `note_repository.cpp`），与目录及命名空间保持一致，彻底避免 Windows/Linux 大小写敏感引发的编译差异。
  - 若接手 Qt 或存量 `PascalCase` 文件命名仓库（如 `MainWindow.h` / `MainWindow.cpp`），沿用既有风格。
  - C++ 头文件首选 `.hpp`（Qt QObject 或 C ABI 公共头可用 `.h`）；`#include` 路径必须与磁盘实际大小写完全一致。

### 完整命名表（已同步至 `.clang-tidy` 模板）

| 实体 | 规则 | 示例 |
| --- | --- | --- |
| 类、结构体、枚举、`using` 别名、`enum class` 值、模板参数 | `PascalCase` | `NoteRepository`、`SaveError::MissingTitle` |
| 函数、方法、参数、局部变量（含局部 `const`） | `camelCase` | `saveNote()`、`requestId`、`const auto itemCount = ...` |
| 私有 / 受保护成员变量 | `m_` + `camelCase` | `m_databasePath`、`m_sourceEdit` |
| 全局 / 静态 / 类内常量（`constexpr` / `static const`） | `k` + `PascalCase` | `kMaxTitleLength`、`kDefaultTimeoutMs` |
| 命名空间、模块目录、CMake target | `snake_case` | `notes::storage`、`notes_core` |
| 预处理器宏（仅限导出/平台开关，优先 `constexpr`） | `PROJECT_UPPER_SNAKE` | `NOTES_CORE_API` |
| 易歧义物理量 / 时间量 | 尾部显式单位后缀 | `timeoutMs`、`retryDelayMs`、`maxPayloadBytes` |

## 2. 注释与文档规范

- **跨组件公开接口（头文件 / 公共类与函数）**：使用 **`///` Doxygen 风格**描述调用契约，按实际需要说明：一句话意图、`@param`、`@return`、指针/视图所有权与生命周期要求、线程归属或锁要求、以及可返回错误码或抛出的异常。

```cpp
/// @brief 持久化保存笔记记录并更新索引。
/// @param note 待保存的业务实体；title 不能为空。
/// @param timeoutMs 数据库锁等待上限（毫秒），须大于 0。
/// @return 成功返回已提交版本号；失败返回显式错误码，不抛出异常。
/// @note 非线程安全；调用方需在同一服务线程执行，且不得在持外部锁期间调用。
SaveResult saveNote(const Note& note, int timeoutMs);
```

- **实现注释（`.cpp` 内）**：只解释 **“为什么这样做”**（业务边界、加锁顺序、协议历史兼容原因、时间复杂度或平台坑），严禁写 `// 循环遍历列表` 这类复述语法的废话注释。
- **同步与清洁纪律**：
  - 注释语言（中文或英文）与目标项目保持一致；修改函数行为或前置条件时必须同步更新对应注释。
  - **严禁提交大段被注释掉的死代码**（用 Git 历史保留）。
- **可追踪待办标记**：只允许带责任方/任务号和明确条件的格式：`// TODO(alice, #142): 在迁移到 Qt 6.8 后移除兼容分支`，禁止写无头无尾的 `// TODO: fix later`。

## 3. 跨语言代码风格基线（`C++ + Web` / `C++ + Python`）

全栈仓库中非 C++ 部分同样优先遵守项目已有 linter/formatter，新工程默认基线如下：
- **Web（TypeScript / React / Vue）**：`.editorconfig` 默认 2 空格缩进；启用 `TypeScript strict: true` + `ESLint` + `Prettier`；组件/类型用 `PascalCase`，变量/函数/Hooks 用 `camelCase`；对外共享工具函数使用 JSDoc。
- **Python（绑定测试 / FastAPI 服务）**：遵循 PEP 8（4 空格缩进）+ `Ruff` 格式化/检查 + 强制 Type Hints（`mypy` / `pyright`）；模块与函数用 `snake_case`，类用 `PascalCase`；对外接口使用 Google/NumPy 风格 docstring 写明参数、异常及是否会释放 GIL。

## 4. 多组件动态库与 ABI 边界（Windows / Linux / macOS）

全栈工程拆分共享库（如 `core.dll` / `libcore.so` 供桌面端或 Python 绑定调用）时，必须严守以下 ABI 规则：

1. **显式符号导出（严禁裸靠全局导出兜底）**：
   - 使用 CMake `include(GenerateExportHeader)` 生成 `<mod>_export.h` 并标注 `MOD_API`（Windows 展开为 `__declspec(dllexport)` / `__declspec(dllimport)`，Unix 为 `__attribute__((visibility("default")))`）。
   - **不要**用 `CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS=ON` 长期替代导出宏：它无法正确处理静态/全局导出数据、部分模板实例化及精细符号隐藏。
   - 默认开启隐藏可见性：`set(CMAKE_CXX_VISIBILITY_PRESET hidden)` 与 `set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)`。
2. **禁止跨模块 CRT 边界混用堆分配与 STL 状态**：
   - 同进程内所有 C++ 目标必须统一编译器主版本、C++ 标准（如 C++20）、CRT 运行库链接方式（`/MD` vs `/MDd`；不可 Debug 库混链 Release 应用）及 `std` 迭代调试宏（`_ITERATOR_DEBUG_LEVEL`）。
   - 若动态库可能被不同 CRT 或语言（如 Python `ctypes`）加载，边界只暴露 **纯 C ABI** 或自带配对销毁函数（如 `create_handle()` / `destroy_handle()`），避免跨 DLL 传递或释放 `std::string` / `std::vector`。
3. **头文件依赖边界**：
   - 仅在公共头文件暴露的第三方类型才用 `target_link_libraries(<lib> PUBLIC <dep>)`；纯实现细节一律用 `PRIVATE` + Pimpl 或接口抽象隔离，减少全栈重编译和符号污染。
4. **Windows MSVC 源码编码**：
   - 含中文注释或字面量的跨平台源码，在 MSVC / `clang-cl` 目标显式添加 `target_compile_options(<tgt> PRIVATE $<$<CXX_COMPILER_FRONTEND_VARIANT:MSVC>:/utf-8>)`，防止本地代码页引发 `C4819` 截断或乱码。

## 5. 关联工程规范

涉及多线程同步、底层协议、模板设计或整体架构拆分时，按需加读：
- [并发编程规范](../engineering/concurrency.md)
- [网络编程规范](../engineering/networking.md)
- [泛型与模板规范](../engineering/generics.md)
- [项目管理、低耦合架构与设计模式](../engineering/architecture-and-project-management.md)
