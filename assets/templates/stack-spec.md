# <Library / Stack Name>

适用范围：<CMake / qmake / Python / Web 等构建与适用边界>。

## 1. 适用场景与选型边界

- **何时选用**：说明核心优势及典型场景。
- **何时避免 / 替代方案**：说明不适用情形及同定位替代库。

## 2. 构建与接入

- 依赖声明（如 `vcpkg.json` port/feature、`pip`/`npm` 包名或 CMake `find_package`）。
- 实际 CMake 导出目标（如 `Pkg::Target`）及 `PUBLIC` vs `PRIVATE` 链接边界。

## 3. 高频踩坑（反模式 vs 正解）

- 聚焦真实项目中高频出错的生命周期、线程/事件循环、编码、ABI 或错误处理陷阱。
- 如附代码片段，必须符合 `assets/templates/.clang-format` 与 `cpp-standards-and-abi.md` 命名规范。

```cpp
// 最小、完整、符合本 Skill 编码规范的反模式/正解示例
```

## 4. 验证要点

- 列出构建配置、单元测试、跨边界集成测试或异常场景的具体可观察验收命令与条件。
