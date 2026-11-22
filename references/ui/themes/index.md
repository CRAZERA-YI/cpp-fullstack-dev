# UI 视觉主题总览（Presets + Native + Custom）

主题系统同时服务于 **C++ + Qt（Widgets / Quick）** 与 **C++ + Web**。先用下表选定方向，**优先运行 `python <skill_dir>/scripts/extract_theme.py <preset|path>` 提取精简语义 Token、CSS 变量、圆角与间距 JSON**（显著节省上下文）；仅在需要细查具体组件样式时，再读取对应 `DESIGN.md` 第 1 行至结束符 `---` 之间的 YAML Frontmatter（预设通常为 240~450 行，`rounded` / `spacing` / `components` 位于第 120 行之后），并在结束符 `---` 处停止，避免通读下文网页营销分析。

## 1. 主题模式与内置精选 Presets

| 标识 | 模式 / 调性 | 核心起点 Token (`canvas` / `surface` / `ink` / `accent`) | 适用场景 | 参考文件 |
| --- | --- | --- | --- | --- |
| `linear` | 深色高密度工作台 | `#010102` / `#0f1011` / `#f7f8f8` / `#5e6ad2` | IDE 工作台、监控、开发者控制台 | [linear/DESIGN.md](presets/linear/DESIGN.md) |
| `cursor` | 暖色浅底编辑器 | `#f7f7f4` / `#ffffff` / `#26251e` / `#f54e00` | 代码/文档编辑工具、AI 助手工作区 | [cursor/DESIGN.md](presets/cursor/DESIGN.md) |
| `notion` | 极简浅色内容与列表 | `#ffffff` / `#f6f5f4` / `#1a1a1a` / `#5645d4` | 笔记、知识库、列表-详情桌面工具 | [notion/DESIGN.md](presets/notion/DESIGN.md) |
| `vercel` | 高对比黑白开发平台 | `#ffffff` / `#fafafa` / `#171717` / `#0070f3` | Web 管理台、API/构建平台控制台 | [vercel/DESIGN.md](presets/vercel/DESIGN.md) |
| `stripe` | 清晰金融/数据仪表盘 | `#ffffff` / `#f6f9fc` / `#0d253d` / `#533afd` | 数据仪表盘、SaaS/运营全栈 Web | [stripe/DESIGN.md](presets/stripe/DESIGN.md) |
| `native` | 跟随宿主 OS 外观 | 使用 OS `QPalette` / 系统深浅色媒体查询 | 原生桌面工具、无自定义品牌诉求 | — |
| `<custom>` | 用户自定义主题 | 来自项目 `DESIGN.md` / `theme.json` 或 `custom/<id>/DESIGN.md` | 企业设计规范或个人定制风格 | [自定义主题接口](custom-interface.md) |

上述 5 份精选 `DESIGN.md` 源自 VoltAgent/awesome-design-md 精选子集，所附许可见 [LICENSE](presets/LICENSE)。若在 `presets/` 之外新增风格，请放入 `custom/` 目录而非直接修改 `presets/`。

### 预设 YAML 键与语义 Token 对照表

内置 `presets/*/DESIGN.md` 的顶层 YAML 键名与 [`assets/templates/DESIGN.md`](../../../assets/templates/DESIGN.md) 语义 Token 的统一映射如下（`stripe`/`vercel`/`notion`/`cursor` 局部缺失语义键时按相近中性灰/语义角色补齐）：

| `presets/*/DESIGN.md` YAML 键 | `assets/templates/DESIGN.md` 语义角色 | Web CSS Custom Property |
| --- | --- | --- |
| `canvas` | `bg.canvas` | `--bg-canvas` |
| `surface-1` / `canvas-soft` / `surface` / `surface-card` | `bg.surface` | `--bg-surface` |
| `surface-2` / `surface-3` / `canvas-soft-2` / `surface-soft` / `surface-strong` | `bg.elevated` | `--bg-elevated` |
| `ink` | `text.primary` | `--text-primary` |
| `ink-muted` / `ink-subtle` / `ink-secondary` / `ink-mute` / `body` / `charcoal` / `slate` / `muted` / `mute` | `text.secondary` | `--text-secondary` |
| `hairline` | `border.subtle` | `--border-subtle` |
| `primary` / `link` | `accent.primary` | `--accent-primary` |
| `primary-hover` / `primary-active` / `primary-pressed` / `primary-press` / `primary-deep` / `link-deep` | `accent.hover` | `--accent-hover` |
| `semantic-success` / `success` | `state.success` | `--state-success` |
| `warning` / `semantic-warning` | `state.warning` | `--state-warning` |
| `error` / `semantic-error` / `danger` | `state.danger` | `--state-danger` |

## 2. 将 `DESIGN.md` 映射到三端前端

原始 `DESIGN.md` 偏重网页分析，落地到实际工程时按以下原则裁剪：
- **桌面密度与字体适配**：把网页的大尺寸 Hero 字号压缩为桌面常规字阶（正文 `13–14px` / 标题 `16–20px`），**必须追加中文系统回退字体**（`"PingFang SC", "Microsoft YaHei UI", "Noto Sans CJK SC"`）。
- **无障碍与可读性**：选中态不能只靠色相区分，需叠加边界、背景层次或勾选/图标标记；检查禁用态、占位符与焦点边框（`1px`~`2px` 强调色）实际对比度。

### Qt Widgets 落地（作用域限定，禁止污染原生弹层）
- 先将画布、文字、选中态映射进窗口 `QPalette`，再为顶层窗口设唯一 `objectName`，把局部 QSS 限定在该作用域内：

```css
QWidget#workbenchRoot {
    background: #010102;
    color: #f7f8f8;
}

QWidget#workbenchRoot QLineEdit:focus {
    border: 1px solid #5e6ad2;
}
```

### Qt Quick 落地
- 使用集中式 `Theme` QML 单例（`pragma Singleton`）导出语义属性（`canvas`, `surface`, `textPrimary`, `accent`, `hairline`），禁止把十六进制颜色硬编码散布到各个 `.qml` 页面。

### Web 落地
- 在全局 CSS 根部定义语义化 CSS Custom Properties（`--bg-canvas`, `--bg-surface`, `--text-primary`, `--border-subtle`, `--accent-primary`），并在 Tailwind/组件样式中引用变量，确保切换主题只需改属性或类名。
