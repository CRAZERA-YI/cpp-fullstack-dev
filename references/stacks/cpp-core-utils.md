# C++ 通用基础库规范（fmt / CLI11 / YAML & TOML / OpenSSL / Eigen & OpenCV）

适用范围：CMake + vcpkg（均作为常用基础设施组合接入 `C++ + Web`、`C++ + Qt`、`C++ + Python` 与纯 C++ 工具）。

## 1. 文本格式化与命令行解析（`fmt` / `CLI11`）

- **`fmt` (`fmt::fmt`)**：
  - 优先使用编译期格式串检查（`fmt::format`）；数值转换需要跨语言/协议稳定性时用不受本地 `LC_NUMERIC` 影响的安全格式。
  - 与 `spdlog` 共用时，在 `CMakeLists.txt` 统一启用 `SPDLOG_FMT_EXTERNAL` 并链接同一份 `fmt::fmt`，防止 `spdlog` 内置副本与独立 `fmt` 在链接期冲突或产生两套 ABI。
- **`CLI11` (`CLI11::CLI11`)**：
  - 使用 `add_subcommand()` 拆分多子命令服务；用 `CLI11_PARSE(app, argc, argv)` 确保 `--help` / 参数校验错误返回标准退出码；支持环境变量与配置文件兜底时注意优先级（命令行参数 > 环境变量 > 配置文件 > 默认值）。

## 2. 配置文件解析（`yaml-cpp` / `toml++`）

- **`yaml-cpp` (`yaml-cpp::yaml-cpp`)**：
  - 读取节点前必须校验 `node.IsDefined()`、`!node.IsNull()` 与类型（`IsScalar()` / `IsSequence()` / `IsMap()`），并在入口处统一捕获 `YAML::Exception`（否则缺字段时 `.as<T>()` 直接抛未捕获异常崩掉服务）。
  - 留意 YAML 1.1 “Norway Problem”：未加引号的 `NO` / `off` / `on` / `yes` 会被解析为布尔值而非字符串。
- **`toml++` (`tomlplusplus::tomlplusplus`)**：
  - 用 `tbl["section"]["key"].value<std::string>()` 返回 `std::optional` 做显式校验；配置文件需要保留中文时按 UTF-8 读入（Windows 下防止直接传窄字符本地路径）。

## 3. 密码学与 TLS（`OpenSSL::SSL` / `OpenSSL::Crypto`）

- **使用 OpenSSL 3.x `EVP_*` 接口**：新代码禁用已废弃的 OpenSSL 1.1 底层函数（如 `MD5_Init`、`SHA256_Init`、`RSA_public_encrypt`），统一使用 `EVP_DigestInit_ex` / `EVP_CIPHER_CTX` 与现代 AEAD（AES-GCM / ChaCha20-Poly1305）。
- **RAII 管理句柄**：所有 `EVP_MD_CTX*`、`EVP_CIPHER_CTX*`、`BIO*`、`X509*` 包装进带专用 deleter（如 `EVP_MD_CTX_free`）的 `std::unique_ptr`，避免错误分支内存泄漏。
- **Windows / Linux CA 证书路径**：Linux/macOS 可调用 `SSL_CTX_set_default_verify_paths()`；**但 OpenSSL 在 Windows 下调用该函数默认不会读取 Windows 系统证书存储区**（仅查编译期 `OPENSSLDIR` 或环境变量）。Windows 交付需随包附带可信 CA bundle（`cacert.pem` 配合 `SSL_CTX_load_verify_locations()`）、启用 OpenSSL 3.2+ `winstore` / CryptoAPI（`CertOpenSystemStore("ROOT")`）导入系统根证书，或直接使用 Schannel。

## 4. 矩阵计算与视觉处理（`Eigen` / `OpenCV`）

- **`Eigen` (`Eigen3::Eigen`)**：
  - **经典 `auto` 悬空引用陷阱**：Eigen 运算符返回懒惰求值表达式模板（Expression Template），如果写出 `auto m = (a * b).transpose();`，其中间临时矩阵在分号处已被销毁，`m` 成为悬空引用！**中间表达式必须声明显式矩阵类型（如 `Eigen::MatrixXd m = ...;`）或结尾调用 `.eval()`。**
  - 性能评估必须在 `Release`（`-O2`/`-O3` + 对应 SIMD 编译选项）下进行，Debug 模式禁用内联时 Eigen 会慢数十倍。
- **`OpenCV` (`opencv_core` 等按模块链接)**：
  - **只链接实际用到的组件**（如 `opencv_core`、`opencv_imgproc`、`opencv_imgcodecs`），避免拖入整个全量模块。
  - `cv::Mat` 赋值与传参为**浅拷贝共享引用计数**；异步投递给后台线程或需要修改副本前必须显式 `.clone()`。
  - 与 Qt `QImage` 或 Python NumPy 桥接时，务必显式核对颜色通道顺序（OpenCV 默认 **BGR**，Qt/Web/PIL 默认 **RGB**）与行对齐步长 `step`（`QImage::Format_BGR888` 或显式 `cvtColor`）。
  - Windows 分发记得随包拷贝匹配的 `opencv_world*.dll` 或分模块 DLL。

## 5. 验证要点

- 覆盖无效配置/参数回归测试、ASan 跑 `Eigen` 表达式与 `OpenSSL` RAII 路径、BGR↔RGB 图像桥接像素级核对，以及脱离构建目录的动态库启动检查。
