# Dear ImGui 桌面工具界面规范

适用范围：CMake（vcpkg port `imgui` 配合后端 features，如 `imgui[docking-experimental,glfw-binding,opengl3-binding]` 或 `sdl2` / `dx11` / `vulkan`）。

## 1. 适用场景与选型边界

- **何时选用**：游戏/图形调试器、性能剖析器（Profiler）、数据可视化工具、工业/算法内部调试面板等需要 60fps 实时刷新、低依赖的桌面工具界面。
- **何时避免 / 替代方案**：需要传统 OS 原生控件、复杂富文本编辑器、系统无障碍（Screen Reader）、精细中文输入法体验与标准商业桌面排版时，优先选 [Qt Widgets](qt-widgets.md) 或 [Qt Quick](qt-quick.md)。

## 2. 构建与接入

- 在 `vcpkg.json` 显式勾选对应平台与渲染后端 features（如 `glfw-binding` + `opengl3-binding`；Windows 原生工具可选 `win32-binding` + `dx11-binding`），不要手动把上游 `backends/*.cpp` 重复拷贝一份导致符号冲突。
- 需要停靠面板（DockSpace）与多视口拖拽时使用 `imgui` docking 分支并在初始化打开 `ImGuiConfigFlags_DockingEnable`。

## 3. 高频踩坑（反模式 vs 正解）

1. **中文与高分屏缩放乱码/模糊（最高频故障）**：
   - ImGui 默认内嵌字体仅含 ASCII，**中文会全部显示为 `???`**！初始化必须调用 `io.Fonts->AddFontFromFileTTF(...)` 加载系统或打包的中文字体（如微软雅黑/苹方/思源黑体），并传入 `io.Fonts->GetGlyphRangesChineseSimplifiedCommon()`（或完整汉字集）。
   - High-DPI 下同步按系统缩放比例缩放字号与 `style.ScaleAllSizes(dpiScale)`，不可仅放大窗口尺寸而不放大字体和间距。
2. **ID 冲突导致同页控件互相联动**：
   - 循环生成同类按钮或同名标签（如多个 `"Delete"` 按钮）共享相同 label 会发生状态串扰。必须用 `"Delete##row_12"` 隐藏后缀或成对的 `ImGui::PushID(rowId)` / `ImGui::PopID()` 隔离作用域。
3. **在每帧渲染循环中阻塞 IO 或每帧重分配内存**：
   - 渲染主循环（Render Loop）内严禁做文件解析、SQLite/HTTP 同步查询或全量字符串拼接；耗时任务放后台线程，每帧仅通过双缓冲/互斥锁抓取快照绘制（列表超大时使用 `ImGuiListClipper` 虚拟裁剪）。
4. **生命周期与主题映射**：
   - 严格配对 `ImGui::Begin()` 与 `ImGui::End()`（即使 `Begin()` 返回 `false` 也要调用 `End()`！而 `BeginPopup`/`BeginChild` 等成对规则各有差异，不可混淆）。
   - 若套用本 Skill 的 `DESIGN.md` 主题，将语义颜色集中映射进 `ImGuiStyle::Colors[]` 与 `FrameRounding` / `WindowBorderSize`。

```cpp
// 显式加载中文字体并做作用域 ID 隔离
ImGuiIO& io = ImGui::GetIO();
io.Fonts->AddFontFromFileTTF(
    fontPath.c_str(), kBaseFontSizePx * dpiScale, nullptr,
    io.Fonts->GetGlyphRangesChineseSimplifiedCommon());

for (int index = 0; index < static_cast<int>(items.size()); ++index) {
    ImGui::PushID(items[index].id);
    if (ImGui::Button("删除")) {
        requestDeleteItem(items[index].id);
    }
    ImGui::PopID();
}
```

## 4. 验证要点

- 启动真实渲染窗口验证：中文长文本无 `???` 乱码、150%/200% DPI 缩放清晰、列表含上千行不掉帧、同页多个相似操作按钮互不串扰，以及关闭重开后 `imgui.ini` 布局可正常恢复且异常损坏时有默认兜底。
