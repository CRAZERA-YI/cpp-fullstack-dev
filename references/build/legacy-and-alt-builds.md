# 存量 Qt5/qmake 与非 vcpkg 构建适配

接手已有项目时，**沿用项目已经验证的构建工具链与命令**，不擅自把存量 qmake、Conan 或 Meson 工程强行改写成 vcpkg。

## 1. 存量 Qt5 / qmake 工程

### 工程维护要点
- **确认活动 kit**：构建前先核对 `qmake -v` 输出的 Qt 版本与编译器（Windows 下区分 MSVC 与 MinGW kit，不可混链），优先复用项目已有 Qt Creator kit 或已初始化终端。
- **文件与模块同步**：新增/移动含 `Q_OBJECT` 的头文件、`.cpp`、`.ui` 或 `.qrc` 时，核对 `.pro` / `.pri` 中的 `HEADERS`、`SOURCES`、`FORMS`、`RESOURCES` 与 `QT +=` 模块是否同步更新。
- **强制执行 `.pro` 变更**：修改 `.pro` / `.pri` 后必须在独立构建目录重新运行 `qmake`，再调用 `nmake` / `jom`（MSVC）或 `mingw32-make` / `make`；切换 kit 时新建独立构建目录。
- **编码与版本门槛**：MSVC 下遇到中文注释/字面量触发 `C4819`，在 `.pro` 添加 `msvc: QMAKE_CXXFLAGS += /utf-8`；需要限定最低 Qt 版本时在 `.pro` 用 `lessThan(QT_MAJOR_VERSION, 5)` + `error()` 做硬约束。

### qmake 高频排错

| 现象 | 先查什么 |
| --- | --- |
| `metaObject` / `qt_metacall` / `vtable` 未解析 | 含 `Q_OBJECT` 的头文件是否列在 `HEADERS` 中、修改后是否重新跑了 `qmake`、槽函数是否缺少实现。 |
| `LNK2019` 符号缺失 | 检查 `.pro` 的 `LIBS +=` 与架构/Debug/Release 配置是否匹配活动 Qt kit。 |
| 开发机能运行、干净机缺 DLL | 用 [Windows 部署指南](platforms/windows.md) 核对所用 Qt kit 的 `windeployqt` 与 MSVC Runtime。 |

## 2. 非 vcpkg 依赖体系适配

| 构建/包管理体系 | 接入与运行要点 | 常见陷阱 |
| --- | --- | --- |
| **Conan 2** (`conanfile.txt` / `.py`) | 先 `conan install . --output-folder=build --build=missing`，再通过 `-DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake` 或生成的 `CMakeUserPresets.json` 触发 CMake。 | Conan profile（compiler/build_type/arch）必须与 CMake preset 一致；勿在未传 `conan_toolchain.cmake` 时直接 `cmake`。 |
| **CMake `FetchContent`** | 在 `CMakeLists.txt` 固定确切 `GIT_TAG`（优先 commit SHA 或校验和 `URL_HASH`），不可跟踪浮动分支（如 `main`）。 | 离线或 CI 缓存环境需配合 `FETCHCONTENT_SOURCE_DIR_<PKG>` 或启用本地缓存，防止每次干净构建重复克隆全量仓库。 |
| **系统包 / `pkg-config`** | Linux/macOS 借助发行版包或 Homebrew 时，核对 `FindPkgConfig` 与头文件/运行库版本一致，记录发行版包名。 | 跨机交付时不可默认目标机已装同版本 `-dev` 包；动态库版本校验见 [Linux 部署](platforms/linux.md)。 |
| **Meson** (`meson.build`) | 遵循 `meson setup <builddir>` → `meson compile -C <builddir>` → `meson test -C <builddir>`。 | 与 C++ 编码规范一样保证 `buildtype`、警告与 Sanitizer（`-Db_sanitize=address,undefined`）独立构建目录。 |
