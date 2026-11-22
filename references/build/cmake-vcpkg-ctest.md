# CMake、vcpkg 与 CTest 指南

新工程默认使用 **CMake（>= 3.23）+ `CMakePresets.json` + vcpkg manifest（`vcpkg.json`）+ CTest**。模板见 [`CMakeLists.txt`](../../assets/templates/CMakeLists.txt)、[`CMakePresets.json`](../../assets/templates/CMakePresets.json) 与 [`vcpkg.json`](../../assets/templates/vcpkg.json)。

## 1. 核心约定

- **Preset 与环境隔离**：提交的 `CMakePresets.json` 使用 `$env{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake`，严禁写入开发机绝对路径；本机 Qt SDK 等私有路径放进 Git 忽略的 `CMakeUserPresets.json`。不同编译器、架构、Qt 版本或 Sanitizer 配置必须使用独立 `binaryDir`。
- **编译缓存加速**：大型 C++ 工程或 CI 可在配置期传入 `-DCMAKE_C_COMPILER_LAUNCHER=sccache` / `ccache` 与 `-DCMAKE_CXX_COMPILER_LAUNCHER=sccache` / `ccache`（注意若启用预编译头 PCH 或 MSVC `/Zi`，需改用 `/Z7` 或 `sccache` 支持的模式）。
- **外部 Qt SDK 定位**：若 Qt 未通过 vcpkg 安装而由官方安装器提供，通过 `CMAKE_PREFIX_PATH` 或 `Qt6_DIR`/`Qt5_DIR` 指定，并核对 CMake 缓存确认未误捞取旧版本或其他编译器 ABI 的 Qt。
- **vcpkg manifest**：新工程将直接依赖、最小必要 `features` 与经验证的 `builtin-baseline`（40 位 Git commit SHA，独立 Git 克隆版 vcpkg 可用 `git -C "$VCPKG_ROOT" rev-parse HEAD`；**Visual Studio 内置 `VC\vcpkg` 无 `.git` 目录**，优先运行 `vcpkg x-update-baseline --add-initial-baseline` 或读取 `$VCPKG_ROOT/vcpkg-bundle.json` 获取）写入 `vcpkg.json`。跨平台条件依赖使用 vcpkg `platform` 表达式，确保各支持平台依赖图均满足契约。
- **Target 与传递边界**：根 `CMakeLists.txt` 只设语言标准、全局选项与 `add_subdirectory`；每个目标声明自己的源码，公共头文件暴露的第三方类型用 `PUBLIC`/`INTERFACE`，内部实现一律用 `PRIVATE`。

## 2. 单配置（Ninja）vs 多配置（Visual Studio）命令差异

**严禁混用两者的 `--config` 行为**（与 [`CMakePresets.json`](../../assets/templates/CMakePresets.json) 严格对应）：

```text
# 1) 单配置生成器（Ninja：Debug/Release 在 configure 阶段由 CMAKE_BUILD_TYPE 决定，不要传 --config）
cmake --list-presets
cmake --preset windows-msvc-ninja-debug
cmake --build --preset windows-msvc-ninja-debug --target <target>
ctest --preset windows-msvc-ninja-debug --output-on-failure --no-tests=error

# 2) 多配置生成器（Visual Studio：一个 build tree 同时承载多配置，build/test preset 内置 configuration 或显式指定 --config）
cmake --preset windows-vs2022
cmake --build --preset windows-vs2022-debug
ctest --preset windows-vs2022-debug --output-on-failure --no-tests=error
```

- 旧版 CTest 若不支持 `--no-tests=error`，先运行 `ctest --test-dir <build-dir> -N` 确认预期测试数量非零后再执行。
- 目标测试或安装行为细节见对应平台指南：[Windows](platforms/windows.md) · [Linux](platforms/linux.md) · [macOS](platforms/macos.md)。

## 3. 增删依赖检查单

- **新增包**：确认 `vcpkg.json` 所需 `features` → 重新 configure 检查实际导出的 CMake imported target（如 `Drogon::Drogon`、`nlohmann_json::nlohmann_json`）→ 验证完整编译链接（仅 `find_package` 成功不代表链接通过）。
- **移除包**：从 `vcpkg.json` 与 `target_link_libraries` 删除 → 在干净或重配的构建树验证无残留链接依赖。

## 4. 高频配置与构建排错

| 现象 | 排查顺序 |
| --- | --- |
| `find_package` 找不到包 | 核对 `CMAKE_TOOLCHAIN_FILE` 是否指向 vcpkg、`VCPKG_ROOT` 是否存在、`VCPKG_TARGET_TRIPLET` 与 `vcpkg.json` 是否被当前 preset 命中。 |
| 包找到了但链接时报未解析符号 | 核对实际导入 target 名（区分大小写及命名空间前缀）、`PUBLIC`/`PRIVATE` 边界，以及 Debug/Release 或架构是否混用。 |
| 更新路径后仍命中旧 Qt | 检查 `CMakeCache.txt` 中的 `Qt6_DIR`/`Qt5_DIR` 与 `PATH`，切换 SDK 后删掉旧 `binaryDir` 或新建独立 preset。 |
| `ctest` 提示 `No tests were found` | 检查 `enable_testing()` 是否位于根 `CMakeLists.txt`、`gtest_discover_tests` 动态发现时运行期 DLL 是否在 `PATH`，用 `ctest -N` 定位；Windows 下 `BUILD_SHARED_LIBS=ON` 可用 CMake 3.21+ `POST_BUILD` 拷贝 `$<TARGET_RUNTIME_DLLS:<test_target>>` 到 `$<TARGET_FILE_DIR:<test_target>>`（或给测试设 `ENVIRONMENT_MODIFICATION` 追加 `PATH`）。 |
