# macOS 构建、Bundle 打包与发布

## 1. 架构切片与最低系统版本

- 通过 `CMAKE_OSX_ARCHITECTURES` 指定 `arm64`、`x86_64` 或双架构 Universal（`arm64;x86_64`），通过 `CMAKE_OSX_DEPLOYMENT_TARGET` 设定最低 macOS 版本；切换架构或最低系统版本必须使用独立 build tree。
- **Universal 二进制要求**：不仅主可执行文件，App Bundle 内携带的**每一个** `.dylib`、Qt framework 与插件都必须同时包含 `arm64` 与 `x86_64` 切片；用 `file <binary>` 或 `lipo -info <binary>` 逐一核查。

## 2. Mach-O 依赖修复与 Qt Bundle 部署

```sh
# 1. 安装生成 .app bundle 到 staging 目录
cmake --install out/build/macos-arm64-release --prefix out/stage

# 2. 部署 Qt frameworks 与插件（Qt Quick 必须传 -qmldir）
macdeployqt out/stage/<App>.app -qmldir=<source-qml-dir>

# 3. 核查加载路径：不得残留 /opt/homebrew、/Users/... 或构建机绝对路径
otool -L out/stage/<App>.app/Contents/MacOS/<App>
```

- Qt 6 CMake 项目可直接使用 `qt_generate_deploy_app_script()` / `qt_generate_deploy_qml_app_script()` 配合 `MACOSX_BUNDLE` 自动打包。
- **非 Qt 第三方 `.dylib`**：`macdeployqt` 不保证收全所有第三方动态库；若 `otool -L` 仍发现外部绝对路径，需拷贝进 `Contents/Frameworks/` 并用 `install_name_tool -change` 修正为 `@executable_path/../Frameworks/...` 或 `@rpath/...`。

## 3. Finder 启动 vs 终端启动（必测差异）

- **工作目录与环境变量差异**：从终端启动会继承你的 shell `PATH` 与当前工作目录；从 **Finder 双击启动** 时工作目录是 `/`，且不带开发机 shell 环境变量。
- **路径纪律**：所有只读资源放进 `Contents/Resources/` 通过 bundle 相对路径或 Qt `qrc:/` 读取；可写配置、SQLite 数据库与日志一律写入 macOS 标准用户目录（如 `~/Library/Application Support/<App>/`、`~/Library/Logs/<App>/`）。

## 4. 签名、公证与升级验收

- **按分发渠道决定**：仅当发布渠道要求时才对最终 `.app` 或 `.dmg`/归档执行代码签名（`codesign`）、公证（`notarytool`）和 `stapler staple`；开发阶段 ad-hoc 签名不等同于可分发的 Developer ID 签名。**任何签名后对 bundle 内文件的改动都会破坏签名，必须重签并重新校验 `codesign --verify --deep --strict`。**
- **验收**：从 staging 位置通过 Finder 启动执行一条代表性业务操作，校验菜单栏、焦点、多架构结果（不以单一架构代表 Universal/另一架构）及升级覆盖安装后用户数据保留。
