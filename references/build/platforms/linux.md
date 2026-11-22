# Linux 构建、动态依赖与图形会话验收

## 1. 工具链与 Qt 来源边界

- **原生构建与 WSL**：x86_64 工程默认用 GCC 或 Clang + Ninja + `x64-linux`；在 WSL 内做 Linux 原生构建时使用 Linux 预设与 Linux 工具链，不可混用 Windows 路径或二进制。
- **Qt 来源单一化**：明确选择 **发行版系统 Qt**（`-dev` 包）或 **vcpkg Qt** 之一，严禁同一个目标混用两套来源的头文件、共享库或 QPA 插件。
- **glibc / libstdc++ 基线**：产物必须在目标环境最老支持的发行版（或同基线容器）上编译与验收；仅在最新开发机跑通不证明旧发行版可运行。
- **多阶段容器交付（`C++ + Web` / `C++ + Python`）**：使用与目标运行时同 glibc 基线的多阶段 Dockerfile：构建阶段装编译器/vcpkg/Node 并执行 `cmake --install --prefix /opt/app`；运行阶段仅从精简基础镜像（含 `libstdc++`/OpenSSL/CA 证书及非 root 用户）拷贝 `/opt/app` staging 产物，不带入构建工具链与源码树。

## 2. RPATH、Staging 安装与动态依赖排查

Linux 没有通用的 `windeployqt` 替代品，必须在 `CMakeLists.txt` 中做好 `install()` 规则与相对 RPATH：

```cmake
# 安装期使用相对可执行文件的 $ORIGIN RPATH，兼容 lib/lib64 与 multiarch
set_target_properties(<app> PROPERTIES
    INSTALL_RPATH "$ORIGIN/../${CMAKE_INSTALL_LIBDIR}"
    BUILD_WITH_INSTALL_RPATH FALSE
)
```

- **检查真实产物依赖**：优先用 `readelf -d <stage-dir>/bin/<app>` 检查 `NEEDED` 与 `RUNPATH`/`RPATH`（注意 `ldd` 只反映当前宿主机解析结果，会隐藏缺失随包依赖的假象）。
- **禁止依赖 `LD_LIBRARY_PATH`**：用户桌面入口或服务启动不应靠手动导出 `LD_LIBRARY_PATH` 救场；缺失插件时可临时设置 `QT_DEBUG_PLUGINS=1` 定位后还原环境。

## 3. 无头测试（Offscreen / Xvfb）vs 真实桌面会话

| 图形后端 / 环境 | 适用范围 | 局限性（不可替代真实桌面验收） |
| --- | --- | --- |
| `QT_QPA_PLATFORM=offscreen` | 纯 Qt 逻辑、信号槽、无窗口管理器的快速 CI 冒烟 | 不加载 `xcb`/`wayland` 真实插件，无法验证键盘焦点、缩放与原生弹出菜单。 |
| `xvfb-run`（X11 虚拟帧缓冲） | 验证 X11 渲染与基础窗口生命周期 | 仅覆盖 X11 语义，不等同于 Wayland 会话与桌面管理器交互。 |
| 真实 X11 / Wayland 会话 | 最终桌面交付必查（焦点、缩放、多屏、窗口关闭重开） | 交付证据中必须注明所测发行版、架构、Qt 来源及图形后端（`X11` 或 `Wayland`）。 |

## 4. 验收清单

- 从 `cmake --install` 生成的 staging 目录（而非 build tree）启动 Release 二进制，检查 `lib/`、Qt `plugins/platforms/` 与资源文件大小写（Linux 严格区分文件名大小写！）。
- 验证可执行权限、服务 systemd/普通用户目录写入权限（`XDG_DATA_HOME` / `QStandardPaths`）及至少一次真实会话窗口关闭/重启。
