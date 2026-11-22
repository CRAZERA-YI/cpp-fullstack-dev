# Windows 构建、调试与发布

## 1. 工具链与 ABI 规则

- **MSVC + Ninja（单配置）**：构建速度快，适合脚本化开发与 CI；**必须在已初始化 MSVC 环境的终端执行**。
- **Visual Studio 生成器（多配置）**：适合 IDE 与多配置切换；通过 `buildPresets` / `--config Debug|Release` 区分配置。
- **MinGW**：仅当工程与所有第三方/Qt 依赖均为同一 MinGW ABI 时使用，严禁与 MSVC 编译的 `.lib`/`.dll` 混链。
- **绝对禁止混链**：Debug 与 Release CRT（`/MDd` vs `/MD`）、`x86` 与 `x64`、不同 MSVC 不兼容运行库或不同 Qt kit 不可混在同一个二进制内。

## 2. PowerShell 下激活 MSVC 构建环境

在普通 PowerShell 会话使用 `Ninja + cl.exe` 前，先用 `python <skill_dir>/scripts/probe_env.py` 查看 `visualStudio.installations` 中的 `vcvars64` 或 `vsDevCmd` 路径；若 `cl.exe` 不在当前 `PATH`，在执行 CMake 的同一条命令链内注入环境变量（或通过 `cmd /c` 串联调用）：

```powershell
# 示例：用 cmd /c 将 vcvars64 环境继承给同一次 cmake/ctest 调用（路径以 probe_env.py 实测为准）
# 若使用 VS 内置 vcpkg（bundledVcpkg），须显式设置 VCPKG_ROOT（vcvars64.bat 只把 vcpkg 加入 PATH，不会设置 VCPKG_ROOT）
$env:VCPKG_ROOT = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\vcpkg"
$vcvars = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
cmd /c "call `"$vcvars`" && cmake --preset windows-msvc-ninja-debug && cmake --build --preset windows-msvc-ninja-debug && ctest --preset windows-msvc-ninja-debug --output-on-failure"
```

注意：每条工具调用是独立进程，使用 Visual Studio 多配置生成器（`windows-vs2022`）通常无需手调 `vcvars64.bat`，但使用 `Ninja` 生成器时必须在同一命令中初始化 MSVC 环境。

## 3. Staging Tree 安装与 Qt 部署

正式发布产物从 Release 构建安装到独立目录（不要在 build tree 里直接分发）：

```powershell
# 单配置 Ninja（无 --config）；Visual Studio 生成器在 install 后加 --config Release
cmake --install out/build/windows-msvc-ninja-release --prefix out/stage

# Qt Widgets 应用：
windeployqt --release out/stage/bin/<app>.exe

# Qt Quick (QML) 应用必须传 --qmldir，否则 QML 模块与插件会被漏掉：
windeployqt --release --qmldir <source-qml-dir> out/stage/bin/<app>.exe
```

- **Qt 6 现代方式**：新 Qt 6 CMake 工程推荐直接集成 `qt_generate_deploy_app_script()` 或 `qt_generate_deploy_qml_app_script()` 到 `install(SCRIPT ...)`，让 `cmake --install` 自动完成部署。
- **第三方与系统运行库**：`windeployqt` 不会自动替你打包所有非 Qt 第三方 DLL（如 OpenSSL `libssl-3-x64.dll` / `libcrypto-3-x64.dll`、`libpqxx`/`libpq` 等）或脱离构建机时的 MSVC Redistributable（`vcruntime140.dll` / `msvcp140.dll`），需核对 `install()` 规则与分发清单。

## 4. 故障诊断与发布前验收

| 症状 | 定位方法 |
| --- | --- |
| `cl.exe` 找不到或 CMake 报编译器未知 | 用 `probe_env.py` 定位 `vcvars64.bat`，确认与 Ninja 同进程执行。 |
| VS 内置 vcpkg 获取 baseline 或拉取 MSYS2 404 | VS 内置 `VC\vcpkg` 无 `.git`，优先用 `vcpkg x-update-baseline --add-initial-baseline` 或读取 `vcpkg-bundle.json`；若需向 vcpkg 端口构建透传宿主机环境变量（如本地 `PKG_CONFIG`），须同时设置 `VCPKG_KEEP_ENV_VARS=PKG_CONFIG`。 |
| `LNK2038` runtime / iterator debug mismatch | 检查是否混用了 Debug 与 Release 库，或 vcpkg triplet 与 CMake 配置不一致。 |
| 开发机可启动，干净机提示缺 DLL | 用 `dumpbin /DEPENDENTS out\stage\bin\<app>.exe` 核对所有非系统依赖 DLL，并清掉开发机 `PATH` 后从 `out/stage` 启动。 |
| Qt 启动报 `could not find the Qt platform plugin "windows"` | 检查 `out/stage/bin/platforms/qwindows.dll` 是否与主程序 Qt 主次版本一致；临时设置 `$env:QT_DEBUG_PLUGINS="1"` 启动排查后记得清除。 |

- **路径兼容测试**：Release 程序在含 **中文字符与空格** 的路径下（安装路径、数据库路径、导入导出文件名）至少实测一次启动、读写与关闭；注意 Windows 下 `std::filesystem::path(narrowStdString)` 按系统本地代码页（ACP）而非 UTF-8 解析，从 UTF-8 字符串（如 HTTP URL 解码或 JSON 字段）构造路径时应经由 `std::u8string` / `char8_t` 转换。
