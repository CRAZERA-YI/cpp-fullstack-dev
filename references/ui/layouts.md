# UI 交互四态与桌面/Web 布局模式

同时适用于 **C++ + Qt（Widgets / Quick）** 与 **C++ + Web（CSS Flex / Grid）**。布局控制结构、伸缩与窗口响应；颜色、字号与状态语义见 [主题总览](themes/index.md)。

## 1. 通用交互四态与防过期准则

任何异步数据视图（表格、详情面板、仪表盘）必须显式处理以下四态：

| 状态 | 界面行为与可操作性 |
| --- | --- |
| **空状态** | 说明当前无选中项或无数据，保留明确的创建/导入/刷新主入口。 |
| **加载 / 保存中** | 展示明确进度反馈；禁止同一非幂等提交双击连发，同时保留取消或安全关闭窗口的路径。 |
| **成功** | 更新真实生效后的数据，并尽量维持用户当前选中项、滚动位置与键盘焦点。 |
| **错误** | 区分校验/权限/网络/存储失败，**保留用户输入允许重试**并给出下一步操作，不弹原始栈跟踪。 |

**防过期覆盖**：切走条目、关闭页面或重新发起请求时递增 `requestGeneration`；旧请求晚到返回时校验 `(requestGeneration == m_activeGeneration)` 且对象未销毁再刷新界面。

## 2. 八大高频布局模式

| 标识 | 适用场景 | Qt Widgets / Quick 核心实现 | Web CSS 对应结构 |
| --- | --- | --- | --- |
| `ide-workbench` | 中央主编辑/工作区 + 侧边/底部可停靠工具窗 | `QMainWindow` + `QDockWidget`（按 UI 版本调 `saveState`/`restoreState`，校验多屏几何可见性；菜单复用 `toggleViewAction()`）。 | CSS Grid (`grid-template-areas`) + 可拖拽调整列宽与折叠抽屉 |
| `list-detail` | 扁平列表选择条目并查看/编辑详情 | `QSplitter` (`setChildrenCollapsible(false)`) + `QListView`/`QTableView`；用业务 ID 记选中态，代理模型索引需先映射到源模型。 | 左右 Flex/Grid 分栏；窄屏切换单页详情并保留返回位置 |
| `three-pane` | 分类导航 + 条目列表 + 详情三栏浏览 | 嵌套 `QSplitter`（分别为两级 splitter 设置稳定 `objectName`），独立记忆分类选中态与滚动位置；窄屏折叠次要栏。 | 3 列 CSS Grid；断点下折叠导航为抽屉 |
| `canvas-inspector` | 中央画布交互 + 侧栏属性检查器 | `QGraphicsView` / Quick 场景 + 单一选择模型；视口→场景→对象坐标分段转换；回填属性用 `QSignalBlocker` 防循环提交；拖动结束合并为单次撤销命令。 | `<canvas>` / SVG + 绝对/侧边属性栏（统一单向状态事务） |
| `ribbon-document` | 单文档编辑，命令按任务分组且随选区变化 | 围绕统一 `QAction` 模型组织菜单、快捷键与工具栏，处理器读取当前活动文档而非创建期缓存指针。 | 顶部命令条 + `overflow-menu` 自适应收纳（保持快捷键与 `aria-label`） |
| `dashboard` | 并行监控多个指标卡片、图表与异常 | `QGridLayout` / Quick `GridLayout`；卡片异常状态结合文字+图标表达；各卡片独立刷新并在失败时保留上次有效读数（无数据不可画成 `0`）。 | `grid-template-columns: repeat(auto-fit, minmax(260px, 1fr))` |
| `split-view` | 差异对比、编辑与实时预览、双日志对照 | `QSplitter`（等权拉伸 `setStretchFactor(..., 1)`）；仅在初次布局完成后恢复比例；联动滚动以语义锚点+更新源标记防递归跳动。 | 双栏 `1fr 1fr` Flex/Grid；窄屏转为上下分栏或 Tab |
| `wizard` | 多步骤顺序向导，上游选项决定后续分支 | `QWizardPage` / Quick 显式步骤状态机；所有输入存在共享业务模型中，页面 `isComplete()` 据模型计算并触发 `completeChanged()`。 | 多步 Form 状态机（Zod/Schema 校验每步门禁） |

## 3. 代码示例：符合规范的向导页与分隔条

```cpp
// 符合 .clang-format 与 m_ 前缀约定：基于共享模型判定下一步可用性
bool SourcePage::isComplete() const {
    return !m_sourceEdit->text().trimmed().isEmpty()
        && m_validationState == ValidationState::Valid;
}
```

- **分隔条恢复时机**：`QSplitter::restoreState()` 与 `QMainWindow::restoreState()` 只能在全部子控件/Dock 创建完成且窗口获得真实尺寸后调用，严禁在每次 `resizeEvent` 覆盖用户拖动比例。
- **验证要求**：在正常尺寸、最小窗口尺寸、高分屏缩放、纯键盘 `Tab` 导航以及中文长标题下验证不截断、不重叠、焦点可见。
